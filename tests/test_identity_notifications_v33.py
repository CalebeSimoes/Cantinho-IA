from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

import app.ai.parsers as parsers
import app.ai.router as router
import app.notion.inbox as inbox
import app.notion.notifications as notifications
import app.notion.users as notion_users
import app.notion.writers as writers
import app.worker as worker
from app.notion.notifications import NotificationResult
from app.schemas.actions import RoutineAction


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(
        parsers,
        "now",
        lambda: datetime(
            2026,
            8,
            24,
            12,
            0,
            tzinfo=ZoneInfo("America/Sao_Paulo"),
        ),
    )


@pytest.mark.parametrize(
    ("name", "role"),
    [
        ("Calebe Simões", "Eu"),
        ("Caleb", "Eu"),
        ("Carolina Fraiz", "Minha esposa"),
        ("Carol", "Minha esposa"),
        ("Cantinho AI", None),
    ],
)
def test_notion_account_name_maps_to_household_role(name, role):
    assert notion_users.role_from_name(name) == role


def test_inbox_infers_carol_from_page_creator(monkeypatch):
    monkeypatch.setattr(
        inbox,
        "query_data_source",
        lambda *args, **kwargs: [{
            "id": "page-1",
            "created_by": {"id": "carol-user"},
            "properties": {
                "Mensagem": {
                    "title": [{"plain_text": "Calebe assinar HBO"}]
                },
                "Autor": {"select": None},
                "Destino": {"select": None},
            },
        }],
    )
    monkeypatch.setattr(
        inbox,
        "author_from_creator_id",
        lambda user_id: "Carol",
    )

    item = inbox.pending_items()[0]

    assert item.author == "Carol"
    assert item.creator_user_id == "carol-user"
    assert item.author_inferred is True


def test_explicit_inbox_author_overrides_creator(monkeypatch):
    monkeypatch.setattr(
        inbox,
        "query_data_source",
        lambda *args, **kwargs: [{
            "id": "page-1",
            "created_by": {"id": "carol-user"},
            "properties": {
                "Mensagem": {
                    "title": [{"plain_text": "Assinar HBO"}]
                },
                "Autor": {"select": {"name": "Eu"}},
                "Destino": {"select": None},
            },
        }],
    )
    monkeypatch.setattr(
        inbox,
        "author_from_creator_id",
        lambda user_id: "Carol",
    )

    item = inbox.pending_items()[0]

    assert item.author == "Eu"
    assert item.author_inferred is False


def test_inbox_waits_for_message_to_stop_changing(monkeypatch):
    inbox._stability_cache.clear()
    first = inbox.InboxItem(
        "page-1",
        "Jogar o lixo fora toda terça, quint",
        "Automático",
        "Eu",
        last_edited_time="2026-08-25T14:54:00.000Z",
    )
    complete = inbox.InboxItem(
        "page-1",
        "Jogar o lixo fora toda terça, quinta e sábado",
        "Automático",
        "Eu",
        last_edited_time="2026-08-25T14:55:00.000Z",
    )

    assert inbox.stable_items(
        [first], stability_seconds=20, monotonic_now=100
    ) == []
    assert inbox.stable_items(
        [complete], stability_seconds=20, monotonic_now=110
    ) == []
    assert inbox.stable_items(
        [complete], stability_seconds=20, monotonic_now=129
    ) == []
    assert inbox.stable_items(
        [complete], stability_seconds=20, monotonic_now=130
    ) == [complete]


def test_inbox_stability_cache_drops_pages_no_longer_pending():
    inbox._stability_cache.clear()
    item = inbox.InboxItem(
        "page-1",
        "Lavar a louça",
        "Automático",
        "Eu",
        last_edited_time="2026-08-25T14:55:00.000Z",
    )
    inbox.stable_items(
        [item], stability_seconds=20, monotonic_now=100
    )

    inbox.stable_items([], stability_seconds=20, monotonic_now=110)

    assert inbox._stability_cache == {}


@pytest.mark.parametrize(
    "phrase",
    [
        "Calebe assinar HBO",
        "Carolina lavar a louça hoje à noite",
        "Calebe e Carol organizar a casa",
    ],
)
def test_named_direct_assignment_routes_without_ollama(
    monkeypatch,
    phrase,
):
    monkeypatch.setattr(
        router,
        "structured_chat",
        lambda *args, **kwargs: pytest.fail(
            "atribuição direta deveria ser determinística"
        ),
    )

    assert router.route_message(phrase).destination == "rotina"


def test_carol_assigns_direct_task_to_calebe():
    action = parsers.fast_routine(
        "Calebe assinar HBO",
        author="Carol",
    )

    assert action.tarefa == "assinar hbo"
    assert action.responsavel == "Eu"
    assert action.solicitado_por == "Minha esposa"


def test_sender_is_default_responsible_when_name_is_omitted():
    action = parsers.fast_routine("Assinar HBO", author="Carol")

    assert action.tarefa == "assinar hbo"
    assert action.responsavel == "Minha esposa"
    assert action.solicitado_por == "Minha esposa"


def test_calebe_assigns_direct_task_to_carol():
    action = parsers.fast_routine(
        "Carol lavar a louça hoje à noite",
        author="Eu",
    )

    assert action.tarefa == "lavar a louca"
    assert action.responsavel == "Minha esposa"
    assert action.solicitado_por == "Eu"
    assert action.dia_data == date(2026, 8, 24)


def test_leading_subject_wins_over_other_name_in_task():
    action = parsers.fast_routine(
        "Calebe fazer massagem na Carol hoje",
        author="Carol",
    )

    assert action.tarefa == "fazer massagem na carol"
    assert action.responsavel == "Eu"


def test_named_couple_is_jointly_responsible():
    action = parsers.fast_routine(
        "Calebe e Carol organizar a casa",
        author="Eu",
    )

    assert action.tarefa == "organizar a casa"
    assert action.responsavel == "Nós dois"


def test_notification_mentions_only_the_other_person(monkeypatch):
    calls = []
    monkeypatch.setattr(
        notifications,
        "household_user_ids",
        lambda: {
            "Eu": "calebe-user",
            "Minha esposa": "carol-user",
        },
    )
    monkeypatch.setattr(
        notifications,
        "request",
        lambda method, path, body: calls.append((method, path, body)) or {},
    )

    result = notifications.notify_routine_assignment(
        "routine-page",
        "lavar a louça",
        "Eu",
        "Minha esposa",
    )

    assert result == NotificationResult(True, "mention", ("Eu",))
    assert calls[0][0:2] == ("POST", "/comments")
    mentions = [
        item["mention"]["user"]["id"]
        for item in calls[0][2]["rich_text"]
        if item["type"] == "mention"
    ]
    assert mentions == ["calebe-user"]
    assert "Rotina do casal" in calls[0][2]["rich_text"][-1]["text"]["content"]


def test_self_assignment_does_not_notify(monkeypatch):
    monkeypatch.setattr(
        notifications,
        "request",
        lambda *args: pytest.fail("não deveria enviar aviso"),
    )

    result = notifications.notify_routine_assignment(
        "routine-page",
        "assinar HBO",
        "Minha esposa",
        "Minha esposa",
    )

    assert result == NotificationResult(False, "skipped")


def test_people_property_is_notification_fallback(monkeypatch):
    updates = []
    monkeypatch.setattr(
        notifications,
        "household_user_ids",
        lambda: {"Eu": "calebe-user"},
    )
    monkeypatch.setattr(
        notifications,
        "request",
        lambda *args: (_ for _ in ()).throw(RuntimeError("comments off")),
    )
    monkeypatch.setattr(
        notifications,
        "optional_property_name",
        lambda *args: "Notificar",
    )
    monkeypatch.setattr(
        notifications,
        "update_page",
        lambda page_id, props: updates.append((page_id, props)) or {},
    )

    result = notifications.notify_routine_assignment(
        "routine-page",
        "lavar a louça",
        "Eu",
        "Minha esposa",
    )

    assert result == NotificationResult(True, "people", ("Eu",))
    assert updates == [(
        "routine-page",
        {"Notificar": {"people": [{
            "object": "user",
            "id": "calebe-user",
        }]}},
    )]


def test_routine_writer_persists_requester_and_notification(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        writers.settings,
        "notion_routine_data_source_id",
        "routine",
    )
    monkeypatch.setattr(writers, "_p", lambda ds, name: name)
    monkeypatch.setattr(
        writers,
        "optional_property_name",
        lambda ds, name: name,
    )
    monkeypatch.setattr(
        writers,
        "create_page",
        lambda ds, props: saved.update(ds=ds, props=props) or {
            "id": "created-page"
        },
    )
    monkeypatch.setattr(
        writers,
        "notify_routine_assignment",
        lambda *args: NotificationResult(True, "mention", ("Eu",)),
    )

    page = writers.write_routine(RoutineAction(
        tarefa="lavar a louça",
        responsavel="Eu",
        solicitado_por="Minha esposa",
    ))

    assert saved["props"]["Solicitado por"]["select"]["name"] == (
        "Minha esposa"
    )
    assert page["_cantinho_notification"]["sent"] is True


def test_worker_persists_only_inferred_author(monkeypatch):
    saved = []
    item = type(
        "Item",
        (),
        {
            "page_id": "inbox-page",
            "author": "Carol",
            "author_inferred": True,
        },
    )()
    monkeypatch.setattr(
        worker,
        "set_author",
        lambda page_id, author: saved.append((page_id, author)),
    )

    worker._persist_inferred_author_safely(item)

    assert saved == [("inbox-page", "Carol")]
