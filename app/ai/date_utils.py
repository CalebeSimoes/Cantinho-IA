import calendar
import re
import unicodedata
from datetime import date, timedelta


MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

WEEKDAYS = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}


def normalize_date_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", value).strip().lower()


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _last_day(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _future_month_day(
    day: int,
    month: int,
    reference: date,
    year: int | None = None,
) -> date | None:
    if year is not None:
        if year < 100:
            year += 2000
        return _safe_date(year, month, day)

    candidate = _safe_date(reference.year, month, day)
    if candidate is None:
        return None
    if candidate < reference:
        candidate = _safe_date(reference.year + 1, month, day)
    return candidate


def contains_temporal_expression(text: str) -> bool:
    t = normalize_date_text(text)
    patterns = [
        r"\bhoje\b",
        r"\bamanha\b",
        r"\bdepois de amanha\b",
        r"\bdaqui a \d+ dias?\b",
        r"\b(?:fim|final|inicio|comeco) (?:do|deste|desse) (?:proximo )?mes\b",
        r"\b(?:semana|mes) que vem\b",
        r"\b(?:proxima?\s+)?(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?(?: que vem)?\b",
        r"\bdia\s+\d{1,2}\b",
        r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
        r"\b\d{1,2}\s+de\s+(?:" + "|".join(MONTHS) + r")\b",
    ]
    return any(re.search(pattern, t) for pattern in patterns)


def resolve_date_expression(
    text: str,
    reference: date | None = None,
) -> date | None:
    reference = reference or date.today()
    t = normalize_date_text(text)

    match = re.search(
        r"\b([0-3]?\d)[/-]([01]?\d)(?:[/-](\d{2,4}))?\b",
        t,
    )
    if match:
        return _future_month_day(
            int(match.group(1)),
            int(match.group(2)),
            reference,
            int(match.group(3)) if match.group(3) else None,
        )

    month_names = "|".join(MONTHS)
    match = re.search(
        rf"\b([0-3]?\d)\s+de\s+({month_names})(?:\s+de\s+(\d{{4}}))?\b",
        t,
    )
    if match:
        return _future_month_day(
            int(match.group(1)),
            MONTHS[match.group(2)],
            reference,
            int(match.group(3)) if match.group(3) else None,
        )

    if re.search(
        r"\b(?:fim|final) (?:do|deste|desse) proximo mes\b",
        t,
    ):
        year, month = _next_month(reference.year, reference.month)
        return _last_day(year, month)

    if re.search(
        r"\b(?:inicio|comeco) (?:do|deste|desse) proximo mes\b",
        t,
    ):
        year, month = _next_month(reference.year, reference.month)
        return date(year, month, 1)

    if re.search(
        r"\b(?:fim|final) (?:do|deste|desse) mes\b",
        t,
    ):
        return _last_day(reference.year, reference.month)

    if re.search(
        r"\b(?:inicio|comeco) (?:do|deste|desse) mes\b",
        t,
    ):
        candidate = date(reference.year, reference.month, 1)
        if candidate < reference:
            year, month = _next_month(reference.year, reference.month)
            return date(year, month, 1)
        return candidate

    if re.search(r"\bdepois de amanha\b", t):
        return reference + timedelta(days=2)
    if re.search(r"\bamanha\b", t):
        return reference + timedelta(days=1)
    if re.search(r"\bhoje\b", t):
        return reference

    match = re.search(r"\bdaqui a (\d+) dias?\b", t)
    if match:
        return reference + timedelta(days=int(match.group(1)))

    for weekday_name, weekday in WEEKDAYS.items():
        if re.search(
            rf"\b(?:proxima?\s+)?{weekday_name}(?:-feira)?(?: que vem)?\b",
            t,
        ):
            days_ahead = (weekday - reference.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return reference + timedelta(days=days_ahead)

    match = re.search(r"\bdia\s+([0-3]?\d)\b", t)
    if match:
        day = int(match.group(1))
        candidate = _safe_date(reference.year, reference.month, day)
        if candidate is not None and candidate >= reference:
            return candidate
        year, month = _next_month(reference.year, reference.month)
        return _safe_date(year, month, day)

    if re.search(r"\bsemana que vem\b", t):
        return reference + timedelta(days=7)

    return None


def strip_temporal_expressions(text: str) -> str:
    t = normalize_date_text(text)
    month_names = "|".join(MONTHS)
    patterns = [
        r"\b(?:no|na|ate|para|pro|pra)?\s*(?:fim|final|inicio|comeco) (?:do|deste|desse) (?:proximo )?mes\b",
        r"\b(?:na|ate|para)?\s*(?:semana|mes) que vem\b",
        r"\b(?:hoje|amanha|depois de amanha)\b",
        r"\bdaqui a \d+ dias?\b",
        rf"\b\d{{1,2}}\s+de\s+(?:{month_names})(?:\s+de\s+\d{{4}})?\b",
        r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
        r"\b(?:no|na|ate|para)?\s*dia\s+\d{1,2}\b",
        r"\b(?:na|no|para|ate)?\s*(?:proxima?\s+)?(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?(?: que vem)?\b",
        r"\b(?:as|a partir das)\s+\d{1,2}(?:(?::|h)\d{0,2})?\b",
    ]
    for pattern in patterns:
        t = re.sub(pattern, " ", t)
    return re.sub(r"\s+", " ", t).strip(" .,-")
