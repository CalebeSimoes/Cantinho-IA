from app.notion import inbox


def test_processed_result_has_clickable_destination(monkeypatch):
    updates = []
    monkeypatch.setattr(
        inbox,
        "update_page",
        lambda page_id, properties: updates.append(
            (page_id, properties)
        ),
    )

    inbox.set_status(
        "inbox-page",
        "Processado",
        "Registrado em Finanças",
        result_url="https://www.notion.so/registro-123",
    )

    page_id, properties = updates[0]
    result_parts = properties["Resultado"]["rich_text"]

    assert page_id == "inbox-page"
    assert result_parts[0]["text"]["content"] == (
        "Registrado em Finanças"
    )
    assert result_parts[1]["text"]["content"].endswith(
        inbox.RESULT_LINK_LABEL
    )
    assert result_parts[1]["text"]["link"]["url"] == (
        "https://www.notion.so/registro-123"
    )
    assert "Processado em" in properties


def test_result_ignores_unsafe_link_scheme():
    result = inbox._result_value(
        "Falha de exemplo",
        "javascript:alert(1)",
    )

    assert len(result["rich_text"]) == 1
    assert "link" not in result["rich_text"][0]["text"]
