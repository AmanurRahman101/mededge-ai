# MedEdge AI

MedEdge is a two-role clinical record demo. React and FastAPI are served together on Render. Neon stores accounts, consent, readings and published notes. Private object storage retains report images and recordings. Resend delivers authentication emails. Meta processes consented images and voice.

Patients upload reports, review redaction, manage history and explicitly approve or revoke doctor access. Doctors open patient summary cards, review source and extraction side by side, dictate bilingual notes, explicitly save drafts and publish reviewed notes. Published revisions are immutable; corrections use amendments. Patient-wide summaries use only published doctor history and are cached by input version.

The UI uses Geist typography, zinc themes and pixel workspace/category icons. Patient cards lead to focused charts. Technical FHIR/trace controls are excluded. Shared demo accounts contain fictional examples. Public clinical-production readiness is not claimed.

Authentication uses one active secure cookie session per browser. Existing tabs pause when the active account changes. Draft revisions prevent stale saves. No credentials or clinical drafts belong in browser persistent storage or test screenshots.
