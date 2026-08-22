import httpx

from app.config import settings
from app.notion.client import NOTION_BASE_URL, notion_headers
from app.schemas.actions import FinanceAction


def create_finance_page(action: FinanceAction) -> dict:
    missing = action.required_missing()
    if missing:
        raise ValueError("Registro incompleto. Campos ausentes: " + ", ".join(missing))

    properties = {
        "Movimento": {
            "title": [
                {
                    "type": "text",
                    "text": {"content": action.movimento},
                }
            ]
        },
        "Categoria": {"select": {"name": action.categoria}},
        "Valor": {"number": action.valor},
        "Tipo": {"select": {"name": action.tipo}},
        "Pago por": {"select": {"name": action.pago_por}},
        "Status": {"select": {"name": action.status}},
        "Data": {"date": {"start": action.data.isoformat()}},
        "Observação": {
            "rich_text": (
                [
                    {
                        "type": "text",
                        "text": {"content": action.observacao[:2000]},
                    }
                ]
                if action.observacao
                else []
            )
        },
    }

    payload = {
        "parent": {
            "type": "data_source_id",
            "data_source_id": settings.notion_finances_data_source_id,
        },
        "properties": properties,
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{NOTION_BASE_URL}/pages",
            headers=notion_headers(),
            json=payload,
        )

    if response.is_error:
        raise RuntimeError(f"Notion {response.status_code}: {response.text}")

    return response.json()
