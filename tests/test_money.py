import pytest

from app.ai.parsers import _to_float, money


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("32", 32.0),
        ("32,50", 32.5),
        ("1.250,90", 1250.9),
        ("2.500", 2500.0),
        ("R$ 1.999,99", 1999.99),
        ("3500", 3500.0),
        ("25.50", 25.5),
        ("1.250.000", 1250000.0),
    ],
)
def test_to_float_br_formats(raw, expected):
    assert _to_float(raw) == expected


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("Paguei 32 no Uber", 32.0),
        ("Paguei 32,50 no Uber", 32.5),
        ("Gastei 1.250,90 no mercado", 1250.9),
        ("Gastei 2.500 no mercado", 2500.0),
        ("Paguei R$ 1.999,99 no mercado", 1999.99),
        ("Quero comprar um fone de ate 400 reais", 400.0),
        ("Comprei 3500 no notebook", 3500.0),
        ("Custando R$ 89,90", 89.9),
        ("Valor de 120 reais", 120.0),
    ],
)
def test_money_extracts_common_phrases(phrase, expected):
    assert money(phrase) == expected


def test_money_without_number_is_none():
    assert money("Paguei no mercado") is None
