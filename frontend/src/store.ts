import { create } from "zustand";

import type { Screen } from "./types";

interface AppState {
  screen: Screen;
  theme: "dark" | "light";
  setScreen: (screen: Screen) => void;
  toggleTheme: () => void;
}

const stored = localStorage.getItem("mededge-theme");
const theme = stored === "light" || stored === "dark" ? stored : "dark";
document.documentElement.classList.toggle("dark", theme === "dark");

export const useApp = create<AppState>((set) => ({
  screen: "start",
  theme,
  setScreen: (screen) => set({ screen }),
  toggleTheme: () =>
    set((state) => {
      const next = state.theme === "dark" ? "light" : "dark";
      localStorage.setItem("mededge-theme", next);
      document.documentElement.classList.toggle("dark", next === "dark");
      return { theme: next };
    }),
}));
