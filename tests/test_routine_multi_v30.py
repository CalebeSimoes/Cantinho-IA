from datetime import date, time

import pytest

import app.action_executor as action_executor
import app.action_store as action_store
import app.ai.parsers as parsers
import app.ai.router as router
import app.processor as processor
import app.query_service as query_service
import app.routine_service as routine_service
from app.ai.action_planner import build_action_plan
from app.ai.query_parser import parse_query
from app.ai.recurrence import next_occurrence, parse_recurrence
from app.notion.readers import RoutineRecord
from app.schemas.actions import (
    AIActionPlan,
    ActionPlan,
    FinanceAction,
    PlannedAction,
)


@pytest.mark.parametrize(
    ("phrase", "frequency", "rule", "due"),
    [
        ("Lavar a louça todo dia", "Diária", "daily", date(2026, 8, 23)),
        ("Lavar banheiro toda terça", "Semanal", "weekly:1", date(2026, 8, 25)),
        ("Limpar geladeira quinzenalmente", "Quinzenal", "biweekly", date(2026, 8, 23)),
        ("Revisar contas uma vez por mês", "Mensal", "monthly:23", date(2026, 8, 23)),
        ("Tomar vitamina nos dias úteis", "Dias úteis", "weekdays", date(2026, 8, 24)),
        ("Limpar quintal no fim de semana", "Fim de semana", "weekends", date(2026, 8, 29)),
    ],
)
def test_recurrence_language_is_persistent(phrase, frequency, rule, due):
    parsed = parse_recurrence(phrase, date(2026, 8, 23))
    assert parsed.frequency == frequency
    assert parsed.rule == rule
    assert parsed.due_date == due


def test_fast_routine_removes_weekday_from_task(monkeypatch):
    monkeypatch.setattr(
        parsers,
        "now",
        lambda: type("Now", (), {"date": lambda self: date(2026, 8, 23)})(),
    )
    action = parsers.fast_routine("Lavar banheiro toda sexta")
    assert action.tarefa == "lavar banheiro"
    assert action.frequencia == "Semanal"
    assert action.recurrence_rule == "weekly:4"
    assert action.dia_data == date(2026, 8, 28)
    assert action.categoria == "Casa"


@pytest.mark.parametrize(
    ("phrase", "task"),
    [
        ("Tomar vitamina nos dias úteis", "tomar vitamina"),
        ("Limpar quintal no fim de semana", "limpar quintal"),
    ],
)
def test_recurrence_prepositions_do_not_leak_into_task(
    monkeypatch, phrase, task
):
    monkeypatch.setattr(
        parsers,
        "now",
        lambda: type("Now", (), {"date": lambda self: date(2026, 8, 23)})(),
    )
    assert parsers.fast_routine(phrase).tarefa == task


@pytest.mark.parametrize(
    ("rule", "current", "completed", "expected"),
    [
        ("daily", date(2026, 8, 23), date(2026, 8, 23), date(2026, 8, 24)),
        ("weekly:4", date(2026, 8, 28), date(2026, 8, 28), date(2026, 9, 4)),
        ("biweekly", date(2026, 8, 23), date(2026, 8, 23), date(2026, 9, 6)),
        ("monthly:31", date(2026, 8, 31), date(2026, 8, 31), date(2026, 9, 30)),
        ("weekdays", date(2026, 8, 28), date(2026, 8, 28), date(2026, 8, 31)),
        ("weekends", date(2026, 8, 29), date(2026, 8, 29), date(2026, 9, 5)),
    ],
)
def test_next_occurrence(rule, current, completed, expected):
    assert next_occurrence(rule, current, completed) == expected


@pytest.mark.parametrize(
    ("phrase", "person", "period", "status", "category"),
    [
        ("O que tenho para fazer hoje?", "Eu", "today", "Pendentes", None),
        ("O que a Carol tem pendente?", "Minha esposa", "all", "Pendentes", None),
        ("Quais tarefas da casa estão atrasadas?", None, "all", "Atrasadas", "Casa"),
    ],
)
def test_smart_routine_questions(phrase, person, period, status, category):
    parsed = parse_query(phrase, reference=date(2026, 8, 23))
    assert parsed.domain == "rotina"
    assert parsed.person == person
    assert parsed.period == period
    assert parsed.status == status
    assert parsed.category == category


def test_overdue_house_tasks_are_filtered(monkeypatch):
    records = [
        RoutineRecord("1", "Lavar banheiro", "Casa", date(2026, 8, 20), "Semanal", "Eu", "A fazer", "", "weekly:4"),
        RoutineRecord("2", "Enviar relatório", "Trabalho", date(2026, 8, 20), "Pontual", "Eu", "A fazer", ""),
        RoutineRecord("3", "Lavar louça", "Casa", date(2026, 8, 20), "Pontual", "Eu", "Concluído", ""),
        RoutineRecord("4", "Limpar quarto", "Casa", date(2026, 8, 25), "Pontual", "Eu", "A fazer", ""),
    ]
    monkeypatch.setattr(query_service.readers, "get_routines", lambda: records)
    answer = query_service.execute_query(
        parse_query(
            "Quais tarefas da casa estão atrasadas?",
            reference=date(2026, 8, 23),
        ),
        reference=date(2026, 8, 23),
    )
    assert "Lavar banheiro" in answer
    assert "Enviar relatório" not in answer
    assert "Lavar louça" not in answer
    assert "Limpar quarto" not in answer


def test_complete_one_off_routine(monkeypatch):
    updates = []
    monkeypatch.setattr(routine_service, "property_name", lambda ds, name: name)
    monkeypatch.setattr(routine_service, "optional_property_name", lambda ds, name: name)
    monkeypatch.setattr(
        routine_service,
        "update_page",
        lambda page_id, props: updates.append((page_id, props)) or {},
    )
    record = RoutineRecord(
        "r1", "lavar a louça", "Casa", date(2026, 8, 23),
        "Pontual", "Eu", "A fazer", "",
    )
    result = routine_service.complete_routine(
        "Terminei de lavar a louça",
        completed_on=date(2026, 8, 23),
        records=[record],
    )
    assert result.success is True
    assert updates[0][1]["Status"]["select"]["name"] == "Concluído"
    assert updates[0][1]["Ultima conclusao"]["date"]["start"] == "2026-08-23"


def test_complete_recurring_routine_advances_instead_of_duplicating(monkeypatch):
    updates = []
    monkeypatch.setattr(routine_service, "property_name", lambda ds, name: name)
    monkeypatch.setattr(routine_service, "optional_property_name", lambda ds, name: name)
    monkeypatch.setattr(
        routine_service,
        "update_page",
        lambda page_id, props: updates.append((page_id, props)) or {},
    )
    record = RoutineRecord(
        "r1", "lavar banheiro", "Casa", date(2026, 8, 28),
        "Semanal", "Eu", "A fazer", "", "weekly:4",
    )
    result = routine_service.complete_routine(
        "Finalizei o banheiro",
        completed_on=date(2026, 8, 28),
        records=[record],
    )
    assert result.next_date == date(2026, 9, 4)
    assert updates[0][1]["Status"]["select"]["name"] == "A fazer"
    assert updates[0][1]["Dia / Data"]["date"]["start"] == "2026-09-04"


def test_question_about_completed_tasks_is_not_a_completion_command():
    assert routine_service.is_completion_command(
        "O que foi feito hoje?"
    ) is False
    assert routine_service.is_completion_command(
        "Quais tarefas estão concluídas?"
    ) is False
    assert routine_service.is_completion_command(
        "Lavar a louça feito"
    ) is True


def test_calendar_parser_preserves_clock_time(monkeypatch):
    monkeypatch.setattr(
        parsers,
        "now",
        lambda: type("Now", (), {"date": lambda self: date(2026, 8, 23)})(),
    )
    action = parsers.fast_calendar("Marcar cinema sábado às 20h")
    assert action.data == date(2026, 8, 29)
    assert action.hora == time(20, 0)


def test_wishlist_purchase_builds_update_and_finance_actions():
    plan = build_action_plan(
        "Comprei o fone da wishlist por 350 reais",
        reference=date(2026, 8, 23),
    )
    assert isinstance(plan, ActionPlan)
    assert [(a.operation, a.destination) for a in plan.actions] == [
        ("update", "wishlist"),
        ("create", "financas"),
    ]
    assert plan.actions[1].payload["valor"] == 350


def test_reservation_builds_place_and_dated_calendar_actions():
    plan = build_action_plan(
        "Reservei o restaurante italiano para sábado às 20h",
        reference=date(2026, 8, 23),
    )
    assert [(a.operation, a.destination) for a in plan.actions] == [
        ("update", "lugares"),
        ("create", "calendario"),
    ]
    assert plan.actions[1].payload["data"] == "2026-08-29"
    assert plan.actions[1].payload["hora"] == "20:00:00"


def test_ticket_purchase_never_invents_calendar_date():
    plan = build_action_plan(
        "Compramos passagem para Campos do Jordão por 600",
        reference=date(2026, 8, 23),
    )
    assert [a.destination for a in plan.actions] == ["financas", "lugares"]
    assert all(a.destination != "calendario" for a in plan.actions)


@pytest.mark.parametrize(
    "phrase",
    [
        "Tenho que comprar pão",
        "Quero comprar uma cafeteira",
        "Comprei pão por 20 reais",
    ],
)
def test_single_intentions_do_not_become_multi_plan(phrase):
    assert build_action_plan(phrase, reference=date(2026, 8, 23)) is None


def test_processor_requires_confirmation_before_multi_write(monkeypatch):
    saved = {}
    monkeypatch.setattr(processor.action_store, "get_completed", lambda key: None)
    monkeypatch.setattr(processor.action_store, "get_pending", lambda key: None)
    monkeypatch.setattr(
        processor.action_store,
        "assign_action_ids",
        lambda plan, key: plan,
    )
    monkeypatch.setattr(
        processor.action_store,
        "save_pending",
        lambda key, message, plan: saved.update(plan=plan),
    )
    result = processor.process_message(
        "Comprei o fone da wishlist por 350 reais",
        idempotency_key="inbox-1",
    )
    assert result.status == "Precisa confirmação"
    assert result.destination == "multi"
    assert len(saved["plan"].actions) == 2
    assert "Confirmar?" in result.summary


def test_processor_executes_saved_plan_only_after_confirmation(monkeypatch):
    plan = build_action_plan(
        "Comprei o fone da wishlist por 350 reais",
        reference=date(2026, 8, 23),
    )
    monkeypatch.setattr(processor.action_store, "get_completed", lambda key: None)
    monkeypatch.setattr(
        processor.action_store,
        "get_pending",
        lambda key: {
            "message": "Comprei o fone da wishlist por 350 reais",
            "plan": plan.model_dump(mode="json"),
            "done_action_ids": [],
        },
    )
    monkeypatch.setattr(
        processor,
        "execute_plan",
        lambda *args: type(
            "Result", (), {"summary": "executado", "first_url": None}
        )(),
    )
    result = processor.process_message(
        "Comprei o fone da wishlist por 350 reais — confirmar",
        idempotency_key="inbox-1",
    )
    assert result.success is True
    assert result.status == "Processado"
    assert result.summary == "executado"


def test_action_store_persists_partial_progress_atomically(monkeypatch, tmp_path):
    monkeypatch.setattr(action_store, "STATE_DIR", tmp_path)
    monkeypatch.setattr(action_store, "STATE_FILE", tmp_path / "actions.json")
    plan = build_action_plan(
        "Comprei o fone da wishlist por 350 reais",
        reference=date(2026, 8, 23),
    )
    action_store.assign_action_ids(plan, "inbox-atomic")
    assert len({action.action_id for action in plan.actions}) == 2
    action_store.save_pending("inbox-atomic", "mensagem", plan)
    action_store.mark_action_done(
        "inbox-atomic", plan.actions[0].action_id
    )
    pending = action_store.get_pending("inbox-atomic")
    assert pending["done_action_ids"] == [plan.actions[0].action_id]
    action_store.finish("inbox-atomic", "ok")
    assert action_store.get_pending("inbox-atomic") is None
    assert action_store.get_completed("inbox-atomic") == "ok"


def test_executor_resumes_after_first_action_without_repeating(monkeypatch):
    plan = ActionPlan(actions=[
        PlannedAction(
            action_id="a1", operation="update", destination="wishlist",
            subject="Fone", payload={"status": "Comprado"},
        ),
        PlannedAction(
            action_id="a2", operation="create", destination="financas",
            subject="Fone", payload=FinanceAction(
                movimento="Fone", valor=350, tipo="Saída",
                categoria="Compras", pago_por="Eu", status="Pago",
                data=date(2026, 8, 23),
            ).model_dump(mode="json"),
        ),
    ])
    executed = []
    monkeypatch.setattr(action_executor, "_preflight", lambda plan: None)
    monkeypatch.setattr(
        action_executor,
        "_execute_action",
        lambda action: executed.append(action.action_id) or ("feito", None),
    )
    monkeypatch.setattr(action_executor.action_store, "mark_action_done", lambda *args: None)
    monkeypatch.setattr(action_executor.action_store, "finish", lambda *args: None)
    action_executor.execute_plan(plan, "inbox", done_action_ids=["a1"])
    assert executed == ["a2"]


def test_origin_marker_recovers_create_after_crash(monkeypatch):
    action = PlannedAction(
        action_id="abc", operation="create", destination="financas",
        subject="Fone", payload=FinanceAction(
            movimento="Fone", valor=350, tipo="Saída",
            categoria="Compras", pago_por="Eu", status="Pago",
            data=date(2026, 8, 23),
        ).model_dump(mode="json"),
    )
    existing = type("Record", (), {"source_key": "cantinho:abc"})()
    monkeypatch.setattr(
        action_executor.readers,
        "get_finances",
        lambda: [existing],
    )
    monkeypatch.setattr(
        action_executor,
        "write_finance",
        lambda action: pytest.fail("não pode duplicar a página"),
    )
    summary, _ = action_executor._execute_action(action)
    assert "já aplicado" in summary


@pytest.mark.parametrize(
    ("phrase", "destination"),
    [
        ("Assinei Netflix por 30 reais", "financas"),
        ("Quero assinar Netflix", "wishlist"),
        ("Tenho que assinar o seguro", "rotina"),
        ("Comprei um notebook por 2500", "financas"),
        ("Quero comprar um notebook", "wishlist"),
        ("Tenho que comprar pão", "wishlist"),
        ("Quero visitar o MASP", "lugares"),
        ("Visitar o MASP", "lugares"),
        ("Preciso visitar minha mãe", "rotina"),
        ("Ir ao dentista terça às 9h", "calendario"),
        ("Preciso fazer a declaração do imposto", "rotina"),
        ("Estou pensando em comprar uma câmera", "wishlist"),
    ],
)
def test_parser_understands_action_state_and_intention(
    monkeypatch, phrase, destination
):
    monkeypatch.setattr(
        router,
        "structured_chat",
        lambda *args, **kwargs: pytest.fail("caso deveria ser determinístico"),
    )
    assert router.route_message(phrase).destination == destination


def test_generic_purchase_keeps_object_name():
    action = parsers.fast_finance("Comprei um notebook por 2500", "Eu")
    assert action.movimento == "Notebook"
    assert action.categoria == "Compras"
    assert action.valor == 2500


def test_ollama_multi_schema_rejects_free_form_notion_labels():
    with pytest.raises(ValueError):
        AIActionPlan.model_validate({
            "actions": [
                {
                    "operation": "update",
                    "destination": "wishlist",
                    "subject": "Fone",
                    "payload": {"item": "Fone", "status": "Comprado"},
                },
                {
                    "operation": "create",
                    "destination": "financas",
                    "subject": "Fone",
                    "payload": {
                        "movimento": "Fone", "valor": 350,
                        "tipo": "compra", "categoria": "eletrônicos",
                        "pago_por": "Eu", "status": "realizado",
                        "data": "2026-08-23",
                    },
                },
            ]
        })


def test_ollama_multi_schema_accepts_exact_notion_contract():
    parsed = AIActionPlan.model_validate({
        "actions": [
            {
                "operation": "update",
                "destination": "wishlist",
                "subject": "Fone",
                "payload": {"item": "Fone", "status": "Comprado"},
            },
            {
                "operation": "create",
                "destination": "financas",
                "subject": "Fone",
                "payload": {
                    "movimento": "Fone", "valor": 350,
                    "tipo": "Saída", "categoria": "Compras",
                    "pago_por": "Eu", "status": "Pago",
                    "data": "2026-08-23",
                },
            },
        ]
    })
    assert parsed.actions[1].payload.tipo == "Saída"
