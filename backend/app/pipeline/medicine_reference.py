"""Bounded, attributed search of the public DGHS/DGDA terminology service."""

import asyncio
import copy
import json
from collections import OrderedDict
from datetime import UTC, datetime
from time import monotonic
from urllib.parse import quote

import httpx

API = "https://api.tr.ocl.dghs.gov.bd"
SYSTEM = "https://fhir.dghs.gov.bd/core/CodeSystem/dgda-drug-registry"
ATTRIBUTION = "DGDA registration data, curated by DGHS via the national OCL terminology service"


class ReferenceUnavailable(Exception):
    pass


def text(value, limit=600):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value if len(value) <= limit else ""


def product(item):
    if (
        not isinstance(item, dict)
        or (item.get("owner"), item.get("source"), item.get("concept_class"))
        != ("MoHFW", "DGDA-Drugs", "Drug")
        or item.get("retired") is not False
    ):
        return None
    extras = item.get("extras")
    if not isinstance(extras, dict):
        extras = {}
    code = text(item.get("id"), 300)
    brand = text(extras.get("trade_name") or item.get("display_name"), 160)
    if not code or not brand:
        return None
    return {
        "code": code,
        "brand": brand,
        "composition": text(extras.get("generic_content_raw")),
        "form": text(extras.get("dosage_form"), 120),
        "manufacturer": text(extras.get("company"), 200),
        "dar_number": text(extras.get("dar_number"), 100),
        "quality_flag": text(extras.get("dar_quality_flag"), 120),
        "concept_version": text(item.get("version"), 80),
        "source_version": text(item.get("latest_source_version"), 80),
        "source_updated_at": text(item.get("updated_on"), 80),
        "source_url": f"{API}/orgs/MoHFW/sources/DGDA-Drugs/concepts/{quote(code, safe='')}/",
    }


class MedicineReference:
    def __init__(self, http):
        self.http = http
        self.cache = OrderedDict()
        self.pending = {}
        self.capacity = asyncio.Semaphore(2)

    async def close(self):
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def search(self, query: str, page: int = 1):
        key = (" ".join(query.split()).casefold(), page)
        cached = self.cache.get(key)
        ttl = 3600 if cached and cached[1]["products"] else 300
        if cached and monotonic() - cached[0] < ttl:
            self.cache.move_to_end(key)
            return {**copy.deepcopy(cached[1]), "cached": True}
        task = self.pending.get(key)
        if task is None:
            if len(self.pending) >= 4:
                raise ReferenceUnavailable("Medicine search is busy. Try again in a moment.")
            task = asyncio.create_task(self._fetch(key))
            self.pending[key] = task

            def finished(done):
                self.pending.pop(key, None)
                if not done.cancelled():
                    done.exception()

            task.add_done_callback(finished)
        try:
            return copy.deepcopy(await asyncio.shield(task))
        except ReferenceUnavailable:
            if cached and cached[1]["products"] and monotonic() - cached[0] < 86400:
                return {**copy.deepcopy(cached[1]), "cached": True, "stale": True}
            raise

    async def _fetch(self, key):
        query, page = key
        async with self.capacity:
            try:
                async with self.http.stream(
                    "GET",
                    f"{API}/concepts/",
                    params={
                        "q": query,
                        "source": "DGDA-Drugs",
                        "owner": "MoHFW",
                        "conceptClass": "Drug",
                        "verbose": "true",
                        "limit": 10,
                        "includeRetired": "false",
                        "page": page,
                    },
                    timeout=httpx.Timeout(10, connect=4),
                    follow_redirects=False,
                ) as response:
                    if response.status_code != 200:
                        raise ReferenceUnavailable("Medicine reference is temporarily unavailable.")
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 1_000_000:
                            raise ValueError("Oversized reference response")
                    rows = json.loads(content)
                    if not isinstance(rows, list) or len(rows) > 10:
                        raise ValueError("Invalid reference response")
                    products = [p for item in rows if (p := product(item))]
                    # An invalid upstream result is never presented as a genuine empty match.
                    if rows and not products:
                        raise ValueError("Unexpected reference source")
                    total = int(response.headers.get("num_found", len(products)))
                    if not 0 <= total <= 1_000_000:
                        raise ValueError("Invalid result count")
            except (httpx.HTTPError, ValueError, TypeError):
                raise ReferenceUnavailable(
                    "Medicine reference is temporarily unavailable."
                ) from None
        result = {
            "products": products,
            "total": total,
            "page": page,
            "has_more": page < 20 and page * 10 < total,
            "checked_at": datetime.now(UTC).isoformat(),
            "attribution": ATTRIBUTION,
            "system": SYSTEM,
            "search_scope": "product_names",
            "cached": False,
            "stale": False,
        }
        self.cache[key] = (monotonic(), result)
        self.cache.move_to_end(key)
        while len(self.cache) > 128:
            self.cache.popitem(last=False)
        return result
