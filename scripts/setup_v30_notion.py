"""Migra o schema v3.0 e cria o Overview nativo do Notion."""

from datetime import date
from urllib.parse import quote

from app.config import settings
from app.notion.client import (
    get_data_source,
    optional_property_name,
    property_name,
    request,
    update_data_source,
    update_page,
)
from app.notion.readers import get_routines


DASHBOARD_NAME = "🌿 Overview do Cantinho"


def _sources() -> dict[str, str]:
    return {
        "inbox": settings.notion_inbox_data_source_id,
        "finances": settings.notion_finances_data_source_id,
        "wishlist": settings.notion_wishlist_data_source_id,
        "places": settings.notion_places_data_source_id,
        "calendar": settings.notion_calendar_data_source_id,
        "routine": settings.notion_routine_data_source_id,
    }


def ensure_schema() -> list[str]:
    changes = []
    sources = _sources()
    for label, ds in sources.items():
        schema = get_data_source(ds).get("properties", {})
        patch = {}
        if "Origem IA" not in schema:
            patch["Origem IA"] = {"rich_text": {}}
        if label == "wishlist":
            if "Responsável" not in schema:
                patch["Responsável"] = {
                    "select": {
                        "options": [
                            {"name": "Eu", "color": "blue"},
                            {"name": "Minha esposa", "color": "pink"},
                            {"name": "Nós dois", "color": "purple"},
                        ]
                    }
                }
            if "Relação do preço" not in schema:
                patch["Relação do preço"] = {
                    "select": {
                        "options": [
                            {"name": "Máximo", "color": "red"},
                            {"name": "Aproximado", "color": "yellow"},
                            {"name": "Exato", "color": "green"},
                            {"name": "Mínimo", "color": "blue"},
                        ]
                    }
                }
        if label == "routine":
            if "Recorrência" not in schema:
                patch["Recorrência"] = {"rich_text": {}}
            if "Última conclusão" not in schema:
                patch["Última conclusão"] = {"date": {}}
            if "Solicitado por" not in schema:
                patch["Solicitado por"] = {
                    "select": {
                        "options": [
                            {"name": "Eu", "color": "blue"},
                            {
                                "name": "Minha esposa",
                                "color": "pink",
                            },
                        ]
                    }
                }
            if "Notificar" not in schema:
                patch["Notificar"] = {"people": {}}

            frequency = schema.get("Frequência", {}).get("select", {})
            existing = frequency.get("options", [])
            existing_names = {item.get("name") for item in existing}
            wanted = {
                "Diária": "blue",
                "Semanal": "green",
                "Quinzenal": "purple",
                "Mensal": "orange",
                "Dias úteis": "yellow",
                "Fim de semana": "pink",
                "Pontual": "gray",
            }
            missing = [name for name in wanted if name not in existing_names]
            if missing:
                patch["Frequência"] = {
                    "select": {
                        "options": [
                            {"id": item["id"]}
                            for item in existing
                        ] + [
                            {"name": name, "color": wanted[name]}
                            for name in missing
                        ]
                    }
                }

            category = schema.get("Categoria", {}).get("select", {})
            existing_categories = category.get("options", [])
            category_names = {
                item.get("name") for item in existing_categories
            }
            if "Lazer" not in category_names:
                patch["Categoria"] = {
                    "select": {
                        "options": [
                            {"id": item["id"]}
                            for item in existing_categories
                        ] + [{"name": "Lazer", "color": "purple"}]
                    }
                }

            responsible = schema.get(
                "Responsável",
                {},
            ).get("select", {})
            existing_responsible = responsible.get("options", [])
            responsible_names = {
                item.get("name") for item in existing_responsible
            }
            if "Nós dois" not in responsible_names:
                patch["Responsável"] = {
                    "select": {
                        "options": [
                            {"id": item["id"]}
                            for item in existing_responsible
                        ] + [{"name": "Nós dois", "color": "purple"}]
                    }
                }
        if patch:
            update_data_source(ds, patch)
            changes.append(label)
    return changes


def _legacy_rule(record) -> str:
    if record.frequencia == "Diária":
        return "daily"
    if record.frequencia == "Semanal":
        return f"weekly:{(record.dia_data or date.today()).weekday()}"
    if record.frequencia == "Quinzenal":
        return "biweekly"
    if record.frequencia == "Mensal":
        return f"monthly:{(record.dia_data or date.today()).day}"
    if record.frequencia == "Dias úteis":
        return "weekdays"
    if record.frequencia == "Fim de semana":
        return "weekends"
    return "once"


def migrate_routine_rows() -> int:
    ds = settings.notion_routine_data_source_id
    recurrence_name = property_name(ds, "Recorrencia")
    changed = 0
    for record in get_routines():
        rule = _legacy_rule(record)
        if record.recurrence_rule != "once" or rule == "once":
            continue
        update_page(record.page_id, {
            recurrence_name: {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": rule},
                }]
            }
        })
        changed += 1
    return changed


def _database_id(data_source_id: str) -> str:
    return get_data_source(data_source_id)["parent"]["database_id"]


def _list_view_details(*, database_id: str | None = None, data_source_id: str | None = None):
    key = "database_id" if database_id else "data_source_id"
    value = database_id or data_source_id
    cursor = None
    details = []
    while True:
        path = f"/views?{key}={quote(value)}&page_size=100"
        if cursor:
            path += f"&start_cursor={quote(cursor)}"
        data = request("GET", path)
        for item in data.get("results", []):
            details.append(request("GET", f"/views/{item['id']}"))
        if not data.get("has_more"):
            return details
        cursor = data.get("next_cursor")


def _find_view(name: str, *, database_id=None, data_source_id=None, dashboard_id=None):
    for view in _list_view_details(
        database_id=database_id,
        data_source_id=data_source_id,
    ):
        if view.get("name") != name:
            continue
        if dashboard_id and view.get("dashboard_view_id") != dashboard_id:
            continue
        return view
    return None


def _create_widget(
    dashboard_id: str,
    data_source_id: str,
    name: str,
    *,
    filter_body: dict | None = None,
    sorts: list[dict] | None = None,
    placement: dict | None = None,
) -> dict:
    existing = _find_view(
        name,
        data_source_id=data_source_id,
        dashboard_id=dashboard_id,
    )
    if existing:
        update = {}
        if filter_body:
            update["filter"] = filter_body
        if sorts:
            update["sorts"] = sorts
        return (
            request("PATCH", f"/views/{existing['id']}", update)
            if update else existing
        )
    body = {
        "view_id": dashboard_id,
        "data_source_id": data_source_id,
        "name": name,
        "type": "list",
        "placement": placement or {"type": "new_row"},
    }
    if filter_body:
        body["filter"] = filter_body
    if sorts:
        body["sorts"] = sorts
    return request("POST", "/views", body)


def ensure_dashboard() -> dict:
    sources = _sources()
    inbox_db = _database_id(sources["inbox"])
    dashboard = _find_view(DASHBOARD_NAME, database_id=inbox_db)
    if not dashboard:
        dashboard = request("POST", "/views", {
            "database_id": inbox_db,
            "data_source_id": sources["inbox"],
            "name": DASHBOARD_NAME,
            "type": "dashboard",
            "position": {"type": "start"},
        })
    dashboard_id = dashboard["id"]

    _create_widget(
        dashboard_id,
        sources["routine"],
        "🌙 Tarefas abertas",
        filter_body={
            "property": "Status",
            "select": {"does_not_equal": "Concluído"},
        },
        sorts=[{"property": "Dia / Data", "direction": "ascending"}],
        placement={"type": "new_row"},
    )
    _create_widget(
        dashboard_id,
        sources["calendar"],
        "🗓️ Próximos compromissos",
        filter_body={
            "property": "Status",
            "select": {"does_not_equal": "Concluído"},
        },
        sorts=[{"property": "Data", "direction": "ascending"}],
        placement={"type": "existing_row", "row_index": 0},
    )
    _create_widget(
        dashboard_id,
        sources["finances"],
        "💸 Movimentações recentes",
        sorts=[{"property": "Data", "direction": "descending"}],
        placement={"type": "new_row"},
    )
    _create_widget(
        dashboard_id,
        sources["wishlist"],
        "🛍️ Wishlist ativa",
        filter_body={
            "or": [
                {"property": "Status", "select": {"equals": "Quero"}},
                {"property": "Status", "select": {"equals": "Planejando"}},
            ]
        },
        placement={"type": "new_row"},
    )
    _create_widget(
        dashboard_id,
        sources["places"],
        "📍 Lugares em aberto",
        filter_body={
            "property": "Status",
            "select": {"does_not_equal": "Feito"},
        },
        placement={"type": "existing_row", "row_index": 2},
    )
    return request("GET", f"/views/{dashboard_id}")


def _block_text(block: dict) -> str:
    payload = block.get(block.get("type", ""), {})
    return "".join(
        item.get("plain_text", "")
        for item in payload.get("rich_text", [])
    )


def _page_has_dashboard_link(page_id: str) -> bool:
    cursor = None
    while True:
        path = f"/blocks/{page_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={quote(cursor)}"
        data = request("GET", path)
        if any("Overview inteligente" in _block_text(block) for block in data.get("results", [])):
            return True
        if not data.get("has_more"):
            return False
        cursor = data.get("next_cursor")


def ensure_page_link(page_id: str, dashboard_url: str) -> bool:
    if _page_has_dashboard_link(page_id):
        return False
    request("PATCH", f"/blocks/{page_id}/children", {
        "children": [{
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🌿"},
                "color": "green_background",
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": "Abrir Overview inteligente do Cantinho →",
                        "link": {"url": dashboard_url},
                    },
                }],
            },
        }]
    })
    return True


def main():
    changed_schemas = ensure_schema()
    migrated = migrate_routine_rows()
    dashboard = ensure_dashboard()
    dashboard_url = dashboard.get("url")
    linked = []
    if dashboard_url:
        for page_id in (
            settings.notion_home_page_id,
            settings.notion_mobile_page_id,
        ):
            if ensure_page_link(page_id, dashboard_url):
                linked.append(page_id)
    print("Schemas atualizados:", changed_schemas or "nenhum")
    print("Rotinas migradas:", migrated)
    print("Dashboard:", dashboard_url)
    print("Atalhos adicionados:", len(linked))


if __name__ == "__main__":
    main()
