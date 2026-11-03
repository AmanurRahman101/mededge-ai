type PatientOption = { patient_id: string | null; status: string; name: string | null };
export function PatientSwitcher({ patients, selected, disabled, onChange }: { patients: PatientOption[]; selected: string; disabled: boolean; onChange: (id: string) => void }) {
  const options = patients.filter(patient => patient.status === "approved" && patient.patient_id);
  if (options.length < 2) return null;
  return <label className="patient-switcher">Switch patient<select value={selected} disabled={disabled} onChange={event => onChange(event.target.value)}>{options.map(patient => <option key={patient.patient_id} value={patient.patient_id || ""}>{patient.name || "Patient"}</option>)}</select></label>;
}
