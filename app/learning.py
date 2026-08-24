import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import settings


DEFAULT_LEARNING_LOG = Path("logs") / "learning_cases.jsonl"


def record_learning_case(
    *,
    message: str,
    status: str,
    destination: str,
    summary: str,
    author: str,
    log_path: str | Path | None = None,
) -> Path:
    """Registra casos que merecem virar novos testes de regressao."""
    path = Path(log_path) if log_path else DEFAULT_LEARNING_LOG
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp": datetime.now(
            ZoneInfo(settings.app_timezone)
        ).isoformat(),
        "message": message,
        "status": status,
        "destination": destination,
        "summary": summary,
        "author": author,
    }

    with path.open("a", encoding="utf-8") as fp:
        fp.write(
            json.dumps(payload, ensure_ascii=False) + "\n"
        )

    return path
