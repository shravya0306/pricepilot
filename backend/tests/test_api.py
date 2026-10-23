from pathlib import Path

from fastapi.testclient import TestClient

from app.config import PRODUCTION_FRONTEND_ORIGIN, Settings
from app.main import app
from app.state import JOBS, MAX_RUNNING_JOBS

REBUILT = Path(__file__).resolve().parents[2]


class ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


class IdleThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target

    def start(self):
        return None


def _sample_deal() -> dict:
    return {
        "merchant": "Example Mart",
        "title": "Phone 128GB",
        "price": 10000,
        "product_url": "https://example.test/p",
        "offers": {
            "bank_offers": [],
            "coupons": [],
            "exchange_offers": [],
            "cashback_offers": [],
        },
        "summary": {
            "base_price": 10000,
            "checkout_price": 10000,
            "guaranteed_discount": 0,
            "guaranteed_label": None,
            "best_conditional_label": None,
            "best_conditional_price": None,
            "best_exchange_label": None,
            "best_exchange_price": None,
            "cashback_value": None,
            "cashback_label": None,
            "estimated_net": None,
            "stacked_checkout": None,
            "stacked_label": None,
            "incompatible_notes": [],
        },
    }


def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_rejects_blank_and_tiny_product_names():
    client = TestClient(app)
    assert client.post("/api/search", json={"product": " "}).status_code == 422
    assert client.post("/api/search", json={"product": "a"}).status_code == 422
    assert client.post("/api/search", json={"product": "x" * 201}).status_code == 422


def test_unknown_job_is_not_found():
    client = TestClient(app)
    assert client.get("/api/jobs/missing").status_code == 404
    assert client.post("/api/jobs/missing/stop").status_code == 404


def test_search_job_lifecycle(monkeypatch):
    def fake_run(job, _settings, deps=None):
        job.log("Searching shopping results", "info")
        job.add_deal(_sample_deal())
        job.set_insight("Example Mart is the only completed result in this test.")
        job.set_status("completed")

    monkeypatch.setattr("app.services.pipeline.run_job", fake_run)
    monkeypatch.setattr("app.jobs.threading.Thread", ImmediateThread)
    client = TestClient(app)

    created = client.post("/api/search", json={"product": "  Phone   128 GB  "})
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "completed"
    assert body["product"] == "Phone 128 GB"
    assert body["deals"][0]["merchant"] == "Example Mart"
    assert body["logs"][0]["type"] == "info"
    assert "Example Mart" in body["insight"]


def test_stop_marks_a_running_job(monkeypatch):
    monkeypatch.setattr("app.jobs.threading.Thread", IdleThread)
    client = TestClient(app)
    created = client.post("/api/search", json={"product": "Phone 128GB"})
    job_id = created.json()["job_id"]
    stopped = client.post(f"/api/jobs/{job_id}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["stop_requested"] is True
    assert stopped.json()["status"] == "running"


def test_busy_limit(monkeypatch):
    monkeypatch.setattr("app.jobs.threading.Thread", IdleThread)
    client = TestClient(app)
    for index in range(MAX_RUNNING_JOBS):
        response = client.post("/api/search", json={"product": f"Phone model {index}"})
        assert response.status_code == 202
    overflow = client.post("/api/search", json={"product": "Another phone"})
    assert overflow.status_code == 429
    assert JOBS


def test_project_examples_and_frontend_do_not_contain_secret_keys():
    env_example = (REBUILT / "backend" / ".env.example").read_text(encoding="utf-8")
    assert "AIza" not in env_example
    assert "GEMINI_API_KEY=" in env_example
    assert "SERPER_API_KEY=" in env_example
    assert "SCRAPER_API_KEY=" in env_example

    frontend = REBUILT / "frontend" / "src"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in frontend.rglob("*")
        if path.is_file()
    )
    assert "SERPER_API_KEY" not in source
    assert "SCRAPER_API_KEY" not in source
    assert "GEMINI_API_KEY" not in source
    assert "AIza" not in source
    assert "api.scraperapi.com" not in source
    assert "google.serper.dev" not in source


def test_production_origin_survives_a_localhost_only_setting():
    settings = Settings(cors_origins="http://localhost:5173", _env_file=None)
    assert settings.cors_origin_list[0] == "http://localhost:5173"
    assert PRODUCTION_FRONTEND_ORIGIN in settings.cors_origin_list


def test_production_frontend_can_call_the_api():
    client = TestClient(app)
    origin = PRODUCTION_FRONTEND_ORIGIN
    health = client.get("/api/health", headers={"Origin": origin})
    assert health.status_code == 200
    assert health.headers["access-control-allow-origin"] == origin

    preflight = client.options(
        "/api/search",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    assert "POST" in preflight.headers["access-control-allow-methods"]


def test_unknown_origin_is_rejected():
    client = TestClient(app)
    response = client.options(
        "/api/search",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
