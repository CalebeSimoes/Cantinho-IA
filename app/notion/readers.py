from dataclasses import dataclass
from datetime import date, datetime, time

from app.config import settings
from app.notion.client import (
    date_value,
    number_value,
    property_value,
    query_data_source,
    rich_text_value,
    select_value,
    title_value,
    url_value,
)


def _date(prop: dict | None) -> date | None:
    value = date_value(prop)
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _p(properties: dict, name: str) -> dict | None:
    return property_value(properties, name)


@dataclass(frozen=True)
class FinanceRecord:
    page_id: str
    movimento: str
    valor: float | None
    tipo: str | None
    categoria: str | None
    pago_por: str | None
    status: str | None
    data: date | None
    observacao: str
    source_key: str = ""


@dataclass(frozen=True)
class WishlistRecord:
    page_id: str
    item: str
    preco_estimado: float | None
    status: str | None
    prioridade: str | None
    tipo: str | None
    data_desejada: date | None
    observacao: str
    link: str | None
    source_key: str = ""
    preco_relacao: str | None = None
    responsavel: str | None = None


@dataclass(frozen=True)
class PlaceRecord:
    page_id: str
    lugar: str
    status: str | None
    prioridade: str | None
    tipo: str | None
    data_planejada: date | None
    valor_estimado: float | None
    local: str
    descricao: str
    source_key: str = ""


@dataclass(frozen=True)
class CalendarRecord:
    page_id: str
    evento: str
    data: date | None
    quem: str | None
    status: str | None
    tipo: str | None
    local: str
    observacao: str
    hora: time | None = None
    source_key: str = ""


@dataclass(frozen=True)
class RoutineRecord:
    page_id: str
    tarefa: str
    categoria: str | None
    dia_data: date | None
    frequencia: str | None
    responsavel: str | None
    status: str | None
    observacao: str
    recurrence_rule: str = "once"
    last_completed: date | None = None
    source_key: str = ""
    solicitado_por: str | None = None


def _time(prop: dict | None) -> time | None:
    value = date_value(prop)
    if not value or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.time().replace(tzinfo=None)
    except ValueError:
        return None


def get_finances() -> list[FinanceRecord]:
    pages = query_data_source(settings.notion_finances_data_source_id)
    records = []
    for page in pages:
        props = page.get("properties", {})
        record = FinanceRecord(
            page_id=page.get("id", ""),
            movimento=title_value(_p(props, "Movimento")),
            valor=number_value(_p(props, "Valor")),
            tipo=select_value(_p(props, "Tipo")),
            categoria=select_value(_p(props, "Categoria")),
            pago_por=select_value(_p(props, "Pago por")),
            status=select_value(_p(props, "Status")),
            data=_date(_p(props, "Data")),
            observacao=rich_text_value(_p(props, "Observacao")),
            source_key=rich_text_value(_p(props, "Origem IA")),
        )
        if record.movimento:
            records.append(record)
    return records


def get_wishlist() -> list[WishlistRecord]:
    pages = query_data_source(settings.notion_wishlist_data_source_id)
    records = []
    for page in pages:
        props = page.get("properties", {})
        record = WishlistRecord(
            page_id=page.get("id", ""),
            item=title_value(_p(props, "Item")),
            preco_estimado=number_value(_p(props, "Preco estimado")),
            status=select_value(_p(props, "Status")),
            prioridade=select_value(_p(props, "Prioridade")),
            tipo=select_value(_p(props, "Tipo")),
            data_desejada=_date(_p(props, "Data desejada")),
            observacao=rich_text_value(_p(props, "Observacao")),
            link=url_value(_p(props, "Link")),
            source_key=rich_text_value(_p(props, "Origem IA")),
            preco_relacao=select_value(_p(props, "Relacao do preco")),
            responsavel=select_value(_p(props, "Responsavel")),
        )
        if record.item:
            records.append(record)
    return records


def get_places() -> list[PlaceRecord]:
    pages = query_data_source(settings.notion_places_data_source_id)
    records = []
    for page in pages:
        props = page.get("properties", {})
        record = PlaceRecord(
            page_id=page.get("id", ""),
            lugar=title_value(_p(props, "Lugar / Experiencia")),
            status=select_value(_p(props, "Status")),
            prioridade=select_value(_p(props, "Prioridade")),
            tipo=select_value(_p(props, "Tipo")),
            data_planejada=_date(_p(props, "Data planejada")),
            valor_estimado=number_value(_p(props, "Valor estimado")),
            local=rich_text_value(_p(props, "Local")),
            descricao=rich_text_value(_p(props, "Descricao")),
            source_key=rich_text_value(_p(props, "Origem IA")),
        )
        if record.lugar:
            records.append(record)
    return records


def get_calendar() -> list[CalendarRecord]:
    pages = query_data_source(settings.notion_calendar_data_source_id)
    records = []
    for page in pages:
        props = page.get("properties", {})
        record = CalendarRecord(
            page_id=page.get("id", ""),
            evento=title_value(_p(props, "Evento")),
            data=_date(_p(props, "Data")),
            quem=select_value(_p(props, "Quem")),
            status=select_value(_p(props, "Status")),
            tipo=select_value(_p(props, "Tipo")),
            local=rich_text_value(_p(props, "Local")),
            observacao=rich_text_value(_p(props, "Observacao")),
            hora=_time(_p(props, "Data")),
            source_key=rich_text_value(_p(props, "Origem IA")),
        )
        if record.evento:
            records.append(record)
    return records


def get_routines() -> list[RoutineRecord]:
    pages = query_data_source(settings.notion_routine_data_source_id)
    records = []
    for page in pages:
        props = page.get("properties", {})
        record = RoutineRecord(
            page_id=page.get("id", ""),
            tarefa=title_value(_p(props, "Tarefa")),
            categoria=select_value(_p(props, "Categoria")),
            dia_data=_date(_p(props, "Dia / Data")),
            frequencia=select_value(_p(props, "Frequencia")),
            responsavel=select_value(_p(props, "Responsavel")),
            status=select_value(_p(props, "Status")),
            observacao=rich_text_value(_p(props, "Observacao")),
            recurrence_rule=(
                rich_text_value(_p(props, "Recorrencia")) or "once"
            ),
            last_completed=_date(_p(props, "Ultima conclusao")),
            source_key=rich_text_value(_p(props, "Origem IA")),
            solicitado_por=select_value(_p(props, "Solicitado por")),
        )
        if record.tarefa:
            records.append(record)
    return records
