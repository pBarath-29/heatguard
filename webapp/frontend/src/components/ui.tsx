import clsx from "clsx";
import { AlertTriangle, ChevronDown, Info, Loader2, RefreshCw, SearchX } from "lucide-react";
import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { ApiError, type Band } from "../lib/api";
import { BAND, PSI } from "../lib/theme";

export function Card({ className, children, padded = true }: { className?: string; children: ReactNode; padded?: boolean }) {
  return <div className={clsx("rounded-2xl border border-ink-200/80 bg-white shadow-card", padded && "p-5", className)}>{children}</div>;
}

export function CardTitle({ icon, title, subtitle, right }: { icon?: ReactNode; title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="flex items-start gap-2.5">
        {icon && <div className="mt-0.5 text-ink-400">{icon}</div>}
        <div>
          <h3 className="text-[15px] font-semibold text-ink-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-sm text-ink-500">{subtitle}</p>}
        </div>
      </div>
      {right}
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, right }: { eyebrow?: ReactNode; title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow && <div className="mb-2">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900 md:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-[15px] text-ink-500">{subtitle}</p>}
      </div>
      {right && <div className="flex shrink-0 flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost"; size?: "sm" | "md"; icon?: ReactNode; loading?: boolean };
export function Button({ variant = "secondary", size = "md", icon, loading, className, children, disabled, ...rest }: BtnProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-xl font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-brand-600 text-white shadow-sm hover:bg-brand-700",
        variant === "secondary" && "border border-ink-200 bg-white text-ink-700 shadow-sm hover:border-ink-300 hover:bg-ink-50",
        variant === "ghost" && "text-ink-600 hover:bg-ink-100 hover:text-ink-900",
        className,
      )}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function Badge({ children, className, dot }: { children: ReactNode; className?: string; dot?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", className ?? "bg-ink-100 text-ink-700 ring-ink-500/10")}>
      {dot && <span className={clsx("h-1.5 w-1.5 rounded-full", dot)} />}
      {children}
    </span>
  );
}

export function BandBadge({ band, prefix = "" }: { band: Band | null | undefined; prefix?: string }) {
  if (!band) return <Badge>{prefix}No data</Badge>;
  const b = BAND[band];
  return <Badge className={clsx(b.bg, b.text, b.ring)} dot={b.dot}>{prefix}{b.label}</Badge>;
}

export function PsiBadge({ band, value }: { band: string | null | undefined; value?: number | null }) {
  if (!band) return null;
  const p = PSI[band] ?? { text: "text-ink-700", bg: "bg-ink-100", ring: "ring-ink-500/10" };
  return <Badge className={clsx(p.bg, p.text, p.ring)}>Haze: {band}{value != null ? ` · PSI ${Math.round(value)}` : ""}</Badge>;
}

export function Stat({ label, value, sub, tone = "text-ink-900", icon, hint }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string; icon?: ReactNode; hint?: string }) {
  return (
    <Card className="relative overflow-hidden">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-ink-500">{label}</span>
        <span className="flex items-center gap-1.5 text-ink-300">
          {hint && <span title={hint} className="cursor-help"><Info className="h-3.5 w-3.5" /></span>}
          {icon}
        </span>
      </div>
      <div className={clsx("mt-2 font-semibold leading-tight tracking-tight", typeof value === "string" && value.length > 8 ? "text-xl md:text-2xl" : "text-[28px] leading-none", tone)}>{value}</div>
      {sub && <div className="mt-2 text-[13px] text-ink-500">{sub}</div>}
    </Card>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("relative overflow-hidden rounded-lg bg-ink-100", className)}><div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent" /></div>;
}

export function PageSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <div className="space-y-2"><Skeleton className="h-8 w-72" /><Skeleton className="h-4 w-96 max-w-full" /></div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}</div>
      <div className="space-y-3">{Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-36 rounded-2xl" />)}</div>
      <p className="text-center text-sm text-ink-400">Loading… the first load of the day can take up to 30 seconds while the data warehouse wakes up.</p>
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "Couldn't load this page" }: { error: unknown; onRetry?: () => void; title?: string }) {
  const [open, setOpen] = useState(false);
  const message = error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
  const detail = error instanceof ApiError ? error.detail : error instanceof Error ? error.message : undefined;
  return (
    <Card className="mx-auto max-w-xl text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-600"><AlertTriangle className="h-6 w-6" /></div>
      <h3 className="text-base font-semibold text-ink-900">{title}</h3>
      <p className="mt-1.5 text-sm text-ink-600">{message}</p>
      {onRetry && <Button variant="primary" className="mt-4" icon={<RefreshCw className="h-4 w-4" />} onClick={onRetry}>Try again</Button>}
      {detail && (
        <div className="mt-4 text-left">
          <button onClick={() => setOpen(!open)} className="inline-flex items-center gap-1 text-xs font-medium text-ink-400 hover:text-ink-600">
            <ChevronDown className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} /> Technical details (for the HeatGuard team)
          </button>
          {open && <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-ink-900 p-3 text-[11px] leading-relaxed text-ink-100">{detail}</pre>}
        </div>
      )}
    </Card>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-ink-200 bg-white/60 px-6 py-12 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-ink-100 text-ink-400"><SearchX className="h-5 w-5" /></div>
      <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
      {body && <p className="mt-1 max-w-sm text-sm text-ink-500">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Banner({ tone, icon, children }: { tone: "info" | "success" | "warning"; icon?: ReactNode; children: ReactNode }) {
  const styles = {
    info: "border-sky-200 bg-sky-50 text-sky-900",
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
  }[tone];
  return <div className={clsx("flex items-start gap-3 rounded-xl border px-4 py-3 text-sm", styles)}>{icon && <span className="mt-0.5 shrink-0">{icon}</span>}<div>{children}</div></div>;
}

export function Segmented<T extends string>({ options, value, onChange, size = "md" }: { options: { value: T; label: ReactNode }[]; value: T; onChange: (v: T) => void; size?: "sm" | "md" }) {
  return (
    <div className="inline-flex rounded-xl bg-ink-100 p-1" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-lg font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
            size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-[13px]",
            value === o.value ? "bg-white text-ink-900 shadow-sm" : "text-ink-500 hover:text-ink-800",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function ScoreRing({ score, color, size = 64, label = "risk" }: { score: number; color: string; size?: number; label?: string }) {
  const r = size / 2 - 5, c = 2 * Math.PI * r, frac = Math.max(0, Math.min(1, score / 100));
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={`Risk score ${Math.round(score)} out of 100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#F1F5F9" strokeWidth={6} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={6} strokeLinecap="round" strokeDasharray={`${c * frac} ${c}`} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-semibold leading-none text-ink-900">{Math.round(score)}</span>
        <span className="mt-0.5 text-[9px] font-medium uppercase tracking-wider text-ink-400">{label}</span>
      </div>
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center gap-1 text-[13px] font-medium text-ink-600">{label}{hint && <span title={hint} className="cursor-help text-ink-300"><Info className="h-3.5 w-3.5" /></span>}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "h-10 w-full rounded-xl border border-ink-200 bg-white px-3 text-sm text-ink-900 shadow-sm placeholder:text-ink-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
