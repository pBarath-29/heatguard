import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ArrowRight, Building2, Check, ChevronDown, Copy, CloudFog, MapPin, RefreshCw, RotateCcw, Send, Share2, Siren, Sun, ThermometerSun,
} from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import TelegramSend from "../components/TelegramSend";
import { Button, ErrorState, inputClass, Skeleton } from "../components/ui";
import { ApiError, api, features, type CheckinRow, type ComposeInput, type Lang, type NearResponse } from "../lib/api";
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
      <form onSubmit={(e) => { e.preventDefault(); if (ok) onSet(v); }} className="mt-8 rounded-3xl border border-ink-200 bg-surface p-5 shadow-card md:p-6">
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
export const TODO_DONE = "heatguard:todo-done";      // fired e.g. after a successful Telegram send

function Todo({ plan, postal }: { plan: NearResponse["plan"]; postal: string }) {
  const key = `heatguard.todo.${postal}.${plan.for_date}`;
  const [done, setDone] = useState<string[]>(() => { try { return JSON.parse(store.get(key) ?? "[]"); } catch { return []; } });
  useEffect(() => { store.set(key, JSON.stringify(done)); }, [key, done]);
  useEffect(() => {
    const on = (e: Event) => { const id = (e as CustomEvent<string>).detail; setDone((d) => (d.includes(id) ? d : [...d, id])); };
    window.addEventListener(TODO_DONE, on);
    return () => window.removeEventListener(TODO_DONE, on);
  }, []);
  const toggle = (id: string) => setDone((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));
  const count = plan.todo.filter((t) => done.includes(t.id)).length;
  const next = plan.todo.find((t) => !done.includes(t.id));
  const goToMessage = () => document.getElementById("message")?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <section className="rounded-3xl border border-ink-200 bg-surface p-5 shadow-card md:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-ink-900">Your to-do</h2>
        <span className={clsx("rounded-full px-3 py-1 text-sm font-medium", count === plan.todo.length ? "bg-emerald-50 text-emerald-700" : "bg-ink-100 text-ink-600")}>
          {count === plan.todo.length ? "All done" : `${count} of ${plan.todo.length} done`}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink-100" aria-hidden>
        <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${(count / plan.todo.length) * 100}%` }} />
      </div>
      <ol className="mt-4 space-y-2.5">
        {plan.todo.map((t) => {
          const on = done.includes(t.id), isNext = next?.id === t.id;
          return (
            <li key={t.id} className={clsx("rounded-2xl border transition", on ? "border-emerald-200 bg-emerald-50/50" : isNext ? "border-brand-300 bg-brand-50/40" : "border-ink-200")}>
              <div className="flex items-start gap-3 p-4">
                <button onClick={() => toggle(t.id)} aria-pressed={on} aria-label={on ? `Mark "${t.text}" as not done` : `Mark "${t.text}" as done`}
                  className={clsx("-m-1.5 mt-[-2px] flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition active:scale-95")}>
                  <span className={clsx("flex h-7 w-7 items-center justify-center rounded-lg border-2 transition", on ? "border-emerald-600 bg-emerald-600 text-white" : "border-ink-300 bg-surface")}>
                    {on && <Check className="h-4 w-4" strokeWidth={3} />}
                  </span>
                </button>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={clsx("text-[13px] font-semibold uppercase tracking-wide", on ? "text-ink-400" : "text-brand-700")}>{t.when}</span>
                    {isNext && <span className="rounded-full bg-brand-600 px-2 py-0.5 text-[11px] font-semibold text-white">Next</span>}
                  </div>
                  <p className={clsx("mt-0.5 text-[16px] leading-relaxed", on ? "text-ink-500 line-through decoration-ink-300" : "text-ink-900")}>{t.text}</p>
                  {t.why && !on && <p className="mt-1 text-sm text-ink-500">{t.why}</p>}
                  {t.action && !on && (t.action.to.startsWith("#") ? (
                    <button onClick={goToMessage} className="mt-2.5 inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink-100 px-3 text-sm font-medium text-ink-800 hover:bg-ink-200">
                      {t.action.label}<ArrowRight className="h-4 w-4" /></button>
                  ) : (
                    <Link to={t.action.to} className="mt-2.5 inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink-100 px-3 text-sm font-medium text-ink-800 hover:bg-ink-200">
                      {t.action.label}<ArrowRight className="h-4 w-4" /></Link>
                  ))}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      {plan.safety && (
        <p className="mt-4 flex items-start gap-2.5 rounded-2xl bg-red-50 p-3.5 text-sm font-medium text-red-900">
          <Siren className="mt-0.5 h-4 w-4 shrink-0" />{plan.safety}
        </p>
      )}
    </section>
  );
}

const LANGS: { code: Lang; label: string }[] = [{ code: "en", label: "English" }, { code: "zh", label: "中文" }, { code: "ms", label: "Melayu" }, { code: "ta", label: "தமிழ்" }];
const LANG_KEY = "heatguard.messageLanguage";

function MessageCard({ plan, centre, cool }: { plan: NearResponse["plan"]; centre: string; cool: string | null }) {
  const [lang, setLang] = useState<Lang>(() => (["en", "zh", "ms", "ta"].includes(store.get(LANG_KEY) ?? "") ? store.get(LANG_KEY) as Lang : "en"));
  const [text, setText] = useState("");
  const [edited, setEdited] = useState(false);
  const [copied, setCopied] = useState(false);
  const [sheet, setSheet] = useState(false);
  const input: ComposeInput = { level: plan.level, for_date: plan.for_date ?? "", language: lang, centre, cool, haze: !!plan.haze };
  const q = useQuery({ queryKey: ["compose", input], queryFn: () => features.compose(input), enabled: !!plan.for_date, staleTime: Infinity });
  const tg = useQuery({ queryKey: ["telegram"], queryFn: features.telegram, staleTime: 60_000, retry: false });
  useEffect(() => { if (q.data) { setText(q.data.text); setEdited(false); } }, [q.data]);
  useEffect(() => { store.set(LANG_KEY, lang); }, [lang]);
  const box = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {                                       // grow with the text so nothing is hidden on phones
    const el = box.current; if (!el) return;
    el.style.height = "auto"; el.style.height = `${el.scrollHeight + 2}px`;
  }, [text, q.isPending]);

  const copy = async () => { try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* text stays selectable */ } };
  const t = tg.data;
  const canSend = !!(t?.configured && t.bot && t.can_manage && t.chats.length > 0);
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(text)}`;
  const ready = !!text.trim() && !q.isPending;

  return (
    <section id="message" className="scroll-mt-20 rounded-3xl border border-ink-200 bg-surface p-5 shadow-card md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-ink-900">Message for your seniors</h2>
          <p className="mt-0.5 text-sm text-ink-500">Ready to send, in plain words and their language. You can edit it before sending.</p>
        </div>
      </div>
      <div className="mt-4 space-y-3">
        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 no-scrollbar" role="radiogroup" aria-label="Language">
          {LANGS.map(({ code, label }) => (
            <button key={code} role="radio" aria-checked={lang === code} onClick={() => setLang(code)} lang={code}
              className={clsx("h-10 shrink-0 rounded-full border px-4 text-[15px] font-medium transition", lang === code ? "border-ink-900 bg-ink-900 text-ink-50" : "border-ink-200 bg-surface text-ink-700 hover:border-ink-400")}>{label}</button>
          ))}
        </div>
      </div>
      <div className="mt-4">
        {q.isPending ? (
          <div className="space-y-2 rounded-2xl bg-ink-50 p-4" aria-label="Preparing your message"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-11/12" /><Skeleton className="h-4 w-4/5" /></div>
        ) : q.isError ? (
          <div className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900">{q.error instanceof ApiError ? q.error.message : "Couldn't prepare the message."} <button onClick={() => q.refetch()} className="font-medium underline">Try again</button></div>
        ) : (
          <>
            <label htmlFor="msg" className="sr-only">Message text</label>
            <textarea id="msg" lang={lang} value={text} onChange={(e) => { setText(e.target.value); setEdited(true); }} ref={box} rows={6}
              className="w-full resize-none overflow-hidden rounded-2xl border border-ink-200 bg-ink-50 p-4 text-[16px] leading-relaxed text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
            {edited && <button onClick={() => { setText(q.data!.text); setEdited(false); }} className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-brand-700"><RotateCcw className="h-3.5 w-3.5" />Undo my changes</button>}
          </>
        )}
      </div>
      <div className="mt-4 grid gap-2 sm:flex sm:flex-wrap">
        {canSend ? (
          <button type="button" disabled={!ready} onClick={() => setSheet(true)}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-telegram px-5 text-base font-semibold text-white shadow-sm transition hover:brightness-110 active:scale-[0.99] disabled:opacity-50">
            <Send className="h-5 w-5" /> Send to Telegram
          </button>
        ) : (
          <a href={ready ? shareUrl : undefined} target="_blank" rel="noreferrer" aria-disabled={!ready}
            className={clsx("inline-flex h-12 items-center justify-center gap-2 rounded-xl px-5 text-base font-semibold text-white shadow-sm transition", ready ? "bg-telegram hover:brightness-110" : "pointer-events-none bg-ink-300")}>
            <Send className="h-5 w-5" /> Share on Telegram
          </a>
        )}
        <div className="grid grid-cols-2 gap-2 sm:flex">
          {canSend && <a href={ready ? shareUrl : undefined} target="_blank" rel="noreferrer" className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-ink-200 bg-surface px-4 text-[15px] font-medium text-ink-700 hover:bg-ink-50"><Share2 className="h-5 w-5" />Share</a>}
          <Button className={clsx("h-12 px-4 text-[15px]", !canSend && "col-span-2")} disabled={!ready} onClick={copy} icon={copied ? <Check className="h-5 w-5" /> : <Copy className="h-5 w-5" />}>{copied ? "Copied" : "Copy"}</Button>
        </div>
      </div>
      <p className="mt-3 text-[13px] text-ink-500">
        {canSend ? <>Sends to {t!.chats.map((c) => c.title).join(", ")}. </> : null}
        {!canSend && t?.configured && t.bot && t.can_manage ? <>To send in one tap, <Link to="/settings" className="font-medium text-brand-700">link your Telegram group in Settings</Link>. </> : null}
        {!canSend && !(t?.configured && t.bot && t.can_manage) ? "Share opens Telegram with the message filled in — pick your centre's group or the people you want. " : null}
        Each language uses fixed, hand-written wording — nothing is machine-translated on the fly.
      </p>
      {sheet && t && <TelegramSend chats={t.chats} text={text} audience="seniors" language={lang} onSent={() => window.dispatchEvent(new CustomEvent(TODO_DONE, { detail: "send" }))} onClose={() => setSheet(false)} />}
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
      <MessageCard plan={plan} centre={title(place.name)} cool={cool?.name ?? null} />

      <section className="rounded-3xl border border-ink-200 bg-surface p-5 shadow-card md:p-6">
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
