from unittest.mock import patch


SAMPLE_JOB = {
    "job_id": "11111111-1111-1111-1111-111111111111",
    "status": "pending",
    "job_type": "send_email",
    "payload": {"to": "a@b.com"},
    "result": None,
    "error": None,
    "attempts": 0,
    "max_retries": 3,
    "version": 0,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
    "started_at": None,
    "finished_at": None,
}


def test_root(api_client):
    resp = api_client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "task-queue-api"


def test_post_jobs_valid(api_client):
    with patch("routers.jobs.create_job", return_value=SAMPLE_JOB) as mock_create, \
         patch("routers.jobs.publish_job") as mock_publish:
        body = {"job_type": "send_email", "payload": {"to": "a@b.com"}}
        resp = api_client.post("/jobs", json=body)
        assert resp.status_code == 201
        assert resp.json()["job_id"] == SAMPLE_JOB["job_id"]
        mock_create.assert_called_once_with("send_email", {"to": "a@b.com"}, 3)
        mock_publish.assert_called_once_with(SAMPLE_JOB["job_id"])


def test_post_jobs_missing_job_type(api_client):
    resp = api_client.post("/jobs", json={"payload": {}})
    assert resp.status_code == 422


def test_get_jobs_list(api_client):
    with patch("routers.jobs.list_jobs", return_value=[SAMPLE_JOB]) as mock_list:
        resp = api_client.get("/jobs")
        assert resp.status_code == 200
        assert resp.json() == [SAMPLE_JOB]
        mock_list.assert_called_once_with(status=None, limit=50, offset=0)


def test_get_jobs_filtered_by_status(api_client):
    with patch("routers.jobs.list_jobs", return_value=[SAMPLE_JOB]) as mock_list:
        resp = api_client.get("/jobs?status=pending")
        assert resp.status_code == 200
        mock_list.assert_called_once_with(status="pending", limit=50, offset=0)


def test_get_job_valid_id(api_client):
    with patch("routers.jobs.get_job", return_value=SAMPLE_JOB):
        resp = api_client.get(f"/jobs/{SAMPLE_JOB['job_id']}")
        assert resp.status_code == 200
        assert resp.json()["job_id"] == SAMPLE_JOB["job_id"]


def test_get_job_invalid_id(api_client):
    with patch("routers.jobs.get_job", return_value=None):
        resp = api_client.get("/jobs/does-not-exist")
        assert resp.status_code == 404


def test_delete_job_pending(api_client):
    with patch("routers.jobs.get_job", return_value=SAMPLE_JOB), \
         patch("routers.jobs.cancel_job", return_value=True) as mock_cancel:
        resp = api_client.delete(f"/jobs/{SAMPLE_JOB['job_id']}")
        assert resp.status_code == 204
        mock_cancel.assert_called_once_with(SAMPLE_JOB["job_id"])


def test_delete_job_not_found(api_client):
    with patch("routers.jobs.get_job", return_value=None):
        resp = api_client.delete("/jobs/does-not-exist")
        assert resp.status_code == 404


def test_delete_job_not_pending(api_client):
    running_job = {**SAMPLE_JOB, "status": "running"}
    with patch("routers.jobs.get_job", return_value=running_job):
        resp = api_client.delete(f"/jobs/{SAMPLE_JOB['job_id']}")
        assert resp.status_code == 400


def test_stats(api_client):
    with patch("routers.jobs.count_jobs_by_status", return_value={"pending": 2, "done": 5}):
        resp = api_client.get("/stats")
        assert resp.status_code == 200
        assert resp.json() == {"pending": 2, "done": 5}
