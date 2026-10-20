export type Band = "Low" | "Moderate" | "High";

export type Tier = "Start here" | "Check in" | "Routine";

export interface CheckinRow {
  rank: number;
  tier: Tier;
  hazard: number;
  exposure: number;
  exposure_pctl: number;
  heat_hazard: number;
  haze_hazard: number;
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
  haze_component: number | null;
  access_component: number | null;
  centroid_latitude: number;
  centroid_longitude: number;
}

export interface DayOutlook {
  for_date: string; level: "High heat possible" | "Moderate heat" | "Low heat"; headline: string; top_areas: string;
  start_here_areas: number; start_here_seniors: number; check_in_areas: number; check_in_seniors: number; routine_areas: number;
  high_alert_areas: number; moderate_areas: number; max_prob_high: number | null; hottest_heat_c: number | null;
  worst_psi: number | null; worst_psi_band: string | null; total_areas: number; total_seniors: number;
}

export interface CheckinResponse {
  meta: { for_date: string | null; today: string; status: "tomorrow" | "today" | "past" | "observed" | "empty"; heat_basis: string; is_forecast: boolean; areas: number };
  outlook: DayOutlook | null;
  rows: CheckinRow[];
}

export interface ReplayDay {
  target_date: string; areas: number; start_here_areas: number; start_here_seniors: number; checkin_areas: number;
  high_areas: number; high_seniors: number; start_here_hits: number; start_here_seniors_hit: number; census_top10_hits: number;
  high_areas_flagged: number; hottest_actual_c: number | null; share_high_areas_flagged: number | null;
}
export interface ReplaySummary {
  days: ReplayDay[];
  totals: { days: number; days_with_high: number; start_here_hits: number; census_top10_hits: number; start_here_areas: number; high_area_days: number };
}
export interface ReplayRow {
  target_date: string; rank: number; census_rank: number; tier: Tier; subzone_name: string; planning_area: string; pop_65_plus: number;
  risk_score: number; hazard: number; exposure: number; heat_wbgt_c: number; heat_band: Band; prob_high: number; high_alert: boolean;
  actual_peak_nearest_c: number | null; actual_band_nearest: Band | null; actually_high: boolean; centroid_latitude: number; centroid_longitude: number;
}
export interface NearResponse {
  place: { name: string; address: string; postal: string; latitude: number; longitude: number };
  point: { target_date: string; heat_wbgt_c: number; prob_moderate_plus: number; prob_high: number; high_alert: boolean; stations: { name: string; distance_km: number }[] } | null;
  areas: (CheckinRow & { distance_km: number })[];
  cool_spaces: (CoolSpace & { distance_km: number })[];
  plan: CentrePlan;
}
export interface CentrePlan {
  for_date: string | null; level: "very_hot" | "hot" | "normal"; title: string; subtitle: string;
  haze: { band: string; text: string } | null; safety: string | null;
  todo: { id: string; when: string; text: string; why: string | null; action: { label: string; to: string } | null }[];
  focus_areas: string[]; message_area: string | null;
}

export interface StationWeight { station_id: string; station_name: string; station_rank: number; distance_km: number; weight: number }
export interface StationPeak { station_id: string; station_name: string; date_sgt: string; afternoon_peak_wbgt_c: number }
export interface StationForecast { station_id: string; station_name: string; target_date: string; predicted_peak_wbgt_c: number; prob_high: number }
export interface ScoreWeight { score: string; component: string; weight: number; description: string }
export interface AreaResponse { row: CheckinRow }

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
  area: (name: string) => request<AreaResponse>(`/api/area/${encodeURIComponent(name)}`),
  genie: (question: string, conversation_id?: string | null) =>
    request<GenieAnswer>("/api/genie", { method: "POST", body: JSON.stringify({ question, conversation_id: conversation_id ?? null }) }),
  near: (postal: string) => request<NearResponse>(`/api/near?postal=${encodeURIComponent(postal)}`),
};

// ---------------------------------------------------------------- coordinator features
export interface Place { name: string; address: string; postal: string | null; latitude: number; longitude: number }
export interface PointForecast {
  date: string; peak_c: number; band: Band; prob_high: number; prob_moderate_plus: number; hourly: Record<string, number>;
  made_on: string; model_version: string; scored_at: string | null; stations: { name: string; distance_km: number }[];
}
export interface NeaPeriod { start: string; end: string | null; label: string; forecast: string }
export interface WeatherResponse {
  today: {
    date: string;
    now: { wbgt: { value_c: number; band: Band; station: string; distance_km: number; time: string } | null;
           air_temp: { value: number; station: string; distance_km: number; time: string } | null;
           humidity: { value: number; station: string; distance_km: number; time: string } | null };
    two_hour: { area: string; forecast: string; distance_km: number; valid_text: string; issued: string } | null;
    observed_by_hour: { station: string; distance_km: number; by_hour: Record<string, number> } | null;
    forecast: PointForecast | null; nea_periods: NeaPeriod[];
  };
  tomorrow: { date: string; forecast: PointForecast | null; nea_periods: NeaPeriod[] };
  nea_24h: { region: string; issued: string; temp_low_c: number; temp_high_c: number; overall: string; valid_text: string } | null;
  notes: string[]; fetched_at: string; sources: string[];
}
export interface ActivityInput { activity: string; exertion: "light" | "moderate" | "vigorous"; latitude: number; longitude: number; place?: string;
  day: "today" | "tomorrow"; start: string; duration_min: number; older_adults: boolean }
export interface CoolPlace { name: string; type: string; latitude: number; longitude: number; address: string; straight_km: number; walk_min_estimate: number;
  opening_hours: string | null; accessibility: string | null; directions_url: string }
export interface ActivityResult {
  status: "Lower risk" | "Caution" | "High risk" | "Insufficient data"; activity: string; place: string | null; date: string; start: string; end: string;
  duration_min: number; exertion: string; older_adults: boolean; reasons: string[]; precautions: string[];
  window?: { hours: number[]; max_c: number; band: Band }; alternatives: { start: string; end: string; status: string; window_max_c: number }[];
  shorter?: { duration_min: number; status: string } | null; indoor_options: CoolPlace[];
  warm_nights?: { streak: number; station: string; text: string } | null; nea_periods: NeaPeriod[];
  forecast: PointForecast | null; uncertainty?: string; sources: string[]; disclaimer: string; nea_note?: string | null;
}
export interface WelfareEvent { action: string; outcome: string | null; remark: string | null; by_email: string; at: string }
export interface Resident {
  resident_id: string; name: string; block: string; street: string; unit: string; postal: string; phone: string; notes: string; demo: boolean;
  state: { completed: boolean; outcome: string | null; follow_up: boolean; version: number; updated_at: string | null; updated_by: string | null;
           status: "pending" | "completed" | "follow_up" | "unsuccessful" };
  history: WelfareEvent[];
}

export type Lang = "en" | "zh" | "ms" | "ta";
export interface ComposeInput { level: "very_hot" | "hot" | "normal"; for_date: string; language: Lang; centre: string; cool: string | null; haze: boolean }
export interface TelegramChat { chat_id: string; title: string; chat_type: string; linked_by?: string; linked_at?: string }
export interface TelegramStatus { configured: boolean; bot: { username: string; name: string } | null; bot_error: string | null; chats: TelegramChat[]; can_manage: boolean }

export const features = {
  locate: (q: string) => request<{ results: Place[] }>(`/api/locate?q=${encodeURIComponent(q)}`),
  weather: (lat: number, lon: number) => request<WeatherResponse>(`/api/weather?lat=${lat}&lon=${lon}`),
  activity: (body: ActivityInput) => request<ActivityResult>("/api/activity-check", { method: "POST", body: JSON.stringify(body) }),
  coolPlaces: (lat: number, lon: number) => request<{ places: CoolPlace[]; heat_now: { value_c: number; band: Band; station: string } | null; coverage: string; source: string }>(`/api/cool-places?lat=${lat}&lon=${lon}`),
  me: () => request<{ signed_in: boolean; role: string | null; can_view_welfare: boolean }>("/api/me"),
  welfare: () => request<{ residents: Resident[]; demo: boolean; notice: string }>("/api/welfare"),
  compose: (body: ComposeInput) => request<{ text: string; language: string }>("/api/message/compose", { method: "POST", body: JSON.stringify(body) }),
  telegram: () => request<TelegramStatus>("/api/telegram"),
  telegramDiscover: () => request<{ chats: (TelegramChat & { linked: boolean })[] }>("/api/telegram/discover", { method: "POST" }),
  telegramLink: (chat_id: string) => request<{ chats: TelegramChat[] }>("/api/telegram/chats", { method: "POST", body: JSON.stringify({ chat_id }) }),
  telegramUnlink: (chat_id: string) => request<{ chats: TelegramChat[] }>(`/api/telegram/chats/${encodeURIComponent(chat_id)}`, { method: "DELETE" }),
  telegramSend: (body: { chat_ids: string[]; text: string; audience?: string; language?: string; client_send_id: string }) =>
    request<{ results: { chat_id: string; title: string | null; ok: boolean; error?: string | null; already_sent?: boolean }[]; sent: number }>("/api/telegram/send", { method: "POST", body: JSON.stringify(body) }),
  welfareEvent: (id: string, body: { action: string; outcome?: string | null; remark?: string | null; expected_version: number; client_event_id: string }) =>
    request<{ state: Resident["state"]; history?: WelfareEvent[]; duplicate?: boolean }>(`/api/welfare/${encodeURIComponent(id)}/events`, { method: "POST", body: JSON.stringify(body) }),
};
