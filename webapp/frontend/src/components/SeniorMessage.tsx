import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, Copy, RotateCcw, Send, Share2 } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, features, type ComposeInput, type Lang } from "../lib/api";
import TelegramSend from "./TelegramSend";
import { Button, Skeleton } from "./ui";

const LANGS: { code: Lang; label: string }[] = [{ code: "en", label: "English" }, { code: "zh", label: "中文" }, { code: "ms", label: "Melayu" }, { code: "ta", label: "தமிழ்" }];
const LANG_KEY = "heatguard.messageLanguage";            // the language last used, on this device

function readLang(): Lang {
  try { const v = localStorage.getItem(LANG_KEY); return v === "zh" || v === "ms" || v === "ta" ? v : "en"; } catch { return "en"; }
}


export default function SeniorMessage({ level, forDate, centre, cool, haze, area }: {
  level: ComposeInput["level"]; forDate: string | null; centre: string; cool: string | null; haze: boolean; area: string;
}) {
  const [lang, setLang] = useState<Lang>(() => readLang());
  const [text, setText] = useState("");
  const [edited, setEdited] = useState(false);
  const [copied, setCopied] = useState(false);
  const [sheet, setSheet] = useState(false);
  const input: ComposeInput = { level, for_date: forDate ?? "", language: lang, centre, cool, haze };
  const q = useQuery({ queryKey: ["compose", input], queryFn: () => features.compose(input), enabled: !!forDate, staleTime: Infinity });
  const tg = useQuery({ queryKey: ["telegram"], queryFn: features.telegram, staleTime: 60_000, retry: false });
  useEffect(() => { if (q.data) { setText(q.data.text); setEdited(false); } }, [q.data]);
  useEffect(() => { try { localStorage.setItem(LANG_KEY, lang); } catch { /* not remembered */ } }, [lang]);
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
          <h2 className="text-lg font-semibold text-ink-900">Message for seniors in {area}</h2>
          <p className="mt-0.5 text-sm text-ink-500">Ready to send in their language, naming the cool place nearest to them. You can edit it before sending.</p>
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
        {!canSend && !(t?.configured && t.bot && t.can_manage) ? "Share opens Telegram with the message filled in — pick the group or the people in this area. " : null}
        Each language uses fixed, hand-written wording — nothing is machine-translated on the fly.
      </p>
      {sheet && t && <TelegramSend chats={t.chats} text={text} audience="seniors" language={lang} onClose={() => setSheet(false)} />}
    </section>
  );
}
