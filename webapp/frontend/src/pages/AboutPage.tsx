import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Database, Eraser, ListOrdered, Lock, Scale, ShieldAlert, TriangleAlert } from "lucide-react";
import { Card, CardTitle, ErrorState, PageHeader, PageSkeleton } from "../components/ui";
import { api } from "../lib/api";
import { pct } from "../lib/format";

const STEPS = [
  { icon: Database, title: "Collect", body: "NEA heat-stress (WBGT) from ~30 stations every 15 minutes, NEA forecasts and haze for 5 regions, plus Census 2020, the URA subzone map, Community Clubs and libraries." },
  { icon: Eraser, title: "Clean", body: "A Databricks pipeline removes faulty sensor readings, duplicates and gaps, and counts every row it drops." },
  { icon: BrainCircuit, title: "Forecast", body: "A machine-learning model, tested on months it never saw, forecasts tomorrow afternoon's peak heat at each station and the chance it reaches High." },
  { icon: ListOrdered, title: "Rank", body: "Each area with seniors gets a risk score from heat, haze, vulnerable seniors and distance to a cool space. Actions come from a fixed rulebook." },
];
const NAMES: Record<string, string> = {
  heat: "Heat", haze: "Haze", vulnerability: "Vulnerable seniors", access: "Distance to a cool space",
  pct_65_plus: "Share aged 65+", pop_65_plus: "Number aged 65+", pct_1_2_room: "Share in 1–2 room flats",
  pa_pct_one_person: "One-person households", pa_pct_difficulty: "Daily-activity difficulty",
};
const GLOSSARY = [
  ["WBGT", "Wet Bulb Globe Temperature (°C): NEA's heat-stress measure. It combines air temperature, humidity, sunshine and wind — how hot it feels to the body."],
  ["Heat-stress level", "NEA bands: Low (below 31°C), Moderate (31–32.9°C), High (33°C and above)."],
  ["Afternoon peak", "The highest WBGT between 12 pm and 6 pm — the most dangerous time for seniors outdoors."],
  ["High-heat alert", "HeatGuard's model sees a meaningful chance of High heat tomorrow, even if the typical forecast is Moderate. Plan as for a High day."],
  ["PSI", "Pollutant Standards Index (24-hour), NEA's haze measure. Good ≤ 50, Moderate 51–100, Unhealthy 101–200, Very unhealthy 201–300, Hazardous above 300."],
  ["Subzone / planning area", "URA's map units. A planning area (e.g. Bukit Merah) contains several subzones (e.g. Telok Blangah Rise)."],
  ["Cool space", "A free, air-conditioned public place seniors can go to: Community Clubs and public libraries."],
];

export default function AboutPage() {
  const q = useQuery({ queryKey: ["about"], queryFn: api.about });
  return (
    <>
      <PageHeader title="About HeatGuard" subtitle="How the check-in list is made, what the numbers mean, and the data behind it." />
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ icon: Icon, title, body }, i) => (
            <Card key={title}>
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-700"><Icon className="h-5 w-5" /></span>
                <span className="text-xs font-semibold uppercase tracking-wider text-ink-400">Step {i + 1}</span>
              </div>
              <h3 className="mt-3 text-[15px] font-semibold text-ink-900">{title}</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-500">{body}</p>
            </Card>
          ))}
        </div>
        <p className="text-[13px] text-ink-500">Updated every evening at about 7 pm (Singapore time), so the list is ready before coordinators plan the next day.</p>

        {q.isPending ? <PageSkeleton rows={1} /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load the score weights" /> : (
          <>
            <div className="grid gap-5 lg:grid-cols-2">
              {[["risk_score", "Risk score (0–100)", "How each area is ranked"], ["vulnerability_score", "Vulnerability", "Part of the risk score: compared with all areas that have at least 50 seniors"]].map(([key, t, sub]) => (
                <Card key={key}>
                  <CardTitle icon={<Scale className="h-4 w-4" />} title={t} subtitle={sub} />
                  <div className="space-y-3">
                    {q.data.weights.filter((w) => w.score === key).map((w) => (
                      <div key={w.component}>
                        <div className="flex items-baseline justify-between gap-3"><span className="text-sm font-medium text-ink-900">{NAMES[w.component] ?? w.component}</span><span className="text-sm font-semibold tabular-nums text-brand-700">{pct(w.weight)}</span></div>
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${w.weight * 100 / 0.35}%` }} /></div>
                        <p className="mt-1 text-[13px] text-ink-500">{w.description}</p>
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
            <Card>
              <CardTitle icon={<ShieldAlert className="h-4 w-4" />} title="What to do at each level (rulebook)" subtitle="Actions are set by people, not chosen by AI. The writing assistant only rewords and translates them." />
              <div className="divide-y divide-ink-100">
                {q.data.rulebook.map((r) => (
                  <div key={`${r.trigger}-${r.level}`} className="grid gap-2 py-3 md:grid-cols-[200px_1fr]">
                    <span className="text-sm font-medium text-ink-900">{r.trigger === "heat" ? "Heat" : "Haze"}: {r.level}</span>
                    <span className="text-sm leading-relaxed text-ink-600">{r.action}</span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs text-ink-400">Draft wording, to be checked against NEA's heat-stress and haze advisories and by an Active Ageing Centre coordinator.</p>
            </Card>
          </>
        )}

        <Card>
          <CardTitle title="Glossary" />
          <dl className="grid gap-x-8 gap-y-4 md:grid-cols-2">
            {GLOSSARY.map(([t, d]) => <div key={t}><dt className="text-sm font-semibold text-ink-900">{t}</dt><dd className="mt-0.5 text-[13px] leading-relaxed text-ink-500">{d}</dd></div>)}
          </dl>
        </Card>

        <div className="grid gap-5 lg:grid-cols-3">
          <Card>
            <CardTitle icon={<TriangleAlert className="h-4 w-4" />} title="Limitations" />
            <ul className="space-y-2 text-[13px] leading-relaxed text-ink-600 [&_li]:ml-4 [&_li]:list-disc">
              <li>Heat is measured at ~30 stations; each area blends its nearest three, so very local hot spots can be missed.</li>
              <li>Census data is from 2020. Living-alone and daily-activity figures exist only for the 30 largest planning areas; elsewhere the national rate is used.</li>
              <li>Distances to cool spaces are straight-line, not walking routes.</li>
              <li>There is no official haze forecast, so the latest haze reading is carried forward.</li>
            </ul>
          </Card>
          <Card>
            <CardTitle icon={<Lock className="h-4 w-4" />} title="Privacy" />
            <p className="text-[13px] leading-relaxed text-ink-600">HeatGuard uses <b>area-level open data only</b> — no names, addresses or personal records. It tells coordinators <i>where and when</i> to act; their own client lists tell them <i>who</i>.</p>
          </Card>
          <Card>
            <CardTitle icon={<Database className="h-4 w-4" />} title="Data sources" />
            <ul className="space-y-1.5 text-[13px] leading-relaxed text-ink-600">
              <li><b>NEA</b> via data.gov.sg: WBGT, forecasts, PSI, PM2.5</li>
              <li><b>SingStat</b>: Census of Population 2020</li>
              <li><b>URA</b>: Master Plan 2019 subzones</li>
              <li><b>People's Association</b>: Community Clubs · <b>NLB</b>: libraries</li>
            </ul>
            <p className="mt-3 text-xs text-ink-400">Singapore Open Data Licence. Built on Databricks: Lakeflow, Unity Catalog, MLflow, Genie, Foundation Model APIs, Apps.</p>
          </Card>
        </div>
      </div>
    </>
  );
}
