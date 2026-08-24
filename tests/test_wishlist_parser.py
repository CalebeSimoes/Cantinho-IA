import pytest

from app.ai.parsers import fast_wishlist


@pytest.mark.parametrize(
    ("phrase", "item", "price", "kind"),
    [
        (
            "Quero comprar um fone de ate 400 reais",
            "fone",
            400.0,
            "Tecnologia",
        ),
        (
            "Quero comprar um fone de ouvido de ate 400 reais",
            "fone de ouvido",
            400.0,
            "Tecnologia",
        ),
        (
            "Queria comprar uma cafeteira por 500 reais",
            "cafeteira",
            500.0,
            "Casa",
        ),
        (
            "Gostaria de comprar uma jaqueta",
            "jaqueta",
            None,
            "Roupa",
        ),
        (
            "Quero comprar um PS5 por R$ 3.500",
            "ps5",
            3500.0,
            "Tecnologia",
        ),
    ],
)
def test_wishlist_common_phrases(phrase, item, price, kind):
    a = fast_wishlist(phrase)
    assert a is not None
    assert a.item == item
    assert a.preco_estimado == price
    assert a.tipo == kind


def test_wishlist_unrelated_returns_none():
    assert fast_wishlist("Paguei 30 no Uber") is None
