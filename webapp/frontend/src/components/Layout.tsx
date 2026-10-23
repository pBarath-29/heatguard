import clsx from "clsx";
import { ClipboardCheck, ClipboardList, CloudSun, MessagesSquare, Monitor, Moon, Settings, ShieldCheck, Snowflake, Sun, Users } from "lucide-react";
import { useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useThemeMode, type ThemeMode } from "../lib/themeMode";

const NAV = [
  { to: "/", label: "My plan", short: "Plan", icon: ClipboardList, end: true },
  { to: "/weather", label: "Weather", short: "Weather", icon: CloudSun },
  { to: "/activity", label: "Activity check", short: "Activity", icon: ClipboardCheck },
  { to: "/cool-places", label: "Cool places", short: "Cooling", icon: Snowflake },
  { to: "/welfare", label: "Welfare checks", short: "Welfare", icon: Users },
  { to: "/ask", label: "Ask", short: "Ask", icon: MessagesSquare },
];
const WIDE = ["/cool-places"];
const NEXT: Record<ThemeMode, ThemeMode> = { system: "light", light: "dark", dark: "system" };
const THEME_ICON = { system: Monitor, light: Sun, dark: Moon };
const THEME_LABEL = { system: "Theme: same as device", light: "Theme: light", dark: "Theme: dark" };

export default function Layout() {
  const { pathname } = useLocation();
  const [mode, setMode] = useThemeMode();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  const width = WIDE.some((p) => pathname.startsWith(p)) ? "max-w-6xl" : "max-w-3xl";
  const ThemeIcon = THEME_ICON[mode];
  const iconBtn = "inline-flex h-10 w-10 items-center justify-center rounded-xl text-ink-600 transition hover:bg-ink-100 hover:text-ink-900";

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-ink-200/80 bg-surface/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2.5">
          <NavLink to="/" className="mr-2 flex shrink-0 items-center gap-2.5">
            <img src="/favicon.svg" alt="" className="h-9 w-9 rounded-xl shadow-sm" />
            <span className="text-[17px] font-semibold tracking-tight text-ink-900">HeatGuard</span>
          </NavLink>
          <nav className="hidden flex-1 justify-center gap-0.5 lg:flex" aria-label="Main">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) => clsx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition",
                  isActive ? "bg-brand-50 text-brand-800" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900")}>
                <Icon className="h-[18px] w-[18px]" />{label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1 lg:ml-0">
            <button type="button" className={iconBtn} onClick={() => setMode(NEXT[mode])} aria-label={`${THEME_LABEL[mode]}. Change theme`} title={THEME_LABEL[mode]}>
              <ThemeIcon className="h-5 w-5" />
            </button>
            <NavLink to="/settings" aria-label="Settings" title="Settings"
              className={({ isActive }) => clsx(iconBtn, isActive && "bg-brand-50 text-brand-800")}><Settings className="h-5 w-5" /></NavLink>
          </div>
        </div>
      </header>

      <main className="flex-1 pb-24 lg:pb-0">
        <div className={clsx("mx-auto px-4 py-5 md:py-8 animate-fade-in", width)} key={pathname}><Outlet /></div>
      </main>

      <footer className="hidden border-t border-ink-200 bg-surface lg:block">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-ink-500">
          <span className="flex items-center gap-1.5"><ShieldCheck className="h-4 w-4" /> No real personal information — public data only; welfare checks use fictional demo residents.</span>
          <span>Forecast updated every afternoon at about 4 pm, using NEA weather data.</span>
        </div>
      </footer>

      {/* Phones and tablets: thumb-reachable tab bar */}
      <nav className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-ink-200 bg-surface/95 backdrop-blur-md lg:hidden" aria-label="Main">
        <div className="mx-auto grid max-w-xl grid-cols-6">
          {NAV.map(({ to, short, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => clsx("flex min-h-[60px] flex-col items-center justify-center gap-1 px-0.5 text-[11px] font-medium leading-tight transition",
                isActive ? "text-brand-700" : "text-ink-500 active:text-ink-900")}>
              {({ isActive }) => (<>
                <span className={clsx("flex h-7 w-12 items-center justify-center rounded-full transition", isActive && "bg-brand-50")}><Icon className="h-[20px] w-[20px]" /></span>
                <span className="w-full truncate text-center">{short}</span>
              </>)}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
