from app.schemas.actions import FinanceAction, WishlistAction, PlaceAction


def test_optional_zero_values_become_none():
    assert WishlistAction(preco_estimado=0).preco_estimado is None
    assert PlaceAction(valor_estimado=-1).valor_estimado is None
    assert FinanceAction(valor="").valor is None


def test_positive_numeric_string_becomes_float():
    assert FinanceAction(valor="32.5").valor == 32.5


def test_required_missing_finance():
    a = FinanceAction()
    missing = a.required_missing()
    assert "valor" in missing
    assert "movimento" in missing
    assert "data" in missing
