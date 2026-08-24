from datetime import date

import pytest

import app.ai.router as router
import app.ai.query_parser as query_parser
import app.notion.client as notion_client
import app.notion.readers as notion_readers
import app.processor as processor
import app.query_service as query_service
from app.ai.query_parser import parse_query
from app.notion.readers import (
    CalendarRecord,
    FinanceRecord,
    PlaceRecord,
    RoutineRecord,
    WishlistRecord,
)
from app.schemas.actions import QueryIntent, RouterDecision


@pytest.fixture
def no_ai(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Ollama não deveria ser chamado")

    monkeypatch.setattr(router, "structured_chat", fail)


@pytest.mark.parametrize(
    "phrase",
    [
        "Quanto gastamos este mês?",
        "Quanto eu gastei com Uber?",
        "Quanto a Carol pagou este mês?",
        "O que temos marcado para sábado?",
        "Quais lugares queremos conhecer?",
        "Qual item mais caro da wishlist?",
        "Quais tarefas continuam sem terminar?",
        "Qual foi a maior mordida no orçamento no mês passado?",
        "O sábado está livre para nós?",
        "Do que ainda estamos sonhando em comprar?",
        "Tem alguma coisa importante vencendo nas próximas semanas?",
    ],
)
def test_questions_are_never_routed_as_new_records(no_ai, phrase):
    assert router.route_message(phrase).destination == "query"


@pytest.mark.parametrize(
    ("phrase", "destination"),
    [
        ("Paguei 30 no Uber", "financas"),
        ("Quero comprar uma cafeteira", "wishlist"),
        ("Quero conhecer o MASP", "lugares"),
        ("Cinema sábado às 20h", "calendario"),
        ("Preciso assinar HBO no fim do mês", "rotina"),
        ("Carol já pagou 128 reais na farmácia", "financas"),
        ("Estamos pensando em comprar um aspirador robô", "wishlist"),
        ("Queremos visitar a Pinacoteca algum dia", "lugares"),
        ("O jantar de aniversário ficou para sábado às 20h", "calendario"),
        ("Todo segundo domingo precisamos revisar o orçamento", "rotina"),
    ],
)
def test_complex_statements_still_register(no_ai, phrase, destination):
    assert router.route_message(phrase).destination == destination


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        (
            "Pensando nas corridas que a Carol pagou, consegue me dizer quanto saiu de Uber neste mês?",
            {
                "domain": "financas",
                "operation": "total",
                "period": "this_month",
                "person": "Minha esposa",
                "term": "Uber",
                "transaction_type": "Saída",
            },
        ),
        (
            "Sem incluir o que já compramos, qual desejo com preço informado pesa mais no bolso?",
            {
                "domain": "wishlist",
                "operation": "max",
                "status": "Ativos",
            },
        ),
        (
            "No sábado que vem, temos algum compromisso ou dá pra planejar um passeio?",
            {
                "domain": "calendario",
                "operation": "list",
                "period": "specific_date",
            },
        ),
        (
            "Entre os lugares que ainda são só ideia, quais ainda queremos conhecer?",
            {
                "domain": "lugares",
                "operation": "list",
                "status": "Ideia",
            },
        ),
        (
            "Quais tarefas da Carol continuam sem terminar até o fim do mês?",
            {
                "domain": "rotina",
                "period": "this_month",
                "person": "Minha esposa",
                "status": "Pendentes",
            },
        ),
        (
            "Eu queria saber quanto eu gastei com transporte no mês passado",
            {
                "domain": "financas",
                "operation": "total",
                "period": "last_month",
                "person": "Eu",
                "term": "Transporte",
            },
        ),
    ],
)
def test_complex_query_context_is_structured(phrase, expected):
    parsed = parse_query(phrase, reference=date(2026, 8, 23))
    for field, value in expected.items():
        assert getattr(parsed, field) == value


def test_esse_mes_is_understood_as_current_month():
    parsed = parse_query(
        "Quanto eu gastei com Uber esse mês?",
        reference=date(2026, 8, 23),
    )
    assert parsed.period == "this_month"


def test_python_sanitizes_cross_domain_fields_from_ollama(monkeypatch):
    monkeypatch.setattr(
        query_parser,
        "structured_chat",
        lambda *args, **kwargs: QueryIntent(
            domain="wishlist",
            operation="list",
            person="Eu",
            transaction_type="Saída",
            term="inventado",
            reason="vontade material",
        ),
    )
    parsed = query_parser.parse_query(
        "Qual vontade material nossa tem o valor mais alto?",
        reference=date(2026, 8, 23),
    )
    assert parsed.domain == "wishlist"
    assert parsed.operation == "max"
    assert parsed.person is None
    assert parsed.transaction_type is None
    assert parsed.term is None


def test_finance_query_aggregates_period_person_and_term(monkeypatch):
    records = [
        FinanceRecord("1", "Uber", 30, "Saída", "Transporte", "Eu", "Pago", date(2026, 8, 2), ""),
        FinanceRecord("2", "Uber volta", 22.5, "Saída", "Transporte", "Eu", "Pago", date(2026, 8, 8), ""),
        FinanceRecord("3", "Uber Carol", 40, "Saída", "Transporte", "Minha esposa", "Pago", date(2026, 8, 9), ""),
        FinanceRecord("4", "Uber julho", 99, "Saída", "Transporte", "Eu", "Pago", date(2026, 7, 9), ""),
    ]
    monkeypatch.setattr(query_service.readers, "get_finances", lambda: records)
    answer = query_service.execute_query(
        QueryIntent(
            domain="financas",
            operation="total",
            period="this_month",
            person="Eu",
            term="Uber",
            transaction_type="Saída",
        ),
        reference=date(2026, 8, 23),
    )
    assert "R$ 52,50" in answer
    assert "2 movimentações" in answer


def test_finance_summary_calculates_balance(monkeypatch):
    records = [
        FinanceRecord("1", "Salário", 3000, "Entrada", "Outros", "Eu", "Pago", date(2026, 8, 2), ""),
        FinanceRecord("2", "Aluguel", 1200, "Saída", "Moradia", "Eu", "Pago", date(2026, 8, 3), ""),
    ]
    monkeypatch.setattr(query_service.readers, "get_finances", lambda: records)
    answer = query_service.execute_query(
        QueryIntent(domain="financas", operation="summary", period="this_month"),
        reference=date(2026, 8, 23),
    )
    assert "entradas R$ 3.000,00" in answer
    assert "saídas R$ 1.200,00" in answer
    assert "saldo R$ 1.800,00" in answer


def test_wishlist_max_ignores_completed_items(monkeypatch):
    records = [
        WishlistRecord("1", "TV comprada", 8000, "Comprado", None, None, None, "", None),
        WishlistRecord("2", "Cafeteira", 1200, "Quero", None, None, None, "", None),
        WishlistRecord("3", "Livro", 100, "Quero", None, None, None, "", None),
    ]
    monkeypatch.setattr(query_service.readers, "get_wishlist", lambda: records)
    answer = query_service.execute_query(
        QueryIntent(domain="wishlist", operation="max", status="Ativos")
    )
    assert "Cafeteira" in answer
    assert "TV comprada" not in answer


def test_calendar_specific_day(monkeypatch):
    records = [
        CalendarRecord("1", "Cinema", date(2026, 8, 29), "Nós dois", "Confirmado", "Encontro", "Shopping", ""),
        CalendarRecord("2", "Consulta", date(2026, 8, 28), "Eu", "Confirmado", "Compromisso", "", ""),
    ]
    monkeypatch.setattr(query_service.readers, "get_calendar", lambda: records)
    answer = query_service.execute_query(
        QueryIntent(
            domain="calendario",
            operation="list",
            period="specific_date",
            specific_date=date(2026, 8, 29),
        )
    )
    assert "Cinema" in answer
    assert "Consulta" not in answer


def test_places_and_routines_apply_contextual_status(monkeypatch):
    monkeypatch.setattr(
        query_service.readers,
        "get_places",
        lambda: [
            PlaceRecord("1", "MASP", "Ideia", None, None, None, None, "SP", ""),
            PlaceRecord("2", "Parque", "Feito", None, None, None, None, "SP", ""),
        ],
    )
    places = query_service.execute_query(
        QueryIntent(domain="lugares", operation="list", status="Ideia")
    )
    assert "MASP" in places and "Parque" not in places

    monkeypatch.setattr(
        query_service.readers,
        "get_routines",
        lambda: [
            RoutineRecord("1", "Pagar conta", None, date(2026, 8, 25), None, "Minha esposa", "A fazer", ""),
            RoutineRecord("2", "Arquivar", None, date(2026, 8, 20), None, "Minha esposa", "Concluído", ""),
        ],
    )
    routines = query_service.execute_query(
        QueryIntent(
            domain="rotina",
            operation="list",
            period="this_month",
            person="Minha esposa",
            status="Pendentes",
        ),
        reference=date(2026, 8, 23),
    )
    assert "Pagar conta" in routines and "Arquivar" not in routines


def test_notion_query_paginates_until_the_end(monkeypatch):
    calls = []
    responses = [
        {"results": [{"id": "1"}], "has_more": True, "next_cursor": "next"},
        {"results": [{"id": "2"}], "has_more": False, "next_cursor": None},
    ]

    def fake_request(method, path, payload):
        calls.append(payload.copy())
        return responses.pop(0)

    monkeypatch.setattr(notion_client, "request", fake_request)
    result = notion_client.query_data_source("database")
    assert [item["id"] for item in result] == ["1", "2"]
    assert "start_cursor" not in calls[0]
    assert calls[1]["start_cursor"] == "next"


def test_all_five_notion_readers_map_real_property_shapes(monkeypatch):
    def title(value):
        return {"title": [{"plain_text": value}]}

    def rich(value):
        return {"rich_text": [{"plain_text": value}]}

    def select(value):
        return {"select": {"name": value}}

    pages = {
        "test-finances": [{
            "id": "f1",
            "properties": {
                "Movimento": title("Uber"), "Valor": {"number": 42},
                "Tipo": select("Saída"), "Categoria": select("Transporte"),
                "Pago por": select("Eu"), "Status": select("Pago"),
                "Data": {"date": {"start": "2026-08-20"}},
                "Observação": rich("corrida"),
            },
        }],
        "test-wishlist": [{
            "id": "w1",
            "properties": {
                "Item": title("Cafeteira"), "Preço estimado": {"number": 900},
                "Status": select("Quero"), "Prioridade": select("⭐ Média"),
                "Tipo": select("Casa"), "Data desejada": {"date": None},
                "Observação": rich(""), "Link": {"url": None},
            },
        }],
        "test-places": [{
            "id": "p1",
            "properties": {
                "Lugar / Experiência": title("MASP"), "Status": select("Ideia"),
                "Prioridade": select("⭐ Média"), "Tipo": select("Passeio"),
                "Data planejada": {"date": None}, "Valor estimado": {"number": None},
                "Local": rich("São Paulo"), "Descrição": rich("Museu"),
            },
        }],
        "test-calendar": [{
            "id": "c1",
            "properties": {
                "Evento": title("Cinema"), "Data": {"date": {"start": "2026-08-29"}},
                "Quem": select("Nós dois"), "Status": select("Confirmado"),
                "Tipo": select("Encontro"), "Local": rich("Shopping"),
                "Observação": rich(""),
            },
        }],
        "test-routine": [{
            "id": "r1",
            "properties": {
                "Tarefa": title("Assinar HBO"), "Categoria": select("Outro"),
                "Dia / Data": {"date": {"start": "2026-08-31"}},
                "Frequência": select("Pontual"), "Responsável": select("Eu"),
                "Status": select("A fazer"), "Observação": rich(""),
            },
        }],
    }
    monkeypatch.setattr(
        notion_readers,
        "query_data_source",
        lambda data_source_id: pages[data_source_id],
    )

    assert notion_readers.get_finances()[0].valor == 42
    assert notion_readers.get_wishlist()[0].item == "Cafeteira"
    assert notion_readers.get_places()[0].lugar == "MASP"
    assert notion_readers.get_calendar()[0].data == date(2026, 8, 29)
    assert notion_readers.get_routines()[0].responsavel == "Eu"


def test_processor_answers_query_without_creating_page(monkeypatch):
    monkeypatch.setattr(
        processor,
        "route_message",
        lambda *args, **kwargs: RouterDecision(
            destination="query", confidence=.99, reason="pergunta"
        ),
    )
    intent = QueryIntent(
        domain="financas",
        operation="total",
        period="this_month",
        transaction_type="Saída",
    )
    monkeypatch.setattr(processor, "parse_query", lambda *args: intent)
    monkeypatch.setattr(processor, "execute_query", lambda value: "Total gasto: R$ 50,00")

    def must_not_write(*args, **kwargs):
        raise AssertionError("consulta não pode criar página")

    monkeypatch.setattr(processor, "write_finance", must_not_write)
    result = processor.process_message("Quanto gastamos este mês?")
    assert result.success is True
    assert result.destination == "query"
    assert result.created_page_id is None
    assert result.summary == "Total gasto: R$ 50,00"
