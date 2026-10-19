import { useSyncExternalStore } from "react";

export type ThemeMode = "system" | "light" | "dark";
const KEY = "heatguard.theme";
const media = () => window.matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function read(): ThemeMode {
  try { const v = localStorage.getItem(KEY); return v === "light" || v === "dark" ? v : "system"; } catch { return "system"; }
}

let mode: ThemeMode = read();

/** Applies the theme to <html> (class "dark") and the browser bar colour. index.html does the same before React loads, so there is no flash. */
function apply() {
  const dark = mode === "dark" || (mode === "system" && media().matches);
  document.documentElement.classList.toggle("dark", dark);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0B1120" : "#F8FAFC");
}

export function setThemeMode(next: ThemeMode) {
  mode = next;
  try { if (next === "system") localStorage.removeItem(KEY); else localStorage.setItem(KEY, next); } catch { /* not remembered */ }
  apply();
  listeners.forEach((l) => l());
}

if (typeof window !== "undefined") {
  apply();
  media().addEventListener("change", () => { if (mode === "system") apply(); });
}

/** One theme setting shared by the header button and the Settings page. */
export function useThemeMode(): [ThemeMode, (m: ThemeMode) => void] {
  const m = useSyncExternalStore((cb) => { listeners.add(cb); return () => listeners.delete(cb); }, () => mode);
  return [m, setThemeMode];
}

/** True while the page is dark (follows the device when the setting is "same as device"). */
export function useIsDark(): boolean {
  const m = useThemeMode()[0];
  return useSyncExternalStore((cb) => { const q = media(); q.addEventListener("change", cb); return () => q.removeEventListener("change", cb); },
    () => m === "dark" || (m === "system" && media().matches));
}
