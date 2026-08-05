from fastapi import APIRouter, HTTPException, Response

from models import JobCreate
from shared.database import (
    create_job,
    get_job,
    list_jobs,
    cancel_job,
    count_jobs_by_status,
)
from shared.redis_client import publish_job

router = APIRouter()


@router.post("/jobs", status_code=201)
def submit_job(job: JobCreate):
    created = create_job(job.job_type, job.payload, job.max_retries)
    publish_job(str(created["job_id"]))
    return created


@router.get("/jobs")
def get_jobs(status: str | None = None, limit: int = 50, offset: int = 0):
    return list_jobs(status=status, limit=limit, offset=offset)


@router.get("/jobs/{job_id}")
def get_single_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "pending":
        raise HTTPException(status_code=400, detail="Only pending jobs can be cancelled")
    cancel_job(job_id)
    return Response(status_code=204)


@router.get("/stats")
def stats():
    return count_jobs_by_status()
