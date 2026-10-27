# Adding real reports

Put photographs of reports and prescriptions in `data/private/raw/`.

That folder is gitignored. Do not commit a photo that still shows a name, phone number, or ID.

The person in the photograph should know it will be sent to the segmentation model, and that only the redacted page is sent to a language model after they confirm the overlay.

`GET /api/inbox` lists the filenames. Upload one through the app, confirm the redaction, and only then share it.

The three sheets in `data/samples/` are fictional drawings used so the demo runs before any real photo is added.
