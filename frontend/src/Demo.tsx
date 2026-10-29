import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { apiBase, getDemo, listCases, type Demo } from "./api";
import { navigate } from "./navigation";
import type { SampleCase } from "./types";

export function DemoPage() {
  const [cases, setCases] = useState<SampleCase[]>([]); const [demo, setDemo] = useState<Demo | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  useEffect(() => { void listCases().then(setCases).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Samples are unavailable.")); }, []);
  async function open(id: string) { setBusy(true); setError(""); try { setDemo(await getDemo(id)); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not open the sample."); } finally { setBusy(false); } }
  return <main className="demo-page"><button className="back-link" type="button" onClick={() => demo ? setDemo(null) : navigate("/")}><ArrowLeft size={16} />{demo ? "All examples" : "Back to MedEdge"}</button>
    {!demo ? <><div className="demo-heading"><h1>See a record<br />come together.</h1><p>Explore a fictional report and its recorded reading. No account or model call is needed.</p></div>{error && <p className="auth-error" role="alert">{error}</p>}<div className="demo-list">{cases.map((item) => <button key={item.id} className="demo-item" disabled={busy} type="button" onClick={() => void open(item.id)}><span><strong>{item.title}</strong><small>{item.summary}</small></span><ArrowRight size={20} /></button>)}</div><p className="demo-note">All examples are fictional. Values are shown as printed.</p></> : <><div className="demo-heading compact"><div><h1>{demo.title}</h1><p>Fictional sample · Recorded reading</p></div><button className="secondary" type="button" onClick={() => navigate("/signup")}>Create an account <ArrowRight size={16} /></button></div>{error && <p className="auth-error" role="alert">{error}</p>}<div className="demo-workspace"><section><h2>Source</h2><div className="sheet"><img src={`${apiBase}${demo.image_url}`} alt={`Fictional ${demo.title} sample`} /></div></section><section><h2>Recorded reading</h2><p className="banner review">Fictional sample. No model produced these values.</p><table><thead><tr><th>Printed name</th><th>Value</th><th>Unit</th></tr></thead><tbody>{demo.extraction.rows.map((row, index) => <tr key={`${row.raw_name}-${index}`}><td>{row.raw_name}</td><td>{row.value ?? row.value_text ?? ""}</td><td>{row.unit ?? ""}</td></tr>)}{demo.extraction.medications.map((item, index) => <tr key={`${item.raw_text}-${index}`}><td colSpan={3}>{item.raw_text}</td></tr>)}</tbody></table>{demo.extraction.advised_tests.length > 0 && <><h3>Tests as written</h3><ul>{demo.extraction.advised_tests.map((test, index) => <li key={`${test.raw_name}-${index}`}>{test.raw_name}</li>)}</ul></>}</section></div></>}
  </main>;
}
