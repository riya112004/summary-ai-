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
    r"validity(?:\s+(?:date|until|till|up\s+to|end\s+date))?)\b",
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
    r"\s+(?=(?:father(?:'s|’s)?\s+name|mother(?:'s|’s)?\s+name|date\s+of\s+birth|"
    r"date\s+of\s+issue|date\s+of\s+expiry|"
    r"dob|birth\s+date|pan|aadhaar|aadhar|passport\s*(?:no|number)?|policy\s*(?:no|number)?|"
    r"document\s*(?:no|number)?|id\s*(?:no|number)?|dl\s*(?:no|number)|"
    r"reference\s*(?:no|number|code)|transaction\s*(?:no|number|id)|"
    r"aadhaar\s*(?:no|number)|"
    r"aadhar\s*(?:no|number)|abha\s*(?:no|number|id)|policy\s*(?:no|number)|"
    r"coverage|sum\s+insured|premium(?:\s+amount)?|total\s+marks|percentage|"
    r"result|issue\s+date|expiry\s+date|valid(?:ity)?(?:\s+(?:date|until|till))?|"
    r"blood\s+group|licen[cs]e|driving|mobile(?:\s+number)?|phone(?:\s+number)?|"
    r"telephone|email)\b)",
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
_PARENT_NAME_LABEL = re.compile(r"\b(?:s|d)\s*/\s*o\b\.?", re.IGNORECASE)
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
_BLOOD_GROUP_LABEL = re.compile(r"\bblood\s+group\b", re.IGNORECASE)
_BLOOD_GROUP_VALUE = re.compile(r"\b(?:AB|A|B|O)\s*[+-](?!\w)", re.IGNORECASE)
_INDIAN_DL_NUMBER = re.compile(
    r"\b[A-Z]{2}\s*-\s*\d{2}\s*-?\s*\d{4}\s*\d{5,7}\b",
    re.IGNORECASE,
)
_NAME_WORDS = re.compile(
    r"[A-Z][A-Z'-]*(?:\s+[A-Z][A-Z'-]*){1,3}",
)


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
        if label_pattern is _HOLDER_LABEL:
            date_match = re.search(_DATE_PATTERN, value, re.IGNORECASE)
            if date_match:
                value = value[:date_match.start()].strip(" \t|,:;")
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
        if match:
            suffix = line[match.end():].strip(" \t:#-/|")
            if suffix:
                value = _NEXT_FIELD_LABEL.split(suffix, maxsplit=1)[0].strip(" \t|,:;")
                date_match = re.search(_DATE_PATTERN, value, re.IGNORECASE)
                if date_match:
                    value = value[:date_match.start()].strip(" \t|,:;")
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

        parent_match = _PARENT_NAME_LABEL.search(line)
        if parent_match:
            value = line[parent_match.end():].strip(" \t:#-/|")
            value = _NEXT_FIELD_LABEL.split(value, maxsplit=1)[0].strip(" \t|,:;")
            if value:
                return value
    return None


def _date_values_precede_labels(text: str) -> bool:
    normalized_text = " ".join(text.split())
    preceding = 0
    following = 0
    for label_pattern in (_DOB_LABEL, _ISSUE_LABEL, _EXPIRY_LABEL):
        for match in label_pattern.finditer(normalized_text):
            prefix = normalized_text[:match.start()]
            suffix = normalized_text[match.end():]
            if re.search(rf"{_DATE_PATTERN}\s*$", prefix, re.IGNORECASE):
                preceding += 1
            if re.match(
                rf"\s*[:#-]?\s*{_DATE_PATTERN}\b",
                suffix,
                re.IGNORECASE,
            ):
                following += 1
    return preceding >= 2 and preceding > following


def _flat_driving_licence_names(
    text: str,
) -> tuple[Optional[str], Optional[str]]:
    normalized_text = " ".join(text.split())
    holder_label = _HOLDER_LABEL.search(normalized_text)
    father_label = _FATHER_NAME_LABEL.search(normalized_text)
    if (
        not holder_label
        or not father_label
        or holder_label.start() > father_label.start()
        or re.search(r"[:=]", normalized_text[holder_label.start():father_label.end()])
    ):
        return None, None

    father_region = normalized_text[holder_label.end():father_label.start()]
    holder_region = normalized_text[father_label.end():]
    holder_date = re.search(_DATE_PATTERN, holder_region, re.IGNORECASE)
    if holder_date:
        holder_region = holder_region[:holder_date.start()]
    father_names = _NAME_WORDS.findall(father_region)
    holder_name = _NAME_WORDS.match(holder_region.strip())
    if father_names and holder_name:
        return holder_name.group(0).strip(), father_names[-1].strip()
    return None, None


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
    text: str,
    label_pattern: re.Pattern[str],
    *,
    prefer_preceding: bool = False,
) -> tuple[bool, Optional[str]]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = label_pattern.search(line)
        if not match:
            continue
        if prefer_preceding:
            line_start = sum(len(previous_line) + 1 for previous_line in lines[:index])
            date_match = re.search(
                rf"({_DATE_PATTERN})\s*$",
                text[:line_start + match.start()][-100:],
                re.IGNORECASE,
            )
            if date_match:
                return True, date_match.group(1)

        suffix = line[match.end():]
        bounded_suffix = _NEXT_FIELD_LABEL.split(suffix, maxsplit=1)[0]
        date_match = re.search(_DATE_PATTERN, bounded_suffix, re.IGNORECASE)
        if date_match:
            return True, date_match.group(0)
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if re.fullmatch(_DATE_PATTERN, next_line, re.IGNORECASE):
                return True, next_line
        return True, None
    return False, None


def _driving_licence_adjacent_dates(
    text: str,
) -> tuple[Optional[str], Optional[str]]:
    """Read issue/validity dates flanking an issue label in flat OCR text."""
    normalized_text = " ".join(text.split())
    for match in _ISSUE_LABEL.finditer(normalized_text):
        preceding_date = re.search(
            rf"({_DATE_PATTERN})\s*$",
            normalized_text[:match.start()],
            re.IGNORECASE,
        )
        following_date = re.match(
            rf"\s*[:#-]?\s*({_DATE_PATTERN})\b",
            normalized_text[match.end():],
            re.IGNORECASE,
        )
        if not preceding_date or not following_date:
            continue
        issue_date = preceding_date.group(1)
        expiry_date = following_date.group(1)
        parsed_issue = _date_from_text(issue_date)
        parsed_expiry = _date_from_text(expiry_date)
        if parsed_issue and parsed_expiry and parsed_expiry > parsed_issue:
            return issue_date, expiry_date
    return None, None


def _document_type(text: str) -> str:
    normalized_text = re.sub(r"\[unclear\]", " ", text, flags=re.IGNORECASE)
    if (
        re.search(r"\bdriv(?:e|ing)?\b", normalized_text, re.IGNORECASE)
        and re.search(r"\blicen[cs]e\b", normalized_text, re.IGNORECASE)
    ):
        return "Driving licence"
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
    document_type = _document_type(text)
    if document_type == "Driving licence" and _date_values_precede_labels(text):
        layout_holder, layout_father = _flat_driving_licence_names(text)
        holder_name = layout_holder or holder_name
        father_name = layout_father or father_name

    document_number = (
        aadhaar_number
        or abha_number
        or policy_number
        or _pan_number(text)
        or _labeled_value(text, _PAN_LABEL)
        or (
            match.group(0).strip()
            if document_type == "Driving licence"
            and (match := _INDIAN_DL_NUMBER.search(text))
            else None
        )
        or (
            candidate
            if _is_identifier_value(candidate := _labeled_value(text, _NUMBER_LABEL))
            else None
        )
    )
    email_match = _EMAIL_PATTERN.search(text)
    phone_value = _labeled_value(text, _PHONE_LABEL)
    phone_match = _PHONE_PATTERN.search(phone_value or "")
    blood_group_match = _BLOOD_GROUP_VALUE.search(text)
    blood_group = (
        blood_group_match.group(0).replace(" ", "").upper()
        if blood_group_match
        else None
    )
    if not blood_group:
        for line in text.splitlines():
            blood_group_label = _BLOOD_GROUP_LABEL.search(line)
            if blood_group_label and re.search(
                r"\[unclear\]\s*$",
                line[:blood_group_label.start()],
                re.IGNORECASE,
            ):
                blood_group = "Unclear"
                break

    prefer_preceding_dates = (
        document_type == "Driving licence"
        and _date_values_precede_labels(text)
    )

    issue_present, issue_date = _find_date_after_label(
        text, _ISSUE_LABEL, prefer_preceding=prefer_preceding_dates
    )
    if issue_present and issue_date:
        issue_date = issue_date.strip()

    dob_present, date_of_birth_text = _find_date_after_label(
        text, _DOB_LABEL, prefer_preceding=prefer_preceding_dates
    )
    if dob_present and date_of_birth_text:
        date_of_birth = date_of_birth_text.strip()

    expiry_present, expiry_date = _find_date_after_label(
        text, _EXPIRY_LABEL, prefer_preceding=prefer_preceding_dates
    )
    if document_type == "Driving licence" and not expiry_present:
        layout_issue_date, layout_expiry_date = (
            _driving_licence_adjacent_dates(text)
        )
        if layout_issue_date and layout_expiry_date:
            issue_date = layout_issue_date
            expiry_present = True
            expiry_date = layout_expiry_date
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
        "document_type": document_type,
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
        "blood_group": blood_group or "Not available",
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
        ("Blood Group", "blood_group"),
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
            (
                "Driving Licence Number"
                if details["document_type"] == "Driving licence"
                else "Document Number",
                "document_number",
            ),
            *field_labels[3:],
        )
    fields = []
    for label, key in field_labels:
        value = details.get(key)
        if value and value != "Not available":
            verification_note = (
                " (verify against the original)"
                if key in {"pan_number", "aadhaar_number", "abha_number",
                           "document_number", "policy_number"}
                else ""
            )
            fields.append(f"- {label}: {value}{verification_note}")

    marks = details.get("marks_details", [])
    fields.extend(f"- Extracted result detail: {line}" for line in marks)
    if details.get("signature_notice"):
        fields.append(
            "- Signature notice: The printed signature wording is unclear; "
            "check the original card."
        )

    summary_sentences = []
    if details["holder_name"] != "Not available":
        subject = (
            f"The {document_type}"
            if details["document_type"] != "Not available"
            else "This document"
        )
        holder_sentence = f"{subject} belongs to **{details['holder_name']}**"
        if details["father_name"] != "Not available":
            holder_sentence += (
                f", whose father's name is **{details['father_name']}**"
            )
        summary_sentences.append(holder_sentence + ".")
    elif details["document_type"] != "Not available":
        summary_sentences.append(f"This is a {document_type}.")

    if (
        details["father_name"] != "Not available"
        and details["holder_name"] == "Not available"
    ):
        summary_sentences.append(
            f"The father's name is **{details['father_name']}**."
        )

    if details["pan_number"] != "Not available":
        summary_sentences.append(
            f"The PAN number is **{details['pan_number']}**; "
            "please verify it against the original card."
        )
    elif details["aadhaar_number"] != "Not available":
        summary_sentences.append(
            f"The Aadhaar number is **{details['aadhaar_number']}**; "
            "please verify it against the original card."
        )
    elif details["abha_number"] != "Not available":
        summary_sentences.append(
            f"The ABHA number is **{details['abha_number']}**; "
            "please verify it against the original card."
        )
    elif (
        details["document_number"] != "Not available"
        and details["document_number"] != details["policy_number"]
    ):
        number_label = (
            "driving licence number"
            if details["document_type"] == "Driving licence"
            else "document number"
        )
        summary_sentences.append(
            f"The {number_label} is **{details['document_number']}**; "
            "please verify it against the original document."
        )
    if details["policy_number"] != "Not available":
        summary_sentences.append(
            f"The policy number is **{details['policy_number']}**."
        )
    if details["date_of_birth"] != "Not available":
        summary_sentences.append(
            f"The date of birth is **{details['date_of_birth']}**."
        )
    if details["issue_date"] != "Not available":
        summary_sentences.append(
            f"The issue date is **{details['issue_date']}**."
        )
    if details["expiry_date"] != "Not available":
        summary_sentences.append(
            f"The expiry/validity date is **{details['expiry_date']}**."
        )
    if details["coverage"] != "Not available":
        summary_sentences.append(f"The coverage is **{details['coverage']}**.")
    if details["premium"] != "Not available":
        summary_sentences.append(f"The premium is **{details['premium']}**.")
    if details["blood_group"] != "Not available":
        summary_sentences.append(
            f"The blood group is **{details['blood_group']}**."
        )
    if details["mobile_or_phone"] != "Not available":
        summary_sentences.append(
            f"The phone number is **{details['mobile_or_phone']}**."
        )
    if details["email"] != "Not available":
        summary_sentences.append(
            f"The email address is **{details['email']}**."
        )
    if marks:
        summary_sentences.append(
            "The marks/result details are: "
            + "; ".join(marks)
            + "."
        )
    if details.get("signature_notice"):
        summary_sentences.append(
            "The signature wording is unclear, so check the original card."
        )
    if not summary_sentences:
        readable_lines = build_source_grounded_summary(text, max_lines=5)
        if readable_lines:
            summary_sentences.append(
                "Readable details include: "
                + "; ".join(
                    line.removeprefix("• ").rstrip(".")
                    for line in readable_lines.splitlines()
                )
                + "."
            )
        else:
            summary_sentences.append(
                "No clear document details could be extracted from the text."
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
