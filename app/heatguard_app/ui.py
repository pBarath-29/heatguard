"""Shared look and feel: colours, badges, KPI tiles, page headers."""
import html

import streamlit as st

BAND = {   # NEA heat-stress bands
    "High":     {"fg": "#B91C1C", "bg": "#FEE2E2", "rgb": [185, 28, 28],  "label": "High", "icon": "🔴"},
    "Moderate": {"fg": "#B45309", "bg": "#FEF3C7", "rgb": [217, 119, 6],  "label": "Moderate", "icon": "🟠"},
    "Low":      {"fg": "#15803D", "bg": "#DCFCE7", "rgb": [21, 128, 61],  "label": "Low", "icon": "🟢"},
}
PSI = {    # NEA PSI bands
    "Good":           {"fg": "#15803D", "bg": "#DCFCE7"},
    "Moderate":       {"fg": "#1D4ED8", "bg": "#DBEAFE"},
    "Unhealthy":      {"fg": "#B45309", "bg": "#FEF3C7"},
    "Very unhealthy": {"fg": "#B91C1C", "bg": "#FEE2E2"},
    "Hazardous":      {"fg": "#7F1D1D", "bg": "#FECACA"},
}
DRIVER = {
    "heat": ("Heat", "🌡️"), "haze": ("Haze", "🌫️"),
    "vulnerability": ("Many vulnerable seniors", "👵"), "access": ("Far from a cool space", "🚶"),
}

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"], .stMarkdown, .stButton button { font-family: 'Inter', system-ui, sans-serif; }
  .block-container { padding-top: 1.6rem; max-width: 1200px; }
  h1, h2, h3 { letter-spacing: -0.01em; }
  .hg-hero { background: linear-gradient(120deg, #7C2D12 0%, #C2410C 55%, #F59E0B 100%); color: #fff;
             border-radius: 18px; padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 6px 20px rgba(124,45,18,.18); }
  .hg-hero h1 { color: #fff; font-size: 1.9rem; margin: 0 0 4px 0; padding: 0; }
  .hg-hero p { margin: 0; opacity: .92; font-size: 1.02rem; }
  .hg-badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: .82rem; font-weight: 600;
              margin: 2px 6px 2px 0; white-space: nowrap; }
  .hg-kpi { background: #fff; border: 1px solid #F3E3D3; border-radius: 14px; padding: 14px 16px; height: 100%;
            box-shadow: 0 1px 3px rgba(0,0,0,.04); }
  .hg-kpi .lbl { color: #6B7280; font-size: .82rem; font-weight: 500; text-transform: uppercase; letter-spacing: .03em; }
  .hg-kpi .val { font-size: 1.75rem; font-weight: 700; line-height: 1.2; margin-top: 4px; }
  .hg-kpi .sub { color: #6B7280; font-size: .85rem; margin-top: 2px; }
  .hg-rank { font-size: 1.9rem; font-weight: 700; color: #C2410C; line-height: 1; }
  .hg-area { font-size: 1.15rem; font-weight: 700; color: #111827; }
  .hg-pa { color: #6B7280; font-size: .9rem; }
  .hg-score { text-align: center; border-radius: 12px; padding: 6px 4px; }
  .hg-score .n { font-size: 1.6rem; font-weight: 700; line-height: 1.1; }
  .hg-score .t { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; }
  .hg-reason { color: #374151; font-size: .93rem; margin: 6px 0 2px 0; }
  .hg-action { background: #F0FDF4; border-left: 4px solid #16A34A; border-radius: 8px; padding: 9px 12px; margin-top: 8px;
               color: #14532D; font-size: .93rem; }
  .hg-action b { color: #166534; }
  .hg-note { color: #6B7280; font-size: .85rem; }
  .hg-step { background: #fff; border: 1px solid #F3E3D3; border-radius: 12px; padding: 12px 14px; height: 100%; }
  .hg-step .num { display: inline-block; width: 26px; height: 26px; border-radius: 50%; background: #C2410C; color: #fff;
                  text-align: center; font-weight: 700; line-height: 26px; margin-right: 6px; }
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
  section[data-testid="stSidebar"] { background: #FFF7ED; }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(x):
    return html.escape("" if x is None else str(x))


def badge(text, fg="#374151", bg="#F3F4F6"):
    return f'<span class="hg-badge" style="color:{fg};background:{bg}">{esc(text)}</span>'


def band_badge(band, prefix=""):
    b = BAND.get(band)
    if not b:
        return badge(f"{prefix}No data")
    return badge(f"{prefix}{b['label']}", b["fg"], b["bg"])


def psi_badge(band, value=None):
    p = PSI.get(band, {"fg": "#374151", "bg": "#F3F4F6"})
    txt = f"Haze: {band}" + (f" (PSI {int(value)})" if value is not None and value == value else "")
    return badge(txt, p["fg"], p["bg"])


def driver_badge(driver):
    label, icon = DRIVER.get(driver, (driver or "—", "•"))
    return badge(f"{icon} Main reason: {label}", "#7C2D12", "#FFEDD5")


def hero(title, subtitle):
    st.markdown(f'<div class="hg-hero"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>', unsafe_allow_html=True)


def kpi(col, label, value, sub="", color="#111827", help_text=None):
    with col:
        st.markdown(f'<div class="hg-kpi" title="{esc(help_text or "")}"><div class="lbl">{esc(label)}</div>'
                    f'<div class="val" style="color:{color}">{esc(value)}</div><div class="sub">{esc(sub)}</div></div>',
                    unsafe_allow_html=True)


def score_box(score, band):
    b = BAND.get(band, {"fg": "#374151", "bg": "#F3F4F6"})
    return (f'<div class="hg-score" style="background:{b["bg"]};color:{b["fg"]}">'
            f'<div class="n">{score:.0f}</div><div class="t">risk score</div></div>')


def risk_rgb(score):
    """Colour for a 0–100 risk score: amber → deep red."""
    t = max(0.0, min(1.0, (score - 35) / 35))
    return [int(245 - 120 * t), int(158 - 130 * t), int(11 + 20 * t), 200]


def pct(x, digits=0):
    return "—" if x is None or x != x else f"{x * 100:.{digits}f}%"


def num(x, digits=0):
    return "—" if x is None or x != x else f"{x:,.{digits}f}"
