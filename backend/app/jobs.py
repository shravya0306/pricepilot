import threading
import uuid

from app.config import Settings
from app.state import JOBS, JOBS_LOCK, MAX_RUNNING_JOBS, MAX_STORED_JOBS, Job


class BusyError(Exception):
    pass


class JobNotFound(Exception):
    pass


def start_job(product: str, settings: Settings) -> Job:
    from app.services.pipeline import run_job

    job = Job(uuid.uuid4().hex, product)
    with JOBS_LOCK:
        running = sum(1 for item in JOBS.values() if item.status == "running")
        if running >= MAX_RUNNING_JOBS:
            raise BusyError("Too many searches are already running")
        JOBS[job.job_id] = job
        _trim_locked()

    thread = threading.Thread(target=run_job, args=(job, settings), daemon=True)
    thread.start()
    return job


def get_job(job_id: str) -> Job:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if job is None:
        raise JobNotFound(job_id)
    return job


def request_stop(job_id: str) -> Job:
    job = get_job(job_id)
    job.request_cancel()
    return job


def _trim_locked() -> None:
    if len(JOBS) <= MAX_STORED_JOBS:
        return
    finished = [job_id for job_id, job in JOBS.items() if job.status != "running"]
    for job_id in finished:
        if len(JOBS) <= MAX_STORED_JOBS:
            return
        JOBS.pop(job_id, None)
