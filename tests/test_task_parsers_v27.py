from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

import app.ai.parsers as parsers


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(
        parsers,
        "now",
        lambda: datetime(
            2026,
            8,
            23,
            12,
            0,
            tzinfo=ZoneInfo("America/Sao_Paulo"),
        ),
    )


def test_hbo_deadline_becomes_one_off_task():
    action = parsers.fast_routine(
        "Calebe precisa assinar HBO final do mes"
    )

    assert action.tarefa == "assinar hbo"
    assert action.dia_data == date(2026, 8, 31)
    assert action.frequencia == "Pontual"
    assert action.responsavel == "Eu"
    assert action.categoria == "Outro"
    assert action.needs_confirmation is False


def test_partner_task_is_attributed_to_partner():
    action = parsers.fast_routine(
        "Carol precisa renovar o passaporte semana que vem"
    )

    assert action.tarefa == "renovar o passaporte"
    assert action.dia_data == date(2026, 8, 30)
    assert action.responsavel == "Minha esposa"


def test_joint_recurring_chore():
    action = parsers.fast_routine(
        "Toda semana precisamos limpar a cozinha"
    )

    assert action.tarefa == "limpar a cozinha"
    assert action.frequencia == "Semanal"
    assert action.responsavel == "Nós dois"
    assert action.categoria == "Casa"


def test_deadline_is_not_mistaken_for_monthly_recurrence():
    action = parsers.fast_routine(
        "Preciso cancelar a assinatura no final do proximo mes"
    )

    assert action.dia_data == date(2026, 9, 30)
    assert action.frequencia == "Pontual"


def test_form_author_is_default_responsible():
    action = parsers.fast_routine(
        "Lembrar de enviar os documentos amanha",
        author="Carol",
    )

    assert action.responsavel == "Minha esposa"
    assert action.dia_data == date(2026, 8, 24)


def test_purchase_desire_does_not_become_routine():
    assert parsers.fast_routine("Quero assinar HBO") is None
    wishlist = parsers.fast_wishlist("Quero assinar HBO")
    assert wishlist.item == "hbo"
    assert wishlist.tipo == "Tecnologia"


def test_calendar_resolves_weekday_and_removes_time_from_title():
    action = parsers.fast_calendar(
        "Marcar cinema sabado as 20h"
    )

    assert action.evento == "cinema"
    assert action.data == date(2026, 8, 29)
    assert action.tipo == "Encontro"
    assert action.needs_confirmation is False


def test_calendar_without_date_still_requests_confirmation():
    action = parsers.fast_calendar("Marcar consulta")

    assert action.evento == "consulta"
    assert action.data is None
    assert action.needs_confirmation is True
    assert action.missing_fields == ["data"]


def test_task_with_deadline_is_not_calendar():
    assert parsers.fast_calendar(
        "Calebe precisa assinar HBO final do mes"
    ) is None
