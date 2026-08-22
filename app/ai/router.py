import re
import unicodedata

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


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).strip().lower()


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

    t = normalize(message)

    def has_any(values):
        return any(value in t for value in values)

    if (
        has_any([
            "paguei", "pagamos", "gastei", "gastamos",
            "comprei", "compramos", "recebi",
            "salario", "reembolso",
        ])
        and re.search(r"\d", t)
    ):
        return RouterDecision(
            destination="financas",
            confidence=.99,
            reason="movimentacao explicita",
        )

    if has_any([
        "quero comprar", "queremos comprar",
        "queria comprar", "gostaria de comprar",
        "quero ganhar", "wishlist",
    ]):
        return RouterDecision(
            destination="wishlist",
            confidence=.99,
            reason="desejo de compra",
        )

    if has_any([
        "todo dia", "todos os dias", "toda semana",
        "semanalmente", "todo mes", "rotina",
        "tarefa", "temos que", "lavar roupa",
        "arrumar a casa",
    ]):
        return RouterDecision(
            destination="rotina",
            confidence=.96,
            reason="tarefa/recorrencia",
        )

    # Expressões que antes caiam no Qwen agora sao deterministicas.
    if has_any([
        "quero conhecer", "queremos conhecer",
        "quero visitar", "queremos visitar",
        "vamos conhecer", "gostaria de conhecer",
        "quero ir", "queremos ir",
        "viajar para", "viagem para",
        "passeio", "hotel", "restaurante para",
    ]):
        return RouterDecision(
            destination="lugares",
            confidence=.98,
            reason="lugar/experiencia",
        )

    if has_any([
        "agendar", "marcar", "compromisso",
        "consulta", "aniversario",
        "reuniao", "evento", " as ",
    ]):
        return RouterDecision(
            destination="calendario",
            confidence=.90,
            reason="evento/compromisso",
        )

    return structured_chat(
        RouterDecision,
        ROUTER_PROMPT,
        f"Mensagem:\n{message}",
    )
