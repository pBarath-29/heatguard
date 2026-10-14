import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  AlertTriangle, ArrowRight, CalendarCheck, CalendarClock, CheckCircle2, ChevronDown, Download, HelpCircle, History, LayoutList,
  Map as MapIcon, MapPin, MessageSquareText, Search, Table2, Thermometer, Users, Wind,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import MessageDialog from "../components/MessageDialog";
import { AreaMap } from "../components/Maps";
import { Badge, Banner, BandBadge, Button, Card, EmptyState, ErrorState, inputClass, PageHeader, PageSkeleton, PsiBadge, ScoreRing, Segmented, Stat } from "../components/ui";
import { api, type CheckinResponse, type CheckinRow } from "../lib/api";
import { dayLabel, deg, downloadCsv, num, pct, title } from "../lib/format";
import { BAND, DRIVER } from "../lib/theme";

type Level = "all" | "moderate" | "high";
type View = "list" | "map" | "table";
const PAGE = 10;

function StatusBanner({ meta }: { meta: CheckinResponse["meta"] }) {
  const model = meta.heat_basis.match(/\(model (v\d+)\)/)?.[1];
  if (meta.status === "observed")
    return <Banner tone="warning" icon={<CalendarClock className="h-4 w-4" />}><b>Tomorrow's forecast isn't ready yet.</b> Heat shown is the latest observed afternoon peak. The forecast is added after the evening update (about 7 pm).</Banner>;
  if (meta.status === "past")
    return <Banner tone="warning" icon={<History className="h-4 w-4" />}><b>This list is for {dayLabel(meta.for_date, { long: true })}, which has passed.</b> The evening update hasn't run since — use it as a rough guide and let the HeatGuard team know.</Banner>;
  if (meta.status === "today")
    return <Banner tone="info" icon={<CalendarClock className="h-4 w-4" />}><b>This is today's list.</b> Tomorrow's list appears after this evening's update (about 7 pm).</Banner>;
  return <Banner tone="success" icon={<CalendarCheck className="h-4 w-4" />}><b>Ready for {dayLabel(meta.for_date, { long: true })}.</b> Heat is HeatGuard's forecast{model ? ` (model ${model})` : ""}; haze is the latest reading, as there is no official haze forecast.</Banner>;
}

function Fact({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 text-[13px] text-ink-600"><span className="text-ink-400">{icon}</span>{children}</span>;
}

function AreaCard({ row, onMessage }: { row: CheckinRow; onMessage: () => void }) {
  const band = row.action_band ? BAND[row.action_band] : null;
  const top = row.rank <= 3;
  return (
    <Card padded={false} className="transition hover:border-ink-300 hover:shadow-lift">
      <div className="flex gap-4 p-5">
        <div className={clsx("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[15px] font-semibold", top ? "bg-brand-600 text-white" : "bg-ink-100 text-ink-700")}>
          {row.rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/area/${encodeURIComponent(row.subzone_name)}`} className="text-[17px] font-semibold text-ink-900 hover:text-brand-700">{title(row.subzone_name)}</Link>
            <BandBadge band={row.action_band} prefix="Heat: " />
            {row.high_alert && row.heat_band !== "High" && (
              <Badge className="bg-red-600 text-white ring-red-700/20"><AlertTriangle className="h-3 w-3" /> High heat possible · {pct(row.prob_high)}</Badge>
            )}
            <PsiBadge band={row.psi_band} value={row.psi_twenty_four_hourly} />
          </div>
          <div className="mt-1 text-sm text-ink-500">{title(row.planning_area)} · {title(row.ura_region)}</div>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
            <Fact icon={<Thermometer className="h-4 w-4" />}>{deg(row.heat_wbgt_c)} {row.heat_is_forecast ? "forecast" : "observed"}</Fact>
            <Fact icon={<Users className="h-4 w-4" />}>{num(row.pop_65_plus)} aged 65+ ({pct(row.pct_65_plus)})</Fact>
            <Fact icon={<MapPin className="h-4 w-4" />}>{row.nearest_cool_space} · {row.cool_space_km} km</Fact>
            {row.pct_1_2_room != null && row.pct_1_2_room >= 0.05 && <Fact icon={<Wind className="h-4 w-4" />}>{pct(row.pct_1_2_room)} in 1–2 room flats</Fact>}
          </div>
          <div className="mt-4 flex gap-2.5 rounded-xl border border-emerald-100 bg-emerald-50/70 px-3.5 py-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
            <p className="text-sm leading-relaxed text-emerald-950"><span className="font-semibold">What to do: </span>{row.action}</p>
          </div>
        </div>
        <div className="hidden flex-col items-center gap-1 sm:flex">
          <ScoreRing score={row.risk_score} color={band?.hex ?? "#94A3B8"} />
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-b-2xl border-t border-ink-100 bg-ink-50/60 px-5 py-3">
        <span className="text-[13px] text-ink-500">Main reason: <span className="font-medium text-ink-800">{DRIVER[row.main_driver]?.label ?? row.main_driver}</span>
          <span className="sm:hidden"> · Risk {Math.round(row.risk_score)}</span></span>
        <div className="flex gap-2">
          <Button size="sm" icon={<MessageSquareText className="h-3.5 w-3.5" />} onClick={onMessage}>Write a message</Button>
          <Link to={`/area/${encodeURIComponent(row.subzone_name)}`}
            className="inline-flex h-8 items-center gap-1 rounded-xl px-3 text-[13px] font-medium text-brand-700 hover:bg-brand-50">Why here <ArrowRight className="h-3.5 w-3.5" /></Link>
        </div>
      </div>
    </Card>
  );
}

function HowTo() {
  const [open, setOpen] = useState(false);
  const steps = [
    ["Start at the top", "Areas are ranked by risk: tomorrow's heat, haze, how many vulnerable seniors live there, and how far they are from a cool space."],
    ["Follow 'What to do'", "Each area shows the action for its heat and haze level. A red 'High heat possible' badge means plan as for a High day."],
    ["Share it", "Use 'Write a message' for a ready-to-send note in English, Chinese, Malay or Tamil, or download the list for your team."],
  ];
  return (
    <Card padded={false}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-5 py-3.5 text-left">
        <span className="flex items-center gap-2 text-sm font-medium text-ink-800"><HelpCircle className="h-4 w-4 text-ink-400" /> How to use this list</span>
        <ChevronDown className={clsx("h-4 w-4 text-ink-400 transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="grid gap-3 border-t border-ink-100 p-5 md:grid-cols-3">
          {steps.map(([t, b], i) => (
            <div key={t} className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">{i + 1}</span>
              <div><div className="text-sm font-semibold text-ink-900">{t}</div><p className="mt-0.5 text-[13px] leading-relaxed text-ink-500">{b}</p></div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function CheckinPage() {
  const q = useQuery({ queryKey: ["checkin"], queryFn: api.checkin });
  const [search, setSearch] = useState("");
  const [area, setArea] = useState("");
  const [level, setLevel] = useState<Level>("all");
  const [view, setView] = useState<View>("list");
  const [shown, setShown] = useState(PAGE);
  const [showCool, setShowCool] = useState(false);
  const [messageRow, setMessageRow] = useState<CheckinRow | null>(null);
  const cool = useQuery({ queryKey: ["cool-spaces"], queryFn: api.coolSpaces, enabled: showCool && view === "map" });

  const rows = q.data?.rows ?? [];
  const areas = useMemo(() => [...new Set(rows.map((r) => r.planning_area))].sort(), [rows]);
  const filtered = useMemo(() => {
    const s = search.trim().toUpperCase();
    return rows.filter((r) =>
      (!s || r.subzone_name.includes(s) || r.planning_area.includes(s)) &&
      (!area || r.planning_area === area) &&
      (level === "all" || (level === "high" ? r.action_band === "High" : r.action_band === "High" || r.action_band === "Moderate")));
  }, [rows, search, area, level]);

  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load the check-in list" />;
  const { meta } = q.data;
  if (!rows.length) return <EmptyState title="The check-in list is empty" body="Ask the HeatGuard team to run the daily update, then refresh." />;

  const high = rows.filter((r) => r.action_band === "High").length;
  const moderate = rows.filter((r) => r.action_band === "Moderate").length;
  const seniorsTop = rows.filter((r) => r.rank <= 20).reduce((a, r) => a + r.pop_65_plus, 0);
  const worstHaze = rows.reduce<CheckinRow | null>((w, r) => (r.psi_twenty_four_hourly ?? -1) > (w?.psi_twenty_four_hourly ?? -1) ? r : w, null);
  const resetPaging = () => setShown(PAGE);

  const exportCsv = () => downloadCsv(`heatguard-checkin-${meta.for_date}.csv`, filtered.map((r) => ({
    Rank: r.rank, Area: title(r.subzone_name), "Planning area": title(r.planning_area), "Risk score": Math.round(r.risk_score),
    "Heat level": r.action_band, "High heat possible": r.high_alert ? "Yes" : "No", "Heat (WBGT °C)": r.heat_wbgt_c,
    "Chance of High": r.prob_high, "Seniors 65+": r.pop_65_plus, "Nearest cool space": r.nearest_cool_space, "Distance (km)": r.cool_space_km,
    Haze: r.psi_band, "What to do": r.action, Why: r.reason,
  })));

  return (
    <>
      <PageHeader
        eyebrow={<Badge className="bg-brand-50 text-brand-800 ring-brand-600/20"><CalendarCheck className="h-3.5 w-3.5" /> {dayLabel(meta.for_date, { long: true, year: true })}</Badge>}
        title={meta.status === "today" ? "Today's check-in list" : "Tomorrow's check-in list"}
        subtitle="Where to check on seniors first, and what to do — ranked from NEA heat and haze data, Census 2020 and distance to cool spaces."
        right={<Button icon={<Download className="h-4 w-4" />} onClick={exportCsv}>Download CSV</Button>}
      />
      <div className="space-y-5">
        <StatusBanner meta={meta} />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="High-heat alerts" value={high} tone={high ? "text-red-600" : "text-emerald-600"} sub={`of ${rows.length} areas with seniors`}
            hint="Areas forecast High, or with a meaningful chance of High heat. Use the High heat actions." icon={<AlertTriangle className="h-4 w-4" />} />
          <Stat label="Moderate heat" value={moderate} tone={moderate ? "text-amber-600" : "text-emerald-600"} sub="areas (WBGT 31–32.9 °C)" icon={<Thermometer className="h-4 w-4" />} />
          <Stat label="Seniors in top 20 areas" value={num(seniorsTop)} sub="residents aged 65+" icon={<Users className="h-4 w-4" />}
            hint="Residents aged 65+ in the 20 highest-priority areas (Census 2020)." />
          <Stat label="Haze" value={worstHaze?.psi_band ?? "—"} tone="text-ink-900" icon={<Wind className="h-4 w-4" />}
            sub={worstHaze?.psi_twenty_four_hourly != null ? `Worst PSI ${Math.round(worstHaze.psi_twenty_four_hourly)} · ${title(worstHaze.haze_region)}` : "No reading"} />
        </div>
        <HowTo />

        <Card className="!p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <input className={clsx(inputClass, "pl-9")} placeholder="Search an area, e.g. Toa Payoh or Bedok North" value={search}
                onChange={(e) => { setSearch(e.target.value); resetPaging(); }} aria-label="Search areas" />
            </div>
            <select className={clsx(inputClass, "lg:w-56")} value={area} onChange={(e) => { setArea(e.target.value); resetPaging(); }} aria-label="Planning area">
              <option value="">All planning areas</option>
              {areas.map((a) => <option key={a} value={a}>{title(a)}</option>)}
            </select>
            <Segmented value={level} onChange={(v) => { setLevel(v); resetPaging(); }}
              options={[{ value: "all", label: "All" }, { value: "moderate", label: "Moderate+" }, { value: "high", label: "High alerts" }]} />
            <Segmented value={view} onChange={setView} options={[
              { value: "list", label: <><LayoutList className="h-4 w-4" /><span className="hidden sm:inline">List</span></> },
              { value: "map", label: <><MapIcon className="h-4 w-4" /><span className="hidden sm:inline">Map</span></> },
              { value: "table", label: <><Table2 className="h-4 w-4" /><span className="hidden sm:inline">Table</span></> },
            ]} />
          </div>
        </Card>

        <div className="flex items-center justify-between text-sm text-ink-500">
          <span>{filtered.length === rows.length ? `${rows.length} areas, highest priority first` : `${filtered.length} of ${rows.length} areas match`}</span>
          {(search || area || level !== "all") && (
            <button className="font-medium text-brand-700 hover:text-brand-800" onClick={() => { setSearch(""); setArea(""); setLevel("all"); resetPaging(); }}>Clear filters</button>
          )}
        </div>

        {filtered.length === 0 ? (
          <EmptyState title="No areas match these filters" body="Try a different name, choose another planning area, or show all heat levels." />
        ) : view === "list" ? (
          <div className="space-y-3">
            {filtered.slice(0, shown).map((r) => <AreaCard key={r.subzone_name} row={r} onMessage={() => setMessageRow(r)} />)}
            {shown < filtered.length && (
              <div className="flex justify-center pt-2">
                <Button onClick={() => setShown(shown + PAGE)} icon={<ChevronDown className="h-4 w-4" />}>Show {Math.min(PAGE, filtered.length - shown)} more</Button>
              </div>
            )}
          </div>
        ) : view === "map" ? (
          <Card className="!p-3">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 px-2">
              <p className="text-[13px] text-ink-500">Circle size = residents aged 65+ · colour = risk score (amber → deep red) · click an area for details.</p>
              <label className="flex items-center gap-2 text-[13px] font-medium text-ink-700">
                <input type="checkbox" className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500" checked={showCool} onChange={(e) => setShowCool(e.target.checked)} />
                Show Community Clubs & libraries
              </label>
            </div>
            <AreaMap rows={filtered} coolSpaces={showCool ? cool.data : undefined} />
          </Card>
        ) : (
          <Card padded={false} className="overflow-hidden">
            <div className="max-h-[640px] overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 z-10 bg-ink-50 text-xs font-semibold uppercase tracking-wide text-ink-500">
                  <tr>{["#", "Area", "Risk", "Heat", "Chance of High", "Seniors 65+", "Nearest cool space", "Haze"].map((h) => <th key={h} className="whitespace-nowrap px-4 py-3">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {filtered.map((r) => (
                    <tr key={r.subzone_name} className="hover:bg-ink-50/70">
                      <td className="px-4 py-3 font-medium text-ink-500">{r.rank}</td>
                      <td className="px-4 py-3"><Link className="font-medium text-ink-900 hover:text-brand-700" to={`/area/${encodeURIComponent(r.subzone_name)}`}>{title(r.subzone_name)}</Link><div className="text-xs text-ink-500">{title(r.planning_area)}</div></td>
                      <td className="px-4 py-3"><div className="flex items-center gap-2"><div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${r.risk_score}%` }} /></div><span className="font-medium tabular-nums">{Math.round(r.risk_score)}</span></div></td>
                      <td className="px-4 py-3"><BandBadge band={r.action_band} /></td>
                      <td className="px-4 py-3 tabular-nums">{pct(r.prob_high)}</td>
                      <td className="px-4 py-3 tabular-nums">{num(r.pop_65_plus)}</td>
                      <td className="px-4 py-3">{r.nearest_cool_space}<div className="text-xs text-ink-500">{r.cool_space_km} km</div></td>
                      <td className="px-4 py-3"><PsiBadge band={r.psi_band} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
      {messageRow && <MessageDialog row={messageRow} onClose={() => setMessageRow(null)} />}
    </>
  );
}
