# MedEdge AI interface

The patient and doctor portals are clinical workspaces. The visual language uses the supplied pixel heart, stethoscope and clinical SVG icons for navigation and information categories. Forms and clinical text use conventional, readable typography.

## Tokens

Keep Geist for body text and headings, Geist Mono for connection codes. Body text is 16px; supporting interface text is 13–14px. Workspace headings are 24–32px, section headings 20px. Preserve the zinc light/dark palette and footer. Blue identifies selection and source links; amber identifies unresolved details; rose identifies private regions and errors.

## Layout

Workspaces use up to 1480px with 32px desktop gutters. The doctor workspace has a 264px patient directory and a flexible chart column. Summary, History and Add report & note are separate sections. At 760px the directory stacks above the chart and allows horizontal patient selection. Forms and bilingual editors use two columns on laptops and one on phones. No desktop workflow is constrained to a phone-width column.

Patient navigation separates My records, Doctors & consent, My summary and Activity. Report management is a native details menu that can be opened and closed. Record pages separate Doctor notes, Report reading, and Image & recording. Privacy review keeps its confirmation beside the preview; confirmation stays disabled until the image loads.

## Summary hierarchy

The patient-wide overview appears first, in English or Bangla, with source links. It is automatically generated from published doctor notes only, with no second verification step. Latest amendments replace superseded text in the overview. Source notes and provisional image readings remain separate expandable sections. Provisional OCR never becomes an input to the combined narrative. Historical medicines must not be described as current without explicit supporting documentation.

## Controls

Use 8px button corners, 10px panels and 1px zinc separators. Keep one primary next action per step. Secondary work remains in its relevant tab or disclosure. Show errors, saving state, upload preparation, processing progress and explicit retries. No FHIR controls, raw bundles or implementation trace panels appear in either portal. Keep the existing account, sign-out and theme actions.

## Verification

Browser journeys use a fictional local SQLite fixture and fake model provider. Test desktop and phone sizes in both themes, dropdown closing, privacy preview, saved drafts, publication, and automatic summary updates. Backend coverage checks consent, cache invalidation, revocation during generation, deletion, amendments and provider failure. Do not use real patient documents in test fixtures.
