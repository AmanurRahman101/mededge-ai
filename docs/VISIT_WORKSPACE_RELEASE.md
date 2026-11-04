# Visit workspace release — 4 November 2026

MedEdge now follows patient → health overview → visit → reviewed prescription/report/note.
The supplied pixel identity, Geist, zinc themes and footer are retained.

## Delivered

- Independent doctor workspaces. Active patient consent is required throughout; another doctor cannot edit a visit or inspect an unrelated doctor's open visit. Completed visits can be read by other consented doctors.
- Explicit Start visit, resumable open consultations, dated lists, completion checks, safe empty-visit/draft discard and stable URLs. Each patient/doctor pair has at most one open visit; concurrent starts converge on it.
- Patient-owned prescriptions, report images, voice recordings and notes grouped by their originating visit. Existing reports can be referenced without moving their source or ownership. Old records remain under Earlier records; dates/authors/visits are not guessed.
- Report plus voice creates structured editable medication rows from separate image and spoken evidence. Identity, strength, morning/noon/night amounts, special schedule, instructions and duration remain separate. Unknowns stay blank; explicit zero and fractions survive. Conflicting identities remain flagged.
- Explicit DGHS/DGDA Bangladesh reference search during review; manual name entry and correction remain available. Listing is not pharmacy stock or proof that an uncertain reading is correct. Selecting a reference does not choose a dose.
- Doctor confirmation for each retained row and both language versions before publication. Published medication tables are readable by the patient and included in printing; later changes are attributed amendments.
- Desktop source/editor comparison with zoom and fit-width; phone Source/Review controls. File availability failures preserve the saved structured reading.
- Compact navigation rail on laptops; labelled mobile navigation. Plain health narrative, patient-reported current medicines, consent controls and saved reports remain separate tasks. Technical FHIR/trace panels remain excluded.
- Existing cookie/CSRF/account-change handling, draft navigation guards, expected revisions, private file retention and summary caching preserved. Page opening never repeats paid report processing.

## Validation

Local checks: backend **128 passed**, isolated PostgreSQL test skipped locally; frontend build and result rendering passed; **25 browser journeys** cover this release. Release CI additionally runs migrations, concurrent visit starts, publication, revocation and cleanup against PostgreSQL 16 before the deployment branch is advanced. The initial release passed **129 backend tests** including PostgreSQL and **24 browser journeys**; the follow-up adds a regression for the shared-demo upload restriction.

Browser coverage includes 320, 375, 390, 768, 1280, 1440 and 1920px in both themes; actual control bounds; keyboard/menu dismissal; account changes; draft conflicts; patient/doctor navigation; manual and voice-only prescriptions; combined report/voice → privacy review → correction → save/reopen → publication → patient readback; visit completion; bilingual print contrast.

New backend regressions cover two patients/two doctors, private open visits, completed read-only sharing, revoked access, patient ownership, retained legacy records, idempotency, completion blockers and safe discard. Provider fixtures use fictional evidence. PostgreSQL cleanup includes referenced records and stale demo visits.

Visual review found and corrected a source/editor alignment defect; the regression checks their actual vertical alignment, not only visibility. The design detector returned no findings for the new care module. Screenshots initially labelled as patient visits were recaptured on the correct Visits surface before final review.

Live checks on the initial release passed using a fictional saved prescription and sample dictation: Meta processing, medication correction, draft reopen, publication, patient table readback, visit completion and matching original-image/audio hashes for both roles. Shared demo accounts intentionally reject uploaded images; the follow-up hides that unavailable input and directs shared-demo users to fictional sample reports. Ordinary verified accounts retain image upload.

## Evidence

Browser CI uploads `workspace-browser-checks`. Local captures live in gitignored `scripts/out/ui/`:

- `visits-doctor-desktop-light.png`, `visits-doctor-mobile-dark.png`
- `visits-patient-desktop-light.png`, `visits-patient-mobile-dark.png`
- `visit-medication-desktop.png`
- `prescription-print.pdf`, `published-note.pdf`

## Rollout and limits

The additive `20261104_visits` Alembic migration preserves accounts, consent, structured history and original ownership. No legacy records are assigned to invented visits. Restore a backup for schema rollback rather than dropping visit history.

Review branch: `codex/visit-workspaces`. Release branch: `codex/mededge-auth-deploy`; Render automatically deploys commits to that branch. Check that no reports are processing before advancing it, then verify the exact commit live and fictional patient/doctor journeys.

This is a production-quality demo, not a claim of clinical-production readiness. Doctor workspaces are account-scoped; hospital teams, appointment booking, pharmacy stock, fine-tuning and an automatic treatment recommendation are not included. Neither tests nor catalogue lookup establish Bangladeshi handwriting recognition accuracy; clinician-reviewed examples remain necessary for that assessment. Routine tests use fake providers; any live provider smoke is bounded and fictional.
