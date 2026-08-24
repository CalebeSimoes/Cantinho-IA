import json

from app.learning import record_learning_case


def test_learning_case_is_jsonl(tmp_path):
    path = tmp_path / "learning.jsonl"
    record_learning_case(
        message="dei 80 conto no atacadao",
        status="Precisa confirmação",
        destination="financas",
        summary="valor incerto",
        author="Eu",
        log_path=path,
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["message"] == "dei 80 conto no atacadao"
    assert data["destination"] == "financas"
    assert data["status"] == "Precisa confirmação"
