import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { BookOpen, CalendarSearch, ExternalLink, FlaskConical, Target, ThermometerSun, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ReplayMap } from "../components/Maps";
import { Banner, Card, CardTitle, ErrorState, inputClass, PageHeader, PageSkeleton, Stat, TierBadge } from "../components/ui";
import { api } from "../lib/api";
import { dayLabel, deg, num, shortDate, title } from "../lib/format";
import { CHART } from "../lib/theme";

const FEATURED = ["2026-09-26", "2026-09-30", "2026-09-02", "2026-08-15"];

const EVIDENCE = [
  { stat: "87,000", text: "residents aged 65 and above were living alone in Singapore in 2024.", source: "Ministry of Health, reply in Parliament, 15 Oct 2025",
    url: "https://www.moh.gov.sg/newsroom/data-on-seniors-aged-65-and-above-living-alone-and-plans-for-new-initiatives-to-prevent-unattended-deaths/" },
  { stat: "37 days", text: "with high heat stress (WBGT ≥ 33 °C) in 2023. 2014–2023 was Singapore's warmest decade on record, 0.33 °C warmer than the decade before.",
    source: "National Environment Agency, Annual Climate Assessment 2023", url: "https://www.nea.gov.sg/media/news/news/index/2023-is-singapore-s-fourth-warmest-year-on-record" },
  { stat: "Prevention", text: "\"In the meantime, our priority is both prevention and early recognition\" — MOH on heat-related illness in the elderly, while its HEATMAP study runs to 2028.",
    source: "Ministry of Health, reply in Parliament, 6 Oct 2026", url: "https://www.moh.gov.sg/newsroom/using-findings-of-heat-map-study-to-help-elderly-recognise-common-symptoms-of-heat-related-illnesses-and-seek-timely-medical-advice/" },
];

export default function ProofPage() {
  const summary = useQuery({ queryKey: ["replay"], queryFn: api.replay });
  const [day, setDay] = useState<string>(FEATURED[0]);
  const detail = useQuery({ queryKey: ["replay", day], queryFn: () => api.replayDay(day), enabled: !!day });
  const days = summary.data?.days ?? [];
  useEffect(() => { if (days.length && !days.some((d) => d.target_date.slice(0, 10) === day)) setDay(days[days.length - 1].target_date.slice(0, 10)); }, [days, day]);
  const chart = useMemo(() => days.filter((d) => d.high_areas > 0).map((d) => ({ date: d.target_date.slice(0, 10), heatguard: d.start_here_hits, census: d.census_top10_hits })), [days]);

  if (summary.isPending) return <PageSkeleton rows={2} />;
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} title="Couldn't load the replay" />;
  const t = summary.data.totals;
  const ratio = t.census_top10_hits ? t.start_here_hits / t.census_top10_hits : null;
  const sel = days.find((d) => d.target_date.slice(0, 10) === day);
  const rows = detail.data?.rows ?? [];
  const top = rows.filter((r) => r.tier === "Start here");

  return (
    <>
      <PageHeader title="Would HeatGuard have helped?" subtitle="We replayed every day of the forecast's test period (Jul–Oct 2026), using only what was known the evening before, and checked where High heat actually struck." />
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Days High heat struck" value={`${t.days_with_high} of ${t.days}`} tone="text-red-600" icon={<ThermometerSun className="h-4 w-4" />}
            sub="at least one area's station reached High" hint="Afternoon peak WBGT of 33 °C or more at the area's nearest station." />
          <Stat label="HeatGuard top 10 hit High" value={num(t.start_here_hits)} tone="text-emerald-600" icon={<Target className="h-4 w-4" />} sub="area-days, across the test period" />
          <Stat label="Census-only top 10 hit High" value={num(t.census_top10_hits)} tone="text-ink-500" icon={<Users className="h-4 w-4" />} sub="same days, ranked by vulnerability alone" />
          <Stat label="Better targeting" value={ratio ? `${ratio.toFixed(1)}×` : "—"} tone="text-brand-700" icon={<FlaskConical className="h-4 w-4" />}
            sub="more hot areas reached first" hint="HeatGuard top-10 hits divided by Census-only top-10 hits." />
        </div>
        <Card className="bg-gradient-to-br from-emerald-50/80 to-white">
          <p className="text-[15px] leading-relaxed text-ink-800">
            <b>What this means:</b> High heat is not rare — it reached at least one area on {t.days_with_high} of {t.days} days in the hot season.
            No forecast can say exactly which street will hit 33 °C, but HeatGuard's daily top 10 landed on areas that really reached High heat{" "}
            <b>{ratio ? `${ratio.toFixed(1)} times` : ""} as often</b> as simply visiting the areas with the most vulnerable seniors. With limited staff and volunteers,
            that is the difference the forecast makes.
          </p>
        </Card>

        <Card>
          <CardTitle icon={<CalendarSearch className="h-4 w-4" />} title="Replay a day" subtitle="Pick a day to see the evening-before list next to what actually happened" />
          <div className="flex flex-wrap items-center gap-2">
            {FEATURED.filter((f) => days.some((d) => d.target_date.slice(0, 10) === f)).map((f) => (
              <button key={f} onClick={() => setDay(f)}
                className={clsx("rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition", day === f ? "border-brand-600 bg-brand-600 text-white" : "border-ink-200 bg-white text-ink-700 hover:border-brand-300")}>
                {dayLabel(f)}
              </button>
            ))}
            <select className={clsx(inputClass, "ml-auto w-auto")} value={day} onChange={(e) => setDay(e.target.value)} aria-label="Choose a day">
              {days.map((d) => <option key={d.target_date} value={d.target_date.slice(0, 10)}>{dayLabel(d.target_date, { year: true })} — {d.high_areas} areas hit High</option>)}
            </select>
          </div>
          {sel && (
            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl bg-emerald-50 px-4 py-3"><div className="text-[13px] text-emerald-800">HeatGuard's top 10 that hit High</div><div className="text-3xl font-semibold text-emerald-700">{sel.start_here_hits} <span className="text-lg text-emerald-600/70">/ {sel.start_here_areas}</span></div></div>
              <div className="rounded-2xl bg-violet-50 px-4 py-3"><div className="text-[13px] text-violet-800">Census-only top 10 that hit High</div><div className="text-3xl font-semibold text-violet-700">{sel.census_top10_hits} <span className="text-lg text-violet-600/70">/ 10</span></div></div>
              <div className="rounded-2xl bg-red-50 px-4 py-3"><div className="text-[13px] text-red-800">Areas that hit High that day</div><div className="text-3xl font-semibold text-red-700">{sel.high_areas} <span className="text-lg text-red-600/70">· hottest {deg(sel.hottest_actual_c)}</span></div></div>
            </div>
          )}
        </Card>

        {detail.isPending ? <PageSkeleton rows={1} /> : detail.isError ? <ErrorState error={detail.error} onRetry={() => detail.refetch()} /> : (
          <div className="grid gap-5 lg:grid-cols-5">
            <Card className="!p-3 lg:col-span-3">
              <div className="flex flex-wrap gap-x-4 gap-y-1 px-2 pb-3 pt-1 text-xs text-ink-600">
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border-[3px] border-brand-600" />HeatGuard top 10</span>
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border-[3px] border-violet-600" />Census-only top 10</span>
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-red-600" />Actually hit High</span>
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-ink-300" />Did not</span>
              </div>
              <ReplayMap rows={rows} />
            </Card>
            <Card className="lg:col-span-2">
              <CardTitle title={`HeatGuard's list the evening before ${dayLabel(day)}`} subtitle="Top 10 areas and what was then measured nearby" />
              <div className="divide-y divide-ink-100">
                {top.map((r) => (
                  <div key={r.subzone_name} className="flex items-center gap-3 py-2.5">
                    <span className="w-5 text-sm font-semibold text-ink-400">{r.rank}</span>
                    <div className="min-w-0 flex-1">
                      <Link to={`/area/${encodeURIComponent(r.subzone_name)}`} className="block truncate text-sm font-medium text-ink-900 hover:text-brand-700">{title(r.subzone_name)}</Link>
                      <div className="text-xs text-ink-500">{num(r.pop_65_plus)} seniors · forecast {deg(r.heat_wbgt_c)}</div>
                    </div>
                    <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-semibold", r.actually_high ? "bg-red-50 text-red-700" : "bg-ink-100 text-ink-500")}>
                      {r.actually_high ? `Hit High · ${deg(r.actual_peak_nearest_c)}` : deg(r.actual_peak_nearest_c)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-3"><TierBadge tier="Start here" /> <span className="ml-1 text-xs text-ink-500">uses exactly the same rules as today's list.</span></div>
            </Card>
          </div>
        )}

        <Card>
          <CardTitle title="Every hot day in the test period" subtitle="How many of each top 10 actually reached High heat" />
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={chart} margin={{ left: -16, right: 8, top: 8 }} onClick={(e) => e?.activeLabel && setDay(String(e.activeLabel))}>
                <CartesianGrid stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11, fill: CHART.axis }} minTickGap={20} />
                <YAxis allowDecimals={false} domain={[0, 10]} tick={{ fontSize: 12, fill: CHART.axis }} />
                <Tooltip labelFormatter={(d) => dayLabel(String(d), { year: true })} cursor={{ fill: "#F8FAFC" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="heatguard" name="HeatGuard top 10" fill={CHART.good} radius={[3, 3, 0, 0]} />
                <Bar dataKey="census" name="Census-only top 10" fill="#A78BFA" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs text-ink-400">Click a day to replay it. Days when no area reached High are left out.</p>
        </Card>

        <Card>
          <CardTitle icon={<BookOpen className="h-4 w-4" />} title="Why this matters" subtitle="Official sources" />
          <div className="grid gap-4 md:grid-cols-3">
            {EVIDENCE.map((e) => (
              <div key={e.stat} className="rounded-2xl border border-ink-100 bg-ink-50/60 p-4">
                <div className="text-2xl font-semibold tracking-tight text-brand-700">{e.stat}</div>
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink-700">{e.text}</p>
                <a href={e.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-ink-500 hover:text-brand-700">{e.source} <ExternalLink className="h-3 w-3" /></a>
              </div>
            ))}
          </div>
        </Card>
        <Banner tone="info" icon={<FlaskConical className="h-4 w-4" />}>
          How the replay works: forecasts come from the model trained only on data before July 2026, made the evening before each day. "Hit High" means the area's nearest
          station recorded an afternoon peak WBGT of 33 °C or more. Neighbouring areas often share a nearest station, so hits come in clusters (one hot station can make several
          areas count as hits) — this affects both lists equally. The Census-only list ranks the same areas by exposure (vulnerability and distance to a cool space) without any forecast.
        </Banner>
      </div>
    </>
  );
}
