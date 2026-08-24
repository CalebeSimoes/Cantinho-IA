"""Run the 400-message couple corpus without writing anything to Notion.

Examples:
    python scripts/eval_couple_ollama.py --mode ollama --run-name baseline
    python scripts/eval_couple_ollama.py --mode all --run-name after-fixes

Results and resumable checkpoints are stored below ``logs/evals`` by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter
from contextlib import nullcontext
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from unittest.mock import patch

from ollama import Client
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai.action_planner import _looks_multi, build_action_plan  # noqa: E402
from app.config import settings  # noqa: E402
from app.ai.router import route_message  # noqa: E402
from app.schemas.actions import RouterDecision  # noqa: E402
from evals.couple_400 import CASES, EvalCase  # noqa: E402


Destination = Literal[
    "query",
    "financas",
    "wishlist",
    "lugares",
    "calendario",
    "rotina",
    "multi",
    "desconhecido",
]


class EvalBatch(BaseModel):
    labels: list[Literal["Q", "F", "W", "L", "C", "R", "M", "D"]] = Field(
        min_length=1, max_length=20
    )


EVAL_PROMPT = """
Voce avalia o roteador de um segundo cerebro de casal. Classifique CADA mensagem
em exatamente um destino e preserve o id recebido.

- query: pergunta ou pedido de consulta; nunca cria nem altera dado.
- financas: dinheiro que ja entrou, saiu, foi pago ou gasto.
- wishlist: produto, servico ou assinatura que ainda sera comprado/contratado.
- lugares: vontade de conhecer lugar, restaurante, cidade ou passeio, sem evento confirmado.
- calendario: compromisso ou evento em data/horario, normalmente com outra pessoa.
- rotina: tarefa, lembrete, habito, lazer a fazer ou responsabilidade domestica.
- multi: duas ou mais acoes independentes que precisam virar registros separados.
- desconhecido: fragmento sem intencao operacional, comentario, negacao ou pedido insuficiente.

Regras criticas:
- "comprar X ate DATA/VALOR" continua wishlist; prazo e teto nao transformam compra em rotina.
- "assistir serie no fim de semana" e rotina; nao e evento social confirmado.
- Perguntas continuam query mesmo quando citam dinheiro, tarefas ou compras.
- Verbo no passado com valor pago/gasto e financas.
- Se a mensagem mandar nao registrar, use desconhecido.
- Use multi somente quando ha pelo menos duas acoes reais separaveis, nao por haver muitos detalhes.
Para economizar processamento, devolva somente um codigo por mensagem, na mesma ordem:
Q=query, F=financas, W=wishlist, L=lugares, C=calendario, R=rotina,
M=multi, D=desconhecido.
Responda com um objeto JSON contendo apenas a chave "labels" e a lista de codigos.
""".strip()

LABELS: dict[str, Destination] = {
    "Q": "query",
    "F": "financas",
    "W": "wishlist",
    "L": "lugares",
    "C": "calendario",
    "R": "rotina",
    "M": "multi",
    "D": "desconhecido",
}

# Hash do primeiro baseline de 400 casos, anterior ao hash ignorar o gabarito.
KNOWN_LEGACY_HASHES = {"1119116418ee0d43"}


def corpus_hash(cases: list[EvalCase]) -> str:
    model_inputs = [
        {key: case[key] for key in ("id", "message", "author")} for case in cases
    ]
    payload = json.dumps(model_inputs, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _legacy_corpus_hash(cases: list[EvalCase]) -> str:
    payload = json.dumps(cases, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _load_checkpoint(path: Path, cases: list[EvalCase]) -> dict:
    expected_hash = corpus_hash(cases)
    if not path.exists():
        return {"corpus_hash": expected_hash, "ollama": {}, "hybrid": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("corpus_hash") not in {
        expected_hash,
        _legacy_corpus_hash(cases),
        *KNOWN_LEGACY_HASHES,
    }:
        raise RuntimeError(
            f"Checkpoint {path} pertence a outra versao do corpus. Use --reset."
        )
    data["corpus_hash"] = expected_hash
    data.setdefault("ollama", {})
    data.setdefault("hybrid", {})
    return data


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))


def _ollama_batch(cases: list[EvalCase]) -> list[dict]:
    started = time.perf_counter()
    prompt_cases = [
        {"author": case["author"], "message": case["message"]} for case in cases
    ]
    client = Client(host=settings.ollama_host, timeout=300)
    last_error: Exception | None = None
    response: EvalBatch | None = None
    for attempt in range(2):
        repair = (
            f"\nA resposta anterior foi invalida. Retorne exatamente {len(cases)} codigos."
            if attempt
            else ""
        )
        try:
            raw = client.chat(
                model=settings.ollama_model,
                messages=[
                    {"role": "system", "content": EVAL_PROMPT},
                    {
                        "role": "user",
                        "content": "Mensagens:\n"
                        + f"TOTAL OBRIGATORIO DE LABELS: {len(cases)}\n"
                        + json.dumps(prompt_cases, ensure_ascii=False)
                        + repair,
                    },
                ],
                format="json",
                think=False,
                keep_alive="30m",
                options={
                    "temperature": 0,
                    "top_p": 0.2,
                    "seed": 7,
                    "num_ctx": 4096,
                    "num_predict": 500,
                },
            )
            candidate = EvalBatch.model_validate_json(raw.message.content)
            if len(candidate.labels) != len(cases):
                raise ValueError(
                    f"esperava {len(cases)} labels, recebeu {len(candidate.labels)}"
                )
            response = candidate
            break
        except Exception as exc:
            last_error = exc
    if response is None:
        raise RuntimeError(f"Ollama nao devolveu JSON valido: {last_error}")
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    per_case_ms = round(elapsed_ms / len(cases))
    return [
        {
            "predicted": LABELS[label],
            "duration_ms_share": per_case_ms,
        }
        for case, label in zip(cases, response.labels, strict=True)
    ]


def evaluate_ollama(
    cases: list[EvalCase],
    results: dict,
    checkpoint: Path,
    batch_size: int,
) -> None:
    def resilient_batch(batch: list[EvalCase]) -> list[dict]:
        try:
            return _ollama_batch(batch)
        except Exception as exc:
            if len(batch) == 1:
                return [{"error": str(exc), "predicted": "erro"}]
            middle = len(batch) // 2
            print(
                f"[ollama] lote de {len(batch)} invalido; dividindo em "
                f"{middle}+{len(batch) - middle}: {exc}",
                flush=True,
            )
            return resilient_batch(batch[:middle]) + resilient_batch(batch[middle:])

    pending = [case for case in cases if case["id"] not in results]
    random.Random(7331).shuffle(pending)
    total_batches = (len(pending) + batch_size - 1) // batch_size
    for batch_number, offset in enumerate(range(0, len(pending), batch_size), 1):
        batch = pending[offset : offset + batch_size]
        predictions = resilient_batch(batch)

        for case, prediction in zip(batch, predictions, strict=True):
            results[case["id"]] = prediction
        _save_json(checkpoint, STATE)
        correct = sum(
            results[case["id"]].get("predicted") == case["expected"]
            for case in cases
            if case["id"] in results
        )
        done = sum(case["id"] in results for case in cases)
        print(
            f"[ollama] lote {batch_number}/{total_batches}: {done}/{len(cases)}; "
            f"acertos parciais={correct}/{done}",
            flush=True,
        )


def evaluate_hybrid(
    cases: list[EvalCase],
    results: dict,
    checkpoint: Path,
    ollama_results: dict,
    replay_model: bool,
) -> None:
    for number, case in enumerate(cases, 1):
        if case["id"] in results:
            continue
        started = time.perf_counter()
        try:
            if replay_model:
                plan = None
                looks_multi = _looks_multi(case["message"])
            else:
                plan = build_action_plan(
                    case["message"],
                    author=case["author"],
                    reference=date(2026, 8, 24),
                )
                looks_multi = plan is not None and len(plan.actions) >= 2
            if looks_multi:
                predicted = "multi"
                reason = (
                    "sinais deterministas de multiplos destinos"
                    if replay_model
                    else f"plano com {len(plan.actions)} acoes"
                )
            else:
                if replay_model:
                    raw_destination = ollama_results.get(case["id"], {}).get(
                        "predicted", "desconhecido"
                    )
                    if raw_destination in {"multi", "erro"}:
                        raw_destination = "desconhecido"
                    replay_decision = RouterDecision(
                        destination=raw_destination,
                        confidence=0.5,
                        reason="decisao Ollama reutilizada do baseline",
                    )
                    router_context = patch(
                        "app.ai.router.structured_chat", return_value=replay_decision
                    )
                else:
                    router_context = nullcontext()
                with router_context:
                    decision = route_message(case["message"])
                predicted = decision.destination
                reason = decision.reason
            results[case["id"]] = {
                "predicted": predicted,
                "reason": reason,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            }
        except Exception as exc:  # keep the remaining corpus running
            results[case["id"]] = {"predicted": "erro", "error": str(exc)}
        _save_json(checkpoint, STATE)
        if number % 20 == 0 or number == len(cases):
            done = sum(case["id"] in results for case in cases)
            correct = sum(
                results[case["id"]].get("predicted") == case["expected"]
                for case in cases
                if case["id"] in results
            )
            print(
                f"[hibrido] {done}/{len(cases)}; acertos parciais={correct}/{done}",
                flush=True,
            )


def _summary(cases: list[EvalCase], results: dict) -> dict:
    evaluated = [case for case in cases if case["id"] in results]
    failures = [
        {
            **case,
            **results[case["id"]],
        }
        for case in evaluated
        if results[case["id"]].get("predicted") != case["expected"]
    ]
    per_destination = {}
    for destination in sorted({case["expected"] for case in cases}):
        group = [case for case in evaluated if case["expected"] == destination]
        correct = sum(
            results[case["id"]].get("predicted") == destination for case in group
        )
        per_destination[destination] = {
            "correct": correct,
            "total": len(group),
            "accuracy": round(correct / len(group), 4) if group else 0,
        }
    confusions = Counter(
        (failure["expected"], failure.get("predicted", "erro"))
        for failure in failures
    )
    return {
        "evaluated": len(evaluated),
        "correct": len(evaluated) - len(failures),
        "accuracy": round((len(evaluated) - len(failures)) / len(evaluated), 4)
        if evaluated
        else 0,
        "per_destination": per_destination,
        "confusions": [
            {"expected": expected, "predicted": predicted, "count": count}
            for (expected, predicted), count in confusions.most_common()
        ],
        "failures": failures,
    }


def build_report(cases: list[EvalCase], state: dict, run_name: str) -> tuple[dict, str]:
    report = {
        "run_name": run_name,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "corpus_hash": corpus_hash(cases),
        "corpus_size": len(cases),
        "ollama": _summary(cases, state["ollama"]),
        "hybrid": _summary(cases, state["hybrid"]),
    }
    lines = [
        f"# Avaliacao do casal — {run_name}",
        "",
        f"Corpus: {len(cases)} mensagens. Nenhuma escrita no Notion.",
        "",
    ]
    for mode, label in (("ollama", "Ollama puro"), ("hybrid", "Fluxo hibrido")):
        summary = report[mode]
        lines.extend(
            [
                f"## {label}",
                "",
                f"- Resultado: {summary['correct']}/{summary['evaluated']} "
                f"({summary['accuracy'] * 100:.1f}%).",
            ]
        )
        for destination, metrics in summary["per_destination"].items():
            lines.append(
                f"- {destination}: {metrics['correct']}/{metrics['total']} "
                f"({metrics['accuracy'] * 100:.1f}%)."
            )
        if summary["confusions"]:
            lines.append("- Confusoes mais frequentes:")
            for confusion in summary["confusions"][:10]:
                lines.append(
                    f"  - {confusion['expected']} -> {confusion['predicted']}: "
                    f"{confusion['count']}"
                )
        lines.extend(["", "### Primeiras falhas", ""])
        if not summary["failures"]:
            lines.append("Nenhuma falha.")
        for failure in summary["failures"][:30]:
            lines.append(
                f"- `{failure['id']}` esperava **{failure['expected']}**, recebeu "
                f"**{failure.get('predicted', 'erro')}**: {failure['message']}"
            )
        lines.append("")
    return report, "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("ollama", "hybrid", "all"), default="all")
    parser.add_argument("--run-name", default="manual")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--reset-hybrid", action="store_true")
    parser.add_argument(
        "--hybrid-model", choices=("replay", "live"), default="replay"
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "logs" / "evals")
    return parser.parse_args()


STATE: dict = {}


def main() -> int:
    global STATE
    args = parse_args()
    if args.batch_size < 1 or args.batch_size > 20:
        raise SystemExit("--batch-size precisa estar entre 1 e 20")
    cases = CASES[: max(1, min(args.limit, len(CASES)))]
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in args.run_name)
    checkpoint = args.output_dir / f"{safe_name}-checkpoint.json"
    if args.reset and checkpoint.exists():
        checkpoint.unlink()
    STATE = _load_checkpoint(checkpoint, cases)
    STATE["run_name"] = args.run_name
    if args.reset_hybrid:
        STATE["hybrid"] = {}

    if args.mode in {"ollama", "all"}:
        evaluate_ollama(cases, STATE["ollama"], checkpoint, args.batch_size)
    if args.mode in {"hybrid", "all"}:
        if args.hybrid_model == "replay" and len(STATE["ollama"]) < len(cases):
            raise SystemExit("O modo replay exige o baseline Ollama completo no checkpoint")
        evaluate_hybrid(
            cases,
            STATE["hybrid"],
            checkpoint,
            STATE["ollama"],
            replay_model=args.hybrid_model == "replay",
        )

    report, markdown = build_report(cases, STATE, args.run_name)
    json_path = args.output_dir / f"{safe_name}-report.json"
    markdown_path = args.output_dir / f"{safe_name}-report.md"
    _save_json(json_path, report)
    markdown_path.write_text(markdown, encoding="utf-8")
    print(f"Relatorio JSON: {json_path}")
    print(f"Relatorio Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
