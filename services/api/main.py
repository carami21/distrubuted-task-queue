from fastapi import FastAPI

from routers import jobs

app = FastAPI(title="Task Queue API", version="1.0.0")
app.include_router(jobs.router)


@app.get("/")
def root():
    return {"service": "task-queue-api", "version": "1.0.0"}
