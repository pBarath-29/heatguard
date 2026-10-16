import clsx from "clsx";
import { ClipboardList, MessagesSquare, ShieldCheck } from "lucide-react";
import { useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const NAV = [
  { to: "/", label: "My plan", icon: ClipboardList, end: true },
  { to: "/ask", label: "Ask a question", icon: MessagesSquare },
];

export default function Layout() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-ink-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2.5">
            <img src="/favicon.svg" alt="" className="h-9 w-9 rounded-xl shadow-sm" />
            <span className="text-[17px] font-semibold text-ink-900">HeatGuard</span>
          </NavLink>
          <nav className="flex gap-1">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) => clsx("inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition",
                  isActive ? "bg-brand-50 text-brand-800" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900")}>
                <Icon className="h-[18px] w-[18px]" /><span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <div className="mx-auto max-w-3xl px-4 py-6 md:py-8 animate-fade-in" key={pathname}><Outlet /></div>
      </main>
      <footer className="border-t border-ink-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-ink-500">
          <span className="flex items-center gap-1.5"><ShieldCheck className="h-4 w-4" /> No personal information — area-level public data only.</span>
          <span>Updated every evening at about 7 pm, using NEA weather data.</span>
        </div>
      </footer>
    </div>
  );
}
