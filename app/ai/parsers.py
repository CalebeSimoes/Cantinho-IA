import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai.ollama_client import structured_chat
from app.ai.prompts import (
    FINANCE_PROMPT,
    WISHLIST_PROMPT,
    PLACE_PROMPT,
    CALENDAR_PROMPT,
    ROUTINE_PROMPT,
)
from app.config import settings
from app.schemas.actions import (
    FinanceAction,
    WishlistAction,
    PlaceAction,
    CalendarAction,
    RoutineAction,
)


def now():
    return datetime.now(ZoneInfo(settings.app_timezone))


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).strip().lower()


def _to_float(raw: str) -> float:
    """
    Converte formatos monetarios comuns no Brasil para float.

    1.250,90 -> 1250.90
    2.500    -> 2500.00
    32,50    -> 32.50
    25.50    -> 25.50
    3500     -> 3500.00
    """
    raw = raw.strip().lower()
    raw = raw.replace("r$", "").replace(" ", "")
    raw = re.sub(r"[^0-9,.-]", "", raw)

    if not raw:
        raise ValueError("Valor monetario vazio.")

    # Formato brasileiro completo: 1.250,90 / 10.000,00
    if "." in raw and "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
        return float(raw)

    # Virgula sem ponto: em pt-BR tratamos como separador decimal.
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
        return float(raw)

    # Apenas ponto.
    if "." in raw:
        parts = raw.split(".")

        # Multiplos pontos: 1.250.000 -> milhares.
        if len(parts) > 2:
            if all(len(part) == 3 for part in parts[1:]):
                return float("".join(parts))

        # Um ponto seguido de exatamente 3 digitos:
        # 1.250 / 12.500 / 999.999 -> separador de milhar.
        if len(parts) == 2 and len(parts[1]) == 3:
            return float("".join(parts))

        # Caso contrario, aceita ponto decimal: 25.50.
        return float(raw)

    return float(raw)


MONEY_TOKEN = r"\d[\d.,]*"


def money(text: str) -> float | None:
    """
    Extrai valor monetario sem confundir separador de milhar com decimal.

    Exemplos:
    Paguei 32 no Uber              -> 32.0
    Paguei 32,50 no Uber           -> 32.5
    Gastei 1.250,90 no mercado     -> 1250.9
    Gastei 2.500 no mercado        -> 2500.0
    Paguei R$ 1.999,99             -> 1999.99
    Fone de ate 400 reais          -> 400.0
    """

    t = normalize(text)

    patterns = [
        # Moeda explicita.
        rf"r\$\s*({MONEY_TOKEN})",

        # Numero seguido da unidade monetaria.
        rf"({MONEY_TOKEN})\s*(?:reais|real|conto|contos)\b",

        # Verbos financeiros seguidos diretamente do valor.
        rf"\b(?:paguei|pagamos|gastei|gastamos|comprei|compramos|recebi|ganhei)\s+(?:r\$\s*)?({MONEY_TOKEN})",

        # Contextos de preco futuro.
        rf"\b(?:ate|por|custa|custando|valor de)\s+(?:r\$\s*)?({MONEY_TOKEN})",
    ]

    for pattern in patterns:
        match = re.search(pattern, t, flags=re.I)
        if match:
            return _to_float(match.group(1))

    # Fallback apenas se houver um token numerico claro.
    match = re.search(MONEY_TOKEN, t)
    if match:
        return _to_float(match.group(0))

    return None


def _strip_leading_article(value: str) -> str:
    value = value.strip(" .,-")
    value = re.sub(
        r"^(?:um|uma|uns|umas|o|a|ao|aos|na|no)\s+",
        "",
        value,
        flags=re.I,
    )
    return value.strip(" .,-")


def _title_case_soft(value: str) -> str:
    value = value.strip()
    if not value:
        return value

    # Mantem siglas/numeros como PS5, MASP etc.
    words = []
    for word in value.split():
        if any(ch.isdigit() for ch in word) or word.isupper():
            words.append(word)
        else:
            words.append(word)
    return " ".join(words)


def _finance_category_and_movement(text: str) -> tuple[str, str]:
    t = normalize(text)

    groups = {
        "Alimentacao": [
            ("ifood", "iFood"),
            ("restaurante", "Restaurante"),
            ("mercado", "Mercado"),
            ("comida", "Comida"),
            ("padaria", "Padaria"),
            ("cafe", "Cafe"),
        ],
        "Transporte": [
            ("uber", "Uber"),
            ("99", "99"),
            ("metro", "Metro"),
            ("onibus", "Onibus"),
            ("gasolina", "Gasolina"),
            ("combustivel", "Combustivel"),
            ("estacionamento", "Estacionamento"),
        ],
        "Lazer": [
            ("cinema", "Cinema"),
            ("show", "Show"),
            ("bar", "Bar"),
            ("jogo", "Jogo"),
        ],
        "Compras": [
            ("amazon", "Amazon"),
            ("mercado livre", "Mercado Livre"),
            ("roupa", "Roupa"),
            ("eletronico", "Eletronico"),
        ],
        "Moradia": [
            ("aluguel", "Aluguel"),
            ("condominio", "Condominio"),
            ("internet", "Internet"),
            ("energia", "Energia"),
            ("luz", "Luz"),
            ("agua", "Agua"),
        ],
        "Saude": [
            ("farmacia", "Farmacia"),
            ("consulta", "Consulta"),
            ("medico", "Medico"),
            ("exame", "Exame"),
        ],
        "Viagem": [
            ("hotel", "Hotel"),
            ("passagem", "Passagem"),
            ("airbnb", "Airbnb"),
            ("viagem", "Viagem"),
        ],
    }

    real_category = {
        "Alimentacao": "Alimentação",
        "Transporte": "Transporte",
        "Lazer": "Lazer",
        "Compras": "Compras",
        "Moradia": "Moradia",
        "Saude": "Saúde",
        "Viagem": "Viagem",
    }

    for group_name, items in groups.items():
        for keyword, movement in items:
            if keyword in t:
                return real_category[group_name], movement

    # Tenta obter estabelecimento apos "no/na".
    match = re.search(
        r"\b(?:no|na|em)\s+([a-z0-9][a-z0-9 ._-]{1,50})$",
        t,
        flags=re.I,
    )
    if match:
        movement = match.group(1).strip().title()
        return "Outros", movement

    return "Outros", "Movimentação"


def fast_finance(message: str, author: str) -> FinanceAction | None:
    t = normalize(message)

    expense_words = [
        "paguei", "pagamos", "gastei", "gastamos",
        "comprei", "compramos",
    ]
    income_words = [
        "recebi", "ganhei", "salario", "reembolso",
    ]

    expense = any(word in t for word in expense_words)
    income = any(word in t for word in income_words)

    if not expense and not income:
        return None

    value = money(message)
    category, movement = _finance_category_and_movement(message)

    if any(
        word in t
        for word in ["pagamos", "gastamos", "compramos", "juntos"]
    ):
        paid_by = "Nós dois"
    elif (
        author == "Carol"
        or "carol pagou" in t
        or "minha esposa pagou" in t
        or "ela pagou" in t
    ):
        paid_by = "Minha esposa"
    else:
        paid_by = "Eu"

    return FinanceAction(
        needs_confirmation=value is None,
        missing_fields=[] if value is not None else ["valor"],
        movimento=movement,
        valor=value,
        tipo="Saída" if expense else "Entrada",
        categoria=category,
        pago_por=paid_by,
        status="Pago",
        data=now().date(),
        observacao=message,
    )


def parse_finance(message: str, author: str) -> FinanceAction:
    parsed = fast_finance(message, author)
    if parsed:
        return parsed

    return structured_chat(
        FinanceAction,
        FINANCE_PROMPT,
        (
            f"Data atual: {now().date()}\n"
            f"Autor: {author}\n"
            f"Mensagem: {message}"
        ),
    )


WISHLIST_PREFIXES = [
    "quero comprar",
    "queremos comprar",
    "queria comprar",
    "gostaria de comprar",
    "quero ganhar",
    "queremos ter",
]


def _wishlist_type(item: str) -> str:
    t = normalize(item)

    if any(
        word in t
        for word in [
            "fone", "headset", "celular", "telefone", "notebook",
            "computador", "pc", "monitor", "teclado", "mouse",
            "ps5", "playstation", "xbox", "tv", "tablet",
        ]
    ):
        return "Tecnologia"

    if any(
        word in t
        for word in [
            "camisa", "camiseta", "calca", "vestido",
            "roupa", "tenis", "sapato", "jaqueta",
        ]
    ):
        return "Roupa"

    if any(
        word in t
        for word in [
            "sofa", "mesa", "cadeira", "cafeteira", "panela",
            "air fryer", "geladeira", "microondas", "cama",
        ]
    ):
        return "Casa"

    return "Item"


def fast_wishlist(message: str) -> WishlistAction | None:
    t = normalize(message)

    prefix = next(
        (item for item in WISHLIST_PREFIXES if item in t),
        None,
    )
    if not prefix:
        return None

    start = t.find(prefix) + len(prefix)
    item = t[start:].strip(" .,-")

    # Remove apenas o trecho de preco. A ordem importa:
    # "fone de ouvido de ate 400" -> "fone de ouvido"
    price_patterns = [
        rf"\s+de\s+ate\s+(?:r\$\s*)?{NUMBER_PATTERN}.*$",
        rf"\s+ate\s+(?:r\$\s*)?{NUMBER_PATTERN}.*$",
        rf"\s+por\s+(?:r\$\s*)?{NUMBER_PATTERN}.*$",
        rf"\s+que\s+custa\s+(?:r\$\s*)?{NUMBER_PATTERN}.*$",
        rf"\s+custando\s+(?:r\$\s*)?{NUMBER_PATTERN}.*$",
    ]

    for pattern in price_patterns:
        item = re.sub(pattern, "", item, flags=re.I)

    item = _strip_leading_article(item)
    item = _title_case_soft(item)

    if not item:
        return None

    return WishlistAction(
        item=item[:200],
        preco_estimado=money(message),
        tipo=_wishlist_type(item),
        observacao=message,
    )


def parse_wishlist(message: str) -> WishlistAction:
    parsed = fast_wishlist(message)
    if parsed:
        return parsed

    return structured_chat(
        WishlistAction,
        WISHLIST_PROMPT,
        f"Data atual: {now().date()}\nMensagem: {message}",
    )


PLACE_PREFIXES = [
    "quero conhecer",
    "queremos conhecer",
    "quero visitar",
    "queremos visitar",
    "vamos conhecer",
    "gostaria de conhecer",
    "quero ir para",
    "queremos ir para",
    "quero ir ao",
    "quero ir a",
    "quero ir no",
    "quero ir na",
    "quero ir",
    "queremos ir",
]


def _place_type(value: str) -> str:
    t = normalize(value)

    if "restaurante" in t:
        return "Restaurante"
    if "hotel" in t or "pousada" in t or "airbnb" in t:
        return "Hotel"
    if "show" in t or "festival" in t or "concerto" in t:
        return "Show"
    if "viagem" in t or "viajar" in t:
        return "Viagem"
    if any(
        word in t
        for word in [
            "museu", "parque", "masp", "aquario",
            "zoologico", "passeio", "exposicao",
        ]
    ):
        return "Passeio"

    return "Outro"


def _has_price_context(text: str) -> bool:
    t = normalize(text)
    return bool(
        re.search(
            rf"(?:r\$|reais|real|ate\s+{NUMBER_PATTERN}|por\s+{NUMBER_PATTERN})",
            t,
            flags=re.I,
        )
    )


def fast_place(message: str) -> PlaceAction | None:
    t = normalize(message)

    prefix = next(
        (item for item in PLACE_PREFIXES if item in t),
        None,
    )
    if not prefix:
        return None

    start = t.find(prefix) + len(prefix)
    value = t[start:].strip(" .,-")
    value = _strip_leading_article(value)

    if not value:
        return None

    local = ""
    place_name = value

    # "restaurante italiano em sp"
    # -> nome: restaurante italiano
    # -> local: sp
    match = re.match(
        r"(.+?)\s+em\s+(.+)$",
        value,
        flags=re.I,
    )
    if match:
        candidate_name = match.group(1).strip()
        candidate_local = match.group(2).strip()

        if candidate_name and candidate_local:
            place_name = candidate_name
            local = candidate_local

    # Remove eventual preco do titulo/local.
    for pattern in [
        rf"\s+de\s+ate\s+(?:r\$\s*)?{NUMBER_PATTERN}.*$",
        rf"\s+ate\s+(?:r\$\s*)?{NUMBER_PATTERN}.*$",
        rf"\s+por\s+(?:r\$\s*)?{NUMBER_PATTERN}.*$",
    ]:
        place_name = re.sub(pattern, "", place_name, flags=re.I)
        local = re.sub(pattern, "", local, flags=re.I)

    place_name = _strip_leading_article(place_name)
    place_name = _title_case_soft(place_name)
    local = _strip_leading_article(local)

    if not place_name:
        return None

    return PlaceAction(
        lugar=place_name[:200],
        local=local[:200],
        descricao=message,
        tipo=_place_type(place_name),
        valor_estimado=money(message) if _has_price_context(message) else None,
        status="Ideia"
    )


def parse_place(message: str) -> PlaceAction:
    parsed = fast_place(message)
    if parsed:
        return parsed

    return structured_chat(
        PlaceAction,
        PLACE_PROMPT,
        f"Data atual: {now().date()}\nMensagem: {message}",
    )


def parse_calendar(message: str) -> CalendarAction:
    return structured_chat(
        CalendarAction,
        CALENDAR_PROMPT,
        f"Data atual: {now().date()}\nMensagem: {message}",
    )


def parse_routine(message: str) -> RoutineAction:
    return structured_chat(
        RoutineAction,
        ROUTINE_PROMPT,
        f"Data atual: {now().date()}\nMensagem: {message}",
    )
