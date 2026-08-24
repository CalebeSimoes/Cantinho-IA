import pytest

import app.ai.router as router


@pytest.fixture
def no_ai(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError(
            "O classificador Python deveria resolver esta frase"
        )

    monkeypatch.setattr(router, "structured_chat", fail)


@pytest.mark.parametrize(
    ("phrase", "destination"),
    [
        ("Paguei 80 reais de internet", "financas"),
        ("Assinei HBO por 30 reais", "financas"),
        ("Transferi 500 reais para a Carol", "financas"),
        ("Recebemos 200 de reembolso", "financas"),
        ("Comprei um sofa por 2.000 reais", "financas"),
        ("Quero assinar HBO", "wishlist"),
        ("Gostaria de assinar Spotify", "wishlist"),
        ("Quero comprar uma bicicleta", "wishlist"),
        ("Coloca uma air fryer na wishlist", "wishlist"),
        ("Sonho em ter um projetor", "wishlist"),
        ("Quero conhecer o MASP", "lugares"),
        ("Gostaria de ir ao parque Ibirapuera", "lugares"),
        ("Vamos conhecer um restaurante mexicano", "lugares"),
        ("Quero visitar uma praia tranquila", "lugares"),
        ("Quero conhecer um hotel fazenda sabado", "lugares"),
        ("Cinema sabado as 20h", "calendario"),
        ("Jantar amanha as 19h", "calendario"),
        ("Reuniao dia 30", "calendario"),
        ("Agendar dentista dia 10", "calendario"),
        ("Marcar consulta amanha", "calendario"),
        ("Aniversario da Carol 10/09/2026", "calendario"),
        ("Quero ir ao cinema sabado", "calendario"),
        ("Calebe precisa assinar HBO final do mes", "rotina"),
        ("Preciso assinar HBO no fim do mes", "rotina"),
        ("Carol precisa renovar o passaporte semana que vem", "rotina"),
        ("Preciso pagar a internet dia 10", "rotina"),
        ("Nao esquecer de levar o carro para revisao amanha", "rotina"),
        ("Todo mes precisamos organizar os documentos", "rotina"),
        ("A conta de luz vence dia 10", "rotina"),
        ("Calebe precisa comprar detergente amanha", "wishlist"),
        ("Temos que limpar a cozinha toda semana", "rotina"),
        ("Lembrar de cancelar o teste gratis dia 28", "rotina"),
        ("Carol deve enviar o relatorio amanha", "rotina"),
        ("Preciso estudar para a prova", "rotina"),
        ("Diariamente tomar o remedio", "rotina"),
        ("Separar os documentos importantes", "rotina"),
        ("Revisar o contrato", "rotina"),
        ("Comprar leite", "wishlist"),
    ],
)
def test_semantic_routing_without_ollama(
    no_ai,
    phrase,
    destination,
):
    decision = router.route_message(phrase)
    assert decision.destination == destination
    assert decision.confidence >= .90


def test_python_evidence_can_raise_matching_ai_confidence(monkeypatch):
    monkeypatch.setattr(
        router,
        "_rule_decision",
        lambda message: None,
    )
    monkeypatch.setattr(
        router,
        "structured_chat",
        lambda *args, **kwargs: router.RouterDecision(
            destination="rotina",
            confidence=.4,
            reason="parece tarefa",
        ),
    )

    decision = router.route_message(
        "Preciso assinar HBO no fim do mes"
    )

    assert decision.destination == "rotina"
    assert decision.confidence >= .72
    assert "Python" in decision.reason
