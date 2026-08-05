import logging

from shared.database import claim_job, get_job, complete_job, fail_job
from shared.redis_client import subscribe_jobs
from processor import process_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [WORKER] %(message)s")
logger = logging.getLogger(__name__)


def run():
    logger.info("Worker starting, waiting for jobs...")
    pubsub = subscribe_jobs()

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        job_id = message["data"]
        logger.info(f"Received job_id: {job_id}")

        job = get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found in DB, skipping")
            continue

        # OPTIMISTIC LOCK — only one worker wins this race
        claimed = claim_job(job_id, job["version"])
        if not claimed:
            logger.info(f"Job {job_id} already claimed by another worker, skipping")
            continue

        logger.info(f"Processing job {job_id} (type={job['job_type']})")
        try:
            result = process_job(job["job_type"], job["payload"])
            complete_job(job_id, result)
            logger.info(f"Job {job_id} completed: {result}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job {job_id} failed: {error_msg}")
            fail_job(job_id, error_msg, job["max_retries"])


if __name__ == "__main__":
    run()
