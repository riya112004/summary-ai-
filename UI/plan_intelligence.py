"""Date-aware summaries for uploaded work plans."""

import hashlib
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


def _tabular_date(value: str) -> Optional[date]:
    value = value.strip()
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _tabular_time(value: str) -> Optional[int]:
    match = re.fullmatch(
        r"\s*(\d{1,2}):(\d{2})\s*(AM|PM)?\s*(?:\(next\s+day\))?\s*",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    meridiem = (match.group(3) or "").upper()
    next_day = bool(re.search(r"\(next\s+day\)", value, re.IGNORECASE))
    if minute > 59:
        return None
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem == "PM" else 0)
    elif hour > 24 or (hour == 24 and minute != 0):
        return None
    total = hour * 60 + minute
    if next_day:
        total += 24 * 60
    return total


def _tabular_schedule_rows(text: str) -> Optional[list[dict]]:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or "|" not in lines[0]:
        return None

    headers = [
        re.sub(r"[^a-z0-9]+", "_", cell.strip().lower()).strip("_")
        for cell in lines[0].split("|")
    ]
    aliases = {
        "date": {"date", "schedule_date", "task_date", "event_date"},
        "activity": {"activity", "title", "task", "event", "meeting"},
        "start_time": {"start_time", "start", "from_time"},
        "end_time": {"end_time", "end", "to_time"},
        "category": {"category", "type", "event_type"},
        "details": {"details", "description", "notes"},
        "location": {"location", "where", "venue"},
        "priority": {"priority", "importance"},
        "status": {"status", "state"},
    }
    columns = {
        field: next(
            (headers.index(alias) for alias in names if alias in headers),
            None,
        )
        for field, names in aliases.items()
    }
    if columns["date"] is None or columns["activity"] is None:
        return None

    entries = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        row = {
            field: cells[index] if index is not None and index < len(cells) else ""
            for field, index in columns.items()
        }
        row_date = _tabular_date(row["date"])
        if row_date is None or not row["activity"]:
            continue
        category = row["category"]
        entries.append({
            "date": row_date.isoformat(),
            "activity": row["activity"],
            "category": category,
            "details": row["details"],
            "location": row["location"],
            "priority": row["priority"],
            "status": row["status"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "start_minute": _tabular_time(row["start_time"]),
            "end_minute": _tabular_time(row["end_time"]),
            "is_meeting": bool(re.search(
                r"\b(meeting|appointment|calendar event)\b",
                f"{category} {row['activity']}",
                re.IGNORECASE,
            )),
        })
    return entries


def build_tabular_schedule_summary(
    text: str,
    *,
    today: Optional[date] = None,
) -> Optional[dict]:
    """Read today's events from extracted pipe-delimited schedule data."""
    all_entries = _tabular_schedule_rows(text)
    if all_entries is None:
        return None

    current_day = today or date.today()
    observed_dates = [date.fromisoformat(entry["date"]) for entry in all_entries]
    entries = [
        entry for entry in all_entries
        if date.fromisoformat(entry["date"]) == current_day
    ]

    entries.sort(
        key=lambda item: (
            item["start_minute"] is None,
            item["start_minute"] if item["start_minute"] is not None else 0,
        )
    )
    return {
        "in_plan_period": bool(
            observed_dates and min(observed_dates) <= current_day <= max(observed_dates)
        ),
        "today": {
            "date": current_day,
            "weekday": current_day.strftime("%A"),
            "type": "scheduled" if entries else "unscheduled",
            "focus": entries[0]["activity"] if entries else "No activities scheduled.",
            "routine": None,
            "due_date": current_day,
            "expiry_date": current_day,
        },
        "entries": entries,
        "week": None,
        "month": None,
        "next_month": None,
        "quarter": None,
        "next_quarter": None,
    }


def build_plan_tasks(text: str, plan_id: str) -> list[dict]:
    """Turn explicit schedule themes and review objectives into stable task records."""
    schedule_entries = _tabular_schedule_rows(text)
    if schedule_entries is not None:
        tasks = []
        occurrences = {}
        for entry in schedule_entries:
            task_date = date.fromisoformat(entry["date"])
            identity = "\x1f".join((
                entry["date"],
                entry["start_time"],
                entry["end_time"],
                entry["category"],
                entry["activity"],
            ))
            fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
            occurrence = occurrences.get(fingerprint, 0)
            occurrences[fingerprint] = occurrence + 1
            description_parts = [
                entry["category"],
                entry["details"],
                f"Location: {entry['location']}" if entry["location"] else "",
                (
                    f"Time: {entry['start_time']}–{entry['end_time']}"
                    if entry["start_time"] or entry["end_time"]
                    else ""
                ),
                f"Priority: {entry['priority']}" if entry["priority"] else "",
            ]
            tasks.append({
                "source_key": f"{plan_id}:csv:{fingerprint}:{occurrence}",
                "plan_document_id": plan_id,
                "task_type": "csv_schedule",
                "title": entry["activity"],
                "description": " · ".join(part for part in description_parts if part),
                "category": entry["category"],
                "priority": entry["priority"],
                "start_time": entry["start_time"],
                "end_time": entry["end_time"],
                "task_date": task_date.isoformat(),
                "due_date": task_date.isoformat(),
                "expiry_date": (task_date + timedelta(days=3)).isoformat(),
            })
        return tasks

    period_match = re.search(r"(?im)^Period:\s*(.+)$", text)
    plan_period = _parse_date_range(period_match.group(1)) if period_match else None
    if not plan_period:
        return []

    start, end = plan_period
    themes = _weekday_themes(text)
    quarters, months = _parse_sections(text)
    tasks = []
    current_day = start
    while current_day <= end:
        weekday = current_day.weekday()
        weekday_name = current_day.strftime("%A")
        theme = themes.get(weekday_name)
        if weekday < 5 and theme:
            due_date = current_day + timedelta(days=4 - weekday)
            tasks.append({
                "source_key": f"{plan_id}:day:{current_day.isoformat()}",
                "plan_document_id": plan_id,
                "task_type": "daily",
                "title": f"{weekday_name}: {theme}",
                "description": theme,
                "task_date": current_day.isoformat(),
                "due_date": due_date.isoformat(),
                "expiry_date": (due_date + timedelta(days=3)).isoformat(),
            })
        current_day += timedelta(days=1)

    for month in months:
        objective = month.get("objective")
        review_date = month.get("review_date")
        if objective:
            due_date = review_date or month["end"]
            tasks.append({
                "source_key": f"{plan_id}:month:{month['year']}:{month['month']}:goal",
                "plan_document_id": plan_id,
                "task_type": "monthly_goal",
                "title": f"Month {month['month']} goal: {objective}",
                "description": objective,
                "task_date": month["start"].isoformat(),
                "due_date": due_date.isoformat(),
                "expiry_date": (due_date + timedelta(days=3)).isoformat(),
            })
        if review_date:
            tasks.append({
                "source_key": f"{plan_id}:month:{month['year']}:{month['month']}:review",
                "plan_document_id": plan_id,
                "task_type": "monthly_review",
                "title": f"Monthly review: Month {month['month']}",
                "description": "Review completed tasks, deadlines, quality, estimates, and unresolved issues.",
                "task_date": review_date.isoformat(),
                "due_date": review_date.isoformat(),
                "expiry_date": (review_date + timedelta(days=3)).isoformat(),
            })

    for quarter in quarters:
        objective = quarter.get("objective")
        review_date = quarter.get("review_date")
        if objective:
            due_date = review_date or quarter["end"]
            tasks.append({
                "source_key": f"{plan_id}:quarter:{quarter['year']}:{quarter['quarter']}:goal",
                "plan_document_id": plan_id,
                "task_type": "quarterly_goal",
                "title": f"Quarter {quarter['quarter']} goal: {objective}",
                "description": objective,
                "task_date": quarter["start"].isoformat(),
                "due_date": due_date.isoformat(),
                "expiry_date": (due_date + timedelta(days=3)).isoformat(),
            })
        if review_date:
            tasks.append({
                "source_key": f"{plan_id}:quarter:{quarter['year']}:{quarter['quarter']}:review",
                "plan_document_id": plan_id,
                "task_type": "quarterly_review",
                "title": f"Quarterly review: Q{quarter['quarter']} {quarter['title']}",
                "description": "Review progress, skills, outcomes, workload, and goals.",
                "task_date": review_date.isoformat(),
                "due_date": review_date.isoformat(),
                "expiry_date": (review_date + timedelta(days=3)).isoformat(),
            })

    return tasks


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
