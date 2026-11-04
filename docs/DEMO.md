# MedEdge AI demo video (about 2:30)

The video is real app footage with a Remotion edit and a narrated voiceover.
Everything shown is fictional: the patient, the doctor, the handwritten
prescription and the doctor's voice note.

## Script

| Time | Beat | What the viewer sees |
| --- | --- | --- |
| 0:00 to 0:13 | The problem | A handwritten prescription, then "Reports in folders. No shared history." |
| 0:13 to 0:42 | Patient control | Landing page, patient portal, English and Bangla, sharing the patient code with a doctor |
| 0:42 to 1:02 | Doctor visit | Only patients who approved this doctor appear; the doctor opens the chart and starts a visit |
| 1:02 to 1:53 | Creating a prescription | Upload the handwritten page, record a voice explanation, privacy preview (SAM 3.1), Muse Voice transcript, Muse Spark 1.3 draft |
| 1:53 to 2:12 | Verify and publish | Editable medication table, per-medicine checks, bilingual note, "Verify and publish prescription" |
| 2:12 to 2:20 | Patient view | The published English and Bangla note in the patient's own record |
| 2:20 to 2:30 | Close | "The AI drafts. The doctor decides." and the live link |

## How it was made

Source and assets live in `video/` (Playwright recording, edge-tts voiceover,
Remotion composition `MedEdge`).

1. `video/reset-local.ps1` resets the local recording database.
2. `node take.mjs` records the scenes against a local instance of the same
   build, with real Meta API calls.
3. `py narrate.py` generates the voiceover with edge-tts.
4. `npx remotion render MedEdge out/mededge-demo.mp4` renders the final video.

## What to say if asked

- The handwritten prescription is a synthetic page; the voice note is text to
  speech. The footage shows the real workflow end to end.
- MedEdge is an administrative data and optical ingestion tool. It is not a
  clinical decision or diagnostic tool. The doctor checks every medicine
  before anything reaches the patient's chart.
- Meta models used: SAM 3.1 (privacy regions), Muse Voice (transcription),
  Muse Spark 1.3 (reading and drafting).

Live app: https://mededge-amanur-ai.onrender.com
