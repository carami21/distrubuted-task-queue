import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import redis
import psycopg2

app = FastAPI(title="Health Monitor", version="1.0.0")


@app.get("/health")
def health():
    checks = {"api": "ok", "redis": "unknown", "postgres": "unknown"}

    try:
        r = redis.from_url(os.environ["REDIS_URL"])
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        conn.close()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    status_code = 200 if all(v == "ok" for v in checks.values()) else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.get("/")
def root():
    return {"service": "health-monitor", "version": "1.0.0"}
