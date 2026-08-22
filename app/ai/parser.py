from datetime import datetime
from zoneinfo import ZoneInfo

from ollama import Client

from app.ai.prompts import SYSTEM_PROMPT
from app.config import settings
from app.schemas.actions import FinanceAction


def _client() -> Client:
    return Client(host=settings.ollama_host)


def parse_finance_message(message: str) -> FinanceAction:
    now = datetime.now(ZoneInfo(settings.app_timezone))

    system_prompt = SYSTEM_PROMPT.format(partner_name=settings.partner_name)

    user_prompt = (
        f"Data atual: {now.date().isoformat()}\n"
        f"Fuso horário: {settings.app_timezone}\n"
        f"Nome da parceira: {settings.partner_name}\n\n"
        f"Mensagem do usuário:\n{message}"
    )

    response = _client().chat(
        model=settings.ollama_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        format=FinanceAction.model_json_schema(),
        options={"temperature": 0},
    )

    content = response.message.content
    if not content:
        raise RuntimeError("O Ollama respondeu sem conteúdo.")

    return FinanceAction.model_validate_json(content)
