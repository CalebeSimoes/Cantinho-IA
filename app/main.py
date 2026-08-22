from fastapi import FastAPI,HTTPException
from app.processor import process_message
from app.schemas.actions import MessageRequest,ProcessResult
app=FastAPI(title='🌿 Cantinho Ghibli AI v2',version='2.0.0',description='Notion Inbox + Router + Ollama local + 5 áreas')
@app.get('/')
def root(): return {'app':'Cantinho Ghibli AI','version':'2.0.0','docs':'/docs'}
@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/mensagem',response_model=ProcessResult)
def mensagem(req:MessageRequest):
    try: return process_message(req.message,req.destino,req.autor)
    except Exception as exc: raise HTTPException(status_code=500,detail=f'Falha ao processar: {exc}') from exc
