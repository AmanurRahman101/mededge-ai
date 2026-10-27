import re

_SLOT = re.compile(r"(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)")
_WHEN = {
    0: "MORN",
    1: "NOON",
    2: "NIGHT",
}
_MEAL = (
    (re.compile(r"after\s+meal|pc\b|post\s*prandial", re.I), "PC"),
    (re.compile(r"before\s+meal|ac\b|pre\s*prandial|empty\s+stomach", re.I), "AC"),
    (re.compile(r"with\s+meal|with\s+food", re.I), "C"),
)


def dose_timing(dose_text: str | None, timing_text: str | None) -> dict | None:
    """Turn a written schedule such as '1+0+1' into FHIR timing, without adding advice.

    Returns None when the text is not a morning-noon-night pattern. The original
    words stay on Dosage.text either way.
    """
    if not dose_text:
        return None
    match = _SLOT.search(dose_text)
    if not match:
        return None
    counts = [float(match.group(i)) for i in (1, 2, 3)]
    when = [_WHEN[i] for i, count in enumerate(counts) if count > 0]
    if not when:
        return None
    doses = len(when)
    for pattern, code in _MEAL:
        if timing_text and pattern.search(timing_text) and code not in when:
            when.append(code)
            break
    # Timing has no text field. The printed words stay on Dosage.text.
    return {
        "repeat": {
            "frequency": doses,
            "period": 1,
            "periodUnit": "d",
            "when": when,
        }
    }
