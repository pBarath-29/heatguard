export type Band = "Low" | "Moderate" | "High";

export interface CheckinRow {
  rank: number;
  subzone_name: string;
  planning_area: string;
  ura_region: string;
  risk_score: number;
  main_driver: "heat" | "haze" | "vulnerability" | "access";
  reason: string;
  action: string;
  heat_wbgt_c: number | null;
  heat_band: Band | null;
  high_alert: boolean;
  action_band: Band | null;
  heat_is_forecast: boolean;
  heat_basis: string;
  for_date: string | null;
  prob_moderate_plus: number | null;
  prob_high: number | null;
  wbgt_latest_c: number | null;
  latest_reading_ts: string | null;
  wbgt_afternoon_peak_c: number | null;
  peak_date_sgt: string | null;
  psi_twenty_four_hourly: number | null;
  psi_band: string | null;
  pm25_one_hourly: number | null;
  pop_total: number;
  pop_65_plus: number;
  pct_65_plus: number;
  pop_75_plus: number;
  pct_75_plus: number;
  pct_1_2_room: number | null;
  pa_pct_one_person: number;
  pa_pct_difficulty: number;
  pa_data_published: boolean;
  vulnerability_score: number;
  nearest_cool_space: string;
  nearest_cool_space_type: string;
  nearest_cool_space_street: string | null;
  nearest_cool_space_postal: string | null;
  cool_space_km: number;
  cool_spaces_within_1km: number;
  nearest_wbgt_station: string;
  nearest_wbgt_station_km: number;
  haze_region: string;
  heat_component: number | null;
  haze_component: number | null;
  vulnerability_component: number | null;
  access_component: number | null;
  centroid_latitude: number;
  centroid_longitude: number;
}

export interface CheckinResponse {
  meta: { for_date: string | null; today: string; status: "tomorrow" | "today" | "past" | "observed" | "empty"; heat_basis: string; is_forecast: boolean; areas: number };
  rows: CheckinRow[];
}

export interface StationWeight { station_id: string; station_name: string; station_rank: number; distance_km: number; weight: number }
export interface StationPeak { station_id: string; station_name: string; date_sgt: string; afternoon_peak_wbgt_c: number }
export interface StationForecast { station_id: string; station_name: string; target_date: string; predicted_peak_wbgt_c: number; prob_high: number }
export interface ScoreWeight { score: string; component: string; weight: number; description: string }
export interface AreaResponse { row: CheckinRow; total_areas: number; stations: StationWeight[]; peaks: StationPeak[]; forecasts: StationForecast[]; weights: ScoreWeight[] }

export interface StationLatest {
  station_id: string; station_name: string; town_center: string; latitude: number; longitude: number;
  latest_reading_ts: string; latest_time_sgt: string; wbgt_c: number; heat_band: Band; peak_so_far_today_c: number; peak_so_far_band: Band;
}
export interface HazeLatest { region: string; time_sgt: string; psi_twenty_four_hourly: number; pm25_twenty_four_hourly: number | null; psi_band: string; pm25_one_hourly: number | null }
export interface DailySummary {
  date_sgt: string; stations_reporting: number; hottest_peak_wbgt_c: number; avg_peak_wbgt_c: number;
  stations_moderate_or_high: number; stations_high: number; worst_psi_24h: number; avg_psi_24h: number; hottest_band: Band; worst_psi_band: string;
}
export interface NowResponse { latest_reading_ts: string | null; stations: StationLatest[]; haze: HazeLatest[]; daily: DailySummary[] }

export interface Evaluation {
  model: string; mae: number; rmse: number; within_1c: number; band_accuracy: number; high_recall: number | null; high_precision: number | null;
  moderate_plus_recall: number; station_days: number; model_version: string; alert_threshold: number; improvement_vs_best_baseline: number; test_period: string;
}
export interface AccuracyResponse {
  evaluation: Evaluation[];
  backtest: { target_date: string; actual: number; heatguard: number; baseline: number; baseline_name: string }[];
  importance: { feature: string; mae_increase_c: number }[];
  track_record: { target_date: string; stations: number; avg_error_c: number; band_correct: number; stations_high: number; high_caught: number }[];
}
export interface AboutResponse { weights: ScoreWeight[]; rulebook: { trigger: string; level: string; action: string }[] }
export interface CoolSpace { name: string; space_type: string; latitude: number; longitude: number; street: string | null; postal_code: string | null }

export interface GenieTable { columns: string[]; rows: (string | number | null)[][] }
export interface GenieAnswer { conversation_id: string; text: string[]; queries: { description: string | null; sql: string | null; table: GenieTable | null }[]; suggestions: string[] }
export interface MessageOptions { languages: string[]; audiences: { id: string; label: string }[] }

export class ApiError extends Error {
  status: number;
  detail?: string;
  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    throw new ApiError("Can't reach HeatGuard. Check your internet connection and try again.", 0);
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    if (res.status === 401 || res.status === 403 || res.redirected) {
      throw new ApiError("Your Databricks sign-in has expired. Reload the page to sign in again.", res.status);
    }
  }
  if (!res.ok) {
    const b = (body ?? {}) as { error?: string; detail?: unknown };
    const message = b.error ?? (typeof b.detail === "string" ? b.detail : "Something went wrong. Please try again.");
    throw new ApiError(message, res.status, typeof b.detail === "string" && b.error ? b.detail : undefined);
  }
  if (body === null) throw new ApiError("HeatGuard sent an unexpected reply. Reload the page and try again.", res.status);
  return body as T;
}

export const api = {
  checkin: () => request<CheckinResponse>("/api/checkin"),
  area: (name: string) => request<AreaResponse>(`/api/area/${encodeURIComponent(name)}`),
  now: () => request<NowResponse>("/api/now"),
  accuracy: () => request<AccuracyResponse>("/api/accuracy"),
  about: () => request<AboutResponse>("/api/about"),
  coolSpaces: () => request<CoolSpace[]>("/api/cool-spaces"),
  messageOptions: () => request<MessageOptions>("/api/message/options"),
  message: (subzone: string, language: string, audience: string) =>
    request<{ text: string; used_ai: boolean }>("/api/message", { method: "POST", body: JSON.stringify({ subzone, language, audience }) }),
  genie: (question: string, conversation_id?: string | null) =>
    request<GenieAnswer>("/api/genie", { method: "POST", body: JSON.stringify({ question, conversation_id: conversation_id ?? null }) }),
  refresh: () => request<{ ok: boolean }>("/api/refresh", { method: "POST" }),
};
