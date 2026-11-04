# UI hardening audit disposition

The supplied reports overlap and contain credentials; neither raw report is copied here. This release preserves cards leading to focused charts, one active browser account, and the existing demo scope.

| IDs | Assessment | Resolution |
|---|---|---|
| V-01–V-07, V-09–V-12 | Confirmed | Bounded containers, compact spacing, aligned source/forms and responsive sections |
| V-08, V-13 | Confirmed | Theme-aware icon details and differentiated navigation icons |
| R-01–R-05 | Confirmed | Wrapping accessible mobile navigation, viewport-contained menu alignment and compact header |
| F-01, F-06 | Confirmed workflow issue | Account-bound requests, cross-tab pause, explicit role feedback and draft navigation guard |
| F-02 | Confirmed | Print variables reset to white/dark text; editor/source excluded |
| F-03 | Confirmed feedback issue | Keep pre-hash throttling; failed-login counter separated and Retry-After provided |
| F-04 | Incorrect | Disconnect already required confirmation; retained |
| F-05 | Confirmed | Desktop source/extraction comparison, zoom and source files |
| F-07–F-09, F-11–F-13 | Confirmed or requiring browser regression | URL state, home navigation, form feedback and recoverable errors reviewed in release checks |
| F-10 | Outside scope | Appointments and doctor discovery deliberately excluded |

Validation uses fictional local fixtures and fake providers. CI exercises SQLite/PostgreSQL, frontend build and browser journeys. Release deployment must match the reviewed commit and be followed by a fictional-account live smoke test. Do not infer clinical accuracy from UI tests.


## Patient annotations — 4 November

| Comment | Resolution | Regression evidence |
|---|---|---|
| 1 | Search stays visible; only type/status/archive filters expand | Visible searchbox assertion |
| 2 | Removed recent-changes entrypoint | Absence assertion |
| 3–4 | One bilingual health narrative; no duplicate heading or category fragments | Versioned model output and narrative browser assertions |
| 5 | Persistent patient-reported current medicines; never inferred from old prescriptions | Ownership, consent, CSRF, idempotency, persistence and browser add/remove tests |
| 6–7 | No report links in patient summary; internal provenance retained | Zero source-link nodes assertion |
| 8–10 | Notes, provisional readings and report index live in Detailed history | Deep-link, refresh, return and absence-on-summary checks |

The narrative uses published doctor history and latest amendments, with no second approval. New scans and unreviewed transcripts remain provisional until publication. Narrative results are cached by a versioned fingerprint. List edits and navigation do not repeat paid inference. Medicine-list changes record current use; they do not prescribe starting or stopping treatment.


## Medicine reference and prescription authoring — 4 November

- Official public DGHS/OCL product-name search is connected with fixed source filters, authenticated same-origin access, bounded concurrency/timeouts, coalesced caching and honest outage/stale states. No bulk catalogue is bundled or scraped.
- Patients retain manual medicine entry and now have optimistic edit controls. Registry suggestions are optional and do not prescribe dosing.
- Consented doctors can create voice-only or manual prescriptions without an image. Voice stages persist the original audio and transcript; explicit retry reuses completed transcription.
- Medicine rows preserve strengths separately from morning/noon/night amounts, fractions, explicit zeros, custom schedules, instructions and duration. Missing details remain blank. Doctors can add, remove and edit rows.
- Publication requires row confirmation, bilingual review and an optimistic draft revision. Published prescriptions remain immutable and amendments reset medicine confirmation. Patient records/history/printing and the cached chart narrative include the reviewed table.
- New routes inherit session/account/CSRF checks and chart consent; pending/revoked doctors cannot create, retry, edit, publish or read protected prescriptions/audio. Real external FHIR export remains disabled.
- Verification includes SQLite tests, PostgreSQL migration/publication in CI, responsive browser journeys, a rendered bilingual prescription PDF, and a bounded fictional live smoke check after deployment.
