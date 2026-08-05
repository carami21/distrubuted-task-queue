from unittest.mock import patch

import shared.database as database


def test_create_job_returns_row(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchone.return_value = {
        "job_id": "job-1",
        "status": "pending",
        "version": 0,
        "job_type": "send_email",
    }
    with patch("shared.database.get_conn", return_value=conn):
        row = database.create_job("send_email", {"to": "a@b.com"}, 3)

    assert row["job_id"] == "job-1"
    assert row["status"] == "pending"
    assert row["version"] == 0
    cursor.execute.assert_called_once()


def test_get_job_found(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchone.return_value = {"job_id": "job-1", "status": "pending"}
    with patch("shared.database.get_conn", return_value=conn):
        row = database.get_job("job-1")

    assert row["job_id"] == "job-1"


def test_get_job_not_found(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchone.return_value = None
    with patch("shared.database.get_conn", return_value=conn):
        row = database.get_job("missing")

    assert row is None


def test_list_jobs_no_status_filter(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchall.return_value = [{"job_id": "job-1"}, {"job_id": "job-2"}]
    with patch("shared.database.get_conn", return_value=conn):
        rows = database.list_jobs()

    assert len(rows) == 2
    query = cursor.execute.call_args[0][0]
    assert "WHERE status" not in query


def test_list_jobs_with_status_filter(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchall.return_value = [{"job_id": "job-1", "status": "pending"}]
    with patch("shared.database.get_conn", return_value=conn):
        rows = database.list_jobs(status="pending")

    assert len(rows) == 1
    query, params = cursor.execute.call_args[0]
    assert "WHERE status" in query
    assert params[0] == "pending"


def test_claim_job_correct_version_succeeds(mock_conn):
    conn, cursor = mock_conn
    cursor.rowcount = 1
    with patch("shared.database.get_conn", return_value=conn):
        claimed = database.claim_job("job-1", 0)

    assert claimed is True
    cursor.execute.assert_called_once()
    args = cursor.execute.call_args[0][1]
    assert args == ("job-1", 0)


def test_claim_job_wrong_version_fails(mock_conn):
    conn, cursor = mock_conn
    cursor.rowcount = 0
    with patch("shared.database.get_conn", return_value=conn):
        claimed = database.claim_job("job-1", 99)

    assert claimed is False


def test_complete_job_executes_update(mock_conn):
    conn, cursor = mock_conn
    with patch("shared.database.get_conn", return_value=conn):
        result = database.complete_job("job-1", {"ok": True})

    assert result is None
    cursor.execute.assert_called_once()


def test_fail_job_passes_max_retries_and_error(mock_conn):
    conn, cursor = mock_conn
    with patch("shared.database.get_conn", return_value=conn):
        database.fail_job("job-1", "boom", 3)

    query, params = cursor.execute.call_args[0]
    assert params == ("boom", 3, 3, "job-1")
    assert "CASE WHEN attempts < %s" in query


def test_get_stale_running_jobs_returns_rows(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchall.return_value = [{"job_id": "job-1", "status": "running"}]
    with patch("shared.database.get_conn", return_value=conn):
        rows = database.get_stale_running_jobs(timeout_minutes=5)

    assert len(rows) == 1
    assert rows[0]["status"] == "running"


def test_count_jobs_by_status(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchall.return_value = [("pending", 2), ("done", 5)]
    with patch("shared.database.get_conn", return_value=conn):
        counts = database.count_jobs_by_status()

    assert counts == {"pending": 2, "done": 5}


def test_cancel_job_success(mock_conn):
    conn, cursor = mock_conn
    cursor.rowcount = 1
    with patch("shared.database.get_conn", return_value=conn):
        cancelled = database.cancel_job("job-1")

    assert cancelled is True


def test_cancel_job_not_pending(mock_conn):
    conn, cursor = mock_conn
    cursor.rowcount = 0
    with patch("shared.database.get_conn", return_value=conn):
        cancelled = database.cancel_job("job-1")

    assert cancelled is False
