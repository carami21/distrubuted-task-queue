from unittest.mock import patch, MagicMock

import shared.redis_client as redis_client


def test_publish_job_publishes_to_jobs_channel():
    mock_conn = MagicMock()
    with patch("shared.redis_client.get_redis", return_value=mock_conn):
        redis_client.publish_job("job-1")

    mock_conn.publish.assert_called_once_with(redis_client.JOBS_CHANNEL, "job-1")


def test_publish_dead_job_publishes_to_dlq_channel():
    mock_conn = MagicMock()
    with patch("shared.redis_client.get_redis", return_value=mock_conn):
        redis_client.publish_dead_job("job-1")

    mock_conn.publish.assert_called_once_with(redis_client.DLQ_CHANNEL, "job-1")


def test_subscribe_jobs_subscribes_to_jobs_channel():
    mock_conn = MagicMock()
    mock_pubsub = MagicMock()
    mock_conn.pubsub.return_value = mock_pubsub
    with patch("shared.redis_client.get_redis", return_value=mock_conn):
        result = redis_client.subscribe_jobs()

    mock_pubsub.subscribe.assert_called_once_with(redis_client.JOBS_CHANNEL)
    assert result is mock_pubsub


def test_get_redis_uses_redis_url_env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:6379")
    with patch("shared.redis_client.redis.from_url") as mock_from_url:
        redis_client.get_redis()

    mock_from_url.assert_called_once_with("redis://example:6379", decode_responses=True)
