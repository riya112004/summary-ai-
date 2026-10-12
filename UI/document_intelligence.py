"""Deterministic extraction and expiry calculations for stored document text."""

import re
from datetime import date, datetime
from typing import Any, Optional


_DATE_PATTERN = (
    r"(?:\d{4}[./-]\d{1,2}[./-]\d{1,2}"
    r"|\d{1,2}[./-]\d{1,2}[./-]\d{4}"
    r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
    r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"
)
_EXPIRY_LABEL = re.compile(
    r"\b(?:date\s+of\s+expiry|expiry(?:\s+date)?|"
    r"expiration(?:\s+date)?|expires?(?:\s+on)?|"
    r"valid\s+(?:until|till|through|thru|upto|up\s+to)|"
    r"validity\s+(?:until|till|up\s+to|end\s+date))\b",
    re.IGNORECASE,
)
_ISSUE_LABEL = re.compile(
    r"\b(?:issue\s+date|date\s+of\s+issue|issued\s+on)\b", re.IGNORECASE
)
_DOB_LABEL = re.compile(
    r"\b(?:date\s+of\s+birth|dob|birth\s+date)\b", re.IGNORECASE
)
_AADHAAR_LABEL = re.compile(
    r"\b(?:aadhaar|aadhar)(?:\s+(?:number|no\.?|#))\b", re.IGNORECASE
)
_ABHA_LABEL = re.compile(
    r"\babha(?:\s+(?:number|no\.?|id|#))\b", re.IGNORECASE
)
_POLICY_LABEL = re.compile(
    r"\bpolicy\s*(?:no\.?|number|#)\b", re.IGNORECASE
)
_COVERAGE_LABEL = re.compile(
    r"\b(?:coverage|sum\s+insured|insured\s+amount|benefit\s+amount)\b",
    re.IGNORECASE,
)
_PREMIUM_LABEL = re.compile(r"\bpremium(?:\s+amount)?\b", re.IGNORECASE)
_NEXT_FIELD_LABEL = re.compile(
    r"\s+(?=(?:father(?:'s)?\s+name|mother(?:'s)?\s+name|date\s+of\s+birth|"
    r"dob|pan|aadhaar|aadhar|passport\s*(?:no|number)?|policy\s*(?:no|number)?|"
    r"document\s*(?:no|number)?|id\s*(?:no|number)?|dl\s*(?:no|number)|"
    r"reference\s*(?:no|number|code)|transaction\s*(?:no|number|id)|"
    r"date\s+of\s+birth|dob|birth\s+date|aadhaar\s*(?:no|number)|"
    r"aadhar\s*(?:no|number)|abha\s*(?:no|number|id)|policy\s*(?:no|number)|"
    r"coverage|sum\s+insured|premium(?:\s+amount)?|total\s+marks|percentage|"
    r"result|issue\s+date|"
    r"date\s+of\s+issue|expiry\s+date|date\s+of\s+expiry|valid\s+until|"
    r"mobile(?:\s+number)?|phone(?:\s+number)?|telephone|email)\b)",
    re.IGNORECASE,
)
_HOLDER_LABEL = re.compile(
    r"\b(?:holder(?:'s)?\s+name|name\s+of\s+(?:the\s+)?(?:holder|insured)|"
    r"insured\s+name|cardholder|name)\b",
    re.IGNORECASE,
)
_NUMBER_LABEL = re.compile(
    r"\b(?:(?:document|identity|id|policy|passport|certificate|membership|"
    r"account|card|visa|licen[cs]e|dl)\s*(?:no\.?|number|#)\b|"
    r"reference\s*(?:no\.?|number|code)|transaction\s*(?:no\.?|number|id)|"
    r"(?:aadhaar|aadhar|abha)\s*(?:no\.?|number|id|#)\b)",
    re.IGNORECASE,
)
_PAN_LABEL = re.compile(r"\bpan\s*(?:(?:no\.?|number|#)\s*)?[:=#-]\s*", re.IGNORECASE)
_FATHER_NAME_LABEL = re.compile(r"\bfather(?:'s|’s)?\s+name\b", re.IGNORECASE)
_PAN_VALUE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_OCR_PAN_VALUE = re.compile(
    r"\b(?=[A-Z0-9]{10}\b)(?=(?:[A-Z0-9]*\d){3})"
    r"(?=[A-Z0-9]*[A-Z])[A-Z0-9]{10}\b"
)
_SIGNATURE_NOTICE = re.compile(
    r"card.{0,12}valid.{0,12}physically\s+signed|"
    r"physically\s+signed.{0,12}card",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_LABEL = re.compile(
    r"\b(?:mobile(?:\s+number)?|phone(?:\s+number)?|telephone|contact\s+number)\b",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")


def _date_from_text(raw_value: str) -> Optional[date]:
    value = raw_value.strip().strip(".,;:")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
                "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    numeric = re.fullmatch(r"(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})", value)
    if not numeric:
        return None
    first, second, third = numeric.groups()
    if len(first) == 4 and len(third) <= 2:
        year, month, day = int(first), int(second), int(third)
    elif len(third) == 4 and len(first) <= 2:
        first_num, second_num, year = int(first), int(second), int(third)
        if first_num > 12:
            day, month = first_num, second_num
        elif second_num > 12:
            month, day = first_num, second_num
        else:
            return None
    else:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _labeled_value(text: str, label_pattern: re.Pattern[str]) -> Optional[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = label_pattern.search(line)
        if not match:
            continue
        if label_pattern is _HOLDER_LABEL and re.search(
            r"\b(?:father|mother)\s*['’]?s?\s*$",
            line[:match.start()],
            re.IGNORECASE,
        ):
            continue
        value = line[match.end():].lstrip(" \t:#-/|")
        value = _NEXT_FIELD_LABEL.split(value, maxsplit=1)[0].strip(" \t|,:;")
        if value:
            return value
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip(" \t:#-/|")
            if next_line and not _NEXT_FIELD_LABEL.match(next_line):
                return next_line
    return None


def _father_name(text: str) -> Optional[str]:
    for line in text.splitlines():
        match = _FATHER_NAME_LABEL.search(line)
        if not match:
            continue
        suffix = line[match.end():].strip(" \t:#-/|")
        if suffix:
            value = _NEXT_FIELD_LABEL.split(suffix, maxsplit=1)[0].strip(" \t|,:;")
            if value:
                return value
        prefix = line[:match.start()]
        # OCR sometimes places the value before the field label; accept only a
        # contiguous sequence of uppercase name-like words, not nearby OCR noise.
        names = re.findall(
            r"(?<![A-Za-z])([A-Z][A-Z'-]*(?:\s+[A-Z][A-Z'-]*){1,3})(?=\s|$)",
            prefix,
        )
        if names:
            return names[-1].strip()
    return None


def _pan_number(text: str) -> Optional[str]:
    exact_match = _PAN_VALUE.search(text)
    if exact_match:
        return exact_match.group(0)
    if not re.search(r"\b(?:PAN|Permanent\s+Account\s+Number)\b", text, re.IGNORECASE):
        return None
    ocr_match = _OCR_PAN_VALUE.search(text)
    return ocr_match.group(0) if ocr_match else None


def _is_identifier_value(value: Optional[str]) -> bool:
    return bool(
        value
        and sum(character.isdigit() for character in value) >= 1
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 /()._-]{2,39}", value)
    )


def _find_date_after_label(
    text: str, label_pattern: re.Pattern[str]
) -> tuple[bool, Optional[str]]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = label_pattern.search(line)
        if not match:
            continue
        date_match = re.search(_DATE_PATTERN, line[match.end():], re.IGNORECASE)
        if date_match:
            return True, date_match.group(0)
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if re.fullmatch(_DATE_PATTERN, next_line, re.IGNORECASE):
                return True, next_line
        return True, None
    return False, None


def _document_type(text: str) -> str:
    known_types = (
        (r"\bmarksheet\b|\bmark\s+sheet\b|\btranscript\b", "Marksheet"),
        (r"\bbonafide\b", "Bonafide Certificate"),
        (r"\bPAN\b|permanent account number", "PAN card"),
        (r"\bAadhaar\b|\bAadhar\b", "Aadhaar card"),
        (r"\bABHA\b|ayushman bharat health account", "ABHA card"),
        (r"\bpassport\b", "Passport"),
        (r"\bdriving licence\b|\bdriving license\b", "Driving licence"),
        (r"\bvoter(?:'s)? id\b|election commission", "Voter ID"),
        (r"\bvisa\b", "Visa"),
        (r"\binsurance\b|\binsured\b|\bpolicy\b", "Insurance document"),
        (r"\bcertificate\b", "Certificate"),
    )
    for pattern, label in known_types:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return "Not available"


def assess_extracted_text(text: str) -> Optional[str]:
    """Return a review reason when stored OCR text is too weak to summarize."""
    normalized = text.strip()
    letters = sum(character.isalpha() for character in normalized)
    if len(normalized) < 20 or letters < 10:
        return "Saved extracted text is too short or contains too little readable text."
    visible = sum(not character.isspace() for character in normalized)
    if visible and letters / visible < 0.2:
        return "Saved extracted text appears too noisy for a reliable summary."
    return None


def extract_document_fields(
    text: str,
    *,
    today: Optional[date] = None,
    expiring_soon_days: int = 30,
) -> dict[str, Any]:
    """Return exact source values and a date-derived expiry status."""
    holder_name = _labeled_value(text, _HOLDER_LABEL)
    father_name = _father_name(text)
    aadhaar_number = _labeled_value(text, _AADHAAR_LABEL)
    abha_number = _labeled_value(text, _ABHA_LABEL)
    policy_number = _labeled_value(text, _POLICY_LABEL)
    coverage = _labeled_value(text, _COVERAGE_LABEL)
    premium = _labeled_value(text, _PREMIUM_LABEL)
    date_of_birth = _labeled_value(text, _DOB_LABEL)
    document_number = (
        aadhaar_number
        or abha_number
        or policy_number
        or _pan_number(text)
        or _labeled_value(text, _PAN_LABEL)
        or (
            candidate
            if _is_identifier_value(candidate := _labeled_value(text, _NUMBER_LABEL))
            else None
        )
    )
    email_match = _EMAIL_PATTERN.search(text)
    phone_value = _labeled_value(text, _PHONE_LABEL)
    phone_match = _PHONE_PATTERN.search(phone_value or "")

    issue_present, issue_date = _find_date_after_label(text, _ISSUE_LABEL)
    if issue_present and issue_date:
        issue_date = issue_date.strip()

    dob_present, date_of_birth_text = _find_date_after_label(text, _DOB_LABEL)
    if dob_present and date_of_birth_text:
        date_of_birth = date_of_birth_text.strip()

    expiry_present, expiry_date = _find_date_after_label(text, _EXPIRY_LABEL)
    parsed_expiry = _date_from_text(expiry_date) if expiry_date else None
    current_date = today or date.today()

    if not expiry_present:
        expiry_status = "unavailable"
    elif parsed_expiry is None:
        expiry_status = "verification_required"
    else:
        days_remaining = (parsed_expiry - current_date).days
        if days_remaining < 0:
            expiry_status = "expired"
        elif days_remaining <= expiring_soon_days:
            expiry_status = "expiring_soon"
        else:
            expiry_status = "valid"

    days_remaining = (
        (parsed_expiry - current_date).days if parsed_expiry is not None else None
    )
    if parsed_expiry is not None and expiry_date not in text:
        expiry_status = "verification_required"
        parsed_expiry = None
        days_remaining = None

    marks_lines = [
        line.strip()
        for line in text.splitlines()
        if re.search(
            r"\b(?:marks?|score|subject|total|percentage|percent|result|grade|"
            r"cgpa|sgpa)\b",
            line,
            re.IGNORECASE,
        )
        and line.strip()
    ]

    return {
        "document_type": _document_type(text),
        "holder_name": holder_name or "Not available",
        "father_name": father_name or "Not available",
        "pan_number": _pan_number(text) or "Not available",
        "document_number": document_number or "Not available",
        "aadhaar_number": aadhaar_number or "Not available",
        "abha_number": abha_number or "Not available",
        "policy_number": policy_number or "Not available",
        "mobile_or_phone": phone_match.group(0).strip() if phone_match else "Not available",
        "email": email_match.group(0) if email_match else "Not available",
        "date_of_birth": date_of_birth or "Not available",
        "issue_date": issue_date or "Not available",
        "coverage": coverage or "Not available",
        "premium": premium or "Not available",
        "marks_details": marks_lines,
        "expiry_date": expiry_date or "Not available",
        "expiry_status": expiry_status,
        "days_remaining": days_remaining,
        "expiry_date_iso": parsed_expiry.isoformat() if parsed_expiry else None,
        "signature_notice": bool(_SIGNATURE_NOTICE.search(text)),
    }


def validate_extractive_summary(summary: str, source_text: str) -> list[str]:
    """Accept only non-empty summary bullets copied exactly from the source."""
    bullets: list[str] = []
    for line in summary.splitlines():
        item = re.sub(r"^\s*(?:[-*•]\s*|\d+[.)]\s*)", "", line).strip()
        item = item.strip("\"'")
        if not item:
            continue
        if item not in source_text:
            raise ValueError("The generated summary could not be verified against the extracted text.")
        bullets.append(item)
    if not bullets:
        raise ValueError("The local model returned no verifiable summary points.")
    return bullets


def build_source_grounded_summary(text: str, max_lines: int = 12) -> str:
    """Select useful source lines verbatim when the local model output is unsafe."""
    candidates: list[tuple[int, int, str]] = []
    for index, raw_line in enumerate(text.splitlines()):
        line = raw_line.strip()
        visible = [character for character in line if not character.isspace()]
        letters = sum(character.isalpha() for character in visible)
        digits = sum(character.isdigit() for character in visible)
        if len(line) < 5 or len(line) > 500 or letters < 3:
            continue
        if letters / len(visible) < 0.25:
            continue

        score = min(letters, 50) + min(digits, 12)
        if re.search(
            r"\b(name|number|no\.?|dob|birth|date|issue|expiry|valid|"
            r"marks?|total|percentage|result|policy|premium|coverage|"
            r"certificate|bonafide|aadhaar|aadhar|abha|pan|licen[cs]e)\b",
            line,
            re.IGNORECASE,
        ):
            score += 30
        if re.search(
            r"\b(permanent account number|government|department|"
            r"school|student|insurance|driving|marksheet|certificate)\b",
            line,
            re.IGNORECASE,
        ):
            score += 20
        candidates.append((score, index, line))

    selected = sorted(
        sorted(candidates, key=lambda candidate: (-candidate[0], candidate[1]))[
            :max_lines
        ],
        key=lambda candidate: candidate[1],
    )
    return "\n".join(f"• {line}" for _, _, line in selected)


def build_document_summary(text: str) -> str:
    """Create a readable summary only from source-verified document fields."""
    details = extract_document_fields(text)
    document_type = details["document_type"]
    if document_type == "PAN card":
        document_type = "Permanent Account Number (PAN) Card"
    elif document_type == "Not available":
        document_type = "Document"

    field_labels = (
        ("Name", "holder_name"),
        ("Father's Name", "father_name"),
        ("PAN Number", "pan_number"),
        ("Date of Birth", "date_of_birth"),
        ("Issue Date", "issue_date"),
        ("Expiry / Validity Date", "expiry_date"),
        ("Policy Number", "policy_number"),
        ("Coverage", "coverage"),
        ("Premium", "premium"),
        ("ABHA Number", "abha_number"),
        ("Aadhaar Number", "aadhaar_number"),
        ("Mobile / Phone", "mobile_or_phone"),
        ("Email", "email"),
    )
    if (
        details["document_number"] != "Not available"
        and details["document_number"] not in {
            details["pan_number"],
            details["aadhaar_number"],
            details["abha_number"],
            details["policy_number"],
        }
    ):
        field_labels = (
            *field_labels[:3],
            ("Document Number", "document_number"),
            *field_labels[3:],
        )
    fields = []
    for label, key in field_labels:
        value = details.get(key)
        if value and value != "Not available":
            verification_note = (
                " (OCR value; verify against the original)"
                if key in {"pan_number", "aadhaar_number", "abha_number",
                           "document_number", "policy_number"}
                else ""
            )
            fields.append(f"- {label}: {value}{verification_note}")

    marks = details.get("marks_details", [])
    fields.extend(f"- Extracted result detail: {line}" for line in marks)
    if details.get("signature_notice"):
        fields.append(
            "- Signature notice: The OCR text mentions physical signing; "
            "check the original card because the extracted wording is unclear."
        )

    summary_sentences = [
        f"The saved OCR text identifies this as a {document_type}."
    ]
    if details["holder_name"] != "Not available":
        summary_sentences.append(
            f"The saved OCR text identifies the holder as {details['holder_name']}."
        )
    if details["father_name"] != "Not available":
        summary_sentences.append(
            f"It lists the father's name as {details['father_name']}."
        )
    if details["pan_number"] != "Not available":
        summary_sentences.append(
            f"The OCR text contains PAN number {details['pan_number']}; "
            "verify its characters against the original document."
        )
    elif details["aadhaar_number"] != "Not available":
        summary_sentences.append(
            f"The OCR text contains Aadhaar number {details['aadhaar_number']}; "
            "verify it against the original document."
        )
    elif details["abha_number"] != "Not available":
        summary_sentences.append(
            f"The OCR text contains ABHA number {details['abha_number']}; "
            "verify it against the original document."
        )
    elif (
        details["document_number"] != "Not available"
        and details["document_number"] != details["policy_number"]
    ):
        summary_sentences.append(
            f"It lists document number {details['document_number']}; "
            "verify it against the original document."
        )
    if details["policy_number"] != "Not available":
        summary_sentences.append(
            f"It lists policy number {details['policy_number']}."
        )
    if details["date_of_birth"] != "Not available":
        summary_sentences.append(
            f"It records the date of birth as {details['date_of_birth']}."
        )
    if details["issue_date"] != "Not available":
        summary_sentences.append(
            f"It records the issue date as {details['issue_date']}."
        )
    if details["expiry_date"] != "Not available":
        summary_sentences.append(
            f"The printed validity date is {details['expiry_date']}."
        )
    if details["coverage"] != "Not available":
        summary_sentences.append(f"It lists coverage as {details['coverage']}.")
    if details["premium"] != "Not available":
        summary_sentences.append(f"It lists premium as {details['premium']}.")
    if details["mobile_or_phone"] != "Not available":
        summary_sentences.append(
            f"The extracted text lists phone number {details['mobile_or_phone']}."
        )
    if details["email"] != "Not available":
        summary_sentences.append(
            f"The extracted text lists email address {details['email']}."
        )
    if marks:
        summary_sentences.append(
            "The extracted text also contains these marks/result lines: "
            + "; ".join(marks)
            + "."
        )
    if len(summary_sentences) == 1:
        readable_lines = build_source_grounded_summary(text, max_lines=5)
        if readable_lines:
            summary_sentences.append(
                "The saved OCR text contains these readable lines: "
                + "; ".join(
                    line.removeprefix("• ").rstrip(".")
                    for line in readable_lines.splitlines()
                )
                + "."
            )
        else:
            summary_sentences.append(
                "No readable details could be reliably extracted from the saved text."
            )

    body = "\n".join(fields) if fields else "No reliable labeled fields were found."
    return (
        f"## {document_type} Details\n"
        f"Document Type: {document_type}\n\n"
        f"{body}\n\n"
        "### Summary\n"
        + " ".join(summary_sentences)
    )


def expiry_alert_priority(document: dict[str, Any]) -> int:
    return {
        "expired": 0,
        "expiring_soon": 1,
        "verification_required": 2,
    }.get(document.get("expiry_status"), 3)
