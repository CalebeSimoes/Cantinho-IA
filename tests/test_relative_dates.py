from datetime import date

import pytest

from app.ai.date_utils import (
    resolve_date_expression,
    strip_temporal_expressions,
)


REFERENCE = date(2026, 8, 23)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("hoje", date(2026, 8, 23)),
        ("amanha", date(2026, 8, 24)),
        ("depois de amanha", date(2026, 8, 25)),
        ("final do mes", date(2026, 8, 31)),
        ("fim do proximo mes", date(2026, 9, 30)),
        ("inicio do proximo mes", date(2026, 9, 1)),
        ("dia 28", date(2026, 8, 28)),
        ("dia 10", date(2026, 9, 10)),
        ("10/09/2026", date(2026, 9, 10)),
        ("30 de setembro", date(2026, 9, 30)),
        ("sabado", date(2026, 8, 29)),
        ("segunda que vem", date(2026, 8, 24)),
        ("daqui a 15 dias", date(2026, 9, 7)),
        ("semana que vem", date(2026, 8, 30)),
    ],
)
def test_relative_date_resolution(phrase, expected):
    assert resolve_date_expression(phrase, REFERENCE) == expected


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("assinar hbo final do mes", "assinar hbo"),
        ("pagar internet dia 10", "pagar internet"),
        ("cinema sabado as 20h", "cinema"),
        ("consulta amanha as 15h", "consulta"),
    ],
)
def test_temporal_expression_is_removed_from_title(phrase, expected):
    assert strip_temporal_expressions(phrase) == expected
