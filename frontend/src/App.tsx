import { Moon, Sun } from "@phosphor-icons/react";

import { Doctor } from "./Doctor";
import { Patient } from "./Patient";
import { Start } from "./Start";
import { useApp } from "./store";

export const DISCLAIMER =
  "MedEdge AI is an administrative data interoperability and optical ingestion pipeline, not a clinical decision or diagnostic tool.";

export function App() {
  const screen = useApp((state) => state.screen);
  const theme = useApp((state) => state.theme);
  const setScreen = useApp((state) => state.setScreen);
  const toggleTheme = useApp((state) => state.toggleTheme);

  return (
    <div className="app">
      <header className="topbar">
        <button className="wordmark" type="button" onClick={() => setScreen("start")}>
          MedEdge AI
        </button>
        <button
          className="icon-button"
          type="button"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Use light mode" : "Use dark mode"}
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </header>
      {screen === "start" && <Start />}
      {screen === "patient" && <Patient />}
      {screen === "doctor" && <Doctor />}
      <footer className="footer">{DISCLAIMER}</footer>
    </div>
  );
}
