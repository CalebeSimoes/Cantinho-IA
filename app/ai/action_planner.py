import re
from datetime import date, time

from app.ai.date_utils import resolve_date_expression
from app.ai.ollama_client import structured_chat
from app.ai.parsers import (
    money,
    normalize,
    parse_calendar,
    parse_finance,
    parse_place,
    parse_routine,
    parse_wishlist,
)
from app.ai.prompts import MULTI_ACTION_PROMPT
from app.ai.router import route_message, score_message
from app.schemas.actions import (
    AIActionPlan,
    ActionPlan,
    CalendarAction,
    FinanceAction,
    PlaceAction,
    PlannedAction,
    RoutineAction,
    WishlistAction,
)


def _clock(message: str) -> time | None:
    text = normalize(message)
    match = re.search(
        r"\b(?:as|a partir das)\s+([01]?\d|2[0-3])"
        r"(?:(?::|h)([0-5]?\d)?)?\b",
        text,
    ) or re.search(r"\b([01]?\d|2[0-3])h([0-5]?\d)?\b", text)
    if not match:
        return None
    return time(int(match.group(1)), int(match.group(2) or 0))


def _paid_by(message: str, author: str) -> str:
    text = normalize(message)
    if re.search(r"\b(?:compramos|pagamos|nos dois|juntos)\b", text):
        return "Nós dois"
    if author == "Carol" or re.search(r"\bcarol\b", text):
        return "Minha esposa"
    return "Eu"


def _clean(value: str) -> str:
    value = re.sub(r"^(?:o|a|os|as|um|uma)\s+", "", value.strip())
    return value.strip(" .,-").capitalize()


def _finance_payload(
    subject: str,
    value: float,
    message: str,
    author: str,
    reference: date,
    category: str = "Compras",
) -> dict:
    return FinanceAction(
        movimento=subject,
        valor=value,
        tipo="Saída",
        categoria=category,
        pago_por=_paid_by(message, author),
        status="Pago",
        data=reference,
        observacao=message,
    ).model_dump(mode="json")


def _wishlist_purchase(
    message: str,
    author: str,
    reference: date,
) -> ActionPlan | None:
    text = normalize(message)
    match = re.search(
        r"\b(?:comprei|compramos)\s+(?:o|a|um|uma)?\s*"
        r"(.+?)\s+(?:da wishlist|que estava na wishlist)\s+"
        r"por\s+(?:r\$\s*)?[\d.,]+",
        text,
    )
    value = money(message)
    if not match or value is None:
        return None
    item = _clean(match.group(1))
    return ActionPlan(
        reason="compra de item acompanhado na wishlist",
        actions=[
            PlannedAction(
                operation="update",
                destination="wishlist",
                subject=item,
                payload={
                    "item": item,
                    "status": "Comprado",
                    "preco_estimado": value,
                },
                reason="marcar desejo como comprado",
            ),
            PlannedAction(
                operation="create",
                destination="financas",
                subject=item,
                payload=_finance_payload(
                    item, value, message, author, reference
                ),
                reason="registrar o gasto realizado",
            ),
        ],
    )


def _reservation(
    message: str,
    author: str,
    reference: date,
) -> ActionPlan | None:
    text = normalize(message)
    match = re.search(
        r"\b(?:reservei|reservamos)\s+(?:o|a|um|uma)?\s*"
        r"(.+?)\s+para\s+(.+)$",
        text,
    )
    event_date = resolve_date_expression(message, reference)
    if not match or event_date is None:
        return None
    place = _clean(match.group(1))
    place_type = "Restaurante" if "restaurante" in normalize(place) else "Outro"
    place_payload = PlaceAction(
        lugar=place,
        data_planejada=event_date,
        descricao=message,
        status="Reservado",
        tipo=place_type,
    ).model_dump(mode="json")
    calendar_payload = CalendarAction(
        evento=f"Reserva: {place}",
        data=event_date,
        hora=_clock(message),
        observacao=message,
        quem=_paid_by(message, author),
        status="Confirmado",
        tipo="Encontro" if place_type == "Restaurante" else "Compromisso",
    ).model_dump(mode="json")
    return ActionPlan(
        reason="reserva de lugar com compromisso datado",
        actions=[
            PlannedAction(
                operation="update",
                destination="lugares",
                subject=place,
                payload=place_payload,
                reason="marcar lugar como reservado",
            ),
            PlannedAction(
                operation="create",
                destination="calendario",
                subject=f"Reserva: {place}",
                payload=calendar_payload,
                reason="criar compromisso da reserva",
            ),
        ],
    )


def _ticket_purchase(
    message: str,
    author: str,
    reference: date,
) -> ActionPlan | None:
    text = normalize(message)
    match = re.search(
        r"\b(?:comprei|compramos)\s+(?:a|as|uma|umas)?\s*"
        r"passage(?:m|ns)\s+para\s+(.+?)\s+por\s+"
        r"(?:r\$\s*)?[\d.,]+",
        text,
    )
    value = money(message)
    if not match or value is None:
        return None
    destination = _clean(match.group(1))
    subject = f"Passagem para {destination}"
    event_date = resolve_date_expression(message, reference)
    actions = [
        PlannedAction(
            operation="create",
            destination="financas",
            subject=subject,
            payload=_finance_payload(
                subject,
                value,
                message,
                author,
                reference,
                category="Viagem",
            ),
            reason="registrar compra das passagens",
        ),
        PlannedAction(
            operation="update",
            destination="lugares",
            subject=destination,
            payload=PlaceAction(
                lugar=destination,
                data_planejada=event_date,
                descricao=message,
                status="Reservado",
                tipo="Viagem",
                valor_estimado=value,
            ).model_dump(mode="json"),
            reason="marcar destino da viagem como reservado",
        ),
    ]
    if event_date:
        actions.append(PlannedAction(
            operation="create",
            destination="calendario",
            subject=f"Viagem para {destination}",
            payload=CalendarAction(
                evento=f"Viagem para {destination}",
                data=event_date,
                hora=_clock(message),
                observacao=message,
                quem=_paid_by(message, author),
                status="Confirmado",
                tipo="Viagem",
            ).model_dump(mode="json"),
            reason="criar viagem no calendário",
        ))
    return ActionPlan(
        reason="compra de passagem com destino associado",
        actions=actions,
    )


def _create_action_from_clause(
    clause: str,
    author: str,
) -> PlannedAction | None:
    decision = route_message(clause)
    destination = decision.destination
    if destination == "financas":
        parsed = parse_finance(clause, author)
        subject = parsed.movimento or clause
    elif destination == "wishlist":
        parsed = parse_wishlist(clause, author)
        subject = parsed.item or clause
    elif destination == "lugares":
        parsed = parse_place(clause)
        subject = parsed.lugar or clause
    elif destination == "calendario":
        parsed = parse_calendar(clause, author)
        subject = parsed.evento or clause
    elif destination == "rotina":
        parsed = parse_routine(clause, author)
        subject = parsed.tarefa or clause
    else:
        return None
    if parsed.needs_confirmation or parsed.missing_fields:
        return None
    return PlannedAction(
        operation="create",
        destination=destination,
        subject=subject,
        payload=parsed.model_dump(mode="json"),
        reason="ação explícita em uma frase composta",
    )


def _clause_plan(message: str, author: str) -> ActionPlan | None:
    clauses = _multi_clauses(message)
    if len(clauses) < 2:
        return None
    actions = []
    for clause in clauses:
        action = _create_action_from_clause(clause, author)
        if action is None:
            return None
        actions.append(action)
    return ActionPlan(
        actions=actions,
        reason="mensagem contém múltiplas ações explícitas",
    )


def _multi_clauses(message: str) -> list[str]:
    clauses = [
        item.strip(" .,-")
        for item in re.split(
            r"\s+(?:e depois|e tambem|e)\s+|\s*;\s*",
            message,
            flags=re.I,
        )
        if item.strip(" .,-")
    ]
    dependent = re.compile(
        r"^(?:nao\b|ainda nao\b|avisar quando terminar\b|"
        r"(?:a\s+)?carol tambem vai\b|isso\b|cada acao\b|"
        r"sao registros separados\b|a primeira parte\b)",
        flags=re.I,
    )
    return [
        clause
        for index, clause in enumerate(clauses)
        if index == 0 or not dependent.search(normalize(clause))
    ]


def _looks_multi(message: str) -> bool:
    if score_message(message)["query"].value >= 15:
        return False
    clauses = _multi_clauses(message)
    if len(clauses) < 2:
        return False
    actionable = 0
    for clause in clauses:
        ranked = sorted(
            score_message(clause).values(),
            key=lambda evidence: evidence.value,
            reverse=True,
        )
        if ranked[0].value >= 7:
            actionable += 1
    return actionable >= 2


def _is_executable(plan: ActionPlan) -> bool:
    models = {
        "financas": FinanceAction,
        "wishlist": WishlistAction,
        "lugares": PlaceAction,
        "calendario": CalendarAction,
        "rotina": RoutineAction,
    }
    try:
        for action in plan.actions:
            if not action.subject.strip():
                return False
            if action.operation == "create":
                parsed = models[action.destination].model_validate(
                    action.payload
                )
                if parsed.needs_confirmation or parsed.missing_fields:
                    return False
                if isinstance(parsed, FinanceAction) and parsed.required_missing():
                    return False
                if isinstance(parsed, WishlistAction) and not parsed.item:
                    return False
                if isinstance(parsed, PlaceAction) and not parsed.lugar:
                    return False
                if isinstance(parsed, CalendarAction) and (
                    not parsed.evento or not parsed.data
                ):
                    return False
                if isinstance(parsed, RoutineAction) and not parsed.tarefa:
                    return False
            elif action.operation == "update":
                if action.destination not in {"wishlist", "lugares"}:
                    return False
            elif action.operation == "complete":
                if action.destination != "rotina":
                    return False
        return True
    except (TypeError, ValueError):
        return False


def build_action_plan(
    message: str,
    author: str = "Eu",
    reference: date | None = None,
) -> ActionPlan | None:
    reference = reference or date.today()
    if score_message(message)["query"].value >= 15:
        return None
    for builder in (_wishlist_purchase, _reservation, _ticket_purchase):
        plan = builder(message, author, reference)
        if plan:
            return plan

    clause_plan = _clause_plan(message, author)
    if clause_plan:
        return clause_plan

    if not _looks_multi(message):
        return None
    try:
        ai_plan = structured_chat(
            AIActionPlan,
            MULTI_ACTION_PROMPT,
            (
                f"Data atual: {reference.isoformat()}\n"
                f"Autor: {author}\nMensagem: {message}"
            ),
        )
    except RuntimeError:
        return None
    plan = ActionPlan(
        actions=[
            PlannedAction(
                operation=action.operation,
                destination=action.destination,
                subject=action.subject,
                payload=action.payload.model_dump(mode="json"),
                sensitive=action.sensitive,
                reason=action.reason,
            )
            for action in ai_plan.actions
        ],
        requires_confirmation=True,
        reason=ai_plan.reason,
    )
    plan.requires_confirmation = True
    for action in plan.actions:
        action.sensitive = True
    return plan if _is_executable(plan) else None
