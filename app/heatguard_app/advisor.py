"""Turn rulebook actions into a ready-to-send message. The language model only rewrites wording; it never adds actions."""
import streamlit as st

from .data import setting, workspace

LANGUAGES = ["English", "中文 (Chinese)", "Bahasa Melayu", "தமிழ் (Tamil)"]
AUDIENCES = {
    "Message to seniors": "a short, warm WhatsApp or SMS message to seniors living in the area, in very simple words, "
                          "large ideas only, no jargon (do not mention WBGT, PSI or scores)",
    "Briefing for staff and volunteers": "a short briefing for Active Ageing Centre staff and volunteers who will phone or visit seniors, "
                                         "with the reason and the steps as a numbered list",
}

SYSTEM = ("You rewrite heat-safety outreach guidance for Active Ageing Centre staff in Singapore. "
          "Use ONLY the facts and actions provided. Do not add new actions, medical advice, phone numbers, places or numbers that are not given. "
          "Keep it under 120 words. Write the whole message in {language}.")


@st.cache_data(ttl=3600, show_spinner=False)
def write_message(area, planning_area, day_text, heat_text, haze_text, cool_space, action, language, audience):
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
    facts = (f"Area: {area} ({planning_area}). Day: {day_text}. Heat: {heat_text}. Haze: {haze_text}. "
             f"Nearest air-conditioned place: {cool_space}.\nActions to include (keep all of them, no others):\n{action}")
    prompt = f"Write {AUDIENCES[audience]}.\n\n{facts}"
    w = workspace()
    resp = w.serving_endpoints.query(
        name=setting("SERVING_ENDPOINT"),
        messages=[ChatMessage(role=ChatMessageRole.SYSTEM, content=SYSTEM.format(language=language)),
                  ChatMessage(role=ChatMessageRole.USER, content=prompt)],
        max_tokens=400, temperature=0.3)
    return resp.choices[0].message.content.strip()


def fallback_message(area, day_text, heat_text, cool_space, action):
    return (f"{area} — {day_text}\n{heat_text}.\nNearest cool space: {cool_space}.\n\nWhat to do:\n{action}")
