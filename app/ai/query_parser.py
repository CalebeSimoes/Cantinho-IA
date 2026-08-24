import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.ai.date_utils import (
    contains_temporal_expression,
    resolve_date_expression,
)
from app.ai.ollama_client import structured_chat
from app.ai.prompts import QUERY_PROMPT
from app.ai.router import normalize
from app.config import settings
from app.schemas.actions import QueryIntent


DOMAIN_PATTERNS = {
    "financas": (
        r"\b(?:financas?|financeir[oa]s?|gastos?|gastei|gastamos|"
        r"pagou|paguei|pagamos|despesas?|recebi|recebemos|salario|"
        r"saldo|entradas?|saidas?|uber|99|ifood|mercado|orcamento|"
        r"dinheiro|bolso|custou|custaram)\b",
        5,
    ),
    "wishlist": (
        r"\b(?:wishlist|lista de desejos|desejos?|item|itens|"
        r"compramos|comprado|comprar|preco estimado|sonhando|sonhos?)\b",
        5,
    ),
    "lugares": (
        r"\b(?:lugares?|destinos?|experiencias?|conhecer|visitar|"
        r"passeios?|restaurantes?|hoteis?|museus?|viagens?)\b",
        5,
    ),
    "calendario": (
        r"\b(?:calendario|agenda|marcado|marcados|compromissos?|"
        r"eventos?|reservas?|consulta|reuniao|cinema|sabado|domingo)\b",
        5,
    ),
    "rotina": (
        r"\b(?:rotinas?|tarefas?|pendencias?|pendentes?|afazeres|a fazer|"
        r"responsavel|sem terminar|concluid[oa]s?|vencendo|"
        r"atrasad[oa]s?|prazos?|tenho para fazer|tem para fazer|"
        r"afazeres|lavar|limpar|arrumar)\b",
        5,
    ),
}


def _local_today() -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def _detect_domain(text: str) -> str:
    scores = {name: 0 for name in DOMAIN_PATTERNS}
    for domain, (pattern, points) in DOMAIN_PATTERNS.items():
        scores[domain] += len(re.findall(pattern, text)) * points

    explicit = {
        "financas": r"\b(?:financas?|saldo|gastos?)\b",
        "wishlist": r"\b(?:wishlist|lista de desejos)\b",
        "lugares": r"\b(?:lugares|destinos|experiencias)\b",
        "calendario": r"\b(?:calendario|agenda|marcado)\b",
        "rotina": r"\b(?:rotina|tarefas|pendencias)\b",
    }
    for domain, pattern in explicit.items():
        if re.search(pattern, text):
            scores[domain] += 8

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] == 0:
        return "desconhecido"
    return ranked[0][0]


def _detect_operation(text: str, domain: str) -> str:
    if re.search(
        r"\b(?:mais car[oa]|maior (?:gasto|valor|preco)|"
        r"pesa mais no bolso|(?:preco|valor) mais alto)\b",
        text,
    ):
        return "max"
    if re.search(r"\bquant[oa]s\b", text):
        return "count"
    if re.search(r"\b(?:resumo|resumir|saldo|balanco)\b", text):
        return "summary"
    if domain == "financas" and re.search(
        r"\b(?:quanto|total|soma|somamos)\b", text
    ):
        return "total"
    if domain != "financas" and re.search(r"\bquanto(?:s|as)?\b", text):
        return "count"
    return "list"


def _detect_period(text: str, reference: date) -> tuple[str, date | None]:
    if re.search(r"\b(?:mes passado|ultimo mes)\b", text):
        return "last_month", None
    if re.search(r"\b(?:proximo mes|mes que vem)\b", text):
        return "next_month", None
    if re.search(
        r"\b(?:este mes|esse mes|deste mes|desse mes|nesse mes|neste mes|mes atual|"
        r"fim (?:do|deste|desse) mes)\b",
        text,
    ):
        return "this_month", None
    if re.search(r"\b(?:esta semana|nessa semana|nesta semana)\b", text):
        return "this_week", None
    if re.search(r"\bhoje\b", text):
        return "today", None
    if contains_temporal_expression(text):
        resolved = resolve_date_expression(text, reference)
        if resolved:
            return "specific_date", resolved
    return "all", None


def _detect_person(text: str) -> str | None:
    partner = normalize(settings.partner_name)
    user = normalize(settings.user_name)
    if re.search(
        rf"\b(?:{re.escape(partner)}|minha esposa|dela)\b",
        text,
    ):
        return "Minha esposa"
    if re.search(r"\b(?:nos dois|juntos)\b", text):
        return "Nós dois"
    if re.search(
        rf"\b(?:{re.escape(user)}|caleb|eu|meu|minha|minhas|tenho)\b",
        text,
    ):
        return "Eu"
    return None


def _detect_status(text: str, domain: str) -> str | None:
    if domain == "wishlist":
        if re.search(r"\b(?:sem incluir.*compr|ainda queremos|nao comprad)\w*", text):
            return "Ativos"
        for status, pattern in {
            "Quero": r"\bquero\b",
            "Planejando": r"\bplanejando\b",
            "Comprado": r"\bcomprad[oa]s?\b",
            "Desistimos": r"\bdesist",
        }.items():
            if re.search(pattern, text):
                return status
    if domain == "lugares":
        for status, pattern in {
            "Ideia": r"\b(?:so|apenas) ideia\b",
            "Planejando": r"\bplanejando\b",
            "Reservado": r"\breservad[oa]s?\b",
            "Feito": r"\b(?:feito|fomos|conhecemos)\b",
        }.items():
            if re.search(pattern, text):
                return status
        if re.search(r"\b(?:ainda queremos|queremos conhecer|nao fomos)\b", text):
            return "Ativos"
    if domain == "rotina" and re.search(
        r"\b(?:atrasad[oa]s?|vencid[oa]s?|fora do prazo)\b", text
    ):
        return "Atrasadas"
    if domain == "rotina" and re.search(
        r"\b(?:pendentes?|a fazer|sem terminar|nao concluid)\w*", text
    ):
        return "Pendentes"
    if domain == "rotina" and re.search(
        r"\b(?:tenho|temos|tem) para fazer\b", text
    ):
        return "Pendentes"
    if domain == "calendario" and re.search(
        r"\b(?:marcad[oa]s?|planejad[oa]s?|confirmad[oa]s?)\b", text
    ):
        return "Ativos"
    if domain == "financas" and re.search(r"\bpendentes?\b", text):
        return "Pendente"
    return None


def _detect_transaction_type(text: str, domain: str) -> str | None:
    if domain != "financas":
        return None
    if re.search(
        r"\b(?:recebi|recebemos|ganhei|ganhamos|salario|renda|entrad[oa]s?)\b",
        text,
    ):
        return "Entrada"
    if re.search(
        r"\b(?:gastei|gastamos|gasto|gastos|pagou|paguei|pagamos|"
        r"despesa|despesas|saida|saidas)\b",
        text,
    ):
        return "Saída"
    return None


def _detect_category(text: str, domain: str) -> str | None:
    if domain != "rotina":
        return None
    categories = {
        "Casa": r"\b(?:casa|domesticas?|banheiro|cozinha|louca|faxina)\b",
        "Saúde": r"\b(?:saude|remedio|academia|terapia)\b",
        "Estudo": r"\b(?:estudo|faculdade|curso|prova)\b",
        "Trabalho": r"\b(?:trabalho|cliente|projeto|relatorio)\b",
        "Relacionamento": r"\b(?:relacionamento|casal)\b",
    }
    for category, pattern in categories.items():
        if re.search(pattern, text):
            return category
    return None


def _detect_term(text: str, domain: str) -> str | None:
    if domain != "financas":
        return None

    known_terms = {
        "Uber": r"\buber\b",
        "99": r"\b99\b",
        "iFood": r"\bifood\b",
        "Transporte": r"\btransporte\b",
        "Alimentação": r"\balimentacao\b",
        "Moradia": r"\bmoradia\b",
        "Lazer": r"\blazer\b",
        "Compras": r"\bcompras\b",
        "Saúde": r"\bsaude\b",
        "Viagem": r"\bviagem\b",
        "Mercado": r"\bmercado\b",
    }
    for label, pattern in known_terms.items():
        if re.search(pattern, text):
            return label

    match = re.search(
        r"\bcom\s+([a-z0-9][a-z0-9 -]{1,40}?)(?=\s+(?:este|neste|"
        r"nesse|no|na|do|da|mes|semana|pago|pagou)|[?.!,]|$)",
        text,
    )
    if match:
        candidate = match.group(1).strip()
        if candidate not in {"a carol", "meu marido", "minha esposa"}:
            return candidate.title()
    return None


def parse_query(message: str, reference: date | None = None) -> QueryIntent:
    reference = reference or _local_today()
    text = normalize(message)
    domain = _detect_domain(text)

    if domain == "desconhecido":
        parsed = structured_chat(
            QueryIntent,
            QUERY_PROMPT,
            (
                f"Data atual: {reference.isoformat()}\n"
                f"Usuario: {settings.user_name}\n"
                f"Parceira: {settings.partner_name}\n"
                f"Pergunta: {message}"
            ),
        )
        if parsed.domain == "desconhecido":
            parsed.needs_confirmation = True
            parsed.missing_fields = sorted(
                set(parsed.missing_fields + ["domain"])
            )
            return parsed

        # O modelo decide a ambiguidade sem ganhar liberdade para carregar
        # campos incompatíveis de outro domínio. Sinais objetivos continuam
        # sob responsabilidade do Python.
        local_operation = _detect_operation(text, parsed.domain)
        if local_operation != "list":
            parsed.operation = local_operation
        local_period, local_date = _detect_period(text, reference)
        if local_period != "all":
            parsed.period = local_period
            parsed.specific_date = local_date
        parsed.person = _detect_person(text)
        parsed.status = _detect_status(text, parsed.domain) or parsed.status
        parsed.category = (
            _detect_category(text, parsed.domain) or parsed.category
        )
        if parsed.domain == "financas":
            parsed.transaction_type = _detect_transaction_type(
                text, parsed.domain
            )
            parsed.term = _detect_term(text, parsed.domain)
        else:
            parsed.transaction_type = None
            parsed.term = None
        return parsed

    period, specific_date = _detect_period(text, reference)
    return QueryIntent(
        domain=domain,
        operation=_detect_operation(text, domain),
        period=period,
        specific_date=specific_date,
        person=_detect_person(text),
        term=_detect_term(text, domain),
        status=_detect_status(text, domain),
        category=_detect_category(text, domain),
        transaction_type=_detect_transaction_type(text, domain),
        reason="consulta interpretada pelo classificador contextual Python",
    )
