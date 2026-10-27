import { useApp } from "./store";

export function Start() {
  const setScreen = useApp((state) => state.setScreen);
  return (
    <main className="choices">
      <button className="choice" type="button" onClick={() => setScreen("patient")}>
        <h1>I'm a patient</h1>
        <p>Photograph a report, confirm what is hidden, and share the record with a doctor.</p>
      </button>
      <button className="choice" type="button" onClick={() => setScreen("doctor")}>
        <h1>I'm a doctor</h1>
        <p>Open a patient's code, check every value against the page, then approve the export.</p>
      </button>
    </main>
  );
}
