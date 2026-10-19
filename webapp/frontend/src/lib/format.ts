const SMALL = new Set(["of", "and", "the"]);
const UPPER = new Set(["cc", "rc", "nlb", "hdb", "mrt", "sg", "ii"]);

/** "TELOK BLANGAH RISE" → "Telok Blangah Rise" */
export function title(s: string | null | undefined): string {
  if (!s) return "";
  return s
    .toLowerCase()
    .split(/(\s+|-|\/)/)
    .map((w, i) => (UPPER.has(w) ? w.toUpperCase() : i > 0 && SMALL.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join("");
}

function asDate(isoDate: string): Date {
  return new Date(`${isoDate.slice(0, 10)}T00:00:00`);
}

/** "2026-10-15..." → "Thu 15 Oct" (or with year / long weekday) */
export function dayLabel(iso: string | null | undefined, opts: { year?: boolean; long?: boolean } = {}): string {
  if (!iso) return "—";
  return asDate(iso).toLocaleDateString("en-SG", {
    weekday: opts.long ? "long" : "short", day: "numeric", month: opts.long ? "long" : "short", ...(opts.year ? { year: "numeric" } : {}),
  });
}

export function shortDate(iso: string): string {
  return asDate(iso).toLocaleDateString("en-SG", { day: "numeric", month: "short" });
}

/** UTC ISO timestamp → "Wed 14 Oct, 8:45 pm" in Singapore time */
export function sgtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-SG", { timeZone: "Asia/Singapore", weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "unknown";
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (secs < 90) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)} min ago`;
  if (secs < 172800) { const h = Math.round(secs / 3600); return `${h} hour${h === 1 ? "" : "s"} ago`; }
  return `${Math.round(secs / 86400)} days ago`;
}

export function hoursSince(iso: string | null | undefined): number {
  return iso ? (Date.now() - new Date(iso).getTime()) / 3600000 : Infinity;
}

export function pct(x: number | null | undefined, digits = 0): string {
  return x === null || x === undefined || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`;
}

export function num(x: number | null | undefined, digits = 0): string {
  return x === null || x === undefined || Number.isNaN(x) ? "—" : x.toLocaleString("en-SG", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function deg(x: number | null | undefined): string {
  return x === null || x === undefined ? "—" : `${x.toFixed(1)}°C`;
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
