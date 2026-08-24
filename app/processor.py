import re

from app import action_store
from app.action_executor import execute_plan
from app.ai.action_planner import build_action_plan
from app.ai.router import route_message
from app.ai.query_parser import parse_query
from app.ai.parsers import (
    parse_finance,
    parse_wishlist,
    parse_place,
    parse_calendar,
    parse_routine,
)
from app.notion.writers import (
    write_finance,
    write_wishlist,
    write_place,
    write_calendar,
    write_routine,
)
from app.schemas.actions import ActionPlan, ProcessResult
from app.query_service import execute_query
from app.routine_service import (
    complete_routine,
    is_completion_command,
)


MIN_AUTO_ROUTE_CONFIDENCE = 0.55


def _unique_missing(values):
    return sorted({value for value in values if value})


def confirm(dest, parsed, missing):
    missing = _unique_missing(missing)
    txt = ", ".join(missing) if missing else "informacoes adicionais"
    return ProcessResult(
        success=False,
        destination=dest,
        status="Precisa confirmação",
        summary=f"Preciso de mais informação: {txt}.",
        parsed_data=parsed.model_dump(mode="json"),
    )


def _is_plan_confirmation(message: str) -> bool:
    return bool(re.search(
        r"\b(?:confirmar|confirmado|pode executar|pode fazer|sim pode)\b",
        message,
        flags=re.I,
    ))


def _is_plan_cancel(message: str) -> bool:
    return bool(re.fullmatch(
        r"\s*(?:cancelar|cancela|não confirmar|nao confirmar)\s*[.!]?\s*",
        message,
        flags=re.I,
    ))


def _plan_preview(plan: ActionPlan) -> str:
    icons = {
        "financas": "💸",
        "wishlist": "🛍️",
        "lugares": "📍",
        "calendario": "🗓️",
        "rotina": "🌙",
    }
    names = {
        "financas": "Finanças",
        "wishlist": "Wishlist",
        "lugares": "Lugares",
        "calendario": "Calendário",
        "rotina": "Rotina",
    }
    verbs = {
        "create": "criar",
        "update": "atualizar",
        "complete": "concluir",
    }
    lines = ["Vou executar este plano:"]
    for index, action in enumerate(plan.actions, 1):
        lines.append(
            f"{index}. {icons[action.destination]} "
            f"{verbs[action.operation]} {names[action.destination]}: "
            f"{action.subject}"
        )
    lines.extend([
        "",
        "Confirmar? Acrescente “confirmar” à Mensagem e mude o Status para Novo.",
        "Para desistir, escreva somente “cancelar” e mude o Status para Novo.",
    ])
    return "\n".join(lines)


def process_message(
    message,
    requested_destination="Automático",
    author="Eu",
    idempotency_key=None,
):
    if idempotency_key:
        completed = action_store.get_completed(idempotency_key)
        if completed:
            return ProcessResult(
                success=True,
                destination="multi",
                status="Processado",
                summary=completed,
                parsed_data={"idempotent_replay": True},
            )

        pending = action_store.get_pending(idempotency_key)
        if pending:
            plan = ActionPlan.model_validate(pending["plan"])
            if _is_plan_cancel(message):
                action_store.discard_pending(idempotency_key)
                return ProcessResult(
                    success=True,
                    destination="multi",
                    status="Processado",
                    summary="Plano cancelado. Nenhuma alteração foi feita.",
                    parsed_data=plan.model_dump(mode="json"),
                )
            if _is_plan_confirmation(message):
                execution = execute_plan(
                    plan,
                    idempotency_key,
                    pending.get("done_action_ids", []),
                )
                return ProcessResult(
                    success=True,
                    destination="multi",
                    status="Processado",
                    summary=execution.summary,
                    created_url=execution.first_url,
                    parsed_data=plan.model_dump(mode="json"),
                )
            if message.strip() == pending.get("message", "").strip():
                return ProcessResult(
                    success=False,
                    destination="multi",
                    status="Precisa confirmação",
                    summary=_plan_preview(plan),
                    parsed_data=plan.model_dump(mode="json"),
                )
            action_store.discard_pending(idempotency_key)

    if is_completion_command(message):
        completion = complete_routine(message, author)
        return ProcessResult(
            success=completion.success,
            destination="rotina",
            status=(
                "Processado"
                if completion.success
                else "Precisa confirmação"
            ),
            summary=completion.summary,
            parsed_data={
                "command": "complete",
                "matched_page_id": (
                    completion.record.page_id
                    if completion.record else None
                ),
                "next_date": (
                    completion.next_date.isoformat()
                    if completion.next_date else None
                ),
            },
        )

    if requested_destination == "Automático":
        plan = build_action_plan(message, author)
        if plan:
            if idempotency_key:
                action_store.assign_action_ids(plan, idempotency_key)
                action_store.save_pending(
                    idempotency_key,
                    message,
                    plan,
                )
            return ProcessResult(
                success=False,
                destination="multi",
                status="Precisa confirmação",
                summary=_plan_preview(plan),
                parsed_data=plan.model_dump(mode="json"),
            )

    d = route_message(message, requested_destination)
    dest = d.destination

    if dest == "desconhecido":
        return ProcessResult(
            success=False,
            destination=dest,
            status="Precisa confirmação",
            summary=(
                "Não consegui decidir para qual área essa anotação "
                "deve ir."
            ),
            parsed_data={"router": d.model_dump()},
        )

    # Destinos escolhidos manualmente chegam com confidence=1.
    # Em roteamento automatico, uma classificacao muito incerta nao deve
    # gerar escrita no Notion.
    if (
        requested_destination == "Automático"
        and d.confidence < MIN_AUTO_ROUTE_CONFIDENCE
    ):
        return ProcessResult(
            success=False,
            destination=dest,
            status="Precisa confirmação",
            summary=(
                "A IA identificou um possível destino, mas com baixa "
                "confiança. Escolha o destino ou reformule a mensagem."
            ),
            parsed_data={"router": d.model_dump()},
        )

    if dest == "query":
        a = parse_query(message)
        missing = _unique_missing(a.missing_fields)
        if a.needs_confirmation or a.domain == "desconhecido" or missing:
            if a.domain == "desconhecido" and "domain" not in missing:
                missing.append("domain")
            return confirm(dest, a, missing)
        summary = execute_query(a)
        return ProcessResult(
            success=True,
            destination=dest,
            status="Processado",
            summary=summary,
            parsed_data=a.model_dump(mode="json"),
        )

    if dest == "financas":
        a = parse_finance(message, author)
        missing = _unique_missing(
            a.missing_fields + a.required_missing()
        )
        if a.needs_confirmation or missing:
            return confirm(dest, a, missing)
        p = write_finance(a)
        summary = (
            f"💸 Registrado em Finanças: {a.movimento} · "
            f"R$ {a.valor:.2f}"
        )

    elif dest == "wishlist":
        a = parse_wishlist(message, author)
        missing = _unique_missing(
            a.missing_fields + ([] if a.item else ["item"])
        )
        if a.needs_confirmation or missing:
            return confirm(dest, a, missing)
        p = write_wishlist(a)
        summary = f"🛍️ Adicionado à Wishlist: {a.item}"
        if a.preco_estimado is not None:
            price_prefix = "até " if a.preco_relacao == "Máximo" else ""
            summary += f" · {price_prefix}R$ {a.preco_estimado:.2f}"
        if a.data_desejada:
            summary += f" · até {a.data_desejada.isoformat()}"

    elif dest == "lugares":
        a = parse_place(message)
        missing = _unique_missing(
            a.missing_fields + ([] if a.lugar else ["lugar"])
        )
        if a.needs_confirmation or missing:
            return confirm(dest, a, missing)
        p = write_place(a)
        summary = (
            f"📍 Adicionado a Lugares & Experiências: {a.lugar}"
        )

    elif dest == "calendario":
        a = parse_calendar(message, author)
        missing = _unique_missing(
            a.missing_fields
            + ([] if a.evento else ["evento"])
            + ([] if a.data else ["data"])
        )
        if a.needs_confirmation or missing:
            return confirm(dest, a, missing)
        p = write_calendar(a)
        summary = (
            f"🗓️ Adicionado ao Calendário: {a.evento} · "
            f"{a.data.isoformat()}"
        )

    elif dest == "rotina":
        a = parse_routine(message, author)
        missing = _unique_missing(
            a.missing_fields + ([] if a.tarefa else ["tarefa"])
        )
        if a.needs_confirmation or missing:
            return confirm(dest, a, missing)
        p = write_routine(a)
        summary = f"🌙 Adicionado à Rotina: {a.tarefa}"
        notification = p.get("_cantinho_notification", {})
        if notification.get("sent"):
            summary += " · 🔔 responsável avisado"
        elif notification.get("mode") == "failed":
            summary += " · ⚠️ aviso mobile não enviado"

    else:
        raise RuntimeError(f"Destino não suportado: {dest}")

    return ProcessResult(
        success=True,
        destination=dest,
        status="Processado",
        summary=summary,
        created_page_id=p.get("id"),
        created_url=p.get("url"),
        parsed_data=a.model_dump(mode="json"),
    )
