import argparse
import sys
import time
import traceback

from app.config import settings
from app.health import write_worker_heartbeat
from app.learning import record_learning_case
from app.notion.inbox import (
    pending_items,
    set_author,
    set_status,
    stable_items,
)
from app.processor import process_message
from app.radar import preview_radar, run_daily_radar


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


def process_once(*, stabilize: bool = False):
    pending = pending_items()
    items = stable_items(pending) if stabilize else pending
    if not items:
        if pending:
            print(
                "⌛ Anotação nova aguardando o fim da digitação.",
                flush=True,
            )
        else:
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


def _run_radar_safely(*, force: bool = False):
    try:
        result = run_daily_radar(force=force)
    except Exception as exc:
        print(
            f"⚠️ Radar falhou sem interromper o Worker: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        traceback.print_exc()
        return None

    if result.status == "sent":
        print(
            f"🌿 Radar enviado com {len(result.alerts)} alerta(s).",
            flush=True,
        )
    elif result.status == "empty":
        print("🌿 Radar verificado: nada acionável hoje.", flush=True)
    elif result.status == "suppressed":
        print("🌿 Radar idêntico recente: envio suprimido.", flush=True)
    elif result.status == "failed":
        print(f"⚠️ Radar não enviado: {result.reason}", flush=True)
    return result


def run_forever():
    print(
        "🌿 Cantinho Ghibli Worker iniciado. CTRL+C para parar.",
        flush=True,
    )
    print(
        f"Intervalo: {settings.worker_poll_seconds}s",
        flush=True,
    )
    if settings.radar_enabled:
        print(
            f"Radar diário: {settings.radar_hour:02d}:"
            f"{settings.radar_minute:02d}",
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
                process_once(stabilize=True)
                _run_radar_safely()
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--radar-now", action="store_true")
    ap.add_argument("--radar-preview", action="store_true")
    args = ap.parse_args()
    if args.radar_preview:
        preview = preview_radar()
        print(preview.message or "🌿 Radar: nada acionável.", flush=True)
    elif args.radar_now:
        _run_radar_safely(force=True)
    elif args.once:
        process_once()
    else:
        run_forever()
