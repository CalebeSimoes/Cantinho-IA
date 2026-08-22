import argparse,time,traceback
from app.config import settings
from app.notion.inbox import pending_items,set_status
from app.processor import process_message

def process_once():
    items=pending_items()
    if not items:
        print('✨ Nenhuma anotação nova.'); return 0
    print(f'📥 {len(items)} anotação(ões) pendente(s).')
    for item in items:
        print(f'→ {item.message}')
        try:
            set_status(item.page_id,'Processando','IA local processando...')
            r=process_message(item.message,item.destination,item.author)
            set_status(item.page_id,r.status,r.summary)
            print(f'  {r.status}: {r.summary}')
        except Exception as exc:
            msg=f'{type(exc).__name__}: {exc}'
            try: set_status(item.page_id,'Erro',msg)
            except Exception: pass
            print('  ❌',msg); traceback.print_exc()
    return len(items)

def run_forever():
    print('🌿 Cantinho Ghibli Worker iniciado. CTRL+C para parar.')
    print(f'Intervalo: {settings.worker_poll_seconds}s')
    try:
        while True:
            process_once(); time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt: print('\nWorker encerrado.')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--once',action='store_true'); args=ap.parse_args()
    process_once() if args.once else run_forever()
