import argparse
import time
import traceback

from app.config import settings
from app.health import write_worker_heartbeat
from app.learning import record_learning_case
from app.notion.inbox import pending_items, set_author, set_status
from app.processor import process_message


def _learn_safely(item, status, destination, summary):
    if status not in {"Precisa confirmação", "Erro"}:
        return

    try:
        record_learning_case(
            message=item.message,
            status=status,
            destination=destination,
            summary=summary,
            author=item.author,
        )
    except Exception:
        # O log de aprendizado nunca pode derrubar o worker.
        traceback.print_exc()


def _persist_inferred_author_safely(item):
    if not getattr(item, "author_inferred", False):
        return
    try:
        set_author(item.page_id, item.author)
    except Exception:
        print(
            "  ⚠️ Não foi possível preencher o Autor inferido no Inbox.",
            flush=True,
        )
        traceback.print_exc()


def process_once():
    items = pending_items()
    if not items:
        print("✨ Nenhuma anotação nova.", flush=True)
        return 0

    print(f"📥 {len(items)} anotação(ões) pendente(s).", flush=True)

    for item in items:
        print(f"→ {item.message}", flush=True)
        try:
            _persist_inferred_author_safely(item)
            set_status(
                item.page_id,
                "Processando",
                "IA local processando...",
            )
            r = process_message(
                item.message,
                item.destination,
                item.author,
                idempotency_key=item.page_id,
            )
            set_status(
                item.page_id,
                r.status,
                r.summary,
                result_url=r.created_url,
            )
            _learn_safely(
                item,
                r.status,
                r.destination,
                r.summary,
            )
            print(f"  {r.status}: {r.summary}", flush=True)

        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            try:
                set_status(item.page_id, "Erro", msg)
            except Exception:
                pass

            _learn_safely(
                item,
                "Erro",
                item.destination or "desconhecido",
                msg,
            )
            print("  ❌", msg, flush=True)
            traceback.print_exc()

    return len(items)


def run_forever():
    print(
        "🌿 Cantinho Ghibli Worker iniciado. CTRL+C para parar.",
        flush=True,
    )
    print(
        f"Intervalo: {settings.worker_poll_seconds}s",
        flush=True,
    )

    consecutive_failures = 0

    try:
        while True:
            write_worker_heartbeat(
                "checking",
                consecutive_failures=consecutive_failures,
            )

            try:
                process_once()
            except Exception as exc:
                # Falhas gerais de Notion/rede nao encerram mais o processo.
                # O Watchdog recebe um heartbeat recente, mas degradado.
                consecutive_failures += 1
                write_worker_heartbeat(
                    "degraded",
                    consecutive_failures=consecutive_failures,
                    error_type=type(exc).__name__,
                )
                print(
                    f"❌ Ciclo do Worker falhou: {type(exc).__name__}: {exc}",
                    flush=True,
                )
                traceback.print_exc()
            else:
                consecutive_failures = 0
                write_worker_heartbeat("healthy")

            time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        print("\nWorker encerrado.", flush=True)
    finally:
        write_worker_heartbeat(
            "stopped",
            consecutive_failures=consecutive_failures,
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    process_once() if args.once else run_forever()
