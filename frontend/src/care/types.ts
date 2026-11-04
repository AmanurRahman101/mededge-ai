export interface Visit {
  id: string;
  patient_id: string;
  doctor_id: string;
  patient_name: string;
  doctor_name: string;
  title: string;
  status: "open" | "completed";
  created_at: string;
  completed_at: string | null;
  revision: number;
  can_edit?: boolean;
  completion_checks?: string[];
  records?: VisitRecord[];
}
export interface VisitRecord {
  run_id: string;
  title: string;
  input_mode: string;
  status: string;
  document_type: string | null;
  has_published_note: boolean;
  reference: boolean;
}
