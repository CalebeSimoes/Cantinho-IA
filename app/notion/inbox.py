from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from app.config import settings
from app.notion.client import query_data_source,select_value,title_value,update_page

@dataclass
class InboxItem:
    page_id:str; message:str; destination:str; author:str

def pending_items():
    filt={'or':[{'property':'Status','select':{'equals':'Novo'}},{'property':'Status','select':{'is_empty':True}}]}
    pages=query_data_source(settings.notion_inbox_data_source_id,filter_body=filt,sorts=[{'timestamp':'created_time','direction':'ascending'}])
    out=[]
    for p in pages:
        props=p.get('properties',{}); msg=title_value(props.get('Mensagem'))
        if msg: out.append(InboxItem(p['id'],msg,select_value(props.get('Destino')) or 'Automático',select_value(props.get('Autor')) or 'Eu'))
    return out

def set_status(page_id,status,result=None):
    props={'Status':{'select':{'name':status}}}
    if result is not None: props['Resultado']={'rich_text':[{'type':'text','text':{'content':result[:2000]}}]}
    if status in {'Processado','Precisa confirmação','Erro'}:
        props['Processado em']={'date':{'start':datetime.now(ZoneInfo(settings.app_timezone)).isoformat()}}
    update_page(page_id,props)
