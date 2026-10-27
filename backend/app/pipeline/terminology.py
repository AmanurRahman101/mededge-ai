import re

import httpx

from app.pipeline.schemas import LoincHit, RxHit

LOINC_SEARCH = "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search"
UCUM_SEARCH = "https://clinicaltables.nlm.nih.gov/api/ucum/v3/search"
RXTERMS_SEARCH = "https://clinicaltables.nlm.nih.gov/api/rxterms/v3/search"

_LOINC = re.compile(r"^\d{1,7}-\d$")


def loinc_check_digit(body: str) -> int:
    """LOINC mod-10 check digit for the digits before the hyphen."""
    total = 0
    for index, char in enumerate(reversed(body), start=1):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (10 - (total % 10)) % 10


def loinc_is_valid(code: str) -> bool:
    if not _LOINC.match(code):
        return False
    body, check = code.split("-")
    return loinc_check_digit(body) == int(check)


def _rows(payload: object) -> list[list]:
    if not isinstance(payload, list) or len(payload) < 4 or not isinstance(payload[3], list):
        return []
    return [row for row in payload[3] if isinstance(row, list)]


async def search_loinc(http: httpx.AsyncClient, term: str, max_list: int = 5) -> list[LoincHit]:
    response = await http.get(LOINC_SEARCH, params={"terms": term, "maxList": max_list})
    response.raise_for_status()
    hits: list[LoincHit] = []
    for row in _rows(response.json()):
        code = str(row[0])
        display = str(row[1]) if len(row) > 1 else code
        if loinc_is_valid(code):
            hits.append(LoincHit(code=code, display=display))
    return hits


async def lookup_ucum(http: httpx.AsyncClient, unit_text: str) -> list[str]:
    response = await http.get(UCUM_SEARCH, params={"terms": unit_text, "maxList": 5})
    response.raise_for_status()
    return [str(row[0]) for row in _rows(response.json()) if row]


async def search_rxterms(http: httpx.AsyncClient, name: str) -> list[RxHit]:
    response = await http.get(RXTERMS_SEARCH, params={"terms": name, "maxList": 5, "ef": "RXCUIS"})
    response.raise_for_status()
    payload = response.json()
    hits: list[RxHit] = []
    for row in _rows(payload):
        drug = str(row[0])
        rxcui = str(row[1]) if len(row) > 1 and row[1] else None
        hits.append(RxHit(name=drug, rxcui=rxcui))
    return hits
