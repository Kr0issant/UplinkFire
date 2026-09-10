from typing import Optional
from pydantic import BaseModel


class AccountAddBody(BaseModel):
    email: str
    password: str
    free_space: Optional[int] = 10_000_000_000


class AccountPatchBody(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    free_space: Optional[int] = None


class DownloadStartBody(BaseModel):
    target: str  # file ID (hex UUID in DB) or a dpaste / manifest URL


class SettingsPatchBody(BaseModel):
    timeout_duration: Optional[str] = None
    upload_duration: Optional[str] = None
    captcha_duration: Optional[str] = None
    auto_logout: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    temp_dir_path: Optional[str] = None
    chunk_size: Optional[str] = None
    upload_strategy: Optional[str] = None
