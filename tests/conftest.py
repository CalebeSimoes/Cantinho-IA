import os
import sys
import types


# Os testes nao devem depender do .env real nem acessar Notion/Ollama.
os.environ.setdefault("NOTION_TOKEN", "test-token")
os.environ.setdefault("NOTION_INBOX_DATA_SOURCE_ID", "test-inbox")
os.environ.setdefault("NOTION_FINANCES_DATA_SOURCE_ID", "test-finances")
os.environ.setdefault("NOTION_WISHLIST_DATA_SOURCE_ID", "test-wishlist")
os.environ.setdefault("NOTION_PLACES_DATA_SOURCE_ID", "test-places")
os.environ.setdefault("NOTION_CALENDAR_DATA_SOURCE_ID", "test-calendar")
os.environ.setdefault("NOTION_ROUTINE_DATA_SOURCE_ID", "test-routine")
os.environ.setdefault("OLLAMA_MODEL", "qwen3:4b")
os.environ.setdefault("APP_TIMEZONE", "America/Sao_Paulo")


# Permite rodar a suite em ambientes de CI que nao tenham o pacote ollama.
# No PC do Cantinho, o pacote real continua sendo usado normalmente.
try:
    import ollama  # noqa: F401
except ImportError:
    fake = types.ModuleType("ollama")

    class Client:  # pragma: no cover - apenas fallback de importacao
        def __init__(self, *args, **kwargs):
            pass

        def chat(self, *args, **kwargs):
            raise RuntimeError("Ollama real nao disponivel neste ambiente")

    fake.Client = Client
    sys.modules["ollama"] = fake
