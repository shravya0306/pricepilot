import threading
from datetime import datetime

from app.schemas import LogType


class Job:
    def __init__(self, job_id: str, product: str) -> None:
        self.job_id = job_id
        self.product = product
        self.status = "running"
        self.logs: list[dict] = []
        self.deals: list[dict] = []
        self.insight: str | None = None
        self.error: str | None = None
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    def log(self, msg: str, type: LogType = "info") -> None:
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "msg": msg,
            "type": type,
        }
        with self._lock:
            self.logs.append(entry)

    def add_deal(self, deal: dict) -> None:
        with self._lock:
            self.deals.append(deal)

    def set_insight(self, text: str | None) -> None:
        with self._lock:
            self.insight = text

    def set_error(self, text: str | None) -> None:
        with self._lock:
            self.error = text

    def set_status(self, status: str) -> None:
        with self._lock:
            if self.status == "stopped" and status != "stopped":
                return
            self.status = status

    def request_cancel(self) -> None:
        self._cancel.set()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "job_id": self.job_id,
                "status": self.status,
                "product": self.product,
                "logs": [dict(entry) for entry in self.logs],
                "deals": [dict(deal) for deal in self.deals],
                "insight": self.insight,
                "error": self.error,
                "stop_requested": self._cancel.is_set(),
            }


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()
MAX_RUNNING_JOBS = 3
MAX_STORED_JOBS = 30
