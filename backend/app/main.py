from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.jobs import BusyError, JobNotFound, get_job, request_stop, start_job
from app.schemas import JobCreated, JobResponse, SearchRequest

settings = get_settings()
app = FastAPI(title="PricePilot API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=JobCreated, status_code=202)
def search(body: SearchRequest) -> JobCreated:
    try:
        job = start_job(body.product, settings)
    except BusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return JobCreated(job_id=job.job_id)


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def read_job(job_id: str) -> JobResponse:
    try:
        job = get_job(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="Search job not found") from exc
    return JobResponse.model_validate(job.snapshot())


@app.post("/api/jobs/{job_id}/stop", response_model=JobResponse)
def stop_job(job_id: str) -> JobResponse:
    try:
        job = request_stop(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="Search job not found") from exc
    return JobResponse.model_validate(job.snapshot())
