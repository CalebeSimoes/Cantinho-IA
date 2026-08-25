"""Radar diário e proativo do Cantinho, sem depender do Ollama."""

from __future__ import annotations

import hashlib
import json
import os
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import settings
from app.notion import readers
from app.notion.notifications import notify_household_radar
from app.notion.readers import CalendarRecord, RoutineRecord, WishlistRecord


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RADAR_STATE = PROJECT_DIR / "state" / "radar-state.json"


@dataclass(frozen=True)
class RadarAlert:
    key: str
    priority: int
    kind: str
    text: str


@dataclass(frozen=True)
class RadarRunResult:
    status: str
    alerts: tuple[RadarAlert, ...] = ()
    message: str = ""
    reason: str = ""


def _normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def _is_open(status: str | None) -> bool:
    return _normalize(status) not in {
        "concluido",
        "cancelado",
        "cancelada",
        "feito",
        "comprado",
        "desistimos",
    }


def _short(value: str, limit: int = 80) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _responsible(value: str | None) -> str:
    return {
        "Eu": settings.user_name,
        "Minha esposa": settings.partner_name,
        "Nós dois": "nós dois",
    }.get(value or "", value or "sem responsável")


def _day_label(value: date, reference: date) -> str:
    difference = (value - reference).days
    if difference == 0:
        return "hoje"
    if difference == 1:
        return "amanhã"
    return value.strftime("%d/%m")


def _hour_label(record: CalendarRecord) -> str:
    return f" às {record.hora.strftime('%H:%M')}" if record.hora else ""


def _record_list(records: list[RoutineRecord], limit: int = 3) -> str:
    items = [
        f"{_short(record.tarefa, 45)} ({_responsible(record.responsavel)})"
        for record in records[:limit]
    ]
    suffix = f" e mais {len(records) - limit}" if len(records) > limit else ""
    return "; ".join(items) + suffix


def _task_count(value: int) -> str:
    return f"{value} tarefa" if value == 1 else f"{value} tarefas"


def build_radar_alerts(
    routines: list[RoutineRecord],
    calendar: list[CalendarRecord],
    wishlist: list[WishlistRecord],
    *,
    reference: date,
    lookahead_days: int = 2,
    max_items: int = 5,
) -> list[RadarAlert]:
    """Gera somente sinais acionáveis e ordenados por urgência."""
    alerts: list[RadarAlert] = []
    active_routines = [record for record in routines if _is_open(record.status)]
    active_calendar = [record for record in calendar if _is_open(record.status)]
    conflicted_ids: set[str] = set()

    # O schema não guarda duração. Portanto, só afirmamos conflito quando dois
    # compromissos têm exatamente o mesmo dia e horário informado.
    calendar_slots: dict[tuple[date, object], list[CalendarRecord]] = {}
    for record in active_calendar:
        if record.data and record.hora:
            calendar_slots.setdefault((record.data, record.hora), []).append(record)
    for (event_date, event_time), records_in_slot in calendar_slots.items():
        if len(records_in_slot) < 2 or event_date < reference:
            continue
        if (event_date - reference).days > lookahead_days:
            continue
        conflicted_ids.update(record.page_id for record in records_in_slot)
        names = " e ".join(_short(record.evento, 55) for record in records_in_slot[:2])
        if len(records_in_slot) > 2:
            names += f" e mais {len(records_in_slot) - 2}"
        alerts.append(RadarAlert(
            key="calendar-conflict:" + ":".join(
                sorted(record.page_id for record in records_in_slot)
            ),
            priority=120 - max(0, (event_date - reference).days),
            kind="calendar_conflict",
            text=(
                f"🚨 Possível conflito {_day_label(event_date, reference)} "
                f"às {event_time.strftime('%H:%M')}: {names}."
            ),
        ))

    overdue = sorted(
        (
            record for record in active_routines
            if record.dia_data and record.dia_data < reference
        ),
        key=lambda record: record.dia_data or date.max,
    )
    if overdue:
        alerts.append(RadarAlert(
            key="routine-overdue:" + ":".join(
                sorted(record.page_id for record in overdue)
            ),
            priority=110,
            kind="routine_overdue",
            text=(
                f"⏰ {_task_count(len(overdue))} "
                f"{'atrasada' if len(overdue) == 1 else 'atrasadas'}: "
                f"{_record_list(overdue)}."
            ),
        ))

    due_today = sorted(
        (
            record for record in active_routines
            if record.dia_data == reference
        ),
        key=lambda record: record.tarefa.casefold(),
    )
    if due_today:
        alerts.append(RadarAlert(
            key="routine-today:" + ":".join(
                sorted(record.page_id for record in due_today)
            ),
            priority=100,
            kind="routine_today",
            text=(
                f"✅ {_task_count(len(due_today))} para hoje: "
                f"{_record_list(due_today)}."
            ),
        ))

    upcoming = sorted(
        (
            record for record in active_calendar
            if record.data
            and 0 <= (record.data - reference).days <= lookahead_days
            and record.page_id not in conflicted_ids
        ),
        key=lambda record: (
            record.data or date.max,
            record.hora or datetime.max.time(),
        ),
    )
    for record in upcoming:
        days = (record.data - reference).days if record.data else lookahead_days
        alerts.append(RadarAlert(
            key=f"calendar-upcoming:{record.page_id}:{record.data}",
            priority=90 - days * 5,
            kind="calendar_upcoming",
            text=(
                f"📅 {_day_label(record.data, reference).capitalize()}"
                f"{_hour_label(record)}: {_short(record.evento)}"
                + (f" · {_short(record.local, 45)}" if record.local else "")
                + "."
            ),
        ))

    active_wishlist = [record for record in wishlist if _is_open(record.status)]
    wanted_until = reference + timedelta(days=7)
    for record in sorted(
        (
            item for item in active_wishlist
            if item.data_desejada and item.data_desejada <= wanted_until
        ),
        key=lambda item: item.data_desejada or date.max,
    ):
        overdue_purchase = bool(
            record.data_desejada and record.data_desejada < reference
        )
        price = ""
        if record.preco_estimado is not None:
            formatted = f"{record.preco_estimado:,.2f}"
            price = " · R$ " + formatted.replace(",", "X").replace(
                ".", ","
            ).replace("X", ".")
        alerts.append(RadarAlert(
            key=f"wishlist-date:{record.page_id}:{record.data_desejada}",
            priority=85 if overdue_purchase else 72,
            kind="wishlist_date",
            text=(
                f"🛒 {_short(record.item)}: data desejada "
                f"{_day_label(record.data_desejada, reference)}{price}."
            ),
        ))

    workload = {"Eu": 0, "Minha esposa": 0}
    for record in active_routines:
        if record.responsavel == "Nós dois":
            workload["Eu"] += 1
            workload["Minha esposa"] += 1
        elif record.responsavel in workload:
            workload[record.responsavel] += 1
    heavier = max(workload, key=workload.get)
    lighter = min(workload, key=workload.get)
    if workload[heavier] >= 4 and workload[heavier] - workload[lighter] >= 3:
        alerts.append(RadarAlert(
            key=f"workload:{workload['Eu']}:{workload['Minha esposa']}",
            priority=50,
            kind="workload",
            text=(
                f"⚖️ Divisão das tarefas abertas: {settings.user_name} "
                f"{workload['Eu']} · {settings.partner_name} "
                f"{workload['Minha esposa']}. Talvez valha redistribuir."
            ),
        ))

    unique = {alert.key: alert for alert in alerts}
    return sorted(
        unique.values(),
        key=lambda alert: (-alert.priority, alert.key),
    )[:max(1, max_items)]


def render_radar_message(alerts: list[RadarAlert], reference: date) -> str:
    lines = [f"🌿 Radar do Cantinho · {reference.strftime('%d/%m')}", ""]
    lines.extend(
        f"{index}. {alert.text}" for index, alert in enumerate(alerts, 1)
    )
    lines.extend(["", "Toque nesta notificação para abrir o Cantinho."])
    message = "\n".join(lines)
    return message if len(message) <= 1800 else message[:1799].rstrip() + "…"


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    for attempt in range(5):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))


def _local_now(value: datetime | None = None) -> datetime:
    zone = ZoneInfo(settings.app_timezone)
    if value is None:
        return datetime.now(zone)
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def _recent_attempt(state: dict, now: datetime) -> bool:
    raw = state.get("last_attempt_at")
    if not raw:
        return False
    try:
        attempted = datetime.fromisoformat(raw)
        if attempted.tzinfo is None:
            attempted = attempted.replace(tzinfo=now.tzinfo)
    except ValueError:
        return False
    return now - attempted < timedelta(
        minutes=max(1, settings.radar_retry_minutes)
    )


def _recent_identical_digest(state: dict, signature: str, now: datetime) -> bool:
    if state.get("last_digest_signature") != signature:
        return False
    raw = state.get("last_sent_at")
    if not raw:
        return False
    try:
        sent_at = datetime.fromisoformat(raw)
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=now.tzinfo)
    except ValueError:
        return False
    return now - sent_at < timedelta(days=max(1, settings.radar_repeat_days))


def preview_radar(*, now: datetime | None = None) -> RadarRunResult:
    """Lê o Notion e monta o Radar sem notificar nem alterar o estado."""
    current = _local_now(now)
    alerts = build_radar_alerts(
        readers.get_routines(),
        readers.get_calendar(),
        readers.get_wishlist(),
        reference=current.date(),
        lookahead_days=max(0, settings.radar_lookahead_days),
        max_items=max(1, settings.radar_max_items),
    )
    if not alerts:
        return RadarRunResult("empty", reason="nenhum alerta acionável")
    message = render_radar_message(alerts, current.date())
    return RadarRunResult("preview", tuple(alerts), message)


def run_daily_radar(
    *,
    now: datetime | None = None,
    state_path: Path | None = None,
    force: bool = False,
) -> RadarRunResult:
    current = _local_now(now)
    path = Path(state_path or DEFAULT_RADAR_STATE)
    state = _load_state(path)
    today = current.date().isoformat()

    if not settings.radar_enabled and not force:
        return RadarRunResult("skipped", reason="Radar desabilitado")
    scheduled = current.replace(
        hour=max(0, min(23, settings.radar_hour)),
        minute=max(0, min(59, settings.radar_minute)),
        second=0,
        microsecond=0,
    )
    if not force and current < scheduled:
        return RadarRunResult("skipped", reason="antes do horário")
    if not force and state.get("last_completed_date") == today:
        return RadarRunResult("skipped", reason="Radar já concluído hoje")
    if not force and _recent_attempt(state, current):
        return RadarRunResult("skipped", reason="aguardando nova tentativa")

    state.update({
        "last_attempt_at": current.isoformat(timespec="seconds"),
        "last_status": "checking",
    })
    _save_state(path, state)

    try:
        alerts = build_radar_alerts(
            readers.get_routines(),
            readers.get_calendar(),
            readers.get_wishlist(),
            reference=current.date(),
            lookahead_days=max(0, settings.radar_lookahead_days),
            max_items=max(1, settings.radar_max_items),
        )
    except Exception as exc:
        state.update({
            "last_status": "failed",
            "last_error": f"{type(exc).__name__}: {exc}",
        })
        _save_state(path, state)
        return RadarRunResult("failed", reason=state["last_error"])

    if not alerts:
        state.update({
            "last_completed_date": today,
            "last_status": "empty",
            "last_alert_count": 0,
        })
        state.pop("last_error", None)
        _save_state(path, state)
        return RadarRunResult("empty", reason="nenhum alerta acionável")

    message = render_radar_message(alerts, current.date())
    digest_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
    signature = hashlib.sha256(
        "\n".join(alert.text for alert in alerts).encode("utf-8")
    ).hexdigest()[:16]
    if not force and _recent_identical_digest(state, signature, current):
        state.update({
            "last_completed_date": today,
            "last_status": "suppressed",
            "last_alert_count": len(alerts),
        })
        _save_state(path, state)
        return RadarRunResult(
            "suppressed",
            tuple(alerts),
            message,
            "resumo idêntico enviado recentemente",
        )
    notification = notify_household_radar(message)
    state.update({
        "last_status": "sent" if notification.sent else "failed",
        "last_alert_count": len(alerts),
        "last_digest_hash": digest_hash,
        "last_digest_signature": signature,
        "last_notification_mode": notification.mode,
    })
    if notification.sent:
        state["last_completed_date"] = today
        state["last_sent_at"] = current.isoformat(timespec="seconds")
        state.pop("last_error", None)
        status = "sent"
        reason = ", ".join(notification.recipients)
    else:
        state["last_error"] = "notificação mobile não enviada"
        status = "failed"
        reason = state["last_error"]
    _save_state(path, state)
    return RadarRunResult(status, tuple(alerts), message, reason)
