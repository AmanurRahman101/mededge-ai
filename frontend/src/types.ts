export type Screen = "start" | "patient" | "doctor";

export interface LabRow {
  raw_name: string;
  value: number | null;
  value_text: string | null;
  unit: string | null;
  ref_low: number | null;
  ref_high: number | null;
  ref_text: string | null;
  flag_printed: string | null;
  contains_identifier: boolean;
}

export interface MedicationRow {
  raw_text: string;
  drug_name: string;
  dose_text: string | null;
  timing_text: string | null;
  duration_text: string | null;
  contains_identifier: boolean;
}

export interface Extraction {
  document_type: string;
  rows: LabRow[];
  medications: MedicationRow[];
  advised_tests: { raw_name: string }[];
}

export interface Encounter {
  status: string;
  class_code: string;
  class_display: string;
  effective_datetime: string | null;
  specimen_fasting: boolean | null;
  note: string;
}

export interface Run {
  run_id: string;
  status: string;
  pseudonym: string;
  document_type: string | null;
  extraction: Extraction | null;
  encounter: Encounter | null;
  bundle: Record<string, unknown> | null;
  transcript: string | null;
  extractor_model: string | null;
  used_fallback: boolean;
  replay: boolean;
  inject_fault: boolean;
  share_code: string | null;
  overlay_url: string;
  redacted_url: string;
}

export interface PipelineEvent {
  seq: number;
  stage: string;
  kind: string;
  message: string;
  model: string | null;
}

export interface SampleCase {
  id: string;
  title: string;
  kind: string;
  summary: string;
}

export interface ClinicalSummary {
  id: string;
  author_id: string;
  author_name?: string | null;
  transcript: string;
  summary_en: string;
  summary_bn: string;
  unresolved: string | string[];
  status: string;
  created_at: string;
  published_at: string | null;
}
