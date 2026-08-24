from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.notion.client import (
    create_page,
    optional_property_name,
    property_name,
)
from app.notion.notifications import notify_routine_assignment
from app.schemas.actions import (
    FinanceAction,
    WishlistAction,
    PlaceAction,
    CalendarAction,
    RoutineAction,
)


def _title(value: str):
    return {
        "title": [
            {
                "type": "text",
                "text": {"content": value[:2000]},
            }
        ]
    }


def _rich(value: str):
    if not value:
        return {"rich_text": []}
    return {
        "rich_text": [
            {
                "type": "text",
                "text": {"content": value[:2000]},
            }
        ]
    }


def _select(value: str):
    return {"select": {"name": value}}


def _p(ds_id: str, logical_name: str) -> str:
    return property_name(ds_id, logical_name)


def _optional_rich(
    props: dict,
    ds_id: str,
    logical_name: str,
    value: str,
):
    real_name = optional_property_name(ds_id, logical_name)
    if real_name and value:
        props[real_name] = _rich(value)


def _optional_select(
    props: dict,
    ds_id: str,
    logical_name: str,
    value: str | None,
):
    real_name = optional_property_name(ds_id, logical_name)
    if real_name and value:
        props[real_name] = _select(value)


def write_finance(a: FinanceAction) -> dict:
    missing = a.required_missing()
    if missing:
        raise ValueError(
            "Campos financeiros ausentes: " + ", ".join(missing)
        )

    ds = settings.notion_finances_data_source_id
    props = {
        _p(ds, "Movimento"): _title(a.movimento),
        _p(ds, "Categoria"): _select(a.categoria),
        _p(ds, "Data"): {"date": {"start": a.data.isoformat()}},
        _p(ds, "Observacao"): _rich(a.observacao),
        _p(ds, "Pago por"): _select(a.pago_por),
        _p(ds, "Status"): _select(a.status),
        _p(ds, "Tipo"): _select(a.tipo),
        _p(ds, "Valor"): {"number": a.valor},
    }
    _optional_rich(props, ds, "Origem IA", a.source_key)
    return create_page(ds, props)


def write_wishlist(a: WishlistAction) -> dict:
    if not a.item:
        raise ValueError("Item da wishlist ausente.")

    ds = settings.notion_wishlist_data_source_id
    props = {
        _p(ds, "Item"): _title(a.item),
        _p(ds, "Observacao"): _rich(a.observacao),
        _p(ds, "Prioridade"): _select(a.prioridade),
        _p(ds, "Status"): _select(a.status),
        _p(ds, "Tipo"): _select(a.tipo),
    }

    if a.data_desejada:
        props[_p(ds, "Data desejada")] = {
            "date": {"start": a.data_desejada.isoformat()}
        }
    if a.link:
        props[_p(ds, "Link")] = {"url": a.link}
    if a.preco_estimado is not None:
        props[_p(ds, "Preco estimado")] = {
            "number": a.preco_estimado
        }
    _optional_select(
        props,
        ds,
        "Relacao do preco",
        a.preco_relacao,
    )
    _optional_select(
        props,
        ds,
        "Responsavel",
        a.responsavel,
    )
    _optional_rich(props, ds, "Origem IA", a.source_key)

    return create_page(ds, props)


def write_place(a: PlaceAction) -> dict:
    if not a.lugar:
        raise ValueError("Lugar/experiencia ausente.")

    ds = settings.notion_places_data_source_id
    props = {
        _p(ds, "Lugar / Experiencia"): _title(a.lugar),
        _p(ds, "Descricao"): _rich(a.descricao),
        _p(ds, "Local"): _rich(a.local),
        _p(ds, "Prioridade"): _select(a.prioridade),
        _p(ds, "Status"): _select(a.status),
        _p(ds, "Tipo"): _select(a.tipo),
    }

    if a.data_planejada:
        props[_p(ds, "Data planejada")] = {
            "date": {"start": a.data_planejada.isoformat()}
        }
    if a.link:
        props[_p(ds, "Link")] = {"url": a.link}
    if a.valor_estimado is not None:
        props[_p(ds, "Valor estimado")] = {
            "number": a.valor_estimado
        }
    _optional_rich(props, ds, "Origem IA", a.source_key)

    return create_page(ds, props)


def write_calendar(a: CalendarAction) -> dict:
    if not a.evento or not a.data:
        raise ValueError(
            "Evento e data sao necessarios para o calendario."
        )

    ds = settings.notion_calendar_data_source_id
    start = a.data.isoformat()
    if a.hora:
        start = datetime.combine(
            a.data,
            a.hora,
            tzinfo=ZoneInfo(settings.app_timezone),
        ).isoformat()

    props = {
        _p(ds, "Evento"): _title(a.evento),
        _p(ds, "Data"): {"date": {"start": start}},
        _p(ds, "Local"): _rich(a.local),
        _p(ds, "Observacao"): _rich(a.observacao),
        _p(ds, "Quem"): _select(a.quem),
        _p(ds, "Status"): _select(a.status),
        _p(ds, "Tipo"): _select(a.tipo),
    }
    _optional_rich(props, ds, "Origem IA", a.source_key)

    return create_page(ds, props)


def write_routine(a: RoutineAction) -> dict:
    if not a.tarefa:
        raise ValueError("Tarefa da rotina ausente.")

    ds = settings.notion_routine_data_source_id
    props = {
        _p(ds, "Tarefa"): _title(a.tarefa),
        _p(ds, "Categoria"): _select(a.categoria),
        _p(ds, "Frequencia"): _select(a.frequencia),
        _p(ds, "Observacao"): _rich(a.observacao),
        _p(ds, "Responsavel"): _select(a.responsavel),
        _p(ds, "Status"): _select(a.status),
    }

    if a.dia_data:
        props[_p(ds, "Dia / Data")] = {
            "date": {"start": a.dia_data.isoformat()}
        }
    _optional_rich(props, ds, "Recorrencia", a.recurrence_rule)
    _optional_rich(props, ds, "Origem IA", a.source_key)
    _optional_select(
        props,
        ds,
        "Solicitado por",
        a.solicitado_por,
    )

    page = create_page(ds, props)
    if page.get("id"):
        notification = notify_routine_assignment(
            page["id"],
            a.tarefa,
            a.responsavel,
            a.solicitado_por,
        )
        page["_cantinho_notification"] = {
            "sent": notification.sent,
            "mode": notification.mode,
            "recipients": list(notification.recipients),
        }
    return page
