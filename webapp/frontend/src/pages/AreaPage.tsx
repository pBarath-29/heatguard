import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, CheckCircle2, ExternalLink, Gauge, MapPin, MessageSquareText, Snowflake, Thermometer, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import MessageDialog from "../components/MessageDialog";
import { Badge, BandBadge, Button, Card, CardTitle, ErrorState, PageSkeleton, PsiBadge, ScoreRing, TierBadge } from "../components/ui";
import { ApiError, api, type AreaResponse } from "../lib/api";
import { dayLabel, deg, num, pct, shortDate, title } from "../lib/format";
import { BAND, CHART, COMPONENT_COLORS, DRIVER, TIER } from "../lib/theme";

function Part({ label, value, max, color, note }: { label: string; value: number; max: number; color: string; note: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm"><span className="font-medium text-ink-800">{label}</span><span className="tabular-nums text-ink-500"><b className="text-ink-900">{value.toFixed(2)}</b> / {max}</span></div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full" style={{ width: `${Math.min(100, (value / max) * 100)}%`, background: color }} /></div>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-500">{note}</p>
    </div>
  );
}

function Breakdown({ data }: { data: AreaResponse }) {
  const r = data.row;
  const vulnPart = 0.7 * r.vulnerability_score, accessPart = 0.3 * (r.access_component ?? 0);
  return (
    <Card>
      <CardTitle icon={<Gauge className="h-4 w-4" />} title="How the risk score is worked out" subtitle="Risk = how dangerous the day is × how exposed the people here are" />
      <div className="mb-6 flex flex-wrap items-center justify-center gap-3 rounded-2xl bg-ink-50 px-4 py-5 text-center">
        <div><div className="text-3xl font-semibold tabular-nums" style={{ color: COMPONENT_COLORS.heat }}>{r.hazard.toFixed(2)}</div><div className="text-xs font-medium uppercase tracking-wide text-ink-500">Hazard</div></div>
        <span className="text-2xl text-ink-300">×</span>
        <div><div className="text-3xl font-semibold tabular-nums" style={{ color: COMPONENT_COLORS.vulnerability }}>{r.exposure.toFixed(2)}</div><div className="text-xs font-medium uppercase tracking-wide text-ink-500">Exposure</div></div>
        <span className="text-2xl text-ink-300">× 100 =</span>
        <div><div className="text-3xl font-semibold tabular-nums text-ink-900">{Math.round(r.risk_score)}</div><div className="text-xs font-medium uppercase tracking-wide text-ink-500">Risk score</div></div>
      </div>
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-4">
          <h4 className="text-sm font-semibold text-ink-900">Hazard — how dangerous {r.heat_is_forecast ? "the forecast day" : "the day"} is</h4>
          <Part label="Heat" value={r.heat_hazard} max={1} color={COMPONENT_COLORS.heat}
            note={r.heat_is_forecast ? `Half from the ${pct(r.prob_moderate_plus)} chance of Moderate-or-higher heat, half from the ${pct(r.prob_high)} chance of High heat (full at 50%).` : `Fixed value for the observed ${r.heat_band} band (no forecast available).`} />
          <Part label="Haze" value={r.haze_hazard} max={0.3} color={COMPONENT_COLORS.haze}
            note={r.psi_twenty_four_hourly != null ? `PSI ${Math.round(r.psi_twenty_four_hourly)} (${r.psi_band}). Adds nothing at PSI 50 and up to 0.3 at PSI 200.` : "No haze reading."} />
        </div>
        <div className="space-y-4">
          <h4 className="text-sm font-semibold text-ink-900">Exposure — who would be affected here</h4>
          <Part label="Vulnerable seniors (70%)" value={vulnPart} max={0.7} color={COMPONENT_COLORS.vulnerability}
            note={`Vulnerability ${r.vulnerability_score.toFixed(2)} of 1, compared with other areas on seniors, small flats, living alone and daily-activity difficulty.`} />
          <Part label="Distance to a cool space (30%)" value={accessPart} max={0.3} color={COMPONENT_COLORS.access}
            note={`${r.cool_space_km} km to ${r.nearest_cool_space}. Nothing at the door, full at 2 km or more.`} />
          <p className="text-[13px] text-ink-500">More exposed than {pct(r.exposure_pctl)} of areas with seniors.</p>
        </div>
      </div>
    </Card>
  );
}

const STATION_COLORS = ["#EA580C", "#7C3AED", "#0284C7"];

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
  const navigate = useNavigate();
  const back = (e: React.MouseEvent) => { if (window.history.length > 1) { e.preventDefault(); navigate(-1); } };

  if (q.isPending) return <PageSkeleton rows={2} />;
  if (q.isError) return (
    <div className="space-y-4">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"><ArrowLeft className="h-4 w-4" /> Back to the list</Link>
      <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load this area" />
    </div>
  );
  const data = q.data;
  const r = data.row;
  const band = r.heat_band ? BAND[r.heat_band] : null;
  const nearest = Math.min(...data.stations.map((s) => s.distance_km));
  const confidence = nearest <= 2 ? ["High", `Measured by a station ${nearest.toFixed(1)} km away.`] :
    nearest <= 5 ? ["Medium", `Nearest station ${nearest.toFixed(1)} km away; heat is blended from ${data.stations.length} stations.`] :
      ["Lower", `Nearest station is ${nearest.toFixed(1)} km away, so local heat may differ.`];
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${r.nearest_cool_space} Singapore ${r.nearest_cool_space_postal ?? ""}`)}`;

  return (
    <>
      <Link to="/" onClick={back} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"><ArrowLeft className="h-4 w-4" /> Back</Link>
      <Card className="mb-5">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="text-[13px] font-medium text-ink-500">#{r.rank} of {data.total_areas} · {title(r.planning_area)} · {title(r.ura_region)}</div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink-900 md:text-[28px]">{title(r.subzone_name)}</h1>
            <div className="mt-3 flex flex-wrap gap-2">
              <TierBadge tier={r.tier} />
              <BandBadge band={r.heat_band} prefix="Heat: " />
              {r.high_alert && r.heat_band !== "High" && <Badge className="bg-red-600 text-white ring-red-700/20"><AlertTriangle className="h-3 w-3" /> High heat possible · {pct(r.prob_high)}</Badge>}
              <PsiBadge band={r.psi_band} value={r.psi_twenty_four_hourly} />
              <Badge className="bg-brand-50 text-brand-800 ring-brand-600/20">Main reason: {DRIVER[r.main_driver]?.label}</Badge>
            </div>
            <p className="mt-3 text-[13px] text-ink-500">{r.heat_basis}</p>
          </div>
          <div className="flex items-center gap-4">
            <ScoreRing score={r.risk_score} color={TIER[r.tier]?.hex ?? "#94A3B8"} size={84} />
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
