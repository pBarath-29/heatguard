import { useQuery } from "@tanstack/react-query";
import { Activity, Clock, Radio, Thermometer, Wind } from "lucide-react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StationMap } from "../components/Maps";
import { Banner, BandBadge, Card, CardTitle, EmptyState, ErrorState, PageHeader, PageSkeleton, Stat } from "../components/ui";
import { api } from "../lib/api";
import { dayLabel, deg, hoursSince, sgtDateTime, shortDate, timeAgo, title } from "../lib/format";
import { BAND, CHART, PSI } from "../lib/theme";

export default function NowPage() {
  const q = useQuery({ queryKey: ["now"], queryFn: api.now });
  if (q.isPending) return <PageSkeleton rows={2} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load the latest readings" />;
  const { stations, haze, daily, latest_reading_ts } = q.data;
  if (!stations.length) return <EmptyState title="No station readings yet" body="Ask the HeatGuard team to run the data update." />;

  const hottest = stations.reduce((a, s) => (s.wbgt_c > a.wbgt_c ? s : a));
  const hotToday = stations.reduce((a, s) => (s.peak_so_far_today_c > a.peak_so_far_today_c ? s : a));
  const modPlus = stations.filter((s) => s.heat_band !== "Low").length;
  const worst = haze.length ? haze.reduce((a, h) => (h.psi_twenty_four_hourly > a.psi_twenty_four_hourly ? h : a)) : null;
  const stale = hoursSince(latest_reading_ts) > 2;
  const trend = daily.map((d) => ({ ...d, date: d.date_sgt.slice(0, 10) }));

  return (
    <>
      <PageHeader title="Heat & haze now" subtitle="Latest readings from NEA's heat-stress stations and haze regions, and how the last month compares." />
      <div className="space-y-5">
        {stale ? (
          <Banner tone="warning" icon={<Clock className="h-4 w-4" />}><b>Readings are from {sgtDateTime(latest_reading_ts)} ({timeAgo(latest_reading_ts)}).</b> Live 15-minute updates may be switched off to save Databricks quota; the check-in list is still updated every evening.</Banner>
        ) : (
          <Banner tone="success" icon={<Radio className="h-4 w-4" />}>Latest readings: <b>{sgtDateTime(latest_reading_ts)}</b> ({timeAgo(latest_reading_ts)}). NEA updates heat every 15 minutes and haze every hour.</Banner>
        )}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Hottest station now" value={deg(hottest.wbgt_c)} tone={BAND[hottest.heat_band]?.text} sub={hottest.station_name} icon={<Thermometer className="h-4 w-4" />} />
          <Stat label="Stations Moderate or High" value={modPlus} tone={modPlus ? "text-amber-600" : "text-emerald-600"} sub={`of ${stations.length} reporting`} icon={<Activity className="h-4 w-4" />} />
          <Stat label="Hottest so far today" value={deg(hotToday.peak_so_far_today_c)} tone={BAND[hotToday.peak_so_far_band]?.text} sub={hotToday.station_name} icon={<Thermometer className="h-4 w-4" />} />
          <Stat label="Worst haze" value={worst ? `PSI ${Math.round(worst.psi_twenty_four_hourly)}` : "—"} tone={worst ? PSI[worst.psi_band]?.text : undefined}
            sub={worst ? `${worst.psi_band} · ${title(worst.region)}` : "No reading"} icon={<Wind className="h-4 w-4" />} />
        </div>

        <div className="grid gap-5 lg:grid-cols-5">
          <Card className="lg:col-span-3 !p-3">
            <div className="flex items-center justify-between px-2 pb-3 pt-1">
              <h3 className="text-[15px] font-semibold text-ink-900">Heat by station</h3>
              <div className="flex gap-3 text-xs text-ink-500">{(["Low", "Moderate", "High"] as const).map((b) => <span key={b} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: BAND[b].hex }} />{b}</span>)}</div>
            </div>
            <StationMap stations={stations} />
          </Card>
          <Card className="lg:col-span-2">
            <CardTitle icon={<Wind className="h-4 w-4" />} title="Haze by region" subtitle="24-hour PSI (NEA)" />
            <div className="space-y-2.5">
              {haze.map((h) => {
                const p = PSI[h.psi_band] ?? PSI.Moderate;
                return (
                  <div key={h.region} className="flex items-center gap-3 rounded-xl border border-ink-100 px-3.5 py-3">
                    <div className="h-10 w-1.5 rounded-full" style={{ background: p.hex }} />
                    <div className="flex-1">
                      <div className="text-sm font-medium text-ink-900">{title(h.region)}</div>
                      <div className="text-xs text-ink-500">at {h.time_sgt}{h.pm25_one_hourly != null ? ` · PM2.5 ${Math.round(h.pm25_one_hourly)} µg/m³` : ""}</div>
                    </div>
                    <div className="text-right"><div className="text-lg font-semibold tabular-nums" style={{ color: p.hex }}>{Math.round(h.psi_twenty_four_hourly)}</div><div className="text-xs" style={{ color: p.hex }}>{h.psi_band}</div></div>
                  </div>
                );
              })}
            </div>
            <p className="mt-3 text-xs leading-relaxed text-ink-400">Good ≤ 50 · Moderate 51–100 · Unhealthy 101–200 · Very unhealthy 201–300 · Hazardous &gt; 300</p>
          </Card>
        </div>

        {trend.length > 0 && (
          <Card>
            <CardTitle title="The last 30 days" subtitle="Afternoon peak WBGT (lines) and worst haze of the day (bars)" />
            <div className="h-80">
              <ResponsiveContainer>
                <ComposedChart data={trend} margin={{ left: -6, right: 4, top: 8 }}>
                  <CartesianGrid stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 12, fill: CHART.axis }} minTickGap={24} />
                  <YAxis yAxisId="t" domain={["dataMin - 1", "dataMax + 1"]} tick={{ fontSize: 12, fill: CHART.axis }} tickFormatter={(v) => `${Math.round(v)}°`} />
                  <YAxis yAxisId="p" orientation="right" tick={{ fontSize: 12, fill: CHART.axis }} />
                  <Tooltip labelFormatter={(d) => dayLabel(String(d))}
                    formatter={(v: number, n: string) => (n === "Worst PSI" ? [Math.round(v), n] : [deg(v), n])} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar yAxisId="p" dataKey="worst_psi_24h" name="Worst PSI" fill="#E2E8F0" radius={[4, 4, 0, 0]} />
                  <ReferenceLine yAxisId="t" y={31} stroke={BAND.Moderate.hex} strokeDasharray="4 4" />
                  <ReferenceLine yAxisId="t" y={33} stroke={BAND.High.hex} strokeDasharray="4 4" />
                  <Line yAxisId="t" dataKey="hottest_peak_wbgt_c" name="Hottest station" stroke={BAND.High.hex} strokeWidth={2.5} dot={false} />
                  <Line yAxisId="t" dataKey="avg_peak_wbgt_c" name="Average of stations" stroke={CHART.brand} strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-ink-400">Dashed lines: Moderate (31°C) and High (33°C) heat stress. Right axis: 24-hour PSI.</p>
          </Card>
        )}

        <Card padded={false} className="overflow-hidden">
          <div className="px-5 pt-5"><CardTitle title="All stations" subtitle="Latest reading and today's peak so far" /></div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-ink-50 text-xs font-semibold uppercase tracking-wide text-ink-500">
                <tr>{["Station", "Near", "Now", "Level", "Today's peak", "Time"].map((h) => <th key={h} className="whitespace-nowrap px-5 py-3">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {stations.map((s) => (
                  <tr key={s.station_id} className="hover:bg-ink-50/70">
                    <td className="px-5 py-3 font-medium text-ink-900">{s.station_name}</td>
                    <td className="px-5 py-3 text-ink-500">{s.town_center}</td>
                    <td className="px-5 py-3 tabular-nums">{deg(s.wbgt_c)}</td>
                    <td className="px-5 py-3"><BandBadge band={s.heat_band} /></td>
                    <td className="px-5 py-3 tabular-nums">{deg(s.peak_so_far_today_c)}</td>
                    <td className="px-5 py-3 text-ink-500">{s.latest_time_sgt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
