from datetime import date, time
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Destination = Literal[
    "multi",
    "query",
    "financas",
    "wishlist",
    "lugares",
    "calendario",
    "rotina",
    "desconhecido",
]
RouterDestination = Literal[
    "query",
    "financas",
    "wishlist",
    "lugares",
    "calendario",
    "rotina",
    "desconhecido",
]

QueryDomain = Literal[
    "financas",
    "wishlist",
    "lugares",
    "calendario",
    "rotina",
    "desconhecido",
]
QueryOperation = Literal["total", "list", "max", "count", "summary"]
QueryPeriod = Literal[
    "all",
    "today",
    "this_week",
    "this_month",
    "last_month",
    "next_month",
    "specific_date",
]


def _optional_positive_number(value: Any) -> float | None:
    """
    Modelos locais às vezes devolvem 0 para representar "não informado".
    Para campos opcionais, normalizamos 0/negativos/strings vazias para None.
    """
    if value is None or value == "":
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if number > 0 else None


class RouterDecision(BaseModel):
    destination: RouterDestination
    confidence: float = Field(default=0, ge=0, le=1)
    reason: str = ""


class QueryIntent(BaseModel):
    """Plano estruturado e somente-leitura para uma pergunta."""

    needs_confirmation: bool = False
    missing_fields: list[str] = Field(default_factory=list)

    domain: QueryDomain = "desconhecido"
    operation: QueryOperation = "list"
    period: QueryPeriod = "all"
    specific_date: date | None = None
    person: Literal["Eu", "Minha esposa", "Nós dois"] | None = None
    term: str | None = None
    status: str | None = None
    category: str | None = None
    transaction_type: Literal["Entrada", "Saída"] | None = None
    reason: str = ""


class FinanceAction(BaseModel):
    needs_confirmation: bool = False
    missing_fields: list[str] = Field(default_factory=list)

    movimento: str | None = None
    valor: float | None = None
    tipo: Literal["Entrada", "Saída"] | None = None
    categoria: Literal[
        "Moradia",
        "Alimentação",
        "Transporte",
        "Lazer",
        "Compras",
        "Saúde",
        "Viagem",
        "Outros",
    ] | None = None
    pago_por: Literal["Eu", "Minha esposa", "Nós dois"] | None = None
    status: Literal["Pago", "Pendente"] | None = None
    data: date | None = None
    observacao: str = ""
    source_key: str = ""

    @field_validator("valor", mode="before")
    @classmethod
    def normalize_valor(cls, value):
        return _optional_positive_number(value)

    def required_missing(self):
        data = {
            "movimento": self.movimento,
            "valor": self.valor,
            "tipo": self.tipo,
            "categoria": self.categoria,
            "pago_por": self.pago_por,
            "status": self.status,
            "data": self.data,
        }
        return [key for key, value in data.items() if value is None]


class WishlistAction(BaseModel):
    needs_confirmation: bool = False
    missing_fields: list[str] = Field(default_factory=list)

    item: str | None = None
    data_desejada: date | None = None
    link: str | None = None
    observacao: str = ""
    preco_estimado: float | None = None
    preco_relacao: Literal[
        "Máximo",
        "Aproximado",
        "Exato",
        "Mínimo",
    ] | None = None
    responsavel: Literal[
        "Eu",
        "Minha esposa",
        "Nós dois",
    ] | None = None
    source_key: str = ""

    prioridade: Literal["🔥 Alta", "⭐ Média", "🌱 Baixa"] = "⭐ Média"
    status: Literal["Quero", "Planejando", "Comprado", "Desistimos"] = "Quero"
    tipo: Literal[
        "Item",
        "Presente",
        "Casa",
        "Tecnologia",
        "Roupa",
        "Outro",
    ] = "Item"

    @field_validator("preco_estimado", mode="before")
    @classmethod
    def normalize_preco(cls, value):
        return _optional_positive_number(value)


class PlaceAction(BaseModel):
    needs_confirmation: bool = False
    missing_fields: list[str] = Field(default_factory=list)

    lugar: str | None = None
    data_planejada: date | None = None
    descricao: str = ""
    link: str | None = None
    local: str = ""
    source_key: str = ""

    prioridade: Literal["🔥 Alta", "⭐ Média", "🌱 Baixa"] = "⭐ Média"
    status: Literal["Ideia", "Planejando", "Reservado", "Feito"] = "Ideia"
    tipo: Literal[
        "Restaurante",
        "Viagem",
        "Passeio",
        "Show",
        "Hotel",
        "Outro",
    ] = "Outro"

    valor_estimado: float | None = None

    @field_validator("valor_estimado", mode="before")
    @classmethod
    def normalize_valor_estimado(cls, value):
        return _optional_positive_number(value)


class CalendarAction(BaseModel):
    needs_confirmation: bool = False
    missing_fields: list[str] = Field(default_factory=list)

    evento: str | None = None
    data: date | None = None
    hora: time | None = None
    local: str = ""
    observacao: str = ""
    source_key: str = ""

    quem: Literal["Eu", "Minha esposa", "Nós dois"] = "Nós dois"
    status: Literal["Planejado", "Confirmado", "Concluído"] = "Planejado"
    tipo: Literal[
        "Encontro",
        "Compromisso",
        "Viagem",
        "Aniversário",
        "Casa",
        "Outro",
    ] = "Outro"


class RoutineAction(BaseModel):
    needs_confirmation: bool = False
    missing_fields: list[str] = Field(default_factory=list)

    tarefa: str | None = None
    categoria: Literal[
        "Casa",
        "Saúde",
        "Estudo",
        "Trabalho",
        "Relacionamento",
        "Lazer",
        "Outro",
    ] = "Outro"
    dia_data: date | None = None
    frequencia: Literal[
        "Diária",
        "Semanal",
        "Quinzenal",
        "Mensal",
        "Dias úteis",
        "Fim de semana",
        "Pontual",
    ] = "Pontual"
    recurrence_rule: str = "once"
    observacao: str = ""
    source_key: str = ""
    responsavel: Literal["Eu", "Minha esposa", "Nós dois"] = "Nós dois"
    solicitado_por: Literal["Eu", "Minha esposa"] = "Eu"
    status: Literal["A fazer", "Em andamento", "Concluído"] = "A fazer"


class PlannedAction(BaseModel):
    """Uma etapa validável de um plano com múltiplos efeitos."""

    action_id: str = ""
    operation: Literal["create", "update", "complete"]
    destination: Literal[
        "financas",
        "wishlist",
        "lugares",
        "calendario",
        "rotina",
    ]
    subject: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sensitive: bool = True
    reason: str = ""


class ActionPlan(BaseModel):
    actions: list[PlannedAction] = Field(min_length=2, max_length=10)
    requires_confirmation: bool = True
    reason: str = ""


class AIPlanActionBase(BaseModel):
    subject: str
    sensitive: bool = True
    reason: str = ""


class AIFinancePlanAction(AIPlanActionBase):
    operation: Literal["create"]
    destination: Literal["financas"]
    payload: FinanceAction


class AIWishlistPlanAction(AIPlanActionBase):
    operation: Literal["create", "update"]
    destination: Literal["wishlist"]
    payload: WishlistAction


class AIPlacePlanAction(AIPlanActionBase):
    operation: Literal["create", "update"]
    destination: Literal["lugares"]
    payload: PlaceAction


class AICalendarPlanAction(AIPlanActionBase):
    operation: Literal["create"]
    destination: Literal["calendario"]
    payload: CalendarAction


class AIRoutinePlanAction(AIPlanActionBase):
    operation: Literal["create", "complete"]
    destination: Literal["rotina"]
    payload: RoutineAction


class AIActionPlan(BaseModel):
    actions: list[
        AIFinancePlanAction
        | AIWishlistPlanAction
        | AIPlacePlanAction
        | AICalendarPlanAction
        | AIRoutinePlanAction
    ] = Field(min_length=2, max_length=10)
    requires_confirmation: bool = True
    reason: str = ""


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    destino: Literal[
        "Automático",
        "Finanças",
        "Wishlist",
        "Lugares",
        "Calendário",
        "Rotina",
    ] = "Automático"
    autor: Literal["Eu", "Carol"] = "Eu"


class ProcessResult(BaseModel):
    success: bool
    destination: Destination
    status: Literal["Processado", "Precisa confirmação", "Erro"]
    summary: str
    created_page_id: str | None = None
    created_url: str | None = None
    parsed_data: dict | None = None
