"""Draw fictional sample sheets. These are not photographs of real patients.

Drop real reports in data/private/raw/. That folder is gitignored.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"
FONT = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = FONT_BOLD if bold else FONT
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def paper(title: str, header: str, lines: list[str], rotate: float = 0) -> Image.Image:
    sheet = Image.new("RGB", (1000, 1400), (252, 252, 248))
    draw = ImageDraw.Draw(sheet)
    draw.text((48, 36), title, font=font(40, bold=True), fill=(24, 24, 24))
    draw.text((48, 100), header, font=font(26), fill=(24, 24, 24))
    draw.line((48, 160, 952, 160), fill=(24, 24, 24), width=2)
    y = 190
    for line in lines:
        draw.text((48, y), line, font=font(28), fill=(24, 24, 24))
        y += 52
    if rotate:
        sheet = sheet.rotate(rotate, expand=True, fillcolor=(214, 206, 190), resample=Image.Resampling.BICUBIC)
    canvas = Image.new("RGB", (sheet.width + 80, sheet.height + 80), (214, 206, 190))
    canvas.paste(sheet, (40, 40))
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    paper(
        "City Diagnostic Centre",
        "Name: Rafiqul Hasan    Age: 54    Sex: M    Mobile: 01700 000000",
        [
            "Test                 Result     Unit        Ref. range",
            "Haemoglobin          11.2       g/dL        13.0-17.0",
            "S. Creatinine        1.4        mg/dL       0.7-1.2",
            "Platelets            2.1        lakh/cumm   1.5-4.0",
            "ESR                  28         mm/1st hr   0-10",
            "WBC                  9800       /cumm       4000-11000",
        ],
    ).save(OUT / "cbc.png")
    paper(
        "River Lab, handwritten copy",
        "Name: Nusrat Jahan    Age: 41    Sex: F    ID: RL-20411",
        [
            "Lipid profile, fasting",
            "Cholesterol     214    mg/dL    <200",
            "Triglyceride    188    mg/dL    <150",
            "HDL             39     mg/dL    >40",
            "LDL             142    mg/dL    <100",
        ],
        rotate=-3.5,
    ).save(OUT / "lipid.png")
    paper(
        "Outpatient prescription",
        "Name: Imran Kabir    Age: 63    Mobile: 01800 000000",
        [
            "Rx",
            "1. Tab. Napa 500 mg    1+0+1    after meal    5 days",
            "2. Cap. Seclo 20 mg    1+0+0    before meal   14 days",
            "Advised: S. Creatinine, CBC",
        ],
    ).save(OUT / "prescription.png")

    manifest = {
        "note": "Fictional sheets drawn for the demo. Not real patients.",
        "cases": [
            {
                "id": "cbc",
                "title": "Complete blood count",
                "kind": "lab_report",
                "summary": "Fictional sheet. The header has a name and a phone number.",
                "file": "cbc.png",
                "extraction": {
                    "document_type": "lab_report",
                    "rows": [
                        {"raw_name": "Haemoglobin", "value": 11.2, "unit": "g/dL", "ref_low": 13.0, "ref_high": 17.0, "contains_identifier": False},
                        {"raw_name": "S. Creatinine", "value": 1.4, "unit": "mg/dL", "ref_low": 0.7, "ref_high": 1.2, "contains_identifier": False},
                        {"raw_name": "Platelets", "value": 2.1, "unit": "lakh/cumm", "ref_low": 1.5, "ref_high": 4.0, "contains_identifier": False},
                        {"raw_name": "ESR", "value": 28, "unit": "mm/1st hr", "ref_low": 0, "ref_high": 10, "contains_identifier": False},
                        {"raw_name": "WBC", "value": 9800, "unit": "/cumm", "ref_low": 4000, "ref_high": 11000, "contains_identifier": False},
                    ],
                    "medications": [],
                    "advised_tests": [],
                },
            },
            {
                "id": "lipid",
                "title": "Skewed lipid profile",
                "kind": "lab_report",
                "summary": "Fictional sheet, slightly rotated. Use Inject a fault to show a repair.",
                "file": "lipid.png",
                "extraction": {
                    "document_type": "lab_report",
                    "rows": [
                        {"raw_name": "Cholesterol", "value": 214, "unit": "mg/dL", "ref_high": 200, "contains_identifier": False},
                        {"raw_name": "Triglyceride", "value": 188, "unit": "mg/dL", "ref_high": 150, "contains_identifier": False},
                        {"raw_name": "HDL", "value": 39, "unit": "mg/dL", "ref_low": 40, "contains_identifier": False},
                        {"raw_name": "LDL", "value": 142, "unit": "mg/dL", "ref_high": 100, "contains_identifier": False},
                    ],
                    "medications": [],
                    "advised_tests": [],
                },
            },
            {
                "id": "prescription",
                "title": "Handwritten-style prescription",
                "kind": "prescription",
                "summary": "Fictional prescription. Doses are copied as written, including 1+0+1.",
                "file": "prescription.png",
                "extraction": {
                    "document_type": "prescription",
                    "rows": [],
                    "medications": [
                        {"raw_text": "Tab. Napa 500 mg 1+0+1 after meal 5 days", "drug_name": "Napa", "dose_text": "1+0+1", "timing_text": "after meal", "duration_text": "5 days", "contains_identifier": False},
                        {"raw_text": "Cap. Seclo 20 mg 1+0+0 before meal 14 days", "drug_name": "Seclo", "dose_text": "1+0+0", "timing_text": "before meal", "duration_text": "14 days", "contains_identifier": False},
                    ],
                    "advised_tests": [{"raw_name": "S. Creatinine"}, {"raw_name": "CBC"}],
                },
            },
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest['cases'])} cases to {OUT}")


if __name__ == "__main__":
    main()
