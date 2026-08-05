from unittest.mock import patch

import pytest

import scheduler


class _StopLoop(Exception):
    pass


def _run_one_iteration():
    with patch("scheduler.time.sleep", side_effect=_StopLoop):
        with pytest.raises(_StopLoop):
            scheduler.run()


def test_no_stale_jobs_means_no_requeue():
    with patch("scheduler.get_stale_running_jobs", return_value=[]), \
         patch("scheduler.fail_job") as mock_fail, \
         patch("scheduler.publish_job") as mock_publish:
        _run_one_iteration()

    mock_fail.assert_not_called()
    mock_publish.assert_not_called()


def test_stale_jobs_are_requeued_when_still_pending():
    stale = [
        {"job_id": "job-1", "attempts": 1, "max_retries": 3},
        {"job_id": "job-2", "attempts": 1, "max_retries": 3},
    ]
    fresh = {"job_id": "job-1", "status": "pending"}

    with patch("scheduler.get_stale_running_jobs", return_value=stale), \
         patch("scheduler.fail_job") as mock_fail, \
         patch("scheduler.get_job", return_value=fresh), \
         patch("scheduler.publish_job") as mock_publish:
        _run_one_iteration()

    assert mock_fail.call_count == 2
    assert mock_publish.call_count == 2


def test_stale_job_not_republished_when_dead():
    stale = [{"job_id": "job-1", "attempts": 3, "max_retries": 3}]
    fresh_dead = {"job_id": "job-1", "status": "dead"}

    with patch("scheduler.get_stale_running_jobs", return_value=stale), \
         patch("scheduler.fail_job") as mock_fail, \
         patch("scheduler.get_job", return_value=fresh_dead), \
         patch("scheduler.publish_job") as mock_publish:
        _run_one_iteration()

    mock_fail.assert_called_once_with("job-1", "Timed out (worker crash detected)", 3)
    mock_publish.assert_not_called()
