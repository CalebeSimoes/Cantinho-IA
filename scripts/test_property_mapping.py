from app.config import settings
from app.notion.client import property_name

tests = [
    (
        "Financas",
        settings.notion_finances_data_source_id,
        ["Movimento", "Observacao", "Pago por"],
    ),
    (
        "Wishlist",
        settings.notion_wishlist_data_source_id,
        ["Item", "Preco estimado", "Observacao"],
    ),
    (
        "Lugares",
        settings.notion_places_data_source_id,
        ["Lugar / Experiencia", "Descricao", "Local"],
    ),
    (
        "Calendario",
        settings.notion_calendar_data_source_id,
        ["Evento", "Observacao", "Data"],
    ),
    (
        "Rotina",
        settings.notion_routine_data_source_id,
        ["Tarefa", "Frequencia", "Responsavel", "Dia / Data"],
    ),
]

for area, ds_id, names in tests:
    print(f"\n[{area}]")
    for logical in names:
        real = property_name(ds_id, logical)
        print(f"  {logical} -> {real}")
