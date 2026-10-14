import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, CheckCircle2, ExternalLink, Gauge, MapPin, MessageSquareText, Snowflake, Thermometer, Users } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import MessageDialog from "../components/MessageDialog";
import { Badge, BandBadge, Button, Card, CardTitle, ErrorState, PageSkeleton, PsiBadge, ScoreRing } from "../components/ui";
import { ApiError, api, type AreaResponse } from "../lib/api";
import { dayLabel, deg, num, pct, shortDate, title } from "../lib/format";
import { BAND, CHART, COMPONENT_COLORS, DRIVER } from "../lib/theme";

const PARTS: { key: "heat" | "vulnerability" | "haze" | "access"; label: string }[] = [
  { key: "heat", label: "Heat" }, { key: "vulnerability", label: "Vulnerable seniors" },
  { key: "haze", label: "Haze" }, { key: "access", label: "Distance to cool space" },
];
const STATION_COLORS = ["#EA580C", "#7C3AED", "#0284C7"];

function Breakdown({ data }: { data: AreaResponse }) {
  const { row, weights } = data;
  const w = Object.fromEntries(weights.filter((x) => x.score === "risk_score").map((x) => [x.component, x.weight]));
  const explain: Record<string, string> = {
    heat: row.heat_wbgt_c != null ? `${deg(row.heat_wbgt_c)} (${row.heat_band}). Scores nothing at 29°C and fully at 34°C.` : "No heat value.",
    vulnerability: `${row.vulnerability_score.toFixed(2)} of 1 — compared with other areas on seniors, small flats, living alone and daily-activity difficulty.`,
    haze: row.psi_twenty_four_hourly != null ? `PSI ${Math.round(row.psi_twenty_four_hourly)} (${row.psi_band}). Scores nothing up to PSI 50 and fully at 200.` : "No haze reading.",
    access: `${row.cool_space_km} km to ${row.nearest_cool_space}. Scores nothing at the door and fully at 2 km or more.`,
  };
  const comp: Record<string, number | null> = { heat: row.heat_component, vulnerability: row.vulnerability_component, haze: row.haze_component, access: row.access_component };
  const bars = PARTS.map((p) => ({ ...p, points: +(100 * (w[p.key] ?? 0) * (comp[p.key] ?? 0)).toFixed(1), max: Math.round(100 * (w[p.key] ?? 0)) }));
  return (
    <Card>
      <CardTitle icon={<Gauge className="h-4 w-4" />} title="How the risk score adds up" subtitle={`${Math.round(row.risk_score)} points out of 100, from four parts`} />
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="h-56 lg:col-span-2">
          <ResponsiveContainer>
            <BarChart data={bars} layout="vertical" margin={{ left: 8, right: 24 }}>
              <CartesianGrid horizontal={false} stroke={CHART.grid} />
              <XAxis type="number" domain={[0, 35]} tick={{ fontSize: 12, fill: CHART.axis }} />
              <YAxis type="category" dataKey="label" width={130} tick={{ fontSize: 12, fill: CHART.ink }} />
              <Tooltip formatter={(v: number, _n, p) => [`${v} of ${p.payload.max} points`, "Score"]} cursor={{ fill: "#F8FAFC" }} />
              <Bar dataKey="points" barSize={18} radius={[0, 6, 6, 0]} background={{ fill: "#F1F5F9", radius: 6 }}>
                {bars.map((b) => <Cell key={b.key} fill={COMPONENT_COLORS[b.key]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-3 lg:col-span-3">
          {bars.map((b) => (
            <div key={b.key} className="flex gap-3">
              <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: COMPONENT_COLORS[b.key] }} />
              <div className="flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm font-medium text-ink-900">{b.label}</span>
                  <span className="text-sm tabular-nums text-ink-500"><b className="text-ink-900">{b.points}</b> / {b.max}</span>
                </div>
                <p className="text-[13px] leading-relaxed text-ink-500">{explain[b.key]}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function Trend({ data }: { data: AreaResponse }) {
  const names = [...new Set(data.stations.map((s) => s.station_name))];
  const byDate = new Map<string, Record<string, number | string>>();
  for (const p of data.peaks) {
    const d = p.date_sgt.slice(0, 10);
    const rec = byDate.get(d) ?? { date: d };
    rec[p.station_name] = p.afternoon_peak_wbgt_c;
    byDate.set(d, rec);
  }
  for (const f of data.forecasts) {
    const d = f.target_date.slice(0, 10);
    const rec = byDate.get(d) ?? { date: d };
    rec[`fc_${f.station_name}`] = f.predicted_peak_wbgt_c;
    byDate.set(d, rec);
  }
  const rows = [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  if (!rows.length) return null;
  return (
    <Card>
      <CardTitle icon={<Thermometer className="h-4 w-4" />} title="Recent afternoon heat near this area"
        subtitle="Daily afternoon peak at the stations used for this area · diamonds show HeatGuard's forecast" />
      <div className="h-72">
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ left: -10, right: 12, top: 8 }}>
            <CartesianGrid stroke={CHART.grid} vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 12, fill: CHART.axis }} minTickGap={24} />
            <YAxis domain={["dataMin - 1", "dataMax + 1"]} tick={{ fontSize: 12, fill: CHART.axis }} tickFormatter={(v) => `${Math.round(v)}°`} />
            <Tooltip labelFormatter={(d) => dayLabel(String(d))} formatter={(v: number, n: string) => [deg(v), n.startsWith("fc_") ? `${n.slice(3)} (forecast)` : n]} />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={(v: string) => (v.startsWith("fc_") ? `${v.slice(3)} forecast` : v)} />
            <ReferenceLine y={31} stroke={BAND.Moderate.hex} strokeDasharray="4 4" label={{ value: "Moderate", fontSize: 11, fill: BAND.Moderate.hex, position: "insideTopLeft" }} />
            <ReferenceLine y={33} stroke={BAND.High.hex} strokeDasharray="4 4" label={{ value: "High", fontSize: 11, fill: BAND.High.hex, position: "insideTopLeft" }} />
            {names.map((n, i) => <Line key={n} dataKey={n} stroke={STATION_COLORS[i % 3]} strokeWidth={2} dot={false} connectNulls />)}
            {names.map((n, i) => <Scatter key={`fc_${n}`} dataKey={`fc_${n}`} fill={STATION_COLORS[i % 3]} shape="diamond" legendType="diamond" />)}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export default function AreaPage() {
  const { name = "" } = useParams();
  const q = useQuery({ queryKey: ["area", name], queryFn: () => api.area(name), retry: (n, e) => !(e instanceof ApiError && e.status === 404) && n < 1 });
  const [messageOpen, setMessageOpen] = useState(false);

  if (q.isPending) return <PageSkeleton rows={2} />;
  if (q.isError) return (
    <div className="space-y-4">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"><ArrowLeft className="h-4 w-4" /> Back to the list</Link>
      <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load this area" />
    </div>
  );
  const data = q.data;
  const r = data.row;
  const band = r.action_band ? BAND[r.action_band] : null;
  const nearest = Math.min(...data.stations.map((s) => s.distance_km));
  const confidence = nearest <= 2 ? ["High", `Measured by a station ${nearest.toFixed(1)} km away.`] :
    nearest <= 5 ? ["Medium", `Nearest station ${nearest.toFixed(1)} km away; heat is blended from ${data.stations.length} stations.`] :
      ["Lower", `Nearest station is ${nearest.toFixed(1)} km away, so local heat may differ.`];
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${r.nearest_cool_space} Singapore ${r.nearest_cool_space_postal ?? ""}`)}`;

  return (
    <>
      <Link to="/" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"><ArrowLeft className="h-4 w-4" /> Back to the list</Link>
      <Card className="mb-5">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="text-[13px] font-medium text-ink-500">Priority #{r.rank} of {data.total_areas} · {title(r.planning_area)} · {title(r.ura_region)}</div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink-900 md:text-[28px]">{title(r.subzone_name)}</h1>
            <div className="mt-3 flex flex-wrap gap-2">
              <BandBadge band={r.action_band} prefix="Heat: " />
              {r.high_alert && r.heat_band !== "High" && <Badge className="bg-red-600 text-white ring-red-700/20"><AlertTriangle className="h-3 w-3" /> High heat possible · {pct(r.prob_high)}</Badge>}
              <PsiBadge band={r.psi_band} value={r.psi_twenty_four_hourly} />
              <Badge className="bg-brand-50 text-brand-800 ring-brand-600/20">Main reason: {DRIVER[r.main_driver]?.label}</Badge>
            </div>
            <p className="mt-3 text-[13px] text-ink-500">{r.heat_basis}</p>
          </div>
          <div className="flex items-center gap-4">
            <ScoreRing score={r.risk_score} color={band?.hex ?? "#94A3B8"} size={84} />
            <Button variant="primary" icon={<MessageSquareText className="h-4 w-4" />} onClick={() => setMessageOpen(true)}>Write a message</Button>
          </div>
        </div>
        <div className="mt-5 flex gap-2.5 rounded-xl border border-emerald-100 bg-emerald-50/70 px-4 py-3.5">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
          <p className="text-[15px] leading-relaxed text-emerald-950"><span className="font-semibold">What to do: </span>{r.action}</p>
        </div>
      </Card>

      <div className="space-y-5">
        <Breakdown data={data} />
        <div className="grid gap-5 lg:grid-cols-3">
          <Card>
            <CardTitle icon={<Users className="h-4 w-4" />} title="Who lives here" subtitle="Census 2020" />
            <dl className="space-y-3 text-sm">
              {[
                ["Residents aged 65+", `${num(r.pop_65_plus)} (${pct(r.pct_65_plus)})`],
                ["Aged 75+", `${num(r.pop_75_plus)} (${pct(r.pct_75_plus)})`],
                ["In 1–2 room HDB flats", pct(r.pct_1_2_room)],
                ["One-person households*", pct(r.pa_pct_one_person)],
                ["Daily-activity difficulty*", pct(r.pa_pct_difficulty)],
              ].map(([k, v]) => <div key={k} className="flex justify-between gap-4 border-b border-ink-100 pb-2.5 last:border-0"><dt className="text-ink-500">{k}</dt><dd className="font-medium text-ink-900 tabular-nums">{v}</dd></div>)}
            </dl>
            <p className="mt-3 text-xs text-ink-400">*{r.pa_data_published ? `Figures for ${title(r.planning_area)} planning area.` : `Singapore-wide rate — the Census doesn't publish this for ${title(r.planning_area)}.`}</p>
          </Card>
          <Card>
            <CardTitle icon={<Thermometer className="h-4 w-4" />} title="Heat" subtitle={r.heat_is_forecast ? `Forecast for ${dayLabel(r.for_date)}` : "Latest observed afternoon peak"} />
            <div className="flex items-end gap-3"><span className="text-4xl font-semibold tracking-tight" style={{ color: band?.hex }}>{deg(r.heat_wbgt_c)}</span><span className="pb-1"><BandBadge band={r.heat_band} /></span></div>
            {r.heat_is_forecast && (
              <div className="mt-4 space-y-3">
                {[["Chance of Moderate or higher", r.prob_moderate_plus, BAND.Moderate.hex], ["Chance of High", r.prob_high, BAND.High.hex]].map(([k, v, c]) => (
                  <div key={k as string}>
                    <div className="mb-1 flex justify-between text-[13px]"><span className="text-ink-500">{k}</span><span className="font-medium text-ink-900">{pct(v as number)}</span></div>
                    <div className="h-2 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full" style={{ width: `${((v as number) ?? 0) * 100}%`, background: c as string }} /></div>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-4 rounded-xl bg-ink-50 px-3 py-2.5 text-[13px] text-ink-600"><span className="font-medium text-ink-900">Measurement confidence: {confidence[0]}.</span> {confidence[1]}</div>
          </Card>
          <Card>
            <CardTitle icon={<Snowflake className="h-4 w-4" />} title="Nearest cool space" subtitle="Free and air-conditioned" />
            <div className="text-lg font-semibold text-ink-900">{r.nearest_cool_space}</div>
            <div className="mt-0.5 text-sm text-ink-500">{r.nearest_cool_space_type}</div>
            {(r.nearest_cool_space_street || r.nearest_cool_space_postal) && (
              <div className="mt-2 flex items-start gap-1.5 text-sm text-ink-600"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />{[r.nearest_cool_space_street, r.nearest_cool_space_postal && `Singapore ${r.nearest_cool_space_postal}`].filter(Boolean).join(", ")}</div>
            )}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-ink-50 px-3 py-2.5"><div className="text-xs text-ink-500">Distance</div><div className="text-lg font-semibold text-ink-900">{r.cool_space_km} km</div></div>
              <div className="rounded-xl bg-ink-50 px-3 py-2.5"><div className="text-xs text-ink-500">Within 1 km</div><div className="text-lg font-semibold text-ink-900">{r.cool_spaces_within_1km}</div></div>
            </div>
            <a href={mapsUrl} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-800">Open in Google Maps <ExternalLink className="h-3.5 w-3.5" /></a>
            <p className="mt-2 text-xs text-ink-400">Straight-line distance from the area's centre.</p>
          </Card>
        </div>
        <Trend data={data} />
        <Card>
          <CardTitle title="Weather stations used for this area" subtitle="Closer stations count more (inverse-distance weighting)" />
          <div className="space-y-3">
            {data.stations.map((s, i) => (
              <div key={s.station_id} className="flex items-center gap-4">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: STATION_COLORS[i % 3] }} />
                <span className="w-56 truncate text-sm font-medium text-ink-900">{s.station_name}</span>
                <span className="w-20 text-sm tabular-nums text-ink-500">{s.distance_km.toFixed(1)} km</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full bg-ink-700" style={{ width: `${s.weight * 100}%` }} /></div>
                <span className="w-12 text-right text-sm tabular-nums text-ink-700">{pct(s.weight)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
      {messageOpen && <MessageDialog row={r} onClose={() => setMessageOpen(false)} />}
    </>
  );
}
