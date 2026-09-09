import asyncio, uuid
from enum import Enum
from typing import Dict

class JobType(Enum):
    UPLOAD = 1
    DOWNLOAD = 2

class JobManager:
    def __init__(self):
        self._upload_jobs: Dict[str, asyncio.Queue] = {}
        self._download_jobs: Dict[str, asyncio.Queue] = {}

    def register_job(self, type: JobType) -> str:
        job_id = uuid.uuid4().hex
        queue = asyncio.Queue()

        match type:
            case JobType.UPLOAD: self._upload_jobs[job_id] = queue
            case JobType.DOWNLOAD: self._download_jobs[job_id] = queue

        return job_id

    def get_queue(self, type: JobType, job_id: str) -> asyncio.Queue:
        match type:
            case JobType.UPLOAD: return self._upload_jobs.get(job_id)
            case JobType.DOWNLOAD: return self._download_jobs.get(job_id)

    def remove_job(self, type: JobType, job_id: str):
        if type == JobType.UPLOAD and job_id in self._upload_jobs:
            del self._upload_jobs[job_id]
        elif type == JobType.DOWNLOAD and job_id in self._download_jobs:
            del self._download_jobs[job_id]
    