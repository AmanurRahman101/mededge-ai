import { useEffect, useRef, useState } from "react";
import { deleteChart, getChart, post, updateChart } from "./api";
import { MedicineLookup } from "./MedicineLookup";
import { PixelPill } from "./PixelIcons";

type Medicine = { id: string; name: string; instructions: string; confirmed_at: string };

export function CurrentMedicines({ patientId, editable, refreshKey = 0 }: { patientId: string; editable: boolean; refreshKey?: number }) {
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Medicine | null>(null);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const key = useRef(crypto.randomUUID());
  const addButton = useRef<HTMLButtonElement>(null);
  const path = `/patients/${encodeURIComponent(patientId)}/medicines`;
  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setMedicines([]); setAdding(false);
    void getChart<{ medicines: Medicine[] }>(path).then(result => {
      if (active) setMedicines(result.medicines);
    }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, reload, refreshKey]);
  function closeForm() { setAdding(false); setEditing(null); setName(""); setInstructions(""); requestAnimationFrame(() => addButton.current?.focus()); }
  return <section className="current-medicines" aria-label="Current medicines">
    <div className="module-heading">
      <h2><PixelPill size={22} /> {editable ? "Medicines I take now" : "Current medicines"}</h2>
      {editable && !adding && <button ref={addButton} className="secondary" type="button" onClick={() => { key.current = crypto.randomUUID(); setEditing(null); setName(""); setInstructions(""); setAdding(true); }}>Add a medicine</button>}
    </div>
    <p className="module-help">{editable ? "Keep this list up to date so your doctor knows what you take." : "Current use reported by the patient; not inferred from past prescriptions."}</p>
    {error && <p role="alert" className="banner pii">{error} <button className="text-link" type="button" onClick={() => setReload(value => value + 1)}>Reload list</button></p>}
    {loading ? <p role="status">Loading medicines…</p> : medicines.length ? <ul className="current-medicine-list">
      {medicines.map(medicine => <li key={medicine.id}>
        <div><strong>{medicine.name}</strong>{medicine.instructions && <p>{medicine.instructions}</p>}
          <small>{editable ? "Confirmed by you" : "Reported by patient"} · {new Date(medicine.confirmed_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</small></div>
        {editable && <div className="action-group"><button className="text-link" type="button" disabled={busy} aria-label={`Edit ${medicine.name}`} onClick={() => { setEditing(medicine); setName(medicine.name); setInstructions(medicine.instructions); setAdding(true); }}>Edit</button><button className="text-link" type="button" disabled={busy} aria-label={`Remove ${medicine.name} from my list`} onClick={async () => {
          if (!window.confirm(`Remove ${medicine.name} from your current-medicines list? This changes your list only, not your prescription.`)) return;
          setBusy(true); setError("");
          try { await deleteChart(`${path}/${medicine.id}`); setMedicines(rows => rows.filter(row => row.id !== medicine.id)); }
          catch(e) { setError(e instanceof Error ? e.message : "Could not update the list."); }
          finally { setBusy(false); }
        }}>Remove from list</button></div>}
      </li>)}
    </ul> : !error && <p className="empty-inline">{editable ? "You haven’t added any medicines yet." : "The patient has not recorded current medicines."}</p>}
    {adding && <form className="current-medicine-form" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError("");
      try {
        const saved = editing
          ? await updateChart<Medicine>(`${path}/${editing.id}`, {name, instructions, expected_confirmed_at: editing.confirmed_at})
          : await post<Medicine>(`/api/chart${path}`, { id: key.current, name, instructions });
        setMedicines(rows => [saved, ...rows.filter(row => row.id !== saved.id)]);
        key.current = crypto.randomUUID(); setName(""); setInstructions(""); closeForm();
      } catch(e) { setError(e instanceof Error ? e.message : "Could not save the medicine."); }
      finally { setBusy(false); }
    }}>
      <MedicineLookup onChoose={medicine => { const label = [medicine.brand, medicine.composition, medicine.form].filter(Boolean).join(" · "); setName(label.length <= 160 ? label : medicine.brand); }} />
      <label>Medicine name and strength<input autoFocus required maxLength={160} value={name} onChange={e => setName(e.target.value)} placeholder="Copy the name on the medicine pack" /></label>
      <label>How you take it (optional)<input maxLength={500} value={instructions} onChange={e => setInstructions(e.target.value)} placeholder="As written on your prescription" /></label>
      <div className="action-group"><button className="primary" disabled={busy || !name.trim()}>{busy ? "Saving…" : editing ? "Save medicine changes" : "I take this medicine"}</button><button className="secondary" type="button" disabled={busy} onClick={closeForm}>Cancel</button></div>
    </form>}
  </section>;
}
