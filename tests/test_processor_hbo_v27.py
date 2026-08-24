from datetime import date, datetime
from zoneinfo import ZoneInfo

import app.ai.parsers as parsers
import app.processor as processor


def test_hbo_phrase_is_written_as_complete_routine(monkeypatch):
    monkeypatch.setattr(
        parsers,
        "now",
        lambda: datetime(
            2026,
            8,
            23,
            12,
            0,
            tzinfo=ZoneInfo("America/Sao_Paulo"),
        ),
    )
    captured = []
    monkeypatch.setattr(
        processor,
        "write_routine",
        lambda action: (
            captured.append(action)
            or {
                "id": "routine-page",
                "url": "https://www.notion.so/routine-page",
            }
        ),
    )

    result = processor.process_message(
        "Calebe precisa assinar HBO final do mes"
    )

    assert result.success is True
    assert result.destination == "rotina"
    assert result.status == "Processado"
    assert captured[0].tarefa == "assinar hbo"
    assert captured[0].dia_data == date(2026, 8, 31)
    assert captured[0].responsavel == "Eu"
