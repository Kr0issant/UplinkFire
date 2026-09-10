from fileops import merger
from pathlib import Path
import asyncio
import playwright.async_api as pw
from data.jobs import JobType, DownloadJob
from data.dpaste import dpaste_to_dict

class DownloadMixin:
    async def download_file_id_to_job(self, file_id: str, output_dir: str | Path) -> str:
        file = self.db.get_file(file_id)
        if not file:
            raise Exception(f"File with id {file_id} not found in database")
        file_name = file["file_name"]
        file_size = file["size"]

        chunks = sorted(self.db.get_chunks(file_id=file_id), key=lambda c: c["chunk_no"])
        chunks_info = [(c["download_url"], c["size"]) for c in chunks]

        job_id = self.job_manager.register_download_job(output_dir, file_name, file_size, chunks_info, file_id)
        return job_id

    async def download_file_url_to_job(self, file_url: str, output_dir: str | Path) -> str:
        file = dpaste_to_dict(file_url)
        file_name = file["file_name"]
        file_size = file["size"]
        chunk_prefix = file["chunk_prefix"]

        chunks = sorted(file["chunks"], key=lambda c: c["chunk_no"])
        chunks_info = [(c["download_url"], c["size"]) for c in chunks]

        job_id = self.job_manager.register_download_job(output_dir, file_name, file_size, chunks_info, chunk_prefix)
        return job_id

    async def download_file_from_job(self, job_id: str):
        temp_dir_path = Path(self.db.get_setting("temp_dir_path"))
        job: DownloadJob = self.job_manager.get_job(JobType.DOWNLOAD, job_id)
        if not job:
            print(f"Download job {job_id} not found")
            return

        try:
            total_chunks = job.total_chunks
            padding_width = len(str(total_chunks))
            chunk_prefix = job.chunk_prefix
            job.chunk_paths = [
                temp_dir_path / f"{chunk_prefix}.part_{i:0{padding_width}d}"
                for i in range(total_chunks)
            ]

            job.status = "downloading_chunks"
            await job.emit_progress()

            browser = await self.start_browser(headless=True)
            context = await self.new_context(browser)

            try:
                for chunk_no in range(total_chunks):
                    await self._download_chunk(context, job_id, chunk_no)
            finally:
                await context.close()

            failed_chunks = [
                i for i in range(total_chunks)
                if job.chunks_telemetry[i]["status"] != "completed" or not job.chunk_paths[i].exists()
            ]

            if len(failed_chunks) > 0:
                print(f"Download failed for {len(failed_chunks)} chunks in job {job_id}")
                job.status = "failed"
                await job.emit_progress()
                return

            job.status = "merging_chunks"
            await job.emit_progress()

            output_dir = Path(job.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file_path = output_dir / job.file_name

            search_pattern = str(temp_dir_path / f"{chunk_prefix}.part_*")
            merger.merge_chunks(search_pattern, output_file_path)

            job.status = "cleaning_temp"
            await job.emit_progress()

            for chunk_path in job.chunk_paths:
                try:
                    chunk_path.unlink(missing_ok=True)
                except Exception as e:
                    print(f"Failed to delete temp chunk {chunk_path}: {e}")

            job.status = "completed"
            await job.emit_progress()
            print(f"File {job.file_name} downloaded successfully to {output_file_path}")

        except Exception as e:
            print(f"Error while downloading file: {e}")
            job.status = "failed"
            await job.emit_progress()

    async def _download_chunk(self, context: pw.BrowserContext, job_id: str, chunk_no: int):
        job: DownloadJob = self.job_manager.get_job(JobType.DOWNLOAD, job_id)
        if not job:
            return
        download_url = job.chunks_telemetry[chunk_no]["download_url"]
        chunk_path = job.chunk_paths[chunk_no]
        timeout_duration = self.db.get_setting("timeout_duration", int) * 1000

        job.chunks_telemetry[chunk_no]["status"] = "downloading"
        await job.emit_progress()

        page = await context.new_page()
        try:
            await page.goto(download_url, timeout=timeout_duration)

            async with page.expect_download(timeout=timeout_duration) as download_info:
                await page.get_by_role("button", name="Download file").first.click(timeout=timeout_duration)

            download = await download_info.value
            download_stream = download.create_read_stream()

            await self._monitor_download(download_stream, chunk_path, job_id, chunk_no)

            job.chunks_telemetry[chunk_no]["status"] = "completed"
            await job.emit_progress()
        except Exception as e:
            print(f"Download of chunk {chunk_no} ({download_url}) failed: {e}")
            job.chunks_telemetry[chunk_no]["status"] = "failed"
            await job.emit_progress()
            raise e
        finally:
            await page.close()

    async def _monitor_download(self, download_stream, download_path: Path, job_id: str, chunk_no: int):
        job: DownloadJob = self.job_manager.get_job(JobType.DOWNLOAD, job_id)
        if not job:
            return
        bytes_downloaded = 0
        last_emit_time = asyncio.get_event_loop().time()

        try:
            with open(download_path, "wb") as f:
                while True:
                    chunk = download_stream.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    
                    job.chunks_telemetry[chunk_no]["bytes_downloaded"] = bytes_downloaded
                    now = asyncio.get_event_loop().time()
                    if now - last_emit_time > 0.25:
                        await job.emit_progress()
                        last_emit_time = now
        except Exception as e:
            raise e