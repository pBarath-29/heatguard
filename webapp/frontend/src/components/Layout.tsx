import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Activity, BadgeCheck, BarChart3, BookOpen, Building2, ClipboardList, Menu, MessagesSquare, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import { dayLabel } from "../lib/format";

const NAV = [
  { group: "Plan", items: [
    { to: "/", label: "Today's plan", icon: ClipboardList, end: true },
    { to: "/my-centre", label: "My centre", icon: Building2 },
    { to: "/now", label: "Heat & haze now", icon: Activity },
  ] },
  { group: "Explore", items: [
    { to: "/proof", label: "Proof: replay a hot day", icon: BadgeCheck },
    { to: "/ask", label: "Ask HeatGuard", icon: MessagesSquare },
    { to: "/accuracy", label: "Forecast accuracy", icon: BarChart3 },
    { to: "/about", label: "About & help", icon: BookOpen },
  ] },
];

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className="h-9 w-9 rounded-xl shadow-sm" />
      <div>
        <div className="text-[15px] font-semibold leading-tight text-ink-900">HeatGuard</div>
        <div className="text-[11px] leading-tight text-ink-500">Heat-risk check-ins</div>
      </div>
    </div>
  );
}

function StatusCard() {
  const { data } = useQuery({ queryKey: ["checkin"], queryFn: api.checkin });
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const meta = data?.meta;
  const tone = !meta ? "bg-ink-300" : meta.status === "tomorrow" ? "bg-emerald-500" : meta.status === "today" ? "bg-sky-500" : "bg-amber-500";
  const text = !meta ? "Loading status…" : meta.status === "tomorrow" ? `List ready for ${dayLabel(meta.for_date)}` :
    meta.status === "today" ? `Showing today's list (${dayLabel(meta.for_date)})` : meta.status === "past" ? `List is out of date (${dayLabel(meta.for_date)})` :
    meta.status === "observed" ? "Forecast not ready yet" : "No list yet";
  const refresh = async () => {
    setBusy(true);
    try { await api.refresh(); } catch { /* the queries below still refetch */ }
    await qc.invalidateQueries();
    setBusy(false);
  };
  return (
    <div className="rounded-2xl border border-ink-200 bg-ink-50 p-3.5">
      <div className="flex items-center gap-2 text-[13px] font-medium text-ink-800">
        <span className="relative flex h-2 w-2"><span className={clsx("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", tone)} /><span className={clsx("relative inline-flex h-2 w-2 rounded-full", tone)} /></span>
        {text}
      </div>
      <p className="mt-1 text-xs text-ink-500">Updated every evening at about 7 pm (SGT).</p>
      <button onClick={refresh} disabled={busy} className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-medium text-brand-700 hover:text-brand-800 disabled:opacity-60">
        <RefreshCw className={clsx("h-3.5 w-3.5", busy && "animate-spin")} /> Refresh data
      </button>
    </div>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="space-y-6">
      {NAV.map((g) => (
        <div key={g.group}>
          <div className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-400">{g.group}</div>
          <div className="space-y-0.5">
            {g.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} onClick={onNavigate}
                className={({ isActive }) => clsx(
                  "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
                  isActive ? "bg-brand-50 text-brand-800" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900",
                )}>
                {({ isActive }) => (<><Icon className={clsx("h-[18px] w-[18px]", isActive ? "text-brand-600" : "text-ink-400 group-hover:text-ink-600")} />{label}</>)}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="px-1 pt-1"><Logo /></div>
      <NavItems onNavigate={onNavigate} />
      <div className="mt-auto space-y-3">
        <StatusCard />
        <div className="flex items-center gap-1.5 px-1 text-[11px] text-ink-400"><ShieldCheck className="h-3.5 w-3.5" /> Area-level open data only. No personal data.</div>
      </div>
    </div>
  );
}

export default function Layout(): ReactNode {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-ink-200 bg-white lg:block"><SidebarBody /></aside>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button onClick={() => setOpen(true)} className="rounded-lg p-2 text-ink-600 hover:bg-ink-100" aria-label="Open menu"><Menu className="h-5 w-5" /></button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-white shadow-xl animate-fade-in">
            <button onClick={() => setOpen(false)} className="absolute right-3 top-3 rounded-lg p-2 text-ink-500 hover:bg-ink-100" aria-label="Close menu"><X className="h-5 w-5" /></button>
            <SidebarBody onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <main className="lg:pl-64">
        <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8 md:py-8 animate-fade-in" key={pathname}><Outlet /></div>
      </main>
    </div>
  );
}
