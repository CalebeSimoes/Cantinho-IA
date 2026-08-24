from collections import Counter

from evals.couple_400 import CASES, EXPECTED_DISTRIBUTION
from scripts.eval_couple_ollama import build_report, corpus_hash


def test_corpus_has_exactly_400_unique_concrete_messages():
    assert len(CASES) == 400
    assert len({case["id"] for case in CASES}) == 400
    assert len({case["message"] for case in CASES}) == 400
    assert all(case["message"].strip() for case in CASES)


def test_corpus_distribution_is_stable():
    assert Counter(case["expected"] for case in CASES) == EXPECTED_DISTRIBUTION


def test_corpus_hash_is_stable_for_checkpoints():
    assert corpus_hash(CASES) == corpus_hash(list(CASES))
    changed = [dict(case) for case in CASES]
    changed[0]["message"] += " alterada"
    assert corpus_hash(changed) != corpus_hash(CASES)


def test_report_exposes_failures_and_confusions():
    state = {
        "ollama": {
            CASES[0]["id"]: {"predicted": "rotina"},
            CASES[1]["id"]: {"predicted": "financas"},
        },
        "hybrid": {},
    }
    report, markdown = build_report(CASES[:2], state, "teste")
    assert report["ollama"]["evaluated"] == 2
    assert report["ollama"]["correct"] == 1
    assert report["ollama"]["confusions"] == [
        {"expected": "financas", "predicted": "rotina", "count": 1}
    ]
    assert "FIN-001" in markdown
    assert "Nenhuma escrita no Notion" in markdown
