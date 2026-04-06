import re


# Patterns for PII removal before sending to OpenAI
_PATTERNS = [
    (re.compile(r"\+?\d[\d\s\-()]{8,}\d"), "[PHONE]"),
    (re.compile(r"[A-Za-zА-Яа-яЁё0-9._%+-]+@[A-Za-zА-Яа-яЁё0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    # Cyrillic full names: "Иванов Иван Иванович"
    (re.compile(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+"), "[ФИО]"),
    # Passport-like numbers
    (re.compile(r"[A-ZА-Я]{2}\d{7}"), "[DOC_NUMBER]"),
    # Dates of birth in common formats (dd.mm.yyyy)
    (re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b"), "[DATE]"),
]


def anonymize(text: str) -> str:
    result = text
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result
