import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, ArrowRight, Building2, CheckCircle2, ExternalLink, MapPin, MessageSquareText, Search, Snowflake, Thermometer } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import MessageDialog from "../components/MessageDialog";
import { BandBadge, Button, Card, CardTitle, EmptyState, ErrorState, inputClass, PageHeader, PageSkeleton, PsiBadge, TierBadge } from "../components/ui";
import { api, type CheckinRow } from "../lib/api";
import { dayLabel, deg, num, pct, title } from "../lib/format";
import { BAND, TIER } from "../lib/theme";

const KEY = "heatguard.centrePostal";
const load = () => { try { return localStorage.getItem(KEY) ?? ""; } catch { return ""; } };
const save = (v: string) => { try { localStorage.setItem(KEY, v); } catch { /* storage unavailable: nothing to remember */ } };
const TIER_ORDER: Record<string, number> = { "Start here": 1, "Check in": 2, Routine: 3 };

export default function MyCentrePage() {
  const [input, setInput] = useState(load);
  const [postal, setPostal] = useState(load);
  const [messageRow, setMessageRow] = useState<CheckinRow | null>(null);
  const valid = /^\d{6}$/.test(input.trim());
  const q = useQuery({ queryKey: ["near", postal], queryFn: () => api.near(postal), enabled: /^\d{6}$/.test(postal), retry: false });

  const submit = (e: React.FormEvent) => { e.preventDefault(); if (!valid) return; const v = input.trim(); setPostal(v); save(v); };
  const areas = q.data ? [...q.data.areas].sort((a, b) => (TIER_ORDER[a.tier] - TIER_ORDER[b.tier]) || (b.risk_score - a.risk_score)) : [];
  const lead = areas[0];
  const point = q.data?.point;
  const band = point ? (point.heat_wbgt_c >= 33 ? "High" : point.heat_wbgt_c >= 31 ? "Moderate" : "Low") : null;

  return (
    <>
      <PageHeader title="My centre" subtitle="Enter your Active Ageing Centre's postal code to see tomorrow's heat where you are, the areas around you, and what to do." />
      <Card className="mb-5">
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1">
            <span className="mb-1.5 block text-[13px] font-medium text-ink-600">Centre postal code</span>
            <div className="relative">
              <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <input value={input} onChange={(e) => setInput(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" placeholder="e.g. 098917"
                className={clsx(inputClass, "pl-9 text-base tracking-wider")} aria-label="Centre postal code" />
            </div>
          </label>
          <Button type="submit" variant="primary" disabled={!valid} loading={q.isFetching} icon={<Search className="h-4 w-4" />}>Show my area</Button>
        </form>
        {input && !valid && <p className="mt-2 text-xs text-ink-500">Singapore postal codes have 6 digits.</p>}
        <p className="mt-3 text-xs text-ink-400">The location is looked up on OneMap (Singapore Land Authority). Your postal code is remembered on this device only.</p>
      </Card>

      {!postal ? (
        <EmptyState title="Enter your centre's postal code" body="HeatGuard will show tomorrow's heat at your centre, the nearby areas in priority order, and the closest cool spaces." />
      ) : q.isPending ? <PageSkeleton rows={2} /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't look up that postal code" /> : (
        <div className="space-y-5">
          <Card>
            <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="flex items-center gap-1.5 text-[13px] font-medium text-ink-500"><MapPin className="h-4 w-4" /> {q.data.place.address}</div>
                <h2 className="mt-1 text-2xl font-semibold tracking-tight text-ink-900">{title(q.data.place.name)}</h2>
                {point && <p className="mt-1 text-sm text-ink-500">Forecast for {dayLabel(point.target_date, { long: true })}, blended from {point.stations.map((s) => `${s.name} (${s.distance_km} km)`).join(", ")}.</p>}
              </div>
              {point && band && (
                <div className="flex items-center gap-4 rounded-2xl bg-ink-50 px-5 py-4">
                  <Thermometer className="h-8 w-8" style={{ color: BAND[band].hex }} />
                  <div>
                    <div className="text-3xl font-semibold" style={{ color: BAND[band].hex }}>{deg(point.heat_wbgt_c)}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2"><BandBadge band={band} /><span className="text-[13px] text-ink-600">{pct(point.prob_high)} chance of High</span></div>
                  </div>
                </div>
              )}
            </div>
            {point?.high_alert && (
              <div className="mt-4 flex items-start gap-2.5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-900">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" /> <span><b>High heat is possible around your centre.</b> Plan as for a High day: call or visit the most vulnerable seniors before 11 am.</span>
              </div>
            )}
            {lead && (
              <div className="mt-4 flex gap-2.5 rounded-xl border border-emerald-100 bg-emerald-50/70 px-4 py-3.5">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                <div className="text-[15px] leading-relaxed text-emerald-950">
                  <span className="font-semibold">What to do ({title(lead.subzone_name)}, {lead.tier.toLowerCase()}): </span>{lead.action}
                  <div className="mt-2"><Button size="sm" icon={<MessageSquareText className="h-3.5 w-3.5" />} onClick={() => setMessageRow(lead)}>Write a message for your seniors</Button></div>
                </div>
              </div>
            )}
          </Card>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card padded={false} className="overflow-hidden lg:col-span-2">
              <div className="px-5 pt-5"><CardTitle title="Areas around your centre" subtitle="Within 1.5 km, highest priority first" /></div>
              {areas.length === 0 ? <p className="px-5 pb-5 text-sm text-ink-500">No areas with 50 or more seniors are close by.</p> : (
                <div className="divide-y divide-ink-100">
                  {areas.map((a) => (
                    <div key={a.subzone_name} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link to={`/area/${encodeURIComponent(a.subzone_name)}`} className="font-semibold text-ink-900 hover:text-brand-700">{title(a.subzone_name)}</Link>
                          <TierBadge tier={a.tier} /><BandBadge band={a.heat_band} prefix="Heat: " /><PsiBadge band={a.psi_band} />
                        </div>
                        <div className="mt-0.5 text-[13px] text-ink-500">{a.distance_km} km away · {num(a.pop_65_plus)} aged 65+ ({pct(a.pct_65_plus)}) · #{a.rank} in Singapore</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold tabular-nums" style={{ color: TIER[a.tier]?.hex }}>{Math.round(a.risk_score)}</span>
                        <button onClick={() => setMessageRow(a)} className="rounded-lg p-2 text-ink-400 hover:bg-ink-100 hover:text-ink-700" title="Write a message"><MessageSquareText className="h-4 w-4" /></button>
                        <Link to={`/area/${encodeURIComponent(a.subzone_name)}`} className="rounded-lg p-2 text-brand-700 hover:bg-brand-50" title="Why here"><ArrowRight className="h-4 w-4" /></Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
            <Card>
              <CardTitle icon={<Snowflake className="h-4 w-4" />} title="Nearest cool spaces" subtitle="Free and air-conditioned" />
              <div className="space-y-3">
                {q.data.cool_spaces.map((c) => (
                  <div key={c.name} className="rounded-xl border border-ink-100 px-3.5 py-3">
                    <div className="font-medium text-ink-900">{c.name}</div>
                    <div className="text-[13px] text-ink-500">{c.space_type} · {c.distance_km} km</div>
                    <a className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:text-brand-800" target="_blank" rel="noreferrer"
                      href={`https://www.google.com/maps/dir/?api=1&origin=${q.data.place.latitude},${q.data.place.longitude}&destination=${c.latitude},${c.longitude}&travelmode=walking`}>
                      Walking directions <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
      {messageRow && <MessageDialog row={messageRow} onClose={() => setMessageRow(null)} />}
    </>
  );
}
