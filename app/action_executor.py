from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher

from app import action_store
from app.ai.router import normalize
from app.config import settings
from app.notion import readers
from app.notion.client import (
    optional_property_name,
    property_name,
    update_page,
)
from app.notion.writers import (
    write_calendar,
    write_finance,
    write_place,
    write_routine,
    write_wishlist,
)
from app.routine_service import complete_routine
from app.schemas.actions import (
    ActionPlan,
    CalendarAction,
    FinanceAction,
    PlaceAction,
    RoutineAction,
    WishlistAction,
)


@dataclass(frozen=True)
class ExecutionResult:
    summary: str
    first_url: str | None = None


def _rich(value: str) -> dict:
    return {
        "rich_text": [{
            "type": "text",
            "text": {"content": value[:2000]},
        }]
    }


def _origin(action_id: str) -> str:
    return f"cantinho:{action_id}"


def _similarity(left: str, right: str) -> float:
    left_n, right_n = normalize(left), normalize(right)
    if left_n == right_n:
        return 1
    if left_n in right_n or right_n in left_n:
        return .92
    return SequenceMatcher(None, left_n, right_n).ratio()


def _best(subject: str, records: list, attribute: str):
    ranked = sorted(
        (
            (_similarity(subject, getattr(record, attribute)), record)
            for record in records
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    return ranked[0][1] if ranked and ranked[0][0] >= .55 else None


def _origin_exists(destination: str, marker: str) -> bool:
    getters = {
        "financas": readers.get_finances,
        "wishlist": readers.get_wishlist,
        "lugares": readers.get_places,
        "calendario": readers.get_calendar,
        "rotina": readers.get_routines,
    }
    return any(
        record.source_key == marker
        for record in getters[destination]()
    )


def _set_origin(props: dict, ds: str, marker: str):
    name = optional_property_name(ds, "Origem IA")
    if name:
        props[name] = _rich(marker)


def _create(destination: str, payload: dict, marker: str) -> tuple[str, str | None]:
    models = {
        "financas": FinanceAction,
        "wishlist": WishlistAction,
        "lugares": PlaceAction,
        "calendario": CalendarAction,
        "rotina": RoutineAction,
    }
    writers = {
        "financas": write_finance,
        "wishlist": write_wishlist,
        "lugares": write_place,
        "calendario": write_calendar,
        "rotina": write_routine,
    }
    parsed = models[destination].model_validate(payload)
    parsed.source_key = marker
    page = writers[destination](parsed)
    labels = {
        "financas": "Finanças",
        "wishlist": "Wishlist",
        "lugares": "Lugares",
        "calendario": "Calendário",
        "rotina": "Rotina",
    }
    return f"{labels[destination]}: criado “{_subject(parsed)}”", page.get("url")


def _subject(parsed) -> str:
    for name in ("movimento", "item", "lugar", "evento", "tarefa"):
        value = getattr(parsed, name, None)
        if value:
            return value
    return "registro"


def _update_wishlist(subject: str, payload: dict, marker: str) -> tuple[str, str | None]:
    record = _best(subject, readers.get_wishlist(), "item")
    status = payload.get("status", "Comprado")
    price = payload.get("preco_estimado")
    if record:
        ds = settings.notion_wishlist_data_source_id
        props = {
            property_name(ds, "Status"): {"select": {"name": status}}
        }
        if price is not None:
            props[property_name(ds, "Preco estimado")] = {"number": price}
        _set_origin(props, ds, marker)
        page = update_page(record.page_id, props)
        return f"Wishlist: “{record.item}” → {status}", page.get("url")

    parsed = WishlistAction(
        item=payload.get("item") or subject,
        status=status,
        preco_estimado=price,
        observacao="Criado por ação múltipla após compra.",
        source_key=marker,
    )
    page = write_wishlist(parsed)
    return f"Wishlist: “{parsed.item}” registrado como {status}", page.get("url")


def _update_place(subject: str, payload: dict, marker: str) -> tuple[str, str | None]:
    record = _best(subject, readers.get_places(), "lugar")
    status = payload.get("status", "Reservado")
    planned = payload.get("data_planejada")
    if record:
        ds = settings.notion_places_data_source_id
        props = {
            property_name(ds, "Status"): {"select": {"name": status}}
        }
        if planned:
            props[property_name(ds, "Data planejada")] = {
                "date": {"start": str(planned)}
            }
        _set_origin(props, ds, marker)
        page = update_page(record.page_id, props)
        return f"Lugares: “{record.lugar}” → {status}", page.get("url")

    parsed = PlaceAction.model_validate(payload)
    parsed.lugar = parsed.lugar or subject
    parsed.source_key = marker
    page = write_place(parsed)
    return f"Lugares: “{parsed.lugar}” registrado como {status}", page.get("url")


def _execute_action(action) -> tuple[str, str | None]:
    marker = _origin(action.action_id)
    if _origin_exists(action.destination, marker):
        return f"{action.subject}: já aplicado", None
    if action.operation == "create":
        return _create(action.destination, action.payload, marker)
    if action.operation == "update" and action.destination == "wishlist":
        return _update_wishlist(action.subject, action.payload, marker)
    if action.operation == "update" and action.destination == "lugares":
        return _update_place(action.subject, action.payload, marker)
    if action.operation == "complete" and action.destination == "rotina":
        result = complete_routine(action.subject)
        if not result.success:
            raise ValueError(result.summary)
        return result.summary, None
    raise ValueError(
        f"Ação não suportada: {action.operation}/{action.destination}"
    )


def _preflight(plan: ActionPlan):
    models = {
        "financas": FinanceAction,
        "wishlist": WishlistAction,
        "lugares": PlaceAction,
        "calendario": CalendarAction,
        "rotina": RoutineAction,
    }
    for action in plan.actions:
        if action.operation == "create":
            models[action.destination].model_validate(action.payload)
        elif action.operation == "update" and action.destination not in {
            "wishlist", "lugares"
        }:
            raise ValueError(
                f"Atualização de {action.destination} não suportada."
            )


def execute_plan(
    plan: ActionPlan,
    source_key: str,
    done_action_ids: list[str] | None = None,
) -> ExecutionResult:
    _preflight(plan)
    done = set(done_action_ids or [])
    summaries = []
    first_url = None
    for action in plan.actions:
        if action.action_id in done:
            summaries.append(f"{action.subject}: já aplicado")
            continue
        summary, url = _execute_action(action)
        action_store.mark_action_done(source_key, action.action_id)
        summaries.append(summary)
        first_url = first_url or url
    answer = "✅ Plano executado com segurança:\n" + "\n".join(
        f"{index}. {summary}"
        for index, summary in enumerate(summaries, 1)
    )
    action_store.finish(source_key, answer)
    return ExecutionResult(answer, first_url)
