import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Info, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, ErrorState, PageHeader, Skeleton } from "../components/ui";
import { api } from "../lib/api";

const SLOW_MS = 20_000;

/* The Genie space runs inside this page only. The sandbox lets it work normally (sign-in, questions, charts, CSV downloads,
   copying) but blocks pop-ups and new tabs, so links inside Genie can't take people out to the Databricks website. */
const SANDBOX = "allow-scripts allow-same-origin allow-forms allow-downloads allow-modals";

export default function AskPage() {
  const links = useQuery({ queryKey: ["genie-embed"], queryFn: api.genieEmbed, staleTime: Infinity, retry: 1 });
  const [reloads, setReloads] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [slow, setSlow] = useState(false);
  const [offline, setOffline] = useState(typeof navigator !== "undefined" && !navigator.onLine);
  const reload = () => setReloads((n) => n + 1);

  useEffect(() => {
    setLoaded(false); setSlow(false);
    const t = setTimeout(() => setSlow(true), SLOW_MS);
    return () => clearTimeout(t);
  }, [reloads, links.data?.embed_url]);
  useEffect(() => {
    const on = () => { setOffline(false); reload(); }, off = () => setOffline(true);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  return (
    <>
      <PageHeader title="Ask a question" subtitle="Ask in your own words about areas, seniors and cool places. Genie shows how it worked out the answer, with charts when they help."
        right={links.isSuccess && <Button size="sm" icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={reload}>Reload</Button>} />

      {links.isPending ? <Skeleton className="h-[70dvh] min-h-[480px] rounded-3xl" /> :
        links.isError ? <ErrorState error={links.error} onRetry={() => links.refetch()} title="Couldn't open Genie" /> : (
        <div className="space-y-3">
          {offline && <p className="rounded-2xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">You're offline. Genie will reload when the connection is back.</p>}

          <div className="relative h-[70dvh] min-h-[480px] overflow-hidden rounded-3xl border border-ink-200 bg-surface shadow-card">
            <iframe key={reloads} src={links.data.embed_url} title="HeatGuard Genie" allow="clipboard-write" sandbox={SANDBOX}
              referrerPolicy="strict-origin-when-cross-origin" onLoad={() => setLoaded(true)}
              className={clsx("h-full w-full border-0 transition-opacity", loaded ? "opacity-100" : "opacity-0")} />
            {!loaded && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center" aria-live="polite">
                {!slow ? (
                  <>
                    <span className="flex gap-1">{[0, 150, 300].map((d) => <span key={d} className="h-2.5 w-2.5 animate-bounce rounded-full bg-brand-400" style={{ animationDelay: `${d}ms` }} />)}</span>
                    <p className="text-sm text-ink-600">Opening Genie… the first time can take 10–20 seconds.</p>
                  </>
                ) : (
                  <div className="max-w-sm space-y-3">
                    <p className="font-medium text-ink-900">Genie is taking longer than usual.</p>
                    <p className="text-sm text-ink-600">Check your internet connection, then try again.</p>
                    <Button variant="primary" icon={<RefreshCw className="h-4 w-4" />} onClick={reload}>Try again</Button>
                  </div>
                )}
              </div>
            )}
          </div>

        </div>
      )}
      <p className="mt-4 flex items-start gap-1.5 text-xs text-ink-500"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />Answers come from HeatGuard's data and can occasionally be wrong — double-check anything important on My plan.</p>
    </>
  );
}
