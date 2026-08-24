from functools import lru_cache
import re
import unicodedata
from urllib.parse import quote

from app.config import settings
from app.notion.client import request


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", value).strip().lower()


def role_from_name(name: str) -> str | None:
    first_name = _normalize(name).split(" ", 1)[0]
    user_first = _normalize(settings.user_name).split(" ", 1)[0]
    partner_first = _normalize(settings.partner_name).split(" ", 1)[0]

    user_aliases = {user_first, "caleb", "calebe"} - {""}
    partner_aliases = {
        partner_first,
        "carol",
        "carolina",
    } - {""}

    if any(
        first_name == alias
        or (
            len(alias) >= 4
            and first_name.startswith(alias)
        )
        for alias in user_aliases
    ):
        return "Eu"
    if any(
        first_name == alias
        or (
            len(alias) >= 4
            and first_name.startswith(alias)
        )
        for alias in partner_aliases
    ):
        return "Minha esposa"
    return None


@lru_cache(maxsize=256)
def get_user(user_id: str) -> dict:
    return request("GET", f"/users/{user_id}")


def author_from_creator_id(user_id: str | None) -> str | None:
    if not user_id:
        return None
    try:
        user = get_user(user_id)
    except Exception:
        return None
    if user.get("type") != "person":
        return None
    role = role_from_name(user.get("name", ""))
    if role == "Minha esposa":
        return "Carol"
    if role == "Eu":
        return "Eu"
    return None


@lru_cache(maxsize=1)
def household_user_ids() -> dict[str, str]:
    users = []
    cursor = None
    while True:
        path = "/users?page_size=100"
        if cursor:
            path += f"&start_cursor={quote(cursor)}"
        data = request("GET", path)
        users.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break

    result = {}
    for user in users:
        if user.get("type") != "person":
            continue
        role = role_from_name(user.get("name", ""))
        if role and role not in result:
            result[role] = user["id"]
    return result
