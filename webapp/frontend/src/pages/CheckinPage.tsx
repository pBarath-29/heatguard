import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  AlertTriangle, ArrowRight, CalendarCheck, CalendarClock, CheckCircle2, ChevronDown, Download, History, LayoutList, Map as MapIcon,
  MapPin, MessageSquareText, Search, ShieldCheck, Table2, Thermometer, Users, Wind,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import MessageDialog from "../components/MessageDialog";
import { AreaMap } from "../components/Maps";
import { Badge, Banner, BandBadge, Button, Card, EmptyState, ErrorState, inputClass, PageSkeleton, PsiBadge, ScoreRing, Segmented, TierBadge } from "../components/ui";
import { api, type CheckinResponse, type CheckinRow, type DayOutlook, type Tier } from "../lib/api";
import { dayLabel, deg, downloadCsv, num, pct, title } from "../lib/format";
import { DRIVER, TIER } from "../lib/theme";

type TierFilter = "all" | "start" | "checkin";
type View = "list" | "map" | "table";

const LEVEL_STYLE: Record<string, { grad: string; chip: string; icon: React.ReactNode }> = {
  "High heat possible": { grad: "from-red-700 via-brand-700 to-brand-500", chip: "bg-white/15 text-white", icon: <AlertTriangle className="h-5 w-5" /> },
  "Moderate heat": { grad: "from-brand-800 via-brand-600 to-amber-500", chip: "bg-white/15 text-white", icon: <Thermometer className="h-5 w-5" /> },
  "Low heat": { grad: "from-emerald-800 via-emerald-700 to-teal-500", chip: "bg-white/15 text-white", icon: <ShieldCheck className="h-5 w-5" /> },
};

function Outlook({ o, meta }: { o: DayOutlook; meta: CheckinResponse["meta"] }) {
  const style = LEVEL_STYLE[o.level] ?? LEVEL_STYLE["Moderate heat"];
  const when = meta.status === "today" ? "Today" : meta.status === "tomorrow" ? "Tomorrow" : dayLabel(meta.for_date);
  return (
    <div className={clsx("relative overflow-hidden rounded-3xl bg-gradient-to-br p-6 text-white shadow-lift md:p-8", style.grad)}>
      <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
      <div className="relative">
        <div className="flex flex-wrap items-center gap-2">
          <span className={clsx("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-semibold", style.chip)}>{style.icon}{o.level}</span>
          <span className="text-[13px] text-white/80">{when} · {dayLabel(meta.for_date, { long: true, year: true })}</span>
        </div>
        <h1 className="mt-4 max-w-3xl text-2xl font-semibold leading-snug tracking-tight md:text-[30px]">{o.headline}</h1>
        {o.start_here_areas > 0 && <p className="mt-2 text-[15px] text-white/85">First on the list: <b>{o.top_areas}</b>.</p>}
        <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ["Start here", `${o.start_here_areas} areas`, `${num(o.start_here_seniors)} seniors aged 65+`],
            ["Check in", `${o.check_in_areas} areas`, `${num(o.check_in_seniors)} seniors aged 65+`],
            ["High heat possible", `${o.high_alert_areas} areas`, o.max_prob_high != null ? `up to ${pct(o.max_prob_high)} chance` : ""],
            ["Haze", o.worst_psi_band ?? "—", o.worst_psi != null ? `worst PSI ${Math.round(o.worst_psi)}` : ""],
          ].map(([k, v, sub]) => (
            <div key={k} className="rounded-2xl bg-white/10 px-4 py-3 backdrop-blur-sm">
              <div className="text-[12px] font-medium uppercase tracking-wide text-white/70">{k}</div>
              <div className="mt-1 text-xl font-semibold">{v}</div>
              <div className="text-[12px] text-white/75">{sub}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatusNote({ meta }: { meta: CheckinResponse["meta"] }) {
  if (meta.status === "observed")
    return <Banner tone="warning" icon={<CalendarClock className="h-4 w-4" />}><b>Tomorrow's forecast isn't ready yet.</b> Heat shown is the latest observed afternoon peak. The forecast is added after the evening update (about 7 pm).</Banner>;
  if (meta.status === "past")
    return <Banner tone="warning" icon={<History className="h-4 w-4" />}><b>This list is for {dayLabel(meta.for_date, { long: true })}, which has passed.</b> The evening update hasn't run since — use it as a rough guide and let the HeatGuard team know.</Banner>;
  if (meta.status === "today")
    return <Banner tone="info" icon={<CalendarClock className="h-4 w-4" />}>This is <b>today's</b> list. Tomorrow's list appears after this evening's update (about 7 pm).</Banner>;
  return null;
}

function Fact({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 text-[13px] text-ink-600"><span className="text-ink-400">{icon}</span>{children}</span>;
}

function Badges({ r }: { r: CheckinRow }) {
  return (
    <>
      <BandBadge band={r.heat_band} prefix="Heat: " />
      {r.high_alert && r.heat_band !== "High" && <Badge className="bg-red-600 text-white ring-red-700/20"><AlertTriangle className="h-3 w-3" /> High heat possible · {pct(r.prob_high)}</Badge>}
      <PsiBadge band={r.psi_band} value={r.psi_twenty_four_hourly} />
    </>
  );
}

function FullCard({ r, onMessage, sharedAction }: { r: CheckinRow; onMessage: () => void; sharedAction?: string | null }) {
  return (
    <Card padded={false} className="transition hover:border-ink-300 hover:shadow-lift">
      <div className="flex gap-4 p-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-[15px] font-semibold text-white">{r.rank}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/area/${encodeURIComponent(r.subzone_name)}`} className="text-[17px] font-semibold text-ink-900 hover:text-brand-700">{title(r.subzone_name)}</Link>
            <Badges r={r} />
          </div>
          <div className="mt-1 text-sm text-ink-500">{title(r.planning_area)} · {title(r.ura_region)}</div>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
            <Fact icon={<Thermometer className="h-4 w-4" />}>{deg(r.heat_wbgt_c)} {r.heat_is_forecast ? "forecast" : "observed"}</Fact>
            <Fact icon={<Users className="h-4 w-4" />}>{num(r.pop_65_plus)} aged 65+ ({pct(r.pct_65_plus)})</Fact>
            <Fact icon={<MapPin className="h-4 w-4" />}>{r.nearest_cool_space} · {r.cool_space_km} km</Fact>
          </div>
          {r.action !== sharedAction && (
            <div className="mt-4 flex gap-2.5 rounded-xl border border-emerald-100 bg-emerald-50/70 px-3.5 py-3">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              <p className="text-sm leading-relaxed text-emerald-950"><span className="font-semibold">What to do: </span>{r.action}</p>
            </div>
          )}
        </div>
        <div className="hidden sm:block"><ScoreRing score={r.risk_score} color={TIER[r.tier]?.hex ?? "#94A3B8"} /></div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-b-2xl border-t border-ink-100 bg-ink-50/60 px-5 py-3">
        <span className="text-[13px] text-ink-500">Main reason: <span className="font-medium text-ink-800">{DRIVER[r.main_driver]?.label ?? r.main_driver}</span>
          <span className="sm:hidden"> · Risk {Math.round(r.risk_score)}</span></span>
        <div className="flex gap-2">
          <Button size="sm" icon={<MessageSquareText className="h-3.5 w-3.5" />} onClick={onMessage}>Write a message</Button>
          <Link to={`/area/${encodeURIComponent(r.subzone_name)}`} className="inline-flex h-8 items-center gap-1 rounded-xl px-3 text-[13px] font-medium text-brand-700 hover:bg-brand-50">Why here <ArrowRight className="h-3.5 w-3.5" /></Link>
        </div>
      </div>
    </Card>
  );
}

function CompactRow({ r, onMessage }: { r: CheckinRow; onMessage: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5 hover:bg-ink-50/70">
      <span className="w-7 text-sm font-semibold tabular-nums text-ink-400">{r.rank}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link to={`/area/${encodeURIComponent(r.subzone_name)}`} className="font-semibold text-ink-900 hover:text-brand-700">{title(r.subzone_name)}</Link>
          <span className="text-[13px] text-ink-500">{title(r.planning_area)}</span>
          <Badges r={r} />
        </div>
        <div className="mt-0.5 text-[13px] text-ink-500">{num(r.pop_65_plus)} aged 65+ · {deg(r.heat_wbgt_c)} · {r.nearest_cool_space} {r.cool_space_km} km</div>
      </div>
      <div className="flex items-center gap-3">
        <div className="hidden items-center gap-2 md:flex"><div className="h-1.5 w-20 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full" style={{ width: `${r.risk_score}%`, background: TIER[r.tier]?.hex }} /></div><span className="w-6 text-sm font-medium tabular-nums text-ink-700">{Math.round(r.risk_score)}</span></div>
        <button onClick={onMessage} className="rounded-lg p-2 text-ink-400 hover:bg-ink-100 hover:text-ink-700" title="Write a message" aria-label={`Write a message for ${title(r.subzone_name)}`}><MessageSquareText className="h-4 w-4" /></button>
        <Link to={`/area/${encodeURIComponent(r.subzone_name)}`} className="rounded-lg p-2 text-brand-700 hover:bg-brand-50" title="Why here" aria-label={`Why ${title(r.subzone_name)}`}><ArrowRight className="h-4 w-4" /></Link>
      </div>
    </div>
  );
}

function TierSection({ tier, rows, onMessage, defaultOpen = true, limit }: { tier: Tier; rows: CheckinRow[]; onMessage: (r: CheckinRow) => void; defaultOpen?: boolean; limit?: number }) {
  const [open, setOpen] = useState(defaultOpen);
  const [shown, setShown] = useState(limit ?? rows.length);
  const t = TIER[tier];
  if (!rows.length) return null;
  const seniors = rows.reduce((a, r) => a + r.pop_65_plus, 0);
  const counts = new Map<string, number>();
  rows.forEach((r) => counts.set(r.action, (counts.get(r.action) ?? 0) + 1));
  const [common, n] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? [null, 0];
  const shared = n >= Math.max(2, rows.length * 0.6) ? common : null;
  return (
    <section className="space-y-3">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between gap-4 text-left">
        <div>
          <div className="flex items-center gap-2"><TierBadge tier={tier} /><span className="text-[15px] font-semibold text-ink-900">{rows.length} area{rows.length === 1 ? "" : "s"} · {num(seniors)} seniors</span></div>
          <p className="mt-1 text-[13px] text-ink-500">{t.blurb}</p>
        </div>
        <ChevronDown className={clsx("h-5 w-5 shrink-0 text-ink-400 transition", open && "rotate-180")} />
      </button>
      {open && shared && (
        <div className="flex gap-2.5 rounded-xl border border-emerald-100 bg-emerald-50/70 px-4 py-3">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          <p className="text-sm leading-relaxed text-emerald-950"><span className="font-semibold">What to do{n < rows.length ? ` (${n} of ${rows.length} areas — others shown on their card)` : ""}: </span>{shared}</p>
        </div>
      )}
      {open && (tier === "Start here" ? (
        <div className="space-y-3">{rows.map((r) => <FullCard key={r.subzone_name} r={r} onMessage={() => onMessage(r)} sharedAction={shared} />)}</div>
      ) : (
        <Card padded={false} className="divide-y divide-ink-100 overflow-hidden">
          {rows.slice(0, shown).map((r) => <CompactRow key={r.subzone_name} r={r} onMessage={() => onMessage(r)} />)}
          {shown < rows.length && (
            <button onClick={() => setShown(shown + 25)} className="flex w-full items-center justify-center gap-1.5 py-3 text-sm font-medium text-brand-700 hover:bg-ink-50">
              <ChevronDown className="h-4 w-4" /> Show {Math.min(25, rows.length - shown)} more
            </button>
          )}
        </Card>
      ))}
    </section>
  );
}

export default function CheckinPage() {
  const q = useQuery({ queryKey: ["checkin"], queryFn: api.checkin });
  const [search, setSearch] = useState("");
  const [area, setArea] = useState("");
  const [tier, setTier] = useState<TierFilter>("all");
  const [view, setView] = useState<View>("list");
  const [showCool, setShowCool] = useState(false);
  const [messageRow, setMessageRow] = useState<CheckinRow | null>(null);
  const cool = useQuery({ queryKey: ["cool-spaces"], queryFn: api.coolSpaces, enabled: showCool && view === "map" });

  const rows = q.data?.rows ?? [];
  const areas = useMemo(() => [...new Set(rows.map((r) => r.planning_area))].sort(), [rows]);
  const filtered = useMemo(() => {
    const s = search.trim().toUpperCase();
    return rows.filter((r) =>
      (!s || r.subzone_name.includes(s) || r.planning_area.includes(s)) && (!area || r.planning_area === area) &&
      (tier === "all" || (tier === "start" ? r.tier === "Start here" : r.tier !== "Routine")));
  }, [rows, search, area, tier]);

  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load the check-in list" />;
  const { meta, outlook } = q.data;
  if (!rows.length) return <EmptyState title="The check-in list is empty" body="Ask the HeatGuard team to run the daily update, then refresh." />;
  const byTier = (t: Tier) => filtered.filter((r) => r.tier === t);
  const filtering = !!(search || area);

  const exportCsv = () => downloadCsv(`heatguard-checkin-${meta.for_date}.csv`, filtered.map((r) => ({
    Rank: r.rank, Priority: r.tier, Area: title(r.subzone_name), "Planning area": title(r.planning_area), "Risk score": Math.round(r.risk_score),
    Heat: r.heat_band, "High heat possible": r.high_alert ? "Yes" : "No", "Heat (WBGT °C)": r.heat_wbgt_c, "Chance of High": r.prob_high,
    "Seniors 65+": r.pop_65_plus, "Nearest cool space": r.nearest_cool_space, "Distance (km)": r.cool_space_km, Haze: r.psi_band,
    "What to do": r.action, Why: r.reason,
  })));

  return (
    <>
      <div className="space-y-5">
        {outlook && <Outlook o={outlook} meta={meta} />}
        <StatusNote meta={meta} />

        <Card className="!p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <input className={clsx(inputClass, "pl-9")} placeholder="Search an area, e.g. Toa Payoh or Bedok North" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search areas" />
            </div>
            <select className={clsx(inputClass, "lg:w-52")} value={area} onChange={(e) => setArea(e.target.value)} aria-label="Planning area">
              <option value="">All planning areas</option>
              {areas.map((a) => <option key={a} value={a}>{title(a)}</option>)}
            </select>
            <Segmented value={tier} onChange={setTier} options={[{ value: "all", label: "All" }, { value: "start", label: "Start here" }, { value: "checkin", label: "Start + Check in" }]} />
            <Segmented value={view} onChange={setView} options={[
              { value: "list", label: <><LayoutList className="h-4 w-4" /><span className="hidden sm:inline">List</span></> },
              { value: "map", label: <><MapIcon className="h-4 w-4" /><span className="hidden sm:inline">Map</span></> },
              { value: "table", label: <><Table2 className="h-4 w-4" /><span className="hidden sm:inline">Table</span></> },
            ]} />
            <Button icon={<Download className="h-4 w-4" />} onClick={exportCsv} title="Download the areas shown as a spreadsheet">CSV</Button>
          </div>
        </Card>

        {filtered.length === 0 ? (
          <EmptyState title="No areas match" body="Try a different name, choose another planning area, or show all tiers."
            action={<Button onClick={() => { setSearch(""); setArea(""); setTier("all"); }}>Clear filters</Button>} />
        ) : view === "list" ? (
          <div className="space-y-8">
            <TierSection tier="Start here" rows={byTier("Start here")} onMessage={setMessageRow} />
            <TierSection tier="Check in" rows={byTier("Check in")} onMessage={setMessageRow} limit={15} />
            <TierSection tier="Routine" rows={byTier("Routine")} onMessage={setMessageRow} defaultOpen={filtering} limit={25} />
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
                  <tr>{["#", "Priority", "Area", "Risk", "Heat", "Chance of High", "Seniors 65+", "Nearest cool space"].map((h) => <th key={h} className="whitespace-nowrap px-4 py-3">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {filtered.map((r) => (
                    <tr key={r.subzone_name} className="hover:bg-ink-50/70">
                      <td className="px-4 py-3 font-medium text-ink-500">{r.rank}</td>
                      <td className="px-4 py-3"><TierBadge tier={r.tier} /></td>
                      <td className="px-4 py-3"><Link className="font-medium text-ink-900 hover:text-brand-700" to={`/area/${encodeURIComponent(r.subzone_name)}`}>{title(r.subzone_name)}</Link><div className="text-xs text-ink-500">{title(r.planning_area)}</div></td>
                      <td className="px-4 py-3 font-medium tabular-nums">{Math.round(r.risk_score)}</td>
                      <td className="px-4 py-3"><BandBadge band={r.heat_band} /></td>
                      <td className="px-4 py-3 tabular-nums">{pct(r.prob_high)}</td>
                      <td className="px-4 py-3 tabular-nums">{num(r.pop_65_plus)}</td>
                      <td className="px-4 py-3">{r.nearest_cool_space}<div className="text-xs text-ink-500">{r.cool_space_km} km</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        <p className="flex items-center gap-1.5 text-xs text-ink-400"><CalendarCheck className="h-3.5 w-3.5" /> {meta.heat_basis}. Haze is the latest reading (there is no official haze forecast). <Wind className="ml-1 h-3.5 w-3.5" /> Area-level data only.</p>
      </div>
      {messageRow && <MessageDialog row={messageRow} onClose={() => setMessageRow(null)} />}
    </>
  );
}
