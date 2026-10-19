import clsx from "clsx";
import { Building2, Crosshair, Loader2, MapPin, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError, features, type Place } from "../lib/api";
import { title } from "../lib/format";
import { inputClass } from "./ui";

export interface Picked { label: string; latitude: number; longitude: number; source: "centre" | "gps" | "search" }

const CENTRE_KEY = "heatguard.centrePostal";
const centrePostal = () => { try { return localStorage.getItem(CENTRE_KEY); } catch { return null; } };

const GEO_ERRORS: Record<number, string> = {
  1: "Location permission was denied. You can allow it in your browser settings, or search for an address below.",
  2: "Your location isn't available right now (location services may be off). Search for an address below instead.",
  3: "Finding your location took too long. Try again, or search for an address below.",
};

/** Choose a place: my centre (remembered postal code), my current location, or a search. */
export default function LocationPicker({ value, onChange, allowGps = true, autoCentre = true }:
  { value: Picked | null; onChange: (p: Picked) => void; allowGps?: boolean; autoCentre?: boolean }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Place[] | null>(null);
  const [busy, setBusy] = useState<"search" | "gps" | "centre" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const postal = centrePostal();

  const useCentre = async () => {
    if (!postal) return;
    setBusy("centre"); setError(null);
    try {
      const r = await features.locate(postal);
      const p = r.results[0];
      onChange({ label: `My centre — ${title(p.name || p.address)}`, latitude: p.latitude, longitude: p.longitude, source: "centre" });
    } catch (e) { setError(e instanceof ApiError ? e.message : "Couldn't find your centre. Search instead."); }
    setBusy(null);
  };
  useEffect(() => { if (autoCentre && !value && postal) void useCentre(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const useGps = () => {
    if (!("geolocation" in navigator)) { setError("This browser can't share your location. Search for an address below."); return; }
    setBusy("gps"); setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => { setBusy(null); onChange({ label: "My current location", latitude: pos.coords.latitude, longitude: pos.coords.longitude, source: "gps" }); },
      (err) => { setBusy(null); setError(GEO_ERRORS[err.code] ?? "Couldn't get your location. Search for an address below."); },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 });
  };

  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setBusy("search"); setError(null); setResults(null);
    try { setResults((await features.locate(q.trim())).results); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Search failed. Try again."); }
    setBusy(null);
  };

  return (
    <div className="space-y-3">
      {value && (
        <div className="flex items-center gap-2 rounded-xl bg-brand-50 px-3.5 py-2.5 text-sm text-brand-900">
          <MapPin className="h-4 w-4 shrink-0 text-brand-600" /><span className="font-medium">{value.label}</span>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {postal && (
          <button type="button" onClick={useCentre} className="inline-flex h-10 items-center gap-2 rounded-xl border border-ink-200 bg-white px-3.5 text-sm font-medium text-ink-700 hover:border-brand-300">
            {busy === "centre" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Building2 className="h-4 w-4" />} My centre
          </button>
        )}
        {allowGps && (
          <button type="button" onClick={useGps} className="inline-flex h-10 items-center gap-2 rounded-xl border border-ink-200 bg-white px-3.5 text-sm font-medium text-ink-700 hover:border-brand-300">
            {busy === "gps" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Crosshair className="h-4 w-4" />} Use my location
          </button>
        )}
      </div>
      <form onSubmit={search} className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Postal code, address or place, e.g. Bedok Reservoir Park"
          className={clsx(inputClass, "flex-1")} aria-label="Search for a place" maxLength={100} />
        <button type="submit" disabled={q.trim().length < 2 || busy === "search"}
          className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink-900 px-4 text-sm font-medium text-white disabled:opacity-50">
          {busy === "search" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Search
        </button>
      </form>
      {error && <p className="rounded-xl bg-amber-50 px-3.5 py-2.5 text-sm text-amber-900" role="alert">{error}</p>}
      {results && (
        <ul className="divide-y divide-ink-100 overflow-hidden rounded-xl border border-ink-200 bg-white">
          {results.map((r) => (
            <li key={`${r.latitude},${r.longitude}`}>
              <button type="button" className="w-full px-3.5 py-2.5 text-left hover:bg-ink-50"
                onClick={() => { onChange({ label: title(r.name || r.address), latitude: r.latitude, longitude: r.longitude, source: "search" }); setResults(null); setQ(""); }}>
                <span className="block text-sm font-medium text-ink-900">{title(r.name || r.address)}</span>
                <span className="block text-xs text-ink-500">{r.address}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
