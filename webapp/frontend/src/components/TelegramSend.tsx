import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { CheckCircle2, Send, X, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ApiError, features, type TelegramChat } from "../lib/api";
import { Button } from "./ui";

const newId = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`);

/** Bottom sheet (phones) / dialog (desktop): choose linked groups, send once, show what happened in each group. */
export default function TelegramSend({ chats, text, audience, language, onClose }: {
  chats: TelegramChat[]; text: string; audience: string; language: string; onClose: () => void;
}) {
  const [picked, setPicked] = useState<string[]>(chats.map((c) => c.chat_id));
  const sendId = useRef(newId());                       // same id on retry → the server never posts twice
  const panel = useRef<HTMLDivElement>(null);
  const m = useMutation({ mutationFn: () => features.telegramSend({ chat_ids: picked, text, audience, language, client_send_id: sendId.current }) });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !m.isPending) onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose, m.isPending]);

  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const done = m.data && m.data.results.every((r) => r.ok);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label="Send to Telegram">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => !m.isPending && onClose()} />
      <div ref={panel} tabIndex={-1} className="pb-safe relative max-h-[90vh] w-full max-w-lg animate-sheet-in overflow-y-auto rounded-t-3xl bg-surface shadow-2xl outline-none sm:rounded-3xl">
        <div className="mx-auto mt-2.5 h-1.5 w-10 rounded-full bg-ink-200 sm:hidden" />
        <div className="flex items-start justify-between gap-3 px-5 pb-2 pt-4">
          <div>
            <h2 className="text-lg font-semibold text-ink-900">Send to Telegram</h2>
            <p className="text-sm text-ink-500">Posts the message in the groups you choose.</p>
          </div>
          <button onClick={onClose} disabled={m.isPending} className="rounded-xl p-2 text-ink-400 hover:bg-ink-100 hover:text-ink-700" aria-label="Close"><X className="h-5 w-5" /></button>
        </div>

        <div className="space-y-4 px-5 pb-5">
          {!m.data && (
            <fieldset className="space-y-2">
              <legend className="mb-1 text-sm font-medium text-ink-700">Groups</legend>
              {chats.map((c) => (
                <label key={c.chat_id} className={clsx("flex min-h-[52px] cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 transition",
                  picked.includes(c.chat_id) ? "border-telegram/60 bg-sky-50" : "border-ink-200")}>
                  <input type="checkbox" className="h-5 w-5 rounded border-ink-300 text-telegram" checked={picked.includes(c.chat_id)} onChange={() => toggle(c.chat_id)} />
                  <span className="flex-1"><span className="block font-medium text-ink-900">{c.title}</span>
                    <span className="block text-xs text-ink-500">{c.chat_type === "channel" ? "Channel" : "Group"}</span></span>
                </label>
              ))}
            </fieldset>
          )}

          <div className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded-2xl bg-ink-50 p-3.5 text-sm leading-relaxed text-ink-700">{text}</div>

          {m.isError && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">{m.error instanceof ApiError ? m.error.message : "Couldn't send. Please try again."}</p>}

          {m.data && (
            <ul className="space-y-2" aria-live="polite">
              {m.data.results.map((r) => (
                <li key={r.chat_id} className={clsx("flex items-start gap-3 rounded-2xl p-3.5", r.ok ? "bg-emerald-50 text-emerald-900" : "bg-red-50 text-red-900")}>
                  {r.ok ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" /> : <XCircle className="mt-0.5 h-5 w-5 shrink-0" />}
                  <span><b>{r.title ?? "Group"}</b>: {r.ok ? (r.already_sent ? "already sent" : "sent") : r.error}</span>
                </li>
              ))}
            </ul>
          )}

          {done ? (
            <Button variant="primary" className="h-12 w-full text-base" onClick={onClose}>Done</Button>
          ) : (
            <button type="button" onClick={() => m.mutate()} disabled={picked.length === 0 || m.isPending}
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-telegram text-base font-semibold text-white shadow-sm transition hover:brightness-110 active:scale-[0.99] disabled:opacity-50">
              <Send className={clsx("h-5 w-5", m.isPending && "animate-pulse")} />
              {m.isPending ? "Sending…" : m.data ? "Try the failed ones again" : `Send to ${picked.length} group${picked.length !== 1 ? "s" : ""}`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
