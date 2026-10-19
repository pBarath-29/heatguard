import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertOctagon, AlertTriangle, CheckCircle2, Clock, HelpCircle, Moon, Navigation, RefreshCw, ShieldAlert } from "lucide-react";
import { useState } from "react";
import LocationPicker, { type Picked } from "../components/LocationPicker";
import { Button, Field, inputClass, PageHeader, Segmented } from "../components/ui";
import { ApiError, features, type ActivityInput, type ActivityResult } from "../lib/api";
import { dayLabel } from "../lib/format";
import { heatWords, hourLabel, sgtDateTime } from "../lib/heat";

const STATUS: Record<ActivityResult["status"], { icon: typeof CheckCircle2; box: string; text: string; action: string }> = {
  "Lower risk": { icon: CheckCircle2, box: "border-emerald-300 bg-emerald-50", text: "text-emerald-800", action: "OK to go ahead with normal precautions." },
  Caution: { icon: AlertTriangle, box: "border-amber-300 bg-amber-50", text: "text-amber-800", action: "Go ahead only with changes — see below." },
  "High risk": { icon: AlertOctagon, box: "border-red-300 bg-red-50", text: "text-red-800", action: "Don't run it as planned — move indoors or reschedule." },
  "Insufficient data": { icon: HelpCircle, box: "border-ink-300 bg-ink-50", text: "text-ink-700", action: "We can't assess this reliably — check NEA's advisory before deciding." },
};

function Result({ r, onRetry }: { r: ActivityResult; onRetry: () => void }) {
  const s = STATUS[r.status];
  const Icon = s.icon;
  return (
    <div className="space-y-4" aria-live="polite">
      <section className={clsx("rounded-3xl border-2 p-6", s.box)}>
        <div className={clsx("flex items-center gap-3", s.text)}><Icon className="h-9 w-9" /><div>
          <div className="text-2xl font-semibold">{r.status}</div>
          <div className="text-[15px] font-medium">{s.action}</div></div></div>
        <p className="mt-3 text-sm text-ink-700">{r.activity}{r.place ? ` at ${r.place}` : ""} · {dayLabel(r.date, { long: true })} · {r.start}–{r.end} ({r.duration_min} min) · {r.exertion} effort{r.older_adults ? " · older adults" : ""}</p>
      </section>

      <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
        <h2 className="text-lg font-semibold text-ink-900">Why</h2>
        <ul className="mt-2 space-y-2">{r.reasons.map((t) => <li key={t} className="flex gap-2.5 text-[15px] text-ink-800"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-ink-400" />{t}</li>)}</ul>
        {r.forecast && (
          <div className="mt-4">
            <div className="mb-2 text-sm font-medium text-ink-700">Estimated heat during the day (activity hours outlined)</div>
            <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
              {Object.entries(r.forecast.hourly).map(([h, v]) => +h >= 7 && +h <= 19 && (
                <div key={h} className={clsx("w-16 shrink-0 rounded-xl border p-2 text-center", r.window?.hours.includes(+h) ? "border-2 border-ink-900" : "border-ink-200")}>
                  <div className="text-[11px] text-ink-500">{hourLabel(+h)}</div>
                  <div className={clsx("mt-1 rounded-full px-1 text-[11px] font-semibold", heatWords(v).cls)}>{heatWords(v).word}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-emerald-200 bg-emerald-50/60 p-5">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-emerald-950"><ShieldAlert className="h-5 w-5" /> What to do</h2>
        <ul className="mt-2 space-y-2">{r.precautions.map((t) => <li key={t} className="flex gap-2.5 text-[15px] text-emerald-950"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />{t}</li>)}</ul>
        {r.warm_nights && <p className="mt-3 flex gap-2 rounded-2xl bg-white/70 p-3 text-sm text-ink-800"><Moon className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />{r.warm_nights.text}</p>}
      </section>

      {(r.alternatives.length > 0 || r.shorter || r.indoor_options.length > 0) && (
        <section className="rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
          <h2 className="text-lg font-semibold text-ink-900">Safer options</h2>
          {r.alternatives.length > 0 && (
            <div className="mt-3 space-y-2">{r.alternatives.map((a) => (
              <div key={a.start} className="flex items-center justify-between gap-3 rounded-2xl bg-ink-50 p-3.5">
                <span className="flex items-center gap-2 font-medium text-ink-900"><Clock className="h-4 w-4 text-ink-500" />Move it to {a.start}–{a.end}</span>
                <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-semibold", a.status === "Lower risk" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800")}>{a.status}</span>
              </div>))}</div>
          )}
          {r.alternatives.length === 0 && r.status !== "Lower risk" && <p className="mt-2 text-sm text-ink-600">No lower-risk time of the same length was found today between 7 am and 7 pm.</p>}
          {r.shorter && <p className="mt-3 text-sm text-ink-700">Shortening it to {r.shorter.duration_min} minutes would make it <b>{r.shorter.status}</b>.</p>}
          {r.indoor_options.length > 0 && (
            <div className="mt-4"><div className="text-sm font-medium text-ink-700">Nearby indoor venues (air-conditioned; check opening hours and booking first)</div>
              <div className="mt-2 space-y-2">{r.indoor_options.map((v) => (
                <div key={v.name} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-ink-200 p-3">
                  <div><div className="font-medium text-ink-900">{v.name}</div><div className="text-xs text-ink-500">{v.type} · about {v.walk_min_estimate} min walk</div></div>
                  <a href={v.directions_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-brand-700"><Navigation className="h-4 w-4" />Directions</a>
                </div>))}</div></div>
          )}
        </section>
      )}

      <section className="rounded-2xl bg-ink-50 p-4 text-xs leading-relaxed text-ink-500">
        {r.forecast && <p>Forecast made {dayLabel(r.forecast.made_on)}{r.forecast.scored_at ? ` (${sgtDateTime(r.forecast.scored_at)})` : ""}, from {r.forecast.stations.map((x) => `${x.name} (${x.distance_km} km)`).join(", ")}. {r.uncertainty}</p>}
        {r.nea_periods.length > 0 && <p className="mt-1">NEA outlook for this time: {r.nea_periods.map((p) => `${p.label}: ${p.forecast}`).join("; ")}.</p>}
        {r.nea_note && <p className="mt-1">NEA forecast unavailable: {r.nea_note}</p>}
        <p className="mt-1">Sources: {r.sources.join("; ")}.</p>
        <p className="mt-1 font-medium text-ink-600">{r.disclaimer}</p>
        {r.status === "Insufficient data" && <Button size="sm" className="mt-2" icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={onRetry}>Try again</Button>}
      </section>
    </div>
  );
}

export default function ActivityPage() {
  const [place, setPlace] = useState<Picked | null>(null);
  const [form, setForm] = useState({ activity: "Taiji", exertion: "light" as ActivityInput["exertion"], day: "tomorrow" as ActivityInput["day"], start: "15:00", duration: 60, older: true });
  const m = useMutation({ mutationFn: () => features.activity({ activity: form.activity.trim(), exertion: form.exertion, latitude: place!.latitude, longitude: place!.longitude,
    place: place!.label.replace(/^My centre — /, ""), day: form.day, start: form.start, duration_min: form.duration, older_adults: form.older }) });
  const valid = !!place && form.activity.trim().length > 0 && form.duration >= 10 && form.duration <= 480 && /^\d{2}:\d{2}$/.test(form.start);

  return (
    <>
      <PageHeader title="Is our activity safe?" subtitle="Check a planned outdoor activity against the heat forecast, and get safer options." />
      <div className="mb-6 space-y-5 rounded-3xl border border-ink-200 bg-white p-5 shadow-card">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Activity"><input className={inputClass} value={form.activity} maxLength={80} onChange={(e) => setForm({ ...form, activity: e.target.value })} /></Field>
          <Field label="How strenuous?" group>
            <Segmented value={form.exertion} onChange={(v) => setForm({ ...form, exertion: v })} options={[{ value: "light", label: "Light" }, { value: "moderate", label: "Moderate" }, { value: "vigorous", label: "Vigorous" }]} />
            <p className="mt-1.5 text-xs text-ink-500">Light: taiji, stretching, slow walk · Moderate: brisk walk, line dancing · Vigorous: running, ball games</p>
          </Field>
          <Field label="Day" group><Segmented value={form.day} onChange={(v) => setForm({ ...form, day: v })} options={[{ value: "today", label: "Today" }, { value: "tomorrow", label: "Tomorrow" }]} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Start time"><input type="time" className={inputClass} value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></Field>
            <Field label="Length (minutes)"><input type="number" min={10} max={480} step={5} className={inputClass} value={form.duration} onChange={(e) => setForm({ ...form, duration: Number(e.target.value) })} /></Field>
          </div>
        </div>
        <label className="flex items-center gap-3 text-[15px] text-ink-800">
          <input type="checkbox" className="h-5 w-5 rounded border-ink-300 text-brand-600" checked={form.older} onChange={(e) => setForm({ ...form, older: e.target.checked })} />
          Participants are older adults
        </label>
        <Field label="Where?" group><LocationPicker value={place} onChange={setPlace} /></Field>
        {form.duration > 480 || form.duration < 10 ? <p className="text-sm text-red-700">Length must be between 10 and 480 minutes.</p> : null}
        <Button type="button" variant="primary" className="h-12 w-full text-base sm:w-auto" disabled={!valid} loading={m.isPending} onClick={() => m.mutate()}>Check the activity</Button>
        {!place && <p className="text-sm text-ink-500">Choose where the activity will be held.</p>}
      </div>
      {m.isError && <div className="mb-4 rounded-2xl bg-amber-50 p-4 text-sm text-amber-900" role="alert">{m.error instanceof ApiError ? m.error.message : "Couldn't check right now."} <button className="font-medium underline" onClick={() => m.mutate()}>Try again</button></div>}
      {m.data && <Result r={m.data} onRetry={() => m.mutate()} />}
    </>
  );
}
