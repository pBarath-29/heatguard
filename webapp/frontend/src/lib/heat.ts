import { useEffect, useState } from "react";

/** Plain words for NEA's heat-stress bands (WBGT): Low < 31, Moderate 31–32.9, High ≥ 33 °C. */
export function heatWords(wbgt: number | null | undefined): { word: string; cls: string; dot: string } {
  if (wbgt == null) return { word: "No data", cls: "bg-ink-100 text-ink-600", dot: "bg-ink-400" };
  if (wbgt >= 33) return { word: "Very hot", cls: "bg-red-100 text-red-800", dot: "bg-red-500" };
  if (wbgt >= 31) return { word: "Hot", cls: "bg-amber-100 text-amber-800", dot: "bg-amber-500" };
  return { word: "Normal", cls: "bg-emerald-100 text-emerald-800", dot: "bg-emerald-500" };
}

export function sgtNow(): Date {
  return new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Singapore" }));
}

/** Today's date in Singapore (YYYY-MM-DD); re-checks every minute so labels never go stale after midnight. */
export function useSgtToday(): string {
  const get = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Singapore" });
  const [d, setD] = useState(get);
  useEffect(() => { const t = setInterval(() => setD(get()), 60_000); return () => clearInterval(t); }, []);
  return d;
}

export function hourLabel(h: number): string {
  if (h === 0) return "12 am";
  if (h === 12) return "12 pm";
  return h < 12 ? `${h} am` : `${h - 12} pm`;
}

export function sgtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-SG", { timeZone: "Asia/Singapore", hour: "numeric", minute: "2-digit" });
}

export function sgtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-SG", { timeZone: "Asia/Singapore", weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}
