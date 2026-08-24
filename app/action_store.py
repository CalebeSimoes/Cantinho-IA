import hashlib
import json
import os
from pathlib import Path

from app.schemas.actions import ActionPlan


STATE_DIR = Path(__file__).resolve().parents[1] / "state"
STATE_FILE = STATE_DIR / "action_state.json"


def _empty() -> dict:
    return {"pending": {}, "completed": {}}


def _load() -> dict:
    if not STATE_FILE.exists():
        return _empty()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    data.setdefault("pending", {})
    data.setdefault("completed", {})
    return data


def _save(data: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, STATE_FILE)


def assign_action_ids(plan: ActionPlan, source_key: str) -> ActionPlan:
    for index, action in enumerate(plan.actions):
        canonical = json.dumps(
            action.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(
            f"{source_key}:{index}:{canonical}".encode("utf-8")
        ).hexdigest()[:24]
        action.action_id = digest
    return plan


def save_pending(source_key: str, message: str, plan: ActionPlan):
    data = _load()
    data["pending"][source_key] = {
        "message": message,
        "plan": plan.model_dump(mode="json"),
        "done_action_ids": [],
    }
    _save(data)


def get_pending(source_key: str) -> dict | None:
    return _load()["pending"].get(source_key)


def discard_pending(source_key: str):
    data = _load()
    data["pending"].pop(source_key, None)
    _save(data)


def mark_action_done(source_key: str, action_id: str):
    data = _load()
    pending = data["pending"].get(source_key)
    if not pending:
        return
    done = set(pending.get("done_action_ids", []))
    done.add(action_id)
    pending["done_action_ids"] = sorted(done)
    _save(data)


def finish(source_key: str, summary: str):
    data = _load()
    data["pending"].pop(source_key, None)
    data["completed"][source_key] = {"summary": summary}
    # Mantém o arquivo pequeno sem perder as execuções mais recentes.
    if len(data["completed"]) > 1000:
        oldest = list(data["completed"])[:-1000]
        for key in oldest:
            data["completed"].pop(key, None)
    _save(data)


def get_completed(source_key: str) -> str | None:
    item = _load()["completed"].get(source_key)
    return item.get("summary") if item else None
