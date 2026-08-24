import pytest

import app.ai.action_planner as action_planner
import app.ai.router as router


@pytest.fixture
def no_router_ai(monkeypatch):
    monkeypatch.setattr(
        router,
        "structured_chat",
        lambda *args, **kwargs: pytest.fail("a regra deveria decidir sem Ollama"),
    )


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("Calebe precisa comprar um micro-ondas de até 300 reais", "wishlist"),
        ("Calebe quer um tênis preto número 41", "wishlist"),
        ("Precisamos de uma estante pequena para a sala", "wishlist"),
        ("Carol quer visitar o Jardim Botânico algum dia", "lugares"),
        ("Vamos guardar a ideia de ir àquele café com livros", "lugares"),
        ("A gente quer experimentar a pizzaria da esquina", "lugares"),
        ("Quanto gastamos com mercado este mês?", "query"),
        ("Quem está responsável por lavar a louça hoje?", "query"),
        ("Existe algum compromisso conflitante na sexta à noite?", "query"),
        ("Nossa consulta de rotina é dia 28 às 9h30", "calendario"),
        ("O técnico da internet vem hoje entre 13h e 17h", "calendario"),
        ("Carol colocar a roupa na máquina amanhã cedo", "rotina"),
        ("Regar as plantas segunda, quarta e sexta", "rotina"),
        ("Dar remédio para o cachorro e avisar quando terminar", "rotina"),
        ("HBO Isso não é pedido nem pergunta", "desconhecido"),
        ("300 reais", "desconhecido"),
    ],
)
def test_battery_families_are_deterministic(no_router_ai, phrase, expected):
    assert router.route_message(phrase).destination == expected


@pytest.mark.parametrize(
    "phrase",
    [
        "Calebe precisa comprar um micro-ondas e ainda não compramos, é só para lembrar da compra.",
        "Dentista da Carol terça-feira às 14h; não é uma rotina recorrente.",
        "Nossa consulta é dia 28 às 9h30 e a Carol também vai.",
        "Dar remédio para o cachorro e avisar quando terminar.",
        "Quando é a próxima consulta do Calebe?",
    ],
)
def test_descriptive_conjunction_is_not_multi(phrase):
    assert action_planner._looks_multi(phrase) is False


@pytest.mark.parametrize(
    "phrase",
    [
        "Paguei 90 reais no mercado e Calebe precisa lavar a louça hoje.",
        "Calebe limpar o banheiro hoje e Carol trocar a roupa de cama amanhã.",
        "Quero comprar um sofá e visitar a loja do centro algum dia.",
        "Paguei a internet, marcar reunião terça às 19h e tirar o lixo hoje.",
    ],
)
def test_two_independent_actions_are_multi(phrase):
    assert action_planner._looks_multi(phrase) is True


def test_question_never_builds_an_action_plan(monkeypatch):
    monkeypatch.setattr(
        action_planner,
        "structured_chat",
        lambda *args, **kwargs: pytest.fail("pergunta não pode chamar planejador"),
    )
    assert action_planner.build_action_plan(
        "Quando é a próxima consulta do Calebe?"
    ) is None


@pytest.mark.parametrize(
    "phrase",
    [
        "Paguei 90 reais no mercado e Calebe precisa lavar a louça hoje; são registros separados.",
        "Comprar uma cafeteira e marcar dentista sexta às 10h; a primeira parte é uma coisa e a segunda é outra.",
    ],
)
def test_trailing_multi_explanation_does_not_hide_real_actions(phrase):
    assert action_planner._looks_multi(phrase) is True
