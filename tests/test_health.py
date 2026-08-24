import json
from datetime import datetime, timezone

from app.health import write_worker_heartbeat


def test_worker_heartbeat_is_valid_and_atomic(tmp_path):
    heartbeat = tmp_path / "worker-heartbeat.json"
    now = datetime(2026, 8, 23, 15, 30, tzinfo=timezone.utc)

    payload = write_worker_heartbeat(
        "degraded",
        consecutive_failures=2,
        error_type="TimeoutError",
        path=heartbeat,
        now=now,
    )

    saved = json.loads(heartbeat.read_text(encoding="utf-8"))
    assert saved == payload
    assert saved["timestamp"] == "2026-08-23T15:30:00+00:00"
    assert saved["state"] == "degraded"
    assert saved["consecutive_failures"] == 2
    assert saved["error_type"] == "TimeoutError"
    assert list(tmp_path.glob("*.tmp")) == []


def test_negative_failure_count_is_normalized(tmp_path):
    payload = write_worker_heartbeat(
        "healthy",
        consecutive_failures=-10,
        path=tmp_path / "heartbeat.json",
    )

    assert payload["consecutive_failures"] == 0
