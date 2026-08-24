from types import SimpleNamespace

import pytest

import app.ai.ollama_client as oc
from app.schemas.actions import RouterDecision


class FakeClient:
    responses = []
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    def chat(self, *args, **kwargs):
        type(self).calls += 1
        content = type(self).responses.pop(0)
        return SimpleNamespace(
            message=SimpleNamespace(content=content)
        )


def test_invalid_structured_response_is_retried(monkeypatch):
    FakeClient.responses = [
        "nao e json",
        '{"destination":"financas","confidence":0.9,"reason":"ok"}',
    ]
    FakeClient.calls = 0
    monkeypatch.setattr(oc, "Client", FakeClient)
    monkeypatch.setattr(oc.time, "sleep", lambda *_: None)

    result = oc.structured_chat(
        RouterDecision,
        "classifique",
        "Paguei 20 no Uber",
    )

    assert result.destination == "financas"
    assert FakeClient.calls == 2


def test_two_invalid_responses_raise_clear_error(monkeypatch):
    FakeClient.responses = ["invalido", "tambem invalido"]
    FakeClient.calls = 0
    monkeypatch.setattr(oc, "Client", FakeClient)
    monkeypatch.setattr(oc.time, "sleep", lambda *_: None)

    with pytest.raises(RuntimeError, match="resposta estruturada valida"):
        oc.structured_chat(
            RouterDecision,
            "classifique",
            "mensagem",
        )

    assert FakeClient.calls == 2
