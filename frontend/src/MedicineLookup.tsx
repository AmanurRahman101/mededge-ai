import { usePatientLanguage } from "./patientLanguage";
import { useEffect, useId, useRef, useState } from "react";
import { post } from "./api";

export type ReferenceMedicine = {
  code: string; brand: string; composition: string; form: string; manufacturer: string;
  dar_number: string; source_version: string; source_url: string;
};
type Results = { products: ReferenceMedicine[]; total: number; page: number; has_more: boolean; checked_at: string; stale: boolean };

export function MedicineLookup({ onChoose }: { onChoose?: (medicine: ReferenceMedicine) => void }) {
  const { t, message, locale, format } = usePatientLanguage();
  const id = useId();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Results | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const searched = useRef("");
  useEffect(() => () => { sequence.current++; }, []);
  async function search(page = 1) {
    if (query.trim().length < 3) return;
    const current = ++sequence.current;
    const term = page === 1 ? query.trim() : searched.current;
    setBusy(true); setError(""); setResult(null);
    try {
      const data = await post<Results>("/api/medicines/search", { query: term, page });
      if (current !== sequence.current) return;
      searched.current = term; setResult(data);
    } catch (e) {
      if (current === sequence.current) setError(e instanceof Error ? e.message : "Could not search the medicine reference.");
    } finally { if (current === sequence.current) setBusy(false); }
  }
  return <section className="medicine-lookup" aria-label="Bangladesh medicine search">
    <label htmlFor={id}>{t("Find a Bangladesh medicine")}</label>
    <div className="medicine-search-controls">
      <input id={id} type="search" value={query} maxLength={80} placeholder={t("Brand name, for example Napa")} onChange={e => {
        sequence.current++; setQuery(e.target.value); setResult(null); setBusy(false); setError("");
      }} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); void search(); } }} />
      <button className="secondary" type="button" disabled={busy || query.trim().length < 3} onClick={() => void search()}>{busy ? t("Searching…") : t("Search")}</button>
    </div>
    <p className="module-help">{t("Search by the brand on the pack. Check the strength and form; similar names can be different medicines.")}</p>
    {error && <p className="banner pii" role="alert">{message(error)}{t("You can still enter the medicine manually.")}</p>}
    {busy && <p role="status">{t("Searching the DGHS medicine reference…")}</p>}
    {result && <>
      {result.stale && <p role="status" className="banner">{t("Showing a saved reference. Updates could not be checked right now.")}</p>}
      {result.products.length ? <ul className="medicine-search-results">
        {result.products.map(m => <li key={m.code}>
          <div><strong>{m.brand}</strong>{m.form && <span> · {m.form}</span>}
            {m.composition && <p>{m.composition}</p>}
            {m.manufacturer && <p className="module-help">{m.manufacturer}</p>}
            <small>{t("Listed in Bangladesh reference")}</small><details><summary>{t("Reference details")}</summary><p>{m.dar_number || m.code}</p></details>
          </div>
          {onChoose && <button type="button" className="secondary" onClick={() => onChoose(m)} aria-label={`Choose ${m.brand} ${m.composition} ${m.form}`}>{t("Choose")}</button>}
          {!onChoose && <a className="text-link" target="_blank" rel="noreferrer" href={m.source_url}>{t("Registry entry")}</a>}
        </li>)}
      </ul> : <p className="empty-inline">{t("No matching product names found. Try the exact brand or enter it manually.")}</p>}
      {result.page >= 20 && result.total > 200 && <p className="module-help">{t("Refine the brand name to narrow these results.")}</p>}
      <div className="medicine-search-pagination">
        {result.page > 1 && <button type="button" className="secondary" disabled={busy} onClick={() => void search(result.page - 1)}>{t("Previous results")}</button>}
        {result.has_more && <button type="button" className="secondary" disabled={busy} onClick={() => void search(result.page + 1)}>{t("More results")}</button>}
      </div>
      <p className="module-help">{format("DGDA registration data, curated by DGHS. Checked {date}. A registry listing does not confirm pharmacy stock. Generic-name searches may miss branded products.", {date: new Date(result.checked_at).toLocaleDateString(locale)})}</p>
    </>}
  </section>;
}
