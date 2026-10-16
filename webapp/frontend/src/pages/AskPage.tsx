import { useMutation } from "@tanstack/react-query";
import { ArrowUp, Download, Info, MessagesSquare, RotateCcw, Sparkles, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button, Card, PageHeader } from "../components/ui";
import { ApiError, api, type GenieAnswer, type GenieTable } from "../lib/api";
import { downloadCsv } from "../lib/format";

const SUGGESTED = [
  "Which areas in Bukit Merah should we check on first tomorrow?",
  "Which areas near Toa Payoh have the most seniors living there?",
  "Which priority areas are more than 1 km from a cool place?",
  "Which Community Clubs or libraries are in Bedok?",
  "Which areas might get very hot tomorrow?",
  "How many seniors live in the areas we should check first tomorrow?",
]

type Msg = { role: "user"; text: string } | { role: "assistant"; answer?: GenieAnswer; error?: string };

// Coordinators see plain columns only: technical ones (scores, codes, coordinates, model outputs) are hidden.
const HIDDEN = /^(rank|risk_score|hazard|exposure|exposure_pctl|heat_hazard|haze_hazard|haze_component|access_component|vulnerability_score|high_alert|action_band|heat_is_forecast|heat_basis|for_date|prob_.*|wbgt.*|.*_ts|.*_latitude|.*_longitude|latitude|longitude|centroid_.*|.*_code|station_id|model_.*|main_driver|reason|action|psi_twenty_four_hourly|pm25_.*|census_rank|pa_.*|pct_75_plus|pop_75_plus|pop_total|cool_spaces_within_1km|nearest_wbgt_station.*|haze_region|ura_region)$/;
const NAMES: Record<string, string> = {
  subzone_name: "Area", planning_area: "Town", pop_65_plus: "Seniors (65+)", pct_65_plus: "Share aged 65+", pct_1_2_room: "In 1–2 room flats",
  nearest_cool_space: "Nearest cool place", nearest_cool_space_type: "Type", cool_space_km: "Distance (km)", tier: "Priority",
  heat_band: "Afternoon", psi_band: "Haze", name: "Name", space_type: "Type", street: "Street", postal_code: "Postal code",
};
const TIER_WORDS: Record<string, string> = { "Start here": "Check first", "Check in": "Phone check-in", Routine: "Routine" };
const HEAT_WORDS: Record<string, string> = { High: "Very hot", Moderate: "Hot", Low: "Normal" };
const titleCase = (v: string) => v.toLowerCase().replace(/\b\w/g, (m) => m.toUpperCase());

function ResultTable({ table }: { table: GenieTable }) {
  const keep = table.columns.map((c, i) => [c, i] as const).filter(([c]) => !HIDDEN.test(c));
  if (!table.rows.length) return <p className="text-sm text-ink-500">Nothing matched that question.</p>;
  if (!keep.length) return null;
  const fmt = (c: string, v: string | number | null) => {
    if (v === null || v === "") return "—";
    if (c.startsWith("pct_") && typeof v === "number") return `${Math.round(v * 100)}%`;
    if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(1);
    if (c === "tier") return TIER_WORDS[v] ?? v;
    if (c === "heat_band") return HEAT_WORDS[v] ?? v;
    if (["subzone_name", "planning_area", "name", "street", "nearest_cool_space"].includes(c) || /^[A-Z0-9 '()&/.-]{3,}$/.test(v)) return titleCase(v);
    return v;
  };
  const nice = (c: string) => NAMES[c] ?? c.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
  table = { columns: keep.map(([c]) => c), rows: table.rows.map((r) => keep.map(([c, i]) => fmt(c, r[i]))) };
  return (
    <div className="overflow-hidden rounded-xl border border-ink-200">
      <div className="max-h-80 overflow-auto">
        <table className="w-full text-left text-[13px]">
          <thead className="sticky top-0 bg-ink-50 text-xs font-semibold text-ink-500"><tr>{table.columns.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2">{nice(c)}</th>)}</tr></thead>
          <tbody className="divide-y divide-ink-100">{table.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className="max-w-xs px-3 py-2 align-top text-ink-800">{v}</td>)}</tr>)}</tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-ink-100 bg-ink-50/60 px-3 py-2 text-xs text-ink-500">
        <span>{table.rows.length} row{table.rows.length === 1 ? "" : "s"}</span>
        <button className="inline-flex items-center gap-1 font-medium text-brand-700 hover:text-brand-800"
          onClick={() => downloadCsv("heatguard-answer.csv", table.rows.map((r) => Object.fromEntries(table.columns.map((c, j) => [c, r[j]]))))}>
          <Download className="h-3.5 w-3.5" /> Download
        </button>
      </div>
    </div>
  );
}

function Answer({ answer }: { answer: GenieAnswer }) {
  return (
    <div className="space-y-4">
      {answer.text.map((t, i) => <div key={i} className="prose-sm max-w-none text-[15px] leading-relaxed text-ink-800 [&_li]:ml-4 [&_li]:list-disc [&_p]:mb-2 [&_strong]:text-ink-900"><ReactMarkdown>{t}</ReactMarkdown></div>)}
      {answer.queries.map((q, i) => (
        <div key={i} className="space-y-2.5">
          {q.table && <ResultTable table={q.table} />}
        </div>
      ))}
    </div>
  );
}

export default function AskPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [conversation, setConversation] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const mutation = useMutation({
    mutationFn: (q: string) => api.genie(q, conversation),
    onSuccess: (a) => { setConversation(a.conversation_id); setMessages((m) => [...m, { role: "assistant", answer: a }]); },
    onError: (e) => setMessages((m) => [...m, { role: "assistant", error: e instanceof ApiError ? e.message : "Something went wrong talking to Genie. Try again in a moment." }]),
  });
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, mutation.isPending]);

  const ask = (q: string) => {
    const text = q.trim();
    if (!text || mutation.isPending) return;
    if (text.length > 500) { setMessages((m) => [...m, { role: "assistant", error: "That question is very long. Please keep it under 500 characters." }]); return; }
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    mutation.mutate(text);
  };
  const reset = () => { setMessages([]); setConversation(null); mutation.reset(); };
  const last = messages[messages.length - 1];
  const suggestions = last?.role === "assistant" && last.answer ? last.answer.suggestions.slice(0, 3) : [];

  return (
    <div className="flex min-h-[calc(100vh-7rem)] flex-col">
      <PageHeader title="Ask a question" subtitle="Ask in your own words about areas, seniors and cool places — HeatGuard looks it up for you."
        right={messages.length > 0 && <Button icon={<RotateCcw className="h-4 w-4" />} onClick={reset}>New conversation</Button>} />

      <div className="flex-1 space-y-5 pb-36">
        {messages.length === 0 && (
          <Card className="bg-gradient-to-br from-white to-brand-50/50">
            <div className="flex items-center gap-2 text-sm font-medium text-ink-900"><Sparkles className="h-4 w-4 text-brand-600" /> Try one of these</div>
            <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
              {SUGGESTED.map((s) => (
                <button key={s} onClick={() => ask(s)} className="group flex items-center gap-3 rounded-xl border border-ink-200 bg-white px-4 py-3 text-left text-sm text-ink-700 shadow-sm transition hover:border-brand-300 hover:text-ink-900">
                  <MessagesSquare className="h-4 w-4 shrink-0 text-ink-400 group-hover:text-brand-600" />{s}
                </button>
              ))}
            </div>
            <p className="mt-4 flex items-start gap-1.5 text-xs text-ink-500"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />Answers are looked up from HeatGuard's data and can occasionally be wrong — double-check anything important on My plan.</p>
          </Card>
        )}

        {messages.map((m, i) => m.role === "user" ? (
          <div key={i} className="flex justify-end gap-3 animate-fade-in">
            <div className="max-w-[80%] rounded-2xl rounded-tr-md bg-ink-900 px-4 py-2.5 text-[15px] text-white">{m.text}</div>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink-200 text-ink-600"><User className="h-4 w-4" /></div>
          </div>
        ) : (
          <div key={i} className="flex gap-3 animate-fade-in">
            <img src="/favicon.svg" alt="" className="h-8 w-8 shrink-0 rounded-full" />
            <Card className="min-w-0 flex-1">
              {m.error ? <p className="text-sm text-amber-800">{m.error}</p> : m.answer && <Answer answer={m.answer} />}
            </Card>
          </div>
        ))}

        {mutation.isPending && (
          <div className="flex gap-3">
            <img src="/favicon.svg" alt="" className="h-8 w-8 shrink-0 rounded-full" />
            <Card className="flex items-center gap-3 !py-4 text-sm text-ink-500">
              <span className="flex gap-1">{[0, 150, 300].map((d) => <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-brand-400" style={{ animationDelay: `${d}ms` }} />)}</span>
              Looking that up… usually 10–30 seconds
            </Card>
          </div>
        )}

        {suggestions.length > 0 && !mutation.isPending && (
          <div className="flex flex-wrap gap-2 pl-11">
            {suggestions.map((s) => <button key={s} onClick={() => ask(s)} className="rounded-full border border-ink-200 bg-white px-3.5 py-1.5 text-[13px] text-ink-700 shadow-sm hover:border-brand-300 hover:text-ink-900">{s}</button>)}
          </div>
        )}
        <div ref={bottom} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); ask(input); }} className="sticky bottom-4 z-10">
        <div className="flex items-center gap-2 rounded-2xl border border-ink-200 bg-white p-2 shadow-lift focus-within:border-brand-400 focus-within:ring-4 focus-within:ring-brand-500/10">
          <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={500} disabled={mutation.isPending}
            placeholder="e.g. Which areas in Toa Payoh should we check first tomorrow?" aria-label="Your question"
            className="h-11 flex-1 bg-transparent px-3 text-[15px] text-ink-900 placeholder:text-ink-400 focus:outline-none" />
          <button type="submit" disabled={!input.trim() || mutation.isPending} aria-label="Send"
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white transition hover:bg-brand-700 disabled:bg-ink-200">
            <ArrowUp className="h-5 w-5" />
          </button>
        </div>
      </form>
    </div>
  );
}
