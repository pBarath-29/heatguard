import { useQuery } from "@tanstack/react-query";
import { BarChart3, Crosshair, FlaskConical, Hourglass, ShieldAlert, Target } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Banner, Card, CardTitle, EmptyState, ErrorState, PageHeader, PageSkeleton, Stat } from "../components/ui";
import { api } from "../lib/api";
import { dayLabel, deg, pct, shortDate } from "../lib/format";
import { CHART } from "../lib/theme";

export default function AccuracyPage() {
  const q = useQuery({ queryKey: ["accuracy"], queryFn: api.accuracy });
  if (q.isPending) return <PageSkeleton rows={2} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load forecast accuracy" />;
  const { evaluation, backtest, importance, track_record } = q.data;
  const hg = evaluation.find((e) => e.model.startsWith("HeatGuard"));
  if (!hg) return <EmptyState title="No evaluation results yet" body="Ask the HeatGuard team to run the forecast training notebook." />;
  const base = evaluation.filter((e) => !e.model.startsWith("HeatGuard")).sort((a, b) => a.mae - b.mae)[0];
  const better = 1 - hg.mae / base.mae;
  const methods = [...evaluation].sort((a, b) => a.mae - b.mae).map((e) => ({ name: e.model.replace(/ \(.*\)/, ""), mae: +e.mae.toFixed(3), hg: e.model.startsWith("HeatGuard") }));
  const caught = evaluation.map((e) => ({ name: e.model.replace(/ \(.*\)/, ""), high: e.high_recall ?? 0, hg: e.model.startsWith("HeatGuard") }));
  const series = backtest.map((b) => ({ ...b, date: b.target_date.slice(0, 10) }));
  const baseName = backtest[0]?.baseline_name ?? "7-day average";

  return (
    <>
      <PageHeader title="How accurate is the forecast?" subtitle="HeatGuard was tested on recent months it never saw while learning, and compared with simple rules of thumb." />
      <div className="space-y-5">
        <Banner tone="info" icon={<FlaskConical className="h-4 w-4" />}>
          <b>Test period: {hg.test_period}</b> · {hg.station_days.toLocaleString()} station-days · model version {hg.model_version}. None of these days were used to build or tune the model.
        </Banner>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Average miss" value={`${hg.mae.toFixed(2)} °C`} tone="text-emerald-600" icon={<Crosshair className="h-4 w-4" />} sub={`vs ${base.mae.toFixed(2)} °C for "${base.model}"`}
            hint="Average difference between the forecast and the real afternoon peak." />
          <Stat label="Within 1 °C" value={pct(hg.within_1c)} tone="text-emerald-600" icon={<Target className="h-4 w-4" />} sub={`vs ${pct(base.within_1c)} for the best simple rule`} />
          <Stat label="High-heat days caught" value={pct(hg.high_recall)} tone="text-red-600" icon={<ShieldAlert className="h-4 w-4" />} sub="flagged the evening before"
            hint="Of the station-days that really reached High (WBGT ≥ 33 °C), the share HeatGuard had flagged." />
          <Stat label="Alerts that were High" value={pct(hg.high_precision)} tone="text-amber-600" icon={<BarChart3 className="h-4 w-4" />} sub="most others were Moderate days"
            hint="Alerts lean towards caution on purpose: an extra phone call costs little, a missed High day can cost a senior's health." />
        </div>
        <Card className="bg-gradient-to-br from-emerald-50/80 to-white">
          <p className="text-[15px] leading-relaxed text-ink-800">
            <b>In short:</b> HeatGuard misses by <b>{pct(better)} less</b> than the best simple rule ("{base.model}") and its High-heat alert caught{" "}
            <b>{pct(hg.high_recall)}</b> of High-heat days, compared with {pct(base.high_recall)} for that rule. Alerts lean towards caution on purpose — an extra phone call costs little; a missed High day can cost a senior's health.
          </p>
        </Card>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardTitle title="Average miss by method" subtitle="Lower is better" />
            <div className="h-56">
              <ResponsiveContainer>
                <BarChart data={methods} layout="vertical" margin={{ left: 8, right: 30 }}>
                  <CartesianGrid horizontal={false} stroke={CHART.grid} />
                  <XAxis type="number" tick={{ fontSize: 12, fill: CHART.axis }} tickFormatter={(v) => `${v}°`} domain={[0, 1.2]} ticks={[0, 0.3, 0.6, 0.9, 1.2]} />
                  <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12, fill: CHART.ink }} />
                  <Tooltip formatter={(v: number) => [`${v.toFixed(2)} °C`, "Average miss"]} cursor={{ fill: "#F8FAFC" }} />
                  <Bar dataKey="mae" barSize={22} radius={[0, 6, 6, 0]} label={{ position: "right", fontSize: 12, fill: CHART.ink, formatter: (v: number) => v.toFixed(2) }}>
                    {methods.map((m) => <Cell key={m.name} fill={m.hg ? CHART.good : CHART.muted} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-ink-400">"Persistence" = tomorrow will be like today. "7-day average" = tomorrow will be like the past week.</p>
          </Card>
          <Card>
            <CardTitle title="High-heat days caught" subtitle="Share of real High days flagged the evening before" />
            <div className="h-56">
              <ResponsiveContainer>
                <BarChart data={caught} layout="vertical" margin={{ left: 8, right: 30 }}>
                  <CartesianGrid horizontal={false} stroke={CHART.grid} />
                  <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fontSize: 12, fill: CHART.axis }} />
                  <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12, fill: CHART.ink }} />
                  <Tooltip formatter={(v: number) => [pct(v), "Caught"]} cursor={{ fill: "#F8FAFC" }} />
                  <Bar dataKey="high" barSize={22} radius={[0, 6, 6, 0]} label={{ position: "right", fontSize: 12, fill: CHART.ink, formatter: (v: number) => pct(v) }}>
                    {caught.map((m) => <Cell key={m.name} fill={m.hg ? "#DC2626" : CHART.muted} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <Card>
          <CardTitle title="Forecast vs what happened" subtitle="Test period, average across all stations each day" />
          <div className="h-80">
            <ResponsiveContainer>
              <LineChart data={series} margin={{ left: -6, right: 8, top: 8 }}>
                <CartesianGrid stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 12, fill: CHART.axis }} minTickGap={32} />
                <YAxis domain={["dataMin - 0.5", "dataMax + 0.5"]} tick={{ fontSize: 12, fill: CHART.axis }} tickFormatter={(v) => `${Math.round(v)}°`} />
                <Tooltip labelFormatter={(d) => dayLabel(String(d))} formatter={(v: number, n: string) => [deg(v), n]} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line dataKey="baseline" name={`${baseName} rule`} stroke={CHART.muted} strokeWidth={1.8} dot={false} />
                <Line dataKey="heatguard" name="HeatGuard forecast" stroke={CHART.good} strokeWidth={2.2} dot={false} />
                <Line dataKey="actual" name="What happened" stroke={CHART.ink} strokeWidth={2.4} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs text-ink-400">The green line should follow the black line more closely than the grey one.</p>
        </Card>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardTitle title="What the forecast relies on" subtitle="How much worse the forecast gets if each input is scrambled" />
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={importance.slice(0, 8)} layout="vertical" margin={{ left: 8, right: 30 }}>
                  <CartesianGrid horizontal={false} stroke={CHART.grid} />
                  <XAxis type="number" tick={{ fontSize: 12, fill: CHART.axis }} tickFormatter={(v) => `${v.toFixed(2)}°`} />
                  <YAxis type="category" dataKey="feature" width={190} tick={{ fontSize: 12, fill: CHART.ink }} />
                  <Tooltip formatter={(v: number) => [`+${v.toFixed(3)} °C`, "Extra miss"]} cursor={{ fill: "#F8FAFC" }} />
                  <Bar dataKey="mae_increase_c" fill="#6B8FB5" barSize={16} radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <CardTitle icon={<Hourglass className="h-4 w-4" />} title="Live track record" subtitle="Every daily forecast compared with what happened" />
            {track_record.length === 0 ? (
              <p className="text-sm text-ink-500">Live forecasts started recently. Results appear the day after each forecasted day has been observed.</p>
            ) : (
              <div className="overflow-hidden rounded-xl border border-ink-200">
                <table className="w-full text-left text-sm">
                  <thead className="bg-ink-50 text-xs font-semibold uppercase tracking-wide text-ink-500"><tr>{["Day", "Avg miss", "Right level", "High days caught"].map((h) => <th key={h} className="px-4 py-2.5">{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-ink-100">
                    {track_record.map((t) => (
                      <tr key={t.target_date}>
                        <td className="px-4 py-2.5 font-medium text-ink-900">{dayLabel(t.target_date)}</td>
                        <td className="px-4 py-2.5 tabular-nums">{t.avg_error_c.toFixed(2)} °C</td>
                        <td className="px-4 py-2.5 tabular-nums">{pct(t.band_correct)}</td>
                        <td className="px-4 py-2.5 tabular-nums">{t.stations_high ? `${t.high_caught} of ${t.stations_high}` : "No High days"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
