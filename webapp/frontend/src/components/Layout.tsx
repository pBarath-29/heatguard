import clsx from "clsx";
import { Building2, ClipboardCheck, ClipboardList, CloudSun, MessagesSquare, ShieldCheck, Snowflake, Users } from "lucide-react";
import { useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const NAV = [
  { to: "/", label: "My plan", icon: ClipboardList, end: true },
  { to: "/weather", label: "Weather", icon: CloudSun },
  { to: "/activity", label: "Activity check", icon: ClipboardCheck },
  { to: "/blocks", label: "Block Radar", icon: Building2 },
  { to: "/cool-places", label: "Cool places", icon: Snowflake },
  { to: "/welfare", label: "Welfare checks", icon: Users },
  { to: "/ask", label: "Ask", icon: MessagesSquare },
];
const WIDE = ["/blocks", "/cool-places"];

export default function Layout() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  const width = WIDE.some((p) => pathname.startsWith(p)) ? "max-w-6xl" : "max-w-3xl";
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-ink-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 pt-3 lg:pb-3">
          <NavLink to="/" className="flex shrink-0 items-center gap-2.5">
            <img src="/favicon.svg" alt="" className="h-9 w-9 rounded-xl shadow-sm" />
            <span className="text-[17px] font-semibold text-ink-900">HeatGuard</span>
          </NavLink>
          <nav className="ml-auto hidden gap-1 lg:flex" aria-label="Main">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) => clsx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-xl px-2.5 py-2 text-sm font-medium transition",
                  isActive ? "bg-brand-50 text-brand-800" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900")}>
                <Icon className="h-[18px] w-[18px]" />{label}
              </NavLink>
            ))}
          </nav>
        </div>
        <nav className="no-scrollbar mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 py-2 lg:hidden" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => clsx("inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition",
                isActive ? "bg-brand-50 text-brand-800" : "text-ink-600 hover:bg-ink-100")}>
              <Icon className="h-4 w-4" />{label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1">
        <div className={clsx("mx-auto px-4 py-6 md:py-8 animate-fade-in", width)} key={pathname}><Outlet /></div>
      </main>
      <footer className="border-t border-ink-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-ink-500">
          <span className="flex items-center gap-1.5"><ShieldCheck className="h-4 w-4" /> No real personal information — public data only; welfare checks use fictional demo residents.</span>
          <span>Forecast updated every evening at about 7 pm, using NEA weather data.</span>
        </div>
      </footer>
    </div>
  );
}
