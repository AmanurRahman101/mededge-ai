# MedEdge AI

MedEdge AI turns paper lab reports, handwritten prescriptions, and spoken visit notes into verified HL7 FHIR R4 bundles.

**MedEdge AI is an administrative data interoperability and optical ingestion pipeline, not a clinical decision or diagnostic tool.** It does not diagnose, interpret a result, or suggest treatment.

Built for the [Meta Global AI Developer Hackathon](https://dev.meta.ai/events/global-hackathon) (October 26 to November 4, 2026), Indie Developer track. Every commit in this repository is new work from that window.

## Two roles

- **Patients** add a report, confirm what is hidden, see the values exactly as printed, and share a 6-character code.
- **Doctors** open that code or upload a report, dictate an administrative visit note, review the result, and approve the export.

Patients and doctors can register with an email address and password. Accounts require email verification; a doctor account is self-declared and is not verification of medical credentials. The fictional guest demo does not require an account and does not call models or create runs.

## Architecture

```mermaid
flowchart LR
  photo[Report photo] --> sam[SAM 3.1 regions]
  photo --> ocr[Local OCR anchors]
  sam --> redact[Dewarp and blur]
  ocr --> redact
  redact --> confirm[User confirms the overlay]
  confirm --> extract[Extractor]
  mic[Visit dictation] --> asr[Muse Voice Transcribe]
  asr --> encounter[Encounter structurer]
  extract --> agent[FHIR agent]
  encounter --> agent
  agent --> verify[Verifier]
  verify --> export[FHIR R4 export]
```

The full page goes to SAM 3.1 only, or stays on the machine when `SAM_PROVIDER=local`. A language model receives the redacted page after the user confirms the overlay. The Patient resource is a session pseudonym. `store` is false on Meta calls. Zero Data Retention is claimed only if Meta enables it on the account.

Prescriptions are transcribed. A dose such as `1+0+1` is copied into FHIR timing. The app adds no dose advice and no interaction check.

## Models

| Job | Model |
| --- | --- |
| Page, table, barcode, signature, stamp, photo | SAM 3.1 |
| Read the redacted page | Partner Muse Spark Open, else Muse Glimmer on Colab, else Muse Spark 1.3 |
| Transcribe | Muse Voice Transcribe |
| Structure the visit and build the bundle | Muse Spark 1.3 |

Set the extractor chain in `.env`, for example `ROLE_EXTRACTOR=glimmer:muse-glimmer,meta:muse-spark-1.3`. The result names the model that actually answered. `colab/glimmer_server.ipynb` serves Muse Glimmer on an L4. A Colab session can die, so the hosted demo must keep Muse Spark 1.3 in the chain.

## Checks

The bundle is checked for R4 schema, internal references, LOINC check digits, UCUM units, a one-to-one match with the source rows, and a policy that rejects diagnoses and computed interpretations. If the agent cannot produce a valid bundle, a deterministic assembler does, and the screen says "Assembled by fallback." "Inject a fault" adds one labeled failure so the repair is visible.

## Run it

Python 3.11 and Node 22.

```powershell
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -e "backend[dev]"
copy .env.example .env
backend\.venv\Scripts\python -m alembic -c backend\alembic.ini upgrade head
backend\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload
```

```powershell
cd frontend
npm install
npm run dev
```

The app is at http://localhost:5173. In development, verification and password-reset emails are saved as `.eml` files in `backend/var/mail/`; open the newest file to use its link. These files contain authentication links and are gitignored. Put `MODEL_API_KEY` in `.env` to use live model features. Fictional samples remain available as recorded readings without a key.

```powershell
backend\.venv\Scripts\python -m pytest -c backend\pyproject.toml backend\tests
backend\.venv\Scripts\python -m ruff check backend\app backend\tests
backend\.venv\Scripts\python scripts\eval.py
```

`scripts/smoke_meta.py` calls the live Meta API and spends credit. Do not run it unless you mean to.

## Evaluation

`scripts/eval.py` checks the fictional sample sheets. These numbers are the deterministic pieces, not a claim about model accuracy:

| Check | Result |
| --- | --- |
| Unit dialects (`lakh/cumm`, `gm%`, `mg%`, `/cumm`, `mm/1st hr`, `mmol/L`) | 6/6 |
| LOINC check digits on five known codes | 5/5 |
| Sample ground truth assembled into a valid bundle | 3/3 |

`python scripts/eval.py --live` adds one extractor call when `MODEL_API_KEY` is set and reports how many printed names matched. That number is filled in after a live run. It is not invented here.

## Data

`data/samples/` holds three fictional drawings. They are not photographs of real patients. Put real reports in `data/private/raw/`. That folder is gitignored. See `data/INTAKE.md`.

## Deploy

`render.yaml` builds one Docker service with the React frontend and FastAPI backend on the same origin. Configure the following in Render's environment settings:

- `APP_ENV=production` and `APP_BASE_URL` set to the HTTPS origin of the deployed app.
- `DATABASE_URL` set to a pooled Neon PostgreSQL connection string with TLS. Set `DATABASE_URL_UNPOOLED` to the direct connection string for the same Neon database; the container uses it for Alembic migrations at startup. If omitted, migrations use `DATABASE_URL`, which is convenient for SQLite development.
- `RESEND_API_KEY` and `RESEND_FROM_EMAIL` set to a sender on a verified domain or sending subdomain. Add the DNS records shown by Resend and wait for verification before inviting users. Disable open and click tracking for the sending domain so authentication links are not rewritten. Never commit credentials.
- `MODEL_API_KEY` for live model features, plus the existing model and privacy configuration as needed.

The auth email quota defaults to 90 messages/day and 2,500/month; `AUTH_EMAIL_DAILY_LIMIT` and `AUTH_EMAIL_MONTHLY_LIMIT` may lower these caps. Resend's own quotas apply across all applications using that account. If delivery is unavailable, account verification or recovery cannot complete until the service is restored. In production the app refuses to start without PostgreSQL, an HTTPS app URL, and a configured Resend sender/key.

Render free services sleep and their filesystem is ephemeral. Accounts and sessions persist in Neon; uploaded images do not persist through a restart or redeploy. Use fictional data for the demo and configure appropriate persistent storage before expecting images to survive. Dev routes stay off in production, and a daily budget limits new model calls.

Render deploys a Git commit or published image, not uncommitted files. Publish the reviewed MedEdge changes to the chosen repository branch or image before connecting the new service. Keep existing services for other projects separate.

Local SAM 3.1 is `SAM_PROVIDER=local` plus `SAM_LOCAL_CHECKPOINT`. Without the weights the call fails with a clear error and the Meta API remains the default.

## Demo

The 2:45 shot list is in `docs/DEMO.md`. Recording, the X post, and the portal submission are done by the author from that script.
