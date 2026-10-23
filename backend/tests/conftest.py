import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.state import JOBS  # noqa: E402


@pytest.fixture(autouse=True)
def clear_jobs():
    JOBS.clear()
    yield
    JOBS.clear()
