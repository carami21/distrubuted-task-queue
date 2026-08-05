import os
import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _row_to_dict(row):
    return dict(row) if row is not None else None


def create_job(job_type: str, payload: dict, max_retries: int = 3) -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO jobs (job_type, payload, max_retries)
                VALUES (%s, %s, %s)
                RETURNING *;
                """,
                (job_type, psycopg2.extras.Json(payload), max_retries),
            )
            row = cur.fetchone()
            conn.commit()
            return _row_to_dict(row)


def get_job(job_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM jobs WHERE job_id = %s;", (job_id,))
            return _row_to_dict(cur.fetchone())


def list_jobs(status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if status:
                cur.execute(
                    """
                    SELECT * FROM jobs WHERE status = %s
                    ORDER BY created_at DESC LIMIT %s OFFSET %s;
                    """,
                    (status, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM jobs
                    ORDER BY created_at DESC LIMIT %s OFFSET %s;
                    """,
                    (limit, offset),
                )
            return [_row_to_dict(row) for row in cur.fetchall()]


def claim_job(job_id: str, version: int) -> bool:
    """Optimistic lock: only succeeds if the row is still pending at the given version."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    attempts = attempts + 1,
                    version = version + 1,
                    started_at = NOW()
                WHERE job_id = %s AND version = %s AND status = 'pending';
                """,
                (job_id, version),
            )
            claimed = cur.rowcount == 1
            conn.commit()
            return claimed


def complete_job(job_id: str, result: dict) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status = 'done',
                    result = %s,
                    version = version + 1,
                    finished_at = NOW()
                WHERE job_id = %s;
                """,
                (psycopg2.extras.Json(result), job_id),
            )
            conn.commit()


def fail_job(job_id: str, error: str, max_retries: int) -> None:
    """Requeue to pending if attempts < max_retries, otherwise move to dead-letter."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET error = %s,
                    status = CASE WHEN attempts < %s THEN 'pending' ELSE 'dead' END,
                    finished_at = CASE WHEN attempts < %s THEN finished_at ELSE NOW() END,
                    version = version + 1
                WHERE job_id = %s;
                """,
                (error, max_retries, max_retries, job_id),
            )
            conn.commit()


def count_jobs_by_status() -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status;")
            return {status: count for status, count in cur.fetchall()}


def cancel_job(job_id: str) -> bool:
    """Cancel a pending job by moving it straight to dead-letter."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status = 'dead', version = version + 1, finished_at = NOW()
                WHERE job_id = %s AND status = 'pending';
                """,
                (job_id,),
            )
            cancelled = cur.rowcount == 1
            conn.commit()
            return cancelled


def get_stale_running_jobs(timeout_minutes: int = 5) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'running'
                  AND started_at < NOW() - make_interval(mins => %s);
                """,
                (timeout_minutes,),
            )
            return [_row_to_dict(row) for row in cur.fetchall()]
