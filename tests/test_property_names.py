from app.notion.client import _normalize_property_name


def test_property_name_normalization_handles_accents_and_slash_spaces():
    assert _normalize_property_name("Lugar / Experiência") == "lugar/experiencia"
    assert _normalize_property_name("Lugar/Experiencia") == "lugar/experiencia"
    assert _normalize_property_name("Preço estimado") == "preco estimado"
