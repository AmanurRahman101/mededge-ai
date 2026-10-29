import { create } from "zustand";

import type { Screen } from "./types";
import type { User } from "./api";
import { navigate } from "./navigation";

interface AppState {
  screen: Screen;
  theme: "dark" | "light";
  user: User | null;
  setUser: (user: User | null) => void;
  setScreen: (screen: Screen) => void;
  toggleTheme: () => void;
}

const stored = localStorage.getItem("mededge-theme");
const theme = stored === "light" || stored === "dark" ? stored : "dark";
document.documentElement.classList.toggle("dark", theme === "dark");

export const useApp = create<AppState>((set) => ({
  screen: "start",
  theme,
  user: null,
  setUser: (user) => set({ user }),
  setScreen: (screen) => { set({ screen }); navigate(screen === "start" ? "/" : `/${screen}`); },
  toggleTheme: () =>
    set((state) => {
      const next = state.theme === "dark" ? "light" : "dark";
      localStorage.setItem("mededge-theme", next);
      document.documentElement.classList.toggle("dark", next === "dark");
      return { theme: next };
    }),
}));
