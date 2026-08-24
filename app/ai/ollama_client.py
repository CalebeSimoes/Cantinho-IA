import time

from ollama import Client

from app.config import settings


def structured_chat(
    model_cls,
    system_prompt: str,
    user_prompt: str,
    *,
    max_attempts: int = 2,
):
    """
    Faz uma chamada estruturada ao Ollama com uma tentativa automatica
    de reparo quando a resposta vem vazia, invalida ou fora do schema.

    Importante: o reparo nunca inventa campos ausentes. Ele apenas pede
    ao modelo para responder novamente respeitando o mesmo schema.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts deve ser >= 1")

    client = Client(host=settings.ollama_host, timeout=120)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        correction = ""
        if attempt > 1:
            correction = (
                "\n\nCORRECAO AUTOMATICA:\n"
                "A resposta anterior nao respeitou o schema esperado. "
                "Tente novamente. Retorne somente dados validos para o "
                "schema, sem explicacoes extras. Nao invente informacoes "
                "que nao estejam na mensagem."
            )

        try:
            response = client.chat(
                model=settings.ollama_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": user_prompt + correction,
                    },
                ],
                format=model_cls.model_json_schema(),
                think=False,
                keep_alive="30m",
                options={
                    "temperature": 0,
                    "top_p": .2,
                    "repeat_penalty": 1.05,
                    "seed": 7,
                    "num_ctx": 4096,
                    "num_predict": 500,
                },
            )

            content = getattr(response.message, "content", None)
            if not content:
                raise RuntimeError("O Ollama respondeu sem conteudo.")

            return model_cls.model_validate_json(content)

        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                time.sleep(0.25)
                continue

    raise RuntimeError(
        "Nao foi possivel obter uma resposta estruturada valida do "
        f"Ollama apos {max_attempts} tentativa(s): {last_error}"
    ) from last_error
