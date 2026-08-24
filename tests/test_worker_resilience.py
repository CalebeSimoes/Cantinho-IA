import app.worker as worker
from app.schemas.actions import ProcessResult


def test_worker_keeps_health_history_when_cycle_fails(monkeypatch):
    heartbeats = []

    def fail_cycle():
        raise TimeoutError("notion indisponivel")

    def stop_after_cycle(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(worker, "process_once", fail_cycle)
    monkeypatch.setattr(worker.time, "sleep", stop_after_cycle)
    monkeypatch.setattr(
        worker,
        "write_worker_heartbeat",
        lambda state, **data: heartbeats.append((state, data)),
    )

    worker.run_forever()

    assert [state for state, _ in heartbeats] == [
        "checking",
        "degraded",
        "stopped",
    ]
    assert heartbeats[1][1]["consecutive_failures"] == 1
    assert heartbeats[1][1]["error_type"] == "TimeoutError"


def test_worker_sends_created_url_to_mobile_result(monkeypatch):
    item = type(
        "Item",
        (),
        {
            "page_id": "inbox-page",
            "message": "Paguei 25 reais no Uber",
            "destination": "Automático",
            "author": "Eu",
        },
    )()
    updates = []

    monkeypatch.setattr(worker, "pending_items", lambda: [item])
    monkeypatch.setattr(
        worker,
        "process_message",
        lambda *args, **kwargs: ProcessResult(
            success=True,
            destination="financas",
            status="Processado",
            summary="Registrado em Finanças",
            created_page_id="created-page",
            created_url="https://www.notion.so/created-page",
        ),
    )
    monkeypatch.setattr(
        worker,
        "set_status",
        lambda *args, **kwargs: updates.append((args, kwargs)),
    )
    monkeypatch.setattr(worker, "_learn_safely", lambda *args: None)

    assert worker.process_once() == 1
    assert updates[-1][0] == (
        "inbox-page",
        "Processado",
        "Registrado em Finanças",
    )
    assert updates[-1][1]["result_url"] == (
        "https://www.notion.so/created-page"
    )
