import type { Band } from "./api";

export const BAND: Record<Band, { label: string; text: string; bg: string; ring: string; dot: string; hex: string; soft: string }> = {
  High: { label: "High", text: "text-red-700", bg: "bg-red-50", ring: "ring-red-600/20", dot: "bg-red-500", hex: "#DC2626", soft: "#FEE2E2" },
  Moderate: { label: "Moderate", text: "text-amber-700", bg: "bg-amber-50", ring: "ring-amber-600/20", dot: "bg-amber-500", hex: "#D97706", soft: "#FEF3C7" },
  Low: { label: "Low", text: "text-emerald-700", bg: "bg-emerald-50", ring: "ring-emerald-600/20", dot: "bg-emerald-500", hex: "#059669", soft: "#D1FAE5" },
};

export const PSI: Record<string, { text: string; bg: string; ring: string; hex: string }> = {
  Good: { text: "text-emerald-700", bg: "bg-emerald-50", ring: "ring-emerald-600/20", hex: "#059669" },
  Moderate: { text: "text-sky-700", bg: "bg-sky-50", ring: "ring-sky-600/20", hex: "#0284C7" },
  Unhealthy: { text: "text-amber-700", bg: "bg-amber-50", ring: "ring-amber-600/20", hex: "#D97706" },
  "Very unhealthy": { text: "text-red-700", bg: "bg-red-50", ring: "ring-red-600/20", hex: "#DC2626" },
  Hazardous: { text: "text-rose-900", bg: "bg-rose-100", ring: "ring-rose-700/30", hex: "#881337" },
};

export const DRIVER: Record<string, { label: string; short: string }> = {
  heat: { label: "Heat", short: "Heat" },
  haze: { label: "Haze", short: "Haze" },
  vulnerability: { label: "Many vulnerable seniors", short: "Vulnerable seniors" },
  access: { label: "Far from a cool space", short: "Distance to cool space" },
};

export const TIER: Record<string, { label: string; text: string; bg: string; ring: string; hex: string; blurb: string }> = {
  "Start here": { label: "Start here", text: "text-white", bg: "bg-brand-600", ring: "ring-brand-700/20", hex: "#EA580C", blurb: "The 10 areas to reach first: highest risk where Moderate or High heat is forecast." },
  "Check in": { label: "Check in", text: "text-amber-800", bg: "bg-amber-100", ring: "ring-amber-600/20", hex: "#D97706", blurb: "Other highly exposed areas with Moderate-or-worse heat: a phone check-in." },
  Routine: { label: "Routine", text: "text-ink-600", bg: "bg-ink-100", ring: "ring-ink-500/10", hex: "#94A3B8", blurb: "No heat-specific action needed beyond routine check-ins." },
};

export const COMPONENT_COLORS: Record<string, string> = {
  heat: "#EA580C",
  vulnerability: "#7C3AED",
  haze: "#64748B",
  access: "#0284C7",
};

/** Risk score (0–100) → colour from amber to deep red. */
export function riskHex(score: number): string {
  const t = Math.max(0, Math.min(1, (score - 35) / 35));
  const from = [251, 191, 36], to = [153, 27, 27];
  const c = from.map((f, i) => Math.round(f + (to[i] - f) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export const CHART = { grid: "#E2E8F0", axis: "#64748B", ink: "#0F172A", muted: "#CBD5E1", brand: "#EA580C", good: "#16A34A" };
