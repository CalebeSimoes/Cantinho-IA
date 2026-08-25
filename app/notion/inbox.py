from dataclasses import dataclass
from datetime import datetime
import time
from zoneinfo import ZoneInfo

from app.config import settings
from app.notion.client import (
    query_data_source,
    select_value,
    title_value,
    update_page,
)
from app.notion.users import author_from_creator_id


RESULT_LINK_LABEL = "Abrir registro \u2197"

@dataclass
class InboxItem:
    page_id: str
    message: str
    destination: str
    author: str
    creator_user_id: str | None = None
    author_inferred: bool = False
    last_edited_time: str | None = None


_stability_cache: dict[str, tuple[str, float]] = {}


def _result_value(result: str, result_url: str | None = None) -> dict:
    link_available = bool(
        result_url
        and result_url.startswith(("https://", "http://"))
    )
    max_summary_length = 1900 if link_available else 2000
    summary = result[:max_summary_length]
    rich_text = []

    if summary:
        rich_text.append(
            {
                "type": "text",
                "text": {"content": summary},
            }
        )

    if link_available:
        label = (
            f" \u00b7 {RESULT_LINK_LABEL}"
            if summary
            else RESULT_LINK_LABEL
        )
        rich_text.append(
            {
                "type": "text",
                "text": {
                    "content": label,
                    "link": {"url": result_url},
                },
            }
        )

    return {"rich_text": rich_text}

def pending_items():
    filt = {
        "or": [
            {
                "property": "Status",
                "select": {"equals": "Novo"},
            },
            {
                "property": "Status",
                "select": {"is_empty": True},
            },
        ]
    }
    pages = query_data_source(
        settings.notion_inbox_data_source_id,
        filter_body=filt,
        sorts=[
            {
                "timestamp": "created_time",
                "direction": "ascending",
            }
        ],
    )
    out = []
    for p in pages:
        props = p.get("properties", {})
        msg = title_value(props.get("Mensagem"))
        if msg:
            explicit_author = select_value(props.get("Autor"))
            creator_user_id = p.get("created_by", {}).get("id")
            inferred_author = (
                None
                if explicit_author
                else author_from_creator_id(creator_user_id)
            )
            out.append(
                InboxItem(
                    p["id"],
                    msg,
                    select_value(props.get("Destino"))
                    or "Automático",
                    explicit_author or inferred_author or "Eu",
                    creator_user_id,
                    not explicit_author and inferred_author is not None,
                    p.get("last_edited_time"),
                )
            )
    return out


def stable_items(
    items: list[InboxItem],
    *,
    stability_seconds: int | None = None,
    monotonic_now: float | None = None,
) -> list[InboxItem]:
    """Só libera mensagens inalteradas por uma janela contínua."""
    delay = (
        settings.inbox_stability_seconds
        if stability_seconds is None
        else stability_seconds
    )
    if delay <= 0:
        return items

    current = time.monotonic() if monotonic_now is None else monotonic_now
    pending_ids = {item.page_id for item in items}
    for page_id in set(_stability_cache) - pending_ids:
        _stability_cache.pop(page_id, None)

    ready = []
    for item in items:
        # Objetos legados e stubs de teste não possuem o timestamp do Notion.
        # Eles continuam compatíveis e são processados imediatamente.
        if not item.last_edited_time:
            ready.append(item)
            continue

        previous = _stability_cache.get(item.page_id)
        if previous is None or previous[0] != item.message:
            _stability_cache[item.page_id] = (item.message, current)
            continue
        if current - previous[1] < delay:
            continue

        ready.append(item)
        _stability_cache.pop(item.page_id, None)
    return ready


def set_author(page_id: str, author: str):
    value = "Carol" if author == "Carol" else "Eu"
    update_page(
        page_id,
        {"Autor": {"select": {"name": value}}},
    )


def set_status(
    page_id: str,
    status: str,
    result: str | None = None,
    result_url: str | None = None,
):
    props = {"Status": {"select": {"name": status}}}
    if result is not None:
        props["Resultado"] = _result_value(result, result_url)
    if status in {"Processado", "Precisa confirmação", "Erro"}:
        props["Processado em"] = {
            "date": {
                "start": datetime.now(
                    ZoneInfo(settings.app_timezone)
                ).isoformat()
            }
        }
    update_page(page_id, props)
