import asyncio
from time import monotonic

import httpx
import pytest

from app.pipeline.medicine_reference import MedicineReference, ReferenceUnavailable
from tests.test_access import access_client as reference_client  # noqa: F401
from tests.test_access import sign_in


def entry(**patch):
    return {
        "id": "fictional-1",
        "owner": "MoHFW",
        "source": "DGDA-Drugs",
        "concept_class": "Drug",
        "retired": False,
        "display_name": "Fictional brand",
        "version": "123",
        "latest_source_version": "v2.0.0",
        "extras": {
            "trade_name": "Fictional brand",
            "generic_content_raw": "Ingredient  ৫ mg",
            "dosage_form": "Tablet",
            "company": "Fictional manufacturer",
        },
        **patch,
    }


async def test_reference_filters_provenance_coalescing_and_cache():
    calls = []

    async def provider(request):
        calls.append(request)
        await asyncio.sleep(0)
        assert request.url.host == "api.tr.ocl.dghs.gov.bd"
        assert request.url.params["source"] == "DGDA-Drugs"
        return httpx.Response(
            200,
            json=[entry(), entry(owner="Other"), entry(retired=True)],
            headers={"num_found": "15"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as http:
        service = MedicineReference(http)
        results = await asyncio.gather(service.search("Napa"), service.search("napa"))
        assert len(calls) == 1
        result = results[0]
        assert len(result["products"]) == 1
        assert result["products"][0]["composition"] == "Ingredient  ৫ mg"
        assert result["products"][0]["source_version"] == "v2.0.0"
        assert result["search_scope"] == "product_names"
        assert result["has_more"] is True
        assert (await service.search("NAPA"))["cached"] is True
        assert len(calls) == 1
        await service.close()


@pytest.mark.parametrize("status", [403, 429, 500, 503])
async def test_provider_failure_is_not_reported_as_no_matches(status):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"detail": "upstream error"})
        )
    ) as http:
        with pytest.raises(ReferenceUnavailable):
            await MedicineReference(http).search("example")


async def test_stale_results_are_labelled_and_bounded():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as http:
        service = MedicineReference(http)
        old = {"products": [entry()], "cached": False, "stale": False}
        service.cache[("example", 1)] = (monotonic() - 4000, old)
        assert (await service.search("example"))["stale"] is True
        service.cache[("example", 1)] = (monotonic() - 90000, old)
        with pytest.raises(ReferenceUnavailable):
            await service.search("example")


def test_reference_auth_validation_and_csrf(request):
    client = request.getfixturevalue("reference_client")
    path = "/api/medicines/search"
    assert client.post(path, json={"query": "Napa"}).status_code in {401, 403}
    sign_in(client, "patient1")
    assert client.post(path, json={"query": "  "}).status_code == 422
    assert client.post(path, json={"query": "Napa", "page": 21}).status_code == 422
    client.headers.pop("x-csrf-token")
    assert client.post(path, json={"query": "Napa"}).status_code == 403
