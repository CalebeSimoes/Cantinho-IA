from ollama import Client
from app.config import settings

def structured_chat(model_cls, system_prompt: str, user_prompt: str):
    client=Client(host=settings.ollama_host, timeout=120)
    response=client.chat(model=settings.ollama_model,messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],format=model_cls.model_json_schema(),think=False,keep_alive="30m",options={"temperature":0,"num_ctx":2048,"num_predict":350})
    if not response.message.content:
        raise RuntimeError("O Ollama respondeu sem conteúdo.")
    return model_cls.model_validate_json(response.message.content)
