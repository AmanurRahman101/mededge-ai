# Demo script (2:45)

Record the screen on the deployed URL. Do not show `.env`, the Render dashboard, or a real report. Use the demo accounts.

1. **0:00** Start screen. Say the one line: MedEdge AI is an administrative pipeline, not a diagnostic tool.
2. **0:10** Sign in with "Use demo doctor." Open the connected demo patient.
3. **0:25** Open the CBC sample record. Point at the source image: the name header is blurred and the overlay is drawn on the blurred pixels, so the original never leaves the machine. Say SAM 3.1 found the regions.
4. **0:45** Click "Use the sample dictation" and run. Watch the live events: Muse Voice transcribes, Muse Spark reads the redacted page and translates the dictation, and the agent calls LOINC and UCUM tools.
5. **1:10** Open "How this record was made." Point at the models, the latency, the tool calls, and the verifier layers. Say the numbers are real, from this run.
6. **1:30** Run a sample with "Inject a fault" checked. Show the trace: the agent submits a bundle, the verifier rejects it with "missing Observation.status," the agent repairs it, and the verifier accepts.
7. **1:55** Review the reading against the source. Point at platelets in lakh/cumm copied as printed. Show the English and Bangla note and its provenance stamp: spoken by the doctor, transcribed and translated, not summarized.
8. **2:15** Approve and open the FHIR JSON. Point at the pseudonym, the LOINC and UCUM badges, and the dose text `1+0+1` in the prescription sample.
9. **2:30** Switch to the demo patient and show the published note and activity log. End on the disclaimer line.

## Cut for X (under 45 seconds)

Blurred source image, dictation, trace panel with the rejected then accepted bundle, FHIR JSON.

## Draft X post

Paper lab reports and a doctor's spoken note, turned into a verified FHIR R4 bundle. The name is blurred before any model sees the page. SAM 3.1 finds regions, Muse Voice transcribes, Muse Spark reads and translates, and an agent builds the bundle while a verifier checks it. Built for the Meta Global AI Developer Hackathon. MedEdge AI is an administrative data interoperability and optical ingestion pipeline, not a clinical decision or diagnostic tool. [live link] [repo link]

## Draft submission text

MedEdge AI helps clinics in Bangladesh move paper records into FHIR R4 without sending a patient's name to a language model. SAM 3.1 finds the page regions and the identifying header is blurred first, with the overlay drawn on the blurred pixels. After the user confirms, Muse Spark 1.3 reads the page exactly as printed (including units such as lakh/cumm), Muse Voice Transcribe turns a doctor's dictation into text, and Muse Spark transcribes and translates it to English and Bangla without summarizing. A Muse Spark agent then builds the bundle by calling LOINC and UCUM lookup tools, and a verifier checks schema, references, LOINC check digits, UCUM units, row-for-row match with the source, and a policy that rejects diagnoses and computed flags. If the agent fails, a deterministic assembler takes over and the screen says so. Every run keeps a trace of models, latency, tool calls, and verifier layers. Live evaluation on three fictional samples: 5/5, 4/4 and 2/2 names read and 5/5, 4/4 and 2/2 values or doses correct in about 4 seconds each. MedEdge AI is an administrative data interoperability and optical ingestion pipeline, not a clinical decision or diagnostic tool. Judges can sign in with the demo patient and demo doctor buttons on the sign-in page.

## What this file does not do

Recording, posting, and the Cerebral Valley submission need the author's accounts. They are not done here.