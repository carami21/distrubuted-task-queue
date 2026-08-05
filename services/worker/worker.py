import logging

from shared.database import claim_job, get_job, complete_job, fail_job, list_jobs
from shared.redis_client import subscribe_jobs
from processor import process_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [WORKER] %(message)s")
logger = logging.getLogger(__name__)


def _process_one(job_id: str):
    job = get_job(job_id)
    if not job:
        logger.warning(f"Job {job_id} not found in DB, skipping")
        return

    # OPTIMISTIC LOCK — only one worker wins this race
    claimed = claim_job(job_id, job["version"])
    if not claimed:
        logger.info(f"Job {job_id} already claimed by another worker, skipping")
        return

    logger.info(f"Processing job {job_id} (type={job['job_type']})")
    try:
        result = process_job(job["job_type"], job["payload"])
        complete_job(job_id, result)
        logger.info(f"Job {job_id} completed: {result}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Job {job_id} failed: {error_msg}")
        fail_job(job_id, error_msg, job["max_retries"])


def _catch_up_pending():
    """Claim any jobs left pending from before this worker subscribed.

    Redis pub/sub only delivers to currently-subscribed clients, so a job published
    while no worker was listening (e.g. requeued by the scheduler while all workers
    were down) would otherwise sit pending forever.
    """
    pending = list_jobs(status="pending", limit=100)
    if pending:
        logger.info(f"Catch-up: found {len(pending)} pending job(s) on startup")
    for job in pending:
        _process_one(str(job["job_id"]))


def run():
    logger.info("Worker starting, waiting for jobs...")
    pubsub = subscribe_jobs()
    _catch_up_pending()

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        job_id = message["data"]
        logger.info(f"Received job_id: {job_id}")
        _process_one(job_id)


if __name__ == "__main__":
    run()
