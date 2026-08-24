from datetime import date

import app.processor as processor
from app.schemas.actions import FinanceAction, RouterDecision


def test_unknown_route_requires_confirmation(monkeypatch):
    monkeypatch.setattr(
        processor,
        "route_message",
        lambda *args, **kwargs: RouterDecision(
            destination="desconhecido",
            confidence=0.1,
            reason="ambiguo",
        ),
    )
    r = processor.process_message("mensagem ambigua")
    assert r.success is False
    assert r.status == "Precisa confirmação"


def test_low_confidence_does_not_write(monkeypatch):
    monkeypatch.setattr(
        processor,
        "route_message",
        lambda *args, **kwargs: RouterDecision(
            destination="financas",
            confidence=0.2,
            reason="incerto",
        ),
    )

    called = {"write": False}

    def write(_):
        called["write"] = True
        return {}

    monkeypatch.setattr(processor, "write_finance", write)
    r = processor.process_message("talvez gastei algo")
    assert r.status == "Precisa confirmação"
    assert called["write"] is False


def test_missing_finance_value_does_not_write(monkeypatch):
    monkeypatch.setattr(
        processor,
        "route_message",
        lambda *args, **kwargs: RouterDecision(
            destination="financas",
            confidence=.99,
            reason="finance",
        ),
    )
    monkeypatch.setattr(
        processor,
        "parse_finance",
        lambda *args, **kwargs: FinanceAction(
            needs_confirmation=True,
            missing_fields=["valor"],
            movimento="Mercado",
            tipo="Saída",
            categoria="Alimentação",
            pago_por="Eu",
            status="Pago",
            data=date(2026, 8, 22),
        ),
    )

    called = {"write": False}
    monkeypatch.setattr(
        processor,
        "write_finance",
        lambda _: called.update(write=True),
    )

    r = processor.process_message("Paguei no mercado")
    assert r.status == "Precisa confirmação"
    assert "valor" in r.summary
    assert called["write"] is False


def test_valid_finance_writes_once(monkeypatch):
    monkeypatch.setattr(
        processor,
        "route_message",
        lambda *args, **kwargs: RouterDecision(
            destination="financas",
            confidence=.99,
            reason="finance",
        ),
    )
    action = FinanceAction(
        movimento="Uber",
        valor=32,
        tipo="Saída",
        categoria="Transporte",
        pago_por="Eu",
        status="Pago",
        data=date(2026, 8, 22),
    )
    monkeypatch.setattr(
        processor,
        "parse_finance",
        lambda *args, **kwargs: action,
    )

    calls = []

    def write(a):
        calls.append(a)
        return {"id": "page-1", "url": "https://example.test/page-1"}

    monkeypatch.setattr(processor, "write_finance", write)
    r = processor.process_message("Paguei 32 no Uber")
    assert r.success is True
    assert r.status == "Processado"
    assert len(calls) == 1
    assert r.created_page_id == "page-1"
