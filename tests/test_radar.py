import json
from datetime import date, datetime, time, timedelta

import pytest

import app.notion.notifications as notifications
import app.radar as radar
import app.worker as worker
from app.notion.notifications import NotificationResult
from app.notion.readers import CalendarRecord, RoutineRecord, WishlistRecord


def _routine(
    page_id: str,
    task: str,
    due: date | None,
    responsible: str = "Eu",
    status: str = "A fazer",
) -> RoutineRecord:
    return RoutineRecord(
        page_id=page_id,
        tarefa=task,
        categoria="Casa",
        dia_data=due,
        frequencia="Pontual",
        responsavel=responsible,
        status=status,
        observacao="",
    )


def _event(
    page_id: str,
    name: str,
    event_date: date,
    event_time: time | None = None,
    status: str = "Confirmado",
) -> CalendarRecord:
    return CalendarRecord(
        page_id=page_id,
        evento=name,
        data=event_date,
        quem="Nós dois",
        status=status,
        tipo="Compromisso",
        local="",
        observacao="",
        hora=event_time,
    )


def _wish(
    page_id: str,
    item: str,
    wanted: date,
    status: str = "Planejando",
) -> WishlistRecord:
    return WishlistRecord(
        page_id=page_id,
        item=item,
        preco_estimado=300,
        status=status,
        prioridade="Média",
        tipo="Casa",
        data_desejada=wanted,
        observacao="",
        link=None,
    )


def test_radar_prioritizes_conflict_overdue_and_today():
    today = date(2026, 8, 24)
    routines = [
        _routine("r1", "Lavar a louça", today - timedelta(days=2)),
        _routine("r2", "Tirar o lixo", today, "Minha esposa"),
        _routine("r3", "Limpar sala", None),
        _routine("r4", "Regar plantas", None),
        _routine("r5", "Organizar armário", None),
    ]
    calendar = [
        _event("c1", "Dentista", today + timedelta(days=1), time(14)),
        _event("c2", "Reunião", today + timedelta(days=1), time(14)),
        _event("c3", "Cinema", today + timedelta(days=2), time(20)),
    ]
    wishlist = [_wish("w1", "Micro-ondas", today + timedelta(days=3))]

    alerts = radar.build_radar_alerts(
        routines,
        calendar,
        wishlist,
        reference=today,
        max_items=5,
    )

    assert len(alerts) == 5
    assert [item.kind for item in alerts[:3]] == [
        "calendar_conflict",
        "routine_overdue",
        "routine_today",
    ]
    assert "Dentista" in alerts[0].text
    assert "Lavar a louça" in alerts[1].text
    assert "Micro-ondas" in "\n".join(item.text for item in alerts)


def test_calendar_without_equal_explicit_times_is_not_a_conflict():
    today = date(2026, 8, 24)
    alerts = radar.build_radar_alerts(
        [],
        [
            _event("c1", "Dentista", today, time(14)),
            _event("c2", "Reunião", today, time(15)),
            _event("c3", "Entrega", today),
        ],
        [],
        reference=today,
    )

    assert all(item.kind != "calendar_conflict" for item in alerts)


def test_completed_records_do_not_create_alerts():
    today = date(2026, 8, 24)
    alerts = radar.build_radar_alerts(
        [_routine("r1", "Feita", today - timedelta(days=1), status="Concluído")],
        [_event("c1", "Cancelado", today, time(10), status="Cancelado")],
        [_wish("w1", "Comprado", today, status="Comprado")],
        reference=today,
    )

    assert alerts == []


def test_radar_before_schedule_does_not_read_notion(monkeypatch, tmp_path):
    monkeypatch.setattr(radar.settings, "radar_hour", 7)
    monkeypatch.setattr(radar.settings, "radar_minute", 30)
    monkeypatch.setattr(
        radar.readers,
        "get_routines",
        lambda: pytest.fail("não deve consultar antes do horário"),
    )

    result = radar.run_daily_radar(
        now=datetime(2026, 8, 24, 7, 29),
        state_path=tmp_path / "radar.json",
    )

    assert result.status == "skipped"
    assert "horário" in result.reason


def test_radar_sends_once_per_day_and_persists_state(monkeypatch, tmp_path):
    today = date(2026, 8, 24)
    state_path = tmp_path / "radar.json"
    notifications_sent = []
    reads = []
    monkeypatch.setattr(
        radar.readers,
        "get_routines",
        lambda: reads.append("routine") or [_routine("r1", "Louça", today)],
    )
    monkeypatch.setattr(radar.readers, "get_calendar", lambda: [])
    monkeypatch.setattr(radar.readers, "get_wishlist", lambda: [])
    monkeypatch.setattr(
        radar,
        "notify_household_radar",
        lambda message: notifications_sent.append(message)
        or NotificationResult(True, "radar_mobile", ("Eu", "Minha esposa")),
    )

    first = radar.run_daily_radar(
        now=datetime(2026, 8, 24, 8),
        state_path=state_path,
    )
    second = radar.run_daily_radar(
        now=datetime(2026, 8, 24, 12),
        state_path=state_path,
    )

    assert first.status == "sent"
    assert second.status == "skipped"
    assert len(notifications_sent) == 1
    assert reads == ["routine"]
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["last_completed_date"] == "2026-08-24"
    assert saved["last_alert_count"] == 1


def test_failed_notification_waits_before_retry(monkeypatch, tmp_path):
    today = date(2026, 8, 24)
    state_path = tmp_path / "radar.json"
    attempts = []
    monkeypatch.setattr(
        radar.readers,
        "get_routines",
        lambda: [_routine("r1", "Louça", today)],
    )
    monkeypatch.setattr(radar.readers, "get_calendar", lambda: [])
    monkeypatch.setattr(radar.readers, "get_wishlist", lambda: [])

    def notify(_message):
        attempts.append("notification")
        return NotificationResult(
            len(attempts) > 1,
            "radar_mobile" if len(attempts) > 1 else "failed",
        )

    monkeypatch.setattr(radar, "notify_household_radar", notify)

    failed = radar.run_daily_radar(
        now=datetime(2026, 8, 24, 8),
        state_path=state_path,
    )
    waiting = radar.run_daily_radar(
        now=datetime(2026, 8, 24, 8, 10),
        state_path=state_path,
    )
    retried = radar.run_daily_radar(
        now=datetime(2026, 8, 24, 8, 31),
        state_path=state_path,
    )

    assert failed.status == "failed"
    assert waiting.status == "skipped"
    assert retried.status == "sent"
    assert attempts == ["notification", "notification"]


def test_empty_radar_marks_day_complete_without_notification(monkeypatch, tmp_path):
    monkeypatch.setattr(radar.readers, "get_routines", lambda: [])
    monkeypatch.setattr(radar.readers, "get_calendar", lambda: [])
    monkeypatch.setattr(radar.readers, "get_wishlist", lambda: [])
    monkeypatch.setattr(
        radar,
        "notify_household_radar",
        lambda _message: pytest.fail("não deve notificar sem alerta"),
    )

    result = radar.run_daily_radar(
        now=datetime(2026, 8, 24, 8),
        state_path=tmp_path / "radar.json",
    )

    assert result.status == "empty"


def test_identical_digest_is_suppressed_for_three_days(monkeypatch, tmp_path):
    state_path = tmp_path / "radar.json"
    notifications_sent = []
    routines = [
        _routine(f"r{index}", f"Tarefa {index}", None)
        for index in range(1, 5)
    ]
    monkeypatch.setattr(radar.readers, "get_routines", lambda: routines)
    monkeypatch.setattr(radar.readers, "get_calendar", lambda: [])
    monkeypatch.setattr(radar.readers, "get_wishlist", lambda: [])
    monkeypatch.setattr(
        radar,
        "notify_household_radar",
        lambda message: notifications_sent.append(message)
        or NotificationResult(True, "radar_mobile"),
    )

    first = radar.run_daily_radar(
        now=datetime(2026, 8, 24, 8),
        state_path=state_path,
    )
    repeated = radar.run_daily_radar(
        now=datetime(2026, 8, 25, 8),
        state_path=state_path,
    )
    after_window = radar.run_daily_radar(
        now=datetime(2026, 8, 27, 8, 1),
        state_path=state_path,
    )

    assert first.status == "sent"
    assert repeated.status == "suppressed"
    assert after_window.status == "sent"
    assert len(notifications_sent) == 2


def test_radar_notification_mentions_both_people_on_mobile(monkeypatch):
    calls = []
    monkeypatch.setattr(
        notifications,
        "household_user_ids",
        lambda: {"Eu": "calebe-id", "Minha esposa": "carol-id"},
    )
    monkeypatch.setattr(
        notifications,
        "request",
        lambda method, path, body: calls.append((method, path, body)) or {},
    )
    monkeypatch.setattr(
        notifications.settings,
        "notion_mobile_page_id",
        "mobile-page",
    )

    result = notifications.notify_household_radar("🌿 Radar de teste")

    assert result == NotificationResult(
        True,
        "radar_mobile",
        ("Eu", "Minha esposa"),
    )
    assert calls[0][2]["parent"]["page_id"] == "mobile-page"
    mentions = [
        item["mention"]["user"]["id"]
        for item in calls[0][2]["rich_text"]
        if item["type"] == "mention"
    ]
    assert mentions == ["calebe-id", "carol-id"]


def test_worker_keeps_running_when_radar_raises(monkeypatch):
    monkeypatch.setattr(
        worker,
        "run_daily_radar",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError("Notion")),
    )

    assert worker._run_radar_safely() is None
