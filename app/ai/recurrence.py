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


@dataclass(frozen=True)
class RecurrenceInfo:
    frequency: str
    rule: str
    due_date: date | None


def _on_or_after(reference: date, weekday: int) -> date:
    return reference + timedelta(days=(weekday - reference.weekday()) % 7)


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
        r"\b(?:todo fim de semana|todos os fins de semana|"
        r"nos fins de semana|fim de semana)\b",
        text,
    ):
        return RecurrenceInfo(
            "Fim de semana",
            "weekends",
            _on_or_after(reference, 5),
        )

    weekday_match = re.search(
        r"\b(?:toda|todo|todas as|todos os)\s+"
        r"(segunda|terca|quarta|quinta|sexta|sabado|domingo)"
        r"(?:-feira)?\b",
        text,
    )
    if weekday_match:
        weekday = WEEKDAYS[weekday_match.group(1)]
        if re.search(r"\bquinzenal(?:mente)?\b", text):
            return RecurrenceInfo(
                "Quinzenal",
                f"biweekly:{weekday}",
                _on_or_after(reference, weekday),
            )
        return RecurrenceInfo(
            "Semanal",
            f"weekly:{weekday}",
            _on_or_after(reference, weekday),
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
        r"\b(?:(?:no|aos)\s+)?(?:todo fim de semana|todos os fins de semana|nos fins de semana|fim de semana)\b",
        r"\b(?:quinzenalmente|quinzenal|a cada 15 dias)\b",
        r"\b(?:uma vez por mes|todo mes|todos os meses|mensalmente|a cada mes)\b",
        r"\b(?:toda semana|semanalmente|a cada semana)\b",
        r"\b(?:toda|todo|todas as|todos os)\s+(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?\b",
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
        weekday = int(rule.split(":", 1)[1])
        return _on_or_after(completed_on + timedelta(days=1), weekday)
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
