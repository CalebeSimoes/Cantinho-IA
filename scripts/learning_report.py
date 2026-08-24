import argparse
import json
from collections import Counter
from pathlib import Path


DEFAULT = Path("logs") / "learning_cases.jsonl"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--file", default=str(DEFAULT))
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print("Nenhum caso de aprendizado registrado ainda.")
        return

    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not cases:
        print("Nenhum caso valido encontrado.")
        return

    print(f"Casos registrados: {len(cases)}")
    print("Por status:", dict(Counter(c["status"] for c in cases)))
    print("Por destino:", dict(Counter(c["destination"] for c in cases)))
    print("\nMais recentes:")

    for case in cases[-args.limit:]:
        print(
            f"- [{case['status']}] {case['message']} "
            f"-> {case['destination']} | {case['summary']}"
        )


if __name__ == "__main__":
    main()
