from functools import lru_cache
import re
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


def request(method: str, path: str, json_body: dict | None = None) -> dict:
    with httpx.Client(timeout=30.0) as client:
        response = client.request(
            method,
            f"{BASE_URL}{path}",
            headers=headers(),
            json=json_body,
        )

    if response.is_error:
        raise RuntimeError(
            f"Notion {response.status_code}: {response.text}"
        )

    if not response.content:
        return {}
    return response.json()


def query_data_source(
    data_source_id: str,
    *,
    filter_body: dict | None = None,
    sorts: list[dict] | None = None,
    page_size: int = 50,
) -> list[dict]:
    payload: dict[str, Any] = {"page_size": page_size}
    if filter_body:
        payload["filter"] = filter_body
    if sorts:
        payload["sorts"] = sorts

    data = request(
        "POST",
        f"/data_sources/{data_source_id}/query",
        payload,
    )
    return data.get("results", [])


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


def _normalize_property_name(value: str) -> str:
    # Remove accents and formatting differences such as spaces around "/".
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*/\s*", "/", value)
    return value


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
