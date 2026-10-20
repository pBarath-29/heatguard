import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, CheckCircle2, CloudFog, MapPin, Navigation, Snowflake, Sun, ThermometerSun, Users } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import SeniorMessage from "../components/SeniorMessage";
import { ErrorState, Skeleton } from "../components/ui";
import { ApiError, api } from "../lib/api";
import { dayLabel, num, pct, title } from "../lib/format";

const PRIORITY = {
  "Start here": { label: "Check first", cls: "bg-brand-600 text-white" },
  "Check in": { label: "Phone check-in", cls: "bg-amber-100 text-amber-800" },
  Routine: { label: "Routine check-ins", cls: "bg-ink-100 text-ink-700" },
} as const;

function walkMinutes(km: number) {
  return Math.max(1, Math.round(km * 15));
}

function centrePostal() { try { return localStorage.getItem("heatguard.centrePostal"); } catch { return null; } }

export default function AreaPage() {
  const { name = "" } = useParams();
  const postal = centrePostal();
  const centre = useQuery({ queryKey: ["near", postal], queryFn: () => api.near(postal!), enabled: !!postal, retry: false });   // cached from My plan: signs the message
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["area", name], queryFn: () => api.area(name), retry: (n, e) => !(e instanceof ApiError && e.status === 404) && n < 1 });
  const back = (e: React.MouseEvent) => { if (window.history.length > 1) { e.preventDefault(); navigate(-1); } };
  const backLink = <Link to="/" onClick={back} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"><ArrowLeft className="h-4 w-4" /> Back</Link>;

  if (q.isPending) return <div className="space-y-4">{backLink}<Skeleton className="h-40 rounded-3xl" /><Skeleton className="h-56 rounded-3xl" /></div>;
  if (q.isError) return <div>{backLink}<ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load this area" /></div>;
  const r = q.data.row;
  const veryHot = r.heat_band === "High" || r.high_alert;
  const hot = veryHot || r.heat_band === "Moderate";
  const heat = veryHot ? { icon: ThermometerSun, text: "Very hot afternoon possible", cls: "text-red-700 bg-red-50" }
    : hot ? { icon: Sun, text: "Hot afternoon", cls: "text-amber-800 bg-amber-50" } : { icon: Sun, text: "Normal afternoon", cls: "text-emerald-800 bg-emerald-50" };
  const HeatIcon = heat.icon;
  const priority = PRIORITY[r.tier] ?? PRIORITY.Routine;

  const reasons: string[] = [];
  if (veryHot) reasons.push("It may get very hot here in the afternoon.");
  else if (hot) reasons.push("The afternoon will be hot.");
  reasons.push(`${num(r.pop_65_plus)} residents are aged 65 or over — about ${pct(r.pct_65_plus)} of people living here.`);
  if ((r.pct_1_2_room ?? 0) >= 0.05) reasons.push(`${pct(r.pct_1_2_room)} of residents live in 1–2 room flats, which can get hot and are less likely to have air-conditioning.`);
  if (r.pa_data_published && r.pa_pct_one_person >= 0.15) reasons.push(`About ${pct(r.pa_pct_one_person)} of households in ${title(r.planning_area)} are people living alone.`);
  if (r.cool_space_km >= 1) reasons.push(`The nearest cool place is ${r.cool_space_km} km away — a long walk on a hot day.`);
  if (["Unhealthy", "Very unhealthy", "Hazardous"].includes(r.psi_band ?? "")) reasons.push(`The haze is ${r.psi_band?.toLowerCase()}.`);
  const cool = r.nearest_cool_space || "the nearest Community Club";
  const steps = veryHot   // same advice and hours as the seniors' message and My plan (very hot: 11 am – 4 pm; hot: 12 – 4 pm)
    ? ["Call or visit seniors who live alone before 11 am.", "Remind them to stay indoors from 11 am to 4 pm and to drink water often.", `If their home gets too hot, suggest ${cool}.`]
    : hot ? ["Phone seniors who live alone in the morning.", "Remind them to avoid going out from 12 pm to 4 pm and to drink water.", `If their home gets too hot, suggest ${cool}.`]
    : ["Routine check-ins. No extra heat steps needed."];
  if (["Unhealthy", "Very unhealthy", "Hazardous"].includes(r.psi_band ?? "")) steps.push("Check that seniors with heart or lung conditions have their medicine, and ask them to keep windows closed.");
  const address = [r.nearest_cool_space_street, r.nearest_cool_space_postal && `Singapore ${r.nearest_cool_space_postal}`].filter(Boolean).join(", ");
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${r.nearest_cool_space} Singapore ${r.nearest_cool_space_postal ?? ""}`)}`;

  return (
    <div className="space-y-5">
      {backLink}
      <section className="rounded-3xl border border-ink-200 bg-surface p-6 shadow-card">
        <div className="text-sm text-ink-500">{title(r.planning_area)} · {dayLabel(r.for_date, { long: true })}</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink-900">{title(r.subzone_name)}</h1>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className={clsx("rounded-full px-3 py-1 text-sm font-semibold", priority.cls)}>{priority.label}</span>
          <span className={clsx("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium", heat.cls)}><HeatIcon className="h-4 w-4" />{heat.text}</span>
          {["Unhealthy", "Very unhealthy", "Hazardous"].includes(r.psi_band ?? "") && <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-100 px-3 py-1 text-sm font-medium text-ink-700"><CloudFog className="h-4 w-4" />Haze: {r.psi_band?.toLowerCase()}</span>}
        </div>
      </section>

      <section className="rounded-3xl border border-ink-200 bg-surface p-6 shadow-card">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900"><Users className="h-5 w-5 text-ink-400" /> Why check here</h2>
        <ul className="mt-3 space-y-2.5">
          {reasons.map((t) => <li key={t} className="flex gap-3 text-[16px] leading-relaxed text-ink-800"><span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />{t}</li>)}
        </ul>
      </section>

      <section className="rounded-3xl border border-emerald-200 bg-emerald-50/60 p-6">
        <h2 className="text-lg font-semibold text-emerald-950">What to do</h2>
        <ul className="mt-3 space-y-2.5">
          {steps.map((t) => <li key={t} className="flex gap-3 text-[16px] leading-relaxed text-emerald-950"><CheckCircle2 className="mt-1 h-5 w-5 shrink-0 text-emerald-600" />{t}</li>)}
        </ul>
      </section>

      {(!postal || !centre.isPending) && (
        <SeniorMessage area={title(r.subzone_name)} level={veryHot ? "very_hot" : hot ? "hot" : "normal"} forDate={r.for_date}
          centre={centre.data ? title(centre.data.place.name) : ""} cool={r.nearest_cool_space} haze={["Unhealthy", "Very unhealthy", "Hazardous"].includes(r.psi_band ?? "")} />
      )}

      <section className="rounded-3xl border border-ink-200 bg-surface p-6 shadow-card">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900"><Snowflake className="h-5 w-5 text-sky-600" /> Nearest cool place</h2>
        <p className="mt-1 text-sm text-ink-500">Free and air-conditioned — suggest it to seniors whose homes get too hot.</p>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-sky-50 p-4">
          <div>
            <div className="text-[17px] font-semibold text-ink-900">{r.nearest_cool_space}</div>
            <div className="text-sm text-ink-600">{r.nearest_cool_space_type} · about {walkMinutes(r.cool_space_km)} min walk</div>
            {address && <div className="mt-1 flex items-center gap-1 text-sm text-ink-500"><MapPin className="h-4 w-4" />{address}</div>}
          </div>
          <a href={mapsUrl} target="_blank" rel="noreferrer" className="inline-flex h-11 items-center gap-2 rounded-xl bg-sky-600 px-4 text-sm font-semibold text-white hover:brightness-110"><Navigation className="h-4 w-4" /> Open in Maps</a>
        </div>
      </section>
    </div>
  );
}
