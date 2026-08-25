"""Configura todos os campos monetários do Cantinho como real brasileiro."""

from app.config import settings
from app.notion.client import (
    get_data_source,
    property_name,
    update_data_source,
)


MONEY_PROPERTIES = (
    (
        "Finanças",
        settings.notion_finances_data_source_id,
        "Valor",
    ),
    (
        "Wishlist",
        settings.notion_wishlist_data_source_id,
        "Preco estimado",
    ),
    (
        "Lugares",
        settings.notion_places_data_source_id,
        "Valor estimado",
    ),
)


def ensure_brl_number_formats() -> list[str]:
    changes = []
    for label, data_source_id, logical_name in MONEY_PROPERTIES:
        real_name = property_name(data_source_id, logical_name)
        schema = get_data_source(data_source_id).get("properties", {})
        current_format = (
            schema.get(real_name, {}).get("number", {}).get("format")
        )
        if current_format == "real":
            continue
        update_data_source(
            data_source_id,
            {real_name: {"number": {"format": "real"}}},
        )
        changes.append(f"{label}.{real_name}: {current_format} -> real")
    return changes


if __name__ == "__main__":
    updated = ensure_brl_number_formats()
    if updated:
        print("Formatos atualizados:")
        for item in updated:
            print(f"- {item}")
    else:
        print("Todos os campos monetários já usam real brasileiro.")
