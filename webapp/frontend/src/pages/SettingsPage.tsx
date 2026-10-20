import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { CheckCircle2, ExternalLink, Link2, Lock, Monitor, Moon, Search, Send, Sun, Unlink } from "lucide-react";
import { useRef } from "react";
import { Button, ErrorState, PageHeader, Segmented, Skeleton } from "../components/ui";
import { ApiError, features, type TelegramChat } from "../lib/api";
import { sgtDateTime } from "../lib/heat";
import { useThemeMode, type ThemeMode } from "../lib/themeMode";

const newId = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`);
const card = "rounded-3xl border border-ink-200 bg-surface p-5 shadow-card md:p-6";

function Step({ n, done, title, children }: { n: number; done?: boolean; title: string; children?: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className={clsx("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold", done ? "bg-emerald-600 text-white" : "bg-ink-100 text-ink-700")}>
        {done ? <CheckCircle2 className="h-4 w-4" /> : n}
      </span>
      <div className="min-w-0 flex-1 pb-1"><div className="font-medium text-ink-900">{title}</div>{children && <div className="mt-1 text-sm text-ink-600">{children}</div>}</div>
    </li>
  );
}

function Telegram() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["telegram"], queryFn: features.telegram, retry: false });
  const discover = useMutation({ mutationFn: features.telegramDiscover });
  const setChats = (chats: TelegramChat[]) => qc.setQueryData(["telegram"], (old: typeof status.data) => old && { ...old, chats });
  const link = useMutation({ mutationFn: features.telegramLink, onSuccess: (r) => { setChats(r.chats); discover.reset(); } });
  const unlink = useMutation({ mutationFn: features.telegramUnlink, onSuccess: (r) => setChats(r.chats) });
  const testId = useRef(newId());
  const test = useMutation({ mutationFn: (chat_id: string) => features.telegramSend({ chat_ids: [chat_id], audience: "test", client_send_id: `${testId.current}-${chat_id}`.slice(0, 64),
    text: "✅ HeatGuard is connected to this group. Heat reminders from your centre will appear here." }) });

  if (status.isPending) return <section className={card}><Skeleton className="h-6 w-40" /><Skeleton className="mt-4 h-32 rounded-2xl" /></section>;
  if (status.isError) return <ErrorState error={status.error} onRetry={() => status.refetch()} title="Couldn't check Telegram" />;
  const t = status.data;
  const err = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

  return (
    <section className={card} id="telegram">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900"><Send className="h-5 w-5 text-telegram" /> Telegram</h2>
      <p className="mt-1 text-sm text-ink-500">Send the daily heat message to your centre's Telegram group. HeatGuard never stores anyone's personal Telegram account.</p>

      {!t.configured || !t.bot ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-start gap-3 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-950">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <p><b>Ready to use — no setup needed.</b> On My plan, <b>Share on Telegram</b> opens Telegram with the message filled in. Pick your centre's group (or the people you want) and send.</p>
          </div>
          {t.bot_error ? <p className="text-sm text-amber-800">{t.bot_error}</p> : (
            <p className="text-[13px] text-ink-500">Optional, for later: the HeatGuard team can switch on a HeatGuard bot that posts to your group in one tap and keeps a record of what was sent.</p>
          )}
        </div>
      ) : !t.can_manage ? (
        <div className="mt-4 flex items-start gap-3 rounded-2xl bg-ink-50 p-4 text-sm text-ink-700"><Lock className="mt-0.5 h-4 w-4 shrink-0" />Only coordinators can link groups and send messages. {t.chats.length > 0 && <>Linked: {t.chats.map((c) => c.title).join(", ")}.</>}</div>
      ) : (
        <>
          <ol className="mt-5 space-y-4">
            <Step n={1} done title={`Bot ready: @${t.bot.username}`}>
              <a href={`https://t.me/${t.bot.username}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-brand-700">Open in Telegram <ExternalLink className="h-3.5 w-3.5" /></a>
            </Step>
            <Step n={2} done={t.chats.length > 0} title="Add the bot to your group">
              In Telegram, open your centre's group → <b>Add members</b> → search <b>@{t.bot.username}</b>. For a channel, add it as an <b>admin</b> who can post. Then send any message in the group so HeatGuard can find it.
            </Step>
            <Step n={3} done={t.chats.length > 0} title="Find and link the group">
              <Button className="mt-2" icon={<Search className="h-4 w-4" />} loading={discover.isPending} onClick={() => discover.mutate()}>Find my groups</Button>
              {discover.isError && <p className="mt-2 rounded-xl bg-amber-50 p-3 text-amber-900">{err(discover.error)}</p>}
              {discover.data && (discover.data.chats.length === 0 ? (
                <p className="mt-2 rounded-xl bg-ink-50 p-3">No groups found yet. Check that the bot is in the group and that someone posted a message there in the last 24 hours, then try again.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {discover.data.chats.map((c) => (
                    <li key={c.chat_id} className="flex items-center justify-between gap-3 rounded-2xl border border-ink-200 p-3">
                      <span><span className="block font-medium text-ink-900">{c.title}</span><span className="text-xs text-ink-500">{c.chat_type === "channel" ? "Channel" : "Group"}</span></span>
                      {c.linked ? <span className="text-sm font-medium text-emerald-700">Linked</span>
                        : <Button size="sm" variant="primary" icon={<Link2 className="h-4 w-4" />} loading={link.isPending && link.variables === c.chat_id} onClick={() => link.mutate(c.chat_id)}>Link</Button>}
                    </li>
                  ))}
                </ul>
              ))}
              {link.isError && <p className="mt-2 rounded-xl bg-amber-50 p-3 text-amber-900">{err(link.error)}</p>}
            </Step>
          </ol>

          <h3 className="mt-6 text-sm font-semibold text-ink-700">Linked groups</h3>
          {t.chats.length === 0 ? <p className="mt-1 text-sm text-ink-500">None yet.</p> : (
            <ul className="mt-2 space-y-2">
              {t.chats.map((c) => (
                <li key={c.chat_id} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-ink-50 p-3.5">
                  <span className="min-w-0"><span className="block font-medium text-ink-900">{c.title}</span>
                    <span className="block text-xs text-ink-500">Linked {c.linked_at ? sgtDateTime(c.linked_at) : ""}{c.linked_by ? ` by ${c.linked_by}` : ""}</span></span>
                  <span className="flex gap-2">
                    <Button size="sm" icon={<Send className="h-4 w-4" />} loading={test.isPending && test.variables === c.chat_id} onClick={() => test.mutate(c.chat_id)}>Send a test</Button>
                    <Button size="sm" variant="ghost" icon={<Unlink className="h-4 w-4" />} loading={unlink.isPending && unlink.variables === c.chat_id} onClick={() => unlink.mutate(c.chat_id)}>Unlink</Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {test.data && <p className="mt-2 text-sm text-emerald-700" aria-live="polite">{test.data.results[0]?.ok ? "Test message sent — check the group." : test.data.results[0]?.error}</p>}
          {(test.isError || unlink.isError) && <p className="mt-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{err(test.error ?? unlink.error)}</p>}
        </>
      )}
    </section>
  );
}

export default function SettingsPage() {
  const [mode, setMode] = useThemeMode();
  return (
    <>
      <PageHeader title="Settings" subtitle="How HeatGuard looks, and where it sends messages." />
      <div className="space-y-5">
        <section className={card}>
          <h2 className="text-lg font-semibold text-ink-900">Appearance</h2>
          <p className="mt-1 text-sm text-ink-500">Dark mode is easier on the eyes at night. Remembered on this device.</p>
          <div className="mt-4">
            <Segmented<ThemeMode> value={mode} onChange={setMode} options={[
              { value: "system", label: <><Monitor className="h-4 w-4" />Same as device</> },
              { value: "light", label: <><Sun className="h-4 w-4" />Light</> },
              { value: "dark", label: <><Moon className="h-4 w-4" />Dark</> },
            ]} />
          </div>
        </section>
        <Telegram />
      </div>
    </>
  );
}
