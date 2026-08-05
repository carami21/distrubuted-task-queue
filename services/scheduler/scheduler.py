import os
import time
import logging

from shared.database import get_stale_running_jobs, fail_job, get_job
from shared.redis_client import publish_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SCHEDULER] %(message)s")
logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))
STALE_TIMEOUT = int(os.getenv("STALE_TIMEOUT_MINUTES", "5"))


def run():
    logger.info(
        f"Scheduler starting. Polling every {POLL_INTERVAL}s for jobs stale >{STALE_TIMEOUT}min"
    )
    while True:
        stale = get_stale_running_jobs(timeout_minutes=STALE_TIMEOUT)
        if stale:
            logger.info(f"Found {len(stale)} stale jobs, requeuing...")
            for job in stale:
                logger.info(f"Requeueing job {job['job_id']} (attempts={job['attempts']})")
                # Reset to pending so a worker can claim it again
                fail_job(job["job_id"], "Timed out (worker crash detected)", job["max_retries"])
                fresh = get_job(job["job_id"])
                if fresh and fresh["status"] == "pending":
                    publish_job(str(job["job_id"]))
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
