# MedEdge AI

MedEdge is a two-role clinical record demo. React and FastAPI are served together on Render. Neon stores accounts, consent, readings and published notes. Private object storage retains report images and recordings. Resend delivers authentication emails. Meta processes consented images and voice.

Patients upload reports, review redaction, manage history and explicitly approve or revoke doctor access. Doctors open patient summary cards, review source and extraction side by side, dictate bilingual notes, explicitly save drafts and publish reviewed notes. Published revisions are immutable; corrections use amendments. Patient-wide summaries use only published doctor history and are cached by input version.

The UI uses Geist typography, zinc themes and pixel workspace/category icons. Patient cards lead to focused charts. Technical FHIR/trace controls are excluded. Shared demo accounts contain fictional examples. Public clinical-production readiness is not claimed.

Authentication uses one active secure cookie session per browser. Existing tabs pause when the active account changes. Draft revisions prevent stale saves. No credentials or clinical drafts belong in browser persistent storage or test screenshots.

The patient summary separates a plain-language, cached health narrative from detailed history. Patients maintain an explicit current-medicines list, visible to consented doctors and independent of past prescriptions. It records reported use, not a new prescription.

Doctors can now start a new prescription with voice only or manual entry, without an image. Voice is transcribed once and structured into editable medicine rows; the doctor confirms each row before publishing. Original audio persists in private storage, structured prescriptions in Neon. Published prescriptions are immutable; amendments require fresh row confirmation. Patient-wide summaries include the published prescription table. Current medicines remain an explicit patient-reported list with add/edit/remove controls.

Medicine lookup uses the public DGHS-hosted DGDA registry through an authenticated same-origin search endpoint. Searches are explicit, bounded and cached; no model calls or registry mirroring are involved. Results provide brand, raw composition, form, manufacturer and source identifiers. Product-name search is supported; complete generic-to-brand search and pharmacy-stock claims are not supported. Manual entry remains available during registry outages.
