import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { CloudSun, Droplets, Info, RefreshCw, Thermometer } from "lucide-react";
import { useState } from "react";
import LocationPicker, { type Picked } from "../components/LocationPicker";
import { Button, ErrorState, PageHeader, Segmented, Skeleton } from "../components/ui";
import { features, type NeaPeriod, type PointForecast } from "../lib/api";
import { dayLabel } from "../lib/format";
import { heatWords, hourLabel, sgtDateTime, sgtNow, sgtTime, useSgtToday } from "../lib/heat";

function Tag({ kind }: { kind: "observed" | "forecast" | "estimate" }) {
  const s = { observed: "bg-sky-100 text-sky-800", forecast: "bg-violet-100 text-violet-800", estimate: "bg-ink-100 text-ink-700" }[kind];
  const t = { observed: "Measured", forecast: "NEA forecast", estimate: "Estimate" }[kind];
  return <span className={clsx("rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide", s)}>{t}</span>;
}

function HourStrip({ hours }: { hours: { h: number; v: number; kind: "observed" | "estimate" }[] }) {
  if (!hours.length) return <p className="text-sm text-ink-500">No hour-by-hour values available.</p>;
  return (
    <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
      {hours.map(({ h, v, kind }) => {
        const w = heatWords(v);
        return (
          <div key={h} className={clsx("w-20 shrink-0 rounded-2xl border p-2.5 text-center", kind === "estimate" ? "border-dashed border-ink-300 bg-white" : "border-ink-200 bg-ink-50")}>
            <div className="text-xs font-medium text-ink-500">{hourLabel(h)}</div>
            <div className={clsx("mx-auto mt-1.5 inline-block rounded-full px-2 py-0.5 text-xs font-semibold", w.cls)}>{w.word}</div>
            <div className="mt-1 text-[11px] text-ink-500">{v.toFixed(1)}°</div>
            <div className="text-[10px] uppercase tracking-wide text-ink-400">{kind === "observed" ? "measured" : "estimate"}</div>
          </div>
        );
      })}
    </div>
  );
}

function Periods({ periods }: { periods: NeaPeriod[] }) {
  if (!periods.length) return <p className="text-sm text-ink-500">NEA hasn't published a forecast for this part of the day.</p>;
  return (
    <ul className="divide-y divide-ink-100">
      {periods.map((p) => (
        <li key={p.start} className="flex items-center justify-between gap-3 py-2.5 text-sm">
          <span className="text-ink-600">{p.label}</span><span className="font-medium text-ink-900">{p.forecast}</span>
        </li>
      ))}
    </ul>
  );
}

function ForecastCard({ fc, label }: { fc: PointForecast | null; label: string }) {
  if (!fc) return <div className="rounded-2xl bg-ink-50 p-4 text-sm text-ink-600">No HeatGuard heat forecast for {label} yet — it is published every evening at about 7 pm.</div>;
  const w = heatWords(fc.peak_c);
  return (
    <div className="rounded-2xl border border-ink-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2"><Tag kind="forecast" /><span className="text-sm text-ink-500">HeatGuard forecast for the afternoon peak</span></div>
      <div className="mt-2 flex flex-wrap items-baseline gap-3">
        <span className={clsx("rounded-full px-3 py-1 text-base font-semibold", w.cls)}>{w.word} afternoon</span>
        <span className="text-sm text-ink-600">heat-stress index about {fc.peak_c.toFixed(1)} °C · {Math.round(fc.prob_high * 100)}% chance of very hot (high heat stress)</span>
      </div>
      <p className="mt-2 text-xs text-ink-400">Made on {dayLabel(fc.made_on)} from stations near you ({fc.stations.map((s) => `${s.name} ${s.distance_km} km`).join(", ")}). Typical error about ±0.8 °C.</p>
    </div>
  );
}

export default function WeatherPage() {
  const [place, setPlace] = useState<Picked | null>(null);
  const [tab, setTab] = useState<"today" | "tomorrow">("today");
  const today = useSgtToday();
  const q = useQuery({ queryKey: ["weather", place?.latitude, place?.longitude, today], queryFn: () => features.weather(place!.latitude, place!.longitude),
    enabled: !!place, refetchInterval: 10 * 60_000 });
  const d = q.data;
  const nowHour = sgtNow().getHours();

  const todayHours = (() => {
    if (!d) return [];
    const obs = d.today.observed_by_hour?.by_hour ?? {};
    const est = d.today.forecast?.hourly ?? {};
    const out: { h: number; v: number; kind: "observed" | "estimate" }[] = [];
    for (let h = 7; h <= 19; h++) {
      if (h <= nowHour && obs[h] != null) out.push({ h, v: obs[h], kind: "observed" });
      else if (h > nowHour && est[h] != null) out.push({ h, v: est[h], kind: "estimate" });
    }
    return out;
  })();
  const tomorrowHours = d?.tomorrow.forecast ? Object.entries(d.tomorrow.forecast.hourly).map(([h, v]) => ({ h: +h, v, kind: "estimate" as const })).filter((x) => x.h >= 7 && x.h <= 19) : [];

  return (
    <>
      <PageHeader title="Weather & heat" subtitle="Today's conditions and tomorrow's outlook for a place in Singapore." />
      <section className="mb-5 rounded-3xl border border-ink-200 bg-white p-5 shadow-card"><LocationPicker value={place} onChange={setPlace} /></section>
      {!place ? <p className="text-sm text-ink-500">Choose a place to see the weather.</p> : q.isPending ? (
        <div className="space-y-4"><Skeleton className="h-40 rounded-3xl" /><Skeleton className="h-32 rounded-3xl" /></div>
      ) : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load the weather" /> : d && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Segmented value={tab} onChange={setTab} options={[{ value: "today", label: `Today · ${dayLabel(d.today.date)}` }, { value: "tomorrow", label: `Tomorrow · ${dayLabel(d.tomorrow.date)}` }]} />
            <Button size="sm" icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={() => q.refetch()} loading={q.isFetching}>Refresh</Button>
          </div>

          {tab === "today" ? (
            <>
              <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
                <div className="flex items-center gap-2"><h2 className="text-lg font-semibold text-ink-900">Right now</h2><Tag kind="observed" /></div>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  {[
                    { icon: Thermometer, label: "Heat stress", val: d.today.now.wbgt ? `${heatWords(d.today.now.wbgt.value_c).word} (${d.today.now.wbgt.value_c.toFixed(1)} °C WBGT)` : "Not available", r: d.today.now.wbgt },
                    { icon: CloudSun, label: "Air temperature", val: d.today.now.air_temp ? `${d.today.now.air_temp.value.toFixed(1)} °C` : "Not available", r: d.today.now.air_temp },
                    { icon: Droplets, label: "Humidity", val: d.today.now.humidity ? `${Math.round(d.today.now.humidity.value)}%` : "Not available", r: d.today.now.humidity },
                  ].map(({ icon: Icon, label, val, r }) => (
                    <div key={label} className="rounded-2xl bg-ink-50 p-4">
                      <div className="flex items-center gap-1.5 text-sm text-ink-500"><Icon className="h-4 w-4" />{label}</div>
                      <div className="mt-1 text-lg font-semibold text-ink-900">{val}</div>
                      {r && <div className="text-xs text-ink-400">{r.station} · {r.distance_km} km away · {sgtTime(r.time)}</div>}
                    </div>
                  ))}
                </div>
                {d.today.two_hour && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 rounded-2xl bg-violet-50 p-3.5 text-sm text-violet-950">
                    <Tag kind="forecast" /> Next 2 hours ({d.today.two_hour.valid_text}) in {d.today.two_hour.area}: <b>{d.today.two_hour.forecast}</b>
                  </div>
                )}
              </section>
              <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
                <h2 className="text-lg font-semibold text-ink-900">Heat through the day</h2>
                <p className="mb-3 mt-1 text-sm text-ink-500">Solid boxes were measured{d.today.observed_by_hour ? ` at ${d.today.observed_by_hour.station}` : ""}; dashed boxes are estimates (NEA does not publish hourly heat forecasts).</p>
                <HourStrip hours={todayHours} />
              </section>
              <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
                <div className="flex items-center gap-2"><h2 className="text-lg font-semibold text-ink-900">NEA forecast for today</h2><Tag kind="forecast" /></div>
                <Periods periods={d.today.nea_periods} />
              </section>
            </>
          ) : (
            <>
              <section className="space-y-3 rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
                <h2 className="text-lg font-semibold text-ink-900">Tomorrow's heat</h2>
                <ForecastCard fc={d.tomorrow.forecast} label="tomorrow" />
                <h3 className="pt-1 text-sm font-semibold text-ink-700">Hour by hour (estimate)</h3>
                <HourStrip hours={tomorrowHours} />
              </section>
              <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
                <div className="flex items-center gap-2"><h2 className="text-lg font-semibold text-ink-900">NEA forecast for tomorrow</h2><Tag kind="forecast" /></div>
                {d.nea_24h && <p className="mt-1 text-sm text-ink-600">{d.nea_24h.overall} · {d.nea_24h.temp_low_c}–{d.nea_24h.temp_high_c} °C ({d.nea_24h.valid_text})</p>}
                <Periods periods={d.tomorrow.nea_periods} />
              </section>
            </>
          )}

          {d.notes.length > 0 && <div className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900"><b>Some information is missing:</b><ul className="mt-1 list-disc pl-5">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul></div>}
          <p className="flex items-start gap-1.5 text-xs text-ink-400"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />Updated {sgtDateTime(d.fetched_at)}. Sources: {d.sources.join("; ")}. Measured values come from the NEA station nearest to you, which may be a few km away.</p>
        </div>
      )}
    </>
  );
}
