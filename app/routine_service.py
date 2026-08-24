import re
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from app.ai.recurrence import next_occurrence
from app.ai.router import normalize
from app.config import settings
from app.notion.client import (
    optional_property_name,
    property_name,
    update_page,
)
from app.notion.readers import RoutineRecord, get_routines


@dataclass(frozen=True)
class CompletionResult:
    success: bool
    summary: str
    record: RoutineRecord | None = None
    next_date: date | None = None


def is_completion_command(message: str) -> bool:
    text = normalize(message)
    explicit = re.search(
        r"^(?:(?:eu|a carol|carol)\s+)?(?:terminei(?: de)?|conclui|"
        r"finalizei|ja fiz|acabei de|dei como concluida|"
        r"pode marcar como concluida|marquei como concluida)\b",
        text,
    )
    done_shorthand = re.search(
        r"^(?:feito|concluido)\s*[:\-]\s*.+$|"
        r"^.+\s+(?:feito|concluido)$",
        text,
    )
    return bool(explicit or done_shorthand)


def _completion_target(message: str) -> str:
    text = normalize(message)
    patterns = [
        r"^.*?\bterminei(?: de)?\s+",
        r"^.*?\bconclui\s+",
        r"^.*?\bfinalizei\s+",
        r"^.*?\bja fiz\s+",
        r"^.*?\bacabei de\s+",
        r"^.*?\b(?:pode )?marcar\s+",
        r"^(?:feito|concluido)\s*[:\-]\s*",
    ]
    for pattern in patterns:
        updated = re.sub(pattern, "", text, count=1)
        if updated != text:
            text = updated
            break
    text = re.sub(
        r"\s+como\s+concluid[oa]\b.*$|\s+como\s+feito\b.*$",
        "",
        text,
    )
    text = re.sub(r"\s+(?:feito|concluido)$", "", text)
    return text.strip(" .,-")


def _tokens(value: str) -> set[str]:
    stop = {
        "a", "o", "as", "os", "de", "da", "do", "das", "dos",
        "um", "uma", "para", "pra", "como", "tarefa",
    }
    return {part for part in normalize(value).split() if part not in stop}


def _score(target: str, candidate: str) -> float:
    left = normalize(target)
    right = normalize(candidate)
    if left == right:
        return 1.0
    if left in right or right in left:
        return .92
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    overlap = (
        len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        if left_tokens and right_tokens else 0
    )
    sequence = SequenceMatcher(None, left, right).ratio()
    return overlap * .65 + sequence * .35


def find_routine(
    target: str,
    author: str = "Eu",
    records: list[RoutineRecord] | None = None,
) -> tuple[RoutineRecord | None, bool]:
    records = records if records is not None else get_routines()
    preferred = "Minha esposa" if author == "Carol" else "Eu"
    ranked = []
    for record in records:
        score = _score(target, record.tarefa)
        if record.responsavel in {preferred, "Nós dois"}:
            score += .04
        ranked.append((score, record))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < .48:
        return None, False
    ambiguous = (
        len(ranked) > 1
        and ranked[1][0] >= .48
        and ranked[0][0] - ranked[1][0] < .08
    )
    return ranked[0][1], ambiguous


def _legacy_rule(record: RoutineRecord) -> str:
    if record.recurrence_rule and record.recurrence_rule != "once":
        return record.recurrence_rule
    if record.frequencia == "Diária":
        return "daily"
    if record.frequencia == "Semanal":
        weekday = (record.dia_data or date.today()).weekday()
        return f"weekly:{weekday}"
    if record.frequencia == "Quinzenal":
        return "biweekly"
    if record.frequencia == "Mensal":
        day = (record.dia_data or date.today()).day
        return f"monthly:{day}"
    if record.frequencia == "Dias úteis":
        return "weekdays"
    if record.frequencia == "Fim de semana":
        return "weekends"
    return "once"


def complete_routine(
    message: str,
    author: str = "Eu",
    *,
    completed_on: date | None = None,
    records: list[RoutineRecord] | None = None,
) -> CompletionResult:
    completed_on = completed_on or datetime.now(
        ZoneInfo(settings.app_timezone)
    ).date()
    target = _completion_target(message)
    if not target:
        return CompletionResult(False, "Qual tarefa você concluiu?")

    record, ambiguous = find_routine(target, author, records)
    if record is None:
        return CompletionResult(
            False,
            f"Não encontrei uma tarefa parecida com “{target}”.",
        )
    if ambiguous:
        return CompletionResult(
            False,
            "Encontrei mais de uma tarefa parecida; diga o nome com mais detalhes.",
        )
    if record.last_completed == completed_on:
        return CompletionResult(
            True,
            f"✅ {record.tarefa} já foi concluída hoje.",
            record,
            record.dia_data,
        )

    ds = settings.notion_routine_data_source_id
    status_name = property_name(ds, "Status")
    date_name = property_name(ds, "Dia / Data")
    props: dict = {}
    completed_name = optional_property_name(ds, "Ultima conclusao")
    if completed_name:
        props[completed_name] = {
            "date": {"start": completed_on.isoformat()}
        }

    rule = _legacy_rule(record)
    next_date = next_occurrence(rule, record.dia_data, completed_on)
    if next_date:
        props[status_name] = {"select": {"name": "A fazer"}}
        props[date_name] = {"date": {"start": next_date.isoformat()}}
        update_page(record.page_id, props)
        return CompletionResult(
            True,
            (
                f"✅ Concluí {record.tarefa}. Próxima ocorrência: "
                f"{next_date.strftime('%d/%m/%Y')}."
            ),
            record,
            next_date,
        )

    if record.status == "Concluído":
        return CompletionResult(
            True,
            f"✅ {record.tarefa} já estava concluída.",
            record,
        )
    props[status_name] = {"select": {"name": "Concluído"}}
    update_page(record.page_id, props)
    return CompletionResult(
        True,
        f"✅ Tarefa concluída: {record.tarefa}.",
        record,
    )
