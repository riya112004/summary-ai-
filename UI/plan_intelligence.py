"""Date-aware summaries for uploaded work plans."""

import re
from datetime import date, datetime, timedelta
from typing import Optional


_DATE_TEXT = r"\d{1,2}\s+[A-Za-z]+\s+\d{4}"
_DATE_RANGE = re.compile(
    rf"({_DATE_TEXT})\s+to\s+({_DATE_TEXT})",
    re.IGNORECASE,
)
_SECTION_HEADER = re.compile(
    r"(?m)^(?:"
    r"---\s*YEAR\s+\d+\s*/\s*QUARTER\s+\d+:[^\r\n]*?---"
    r"|YEAR\s+\d+\s*/\s*MONTH\s+\d+[^\r\n]*"
    r")\s*$",
    re.IGNORECASE,
)
_QUARTER_HEADER = re.compile(
    rf"^---\s*YEAR\s+(\d+)\s*/\s*QUARTER\s+(\d+):\s*(.*?)\s*"
    rf"\(({_DATE_TEXT})\s+to\s+({_DATE_TEXT})\)\s*---$",
    re.IGNORECASE,
)
_MONTH_HEADER = re.compile(
    rf"^YEAR\s+(\d+)\s*/\s*MONTH\s+(\d+)\s*"
    rf"\(({_DATE_TEXT})\s+to\s+({_DATE_TEXT})\)",
    re.IGNORECASE,
)
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def _parse_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        pass
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_date_range(value: str) -> Optional[tuple[date, date]]:
    match = _DATE_RANGE.search(value)
    if not match:
        return None
    start = _parse_date(match.group(1))
    end = _parse_date(match.group(2))
    if not start or not end or end < start:
        return None
    return start, end


def _section_body(text: str, end_of_header: int, next_header: int) -> str:
    body = text[end_of_header:next_header].strip()
    return re.sub(r"\s+", " ", body)


def _objective(body: str, *, month: bool) -> Optional[str]:
    pattern = (
        r"\bI will\s+(.+?)(?:\.\s|$)"
        if not month
        else r"\bI will\s+(.+?)(?:\.\s+This plan month\b|$)"
    )
    match = re.search(pattern, body, re.IGNORECASE)
    if not match:
        return None
    objective = match.group(1).strip()
    return objective[:1].upper() + objective[1:] if objective else None


def _extract_review_date(body: str, pattern: str) -> Optional[date]:
    match = re.search(rf"{pattern}\s+({_DATE_TEXT})", body, re.IGNORECASE)
    return _parse_date(match.group(1)) if match else None


def _parse_sections(text: str) -> tuple[list[dict], list[dict]]:
    headings = list(_SECTION_HEADER.finditer(text))
    quarters = []
    months = []
    for index, heading in enumerate(headings):
        next_start = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = _section_body(text, heading.end(), next_start)
        line = heading.group(0)
        quarter_match = _QUARTER_HEADER.match(line)
        if quarter_match:
            start = _parse_date(quarter_match.group(4))
            end = _parse_date(quarter_match.group(5))
            if start and end and end >= start:
                quarters.append({
                    "year": int(quarter_match.group(1)),
                    "quarter": int(quarter_match.group(2)),
                    "title": quarter_match.group(3).strip(),
                    "start": start,
                    "end": end,
                    "objective": _objective(body, month=False),
                    "review_date": _extract_review_date(
                        body, r"quarterly review will take place on"
                    ),
                })
            continue
        month_match = _MONTH_HEADER.match(line)
        if month_match:
            start = _parse_date(month_match.group(3))
            end = _parse_date(month_match.group(4))
            if start and end and end >= start:
                months.append({
                    "year": int(month_match.group(1)),
                    "month": int(month_match.group(2)),
                    "start": start,
                    "end": end,
                    "objective": _objective(body, month=True),
                    "review_date": _extract_review_date(
                        body, r"monthly review is on"
                    ),
                })
    return quarters, months


def _weekday_themes(text: str) -> dict[str, str]:
    match = re.search(r"(?im)^Weekday theme:\s*(.+)$", text)
    if not match:
        return {}
    paragraph = match.group(1)
    themes = {}
    pair = re.search(
        r"\bTuesday\s+and\s+Wednesday\s+are\s+for\s+(.+?)(?=,\s*Thursday\s+is\b|\.|$)",
        paragraph,
        re.IGNORECASE,
    )
    if pair:
        themes["Tuesday"] = pair.group(1).strip()
        themes["Wednesday"] = pair.group(1).strip()
    for index, weekday in enumerate(_WEEKDAYS):
        if weekday in themes:
            continue
        next_day = _WEEKDAYS[index + 1] if index + 1 < len(_WEEKDAYS) else None
        ending = rf"(?=,\s*{next_day}\s+is\b|\.|$)" if next_day else r"(?=\.|$)"
        theme = re.search(
            rf"\b{weekday}\s+is\s+(?:for|a day for)\s+(.+?){ending}",
            paragraph,
            re.IGNORECASE,
        )
        if theme:
            themes[weekday] = theme.group(1).strip()
    return themes


def build_plan_schedule_summary(
    text: str,
    *,
    today: Optional[date] = None,
) -> Optional[dict]:
    """Extract today's, this week's, month's, and quarter's plan highlights."""
    current_day = today or date.today()
    period_match = re.search(r"(?im)^Period:\s*(.+)$", text)
    if not period_match:
        return None
    plan_period = _parse_date_range(period_match.group(1))
    if not plan_period:
        return None
    quarters, months = _parse_sections(text)
    if not quarters or not months:
        return None

    day_name = current_day.strftime("%A")
    routine_match = re.search(r"(?im)^Daily routine:\s*(.+)$", text)
    routine = routine_match.group(1).strip() if routine_match else None
    themes = _weekday_themes(text)
    start, end = plan_period
    in_plan_period = start <= current_day <= end

    if day_name == "Sunday":
        today_focus = "Rest day; no planned work."
        today_type = "rest"
        due_date = current_day
        expiry_date = current_day
    elif day_name == "Saturday":
        today_focus = "Optional light work or learning (up to two hours); skip freely if rest is needed."
        today_type = "optional"
        due_date = current_day
        expiry_date = current_day
    else:
        today_focus = themes.get(day_name, "Follow the daily routine and plan priorities.")
        today_type = "workday"
        days_to_friday = 4 - current_day.weekday()
        due_date = current_day + timedelta(days=days_to_friday)
        expiry_date = due_date + timedelta(days=3)

    week_start = current_day - timedelta(days=current_day.weekday())
    week_end = week_start + timedelta(days=6)
    this_week = {
        "start": week_start,
        "end": week_end,
        "days": [
            {"day": weekday, "focus": themes.get(weekday, "No weekday theme specified.")}
            for weekday in _WEEKDAYS
        ],
        "saturday": "Optional light work or learning; no more than two hours.",
        "sunday": "Rest day; no planned work.",
        "deliverable_due": week_start + timedelta(days=4),
        "task_expiry": week_start + timedelta(days=7),
    }

    active_month = next(
        (month for month in months if month["start"] <= current_day <= month["end"]),
        None,
    )
    active_quarter = next(
        (quarter for quarter in quarters
         if quarter["start"] <= current_day <= quarter["end"]),
        None,
    )
    monthly_review = active_month or next(
        (month for month in months if month["start"] > current_day),
        None,
    )
    quarterly_review = active_quarter or next(
        (quarter for quarter in quarters if quarter["start"] > current_day),
        None,
    )
    return {
        "in_plan_period": in_plan_period,
        "plan_start": start,
        "plan_end": end,
        "today": {
            "date": current_day,
            "weekday": day_name,
            "type": today_type,
            "focus": today_focus,
            "routine": routine if today_type == "workday" else None,
            "due_date": due_date,
            "expiry_date": expiry_date,
        },
        "week": this_week,
        "month": {
            "number": active_month["month"],
            "start": active_month["start"],
            "end": active_month["end"],
            "focus": active_month["objective"],
            "review_date": active_month["review_date"],
        } if active_month else None,
        "next_month": {
            "number": monthly_review["month"],
            "start": monthly_review["start"],
            "end": monthly_review["end"],
            "focus": monthly_review["objective"],
            "review_date": monthly_review["review_date"],
        } if not active_month and monthly_review else None,
        "quarter": {
            "number": active_quarter["quarter"],
            "title": active_quarter["title"],
            "start": active_quarter["start"],
            "end": active_quarter["end"],
            "focus": active_quarter["objective"],
            "review_date": active_quarter["review_date"],
        } if active_quarter else None,
        "next_quarter": {
            "number": quarterly_review["quarter"],
            "title": quarterly_review["title"],
            "start": quarterly_review["start"],
            "end": quarterly_review["end"],
            "focus": quarterly_review["objective"],
            "review_date": quarterly_review["review_date"],
        } if not active_quarter and quarterly_review else None,
    }


def serialize_plan_schedule(value):
    """Convert dates in a schedule summary to JSON-friendly ISO strings."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize_plan_schedule(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_plan_schedule(item) for item in value]
    return value
