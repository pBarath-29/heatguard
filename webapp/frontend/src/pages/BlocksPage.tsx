import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Building, Footprints, Info, MapPin, Navigation, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import LocationPicker, { type Picked } from "../components/LocationPicker";
import MapKit, { type Marker } from "../components/MapKit";
import { Button, EmptyState, ErrorState, Field, inputClass, PageHeader, Segmented, Skeleton } from "../components/ui";
import { ApiError, features, type Block, type RouteResponse } from "../lib/api";
import { dayLabel, title } from "../lib/format";

const key = (b: Pick<Block, "blk_no" | "street">) => `${b.blk_no}|${b.street}`;
const blockName = (b: Block) => `Blk ${b.blk_no} ${title(b.street_full || b.street)}`;
const TOP = "#C2410C", OTHER = "#94A3B8", NONE = "#E2E8F0";

function RouteResult({ r }: { r: RouteResponse }) {
  const tone = r.timing.status === "ok" ? "bg-emerald-50 text-emerald-950 border-emerald-200" : r.timing.status === "too_hot" ? "bg-red-50 text-red-950 border-red-200" : "bg-ink-50 text-ink-800 border-ink-200";
  return (
    <section className="space-y-4 rounded-3xl border border-ink-200 bg-white p-5 shadow-card" aria-live="polite">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900"><Footprints className="h-5 w-5" />Walking round · {dayLabel(r.date, { long: true })}</h2>
      <div className={clsx("rounded-2xl border p-4 text-[15px]", tone)}>{r.advice}</div>
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-2xl bg-ink-50 p-3"><div className="text-xs text-ink-500">Walking</div><div className="text-lg font-semibold">~{r.walk_min} min</div><div className="text-xs text-ink-500">{r.walk_km.toFixed(1)} km</div></div>
        <div className="rounded-2xl bg-ink-50 p-3"><div className="text-xs text-ink-500">Visits</div><div className="text-lg font-semibold">{r.visit_min} min</div><div className="text-xs text-ink-500">{r.stops.length} blocks</div></div>
        <div className="rounded-2xl bg-ink-50 p-3"><div className="text-xs text-ink-500">Total</div><div className="text-lg font-semibold">~{Math.round(r.total_min / 5) * 5} min</div></div>
      </div>
      <ol className="space-y-1.5">
        <li className="flex items-center gap-3 text-sm text-ink-600"><span className="grid h-7 w-7 place-items-center rounded-full bg-ink-900 text-xs font-semibold text-white">S</span>{r.start.label}</li>
        {r.stops.map((s, i) => (
          <li key={key(s)} className="flex items-center gap-3 text-[15px] text-ink-900">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-600 text-xs font-semibold text-white">{i + 1}</span>
            <span className="flex-1">{blockName(s)}</span>
            <span className="text-xs text-ink-500">{r.legs[i] ? `~${r.legs[i].walk_min} min walk` : ""}</span>
          </li>
        ))}
      </ol>
      {r.missing.length > 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Left out (no map location): {r.missing.join(", ")}</p>}
      <a href={r.directions_url} target="_blank" rel="noreferrer" className="inline-flex h-12 items-center gap-2 rounded-xl bg-brand-600 px-5 text-base font-medium text-white hover:bg-brand-700">
        <Navigation className="h-5 w-5" />Open walking directions
      </a>
      <p className="text-xs text-ink-500">{r.assumptions} Directions open in Google Maps; walking times there may differ.</p>
    </section>
  );
}

export default function BlocksPage() {
  const [params, setParams] = useSearchParams();
  const subzone = params.get("area") ?? "";
  const [near, setNear] = useState<Picked | null>(null);
  const [filters, setFilters] = useState<{ min_rental?: number; year_from?: number; year_to?: number; min_floor?: number }>({});
  const [showFilters, setShowFilters] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [start, setStart] = useState<Picked | null>(null);
  const [visit, setVisit] = useState(15);
  const [day, setDay] = useState<"today" | "tomorrow">("tomorrow");
  const [focus, setFocus] = useState<string | null>(null);

  const sz = useQuery({ queryKey: ["subzones", near?.latitude, near?.longitude], queryFn: () => features.subzones(near?.latitude, near?.longitude) });
  const bq = useQuery({ queryKey: ["blocks", subzone, filters], queryFn: () => features.blocks(subzone, filters), enabled: !!subzone });
  const route = useMutation({ mutationFn: () => {
    const all = [...(bq.data?.ranking.top ?? []), ...(bq.data?.blocks ?? [])];
    const stops = picked.map((k) => all.find((b) => key(b) === k)!).filter(Boolean).map((b) => ({ blk_no: b.blk_no, street: b.street }));
    return features.route({ subzone, stops, start_latitude: start!.latitude, start_longitude: start!.longitude, start_label: start!.label, visit_min: visit, day });
  } });

  useEffect(() => { setPicked([]); setFocus(null); route.reset(); setFilters({}); }, [subzone]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (bq.data && picked.length === 0) setPicked(bq.data.ranking.top.map(key)); }, [bq.data]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { route.reset(); }, [picked, start, visit, day]); // eslint-disable-line react-hooks/exhaustive-deps

  const d = bq.data;
  const topKeys = useMemo(() => new Set(d?.ranking.top.map(key) ?? []), [d]);
  const focusBlock = d ? [...d.ranking.top, ...d.blocks].find((b) => key(b) === focus) : undefined;
  const toggle = (k: string) => setPicked((p) => p.includes(k) ? p.filter((x) => x !== k) : p.length >= 10 ? p : [...p, k]);

  const markers: Marker[] = useMemo(() => {
    if (!d) return [];
    const byKey = new Map(d.blocks.map((b) => [key(b), b]));
    d.ranking.top.forEach((b) => byKey.set(key(b), b));
    const ranks = new Map(d.ranking.top.map((b) => [key(b), b.rank]));
    const m: Marker[] = [...byKey.values()].map((b) => {
      const k = key(b), top = topKeys.has(k);
      return { id: k, lat: b.latitude, lon: b.longitude, color: top ? TOP : b.rental_total > 0 ? OTHER : NONE, radius: top ? 12 : b.rental_total > 0 ? 6 : 4,
        label: top ? String(ranks.get(k)) : undefined, selected: focus === k, ring: picked.includes(k) && !top ? "#C2410C" : undefined, onClick: () => setFocus(k),
        tooltip: <span><b>{blockName(b)}</b><br />{b.rental_total} rental flats (1-room {b.rental_1room ?? 0}, 2-room {b.rental_2room ?? 0})</span> };
    });
    if (start) m.push({ id: "start", lat: start.latitude, lon: start.longitude, color: "#111827", radius: 8, label: "S", tooltip: start.label });
    return m;
  }, [d, topKeys, focus, picked, start]);
  const line: [number, number][] | undefined = route.data ? [[route.data.start.latitude, route.data.start.longitude], ...route.data.stops.map((s) => [s.latitude, s.longitude] as [number, number])] : undefined;

  const num = (v: string) => (v === "" ? undefined : Number(v));

  return (
    <>
      <PageHeader title="Block Radar" subtitle="Where in an area to start outreach: HDB blocks with the most 1- and 2-room rental flats, and a walking round to visit them." />

      <section className="mb-5 space-y-4 rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
        <Field label="Area (subzone)" group>
          {sz.isPending ? <Skeleton className="h-10 rounded-xl" /> : sz.isError ? <ErrorState error={sz.error} onRetry={() => sz.refetch()} title="Couldn't load the list of areas" /> : (
            <select aria-label="Area (subzone)" className={inputClass} value={subzone} onChange={(e) => setParams(e.target.value ? { area: e.target.value } : {})}>
              <option value="">Choose an area…</option>
              {sz.data!.subzones.map((s) => (
                <option key={s.subzone_name} value={s.subzone_name}>
                  {title(s.subzone_name)} ({title(s.planning_area)}){s.distance_km != null ? ` · ${s.distance_km} km` : ""}{s.tier === "Start here" ? " · Start here" : ""} — {s.rental_flats.toLocaleString()} rental flats
                </option>))}
            </select>)}
          <p className="mt-1.5 text-xs text-ink-500">{near ? `Nearest to ${near.label} first.` : "Today's check-in priority first. Pick a place below to sort by distance instead."}</p>
        </Field>
        <details className="group"><summary className="cursor-pointer text-sm font-medium text-brand-700">Find areas near a place</summary>
          <div className="mt-3"><LocationPicker value={near} onChange={setNear} autoCentre={false} /></div></details>
      </section>

      {!subzone ? <EmptyState title="Choose an area to begin" body="You'll see the six blocks with the most 1- and 2-room rental flats, marked on a map." /> :
        bq.isPending ? <div className="space-y-4"><Skeleton className="h-[460px] rounded-3xl" /><Skeleton className="h-40 rounded-3xl" /></div> :
        bq.isError ? <ErrorState error={bq.error} onRetry={() => bq.refetch()} title={bq.error instanceof ApiError && bq.error.status === 404 ? "No blocks found here" : "Couldn't load the blocks"} /> : d && (
        <div className="space-y-5">
          <section className="rounded-3xl border border-brand-200 bg-brand-50/60 p-5">
            <h2 className="text-lg font-semibold text-ink-900">{title(d.subzone)} · {title(d.planning_area)}</h2>
            {d.ranking.top_share != null ? (
              <p className="mt-1 text-[15px] text-ink-800">
                The top {d.ranking.top.length} block{d.ranking.top.length !== 1 ? "s" : ""} hold <b>{Math.round(d.ranking.top_share * 100)}%</b> of the area's 1- and 2-room rental flats
                ({d.ranking.top_rental_total.toLocaleString()} of {d.ranking.subzone_rental_total.toLocaleString()}, across {d.ranking.blocks_with_rental} blocks that have any).
              </p>
            ) : <p className="mt-1 text-[15px] text-ink-800">{d.ranking.note}</p>}
            {d.ranking.note && d.ranking.top_share != null && <p className="mt-1 text-sm text-ink-600">{d.ranking.note}</p>}
            <p className="mt-2 flex gap-1.5 text-xs text-ink-600"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />{d.proxy_note}</p>
          </section>

          <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
            <section className="rounded-3xl border border-ink-200 bg-white p-3 shadow-card">
              <MapKit markers={markers} line={line} fitKey={`${d.subzone}-${!!route.data}`} />
              <div className="flex flex-wrap gap-x-4 gap-y-1 px-2 pt-3 text-xs text-ink-600">
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full" style={{ background: TOP }} />Top {d.ranking.top.length} (numbered)</span>
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: OTHER }} />Other blocks with rental flats</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full border border-ink-300" style={{ background: NONE }} />No rental flats</span>
                {start && <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-ink-900" />Start</span>}
              </div>
            </section>

            <section className="space-y-3">
              <h2 className="text-base font-semibold text-ink-900">Top blocks — tick to include in the round</h2>
              {d.ranking.top.map((b) => {
                const k = key(b), on = picked.includes(k);
                return (
                  <div key={k} className={clsx("rounded-2xl border bg-white p-3.5 shadow-card", focus === k ? "border-ink-900" : "border-ink-200")}>
                    <div className="flex items-start gap-3">
                      <input type="checkbox" aria-label={`Include ${blockName(b)}`} checked={on} onChange={() => toggle(k)} className="mt-1 h-5 w-5 rounded border-ink-300 text-brand-600" />
                      <button type="button" className="flex-1 text-left" onClick={() => setFocus(k)}>
                        <div className="flex items-center gap-2"><span className="grid h-6 w-6 place-items-center rounded-full bg-brand-600 text-xs font-semibold text-white">{b.rank}</span>
                          <span className="font-semibold text-ink-900">{blockName(b)}</span></div>
                        <div className="mt-1 text-sm text-ink-700"><b>{b.rental_total}</b> rental flats · 1-room {b.rental_1room ?? 0} · 2-room {b.rental_2room ?? 0}</div>
                        {b.flags && b.flags.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{b.flags.map((f) => <span key={f} className="rounded-full bg-ink-100 px-2 py-0.5 text-[11px] text-ink-700">{f}</span>)}</div>}
                      </button>
                    </div>
                  </div>);
              })}
              {focusBlock && !topKeys.has(key(focusBlock)) && (
                <div className="rounded-2xl border border-ink-900 bg-white p-3.5">
                  <div className="font-semibold text-ink-900">{blockName(focusBlock)}</div>
                  <div className="mt-1 text-sm text-ink-700">{focusBlock.rental_total} rental flats · built {focusBlock.year_completed ?? "—"} · {focusBlock.max_floor ?? "—"} floors</div>
                  {focusBlock.rental_total > 0 && <Button size="sm" className="mt-2" onClick={() => toggle(key(focusBlock))}>{picked.includes(key(focusBlock)) ? "Remove from round" : "Add to round"}</Button>}
                </div>)}
              <p className="text-xs text-ink-500">{d.flag_note}</p>
            </section>
          </div>

          <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
            <button type="button" className="flex items-center gap-2 text-sm font-medium text-ink-700" onClick={() => setShowFilters((s) => !s)} aria-expanded={showFilters}>
              <SlidersHorizontal className="h-4 w-4" />Filter the map ({d.blocks.length} of {d.total_blocks} blocks shown)
            </button>
            {showFilters && (
              <div className="mt-4 grid gap-3 sm:grid-cols-4">
                <Field label="At least N rental flats"><input type="number" min={0} className={inputClass} value={filters.min_rental ?? ""} onChange={(e) => setFilters({ ...filters, min_rental: num(e.target.value) })} /></Field>
                <Field label="Built from (year)"><input type="number" min={1930} max={2030} className={inputClass} value={filters.year_from ?? ""} onChange={(e) => setFilters({ ...filters, year_from: num(e.target.value) })} /></Field>
                <Field label="Built up to (year)"><input type="number" min={1930} max={2030} className={inputClass} value={filters.year_to ?? ""} onChange={(e) => setFilters({ ...filters, year_to: num(e.target.value) })} /></Field>
                <Field label="At least N floors"><input type="number" min={1} max={60} className={inputClass} value={filters.min_floor ?? ""} onChange={(e) => setFilters({ ...filters, min_floor: num(e.target.value) })} /></Field>
                <div className="sm:col-span-4 flex items-center gap-3">
                  <Button size="sm" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={() => setFilters({})}>Clear filters</Button>
                  <span className="text-xs text-ink-500">Filters change the map only — the top blocks and percentage always use the whole area.</span>
                </div>
              </div>)}
          </section>

          <section className="space-y-4 rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900"><MapPin className="h-5 w-5" />Plan a walking round</h2>
            <Field label="Start from (e.g. your centre)" group><LocationPicker value={start} onChange={setStart} /></Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Minutes at each block"><input type="number" min={5} max={90} step={5} className={inputClass} value={visit} onChange={(e) => setVisit(Math.max(5, Math.min(90, Number(e.target.value) || 15)))} /></Field>
              <Field label="Day" group><Segmented value={day} onChange={setDay} options={[{ value: "today", label: "Today" }, { value: "tomorrow", label: "Tomorrow" }]} /></Field>
            </div>
            <Button variant="primary" className="h-12 w-full text-base sm:w-auto" icon={<Building className="h-5 w-5" />} disabled={!start || picked.length === 0} loading={route.isPending} onClick={() => route.mutate()}>
              Plan a round of {picked.length} block{picked.length !== 1 ? "s" : ""}
            </Button>
            {!start && <p className="text-sm text-ink-500">Choose a starting point to plan the round.</p>}
            {picked.length >= 10 && <p className="text-sm text-ink-500">A round can include up to 10 blocks.</p>}
            {route.isError && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">{route.error instanceof ApiError ? route.error.message : "Couldn't plan the round."}</p>}
          </section>
          {route.data && <RouteResult r={route.data} />}

          <p className="text-xs leading-relaxed text-ink-500">
            Source: {d.source.dataset}{d.source.loaded_at ? `, loaded ${dayLabel(d.source.loaded_at.slice(0, 10))}` : ""}. Locations: {d.source.locations}.
            {d.unplaced_in_town.blocks > 0 && ` ${d.unplaced_in_town.blocks} block${d.unplaced_in_town.blocks !== 1 ? "s" : ""} with ${d.unplaced_in_town.rental_flats.toLocaleString()} rental flats in ${title(d.planning_area)} couldn't be placed on the map exactly, so they aren't counted in any area.`}
          </p>
        </div>
      )}
    </>
  );
}
