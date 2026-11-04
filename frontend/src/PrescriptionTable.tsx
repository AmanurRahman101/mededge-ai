import { MedicineLookup } from "./MedicineLookup";
import type { PrescribedMedicine } from "./types";
import { useState } from "react";

export const blankMedicine = (): PrescribedMedicine => ({
  id: crypto.randomUUID(), name: "", strength: "", form: "", morning: "", noon: "", night: "",
  other_schedule: "", instructions: "", duration: "", spoken_text: "", confirmed: false,
});

export function PrescriptionTable({ medicines }: { medicines: PrescribedMedicine[] }) {
  if (!medicines.length) return null;
  return <div className="table-scroll prescription-table"><table>
    <thead><tr><th>Medicine / ওষুধ</th><th>Strength / শক্তি</th><th>Morning / সকাল</th><th>Noon / দুপুর</th><th>Night / রাত</th><th>Instructions / নির্দেশনা</th><th>Duration / কতদিন</th></tr></thead>
    <tbody>{medicines.map(m => <tr key={m.id}>
      <td><strong>{m.name}</strong>{m.form && <div>{m.form}</div>}</td><td>{m.strength || "Not specified"}</td>
      <td>{m.morning || "—"}</td><td>{m.noon || "—"}</td><td>{m.night || "—"}</td>
      <td>{[m.other_schedule, m.instructions].filter(Boolean).join(" · ") || "Not specified"}</td><td>{m.duration || "Not specified"}</td>
    </tr>)}</tbody>
  </table></div>;
}

export function PrescriptionEditor({ medicines, onChange }: { medicines: PrescribedMedicine[]; onChange: (rows: PrescribedMedicine[]) => void }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  function update(id: string, patch: Partial<PrescribedMedicine>) {
    onChange(medicines.map(row => row.id === id ? { ...row, ...patch, confirmed: patch.confirmed ?? false } : row));
  }
  return <section id="prescription-medicines" className="prescription-editor" aria-label="Edit prescription medicines">
    <div className="module-heading"><h2>Prescription medicines</h2><button className="secondary" type="button" disabled={medicines.length >= 40} onClick={() => onChange([...medicines, blankMedicine()])}>Add medicine manually</button></div>
    <p className="module-help">Check each medicine and its instructions before publishing. Leave unstated details blank. An explicit 0 means no dose at that time.</p>
    {!!medicines.length && <p className="review-progress" role="status">{medicines.filter(m => m.confirmed && m.name.trim()).length} of {medicines.length} checked</p>}
    {!medicines.length && <p className="empty-inline">No medicines entered yet. Add one manually to begin.</p>}
    {medicines.map((m, index) => m.confirmed && m.name.trim() && collapsed.has(m.id) ? <article id={`medicine-${m.id}`} className="prescription-medicine medicine-compact" key={m.id} aria-label={`Medicine ${index + 1}`}>
      <div><h3>{m.name} {m.strength}</h3><p>{[m.form, [m.morning || "—", m.noon || "—", m.night || "—"].join(" / "), m.other_schedule, m.instructions, m.duration].filter(Boolean).join(" · ")}</p><small>Checked</small></div>
      <button type="button" className="secondary" aria-label={`Edit medicine ${index + 1}`} onClick={() => setCollapsed(previous => { const next = new Set(previous); next.delete(m.id); return next; })}>Edit</button>
    </article> : <article id={`medicine-${m.id}`} className="prescription-medicine" key={m.id} aria-label={`Medicine ${index + 1}`}>
      <div className="module-heading"><h3>Medicine {index + 1}</h3><button type="button" className="text-link" onClick={() => onChange(medicines.filter(row => row.id !== m.id))}>Remove medicine {index + 1}</button></div>
      <div className="prescription-fields">
        <label className="medicine-name">Medicine name<input value={m.name} maxLength={200} required onChange={e => update(m.id, { name: e.target.value })} /></label>
        <label>Strength and unit<input value={m.strength} maxLength={120} placeholder="Not specified" onChange={e => update(m.id, { strength: e.target.value })} /></label>
        <label>Form<input value={m.form} maxLength={100} placeholder="Tablet, cream…" onChange={e => update(m.id, { form: e.target.value })} /></label>
        <fieldset className="dose-slots"><legend>Amount each time</legend>
          {(["morning", "noon", "night"] as const).map(slot => <label key={slot}>{slot === "morning" ? "Morning" : slot === "noon" ? "Noon" : "Night"}<input value={m[slot]} maxLength={60} placeholder="Unknown" onChange={e => update(m.id, { [slot]: e.target.value })} /></label>)}
        </fieldset>
        <label>Duration<input value={m.duration} maxLength={200} placeholder="Days, চলবে / Continue, or blank" onChange={e => update(m.id, { duration: e.target.value })} /></label>
        <label className="medicine-instructions">Instructions<input value={m.instructions} maxLength={1000} placeholder="Food timing, route, application…" onChange={e => update(m.id, { instructions: e.target.value })} /></label>
        <label className="medicine-instructions">Other schedule<input value={m.other_schedule} maxLength={500} placeholder="As needed, weekly, tapering, topical…" onChange={e => update(m.id, { other_schedule: e.target.value })} /></label>
      </div>
      <details><summary>Check the spoken text or Bangladesh reference</summary>
        {m.image_text && <p className="spoken-evidence"><strong>Image:</strong> {m.image_text}</p>}
        {!!m.conflicts?.length && <ul className="care-conflicts">{m.conflicts.map((conflict, i) => <li key={i}>{conflict}</li>)}</ul>}
        {m.spoken_text && <p className="spoken-evidence">{m.spoken_text}</p>}
        <MedicineLookup onChoose={product => update(m.id, { name: product.brand, form: product.form })} />
        <p className="module-help">Choosing a product changes its name and form only. Check the listed composition against the strength you prescribed.</p>
      </details>
      <label className="check"><input type="checkbox" checked={m.confirmed} disabled={!m.name.trim()} onChange={e => update(m.id, { confirmed: e.target.checked })} />I checked medicine {index + 1}, its strength, schedule and duration.</label>
      {m.confirmed && m.name.trim() && <button type="button" className="text-link" onClick={() => { setCollapsed(previous => new Set(previous).add(m.id)); requestAnimationFrame(() => document.getElementById(`medicine-${m.id}`)?.querySelector<HTMLElement>("button")?.focus()); }}>Collapse checked medicine</button>}
    </article>)}
  </section>;
}
