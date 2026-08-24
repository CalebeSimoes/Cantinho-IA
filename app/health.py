import json
import os
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WORKER_HEARTBEAT = PROJECT_DIR / "logs" / "worker-heartbeat.json"


def write_worker_heartbeat(
    state="healthy",
    *,
    consecutive_failures=0,
    error_type=None,
    path=None,
    now=None,
):
    """Publica, de forma atomica, o sinal de vida observado pelo Watchdog."""
    heartbeat_path = Path(path or DEFAULT_WORKER_HEARTBEAT)
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    payload = {
        "pid": os.getpid(),
        "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
        "state": state,
        "consecutive_failures": max(0, int(consecutive_failures)),
        "error_type": error_type,
    }

    temporary_path = heartbeat_path.with_name(
        f"{heartbeat_path.name}.{os.getpid()}.tmp"
    )
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary_path, heartbeat_path)
    return payload
