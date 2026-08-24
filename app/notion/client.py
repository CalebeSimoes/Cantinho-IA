from functools import lru_cache
import re
import time
import unicodedata
from typing import Any

import httpx

from app.config import settings


BASE_URL = "https://api.notion.com/v1"


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": settings.notion_api_version,
        "Content-Type": "application/json",
    }


def request(
    method: str,
    path: str,
    json_body: dict | None = None,
) -> dict:
    method = method.upper()

    # Consultas podem ser repetidas com seguranca.
    # PATCH tambem pode ser repetido porque apenas atualiza
    # as mesmas propriedades da pagina.
    # POST /pages nao tera retry para evitar duplicidades.
    retryable = (
        method in {"GET", "PATCH"}
        or path.endswith("/query")
    )

    max_attempts = 3 if retryable else 1

    timeout = httpx.Timeout(
        connect=10.0,
        read=60.0,
        write=30.0,
        pool=10.0,
    )

    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method,
                    f"{BASE_URL}{path}",
                    headers=headers(),
                    json=json_body,
                )

            if (
                retryable
                and response.status_code in {429, 500, 502, 503, 504}
                and attempt < max_attempts
            ):
                retry_after = response.headers.get("Retry-After")

                try:
                    wait_seconds = (
                        float(retry_after)
                        if retry_after
                        else 2 ** (attempt - 1)
                    )
                except ValueError:
                    wait_seconds = 2 ** (attempt - 1)

                print(
                    f"[Notion] HTTP {response.status_code}. "
                    f"Tentativa {attempt}/{max_attempts}. "
                    f"Nova tentativa em {wait_seconds}s.",
                    flush=True,
                )

                time.sleep(wait_seconds)
                continue

            if response.is_error:
                raise RuntimeError(
                    f"Notion {response.status_code}: {response.text}"
                )

            if not response.content:
                return {}

            return response.json()

        except httpx.RequestError as exc:
            if not retryable or attempt >= max_attempts:
                raise

            wait_seconds = 2 ** (attempt - 1)

            print(
                f"[Notion] {type(exc).__name__}: {exc}. "
                f"Tentativa {attempt}/{max_attempts}. "
                f"Nova tentativa em {wait_seconds}s.",
                flush=True,
            )

            time.sleep(wait_seconds)

    raise RuntimeError("Falha inesperada ao acessar o Notion.")
def query_data_source(
    data_source_id: str,
    *,
    filter_body: dict | None = None,
    sorts: list[dict] | None = None,
    page_size: int = 100,
    max_pages: int = 100,
) -> list[dict]:
    if not 1 <= page_size <= 100:
        raise ValueError("page_size deve estar entre 1 e 100.")
    if max_pages < 1:
        raise ValueError("max_pages deve ser >= 1.")

    results: list[dict] = []
    cursor: str | None = None

    for _ in range(max_pages):
        payload: dict[str, Any] = {"page_size": page_size}
        if filter_body:
            payload["filter"] = filter_body
        if sorts:
            payload["sorts"] = sorts
        if cursor:
            payload["start_cursor"] = cursor

        data = request(
            "POST",
            f"/data_sources/{data_source_id}/query",
            payload,
        )
        results.extend(data.get("results", []))

        if not data.get("has_more"):
            return results
        cursor = data.get("next_cursor")
        if not cursor:
            raise RuntimeError(
                "O Notion informou mais resultados, mas nao forneceu cursor."
            )

    raise RuntimeError(
        f"Consulta ao Notion excedeu o limite de {max_pages} paginas."
    )


def create_page(data_source_id: str, properties: dict) -> dict:
    return request(
        "POST",
        "/pages",
        {
            "parent": {
                "type": "data_source_id",
                "data_source_id": data_source_id,
            },
            "properties": properties,
        },
    )


def update_page(page_id: str, properties: dict) -> dict:
    return request(
        "PATCH",
        f"/pages/{page_id}",
        {"properties": properties},
    )


def get_data_source(data_source_id: str) -> dict:
    return request("GET", f"/data_sources/{data_source_id}")


def update_data_source(data_source_id: str, properties: dict) -> dict:
    result = request(
        "PATCH",
        f"/data_sources/{data_source_id}",
        {"properties": properties},
    )
    _property_map.cache_clear()
    return result


def title_value(prop: dict | None) -> str:
    if not prop:
        return ""
    parts = prop.get("title") or []
    return "".join(
        item.get("plain_text", "")
        for item in parts
    ).strip()


def select_value(prop: dict | None) -> str | None:
    if not prop:
        return None
    item = prop.get("select")
    return item.get("name") if item else None


def rich_text_value(prop: dict | None) -> str:
    if not prop:
        return ""
    parts = prop.get("rich_text") or []
    return "".join(
        item.get("plain_text", "")
        for item in parts
    ).strip()


def number_value(prop: dict | None) -> float | None:
    if not prop:
        return None
    value = prop.get("number")
    return float(value) if value is not None else None


def date_value(prop: dict | None) -> str | None:
    if not prop:
        return None
    value = prop.get("date")
    return value.get("start") if value else None


def url_value(prop: dict | None) -> str | None:
    return prop.get("url") if prop else None


def _normalize_property_name(value: str) -> str:
    # Remove accents and formatting differences such as spaces around "/".
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*/\s*", "/", value)
    return value


def property_value(properties: dict, logical_name: str) -> dict | None:
    """Encontra uma propriedade recebida sem depender de acentos."""
    wanted = _normalize_property_name(logical_name)
    for real_name, value in properties.items():
        if _normalize_property_name(real_name) == wanted:
            return value
    return None


@lru_cache(maxsize=32)
def _property_map(data_source_id: str) -> dict[str, str]:
    data = get_data_source(data_source_id)
    properties = data.get("properties", {})

    if not properties:
        raise RuntimeError(
            "O Notion nao retornou o schema de propriedades para "
            f"{data_source_id}."
        )

    return {
        _normalize_property_name(real_name): real_name
        for real_name in properties.keys()
    }


def property_name(data_source_id: str, logical_name: str) -> str:
    """
    Resolve um nome logico ASCII para o nome REAL da coluna no Notion.

    Exemplo:
      logical_name = "Lugar / Experiencia"
      real_name    = "Lugar / Experiencia" com o acento correto no Notion.

    Isso evita bugs de encoding no Windows e diferencas de espacos.
    """
    normalized = _normalize_property_name(logical_name)
    mapping = _property_map(data_source_id)

    if normalized not in mapping:
        available = ", ".join(sorted(mapping.values()))
        raise RuntimeError(
            f'Propriedade "{logical_name}" nao encontrada no Notion. '
            f"Disponiveis: {available}"
        )

    return mapping[normalized]


def optional_property_name(
    data_source_id: str,
    logical_name: str,
) -> str | None:
    """Resolve uma coluna opcional sem quebrar bases ainda não migradas."""
    return _property_map(data_source_id).get(
        _normalize_property_name(logical_name)
    )
