import pytest

import app.ai.router as router
from app.schemas.actions import RouterDecision


@pytest.fixture
def no_ai(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Ollama nao deveria ser chamado neste caso")

    monkeypatch.setattr(router, "structured_chat", fail)


@pytest.mark.parametrize(
    ("phrase", "destination"),
    [
        ("Paguei 25 reais no Uber", "financas"),
        ("Paguei no mercado", "financas"),
        ("Recebi 200 de reembolso", "financas"),
        ("Quero comprar uma cafeteira de ate 500 reais", "wishlist"),
        ("Quero conhecer um restaurante japones", "lugares"),
        ("Quero visitar o MASP", "lugares"),
        ("Agendar cinema sabado as 20h", "calendario"),
        ("Marcar consulta amanha", "calendario"),
        ("Toda semana precisamos limpar a cozinha", "rotina"),
        ("Temos que arrumar a casa", "rotina"),
    ],
)
def test_router_deterministic(no_ai, phrase, destination):
    assert router.route_message(phrase).destination == destination


def test_explicit_destination_never_calls_ai(no_ai):
    d = router.route_message("qualquer coisa", "Finanças")
    assert d.destination == "financas"
    assert d.confidence == 1


def test_word_as_does_not_force_calendar(monkeypatch):
    monkeypatch.setattr(
        router,
        "structured_chat",
        lambda *args, **kwargs: RouterDecision(
            destination="desconhecido",
            confidence=0.2,
            reason="ambiguo",
        ),
    )
    d = router.route_message("Precisamos limpar as janelas")
    assert d.destination != "calendario"
