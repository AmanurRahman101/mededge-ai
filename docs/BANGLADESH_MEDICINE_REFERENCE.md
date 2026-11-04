# Bangladesh medicine reference for MedEdge

Verified 2026-11-04 (Asia/Dhaka) with anonymous, read-only HTTPS GET requests. No account, paid service, bulk dataset download, or external mutation was used.

## Decision

Use the **official DGHS-hosted OCL public concept search through MedEdge's backend**, with bounded response caching and source attribution. It supplies Bangladesh product identity and composition text. It is not a complete clinical monograph, price feed, or verified pharmacy availability feed. Keep manual entry available.

The working API host is `https://api.tr.ocl.dghs.gov.bd`, disclosed by the official terminology browser's [public configuration](https://tr.ocl.dghs.gov.bd/env-config.js). The `tr.ocl.dghs.gov.bd` host serves the browser UI, including on URLs that look like API paths.

## Working search and actual response

[Working Napa search](https://api.tr.ocl.dghs.gov.bd/concepts/?q=Napa&source=DGDA-Drugs&owner=MoHFW&conceptClass=Drug&limit=2&verbose=true):

```http
GET /concepts/?q=Napa&source=DGDA-Drugs&owner=MoHFW&conceptClass=Drug&limit=2&verbose=true
```

HTTP 200, JSON array; no authorization header required. Response headers included `X-OCL-REQUEST-USER: AnonymousUser`, `X-OCL-API-VERSION: 2.3.201-dev`, `num_found: 35`, `num_returned: 2`, `pages: 18`, `page_number: 1`, and an absolute `next` URL carrying `page=2`.

Relevant fields from the first returned concept:

```json
{
  "id": "186-0153-006--napa",
  "display_name": "Napa",
  "owner": "MoHFW",
  "source": "DGDA-Drugs",
  "concept_class": "Drug",
  "retired": false,
  "version": "466802",
  "latest_source_version": "v2.0.0",
  "extras": {
    "company": "Beximco Pharmaceuticals Ltd.",
    "dar_number": "186-0153-006",
    "trade_name": "Napa",
    "dosage_form": "Suppository",
    "dar_quality_flag": "",
    "generic_content_raw": "Paracetamol  250 mg"
  }
}
```

Map brand to `extras.trade_name` (fallback `display_name`), manufacturer to `extras.company`, form to `extras.dosage_form`, and composition/strength display to **the unchanged** `extras.generic_content_raw`. There are no separate normalized generic and strength fields in the inspected products. Preserve the concept ID, DAR number, version, source, and fetch time; DAR alone is not a guaranteed unique product key (`shared_dar` quality flags occur). Do not silently select a strength or form from brand alone.

An inspected [Tericin mapping](https://api.tr.ocl.dghs.gov.bd/orgs/MoHFW/sources/DGDA-Drugs/concepts/341-0160-020--tericin/mappings/) has `map_type: Has-active-ingredient`, `to_concept_name: Amphotericin B`, `to_concept_code: XM5TR4`, and target source `ICD-11-MMS`. This establishes one actual ingredient mapping, not universal mapping completeness.

## Search semantics and limitations

| Verified query (same filters above) | `num_found` | Observation |
| --- | ---: | --- |
| `Napa` | 35 | Multiple strengths/forms; first example above |
| `Histacin` | 5 | Injection 10 mg/ml and tablet 4 mg from Jayson seen |
| `paracetamol` | 36 | First results are products literally named Paracetamol |
| `chlorpheniramine` | 5 | First results literally named Chlorpheniramine |
| `nap` | 245 | Includes H-Nap and Napguard; not exact brand matching |
| `Tericin` | 4 | Includes Teracin; relevance/fuzzy matching occurs |

The [OCL concept API documentation](https://docs.openconceptlab.org/en/latest/oclapi/apireference/concepts.html) describes text search over concept IDs, names, and descriptions. It does not document searching custom composition extras. **Generic-name queries are not demonstrated to return every branded product containing that ingredient.** Present this as product/brand search with composition shown, not a complete ingredient-to-brand lookup.

The source, owner, and concept-class filters were checked using invalid filter values, each of which produced zero results. Still validate these fields before accepting upstream results. URL-encode query input, bound query length/result count, debounce requests, and handle timeout/429/5xx distinctly from a genuine empty result.

**Do not use the source-scoped `.../sources/DGDA-Drugs/concepts/?q=...` or collection-scoped search:** both returned empty arrays even for the known existing Tericin product. The top-level `/concepts/` search with filters works.

## Counts, pagination, and versions

- [Source HEAD listing](https://api.tr.ocl.dghs.gov.bd/orgs/MoHFW/sources/DGDA-Drugs/concepts/?limit=2&verbose=true) returned `num_found: 39196`; [collection HEAD listing](https://api.tr.ocl.dghs.gov.bd/orgs/MoHFW/collections/dgda-registered-drugs-valueset/concepts/?limit=1&verbose=true) returned **39195**. The one-item discrepancy was not resolved.
- [Released source versions](https://api.tr.ocl.dghs.gov.bd/orgs/MoHFW/sources/DGDA-Drugs/versions/) include `v2.0.0` (2026-10-14, released true), `v1.0.0`, and mutable unreleased `HEAD`. `v2.0.0` uses the current DGHS canonical URL. Search results inspected expose `latest_source_version: v2.0.0` and individual concept versions.
- Release-scoped `v2.0.0/concepts/?limit=1` returned zero, despite nonempty HEAD. Adding `sourceVersion=v2.0.0` to global search cannot establish pinning: `sourceVersion=INVALID` produced the same results. Do not claim the search is pinned to a release.
- Standard OCL pagination uses `limit`, `page`, and response headers. [OCL overview](https://docs.openconceptlab.org/en/latest/oclapi/overview.html) recommends pages of at most 100 and honoring `Retry-After`. The integration should fetch only a bounded page per user search, not mirror the registry.
- The existing released [export GET](https://api.tr.ocl.dghs.gov.bd/orgs/MoHFW/sources/DGDA-Drugs/v2.0.0/export/) returned HTTP 500 with `NoCredentialsError`; no usable export was obtained. No export creation was attempted.
- CORS responses allowed `https://tr.ocl.dghs.gov.bd`; use the backend rather than relying on browser cross-origin fetches. No SLA or published deployment-specific rate limit was found. Successful spot checks do not establish ongoing availability.

## Provenance and data rights

The official [CodeSystem](https://fhir.dghs.gov.bd/core/CodeSystem-dgda-drug-registry.html) attributes registration ownership to DGDA and terminology curation/mapping to DGHS. Its current canonical is `https://fhir.dghs.gov.bd/core/CodeSystem/dgda-drug-registry`. The [ValueSet](https://fhir.dghs.gov.bd/core/ValueSet-dgda-registered-drugs.html) documents 39,196 products and no FHIR `$expand` support. These pages are BD Core IG 0.5.0; that is distinct from OCL dataset release v2.0.0.

The [ImplementationGuide JSON](https://fhir.dghs.gov.bd/core/ImplementationGuide-bd.fhir.core.json) declares `license: CC0-1.0`. However, its CodeSystem is a stub without product concepts, and the registry pages separately assert DGDA data ownership. Source and collection API metadata say `public_access: View` and `copyright: null`. **No explicit license granting bulk republication of the product registry was established.** Public read access is documented by [OCL permissions](https://docs.openconceptlab.org/en/latest/oclapi/apireference/permissionssummary.html); it is not itself a data redistribution license. Attribute live results to “DGDA registration data, curated by DGHS via the national OCL terminology service.” Obtain explicit applicable terms before bulk importing, bundling, or republishing the registry.

## Alternatives assessed

- [MedEx terms](https://medex.com.bd/terms-of-use) restrict use to personal, noncommercial purposes and prohibit automated data extraction without express written consent. No documented licensed public API was verified. Do not scrape MedEx or infer permission from third-party packages.
- [BDDrugBank's creator-published Zenodo record](https://zenodo.org/records/20749707) describes a September 2025 MedEx-derived snapshot of 24,725 products. Its [record metadata](https://zenodo.org/api/records/20749707) declares CC-BY-4.0, but that does not establish upstream MedEx permission; the linked GitHub repository returned 404 during verification. No data archive was downloaded. It is not a clean rights substitute without clarification.


## MedEdge connection

`POST /api/medicines/search` accepts `{ "query": "Napa", "page": 1 }` under the existing authenticated cookie and CSRF protections. Search text is placed in the request body rather than the app's access-log URL. The backend fixes the upstream host and source filters, validates returned ownership/type/retirement metadata, limits a page to ten products and accepts at most twenty pages per query. Responses preserve raw composition rather than inventing separate strength/ingredient fields.

The service coalesces equal searches, allows at most two simultaneous upstream calls and four pending searches, and caches at most 128 result pages. Positive results cache for one hour, empty results five minutes. During failure, nonempty cached results younger than one day can be returned explicitly labelled stale; a failed request is never represented as a genuine empty match. The cache is temporary per Render process. No bulk mirror, background sync, source API credential or database keepalive is introduced.

Lookup appears in patient manual medicine entry, doctor report reading, and each editable prescription row. Manual input remains available. Choosing a product in a prescription fills the name/form only; the doctor checks the reported composition against the prescribed strength.
