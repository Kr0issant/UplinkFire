import asyncio, re, math, glob
import playwright.async_api as pw
from pathlib import Path
from tqdm import tqdm
from fileops import merger, splitter

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

        except Exception as e:
            print(f"Error wile uploading file: {e}")
            # self.db.delete_file(file_id)
            # self.db.delete_chunks(file_id = file_id)

    async def _upload_chunks(self, chunk_paths: str | Path, ):
        pass

    async def _upload_chunk_in_context(self, context: pw.BrowserContext, chunk_path: str | Path) -> str:
        download_url = ""
        timeout_duration = self.db.get_setting("timeout_duration", int) * 1000
        chunk_path = Path(chunk_path)

        page = await context.new_page()
        try:
            await page.goto("https://app.mediafire.com/folder/myfiles", timeout = timeout_duration)

            await page.get_by_role("button", name="Upload files").click()
            await page.locator('input[type="file"]').set_input_files(chunk_path)
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

    async def _monitor_upload(page):
        pbar = tqdm(total=100, desc="Uploading", unit="%")
        last_percentage = 0

        while True:
            is_completed = await page.locator('div:has-text("Upload Completed")').is_visible()
            if is_completed:
                pbar.update(100 - last_percentage)
                break
                
            try:
                percentage_text = await page.locator('div[dir="auto"]:text-matches("%")').first.text_content(timeout=1000)
                current_percentage = int(re.search(r'\d+', percentage_text).group())
                
                if current_percentage > last_percentage:
                    pbar.update(current_percentage - last_percentage)
                    last_percentage = current_percentage
                    
            except Exception:
                pass
                
            await asyncio.sleep(0.2)
            
        pbar.close()
        return