import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.ai.router import normalize
from app.config import settings
from app.notion import readers
from app.schemas.actions import QueryIntent


def _today() -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def _money(value: float) -> str:
    raw = f"{value:,.2f}"
    return "R$ " + raw.replace(",", "_").replace(".", ",").replace("_", ".")


def _day(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "sem data"


def _hour(value) -> str:
    return f" às {value.strftime('%H:%M')}" if value else ""


def _period_bounds(
    intent: QueryIntent,
    reference: date,
) -> tuple[date, date] | None:
    if intent.period == "all":
        return None
    if intent.period == "today":
        return reference, reference
    if intent.period == "specific_date" and intent.specific_date:
        return intent.specific_date, intent.specific_date
    if intent.period == "this_week":
        start = reference - timedelta(days=reference.weekday())
        return start, start + timedelta(days=6)
    if intent.period == "this_month":
        end = calendar.monthrange(reference.year, reference.month)[1]
        return date(reference.year, reference.month, 1), date(
            reference.year, reference.month, end
        )
    if intent.period == "last_month":
        end = date(reference.year, reference.month, 1) - timedelta(days=1)
        return date(end.year, end.month, 1), end
    if intent.period == "next_month":
        if reference.month == 12:
            year, month = reference.year + 1, 1
        else:
            year, month = reference.year, reference.month + 1
        end = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, end)
    return None


def _period_label(intent: QueryIntent) -> str:
    labels = {
        "all": "em todo o período",
        "today": "hoje",
        "this_week": "nesta semana",
        "this_month": "neste mês",
        "last_month": "no mês passado",
        "next_month": "no próximo mês",
    }
    if intent.period == "specific_date" and intent.specific_date:
        return f"em {_day(intent.specific_date)}"
    return labels.get(intent.period, "no período pedido")


def _in_period(value: date | None, bounds: tuple[date, date] | None) -> bool:
    if bounds is None:
        return True
    return value is not None and bounds[0] <= value <= bounds[1]


def _same_person(actual: str | None, wanted: str | None) -> bool:
    return wanted is None or actual == wanted


def _contains(term: str | None, *values: str | None) -> bool:
    if not term:
        return True
    needle = normalize(term)
    return any(needle in normalize(value or "") for value in values)


def _cap(answer: str) -> str:
    if len(answer) <= 2000:
        return answer
    return answer[:1978].rstrip() + "… (resultado resumido)"


def _count(value: int, singular: str, plural: str) -> str:
    return f"{value} {singular if value == 1 else plural}"


def _list_lines(lines: list[str], empty: str) -> str:
    if not lines:
        return empty
    shown = lines[:10]
    answer = "\n".join(shown)
    if len(lines) > len(shown):
        answer += f"\n… e mais {len(lines) - len(shown)} registro(s)."
    return answer


def _finance(intent: QueryIntent, reference: date) -> str:
    bounds = _period_bounds(intent, reference)
    records = [
        item for item in readers.get_finances()
        if _in_period(item.data, bounds)
        and _same_person(item.pago_por, intent.person)
        and (not intent.transaction_type or item.tipo == intent.transaction_type)
        and (not intent.status or item.status == intent.status)
        and _contains(
            intent.term,
            item.movimento,
            item.categoria,
            item.observacao,
        )
    ]
    period = _period_label(intent)
    if not records:
        detail = f" com “{intent.term}”" if intent.term else ""
        return f"Não encontrei movimentações{detail} {period}."

    if intent.operation == "summary" or (
        intent.operation == "total" and not intent.transaction_type
    ):
        incoming = sum(item.valor or 0 for item in records if item.tipo == "Entrada")
        outgoing = sum(item.valor or 0 for item in records if item.tipo == "Saída")
        return (
            f"Resumo financeiro {period}: entradas {_money(incoming)}, "
            f"saídas {_money(outgoing)} e saldo {_money(incoming - outgoing)} "
            f"({_count(len(records), 'movimentação', 'movimentações')})."
        )

    if intent.operation == "total":
        total = sum(item.valor or 0 for item in records)
        label = "gasto" if intent.transaction_type == "Saída" else "recebido"
        suffix = f" com {intent.term}" if intent.term else ""
        return (
            f"Total {label}{suffix} {period}: {_money(total)} "
            f"em {_count(len(records), 'movimentação', 'movimentações')}."
        )

    valued = [item for item in records if item.valor is not None]
    if intent.operation == "max":
        if not valued:
            return f"Há movimentações {period}, mas nenhuma tem valor informado."
        item = max(valued, key=lambda value: value.valor or 0)
        return (
            f"Maior movimentação {period}: {item.movimento} — "
            f"{_money(item.valor or 0)} em {_day(item.data)} "
            f"({item.pago_por or 'sem responsável'})."
        )
    if intent.operation == "count":
        return f"Encontrei {_count(len(records), 'movimentação', 'movimentações')} {period}."

    records.sort(key=lambda item: item.data or date.min, reverse=True)
    lines = [
        f"• {_day(item.data)} · {item.movimento} · {_money(item.valor or 0)}"
        for item in records
    ]
    return _list_lines(lines, f"Não encontrei movimentações {period}.")


def _wishlist(intent: QueryIntent, reference: date) -> str:
    bounds = _period_bounds(intent, reference)
    records = [
        item for item in readers.get_wishlist()
        if _in_period(item.data_desejada, bounds)
    ]
    if intent.status == "Ativos":
        records = [
            item for item in records
            if item.status not in {"Comprado", "Desistimos"}
        ]
    elif intent.status:
        records = [item for item in records if item.status == intent.status]

    if not records:
        return "Não encontrei itens da wishlist com esses critérios."
    valued = [item for item in records if item.preco_estimado is not None]
    if intent.operation == "max":
        if not valued:
            return "Há itens na wishlist, mas nenhum tem preço estimado informado."
        item = max(valued, key=lambda value: value.preco_estimado or 0)
        return (
            f"Item mais caro da wishlist: {item.item} — "
            f"{_money(item.preco_estimado or 0)} ({item.status or 'sem status'})."
        )
    if intent.operation == "total":
        return f"Total estimado da wishlist: {_money(sum(item.preco_estimado or 0 for item in valued))}."
    if intent.operation == "count":
        return f"A wishlist tem {_count(len(records), 'item', 'itens')} com esses critérios."
    lines = [
        f"• {item.item} · {item.status or 'sem status'}"
        + (f" · {_money(item.preco_estimado)}" if item.preco_estimado is not None else "")
        for item in records
    ]
    return _list_lines(lines, "Não encontrei itens na wishlist.")


def _places(intent: QueryIntent, reference: date) -> str:
    bounds = _period_bounds(intent, reference)
    records = [
        item for item in readers.get_places()
        if _in_period(item.data_planejada, bounds)
    ]
    if intent.status == "Ativos":
        records = [item for item in records if item.status != "Feito"]
    elif intent.status:
        records = [item for item in records if item.status == intent.status]

    if not records:
        return "Não encontrei lugares ou experiências com esses critérios."
    if intent.operation == "count":
        return f"Encontrei {_count(len(records), 'lugar ou experiência', 'lugares ou experiências')}."
    if intent.operation == "max":
        valued = [item for item in records if item.valor_estimado is not None]
        if not valued:
            return "Há lugares cadastrados, mas nenhum tem valor estimado."
        item = max(valued, key=lambda value: value.valor_estimado or 0)
        return f"Experiência de maior valor: {item.lugar} — {_money(item.valor_estimado or 0)}."
    lines = [
        f"• {item.lugar} · {item.status or 'sem status'}"
        + (f" · {item.local}" if item.local else "")
        for item in records
    ]
    return _list_lines(lines, "Não encontrei lugares cadastrados.")


def _calendar(intent: QueryIntent, reference: date) -> str:
    bounds = _period_bounds(intent, reference)
    records = [
        item for item in readers.get_calendar()
        if _in_period(item.data, bounds)
        and _same_person(item.quem, intent.person)
    ]
    if intent.status == "Ativos":
        records = [item for item in records if item.status != "Concluído"]
    elif intent.status:
        records = [item for item in records if item.status == intent.status]

    records.sort(key=lambda item: item.data or date.max)
    period = _period_label(intent)
    if not records:
        return f"Não há compromissos encontrados {period}."
    if intent.operation == "count":
        return f"Há {_count(len(records), 'compromisso', 'compromissos')} {period}."
    lines = [
        f"• {_day(item.data)}{_hour(item.hora)} · {item.evento}"
        + (f" · {item.local}" if item.local else "")
        for item in records
    ]
    return _list_lines(lines, f"Não há compromissos {period}.")


def _routines(intent: QueryIntent, reference: date) -> str:
    bounds = _period_bounds(intent, reference)
    records = [
        item for item in readers.get_routines()
        if _in_period(item.dia_data, bounds)
        and _same_person(item.responsavel, intent.person)
        and (not intent.category or item.categoria == intent.category)
    ]
    if intent.status == "Atrasadas":
        records = [
            item for item in records
            if item.status != "Concluído"
            and item.dia_data is not None
            and item.dia_data < reference
        ]
    elif intent.status == "Pendentes":
        records = [item for item in records if item.status != "Concluído"]
    elif intent.status:
        records = [item for item in records if item.status == intent.status]

    records.sort(key=lambda item: item.dia_data or date.max)
    if not records:
        return "Não encontrei tarefas ou rotinas com esses critérios."
    if intent.operation == "count":
        return f"Encontrei {_count(len(records), 'tarefa ou rotina', 'tarefas ou rotinas')}."
    lines = [
        f"• {item.tarefa} · {_day(item.dia_data)} · {item.status or 'sem status'}"
        for item in records
    ]
    return _list_lines(lines, "Não encontrei tarefas ou rotinas.")


def execute_query(intent: QueryIntent, reference: date | None = None) -> str:
    """Executa uma consulta local sobre leitores paginados do Notion."""
    reference = reference or _today()
    handlers = {
        "financas": _finance,
        "wishlist": _wishlist,
        "lugares": _places,
        "calendario": _calendar,
        "rotina": _routines,
    }
    handler = handlers.get(intent.domain)
    if not handler:
        raise ValueError("Domínio de consulta não suportado.")
    return _cap(handler(intent, reference))
