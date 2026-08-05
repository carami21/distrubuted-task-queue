from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JobCreate(BaseModel):
    job_type: str
    payload: dict = {}
    max_retries: int = 3


class JobResponse(BaseModel):
    job_id: str
    status: str
    job_type: str
    payload: dict
    result: Optional[dict] = None
    error: Optional[str] = None
    attempts: int
    max_retries: int
    version: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
