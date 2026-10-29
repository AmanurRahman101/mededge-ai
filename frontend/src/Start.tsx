import { ArrowRight, ArrowUpRight } from "@phosphor-icons/react";
import { navigate } from "./navigation";
import { useApp } from "./store";

export function Start() {
  const user = useApp((state) => state.user);
  function open(role: "patient" | "doctor") { navigate(user ? `/${user.role}` : `/signin?role=${role}`); }
  return <main className="start-wrap"><div className="choices">
    <button className="choice" type="button" onClick={() => open("patient")} disabled={!!user && user.role !== "patient"}><span className="choice-arrow" aria-hidden="true"><ArrowUpRight size={24} /></span><div className="choice-content"><span className="choice-label">For patients</span><h1>Your records,<br />within reach.</h1><p>Photograph a report, check what’s hidden, and share it with a doctor.</p><span className="choice-action">Continue as a patient <ArrowRight size={18} /></span></div></button>
    <button className="choice" type="button" onClick={() => open("doctor")} disabled={!!user && user.role !== "doctor"}><span className="choice-arrow" aria-hidden="true"><ArrowUpRight size={24} /></span><div className="choice-content"><span className="choice-label">For doctors</span><h1>A clearer view,<br />on every page.</h1><p>Open a patient’s record, review its source, and approve the export.</p><span className="choice-action">Continue as a doctor <ArrowRight size={18} /></span></div></button>
  </div><div className="demo-strip"><div><strong>See how it works.</strong><span>Explore a fictional example without an account.</span></div><button className="text-link demo-link" type="button" onClick={() => navigate("/demo")}>Explore the demo <ArrowRight size={17} /></button></div></main>;
}
