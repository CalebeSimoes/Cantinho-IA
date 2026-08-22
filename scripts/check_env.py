from app.config import settings
print('Modelo:',settings.ollama_model)
print('Token Notion:','OK' if settings.notion_token!='COLE_SEU_TOKEN_NOTION_AQUI' else 'NÃO CONFIGURADO')
print('Inbox:',settings.notion_inbox_data_source_id)
print('Worker poll:',settings.worker_poll_seconds,'s')
