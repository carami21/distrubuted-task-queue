from unittest.mock import patch

import pytest

import worker
from processor import process_job


BASE_JOB = {
    "job_id": "job-1",
    "version": 0,
    "job_type": "send_email",
    "payload": {},
    "max_retries": 3,
}


def fake_pubsub(messages):
    pubsub = type("FakePubSub", (), {})()
    pubsub.listen = lambda: iter(messages)
    return pubsub


def test_claim_job_called_with_correct_job_id_and_version():
    job = dict(BASE_JOB)
    messages = [{"type": "message", "data": "job-1"}]

    with patch("worker.subscribe_jobs", return_value=fake_pubsub(messages)), \
         patch("worker.get_job", return_value=job), \
         patch("worker.claim_job", return_value=True) as mock_claim, \
         patch("worker.process_job", return_value={"ok": True}), \
         patch("worker.complete_job"):
        worker.run()

    mock_claim.assert_called_once_with("job-1", 0)


def test_job_skipped_when_claim_fails():
    job = dict(BASE_JOB)
    messages = [{"type": "message", "data": "job-1"}]

    with patch("worker.subscribe_jobs", return_value=fake_pubsub(messages)), \
         patch("worker.get_job", return_value=job), \
         patch("worker.claim_job", return_value=False), \
         patch("worker.process_job") as mock_process:
        worker.run()

    mock_process.assert_not_called()


def test_job_skipped_when_not_found_in_db():
    messages = [{"type": "message", "data": "missing-job"}]

    with patch("worker.subscribe_jobs", return_value=fake_pubsub(messages)), \
         patch("worker.get_job", return_value=None), \
         patch("worker.claim_job") as mock_claim:
        worker.run()

    mock_claim.assert_not_called()


def test_non_message_events_are_ignored():
    messages = [{"type": "subscribe", "data": 1}]

    with patch("worker.subscribe_jobs", return_value=fake_pubsub(messages)), \
         patch("worker.get_job") as mock_get_job:
        worker.run()

    mock_get_job.assert_not_called()


def test_process_success_calls_complete_job():
    job = {**BASE_JOB, "payload": {"to": "a@b.com"}}
    messages = [{"type": "message", "data": "job-1"}]
    result = {"sent_to": "a@b.com"}

    with patch("worker.subscribe_jobs", return_value=fake_pubsub(messages)), \
         patch("worker.get_job", return_value=job), \
         patch("worker.claim_job", return_value=True), \
         patch("worker.process_job", return_value=result), \
         patch("worker.complete_job") as mock_complete, \
         patch("worker.fail_job") as mock_fail:
        worker.run()

    mock_complete.assert_called_once_with("job-1", result)
    mock_fail.assert_not_called()


def test_process_failure_calls_fail_job():
    job = {**BASE_JOB, "job_type": "resize_image"}
    messages = [{"type": "message", "data": "job-1"}]

    with patch("worker.subscribe_jobs", return_value=fake_pubsub(messages)), \
         patch("worker.get_job", return_value=job), \
         patch("worker.claim_job", return_value=True), \
         patch("worker.process_job", side_effect=ValueError("boom")), \
         patch("worker.complete_job") as mock_complete, \
         patch("worker.fail_job") as mock_fail:
        worker.run()

    mock_fail.assert_called_once_with("job-1", "boom", 3)
    mock_complete.assert_not_called()


def test_process_job_send_email_returns_expected_shape():
    result = process_job("send_email", {"to": "a@b.com"})
    assert result["sent_to"] == "a@b.com"
    assert "message_id" in result


def test_process_job_generate_report_returns_expected_shape():
    result = process_job("generate_report", {})
    assert "report_id" in result
    assert "rows" in result


def test_process_job_unknown_type_raises():
    with pytest.raises(ValueError):
        process_job("unknown_type", {})
