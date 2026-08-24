from app.ai.parsers import fast_finance


def test_finance_uber():
    a = fast_finance("Paguei 32 no Uber", "Eu")
    assert a is not None
    assert a.valor == 32.0
    assert a.categoria == "Transporte"
    assert a.movimento == "Uber"
    assert a.tipo == "Saída"
    assert a.pago_por == "Eu"
    assert a.needs_confirmation is False


def test_finance_market_br_value():
    a = fast_finance("Gastei 1.250,90 no mercado", "Eu")
    assert a.valor == 1250.9
    assert a.categoria == "Alimentação"
    assert a.movimento == "Mercado"


def test_finance_joint_payment():
    a = fast_finance("Pagamos 80 no restaurante", "Eu")
    assert a.pago_por == "Nós dois"
    assert a.categoria == "Alimentação"


def test_finance_carol_author():
    a = fast_finance("Paguei 45 na farmacia", "Carol")
    assert a.pago_por == "Minha esposa"
    assert a.categoria == "Saúde"


def test_finance_income():
    a = fast_finance("Recebi 500 de reembolso", "Eu")
    assert a.tipo == "Entrada"
    assert a.valor == 500.0


def test_finance_missing_value_requests_confirmation():
    a = fast_finance("Paguei no mercado", "Eu")
    assert a.needs_confirmation is True
    assert "valor" in a.missing_fields
    assert a.valor is None


def test_non_finance_returns_none():
    assert fast_finance("Quero conhecer um museu", "Eu") is None
