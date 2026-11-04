# MedEdge AI interface

The patient and doctor portals are clinical workspaces. The visual language uses the supplied pixel heart, stethoscope and clinical SVG icons for navigation and information categories. Forms and clinical text use conventional, readable typography.

## Tokens

Keep Geist for body text and headings, Geist Mono for connection codes. Body text is 16px; supporting interface text is 13–14px. Workspace headings are 24–32px, section headings 20px. Preserve the zinc light/dark palette and footer. Blue identifies selection and source links; amber identifies unresolved details; rose identifies private regions and errors.

## Layout

Workspaces use centered 1200px containers; desktop document review uses up to 1440px. The doctor workspace has a 264px patient directory and a flexible chart column. Summary, History and Add report & note are separate sections. At 760px the directory stacks above the chart and allows horizontal patient selection. Forms and bilingual editors use two columns on laptops and one on phones. No desktop workflow is constrained to a phone-width column.

Patient navigation separates My records, My doctors and My summary. Search stays visible on the records page; advanced filters remain optional. Activity is not part of the primary patient flow. Report management is a native details menu that can be opened and closed. Record pages separate Doctor notes, Report reading, and Image & recording. Privacy review keeps its confirmation beside the preview; confirmation stays disabled until the image loads.

## Summary hierarchy

The patient summary is a coherent plain-language narrative in English or Bangla, without source-link clutter or categorized fragments. Internal provenance stays available to doctors. It is automatically generated from published doctor notes only, with no second verification step. Latest amendments replace superseded text in the overview. Patient source notes, provisional image readings and the report index live in a dedicated Detailed history view. The summary links to that view once. Provisional OCR never becomes an input to the combined narrative. Historical medicines must not be described as current without explicit supporting documentation.

## Controls

Use 8px button corners, 10px panels and 1px zinc separators. Keep one primary next action per step. Secondary work remains in its relevant tab or disclosure. Show errors, saving state, upload preparation, processing progress and explicit retries. No FHIR controls, raw bundles or implementation trace panels appear in either portal. Keep the existing account, sign-out and theme actions.

## Verification

Browser journeys use a fictional local SQLite fixture and fake model provider. Test desktop and phone sizes in both themes, dropdown closing, privacy preview, saved drafts, publication, and automatic summary updates. Backend coverage checks consent, cache invalidation, revocation during generation, deletion, amendments and provider failure. Do not use real patient documents in test fixtures.

## Current medicines

The patient summary shows an explicitly patient-reported current-medicines list, with name/strength, optional instructions and confirmation date. Historical prescriptions never automatically become active medicines. Patients can add or remove entries; consented doctors can read the list but cannot rewrite the patient’s report of current use. List operations do not call a model.

## Prescription authoring

The doctor's Add report & note section offers Report & note or New prescription. New prescriptions offer Dictate a prescription or Write manually. The prescription editor keeps identity/strength/form together, distinguishes morning/noon/night amounts from strength, and preserves custom schedules and duration. Unknown slots stay blank and an explicit zero remains zero. Each row has a confirmation checkbox and an optional spoken-evidence/registry disclosure. Publishing requires row review and review of English/Bangla assessment text. Patient names, author/date and a bilingual medication table appear in the printed prescription.

Registry lookup searches only when the user selects Search or presses Enter. Selecting a reference never prescribes a dose or replaces treatment automatically. Patients can still type and edit current medicines manually; doctors can type, add, remove and edit prescription rows after dictation.

## Entry pages

Keep the landing page's two workspace choices and pixel illustrations. Each choice has a workspace title, one short description and one action. Authentication uses a centered 440px form with persistent labels and no promotional sidebar. Sign-up uses simple patient/doctor choices; the doctor credential disclosure remains visible when selected. Recovery, verification and fictional demo access remain available, with secondary sign-in options collapsed below the main form. Preserve the footer and both themes.

## Patient language and review clarity

Patients choose English or Bangla once per device; the initial choice follows the browser language. Translate interface controls, consent, privacy instructions, known error messages and dates without rewriting clinical evidence, medicine names or the doctor's authored text. Use self-hosted Noto Sans Bengali for Bengali glyphs and Geist for Latin text. Keep the original footer. Language changes never trigger processing or discard an unfinished medicine form.

Patient mobile navigation uses three equal icon-and-label choices, without uneven wrapping. Keep search visible, show active filters with Clear filters, and put optional medicine-reference search after direct medicine entry. Doctor record links retain the patient and history page. Route changes focus the destination heading and update the document title.

Prescription and dictated-note publication show linked outstanding checks rather than only a disabled button. Confirmed medication rows may be collapsed explicitly and reopened for editing. Changes still invalidate confirmation. Display saved/unsaved/saving status; keep English and Bangla assessment editors beside each other on desktop. Loading failures must never appear as an empty saved prescription. Do not animate button background colors across a theme switch because transient foreground/background mismatches reduce contrast.
