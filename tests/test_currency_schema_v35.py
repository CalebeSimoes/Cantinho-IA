import scripts.setup_v35_currency as migration


def test_currency_migration_updates_dollar_fields(monkeypatch):
    updates = []
    monkeypatch.setattr(
        migration,
        "MONEY_PROPERTIES",
        (("Finanças", "finance-ds", "Valor"),),
    )
    monkeypatch.setattr(
        migration,
        "property_name",
        lambda _data_source_id, logical_name: logical_name,
    )
    monkeypatch.setattr(
        migration,
        "get_data_source",
        lambda _data_source_id: {
            "properties": {
                "Valor": {"number": {"format": "dollar"}}
            }
        },
    )
    monkeypatch.setattr(
        migration,
        "update_data_source",
        lambda data_source_id, properties: updates.append(
            (data_source_id, properties)
        ),
    )

    assert migration.ensure_brl_number_formats() == [
        "Finanças.Valor: dollar -> real"
    ]
    assert updates == [
        ("finance-ds", {"Valor": {"number": {"format": "real"}}})
    ]


def test_currency_migration_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        migration,
        "MONEY_PROPERTIES",
        (("Wishlist", "wishlist-ds", "Preco estimado"),),
    )
    monkeypatch.setattr(
        migration,
        "property_name",
        lambda _data_source_id, _logical_name: "Preço estimado",
    )
    monkeypatch.setattr(
        migration,
        "get_data_source",
        lambda _data_source_id: {
            "properties": {
                "Preço estimado": {"number": {"format": "real"}}
            }
        },
    )
    monkeypatch.setattr(
        migration,
        "update_data_source",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("não deve atualizar")
        ),
    )

    assert migration.ensure_brl_number_formats() == []
