from app.config import settings
from app.notion.client import get_data_source
for name,ds in {'Inbox':settings.notion_inbox_data_source_id,'Finanças':settings.notion_finances_data_source_id,'Wishlist':settings.notion_wishlist_data_source_id,'Lugares':settings.notion_places_data_source_id,'Calendário':settings.notion_calendar_data_source_id,'Rotina':settings.notion_routine_data_source_id}.items():
    print('Testando',name,'...'); print(' OK:',get_data_source(ds).get('id'))
