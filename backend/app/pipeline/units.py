import re

# Printed South Asian unit spellings mapped to UCUM. The value is copied unchanged.
_DIALECTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^lakh/?c(?:umm|mm)$", re.I), "10*5/uL"),
    (re.compile(r"^lakhs?/?c(?:umm|mm)$", re.I), "10*5/uL"),
    (re.compile(r"^gm\s*%$|^gm%$", re.I), "g/dL"),
    (re.compile(r"^mg\s*%$|^mg%$", re.I), "mg/dL"),
    (re.compile(r"^/?c(?:umm|mm)$", re.I), "/uL"),
    (re.compile(r"^cells?/c(?:umm|mm)$", re.I), "/uL"),
    (re.compile(r"^mm/?1st\s*hr$|^mm/hr$|^mm/hour$", re.I), "mm/h"),
    (re.compile(r"^thou/?c(?:umm|mm)$|^10\^3/c(?:umm|mm)$", re.I), "10*3/uL"),
    (re.compile(r"^mill/?c(?:umm|mm)$|^10\^6/c(?:umm|mm)$", re.I), "10*6/uL"),
    (re.compile(r"^iu/l$", re.I), "[IU]/L"),
    (re.compile(r"^u/l$", re.I), "U/L"),
    (re.compile(r"^pg$", re.I), "pg"),
    (re.compile(r"^fl$", re.I), "fL"),
    (re.compile(r"^g/dl$", re.I), "g/dL"),
    (re.compile(r"^mg/dl$", re.I), "mg/dL"),
    (re.compile(r"^mmol/l$", re.I), "mmol/L"),
    (re.compile(r"^umol/l$|^µmol/l$", re.I), "umol/L"),
    (re.compile(r"^ng/ml$", re.I), "ng/mL"),
    (re.compile(r"^pg/ml$", re.I), "pg/mL"),
    (re.compile(r"^%$|^percent$", re.I), "%"),
]


def normalize_unit(unit_text: str | None) -> str | None:
    if unit_text is None:
        return None
    cleaned = " ".join(unit_text.strip().split())
    if not cleaned:
        return None
    for pattern, ucum in _DIALECTS:
        if pattern.match(cleaned):
            return ucum
    return cleaned
