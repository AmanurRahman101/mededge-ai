from typing import Literal

from pydantic import BaseModel, Field


class LabRow(BaseModel):
    raw_name: str
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    ref_text: str | None = None
    flag_printed: str | None = None
    contains_identifier: bool = False
    row_bbox: list[int] | None = None


class MedicationRow(BaseModel):
    raw_text: str
    drug_name: str
    dose_text: str | None = None
    timing_text: str | None = None
    duration_text: str | None = None
    contains_identifier: bool = False


class AdvisedTest(BaseModel):
    raw_name: str


class Extraction(BaseModel):
    document_type: Literal["lab_report", "prescription", "mixed", "other"]
    rows: list[LabRow] = Field(default_factory=list)
    medications: list[MedicationRow] = Field(default_factory=list)
    advised_tests: list[AdvisedTest] = Field(default_factory=list)


class ConsultationDraft(BaseModel):
    extraction: Extraction
    summary_en: str
    summary_bn: str
    unresolved: list[str] = Field(default_factory=list)


class EncounterFields(BaseModel):
    status: Literal[
        "planned", "arrived", "triaged", "in-progress", "onleave", "finished", "cancelled"
    ] = "finished"
    class_code: Literal["AMB", "IMP", "EMER", "HH", "VR"] = "AMB"
    class_display: str = "ambulatory"
    effective_datetime: str | None = None
    specimen_fasting: bool | None = None
    note: str = ""


class LoincHit(BaseModel):
    code: str
    display: str


class RxHit(BaseModel):
    name: str
    rxcui: str | None = None
