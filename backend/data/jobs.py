import asyncio, uuid
from enum import Enum
from typing import Dict, Optional
from pathlib import Path

class JobType(Enum):
    UPLOAD = 1
    DOWNLOAD = 2

class UploadJob:
    def __init__(self, file_path: str | Path, file_id: str, file_bytes: int, total_chunks: int, chunk_size: int):
        self.queue = asyncio.Queue()
        self.type = JobType.UPLOAD
        self.file_id = file_id
        self.file_path = Path(file_path)
        self.file_bytes = file_bytes
        self.total_chunks = total_chunks
        self.chunk_size = chunk_size
        self.chunk_paths = []
        self.status = "queued" # queued, splitting_file, allocating_space, authenticating <-> uploading_chunks, cleaning_temp, completed, failed
        
        self.chunks_telemetry: Dict[int, dict] = {
            i: {
                "chunk_index": i,
                "status": "queued",  # queued, uploading, completed, failed
                "bytes_uploaded": 0,
                "total_bytes": 0
            } for i in range(total_chunks)
        }
    
    def get_snapshot(self):
        return {
            "status": self.status,
            "chunks_telemetry": list(self.chunks_telemetry.values())
        }
    
    async def emit_progress(self):
        await self.queue.put(self.get_snapshot())
    
class DownloadJob:
    def __init__(self, output_dir: str | Path, file_name: str, file_bytes: int, chunks_info: list[(str, int)], chunk_prefix: str = ""):
        self.queue = asyncio.Queue()
        self.type = JobType.DOWNLOAD
        self.file_name = file_name
        self.chunk_prefix = chunk_prefix
        self.output_dir = Path(output_dir)
        self.file_bytes = file_bytes
        self.total_chunks = len(chunks_info)
        self.chunk_paths = []
        self.status = "queued" # queued, processing_metadata, fetching_chunks, downloading_chunks, merging_chunks, cleaning_temp, completed, failed
        
        self.chunks_telemetry: Dict[int, dict] = {
            i: {
                "chunk_index": i,
                "status": "queued",  # queued, downloading, completed, failed
                "download_url": c[0],
                "bytes_downloaded": 0,
                "total_bytes": c[1]
            } for i, c in enumerate(chunks_info)
        }
    
    def get_snapshot(self):
        return {
            "status": self.status,
            "chunks_telemetry": list(self.chunks_telemetry.values())
        }

    async def emit_progress(self):
        await self.queue.put(self.get_snapshot())

class JobManager:
    def __init__(self):
        self._upload_jobs: Dict[str, UploadJob] = {}
        self._download_jobs: Dict[str, DownloadJob] = {}

    def register_upload_job(self, file_path: str | Path, file_id: str, file_bytes: int, total_chunks: int, chunk_size: int) -> str:
        job_id = uuid.uuid4().hex
        self._upload_jobs[job_id] = UploadJob(file_path, file_id, file_bytes, total_chunks, chunk_size)
        return job_id
    
    def register_download_job(self, output_dir: str | Path, file_name: str, file_bytes: int, chunks_info: list[(str, int)], chunk_prefix: str = "") -> str:
        job_id = uuid.uuid4().hex
        self._download_jobs[job_id] = DownloadJob(output_dir, file_name, file_bytes, chunks_info, chunk_prefix)
        return job_id

    def get_job(self, type: JobType, job_id: str) -> Optional[UploadJob | DownloadJob]:
        match type:
            case JobType.UPLOAD: return self._upload_jobs.get(job_id)
            case JobType.DOWNLOAD: return self._download_jobs.get(job_id)

    def remove_job(self, type: JobType, job_id: str):
        if type == JobType.UPLOAD and job_id in self._upload_jobs:
            del self._upload_jobs[job_id]
        elif type == JobType.DOWNLOAD and job_id in self._download_jobs:
            del self._download_jobs[job_id]
    