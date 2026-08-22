from app.config import settings
from app.notion.client import get_data_source

TARGETS = {
    "Inbox": settings.notion_inbox_data_source_id,
    "Finanças": settings.notion_finances_data_source_id,
    "Wishlist": settings.notion_wishlist_data_source_id,
    "Lugares": settings.notion_places_data_source_id,
    "Calendário": settings.notion_calendar_data_source_id,
    "Rotina": settings.notion_routine_data_source_id,
}

for name, ds_id in TARGETS.items():
    print(f"\n=== {name} ===")
    data = get_data_source(ds_id)
    props = data.get("properties", {})
    if not props:
        # Newer Notion response shapes may keep properties in another field.
        print("Data source acessível. ID:", data.get("id"))
        print("Para nomes exatos de propriedades, confira o schema no Notion.")
        continue

    for prop_name, prop in props.items():
        print(f"- {prop_name}: {prop.get('type')}")
