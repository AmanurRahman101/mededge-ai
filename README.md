# MedEdge AI

MedEdge AI turns paper lab reports, handwritten prescriptions, and spoken visit notes into verified HL7 FHIR R4 bundles.

**MedEdge AI is an administrative data interoperability and optical ingestion pipeline, not a clinical decision or diagnostic tool.** It does not diagnose, interpret health status, or suggest treatment.

Built for the [Meta Global AI Developer Hackathon](https://dev.meta.ai/events/global-hackathon) (October 26 to November 4, 2026), Indie Developer track.

## Who it is for

- **Patients** photograph a report or prescription, confirm that personal details are hidden, and share the record with a doctor.
- **Doctors** open that share, dictate the visit note, review the structured result, and export it.

## Status

Day 1. The backend can route each job across Meta Model API, a hosted open-weight partner, and a self-hosted Muse Glimmer server, and it falls back automatically when one is down. Segmentation, extraction, the FHIR agent, and the interface are still being built. Every commit in this repository is new work from the hackathon window.

## Models

| Job | Model |
| --- | --- |
| Find the page, the results table, and items to hide | SAM 3.1 |
| Read the redacted page | Muse Spark Open, or Muse Glimmer on Colab, with Muse Spark 1.3 as fallback |
| Transcribe the visit note | Muse Voice Transcribe |
| Structure the visit and build the FHIR bundle | Muse Spark 1.3 |

## Run the backend

Requires Python 3.11.

```powershell
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -e "backend[dev]"
copy .env.example .env
backend\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload
```

Put your Meta Model API key in `.env`. That file is gitignored. Do not commit it.

```powershell
cd backend
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check app tests
```

`scripts/smoke_meta.py` calls the live Meta endpoints and spends a small amount of credit.

## Patient documents

Real reports and prescriptions go in `data/private/`. That folder is gitignored. Do not commit photographs of real documents, and do not commit anything that still shows a name, phone number, or ID.
