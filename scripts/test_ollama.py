from ollama import Client
from app.config import settings
r=Client(host=settings.ollama_host,timeout=60).chat(model=settings.ollama_model,messages=[{'role':'user','content':'Responda somente OK.'}],think=False,options={'temperature':0,'num_predict':10})
print('Resposta:',r.message.content)
