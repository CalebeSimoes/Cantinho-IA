from dataclasses import dataclass

from app.notion.client import (
    optional_property_name,
    request,
    update_page,
)
from app.config import settings
from app.notion.users import household_user_ids


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    mode: str
    recipients: tuple[str, ...] = ()


def _recipient_roles(
    responsible: str,
    requested_by: str,
) -> list[str]:
    if responsible == "Nós dois":
        roles = ["Eu", "Minha esposa"]
    elif responsible in {"Eu", "Minha esposa"}:
        roles = [responsible]
    else:
        roles = []
    return [role for role in roles if role != requested_by]


def _mentioned_body(user_ids: list[str], text: str) -> dict:
    rich_text = []
    for index, user_id in enumerate(user_ids):
        if index:
            rich_text.append({
                "type": "text",
                "text": {"content": ", "},
            })
        rich_text.append({
            "type": "mention",
            "mention": {
                "type": "user",
                "user": {"object": "user", "id": user_id},
            },
        })
    rich_text.append({
        "type": "text",
        "text": {"content": text[:1900]},
    })
    return {"rich_text": rich_text}


def _comment_body(user_ids: list[str], task: str) -> dict:
    return _mentioned_body(
        user_ids,
        " 🌙 Tarefa adicionada na Rotina do casal: " + task[:500],
    )


def notify_routine_assignment(
    page_id: str,
    task: str,
    responsible: str,
    requested_by: str,
) -> NotificationResult:
    roles = _recipient_roles(responsible, requested_by)
    if not roles:
        return NotificationResult(False, "skipped")

    try:
        users = household_user_ids()
        recipients = [
            (role, users[role])
            for role in roles
            if role in users
        ]
    except Exception as exc:
        print(
            "[Notion] Não foi possível localizar destinatários da "
            f"notificação: {type(exc).__name__}: {exc}",
            flush=True,
        )
        return NotificationResult(False, "failed")

    if not recipients:
        return NotificationResult(False, "failed")

    labels = tuple(role for role, _ in recipients)
    user_ids = [user_id for _, user_id in recipients]
    try:
        request(
            "POST",
            "/comments",
            {
                "parent": {"page_id": page_id},
                **_comment_body(user_ids, task),
            },
        )
        return NotificationResult(True, "mention", labels)
    except Exception as comment_error:
        try:
            property_name = optional_property_name(
                settings.notion_routine_data_source_id,
                "Notificar",
            )
            if not property_name:
                raise RuntimeError("Propriedade Notificar ausente.")
            update_page(
                page_id,
                {
                    property_name: {
                        "people": [
                            {"object": "user", "id": user_id}
                            for user_id in user_ids
                        ]
                    }
                },
            )
            return NotificationResult(True, "people", labels)
        except Exception as fallback_error:
            print(
                "[Notion] Tarefa criada, mas o aviso mobile falhou: "
                f"comentário={type(comment_error).__name__}; "
                f"fallback={type(fallback_error).__name__}",
                flush=True,
            )
            return NotificationResult(False, "failed", labels)


def notify_household_radar(message: str) -> NotificationResult:
    """Menciona o casal no Radar; o comentário abre a página mobile."""
    try:
        users = household_user_ids()
        recipients = [
            (role, users[role])
            for role in ("Eu", "Minha esposa")
            if role in users
        ]
    except Exception as exc:
        print(
            "[Notion] Não foi possível localizar o casal para o Radar: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        return NotificationResult(False, "failed")

    if not recipients:
        return NotificationResult(False, "failed")

    labels = tuple(role for role, _ in recipients)
    user_ids = [user_id for _, user_id in recipients]
    body = {
        "parent": {"page_id": settings.notion_mobile_page_id},
        **_mentioned_body(user_ids, " " + message),
    }
    try:
        request("POST", "/comments", body)
        return NotificationResult(True, "radar_mobile", labels)
    except Exception as mobile_error:
        if settings.notion_home_page_id == settings.notion_mobile_page_id:
            print(
                "[Notion] O aviso do Radar falhou: "
                f"{type(mobile_error).__name__}: {mobile_error}",
                flush=True,
            )
            return NotificationResult(False, "failed", labels)
        try:
            request(
                "POST",
                "/comments",
                {
                    "parent": {"page_id": settings.notion_home_page_id},
                    **_mentioned_body(user_ids, " " + message),
                },
            )
            return NotificationResult(True, "radar_home", labels)
        except Exception as home_error:
            print(
                "[Notion] O aviso do Radar falhou nas páginas mobile e Home: "
                f"mobile={type(mobile_error).__name__}; "
                f"home={type(home_error).__name__}",
                flush=True,
            )
            return NotificationResult(False, "failed", labels)
