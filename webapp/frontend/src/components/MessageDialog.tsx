import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, Copy, Info, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ApiError, api, type CheckinRow } from "../lib/api";
import { dayLabel, title } from "../lib/format";
import { Banner, Button, Field, inputClass, Segmented } from "./ui";

export default function MessageDialog({ row, onClose }: { row: CheckinRow; onClose: () => void }) {
  const opts = useQuery({ queryKey: ["message-options"], queryFn: api.messageOptions, staleTime: Infinity });
  const [audience, setAudience] = useState("seniors");
  const [language, setLanguage] = useState("English");
  const [copied, setCopied] = useState(false);
  const mutation = useMutation({ mutationFn: () => api.message(row.subzone_name, language, audience) });
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);

  const copy = async () => {
    if (!mutation.data) return;
    try { await navigator.clipboard.writeText(mutation.data.text); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* clipboard blocked: text is still selectable */ }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label="Write a message">
      <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm" onClick={onClose} />
      <div ref={panel} tabIndex={-1} className="relative w-full max-w-2xl animate-fade-in rounded-t-3xl bg-white shadow-2xl outline-none sm:rounded-3xl">
        <div className="flex items-start justify-between border-b border-ink-100 px-6 py-5">
          <div>
            <div className="flex items-center gap-2 text-[13px] font-medium text-brand-700"><Sparkles className="h-4 w-4" /> Write a message</div>
            <h2 className="mt-1 text-lg font-semibold text-ink-900">{title(row.subzone_name)}</h2>
            <p className="text-sm text-ink-500">{title(row.planning_area)} · {dayLabel(row.for_date, { long: true })}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-ink-400 hover:bg-ink-100 hover:text-ink-700" aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-5 px-6 py-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Who is it for?">
              <Segmented size="sm" value={audience} onChange={(v) => { setAudience(v); mutation.reset(); }}
                options={(opts.data?.audiences ?? [{ id: "seniors", label: "Message to seniors" }, { id: "staff", label: "Briefing for staff and volunteers" }]).map((a) => ({ value: a.id, label: a.id === "seniors" ? "Seniors" : "Staff & volunteers" }))} />
            </Field>
            <Field label="Language">
              <select className={inputClass} value={language} onChange={(e) => { setLanguage(e.target.value); mutation.reset(); }}>
                {(opts.data?.languages ?? ["English"]).map((l) => <option key={l}>{l}</option>)}
              </select>
            </Field>
          </div>
          <div className="flex items-start gap-2 rounded-xl bg-ink-50 px-3.5 py-3 text-[13px] text-ink-600">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />
            The message only includes HeatGuard's standard safety steps, written warmly and translated for you.
          </div>
          {mutation.isError && (
            <Banner tone="warning">{mutation.error instanceof ApiError ? mutation.error.message : "Couldn't write the message. Please try again."}</Banner>
          )}
          {mutation.data && (
            <div className="space-y-2">
              {!mutation.data.used_ai && <Banner tone="info">The writing assistant is busy right now, so here is the plain version. You can still copy and send it.</Banner>}
              <div className="relative rounded-2xl border border-ink-200 bg-white">
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap px-4 py-4 pr-24 font-sans text-[15px] leading-relaxed text-ink-800">{mutation.data.text}</pre>
                <Button size="sm" className={clsx("absolute right-3 top-3", copied && "border-emerald-300 text-emerald-700")} icon={copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} onClick={copy}>
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-ink-100 px-6 py-4">
          <Button variant="ghost" onClick={onClose}>Close</Button>
          <Button variant="primary" icon={<Sparkles className="h-4 w-4" />} loading={mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending ? "Writing…" : mutation.data ? "Write again" : "Write the message"}
          </Button>
        </div>
      </div>
    </div>
  );
}
