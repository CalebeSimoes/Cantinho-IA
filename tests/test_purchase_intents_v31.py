from datetime import date

import pytest

import app.ai.parsers as parsers
import app.ai.router as router
import app.notion.writers as writers
from app.schemas.actions import WishlistAction


REFERENCE = date(2026, 8, 23)


@pytest.fixture
def frozen_now(monkeypatch):
    class FrozenNow:
        def date(self):
            return REFERENCE

    monkeypatch.setattr(parsers, "now", lambda: FrozenNow())


@pytest.mark.parametrize(
    ("phrase", "destination"),
    [
        (
            "Calebe precisa comprar um micro-ondas de até 300 reais",
            "wishlist",
        ),
        ("Carol precisa comprar uma geladeira até sexta", "wishlist"),
        ("Tenho que comprar pão", "wishlist"),
        ("Comprar leite", "wishlist"),
        ("Vou adquirir um guarda-roupa mês que vem", "wishlist"),
        ("Comprar ração toda segunda-feira", "rotina"),
        ("Me lembre de comprar ração sexta", "rotina"),
        ("Não esquecer de comprar ração sexta", "rotina"),
        ("Pesquisar preços antes de comprar um notebook", "rotina"),
        ("Comprei um micro-ondas por 300 reais", "financas"),
    ],
)
def test_purchase_state_controls_destination(
    monkeypatch,
    phrase,
    destination,
):
    monkeypatch.setattr(
        router,
        "structured_chat",
        lambda *args, **kwargs: pytest.fail(
            "caso de compra deveria ser determinístico"
        ),
    )
    assert router.route_message(phrase).destination == destination


def test_negated_purchase_never_creates_positive_item():
    decision = router.route_message("Não comprar micro-ondas agora")
    assert decision.destination == "desconhecido"
    assert decision.confidence >= .90


@pytest.mark.parametrize(
    ("phrase", "task"),
    [
        ("Me lembre de comprar ração sexta", "comprar racao"),
        (
            "Pesquisar preços antes de comprar um notebook",
            "pesquisar precos antes de comprar um notebook",
        ),
    ],
)
def test_purchase_exceptions_are_extracted_as_routines(
    frozen_now,
    phrase,
    task,
):
    action = parsers.fast_routine(phrase, "Eu")
    assert action is not None
    assert action.tarefa == task


def test_planned_purchase_extracts_all_constraints(frozen_now):
    action = parsers.fast_wishlist(
        "Calebe precisa comprar um micro-ondas até sexta, "
        "de até 300 reais",
        "Eu",
    )

    assert action is not None
    assert action.item == "micro-ondas"
    assert action.data_desejada == date(2026, 8, 28)
    assert action.preco_estimado == 300
    assert action.preco_relacao == "Máximo"
    assert action.responsavel == "Eu"
    assert action.status == "Planejando"
    assert action.tipo == "Casa"


def test_partner_is_responsible_for_planned_purchase(frozen_now):
    action = parsers.fast_wishlist(
        "Carol precisa comprar uma cafeteira até amanhã",
        "Eu",
    )

    assert action is not None
    assert action.item == "cafeteira"
    assert action.data_desejada == date(2026, 8, 24)
    assert action.responsavel == "Minha esposa"


def test_product_numbers_are_not_mistaken_for_price(frozen_now):
    action = parsers.fast_wishlist(
        "Quero comprar uma TV 55 polegadas 4K",
        "Eu",
    )

    assert action is not None
    assert action.item == "tv 55 polegadas 4k"
    assert action.preco_estimado is None
    assert action.preco_relacao is None


def test_capacity_is_preserved_while_price_is_extracted(frozen_now):
    action = parsers.fast_wishlist(
        "Quero comprar um micro-ondas de 30 litros até 300 reais",
        "Eu",
    )

    assert action is not None
    assert action.item == "micro-ondas de 30 litros"
    assert action.preco_estimado == 300


def test_wishlist_writer_persists_new_optional_fields(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        writers.settings,
        "notion_wishlist_data_source_id",
        "wishlist",
    )
    monkeypatch.setattr(writers, "_p", lambda ds, name: name)
    monkeypatch.setattr(
        writers,
        "optional_property_name",
        lambda ds, name: name,
    )
    monkeypatch.setattr(
        writers,
        "create_page",
        lambda ds, props: saved.update(ds=ds, props=props) or {},
    )

    writers.write_wishlist(WishlistAction(
        item="micro-ondas",
        preco_estimado=300,
        preco_relacao="Máximo",
        responsavel="Eu",
        status="Planejando",
    ))

    assert saved["props"]["Relacao do preco"]["select"]["name"] == "Máximo"
    assert saved["props"]["Responsavel"]["select"]["name"] == "Eu"
