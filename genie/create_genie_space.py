"""Create (or update) the HeatGuard Genie space.

Usage (from the repo root, with the Databricks CLI profile `heatguard`):
    python genie/create_genie_space.py            # creates the space and prints its id
    python genie/create_genie_space.py <space_id> # updates an existing space in place

The space lets coordinators ask questions about the check-in list, heat, haze, cool spaces and forecast accuracy in plain English.
"""
import json, os, subprocess, sys, uuid

PROFILE = "heatguard"
WAREHOUSE_ID = "e4c9f81b068eb070"
S = "workspace.heatguard"
TITLE = "HeatGuard: ask about heat risk"
DESCRIPTION = ("Ask questions in plain English about tomorrow's heat-risk check-in list, current heat and haze, cool spaces near seniors, "
               "and how accurate HeatGuard's forecast has been. Area-level data only (no personal data).")

TABLES = sorted(f"{S}.{t}" for t in [
    "gold_checkin_list", "gold_subzone_profile", "gold_daily_summary", "gold_wbgt_station_latest", "gold_haze_latest",
    "gold_score_weights", "gold_rulebook", "silver_cool_spaces", "silver_wbgt_daily_peak",
    "gold_day_outlook", "gold_replay_summary", "gold_replay_list",
    "ml_wbgt_forecast", "ml_model_evaluation", "ml_forecast_track_record",
])

INSTRUCTIONS = f"""* HeatGuard helps Active Ageing Centre coordinators decide which areas to check on before hot afternoons. Answer in plain, friendly English for a non-technical reader.
* The people asking are coordinators, not analysts. Never mention SQL, tables, columns, models, scores, WBGT or PSI numbers unless they ask. Say "check first" for tier 'Start here', "phone check-in" for 'Check in', and "routine" for 'Routine'. Describe heat exactly by heat_band: 'High' = "very hot afternoon", 'Moderate' = "hot afternoon", 'Low' = "normal afternoon" (high_alert = true adds "could become very hot"); describe haze by psi_band in lower case (e.g. "unhealthy"). Write area names in normal capitalisation (e.g. Telok Blangah Rise). Keep answers short: one or two sentences plus the list.
* Areas: a subzone (e.g. TELOK BLANGAH RISE) sits inside a planning area (e.g. BUKIT MERAH). Names are stored in UPPER CASE; match user input case-insensitively (use upper() or ILIKE).
* "Seniors" means residents aged 65 and over (pop_65_plus, pct_65_plus) from Census 2020.
* Heat is measured as WBGT (Wet Bulb Globe Temperature, deg C). NEA heat-stress bands: Low below 31, Moderate 31 to 32.9, High 33 and above.
* Haze is the 24-hour PSI: Good up to 50, Moderate 51-100, Unhealthy 101-200, Very unhealthy 201-300, Hazardous above 300.
* For "tomorrow", "today's list", "which areas first", "priority" questions use {S}.gold_checkin_list: rank 1 is the highest priority; for_date is the day the list is for; heat_basis says whether heat is a forecast or observed; high_alert = true means the model gives a meaningful chance of High heat (prob_high).
* tier: 'Start here' = the 10 highest-risk areas where Moderate or High heat is forecast (reach these first); 'Check in' = other highly exposed areas with Moderate-or-worse heat (phone check-in); 'Routine' = everything else.
* risk_score (0-100) = 100 x hazard x exposure. hazard (0-1) = how dangerous the day is (0.5 x chance of Moderate-or-higher heat + 0.5 x chance of High heat, full at 50%, plus up to 0.3 for haze). exposure (0-1) = 0.7 x vulnerability_score + 0.3 x distance to the nearest cool space. Weights are in {S}.gold_score_weights.
* For a one-line summary of the day ("what's the outlook", "how many seniors to reach") use {S}.gold_day_outlook (level, headline, start_here_areas, start_here_seniors).
* For "would HeatGuard have helped", "proof", "past hot days" use {S}.gold_replay_summary (one row per test-period day: start_here_hits = HeatGuard top-10 areas that actually hit High; census_top10_hits = the same for a Census-only top 10; high_areas = areas that hit High) and {S}.gold_replay_list (per area per day).
* Cool spaces are Community Clubs and public libraries ({S}.silver_cool_spaces). cool_space_km is straight-line distance from the subzone centre.
* Current conditions: {S}.gold_wbgt_station_latest (latest WBGT per station) and {S}.gold_haze_latest (latest PSI per region).
* History: {S}.gold_daily_summary has one row per day (hottest station peak, stations reaching Moderate/High, worst PSI). A "High heat day" is a day with stations_high > 0.
* Forecast accuracy: {S}.ml_model_evaluation (test-period scores vs simple baselines) and {S}.ml_forecast_track_record (each live forecast vs what happened).
* Census planning-area rates (one-person households, daily-activity difficulty) are only published for the 30 largest planning areas; where pa_data_published = false the national rate was used. Mention this when relevant.
* Never claim data about individual people: all data is area-level.
* Round temperatures to 1 decimal place and percentages to whole numbers. Format pct_* columns (stored as 0-1) as percentages."""

SAMPLE_QUESTIONS = [
    "Which 10 areas should we check on first tomorrow?",
    "What is the outlook for tomorrow and how many seniors should we reach first?",
    "Which areas are on High-heat alert tomorrow?",
    "Show tomorrow's list for Bedok",
    "How many seniors live in areas forecast Moderate or High tomorrow?",
    "Which priority areas are more than 1 km from a cool space?",
    "How many High heat days were there each month this year?",
    "On which past days did HeatGuard's top 10 catch the most High-heat areas?",
    "What is the haze level in each region right now?",
]

EXAMPLES = [
    ("Which areas should we check on first tomorrow?",
     f"SELECT rank, tier, subzone_name, planning_area, risk_score, heat_band, high_alert, pop_65_plus, reason, action\nFROM {S}.gold_checkin_list\nWHERE tier = 'Start here'\nORDER BY rank"),
    ("How much better is HeatGuard than ranking by vulnerability alone?",
     f"SELECT sum(start_here_hits) AS heatguard_top10_hits, sum(census_top10_hits) AS census_top10_hits,\n       round(sum(start_here_hits) / sum(census_top10_hits), 1) AS times_better\nFROM {S}.gold_replay_summary"),
    ("How many High heat days were there each month?",
     f"SELECT month, count_if(stations_high > 0) AS high_heat_days, count(*) AS days\nFROM {S}.gold_daily_summary\nGROUP BY month\nORDER BY month"),
    ("Which priority areas are far from a cool space?",
     f"SELECT rank, subzone_name, planning_area, nearest_cool_space, cool_space_km\nFROM {S}.gold_checkin_list\nWHERE cool_space_km > 1\nORDER BY rank"),
    ("How accurate is the forecast?",
     f"SELECT model, round(mae_c, 2) AS average_error_c, round(within_1c * 100) AS pct_within_1c, round(high_recall * 100) AS pct_high_days_caught, test_period\nFROM {S}.ml_model_evaluation\nORDER BY mae_c"),
]

def gid():
    return uuid.uuid4().hex

def lines(text):
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]

space = {
    "version": 2,
    "config": {"sample_questions": [{"id": gid(), "question": [q]} for q in SAMPLE_QUESTIONS]},
    "data_sources": {"tables": [{"identifier": t} for t in TABLES]},
    "instructions": {
        "text_instructions": [{"id": gid(), "content": lines(INSTRUCTIONS)}],
        "example_question_sqls": [{"id": gid(), "question": [q], "sql": lines(sql)} for q, sql in EXAMPLES],
    },
}
# Genie expects ids sorted within each list
space["config"]["sample_questions"].sort(key=lambda x: x["id"])
space["instructions"]["text_instructions"].sort(key=lambda x: x["id"])
space["instructions"]["example_question_sqls"].sort(key=lambda x: x["id"])

body = {"warehouse_id": WAREHOUSE_ID, "serialized_space": json.dumps(space), "title": TITLE, "description": DESCRIPTION}
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_space_request.json")
with open(path, "w", encoding="utf-8") as fh:
    json.dump(body, fh)

env = dict(os.environ, MSYS_NO_PATHCONV="1")
if len(sys.argv) > 1:
    cmd = ["databricks", "-p", PROFILE, "genie", "update-space", sys.argv[1], "--json", f"@{path}", "-o", "json"]
else:
    cmd = ["databricks", "-p", PROFILE, "genie", "create-space", "--json", f"@{path}", "-o", "json"]
out = subprocess.run(cmd, capture_output=True, text=True, env=env)
os.remove(path)
if out.returncode:
    raise SystemExit(out.stderr)
result = json.loads(out.stdout)
print("Genie space:", result.get("space_id"), "-", result.get("title"))
