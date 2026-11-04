import { ArrowRight, ArrowUpRight } from "@phosphor-icons/react";
import { PixelWorkspaceIcon } from "./PixelIcons";
import { navigate } from "./navigation";
import { useApp } from "./store";

export function Start() {
  const user = useApp((state) => state.user);
  function open(role: "patient" | "doctor") {
    navigate(user ? `/${user.role}` : `/signin?role=${role}`);
  }
  return (
    <main className="start-wrap">
      <h1 className="sr-only">MedEdge AI</h1>
      <div className="choices">
        <button
          className="choice"
          type="button"
          onClick={() => open("patient")}
          disabled={!!user && user.role !== "patient"}
        >
          <span className="choice-arrow" aria-hidden="true">
            <ArrowUpRight size={24} />
          </span>
          <div className="choice-content">
            <PixelWorkspaceIcon workspace="patient" size={120} />
            <h2>Patient portal</h2>
            <p>Your reports and doctor’s notes, together.</p>
            <span className="choice-action">
              Open patient portal <ArrowRight size={18} />
            </span>
          </div>
        </button>
        <button
          className="choice"
          type="button"
          onClick={() => open("doctor")}
          disabled={!!user && user.role !== "doctor"}
        >
          <span className="choice-arrow" aria-hidden="true">
            <ArrowUpRight size={24} />
          </span>
          <div className="choice-content">
            <PixelWorkspaceIcon workspace="doctor" size={120} />
            <h2>Doctor workspace</h2>
            <p>Review patient history. Write prescriptions.</p>
            <span className="choice-action">
              Open doctor workspace <ArrowRight size={18} />
            </span>
          </div>
        </button>
      </div>
      <div className="demo-strip">
        <span>Try a fictional example. No account needed.</span>
        <button
          className="text-link demo-link"
          type="button"
          onClick={() => navigate("/demo")}
        >
          View demo <ArrowRight size={17} />
        </button>
      </div>
    </main>
  );
}
