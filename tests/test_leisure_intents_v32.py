from datetime import date

import pytest

import app.ai.parsers as parsers
import app.ai.router as router
from app.ai.recurrence import parse_recurrence


REFERENCE = date(2026, 8, 24)


@pytest.fixture
def frozen_now(monkeypatch):
    class FrozenNow:
        def date(self):
            return REFERENCE

    monkeypatch.setattr(parsers, "now", lambda: FrozenNow())


def test_mentalista_routes_locally_to_routine(monkeypatch):
    monkeypatch.setattr(
        router,
        "structured_chat",
        lambda *args, **kwargs: pytest.fail(
            "a intenção de lazer deveria ser determinística"
        ),
    )

    decision = router.route_message(
        "Assistir serie o mentalista final de semana"
    )

    assert decision.destination == "rotina"
    assert decision.confidence >= .90


def test_mentalista_is_point_in_time_leisure(frozen_now):
    action = parsers.fast_routine(
        "Assistir serie o mentalista final de semana"
    )

    assert action is not None
    assert action.tarefa == "assistir serie o mentalista"
    assert action.categoria == "Lazer"
    assert action.dia_data == date(2026, 8, 29)
    assert action.frequencia == "Pontual"
    assert action.recurrence_rule == "once"
    assert action.responsavel == "Eu"


@pytest.mark.parametrize(
    "phrase",
    [
        "Assistir O Mentalista no fim de semana",
        "Assistir O Mentalista neste fim de semana",
        "Assistir O Mentalista no final de semana",
        "Assistir O Mentalista neste final de semana",
        "Assistir O Mentalista no final da semana",
    ],
)
def test_singular_weekend_variants_are_point_in_time(frozen_now, phrase):
    action = parsers.fast_routine(phrase)

    assert action is not None
    assert action.tarefa == "assistir o mentalista"
    assert action.categoria == "Lazer"
    assert action.dia_data == date(2026, 8, 29)
    assert action.frequencia == "Pontual"
    assert action.recurrence_rule == "once"


@pytest.mark.parametrize(
    "phrase",
    [
        "Assistir O Mentalista todo fim de semana",
        "Assistir O Mentalista todo final de semana",
        "Assistir O Mentalista nos fins de semana",
        "Assistir O Mentalista aos finais de semana",
    ],
)
def test_only_explicit_weekend_language_is_recurring(frozen_now, phrase):
    action = parsers.fast_routine(phrase)

    assert action is not None
    assert action.tarefa == "assistir o mentalista"
    assert action.dia_data == date(2026, 8, 29)
    assert action.frequencia == "Fim de semana"
    assert action.recurrence_rule == "weekends"


def test_recurrence_parser_keeps_bare_weekend_point_in_time():
    point_in_time = parse_recurrence(
        "Assistir série no fim de semana",
        REFERENCE,
    )
    recurring = parse_recurrence(
        "Assistir série todo fim de semana",
        REFERENCE,
    )

    assert point_in_time.frequency == "Pontual"
    assert point_in_time.rule == "once"
    assert point_in_time.due_date == date(2026, 8, 29)
    assert recurring.frequency == "Fim de semana"
    assert recurring.rule == "weekends"
