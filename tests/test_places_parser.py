import pytest

from app.ai.parsers import fast_place


@pytest.mark.parametrize(
    ("phrase", "place", "local", "kind", "price"),
    [
        (
            "Quero conhecer um restaurante italiano em SP",
            "restaurante italiano",
            "sp",
            "Restaurante",
            None,
        ),
        (
            "Quero visitar o MASP em Sao Paulo",
            "masp",
            "sao paulo",
            "Passeio",
            None,
        ),
        (
            "Quero conhecer um hotel em Campos do Jordao de ate 900 reais",
            "hotel",
            "campos do jordao",
            "Hotel",
            900.0,
        ),
        (
            "Quero visitar um parque em Curitiba",
            "parque",
            "curitiba",
            "Passeio",
            None,
        ),
    ],
)
def test_places_common_phrases(phrase, place, local, kind, price):
    a = fast_place(phrase)
    assert a is not None
    assert a.lugar == place
    assert a.local == local
    assert a.tipo == kind
    assert a.valor_estimado == price


def test_place_unrelated_returns_none():
    assert fast_place("Paguei 50 no Uber") is None
