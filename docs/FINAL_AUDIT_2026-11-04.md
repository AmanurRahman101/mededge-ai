# MedEdge functional audit — 4 November 2026

This audit covers the implemented patient/doctor demo, not clinical validation of model output. All automated fixtures use fictional data. Original user reports and credentials are excluded.

## Confirmed defects fixed

| Finding | Change | Evidence |
| --- | --- | --- |
| Cancelling sign-out still revoked the session | Confirm leaving before sending logout; preserve the editor on logout failure | Browser regression asserts zero logout requests after cancellation |
| Native browser Back bypassed unsaved-note protection | Indexed browser history and shared navigation guard restore the current location on cancellation | Browser Back regression retains URL and typed medicine |
| Patient/chart selection disappeared on reload | Doctor patient ID and section are URL state; invalid connections have a recovery message | Reload and Back/Forward browser regression |
| Typing during a slow save could be overwritten by the response | Disable editable prescription/current-medicine fields while saving | Delayed-response browser regression |
| Editing another current medicine could discard unsaved edits | Confirm before switching the edited entry; guard navigation/reload | Explicit save/discard controls, portal journey |
| Session checks made two bootstrap requests and called every failure an account change | One account-bound bootstrap, distinct expired/offline/changed states and explicit retry | Browser regression restores the original draft with one recovery request |
| A hidden stale tab could continue microphone capture | Stop capture when session pauses, including a pending microphone setup; retain captured audio in memory | Browser test with Chromium's fictional microphone |
| Mobile account icon lacked an accessible name | Persistent accessible Account label | axe checks at 320/1440px, both themes |
| Demo cleanup omitted grant dependencies, cached summaries, old current medicines and private files | Delete dependencies before records, invalidate the demo digest, retry failed private-file deletion, restrict cleanup to demo ownership | SQLite foreign-key-on and storage-failure tests; PostgreSQL integration in CI |
| Cleanup errors could prevent startup | Seed before readiness; perform cleanup in the existing guarded maintenance loop | Startup/seed/restart tests |
| Protected chart query links were lost through sign-in | Preserve validated role-specific query URLs | Source/route regression checks |
| Report/recording could be silently abandoned or overwritten by changing modes | Shared leave guard and explicit mode-change confirmation; lock navigation while recording/submitting | Portal and microphone journeys |

## Checks retained

- Backend coverage: registration, verification/recovery, cookies/CSRF, session/account binding, throttling, consent approval/revocation, ownership, files/streams, provider errors, idempotency, draft conflicts, publication/amendments, summary caching and private image/audio storage.
- Frontend: type/build checks, extracted-result assertions, patient/doctor browser journeys, prescription dictation/manual authoring, explicit saving/publication, patient readback and bilingual print.
- Responsive control bounds: 320, 375, 390, 768, 831, 1280, 1440 and 1920px across the portal suite. Both themes receive desktop/mobile checks. Automated accessibility checks supplement visual review; they are not a complete accessibility certification.
- Dependency check: npm reported no known vulnerabilities at audit time. This is not a security certification or a complete Python dependency audit.
- PostgreSQL: CI uses an isolated PostgreSQL 16 service for migrations, auth, atomic email budgeting, consent, summary caching, prescription publication and demo dependency cleanup. Local checks use SQLite.

## Remaining product boundaries

Render is still on its free plan; an idle service can take time to start. No paid infrastructure was purchased. Processing is bounded and explicit retries remain necessary after interruption. Automatic retry on page opening is deliberately absent.

DGHS/DGDA lookup is a reference search, not a complete medicine-stock feed or automatic brand matcher. Unclear medication identity/dose remains for doctor review. Prescription transcription and bilingual clinical content still require clinician evaluation with representative Bangladesh examples before any clinical-production claim.

Published notes remain the only inputs to the patient-wide narrative. Current medicines are explicitly patient-reported. Manual changes and opening pages do not repeat paid prescription processing. Images/audio use private storage until record deletion; real records are excluded from demo cleanup.

The supplied audit IDs and patient annotations remain mapped in `UI_RELEASE_CHECKLIST.md`. Release requires passing CI, the exact commit reported live by Render, and fictional-account live smoke checks. No secrets or clinical source documents belong in evidence artifacts.
