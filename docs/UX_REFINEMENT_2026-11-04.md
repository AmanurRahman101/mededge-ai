# Portal usability refinement — 4 November 2026

This release follows independent design and technical reviews of commit 36b0bbe. It preserves the current product identity and clinical workflow.

## Resolved findings

- Patient language: persistent English/Bangla interface choice, localized navigation, upload/privacy instructions, consent, dates, known errors and medicine controls. Self-hosted Bengali fonts avoid external font requests. Clinical evidence and drug names remain unchanged.
- Patient navigation: equal mobile navigation items; visible search and active filter chips with a clear recovery action.
- Medicine entry: name/strength first, optional registry help afterward. No automatic searches or dose suggestions.
- Publication: outstanding checks link to fields; progress and saved state are visible. Confirmed rows collapse only on request. Both-language review and server validation remain required.
- Record navigation: doctor return links preserve patient/history page; in-memory scroll restoration applies after history loads.
- Accessibility: route heading focus and page titles; larger header hit areas; keyboard menu dismissal and focus return; no theme-switch button contrast animation.
- Saved-content loading: loading, failure and true absence are distinct in prescription and dictated-note review.

## Interfaces

`GET /api/chart/connections` adds `consent_text_bn` for the existing `chart-access-v2` disclosure. Canonical consent scope, version and decision storage remain unchanged. Authorized `GET /api/runs/{id}` adds `patient_id` for chart return navigation. No schema migration is needed.

## Verification

Routine checks use fictional local accounts, generated reports and fake providers. Browser regressions cover language persistence, clinical-name preservation, translated consent, filter clearing, open-menu bounds/dismissal, route focus/title, linked publication requirements, row collapse, saved state, delayed/failed summary loading and returning to the chart. Existing tests cover manual/voice prescriptions, publication, printing, amendments, session changes, draft guards and source comparison.

Review screenshots and print artifacts are generated under gitignored `scripts/out/ui/`. CI runs the backend suite against SQLite and an isolated PostgreSQL service, plus frontend checks and all browser journeys. This is a production-quality demo; no clinical accuracy or real-user usability study is claimed.
