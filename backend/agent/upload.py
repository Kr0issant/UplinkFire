import asyncio, re, math, glob
import playwright.async_api as pw
from pathlib import Path
from tqdm import tqdm
from fileops import splitter

class UploadMixin:
    async def upload_file(self, file_path: str | Path):
        file_path = Path(file_path)
        temp_dir_path = Path(self.db.get_setting("temp_dir_path"))
        chunk_size = self.db.get_setting("chunk_size", int) * 1024 * 1024
        file_id = ""

        try:
            if not file_path.is_file():
                raise Exception(f"File: {file_path} doesn't exist")
            
            file_size = file_path.stat().st_size
            total_chunks = math.ceil(file_size / chunk_size) if file_size > 0 else 1

            file_id = self.db.add_file(file_path.name, file_size, chunk_size, total_chunks)

            splitter.split_file(file_path, temp_dir_path, chunk_size, file_id)
            chunk_paths = sorted([Path(p) for p in glob.glob(str(temp_dir_path / f"{file_id}.part_*"))])

            await self._upload_chunks(chunk_paths, file_id)

            await self._upload_chunks(chunk_paths, file_id)
            successful_set = {c["chunk_no"] for c in self.db.get_chunks(file_id=file_id)}

            successful_chunk_nos = [n for n in range(total_chunks) if n in successful_set]
            unsuccessful_chunk_nos = [n for n in range(total_chunks) if n not in successful_set]

            if len(unsuccessful_chunk_nos > 0):
                print(f"File {file_id} ({file_path.name}) uploaded [{len(successful_chunk_nos)}/{len(total_chunks)}] chunks successfully")
                print(f"Retrying for {len(unsuccessful_chunk_nos)} chunks...")
                # WIP (retry unsuccessful chunks)
            else:
                print(f"File {file_id} ({file_path.name}) uploaded successfully")

        except Exception as e:
            print(f"Error wile uploading file: {e}")
            # self.db.delete_file(file_id)
            # self.db.delete_chunks(file_id = file_id)

    async def _upload_chunks(self, chunk_paths: list[Path], file_id: str):
        strategy = self.db.get_setting("upload_strategy", str, "least_scatter")
        browser = await self.start_browser(headless=True)
        
        chunk_tasks = [
            {"chunk_no": i + 1, "path": p, "size": p.stat().st_size} 
            for i, p in enumerate(chunk_paths)
        ]
        
        assigned_plan = []  # List of tuples: (account_id, [list of chunk dicts])

        # Create a working copy of account spaces in memory to plan accurately without premature DB writes
        accounts_cache = {a["id"]: dict(a) for a in self.db.get_accounts()}

        def get_or_create_account(min_space: int) -> dict:
            # Check cache first for an eligible account
            eligible = [a for a in accounts_cache.values() if a["free_space"] >= min_space]
            if eligible:
                if strategy == "least_scatter":
                    # Pick the roomiest account
                    acc = max(eligible, key=lambda x: x["free_space"])
                else:
                    # Pick the tightest fit (least leftovers)
                    acc = min(eligible, key=lambda x: x["free_space"])
                return acc
            
            # If none fit, register a new account synchronously via a temporary context
            # (Note: since we are inside an async function, we handle registration creation outside or sequentially)
            return None

        if strategy == "least_scatter":
            current_chunks = list(chunk_tasks)
            while current_chunks:
                total_remaining_size = sum(c["size"] for c in current_chunks)
                acc = get_or_create_account(total_remaining_size)
                
                if not acc and accounts_cache:
                    # Fallback to the account with the most space available if none fit all
                    acc = max(accounts_cache.values(), key=lambda x: x["free_space"])

                if not acc or acc["free_space"] < current_chunks[0]["size"]:
                    headed_browser = await self.start_browser(headless=False)
                    context = await self.new_context(headed_browser)
                    new_id = await self.register(context)
                    await context.close()
                    new_acc = self.db.get_account(new_id)
                    accounts_cache[new_id] = dict(new_acc)
                    acc = accounts_cache[new_id]

                fit_chunks = []
                remaining_next = []
                for c in current_chunks:
                    if acc["free_space"] >= c["size"]:
                        fit_chunks.append(c)
                        acc["free_space"] -= c["size"]
                    else:
                        remaining_next.append(c)
                
                if not fit_chunks:
                    fit_chunks.append(current_chunks[0])
                    acc["free_space"] -= current_chunks[0]["size"]
                    remaining_next = current_chunks[1:]

                assigned_plan.append((acc["id"], fit_chunks))
                current_chunks = remaining_next

        elif strategy == "least_leftovers":
            for chunk in chunk_tasks:
                acc = get_or_create_account(chunk["size"])
                
                if not acc:
                    headed_browser = await self.start_browser(headless=False)
                    context = await self.new_context(headed_browser)
                    new_id = await self.register(context)
                    await context.close()
                    new_acc = self.db.get_account(new_id)
                    accounts_cache[new_id] = dict(new_acc)
                    acc = accounts_cache[new_id]
                
                acc["free_space"] -= chunk["size"]
                
                existing_entry = next((item for item in assigned_plan if item[0] == acc["id"]), None)
                if existing_entry:
                    existing_entry[1].append(chunk)
                else:
                    assigned_plan.append((acc["id"], [chunk]))

        # Execute the upload plan and perform a single authoritative DB update per chunk
        for account_id, chunks in assigned_plan:
            context = await self.new_context(browser)
            try:
                await self.login(context, account_id)
                for c in chunks:
                    download_url = await self._upload_chunk_in_context(context, c["path"])
                    if download_url:
                        self.db.add_chunk(
                            file_id=file_id,
                            account_id=account_id,
                            chunk_no=c["chunk_no"],
                            size=c["size"],
                            download_url=download_url
                        )
                        # Update database free space accurately once per successful upload
                        current_acc = self.db.get_account(account_id)
                        new_space = max(0, current_acc["free_space"] - c["size"])
                        self.db.update_account_free_space(account_id, new_space)
                        print(f"Chunk {c["chunk_no"]} upload for file: {file_id} successful")
            except Exception as e:
                print(f"Failed upload batch for account {account_id}: {e}")
            finally:
                await context.close()

    async def _upload_chunk_in_context(self, context: pw.BrowserContext, chunk_path: str | Path) -> str:
        download_url = ""
        timeout_duration = self.db.get_setting("timeout_duration", int) * 1000
        chunk_path = Path(chunk_path)

        page = await context.new_page()
        try:
            await page.goto("https://app.mediafire.com/folder/myfiles", timeout = timeout_duration)

            await asyncio.sleep(0.5)
            await page.evaluate("""() => {
                const dialog = document.querySelector('div[role="dialog"]');
                if (dialog && dialog.parentElement && dialog.parentElement.parentElement) {
                    dialog.parentElement.parentElement.remove();
                } else if (dialog) {
                    dialog.remove();
                }
            }""")

            await page.get_by_role("button", name="Upload files").click()
            file_input = page.locator('input[type="file"]').first
            await file_input.wait_for(state="attached", timeout=timeout_duration)
            await file_input.set_input_files(chunk_path, timeout=timeout_duration)

            await page.get_by_role("button", name="Start upload").click()

            await self._monitor_upload(page)

            await page.locator('span:has-text("Copy Link")').click()
            await asyncio.sleep(0.5)
            download_url = await page.evaluate("navigator.clipboard.readText()")
        except Exception as e:
            print(f"Upload of chunk: {chunk_path} failed: {e}")
        finally:
            await page.close()

        return download_url

    async def _monitor_upload(self, page: pw.Page) -> bool:
        pbar = tqdm(total=100, desc="Uploading", unit="%")
        last_percentage = 0
        timeout_duration = self.db.get_setting("timeout_duration", int) * 1000

        while True:
            is_completed = await page.get_by_text("Upload Completed").is_visible(timeout=timeout_duration)
            if is_completed:
                pbar.update(100 - last_percentage)
                break
                
            try:
                percentage_locator = page.locator('div[dir="auto"]:text-matches("%")').first
                if await percentage_locator.is_visible(timeout=timeout_duration):
                    percentage_text = await percentage_locator.text_content(timeout=timeout_duration)
                    current_percentage = int(re.search(r'\d+', percentage_text).group())
                    
                    if current_percentage > last_percentage:
                        pbar.update(current_percentage - last_percentage)
                        last_percentage = current_percentage
                    
            except Exception as e:
                pbar.close()
                raise e
                
            await asyncio.sleep(0.2)
        pbar.close()
        return