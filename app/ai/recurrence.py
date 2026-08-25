import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.ai.date_utils import resolve_date_expression
from app.ai.router import normalize


WEEKDAYS = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}

WEEKDAY_PATTERN = (
    r"segunda|terca|quarta|quinta|sexta|sabado|domingo"
)


@dataclass(frozen=True)
class RecurrenceInfo:
    frequency: str
    rule: str
    due_date: date | None


def _on_or_after(reference: date, weekday: int) -> date:
    return reference + timedelta(days=(weekday - reference.weekday()) % 7)


def _mentioned_weekdays(text: str) -> tuple[int, ...]:
    """Retorna dias citados, sem duplicatas, na ordem da semana."""
    mentioned = {
        WEEKDAYS[match.group(1)]
        for match in re.finditer(
            rf"\b({WEEKDAY_PATTERN})(?:s|-feiras?)?\b",
            text,
        )
    }
    return tuple(sorted(mentioned))


def _weekday_list_is_recurring(
    text: str,
    weekdays: tuple[int, ...],
) -> bool:
    if not weekdays:
        return False
    explicit_weekday_schedule = re.search(
        rf"\b(?:toda|todo|todas as|todos os|as|nas|aos)\s+"
        rf"(?:{WEEKDAY_PATTERN})(?:s|-feiras?)?\b",
        text,
    )
    explicit_weekly_frequency = (
        len(weekdays) >= 2
        and re.search(
            r"\b(?:toda semana|semanalmente|a cada semana)\b",
            text,
        )
    )
    return bool(explicit_weekday_schedule or explicit_weekly_frequency)


def _first_weekday_on_or_after(
    reference: date,
    weekdays: tuple[int, ...],
) -> date:
    return min(_on_or_after(reference, weekday) for weekday in weekdays)


def parse_recurrence(message: str, reference: date) -> RecurrenceInfo:
    """Converte linguagem natural em um padrão estável e próxima data."""
    text = normalize(message)

    if re.search(r"\b(?:todo dia|todos os dias|diariamente)\b", text):
        return RecurrenceInfo("Diária", "daily", reference)

    if re.search(r"\b(?:dias uteis|de segunda a sexta)\b", text):
        due = reference
        while due.weekday() >= 5:
            due += timedelta(days=1)
        return RecurrenceInfo("Dias úteis", "weekdays", due)

    if re.search(
        r"\b(?:todo (?:fim|final) de semana|"
        r"todos os (?:fins|finais) de semana|"
        r"(?:nos|aos) (?:fins|finais) de semana)\b",
        text,
    ):
        return RecurrenceInfo(
            "Fim de semana",
            "weekends",
            _on_or_after(reference, 5),
        )

    weekdays = _mentioned_weekdays(text)
    if _weekday_list_is_recurring(text, weekdays):
        rule_days = ",".join(str(weekday) for weekday in weekdays)
        if re.search(r"\bquinzenal(?:mente)?\b", text):
            return RecurrenceInfo(
                "Quinzenal",
                f"biweekly:{rule_days}",
                _first_weekday_on_or_after(reference, weekdays),
            )
        return RecurrenceInfo(
            "Semanal",
            f"weekly:{rule_days}",
            _first_weekday_on_or_after(reference, weekdays),
        )

    if re.search(r"\b(?:quinzenalmente|quinzenal|a cada 15 dias)\b", text):
        return RecurrenceInfo("Quinzenal", "biweekly", reference)

    if re.search(
        r"\b(?:uma vez por mes|todo mes|todos os meses|mensalmente|"
        r"a cada mes)\b",
        text,
    ):
        day_match = re.search(r"\bdia\s+([0-3]?\d)\b", text)
        day = int(day_match.group(1)) if day_match else reference.day
        day = max(1, min(day, 31))
        last = calendar.monthrange(reference.year, reference.month)[1]
        due = date(reference.year, reference.month, min(day, last))
        if due < reference:
            due = _next_month_day(reference, day)
        return RecurrenceInfo("Mensal", f"monthly:{day}", due)

    if re.search(r"\b(?:toda semana|semanalmente|a cada semana)\b", text):
        return RecurrenceInfo(
            "Semanal",
            f"weekly:{reference.weekday()}",
            reference,
        )

    return RecurrenceInfo(
        "Pontual",
        "once",
        resolve_date_expression(message, reference),
    )


def strip_recurrence_expression(message: str) -> str:
    value = normalize(message)
    patterns = [
        r"\b(?:todo dia|todos os dias|diariamente)\b",
        r"\b(?:(?:nos|em)\s+)?(?:dias uteis|de segunda a sexta)\b",
        r"\b(?:todo (?:fim|final) de semana|todos os (?:fins|finais) de semana|(?:nos|aos) (?:fins|finais) de semana)\b",
        r"\b(?:quinzenalmente|quinzenal|a cada 15 dias)\b",
        r"\b(?:uma vez por mes|todo mes|todos os meses|mensalmente|a cada mes)\b",
        r"\b(?:toda semana|semanalmente|a cada semana)\b",
        rf"\b(?:toda|todo|todas as|todos os|as|nas|aos)\s+"
        rf"(?:{WEEKDAY_PATTERN})(?:s|-feiras?)?"
        rf"(?:\s*(?:,|e)?\s*(?:{WEEKDAY_PATTERN})(?:s|-feiras?)?)+\b",
        rf"\b(?:toda|todo|todas as|todos os|as|nas|aos)\s+"
        rf"(?:{WEEKDAY_PATTERN})(?:s|-feiras?)?\b",
    ]
    for pattern in patterns:
        value = re.sub(pattern, " ", value)
    return re.sub(r"\s+", " ", value).strip(" .,-")


def _next_month_day(reference: date, day: int) -> date:
    if reference.month == 12:
        year, month = reference.year + 1, 1
    else:
        year, month = reference.year, reference.month + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def next_occurrence(
    rule: str,
    current_due: date | None,
    completed_on: date,
) -> date | None:
    """Calcula a primeira ocorrência estritamente após a conclusão."""
    if not rule or rule == "once":
        return None
    if rule == "daily":
        return completed_on + timedelta(days=1)
    if rule == "weekdays":
        candidate = completed_on + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate
    if rule == "weekends":
        return _on_or_after(completed_on + timedelta(days=1), 5)
    if rule.startswith("weekly:"):
        weekdays = tuple(
            int(value)
            for value in rule.split(":", 1)[1].split(",")
        )
        return _first_weekday_on_or_after(
            completed_on + timedelta(days=1),
            weekdays,
        )
    if rule.startswith("biweekly"):
        anchor = current_due or completed_on
        candidate = anchor + timedelta(days=14)
        while candidate <= completed_on:
            candidate += timedelta(days=14)
        return candidate
    if rule.startswith("monthly:"):
        day = int(rule.split(":", 1)[1])
        return _next_month_day(completed_on, day)
    return None
