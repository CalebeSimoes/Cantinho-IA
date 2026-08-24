from dataclasses import dataclass
from datetime import datetime
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
                )
            )
    return out


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
