import re
import unicodedata
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.ai.date_utils import (
    resolve_date_expression,
    strip_temporal_expressions,
)
from app.ai.ollama_client import structured_chat
from app.ai.recurrence import (
    parse_recurrence,
    strip_recurrence_expression,
)
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
# Alias semantico usado nos regex de preco.
NUMBER_PATTERN = MONEY_TOKEN


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
        rf"\b(?:paguei|pagou|pagamos|gastei|gastou|gastamos|"
        rf"comprei|comprou|compramos|recebi|recebeu|ganhei|ganhou)\s+"
        rf"(?:r\$\s*)?({MONEY_TOKEN})",

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
            ("hbo", "HBO"),
            ("netflix", "Netflix"),
            ("streaming", "Streaming"),
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

    match = re.search(
        r"\b(?:comprei|comprou|compramos)\s+(?:o|a|um|uma)?\s*"
        r"(.+?)(?=\s+(?:por|de)\s+(?:r\$\s*)?\d|$)",
        t,
    )
    if match:
        return "Compras", _strip_leading_article(
            match.group(1)
        ).strip().title()

    match = re.search(
        r"\b(?:com|em|no|na)\s+(?:um|uma|o|a)?\s*"
        r"([a-z][a-z0-9 ._-]{1,50})$",
        t,
    )
    if match:
        return "Outros", match.group(1).strip().title()

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
        "paguei", "pagou", "pagamos", "gastei", "gastou", "gastamos",
        "comprei", "comprou", "compramos", "assinei", "assinou", "assinamos",
    ]
    income_words = [
        "recebi", "recebeu", "ganhei", "ganhou", "salario", "reembolso",
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
    "quero assinar",
    "queremos assinar",
    "gostaria de assinar",
    "estou pensando em comprar",
    "estamos pensando em comprar",
    "planejo comprar",
    "planejamos comprar",
]


PURCHASE_VERB_PATTERN = r"\b(?:comprar|adquirir|encomendar)\b"


def _wishlist_price_relation(message: str) -> str | None:
    if not _has_price_context(message):
        return None

    t = normalize(message)
    if re.search(r"\b(?:de\s+)?(?:ate|no maximo)\b", t):
        return "Máximo"
    if re.search(r"\b(?:a partir de|no minimo)\b", t):
        return "Mínimo"
    if re.search(r"\b(?:cerca de|por volta de|mais ou menos)\b", t):
        return "Aproximado"
    if re.search(r"\bexatamente\b", t):
        return "Exato"
    return "Aproximado"


def _wishlist_status(message: str) -> str:
    t = normalize(message)
    if re.search(
        r"\b(?:preciso|precisa|precisamos|tenho que|tem que|temos que|"
        r"devo|deve|devemos|vou|vai|vamos|planejo|planejamos)\b",
        t,
    ):
        return "Planejando"
    return "Quero"


def _strip_purchase_constraints(value: str) -> str:
    price = rf"(?:r\$\s*)?{NUMBER_PATTERN}(?:\s*(?:reais?|contos?))?"
    patterns = [
        rf"\b(?:de\s+)?(?:ate|no maximo)\s+{price}",
        rf"\b(?:a partir de|no minimo)\s+{price}",
        rf"\b(?:por|que custa|custando|no valor de|exatamente|"
        rf"cerca de|por volta de|mais ou menos)\s+{price}",
    ]
    for pattern in patterns:
        value = re.sub(pattern, " ", value, flags=re.I)
    value = strip_temporal_expressions(value)
    value = re.sub(r"\b(?:ate|para|de)\s*$", "", value)
    return re.sub(r"\s+", " ", value).strip(" .,-")


def _wishlist_type(item: str) -> str:
    t = normalize(item)

    if any(
        word in t
        for word in [
            "fone", "headset", "celular", "telefone", "notebook",
            "computador", "pc", "monitor", "teclado", "mouse",
            "ps5", "playstation", "xbox", "tv", "tablet",
            "hbo", "netflix", "spotify", "streaming", "assinatura",
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
            "air fryer", "geladeira", "microondas", "micro-ondas",
            "forno", "lava-loucas", "lava-louças", "guarda-roupa",
            "ar-condicionado", "cama",
        ]
    ):
        return "Casa"

    return "Item"


def fast_wishlist(
    message: str,
    author: str = "Eu",
) -> WishlistAction | None:
    t = normalize(message)

    purchase = re.search(PURCHASE_VERB_PATTERN, t)
    if purchase:
        start = purchase.end()
    else:
        prefix = next(
            (item for item in WISHLIST_PREFIXES if item in t),
            None,
        )
        if not prefix:
            return None
        start = t.find(prefix) + len(prefix)

    item = _strip_purchase_constraints(t[start:])

    item = _strip_leading_article(item)
    item = _title_case_soft(item)

    if not item:
        return None

    return WishlistAction(
        item=item[:200],
        data_desejada=resolve_date_expression(message, now().date()),
        preco_estimado=(
            money(message) if _has_price_context(message) else None
        ),
        preco_relacao=_wishlist_price_relation(message),
        responsavel=_subject_responsible(message, author),
        status=_wishlist_status(message),
        tipo=_wishlist_type(item),
        observacao=message,
    )


def parse_wishlist(
    message: str,
    author: str = "Eu",
) -> WishlistAction:
    parsed = fast_wishlist(message, author)
    if parsed:
        return parsed

    return structured_chat(
        WishlistAction,
        WISHLIST_PROMPT,
        (
            f"Data atual: {now().date()}\n"
            f"Autor: {author}\nMensagem: {message}"
        ),
    )


PLACE_PREFIXES = [
    "quero conhecer",
    "queremos conhecer",
    "quero visitar",
    "queremos visitar",
    "vamos conhecer",
    "vamos visitar",
    "pretendemos conhecer",
    "pretendemos visitar",
    "gostaria de conhecer",
    "quero ir para",
    "queremos ir para",
    "quero ir ao",
    "quero ir a",
    "quero ir no",
    "quero ir na",
    "quero ir",
    "queremos ir",
    "visitar",
    "conhecer",
    "ir para",
    "ir ao",
    "ir a",
    "ir no",
    "ir na",
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
            rf"(?:r\$|reais?\b|contos?\b|"
            rf"(?:ate|no maximo|por|custa|custando|no valor de|"
            rf"a partir de|no minimo|cerca de|por volta de|mais ou menos)"
            rf"\s+(?:r\$\s*)?{NUMBER_PATTERN})",
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


def _subject_responsible(message: str, author: str) -> str:
    t = normalize(message)
    partner = normalize(settings.partner_name)
    user = normalize(settings.user_name)

    if re.search(
        r"\b(?:nos dois|juntos|precisamos|temos que|devemos|queremos|"
        r"vamos|planejamos)\b",
        t,
    ) or (
        partner in t
        and any(alias in t for alias in {user, "caleb", "calebe"})
    ):
        return "Nós dois"

    partner_subject = bool(
        partner
        and re.match(
            rf"^(?:a\s+)?{re.escape(partner)}\b.*\b(?:precisa|deve|vai|tem que)\b",
            t,
        )
    )
    if partner_subject or re.match(
        r"^(?:minha esposa|ela)\b.*\b(?:precisa|deve|vai|tem que)\b",
        t,
    ):
        return "Minha esposa"

    user_aliases = {
        alias for alias in {user, "caleb", "calebe"}
        if alias
    }
    if any(
        re.match(
            rf"^(?:o\s+)?{re.escape(alias)}\b.*\b(?:precisa|deve|vai|tem que)\b",
            t,
        )
        for alias in user_aliases
    ) or re.match(r"^eu\b.*\b(?:preciso|devo|vou|tenho que)\b", t):
        return "Eu"

    return "Minha esposa" if author == "Carol" else "Eu"


def _strip_action_prefix(text: str) -> str:
    value = strip_temporal_expressions(
        strip_recurrence_expression(text)
    )
    recurrence_prefixes = [
        r"^(?:todo dia|todos os dias|diariamente)\s+",
        r"^(?:toda semana|semanalmente|a cada semana)\s+",
        r"^(?:todo mes|mensalmente|a cada mes)\s+",
    ]
    subject = (
        r"(?:(?:eu|nos|a gente|caleb|calebe|carol|minha esposa|ela)\s+|"
        r"(?:o|a)\s+[a-z0-9_-]+\s+|[a-z0-9_-]+\s+)?"
    )
    action_prefixes = [
        rf"^{subject}(?:preciso|precisa|precisamos|tenho que|tem que|temos que|devo|deve|devemos)\s+",
        rf"^{subject}(?:nao esquecer(?: de)?|lembrar de|me lembr(?:a|e)(?: de)?)\s+",
        rf"^{subject}(?:fica responsavel por)\s+",
    ]

    changed = True
    while changed:
        changed = False
        for pattern in recurrence_prefixes + action_prefixes:
            updated = re.sub(pattern, "", value, count=1)
            if updated != value:
                value = updated.strip()
                changed = True

    return re.sub(r"^(?:de|que)\s+", "", value).strip(" .,-")


def _routine_frequency(message: str) -> str:
    return parse_recurrence(message, now().date()).frequency


def _routine_category(task: str) -> str:
    t = normalize(task)
    categories = [
        (
            "Casa",
            r"\b(?:limpar|lavar|arrumar|organizar a casa|cozinha|banheiro|quarto|roupa|louca|mercado|lixo|faxina)\b",
        ),
        (
            "Saúde",
            r"\b(?:remedio|medico|consulta|exame|academia|treinar|vacina|terapia|saude|vitamina|suplemento)\b",
        ),
        (
            "Estudo",
            r"\b(?:estudar|prova|curso|faculdade|aula|trabalho da faculdade|ler livro)\b",
        ),
        (
            "Trabalho",
            r"\b(?:cliente|relatorio|reuniao de trabalho|planilha|projeto|contrato|curriculo|entrevista)\b",
        ),
        (
            "Relacionamento",
            r"\b(?:casal|encontro|presente para|aniversario de namoro|tempo juntos)\b",
        ),
    ]
    for category, pattern in categories:
        if re.search(pattern, t):
            return category
    return "Outro"


def fast_routine(
    message: str,
    author: str = "Eu",
) -> RoutineAction | None:
    t = normalize(message)
    desire = re.search(
        r"\b(?:quero|queremos|queria|gostaria)\s+(?:comprar|ter|ganhar|assinar|conhecer|visitar)\b",
        t,
    )
    task_signal = re.search(
        r"\b(?:preciso|precisa|precisamos|tenho que|tem que|temos que|"
        r"devo|deve|devemos|nao esquecer|lembrar de|me lembr(?:a|e)(?: de)?|"
        r"todo dia|toda semana|"
        r"todo mes|diariamente|semanalmente|mensalmente|quinzenalmente|"
        r"dias uteis|fim de semana|uma vez por mes|"
        r"toda (?:segunda|terca|quarta|quinta|sexta|sabado|domingo)|"
        r"tarefa|rotina)\b",
        t,
    )
    action_signal = re.search(
        r"\b(?:assinar|renovar|cancelar|limpar|lavar|arrumar|organizar|resolver|ligar|enviar|buscar|levar|estudar|treinar|instalar|consertar|preparar|pagar|comprar|pesquisar|comparar|cotar|procurar|separar|conferir|revisar|atualizar|responder|devolver|retirar|guardar|cozinhar|fazer)\b",
        t,
    )
    if desire or not (task_signal or action_signal):
        return None

    task = _strip_action_prefix(message)
    if not task:
        return None

    recurrence = parse_recurrence(message, now().date())
    return RoutineAction(
        tarefa=task[:200],
        categoria=_routine_category(task),
        dia_data=recurrence.due_date,
        frequencia=recurrence.frequency,
        recurrence_rule=recurrence.rule,
        observacao=message,
        responsavel=_subject_responsible(message, author),
        status="A fazer",
    )


def _calendar_type(event: str) -> str:
    t = normalize(event)
    if "aniversario" in t:
        return "Aniversário"
    if "viagem" in t:
        return "Viagem"
    if any(
        word in t
        for word in ["jantar", "almoco", "cinema", "encontro"]
    ):
        return "Encontro"
    if any(word in t for word in ["casa", "condominio", "mudanca"]):
        return "Casa"
    if any(word in t for word in ["consulta", "reuniao", "entrevista"]):
        return "Compromisso"
    return "Outro"


def _calendar_time(message: str) -> time | None:
    text = normalize(message)
    match = re.search(
        r"\b(?:as|a partir das)\s+([01]?\d|2[0-3])"
        r"(?:(?::|h)([0-5]?\d)?)?\b",
        text,
    )
    if not match:
        match = re.search(
            r"\b([01]?\d|2[0-3])h([0-5]?\d)?\b",
            text,
        )
    if not match:
        return None
    return time(
        hour=int(match.group(1)),
        minute=int(match.group(2) or 0),
    )


def fast_calendar(
    message: str,
    author: str = "Eu",
) -> CalendarAction | None:
    t = normalize(message)
    task_frame = re.search(
        r"\b(?:preciso|precisa|precisamos|tenho que|temos que)\b",
        t,
    )
    schedule = re.search(
        r"\b(?:agendar|agendei|agendamos|marcar|marquei|marcamos|"
        r"reservar|reservei|reservamos)\b",
        t,
    )
    event_signal = re.search(
        r"\b(?:consulta|reuniao|aniversario|evento|compromisso|jantar|almoco|cinema|show|cerimonia|festa|entrevista|viagem|dentista|medico)\b",
        t,
    )
    if task_frame and not schedule:
        return None
    if not (schedule or event_signal):
        return None

    event = _strip_action_prefix(message)
    event = re.sub(
        r"^(?:agendar|agendei|agendamos|marcar|marquei|marcamos|"
        r"reservar|reservei|reservamos)\s+",
        "",
        event,
    ).strip(" .,-")
    if not event:
        return None

    event_date = resolve_date_expression(message, now().date())
    return CalendarAction(
        needs_confirmation=event_date is None,
        missing_fields=[] if event_date else ["data"],
        evento=event[:200],
        data=event_date,
        hora=_calendar_time(message),
        observacao=message,
        quem=_subject_responsible(message, author),
        status="Planejado",
        tipo=_calendar_type(event),
    )


def parse_calendar(
    message: str,
    author: str = "Eu",
) -> CalendarAction:
    parsed = fast_calendar(message, author)
    if parsed:
        return parsed
    return structured_chat(
        CalendarAction,
        CALENDAR_PROMPT,
        (
            f"Data atual: {now().date()}\n"
            f"Autor: {author}\nMensagem: {message}"
        ),
    )


def parse_routine(
    message: str,
    author: str = "Eu",
) -> RoutineAction:
    parsed = fast_routine(message, author)
    if parsed:
        return parsed
    return structured_chat(
        RoutineAction,
        ROUTINE_PROMPT,
        (
            f"Data atual: {now().date()}\n"
            f"Autor: {author}\nMensagem: {message}"
        ),
    )
