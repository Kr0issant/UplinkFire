import asyncio, uuid
from enum import Enum
from typing import Dict, Optional

class JobType(Enum):
    UPLOAD = 1
    DOWNLOAD = 2

class Job:
    def __init__(self, type: JobType, total_chunks: int):
        self.queue = asyncio.Queue()
        self.type = type
        self.total_chunks = total_chunks
        # UPLOAD:   queued, splitting_file, authenticating <-> uploading_chunks, saving_metadata, cleaning_temp, completed, failed
        # DOWNLOAD: queued, processing_metadata, fetching_chunks, downloading_chunks, merging_chunks, cleaning_temp, completed, failed
        self.status = "queued"
        
        self.chunks_telemetry: Dict[int, dict] = {
            i: {
                "chunk_index": i,
                "status": "queued",  # queued, uploading/downloading, completed, failed
                "bytes_written": 0,
                "total_bytes": 0
            } for i in range(total_chunks)
        }

    def get_snapshot(self):
        return list(self.chunks_telemetry.values())

class JobManager:
    def __init__(self):
        self._upload_jobs: Dict[str, Job] = {}
        self._download_jobs: Dict[str, Job] = {}

    def register_job(self, type: JobType, total_chunks: int) -> str:
        job_id = uuid.uuid4().hex

        match type:
            case JobType.UPLOAD: self._upload_jobs[job_id] = Job(type, total_chunks)
            case JobType.DOWNLOAD: self._download_jobs[job_id] = Job(type, total_chunks)

        return job_id

    def get_job(self, type: JobType, job_id: str) -> Optional[Job]:
        match type:
            case JobType.UPLOAD: return self._upload_jobs.get(job_id)
            case JobType.DOWNLOAD: return self._download_jobs.get(job_id)

    def remove_job(self, type: JobType, job_id: str):
        if type == JobType.UPLOAD and job_id in self._upload_jobs:
            del self._upload_jobs[job_id]
        elif type == JobType.DOWNLOAD and job_id in self._download_jobs:
            del self._download_jobs[job_id]
    