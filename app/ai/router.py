import re
import unicodedata
from dataclasses import dataclass, field

from app.ai.date_utils import contains_temporal_expression
from app.ai.ollama_client import structured_chat
from app.ai.prompts import ROUTER_PROMPT
from app.schemas.actions import RouterDecision


EXPLICIT = {
    "Finanças": "financas",
    "Wishlist": "wishlist",
    "Lugares": "lugares",
    "Calendário": "calendario",
    "Rotina": "rotina",
}

DESTINATIONS = (
    "query",
    "financas",
    "wishlist",
    "lugares",
    "calendario",
    "rotina",
)


@dataclass
class IntentScore:
    value: int = 0
    reasons: list[str] = field(default_factory=list)

    def add(self, points: int, reason: str):
        self.value += points
        self.reasons.append(reason)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).strip().lower()


def _matches(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, flags=re.I))


def _looks_like_clock_time(text: str) -> bool:
    return _matches(
        text,
        r"\bas\s+\d{1,2}(?:(?::|h)\d{0,2})?\b",
    )


def score_message(message: str) -> dict[str, IntentScore]:
    t = normalize(message)
    scores = {name: IntentScore() for name in DESTINATIONS}

    task_frame = _matches(
        t,
        r"\b(?:preciso|precisa|precisamos|tenho que|tem que|temos que|devo|deve|devemos|nao esquecer(?: de)?|lembrar de|fica responsavel por)\b",
    )
    recurrence = _matches(
        t,
        r"\b(?:todo dia|todos os dias|diariamente|toda semana|semanalmente|"
        r"todo mes|mensalmente|a cada semana|a cada mes|uma vez por mes|"
        r"quinzenalmente|quinzenal|a cada 15 dias|dias uteis|"
        r"todo fim de semana|nos fins de semana|"
        r"tod[oa]s? (?:primeir[oa] |segund[oa] |terceir[oa] |ultim[oa] )?"
        r"(?:segunda|terca|quarta|quinta|sexta|sabado|domingo))\b",
    )
    temporal = contains_temporal_expression(t) or _looks_like_clock_time(t)
    bare_action = _matches(
        t,
        r"^(?:assinar|renovar|cancelar|limpar|lavar|arrumar|organizar|resolver|ligar|enviar|buscar|levar|estudar|treinar|instalar|consertar|preparar|pagar|comprar|separar|conferir|revisar|atualizar|responder|devolver|retirar|guardar|cozinhar|fazer)\b",
    )

    direct_interrogative = _matches(
        t,
        r"^(?:quanto(?:s|as)?|qual|quais|o que|do que|quando|onde|"
        r"tem(?:os)? (?:algo|algum|alguma))\b",
    )
    embedded_interrogative = "?" in message and _matches(
        t,
        r"\b(?:quanto(?:s|as)?|qual|quais|o que|do que|quando|onde|"
        r"tem(?:os)? (?:algo|algum|alguma)|ha (?:algo|algum|alguma)|"
        r"esta livre|ficou livre)\b",
    )
    explicit_information_request = _matches(
        t,
        r"\b(?:me diga|me mostre|mostre|liste|quero saber|queria saber|"
        r"consegue me dizer)\b",
    )
    information_request = (
        direct_interrogative
        or embedded_interrogative
        or explicit_information_request
    )
    question_about_records = _matches(
        t,
        r"\b(?:gastei|gastamos|pagou|pagamos|recebi|recebemos|"
        r"marcado|agenda|compromissos?|eventos?|wishlist|desejos?|"
        r"lugares?|tarefas?|rotinas?|pendencias?|vencendo|atrasad[oa]s?)\b",
    )
    if information_request:
        scores["query"].add(15, "pedido de consulta ou calculo")
    if question_about_records and (
        "?" in message or information_request
    ):
        scores["query"].add(5, "pergunta sobre dados registrados")

    if _matches(
        t,
        r"\b(?:paguei|pagou|pagamos|gastei|gastou|gastamos|"
        r"comprei|comprou|compramos|assinei|assinou|assinamos|"
        r"recebi|recebeu|recebemos|ganhei|ganhou|ganhamos|"
        r"transferi|transferiu|transferimos|depositei|depositou|depositamos)\b",
    ):
        scores["financas"].add(
            12,
            "movimentacao financeira ja realizada",
        )
    if _matches(t, r"(?:r\$|\breais?\b|\bcontos?\b)"):
        scores["financas"].add(2, "valor monetario")
    if _matches(
        t,
        r"\b(?:salario|reembolso|pix|boleto|fatura|aluguel|conta de luz)\b",
    ):
        scores["financas"].add(2, "termo financeiro")

    if _matches(
        t,
        r"\b(?:quero|queremos|queria|queriamos|gostaria|gostariamos|sonho em)\s+(?:de\s+)?(?:muito\s+)?(?:comprar|ter|ganhar|assinar)\b",
    ):
        scores["wishlist"].add(12, "desejo de aquisicao futura")
    if _matches(
        t,
        r"\b(?:pensando|planejando|cogitando) em (?:comprar|ter|adquirir)\b",
    ):
        scores["wishlist"].add(11, "aquisicao futura em consideracao")
    if _matches(t, r"\b(?:wishlist|lista de desejos|coloca na lista)\b"):
        scores["wishlist"].add(10, "lista de desejos explicita")

    place_desire = _matches(
        t,
        r"\b(?:quero|queremos|queria|gostaria|vamos|pretendo|pretendemos|"
        r"planejo|planejamos)\s+(?:de\s+)?(?:muito\s+)?"
        r"(?:conhecer|visitar|ir(?: ao| a| no| na| para)?)\b",
    )
    if place_desire:
        scores["lugares"].add(11, "desejo de conhecer ou visitar")
    if _matches(
        t,
        r"^(?:visitar|conhecer|ir(?: ao| a| no| na| para))\b",
    ) and not task_frame:
        scores["lugares"].add(9, "lugar ou experiência em formato direto")
    if _matches(
        t,
        r"\b(?:museu|parque|restaurante|hotel|pousada|praia|cidade|destino|passeio|experiencia)\b",
    ):
        scores["lugares"].add(2, "lugar ou experiencia")

    schedule = _matches(
        t,
        r"\b(?:agendar|agendei|agendamos|marcar|marquei|marcamos|"
        r"reservar|reservei|reservamos)\b",
    )
    event = _matches(
        t,
        r"\b(?:consulta|reuniao|aniversario|evento|compromisso|jantar|almoco|cinema|show|cerimonia|festa|entrevista|viagem|dentista|medico)\b",
    )
    if schedule:
        scores["calendario"].add(9, "acao de agendamento")
    if event:
        scores["calendario"].add(4, "evento ou compromisso")
    if event and temporal:
        scores["calendario"].add(7, "evento com data ou horario")
    elif schedule and temporal:
        scores["calendario"].add(4, "agendamento com data ou horario")
    if temporal and _matches(
        t,
        r"^(?:ir|vou)\s+(?:ao|a|no|na)\s+(?:dentista|medico|consulta)\b",
    ):
        scores["calendario"].add(
            6,
            "deslocamento para compromisso datado",
        )

    if task_frame:
        scores["rotina"].add(11, "obrigacao ou tarefa explicita")
    if recurrence:
        scores["rotina"].add(12, "recorrencia explicita")
    if _matches(
        t,
        r"\b(?:limpar|lavar|arrumar|organizar|resolver|ligar|enviar|buscar|levar|estudar|treinar|renovar|cancelar|assinar|instalar|consertar|preparar|pagar|comprar|separar|conferir|revisar|atualizar|responder|devolver|retirar|guardar|cozinhar|fazer|visitar|ir)\b",
    ):
        scores["rotina"].add(4, "verbo de acao executavel")
    if bare_action:
        scores["rotina"].add(8, "acao direta em formato de lembrete")
    if _matches(t, r"\b(?:tarefa|rotina|pendencia|lembrete)\b"):
        scores["rotina"].add(8, "tarefa declarada")
    if task_frame and temporal:
        scores["rotina"].add(4, "tarefa com prazo")
    if _matches(t, r"\b(?:vence|vencimento)\b") and temporal:
        scores["rotina"].add(8, "obrigacao com vencimento")

    # Uma data define o prazo da tarefa, mas nao a transforma em evento.
    if task_frame and not schedule:
        scores["calendario"].value = max(
            0,
            scores["calendario"].value - 3,
        )
        if scores["calendario"].reasons:
            scores["calendario"].reasons.append(
                "penalizado por linguagem de tarefa"
            )

    # Uma experiencia datada, como cinema no sabado, vira plano de agenda.
    if place_desire and event and temporal:
        scores["calendario"].add(
            5,
            "experiencia transformada em plano datado",
        )

    return scores


def _ranked_scores(
    scores: dict[str, IntentScore],
) -> list[tuple[str, IntentScore]]:
    return sorted(
        scores.items(),
        key=lambda item: item[1].value,
        reverse=True,
    )


def _rule_decision(message: str) -> RouterDecision | None:
    ranked = _ranked_scores(score_message(message))
    destination, top = ranked[0]
    second = ranked[1][1].value
    margin = top.value - second

    if top.value >= 14 and margin >= 4:
        confidence = .99
    elif top.value >= 10 and margin >= 3:
        confidence = .96
    elif top.value >= 7 and margin >= 3:
        confidence = .90
    else:
        return None

    return RouterDecision(
        destination=destination,
        confidence=confidence,
        reason="; ".join(top.reasons),
    )


def _evidence_for_model(message: str) -> str:
    ranked = _ranked_scores(score_message(message))
    lines = []
    for destination, evidence in ranked:
        if evidence.value:
            reasons = ", ".join(evidence.reasons)
            lines.append(
                f"- {destination}: {evidence.value} ponto(s) ({reasons})"
            )
    return "\n".join(lines) or "- nenhum sinal deterministico forte"


def route_message(
    message: str,
    requested_destination: str = "Automático",
) -> RouterDecision:
    if requested_destination in EXPLICIT:
        return RouterDecision(
            destination=EXPLICIT[requested_destination],
            confidence=1,
            reason="Destino escolhido no formulario",
        )

    rule_decision = _rule_decision(message)
    if rule_decision is not None:
        return rule_decision

    scores = score_message(message)
    ranked = _ranked_scores(scores)
    ai_decision = structured_chat(
        RouterDecision,
        ROUTER_PROMPT,
        (
            f"Mensagem:\n{message}\n\n"
            "Evidencias calculadas pelo Python (sao auxiliares, nao uma "
            f"ordem):\n{_evidence_for_model(message)}"
        ),
    )

    top_destination, top = ranked[0]
    second = ranked[1][1].value
    if (
        ai_decision.destination == top_destination
        and top.value >= 4
        and top.value - second >= 2
    ):
        ai_decision.confidence = max(ai_decision.confidence, .72)
        ai_decision.reason = (
            f"{ai_decision.reason}; corroborado pelo classificador Python"
        ).strip("; ")

    return ai_decision
