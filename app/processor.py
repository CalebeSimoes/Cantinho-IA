from app.ai.router import route_message
from app.ai.parsers import parse_finance,parse_wishlist,parse_place,parse_calendar,parse_routine
from app.notion.writers import write_finance,write_wishlist,write_place,write_calendar,write_routine
from app.schemas.actions import ProcessResult

def confirm(dest,parsed,missing):
    txt=', '.join(sorted(set(missing))) if missing else 'informações adicionais'
    return ProcessResult(success=False,destination=dest,status='Precisa confirmação',summary=f'Preciso de mais informação: {txt}.',parsed_data=parsed.model_dump(mode='json'))

def process_message(message,requested_destination='Automático',author='Eu'):
    d=route_message(message,requested_destination); dest=d.destination
    if dest=='desconhecido': return ProcessResult(success=False,destination=dest,status='Precisa confirmação',summary='Não consegui decidir para qual área essa anotação deve ir.',parsed_data={'router':d.model_dump()})
    if dest=='financas':
        a=parse_finance(message,author); missing=a.missing_fields+a.required_missing()
        if a.needs_confirmation or missing: return confirm(dest,a,missing)
        p=write_finance(a); summary=f'💸 Registrado em Finanças: {a.movimento} · R$ {a.valor:.2f}'
    elif dest=='wishlist':
        a=parse_wishlist(message); missing=a.missing_fields+([] if a.item else ['item'])
        if a.needs_confirmation or missing: return confirm(dest,a,missing)
        p=write_wishlist(a); summary=f'🛍️ Adicionado à Wishlist: {a.item}'+(f' · R$ {a.preco_estimado:.2f}' if a.preco_estimado else '')
    elif dest=='lugares':
        a=parse_place(message); missing=a.missing_fields+([] if a.lugar else ['lugar'])
        if a.needs_confirmation or missing: return confirm(dest,a,missing)
        p=write_place(a); summary=f'📍 Adicionado a Lugares & Experiências: {a.lugar}'
    elif dest=='calendario':
        a=parse_calendar(message); missing=a.missing_fields+([] if a.evento else ['evento'])+([] if a.data else ['data'])
        if a.needs_confirmation or missing: return confirm(dest,a,missing)
        p=write_calendar(a); summary=f'🗓️ Adicionado ao Calendário: {a.evento} · {a.data.isoformat()}'
    elif dest=='rotina':
        a=parse_routine(message); missing=a.missing_fields+([] if a.tarefa else ['tarefa'])
        if a.needs_confirmation or missing: return confirm(dest,a,missing)
        p=write_routine(a); summary=f'🌙 Adicionado à Rotina: {a.tarefa}'
    else: raise RuntimeError(f'Destino não suportado: {dest}')
    return ProcessResult(success=True,destination=dest,status='Processado',summary=summary,created_page_id=p.get('id'),created_url=p.get('url'),parsed_data=a.model_dump(mode='json'))
