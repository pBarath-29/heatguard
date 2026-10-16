import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ArrowRight, Building2, Check, ChevronDown, Copy, CloudFog, MapPin, Navigation, RefreshCw, Send, Snowflake, Sun, ThermometerSun,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button, ErrorState, inputClass, Segmented, Skeleton } from "../components/ui";
import { ApiError, api, type CheckinRow, type NearResponse } from "../lib/api";
import { dayLabel, num, pct, title } from "../lib/format";

// ---------- remembered on this device only ----------
const CENTRE_KEY = "heatguard.centrePostal";
const store = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* private mode: nothing to remember */ } },
  del: (k: string) => { try { localStorage.removeItem(k); } catch { /* ignore */ } },
};

const LEVEL = {
  very_hot: { bg: "bg-gradient-to-br from-red-600 to-brand-600", icon: ThermometerSun, chip: "Take extra care" },
  hot: { bg: "bg-gradient-to-br from-brand-600 to-amber-500", icon: Sun, chip: "Take care" },
  normal: { bg: "bg-gradient-to-br from-emerald-600 to-teal-500", icon: Sun, chip: "Routine day" },
};
const LANGS = [["English", "English"], ["中文 (Chinese)", "中文"], ["Bahasa Melayu", "Melayu"], ["தமிழ் (Tamil)", "தமிழ்"]] as const;

function walkMinutes(km: number) {
  return Math.max(1, Math.round(km * 15));   // a gentle walking pace for seniors (~4 km/h)
}

function plainReasons(a: CheckinRow & { distance_km: number }) {
  const out: string[] = [];
  if (a.high_alert || a.heat_band === "High") out.push("may get very hot");
  if (a.pct_65_plus >= 0.2) out.push(`many older residents (${pct(a.pct_65_plus)} aged 65+)`);
  if ((a.pct_1_2_room ?? 0) >= 0.1) out.push("many small rental flats");
  if (a.cool_space_km >= 1) out.push(`${a.cool_space_km} km from a cool place`);
  if (!out.length) out.push(`${num(a.pop_65_plus)} seniors live here`);
  return out.slice(0, 2).join(" · ");
}

// ---------- first visit: which centre? ----------
function Welcome({ onSet }: { onSet: (postal: string) => void }) {
  const [v, setV] = useState("");
  const ok = /^\d{6}$/.test(v);
  return (
    <div className="mx-auto max-w-xl py-6 md:py-14">
      <img src="/favicon.svg" alt="" className="h-14 w-14 rounded-2xl shadow-lift" />
      <h1 className="mt-6 text-3xl font-semibold tracking-tight text-ink-900 md:text-4xl">Plan tomorrow's heat check-ins in one minute</h1>
      <p className="mt-3 text-lg leading-relaxed text-ink-600">HeatGuard tells you, every evening, how hot tomorrow afternoon will be around your centre, what to do, and gives you a message ready to send to your seniors.</p>
      <form onSubmit={(e) => { e.preventDefault(); if (ok) onSet(v); }} className="mt-8 rounded-3xl border border-ink-200 bg-white p-5 shadow-card md:p-6">
        <label className="block text-[15px] font-medium text-ink-800" htmlFor="postal">Your centre's postal code</label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Building2 className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-400" />
            <input id="postal" value={v} onChange={(e) => setV(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoFocus
              placeholder="6 digits, e.g. 098917" className={clsx(inputClass, "h-12 pl-11 text-lg tracking-wider")} />
          </div>
          <Button type="submit" variant="primary" disabled={!ok} className="h-12 px-6 text-base">Show my plan</Button>
        </div>
        <button type="button" onClick={() => onSet("098917")} className="mt-3 text-sm font-medium text-brand-700 hover:text-brand-800">Just looking? Try an example centre (Radin Mas CC)</button>
        <p className="mt-4 text-xs text-ink-400">Remembered on this device only. HeatGuard uses area-level open data — no personal information.</p>
      </form>
    </div>
  );
}

// ---------- the plan ----------
function Todo({ plan, postal }: { plan: NearResponse["plan"]; postal: string }) {
  const key = `heatguard.todo.${postal}.${plan.for_date}`;
  const [done, setDone] = useState<string[]>(() => { try { return JSON.parse(store.get(key) ?? "[]"); } catch { return []; } });
  useEffect(() => { store.set(key, JSON.stringify(done)); }, [key, done]);
  const toggle = (id: string) => setDone((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));
  const count = plan.todo.filter((t) => done.includes(t.id)).length;
  return (
    <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink-900">Your to-do</h2>
        <span className={clsx("rounded-full px-3 py-1 text-sm font-medium", count === plan.todo.length ? "bg-emerald-50 text-emerald-700" : "bg-ink-100 text-ink-600")}>
          {count === plan.todo.length ? "All done" : `${count} of ${plan.todo.length} done`}
        </span>
      </div>
      <ul className="mt-4 space-y-2.5">
        {plan.todo.map((t) => {
          const on = done.includes(t.id);
          return (
            <li key={t.id}>
              <button onClick={() => toggle(t.id)} aria-pressed={on}
                className={clsx("flex w-full items-start gap-4 rounded-2xl border p-4 text-left transition", on ? "border-emerald-200 bg-emerald-50/60" : "border-ink-200 hover:border-brand-300 hover:bg-brand-50/30")}>
                <span className={clsx("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border-2 transition", on ? "border-emerald-600 bg-emerald-600 text-white" : "border-ink-300 bg-white")}>
                  {on && <Check className="h-4 w-4" strokeWidth={3} />}
                </span>
                <span>
                  <span className="block text-[13px] font-semibold uppercase tracking-wide text-brand-700">{t.when}</span>
                  <span className={clsx("mt-0.5 block text-[16px] leading-relaxed", on ? "text-ink-500 line-through decoration-ink-300" : "text-ink-900")}>{t.text}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function MessageCard({ area, centre }: { area: string | null; centre: string }) {
  const [lang, setLang] = useState<string>("English");
  const [audience, setAudience] = useState("seniors");
  const [copied, setCopied] = useState(false);
  const q = useQuery({ queryKey: ["msg", area, lang, audience, centre], queryFn: () => api.message(area!, lang, audience, centre), enabled: !!area, staleTime: Infinity, retry: 1 });
  const copy = async () => { if (!q.data) return; try { await navigator.clipboard.writeText(q.data.text); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* text is still selectable */ } };
  if (!area) return null;
  return (
    <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card md:p-6">
      <h2 className="text-lg font-semibold text-ink-900">Message ready to send</h2>
      <p className="mt-1 text-sm text-ink-500">Uses only HeatGuard's safety steps, written warmly and translated for you.</p>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Segmented value={audience} onChange={setAudience} options={[{ value: "seniors", label: "For seniors" }, { value: "staff", label: "For staff & volunteers" }]} />
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Language">
          {LANGS.map(([value, label]) => (
            <button key={value} role="radio" aria-checked={lang === value} onClick={() => setLang(value)}
              className={clsx("rounded-full border px-3.5 py-1.5 text-sm font-medium transition", lang === value ? "border-ink-900 bg-ink-900 text-white" : "border-ink-200 bg-white text-ink-700 hover:border-ink-400")}>{label}</button>
          ))}
        </div>
      </div>
      <div className="mt-4 rounded-2xl bg-ink-50 p-4">
        {q.isPending ? (
          <div className="space-y-2" aria-label="Preparing your message"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-11/12" /><Skeleton className="h-4 w-4/5" /><p className="pt-1 text-xs text-ink-400">Preparing your message…</p></div>
        ) : q.isError ? (
          <div className="text-sm text-amber-800">{q.error instanceof ApiError ? q.error.message : "Couldn't prepare the message."} <button onClick={() => q.refetch()} className="font-medium underline">Try again</button></div>
        ) : (
          <>
            {!q.data.used_ai && <p className="mb-2 text-xs text-ink-500">The writing assistant is busy, so this is the plain version.</p>}
            <p className="whitespace-pre-wrap text-[16px] leading-relaxed text-ink-900">{q.data.text}</p>
          </>
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <a href={q.data ? `https://wa.me/?text=${encodeURIComponent(q.data.text)}` : undefined} target="_blank" rel="noreferrer"
          aria-disabled={!q.data} className={clsx("inline-flex h-12 items-center gap-2 rounded-xl px-5 text-base font-semibold text-white shadow-sm transition", q.data ? "bg-[#25D366] hover:bg-[#1EB956]" : "pointer-events-none bg-ink-300")}>
          <Send className="h-5 w-5" /> Send on WhatsApp
        </a>
        <Button className="h-12 px-5 text-base" disabled={!q.data} onClick={copy} icon={copied ? <Check className="h-5 w-5" /> : <Copy className="h-5 w-5" />}>{copied ? "Copied" : "Copy"}</Button>
      </div>
    </section>
  );
}

function Plan({ data, postal, onChange }: { data: NearResponse; postal: string; onChange: () => void }) {
  const [details, setDetails] = useState(false);
  const [allAreas, setAllAreas] = useState(false);
  const { plan, point, place } = data;
  const L = LEVEL[plan.level];
  const Icon = L.icon;
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Singapore" });
  const when = plan.for_date === today ? "Today" : "Tomorrow";
  const areas = useMemo(() => {
    const order: Record<string, number> = { "Start here": 1, "Check in": 2, Routine: 3 };
    return [...data.areas].sort((a, b) => order[a.tier] - order[b.tier] || b.risk_score - a.risk_score);
  }, [data.areas]);
  const cool = data.cool_spaces[0];

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[15px] text-ink-600"><Building2 className="h-5 w-5 text-ink-400" /><span className="font-semibold text-ink-900">{title(place.name)}</span></div>
        <button onClick={onChange} className="text-sm font-medium text-brand-700 hover:text-brand-800">Change centre</button>
      </div>

      <section className={clsx("relative overflow-hidden rounded-3xl p-6 text-white shadow-lift md:p-8", L.bg)}>
        <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
        <div className="relative">
          <div className="text-[15px] font-medium text-white/85">{when} · {dayLabel(plan.for_date, { long: true })}</div>
          <div className="mt-3 flex items-start gap-4">
            <Icon className="mt-1 h-12 w-12 shrink-0" strokeWidth={1.75} />
            <div>
              <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{plan.title}</h1>
              <p className="mt-2 text-lg leading-relaxed text-white/90">{plan.subtitle}</p>
            </div>
          </div>
          {plan.haze && <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-white/15 px-4 py-2 text-[15px]"><CloudFog className="h-5 w-5" />{plan.haze.text}</div>}
          <button onClick={() => setDetails(!details)} className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-white/85 hover:text-white">
            {details ? "Hide" : "How sure is this?"} <ChevronDown className={clsx("h-4 w-4 transition", details && "rotate-180")} />
          </button>
          {details && point && (
            <div className="mt-3 space-y-2 rounded-2xl bg-black/15 p-4 text-[15px] text-white/95">
              <p><b>How sure is this?</b> The chance of a very hot afternoon near your centre is about {pct(point.prob_high)}{point.prob_high >= 0.1 ? ` (around 1 in ${Math.max(2, Math.round(1 / point.prob_high))})` : ""}.</p>
              <p>Based on NEA's weather stations nearest your centre ({point.stations[0]?.name}, {point.stations[0]?.distance_km} km away) and NEA's forecast.</p>
              <p className="text-sm text-white/75">HeatGuard gives an early warning so you can plan; on the day, always follow NEA's latest advisories.</p>
            </div>
          )}
        </div>
      </section>

      <Todo plan={plan} postal={postal} />
      <MessageCard area={plan.message_area} centre={title(place.name)} />

      <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card md:p-6">
        <h2 className="text-lg font-semibold text-ink-900">Areas near you to check first</h2>
        <p className="mt-1 text-sm text-ink-500">Within 1.5 km of your centre, most at risk first.</p>
        <div className="mt-3 divide-y divide-ink-100">
          {(allAreas ? areas : areas.slice(0, 3)).map((a, i) => (
            <Link key={a.subzone_name} to={`/area/${encodeURIComponent(a.subzone_name)}`} className="group flex items-center gap-4 py-3.5">
              <span className={clsx("flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold", i < 2 && a.tier !== "Routine" ? "bg-brand-600 text-white" : "bg-ink-100 text-ink-600")}>{i + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[16px] font-semibold text-ink-900 group-hover:text-brand-700">{title(a.subzone_name)}</span>
                <span className="block text-sm text-ink-500">{plainReasons(a)}</span>
                <span className="block text-xs text-ink-400">{num(a.pop_65_plus)} seniors · {a.distance_km} km from your centre</span>
              </span>
              <ArrowRight className="h-5 w-5 shrink-0 text-ink-300 group-hover:text-brand-600" />
            </Link>
          ))}
        </div>
        {areas.length > 3 && (
          <button onClick={() => setAllAreas(!allAreas)} className="mt-2 text-sm font-medium text-brand-700 hover:text-brand-800">{allAreas ? "Show fewer" : `Show all ${areas.length} nearby areas`}</button>
        )}
      </section>

      {cool && (
        <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card md:p-6">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900"><Snowflake className="h-5 w-5 text-sky-600" /> Nearest cool place</h2>
          <p className="mt-1 text-sm text-ink-500">Free and air-conditioned — suggest it to seniors whose homes get too hot.</p>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-sky-50 p-4">
            <div>
              <div className="text-[17px] font-semibold text-ink-900">{cool.name}</div>
              <div className="text-sm text-ink-600">{cool.space_type} · about {walkMinutes(cool.distance_km)} min walk ({cool.distance_km} km)</div>
            </div>
            <a target="_blank" rel="noreferrer" href={`https://www.google.com/maps/dir/?api=1&origin=${place.latitude},${place.longitude}&destination=${cool.latitude},${cool.longitude}&travelmode=walking`}
              className="inline-flex h-11 items-center gap-2 rounded-xl bg-sky-600 px-4 text-sm font-semibold text-white hover:bg-sky-700"><Navigation className="h-4 w-4" /> Directions</a>
          </div>
          {data.cool_spaces.length > 1 && (
            <p className="mt-3 text-sm text-ink-500">Also nearby: {data.cool_spaces.slice(1).map((c) => `${c.name} (${walkMinutes(c.distance_km)} min)`).join(", ")}.</p>
          )}
        </section>
      )}

      <div className="flex items-center gap-1.5 px-1 pb-2 text-sm text-ink-500"><MapPin className="h-4 w-4 shrink-0" /> {title(place.address)}</div>
    </div>
  );
}

export default function HomePage() {
  const [postal, setPostal] = useState<string | null>(() => store.get(CENTRE_KEY));
  const q = useQuery({ queryKey: ["near", postal], queryFn: () => api.near(postal!), enabled: !!postal, retry: false });
  const set = (p: string) => { store.set(CENTRE_KEY, p); setPostal(p); };
  const change = () => { store.del(CENTRE_KEY); setPostal(null); };

  if (!postal) return <Welcome onSet={set} />;
  if (q.isPending) return (
    <div className="mx-auto max-w-3xl space-y-5" aria-busy="true">
      <Skeleton className="h-6 w-56" /><Skeleton className="h-56 rounded-3xl" /><Skeleton className="h-64 rounded-3xl" /><Skeleton className="h-48 rounded-3xl" />
      <p className="text-center text-sm text-ink-400">Getting tomorrow's plan for your centre… the first load of the day can take up to 30 seconds.</p>
    </div>
  );
  if (q.isError) return (
    <div className="mx-auto max-w-xl space-y-4 py-6">
      <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load your plan" />
      <div className="text-center"><Button icon={<RefreshCw className="h-4 w-4" />} onClick={change}>Use a different postal code</Button></div>
    </div>
  );
  return <Plan data={q.data} postal={postal} onChange={change} />;
}
