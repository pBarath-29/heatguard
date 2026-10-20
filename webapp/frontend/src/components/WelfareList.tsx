import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Flag, History, Loader2, Lock, MessageSquarePlus, PhoneOff, Search, Undo2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button, EmptyState, ErrorState, Segmented, Skeleton, inputClass } from "./ui";
import { ApiError, features, type Resident, type WelfareEvent } from "../lib/api";
import { title } from "../lib/format";
import { sgtDateTime } from "../lib/heat";

type Filter = "all" | "todo" | "follow_up" | "done";
type Draft = { remark: string; outcome: string };

const OUTCOME_LABEL: Record<string, string> = {
  reached: "Reached", no_response: "No response", unavailable: "Not available", unreachable: "Couldn't reach / wrong number", referred: "Referred for help",
};
const STATUS_STYLE: Record<Resident["state"]["status"], { label: string; cls: string }> = {
  pending: { label: "To do", cls: "bg-ink-100 text-ink-700" },
  completed: { label: "Done", cls: "bg-emerald-100 text-emerald-800" },
  follow_up: { label: "Follow up", cls: "bg-amber-100 text-amber-800" },
  unsuccessful: { label: "Not reached", cls: "bg-red-100 text-red-800" },
};
const ACTION_LABEL: Record<string, string> = {
  complete: "Marked done", uncomplete: "Undid 'done'", attempt: "Unsuccessful attempt", remark: "Remark", follow_up_on: "Flagged for follow-up", follow_up_off: "Follow-up cleared",
};
const newId = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`);

function HistoryList({ history }: { history: WelfareEvent[] }) {
  if (!history.length) return <p className="text-sm text-ink-500">Nothing recorded yet.</p>;
  return (
    <ol className="space-y-2">
      {[...history].reverse().map((e, i) => (
        <li key={`${e.at}-${i}`} className="rounded-xl bg-ink-50 p-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-500">
            <span className="font-medium text-ink-700">{ACTION_LABEL[e.action] ?? e.action}{e.outcome ? ` · ${OUTCOME_LABEL[e.outcome] ?? e.outcome}` : ""}</span>
            <span>{sgtDateTime(e.at)} · {e.by_email}</span>
          </div>
          {e.remark && <p className="mt-1 whitespace-pre-wrap text-ink-800">{e.remark}</p>}
        </li>))}
    </ol>
  );
}

function ResidentCard({ r, draft, setDraft, onSave, saving, error, showArea }: {
  r: Resident; showArea?: boolean; draft: Draft; setDraft: (d: Draft) => void; saving: string | null; error: string | null;
  onSave: (action: string, extra?: { outcome?: string; remark?: string }) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"none" | "attempt" | "remark">("none");
  const s = r.state, st = STATUS_STYLE[s.status];
  const busy = saving !== null;
  return (
    <article className={clsx("rounded-3xl border bg-surface p-4 shadow-card sm:p-5", s.completed ? "border-emerald-200" : s.follow_up ? "border-amber-200" : "border-ink-200")}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-ink-900">{r.name}</h3>
            <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-semibold", st.cls)}>{st.label}</span>
            {s.follow_up && s.completed && <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">Follow up</span>}
          </div>
          <div className="mt-0.5 text-sm text-ink-600">Blk {r.block} {r.street} · {r.unit} · {r.phone}</div>
          {showArea && r.subzone_name && <div className="mt-0.5 text-xs font-medium text-ink-500">{title(r.subzone_name)}</div>}
          {r.notes && <div className="mt-1 text-sm text-ink-700">{r.notes}</div>}
          {s.updated_at && <div className="mt-1 text-xs text-ink-400">Last update {sgtDateTime(s.updated_at)}{s.updated_by ? ` by ${s.updated_by}` : ""}</div>}
        </div>
        <button type="button" disabled={busy} onClick={() => onSave(s.completed ? "uncomplete" : "complete")}
          aria-pressed={s.completed} aria-label={s.completed ? `Undo done for ${r.name}` : `Mark ${r.name} as done`}
          className={clsx("inline-flex h-14 min-w-[150px] items-center justify-center gap-2 rounded-2xl px-4 text-base font-semibold transition",
            s.completed ? "border-2 border-emerald-500 bg-emerald-50 text-emerald-800 hover:bg-emerald-100" : "bg-emerald-600 text-white hover:brightness-110", busy && "opacity-60")}>
          {saving === "complete" || saving === "uncomplete" ? <Loader2 className="h-5 w-5 animate-spin" /> : s.completed ? <Undo2 className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
          {s.completed ? "Done · undo" : "Mark done"}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" icon={<PhoneOff className="h-4 w-4" />} onClick={() => setMode(mode === "attempt" ? "none" : "attempt")} disabled={busy}>Couldn't complete</Button>
        <Button size="sm" icon={<MessageSquarePlus className="h-4 w-4" />} onClick={() => setMode(mode === "remark" ? "none" : "remark")} disabled={busy}>Add remark</Button>
        <Button size="sm" icon={<Flag className="h-4 w-4" />} onClick={() => onSave(s.follow_up ? "follow_up_off" : "follow_up_on")} disabled={busy} loading={saving === "follow_up_on" || saving === "follow_up_off"}>
          {s.follow_up ? "Clear follow-up" : "Flag for follow-up"}
        </Button>
        <Button size="sm" icon={<History className="h-4 w-4" />} onClick={() => setOpen(!open)} aria-expanded={open}>History ({r.history.length})</Button>
      </div>

      {mode !== "none" && (
        <form className="mt-3 space-y-3 rounded-2xl bg-ink-50 p-4" onSubmit={(e) => {
          e.preventDefault();
          const done = mode === "attempt" ? onSave("attempt", { outcome: draft.outcome, remark: draft.remark }) : onSave("remark", { remark: draft.remark });
          void done.then((ok) => { if (ok) setMode("none"); });
        }}>
          {mode === "attempt" && (
            <fieldset><legend className="mb-2 text-sm font-medium text-ink-800">What happened?</legend>
              <div className="flex flex-wrap gap-2">{["no_response", "unavailable", "unreachable", "referred"].map((o) => (
                <label key={o} className={clsx("cursor-pointer rounded-xl border px-3 py-2 text-sm", draft.outcome === o ? "border-ink-900 bg-surface font-medium" : "border-ink-200 bg-surface")}>
                  <input type="radio" name={`o-${r.resident_id}`} value={o} checked={draft.outcome === o} onChange={() => setDraft({ ...draft, outcome: o })} className="sr-only" />{OUTCOME_LABEL[o]}
                </label>))}</div></fieldset>)}
          <label className="block text-sm font-medium text-ink-800">{mode === "attempt" ? "Remark (optional)" : "Remark"}
            <textarea className={clsx(inputClass, "mt-1 h-24 py-2")} maxLength={1000} value={draft.remark} onChange={(e) => setDraft({ ...draft, remark: e.target.value })}
              placeholder="e.g. Neighbour says she is staying with family this week" />
          </label>
          <div className="flex items-center justify-between gap-2 text-xs text-ink-500"><span>{draft.remark.length}/1000 · don't include medical details or other people's personal data</span></div>
          <div className="flex gap-2">
            <Button type="submit" variant="primary" loading={saving === mode} disabled={busy || (mode === "attempt" ? !draft.outcome : !draft.remark.trim())}>Save</Button>
            <Button type="button" onClick={() => setMode("none")}>Close</Button>
          </div>
        </form>)}
      {error && <p className="mt-3 flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</p>}
      {open && <div className="mt-3"><HistoryList history={r.history} /></div>}
    </article>
  );
}

/** The welfare checklist. `subzone` → only seniors living in that area (used on area pages, compact); otherwise the full list with an
 *  area filter (the Welfare checks page). Both read the same records, so a tick in one place shows in the other. */
export default function WelfareList({ subzone }: { subzone?: string }) {
  const inArea = !!subzone;
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: features.me, staleTime: 5 * 60_000 });
  const list = useQuery({ queryKey: ["welfare"], queryFn: features.welfare, enabled: !!me.data?.can_view_welfare, refetchInterval: 60_000 });
  const [filter, setFilter] = useState<Filter>(() => {               // e.g. /welfare?filter=follow_up from the to-do list
    if (subzone) return "all";
    const f = new URLSearchParams(window.location.search).get("filter");
    return f === "follow_up" || f === "done" || f === "all" ? f : "todo";
  });
  const [area, setArea] = useState<string>(() => subzone ?? new URLSearchParams(window.location.search).get("area")?.toUpperCase() ?? "");
  const [q, setQ] = useState("");
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});         // in memory only — never written to browser storage
  const [saving, setSaving] = useState<Record<string, string | null>>({});
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const pendingIds = useRef<Record<string, string>>({});
  const [touched, setTouched] = useState<Set<string>>(new Set());          // just-changed cards stay in view (so "undo" is reachable)
  useEffect(() => { setTouched(new Set()); }, [filter, area]);                    // same id on retry → server ignores duplicates

  const unsaved = Object.values(drafts).some((d) => d.remark.trim() || d.outcome) || Object.values(saving).some(Boolean);
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => { if (unsaved) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [unsaved]);

  const save = async (r: Resident, action: string, extra?: { outcome?: string; remark?: string }): Promise<boolean> => {
    const sig = `${r.resident_id}|${action}|${extra?.outcome ?? ""}|${extra?.remark ?? ""}|${r.state.version}`;
    const cid = pendingIds.current[sig] ?? (pendingIds.current[sig] = newId());
    setTouched((t) => new Set(t).add(r.resident_id));
    setSaving((s) => ({ ...s, [r.resident_id]: action })); setErrors((e) => ({ ...e, [r.resident_id]: null }));
    try {
      const res = await features.welfareEvent(r.resident_id, { action, outcome: extra?.outcome || null, remark: extra?.remark?.trim() || null, expected_version: r.state.version, client_event_id: cid });
      delete pendingIds.current[sig];
      if (action === "attempt" || action === "remark") setDrafts((d) => ({ ...d, [r.resident_id]: { remark: "", outcome: "" } }));
      qc.setQueryData<Awaited<ReturnType<typeof features.welfare>>>(["welfare"], (old) => old && {
        ...old, residents: old.residents.map((x) => x.resident_id === r.resident_id ? { ...x, state: res.state, history: res.history ?? x.history } : x) });
      if (res.duplicate) void list.refetch();
      return true;
    } catch (err) {
      const conflict = err instanceof ApiError && err.status === 409;
      if (conflict) delete pendingIds.current[sig];
      setErrors((e) => ({ ...e, [r.resident_id]: err instanceof ApiError ? err.message : "Couldn't save. Your changes are still here — try again." }));
      if (conflict) void list.refetch();
      return false;
    } finally {
      setSaving((s) => ({ ...s, [r.resident_id]: null }));
    }
  };

  const everyone = list.data?.residents ?? [];
  const areas = useMemo(() => {
    const m = new Map<string, number>();
    everyone.forEach((r) => r.subzone_name && m.set(r.subzone_name, (m.get(r.subzone_name) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [everyone]);
  const residents = area ? everyone.filter((r) => r.subzone_name === area) : everyone;
  const counts = useMemo(() => ({
    all: residents.length, todo: residents.filter((r) => !r.state.completed).length,
    follow_up: residents.filter((r) => r.state.follow_up).length, done: residents.filter((r) => r.state.completed).length }), [residents]);
  const shown = residents.filter((r) => {
    if (touched.has(r.resident_id)) return true;
    if (filter === "todo" && r.state.completed) return false;
    if (filter === "done" && !r.state.completed) return false;
    if (filter === "follow_up" && !r.state.follow_up) return false;
    const t = q.trim().toLowerCase();
    return !t || `${r.name} ${r.block} ${r.street} ${r.unit}`.toLowerCase().includes(t);
  });

  if (me.isPending) return <Skeleton className="h-40 rounded-3xl" />;
  if (me.isError) return inArea ? null : <ErrorState error={me.error} onRetry={() => me.refetch()} />;
  if (!me.data.can_view_welfare) return inArea ? (
    <p className="flex items-center gap-2 rounded-2xl bg-ink-50 p-4 text-sm text-ink-600"><Lock className="h-4 w-4 shrink-0" />Only volunteers and coordinators can see who lives here.</p>
  ) : (
    <>
      <div className="flex items-start gap-3 rounded-3xl border border-ink-200 bg-surface p-6 shadow-card"><Lock className="mt-0.5 h-6 w-6 text-ink-400" /><div>
        <h2 className="text-lg font-semibold text-ink-900">{me.data.signed_in ? "You don't have access yet" : "Please sign in"}</h2>
        <p className="mt-1 text-ink-600">{me.data.signed_in ? "Welfare check lists are only shown to volunteers and coordinators. Ask your coordinator to add you." : "Sign in with your Databricks account to see welfare checks."}</p></div></div></>);

  if (inArea && list.isSuccess && residents.length === 0) return (
    <p className="rounded-2xl bg-ink-50 p-4 text-sm text-ink-600">No one on your welfare list lives in this area. <Link to="/welfare" className="font-medium text-brand-700">See the full list</Link></p>
  );

  return (
    <>
      {list.data?.demo && (inArea
        ? <p className="mb-3 inline-block rounded-full border border-dashed border-violet-300 bg-violet-50 px-3 py-1 text-xs font-medium text-violet-900">Demo data — fictional residents</p>
        : <div className="mb-4 rounded-2xl border-2 border-dashed border-violet-300 bg-violet-50 p-4 text-sm font-medium text-violet-900">{list.data.notice}</div>)}
      {list.isPending ? <div className="space-y-3"><Skeleton className="h-32 rounded-3xl" /><Skeleton className="h-32 rounded-3xl" /></div> :
        list.isError ? <ErrorState error={list.error} onRetry={() => list.refetch()} title="Couldn't load the welfare list" /> : (
        <>
          {!inArea && <div className="mb-4 grid grid-cols-3 gap-3">
            {[["To do", counts.todo, "text-ink-900"], ["Follow up", counts.follow_up, "text-amber-700"], ["Done", counts.done, "text-emerald-700"]].map(([l, n, c]) => (
              <div key={l as string} className="rounded-2xl border border-ink-200 bg-surface p-3 text-center shadow-card"><div className={clsx("text-2xl font-semibold", c as string)}>{n}</div><div className="text-xs text-ink-500">{l}</div></div>))}
          </div>}
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Segmented value={filter} onChange={setFilter} options={[{ value: "todo", label: `To do (${counts.todo})` }, { value: "follow_up", label: `Follow up (${counts.follow_up})` }, { value: "done", label: `Done (${counts.done})` }, { value: "all", label: "All" }]} />
            {!inArea && areas.length > 1 && (
              <select aria-label="Area" className={clsx(inputClass, "sm:w-56")} value={area} onChange={(e) => setArea(e.target.value)}>
                <option value="">All areas ({everyone.length})</option>
                {areas.map(([a, n]) => <option key={a} value={a}>{title(a)} ({n})</option>)}
              </select>
            )}
            {!inArea && <label className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <input className={clsx(inputClass, "pl-9")} placeholder="Search name or block" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search residents" /></label>}
          </div>
          {shown.length === 0 ? <EmptyState title={filter === "todo" && counts.all > 0 ? "Everyone has been checked" : "No one matches"} body={filter === "todo" ? "Nice work. Check the follow-up list for anyone who still needs help." : "Try another filter or search."} /> : (
            <div className="space-y-3">
              {shown.map((r) => (
                <ResidentCard key={r.resident_id} r={r} showArea={!inArea} saving={saving[r.resident_id] ?? null} error={errors[r.resident_id] ?? null}
                  draft={drafts[r.resident_id] ?? { remark: "", outcome: "" }} setDraft={(d) => setDrafts((all) => ({ ...all, [r.resident_id]: d }))}
                  onSave={(a, extra) => save(r, a, extra)} />))}
            </div>)}
          {inArea && <Link to={`/welfare?area=${encodeURIComponent(subzone!)}`} className="mt-3 inline-block text-sm font-medium text-brand-700">Open in the full welfare list</Link>}
          {!inArea && <p className="mt-6 flex items-center gap-1.5 text-xs text-ink-500"><History className="h-3.5 w-3.5 shrink-0" />Every change is kept in the history with who made it and when. The list refreshes every minute; if someone else updates a record first, you'll be asked to review before saving again.</p>}
        </>)}
    </>
  );
}
