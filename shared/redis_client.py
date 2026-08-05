import os
import redis

JOBS_CHANNEL = "jobs:pending"
DLQ_CHANNEL = "jobs:dead"


def get_redis():
    return redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def publish_job(job_id: str) -> None:
    get_redis().publish(JOBS_CHANNEL, job_id)


def publish_dead_job(job_id: str) -> None:
    get_redis().publish(DLQ_CHANNEL, job_id)


def subscribe_jobs():
    pubsub = get_redis().pubsub()
    pubsub.subscribe(JOBS_CHANNEL)
    return pubsub
