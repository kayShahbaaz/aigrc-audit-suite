"""
app.py — AI GRC Audit Suite
==============================
Main Streamlit application entry point.

This file is responsible for:
1. Page configuration (title, icon, layout)
2. Visual design system — typography, color tokens, component styling
3. Region selector — Gulf / India tabs at the top
4. Country selector — Saudi Arabia (active) | UAE (coming soon)
5. Company Profile form — filled once, passed to every module
6. Module tabs — one tab per module, rendered by calling module.render()

Running the app:
    streamlit run app.py

Architecture:
- All AI logic lives in utils/groq_client.py
- All framework data lives in config/frameworks.py
- Each module's UI and logic lives in modules/*.py
- This file is ONLY navigation, layout, and company profile
- No direct AI calls in app.py — everything goes through modules

Design system:
- Display face: Georgia (serif) for headlines — signals institutional authority,
  matching the visual register of professional audit/advisory deliverables
- Body face: system sans-serif — clean, legible, fast-rendering
- Palette: deep navy (#1A375E) + gold (#C89A1A), the two-colour seal palette
  used throughout the exported DOCX/PDF/Excel deliverables, so the in-app
  experience and the client-facing output feel like one coherent product
- Signature element: a custom hexagonal shield-and-checkmark mark (assets/logo.svg)
  replacing the generic shield emoji — built once, used as the header logo

Coding rules:
- Company profile is collected here and passed to every module
- Modules never ask for company name again
- Session state stores company profile across tab switches
"""

import base64
import streamlit as st
import streamlit.components.v1 as components
from datetime import date
from pathlib import Path

# --- App config imports ---
from config.settings import (
    APP_NAME,
    APP_VERSION,
    APP_TAGLINE,
    PAGE_TITLE,
    PAGE_ICON,
    PAGE_LAYOUT,
    SIDEBAR_STATE,
    COMPANY_SIZE_OPTIONS,
    INDUSTRY_OPTIONS,
    CITY_OPTIONS_SAUDI,
)
from config.frameworks import get_framework_list, FRAMEWORKS

# --- Module imports ---
# Each module exports one render(company_profile) function
from modules.policy    import render as render_policy
from modules.risk      import render as render_risk
from modules.checklist import render as render_checklist
from modules.gap       import render as render_gap
from modules.vendor    import render as render_vendor
from modules.playbook  import render as render_playbook
from modules.report    import render as render_report


# =============================================================
# PAGE CONFIG — must be first Streamlit call
# =============================================================

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
    initial_sidebar_state="expanded",
)

# =============================================================
# THEME STATE
# Stored in session_state so it persists across reruns.
# The hidden theme toggle button below triggers st.rerun() which
# re-injects the correct CSS for the chosen theme.
# =============================================================

# Read theme from URL query param (set by banner JS) or session_state
# This is the cleanest approach — no hidden button, no CSS fighting.
# When the sun/moon is clicked in the iframe, JS sets ?theme=dark or ?theme=light
# in window.parent.location, which causes Streamlit to rerun and we read it here.
_qp = st.query_params.get("theme", None)
if _qp in ("dark", "light"):
    st.session_state["theme"] = _qp
elif "theme" not in st.session_state:
    st.session_state["theme"] = "light"

_is_dark = st.session_state["theme"] == "dark"


# =============================================================
# LOGO LOADING
# Reads the custom shield-and-checkmark SVG mark and inlines it as base64
# so it can be embedded directly in markdown without a separate file server.
# =============================================================

def _load_logo_base64() -> str:
    """
    Read assets/logo.svg and return it as a base64 data URI.
    Falls back to an inline SVG string if the file is missing, so the
    app never breaks even if assets/ isn't deployed correctly.
    """
    logo_path = Path(__file__).parent / "assets" / "logo.svg"
    try:
        svg_bytes = logo_path.read_bytes()
        encoded = base64.b64encode(svg_bytes).decode("utf-8")
        return f"data:image/svg+xml;base64,{encoded}"
    except FileNotFoundError:
        # Inline fallback — same mark, defined directly so the app degrades gracefully
        fallback_svg = (
            '<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M32 2.5 L57 13.5 L57 31 C57 45.5 47.5 55 32 61 C16.5 55 7 45.5 7 31 L7 13.5 Z" '
            'fill="#1A375E" stroke="#C89A1A" stroke-width="1.25"/>'
            '<path d="M21 32.5 L28 39.5 L43.5 23" fill="none" stroke="#C89A1A" stroke-width="3.75" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>'
        )
        encoded = base64.b64encode(fallback_svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{encoded}"


LOGO_DATA_URI = _load_logo_base64()


# =============================================================
# DESIGN TOKENS
# Single source of truth for the visual system — referenced throughout
# the CSS block below. Keeping these named makes the palette legible
# and easy to adjust in one place rather than hunting through hex codes.
# =============================================================

NAVY        = "#1A375E"   # primary brand — headers, primary actions
NAVY_DARK   = "#0F1F35"   # deepest navy — body text on light, gradients
NAVY_DEEP   = "#13294B"   # mid-dark navy — sidebar, footer bands
GOLD        = "#C89A1A"   # accent — CTAs, dividers, highlights
GOLD_LIGHT  = "#E0B94A"   # lighter gold — hover states
INK         = "#1C2330"   # primary text — near-black with a navy cast
SLATE       = "#5B6472"   # secondary text — captions, helper copy
PAGE_BG     = "#FAFAF8"   # warm off-white page background
CARD_BG     = "#FFFFFF"   # card / panel surfaces
LINE        = "#E4E1D8"   # hairline borders on warm background
LINE_SOFT   = "#EDEAE0"   # lighter dividers


# =============================================================
# CUSTOM CSS
# A deliberate type and colour system rather than Streamlit defaults.
# Serif display face for headings (institutional, matches the register
# of an audit deliverable) paired with clean sans body text.
# =============================================================

# Inject theme-aware CSS — regenerated on every rerun based on session_state["theme"]
# Light theme uses warm off-white; dark theme uses deep navy backgrounds.
# All colour variables are defined here and referenced by CSS selectors.

_T = {
    "page_bg":     "#0A1628"  if _is_dark else "#F5F7FA",
    "card_bg":     "#0F2040"  if _is_dark else "#FFFFFF",
    "text":        "#E8EDF3"  if _is_dark else "#1C2330",
    "text2":       "#8AAABF"  if _is_dark else "#5B6472",
    "line":        "#1E3A5F"  if _is_dark else "#E4E1D8",
    "input_bg":    "#0D1C30"  if _is_dark else "#FFFFFF",
    "input_border":"#2A4A70"  if _is_dark else "#D0CCC4",
    "metric_bg":   "#0F2040"  if _is_dark else "#FFFFFF",
    "expander_bg": "#0F2040"  if _is_dark else "#FFFFFF",
    "sidebar_bg":  "#060E1D"  if _is_dark else "#13294B",
    "form_bg":     "#0D1C30"  if _is_dark else "#FFFFFF",
    "success_bg":  "#0A2410"  if _is_dark else "#F0FFF4",
    "info_bg":     "#0A1E35"  if _is_dark else "#EBF5FF",
    "warn_bg":     "#2A1A00"  if _is_dark else "#FFFBEB",
    "err_bg":      "#2A0A0A"  if _is_dark else "#FFF5F5",
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}

    /* ── PAGE BACKGROUND ── */
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main {{
        background-color: {_T["page_bg"]} !important;
    }}

    /* Hide Streamlit chrome bar — our banner replaces it */
    [data-testid="stHeader"] {{
        display: none !important;
    }}

    /* No hidden button needed — theme is toggled via URL query params */

    /* Flush top padding for banner */
    .block-container {{
        padding-top: 0 !important;
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }}
    .main .block-container {{ padding-top: 0 !important; }}

    /* ── TYPOGRAPHY ── */
    h1, h2, h3 {{
        font-family: 'Source Serif 4', Georgia, serif !important;
        color: {_T["text"]} !important;
        letter-spacing: -0.01em;
    }}
    h1 {{ font-weight: 700 !important; }}
    h2 {{ font-weight: 600 !important; }}
    h3 {{ font-weight: 600 !important; }}
    p, span, label, div {{ color: {_T["text"]}; }}
    [data-testid="stCaptionContainer"], .stCaption {{ color: {_T["text2"]} !important; }}
    small, .small {{ color: {_T["text2"]} !important; }}

    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        border-bottom: 1px solid {_T["line"]};
        background: transparent;
    }}
    .stTabs [data-baseweb="tab"] {{
        font-weight: 500;
        font-size: 14px;
        color: {_T["text2"]};
        padding: 10px 16px;
        background: transparent;
    }}
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
        border-bottom: 2.5px solid {GOLD};
        color: {NAVY};
        font-weight: 600;
        background: transparent;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        background: transparent !important;
    }}

    /* ── BUTTONS ── */
    .stButton > button[kind="primary"] {{
        background-color: {NAVY};
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        padding: 0.55rem 1.4rem;
        transition: background-color 0.15s ease;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {GOLD};
        color: white;
    }}
    .stButton > button[kind="secondary"] {{
        border: 1px solid {_T["line"]};
        border-radius: 6px;
        color: {_T["text"]};
        background-color: {_T["card_bg"]};
    }}
    .stButton > button[kind="secondary"]:hover {{
        border-color: {NAVY};
    }}

    /* ── DOWNLOAD BUTTONS ── */
    .stDownloadButton > button {{
        background-color: {GOLD};
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
    }}
    .stDownloadButton > button:hover {{
        background-color: {NAVY};
        color: white;
    }}

    /* ── FORM FIELDS ── */
    .stTextInput input, .stTextArea textarea,
    .stSelectbox > div > div, .stNumberInput input, .stDateInput input {{
        border-radius: 6px !important;
        border-color: {_T["input_border"]} !important;
        background-color: {_T["input_bg"]} !important;
        color: {_T["text"]} !important;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {NAVY} !important;
        box-shadow: 0 0 0 1px {NAVY} !important;
    }}
    [data-testid="stForm"] {{
        background-color: {_T["form_bg"]};
        border: 1px solid {_T["line"]};
        border-radius: 10px;
        padding: 1.5rem 1.5rem 0.75rem 1.5rem;
    }}

    /* ── EXPANDERS ── */
    [data-testid="stExpander"] {{
        border: 1px solid {_T["line"]} !important;
        border-radius: 8px !important;
        background-color: {_T["expander_bg"]} !important;
    }}
    [data-testid="stExpander"] summary {{
        color: {_T["text"]} !important;
    }}

    /* ── DIVIDERS ── */
    hr {{ border-color: {_T["line"]} !important; margin: 1.4rem 0 !important; }}

    /* ── METRICS ── */
    [data-testid="stMetric"] {{
        background-color: {_T["metric_bg"]};
        border: 1px solid {_T["line"]};
        border-radius: 8px;
        padding: 12px 16px;
    }}
    [data-testid="stMetricLabel"] {{ color: {_T["text2"]} !important; font-size: 12px !important; }}
    [data-testid="stMetricValue"] {{
        color: {_T["text"]} !important;
        font-family: 'Source Serif 4', Georgia, serif !important;
    }}

    /* ── ALERTS ── */
    [data-testid="stAlertContainer"] {{ border-radius: 8px; border-width: 1px; }}

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] {{ background-color: {_T["sidebar_bg"]}; }}
    [data-testid="stSidebar"] * {{ color: #E8EDF3 !important; }}
    [data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.15) !important; }}

    /* Theme toggle button in sidebar */
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] > button {{
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(200,154,26,0.4) !important;
        color: #E0B94A !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em !important;
        transition: all 0.2s !important;
    }}
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] > button:hover {{
        background: rgba(200,154,26,0.2) !important;
        border-color: #C89A1A !important;
    }}
    /* Sidebar arrow visible so user can open/close sidebar */

    /* ── THEME TOGGLE BUTTON — small circle, top-right of page ── */
    [data-st-key="main_theme_toggle"] > button {{
        width: 36px !important;
        height: 36px !important;
        border-radius: 50% !important;
        padding: 0 !important;
        font-size: 17px !important;
        min-width: unset !important;
        border: 1.5px solid {('rgba(200,154,26,0.65)' if _is_dark else 'rgba(26,55,94,0.3)')} !important;
        background: {('rgba(200,154,26,0.1)' if _is_dark else 'rgba(26,55,94,0.05)')} !important;
        color: {('#E0B94A' if _is_dark else '#1A375E')} !important;
        line-height: 1 !important;
        transition: all 0.18s !important;
    }}
    [data-st-key="main_theme_toggle"] > button:hover {{
        background: {('rgba(200,154,26,0.22)' if _is_dark else 'rgba(26,55,94,0.12)')} !important;
        border-color: {('#C89A1A' if _is_dark else '#1A375E')} !important;
        transform: scale(1.1) !important;
    }}

    /* ── REGION SELECTBOX — pill style ── */
    [data-testid="stSelectbox"][data-st-key="region_selector"] > div > div {{
        border-radius: 24px !important;
        border-color: {('rgba(200,154,26,0.4)' if _is_dark else 'rgba(26,55,94,0.25)')} !important;
        background: {('rgba(255,255,255,0.04)' if _is_dark else 'rgba(26,55,94,0.04)')} !important;
        font-weight: 500 !important;
        font-size: 14px !important;
    }}

    /* Theme toggle is in the sidebar */

    /* ── SECTION LABELS ── */
    .grc-section-label {{
        display: flex; align-items: center; gap: 10px; margin: 8px 0 2px 0;
    }}
    .grc-section-num {{
        font-family: 'Source Serif 4', Georgia, serif;
        font-size: 13px; font-weight: 700;
        color: #fff;
        background: {NAVY};
        width: 24px; height: 24px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
    }}

    /* ── FOOTER ── */
    .grc-footer {{
        margin-top: 3rem; padding-top: 1.25rem;
        border-top: 1px solid {_T["line"]};
        display: flex; justify-content: space-between; align-items: center;
    }}
    .grc-footer-text {{ font-size: 12px; color: {_T["text2"]}; }}

    /* ── SELECTBOX OPTIONS (dropdown items) ── */
    [data-testid="stSelectbox"] > div > div {{
        background-color: {_T["card_bg"]} !important;
        color: {_T["text"]} !important;
    }}

    /* ── MULTISELECT ── */
    [data-testid="stMultiSelect"] > div > div {{
        background-color: {_T["input_bg"]} !important;
        border-color: {_T["input_border"]} !important;
    }}

    /* ── RADIO + CHECKBOX ── */
    [data-testid="stRadio"] label span,
    [data-testid="stCheckbox"] label span {{
        color: {_T["text"]} !important;
    }}

    /* ── STATUS BOXES ── */
    [data-testid="stStatusWidget"] {{
        background-color: {_T["card_bg"]} !important;
        border-color: {_T["line"]} !important;
    }}

    /* Dataframe */
    [data-testid="stDataFrame"] {{
        background-color: {_T["card_bg"]} !important;
    }}
</style>
""", unsafe_allow_html=True)

# ── Single theme toggle — top-right, symbol only ─────────────────────────────
_t_spacer, _t_col = st.columns([14, 1])
with _t_col:
    if st.button("☀" if _is_dark else "☾", key="main_theme_toggle",
                 help="Toggle light / dark mode", use_container_width=False):
        st.session_state["theme"] = "light" if _is_dark else "dark"
        st.rerun()


# =============================================================
# SIDEBAR — App identity and quick reference
# =============================================================

with st.sidebar:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">'
        f'<img src="{LOGO_DATA_URI}" width="32" height="32"/>'
        f'<span style="font-family:\'Source Serif 4\',Georgia,serif;font-size:18px;'
        f'font-weight:700;color:white;">{APP_NAME}</span></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Version {APP_VERSION}")
    st.divider()

    st.markdown("**Regional coverage**")
    st.markdown("Saudi Arabia — Active")
    st.markdown("UAE — Coming soon")
    st.markdown("India — Coming soon")

    st.divider()

    st.markdown("**Frameworks supported**")
    framework_options = get_framework_list()
    for fw_id, display_name in framework_options:
        short_name = display_name.split(" — ")[0]
        st.markdown(f"· {short_name}")

    st.divider()

    st.markdown("**Audit modules**")
    modules_list = [
        "1 · Policy generator",
        "2 · Risk register",
        "3 · Audit checklist",
        "4 · Gap assessment",
        "5 · Vendor risk",
        "6 · IR playbook",
        "7 · Audit report",
    ]
    for m in modules_list:
        st.markdown(f"· {m}")

    st.divider()

    st.caption("Built for the Saudi and Gulf compliance market.")


# =============================================================
# HERO HEADER
# Logo mark, product name, and a real professional brief explaining
# what the tool does and why it matters — replacing the generic tagline.
# =============================================================

# ── Full-bleed header banner ────────────────────────────────────────────────
# components.html() renders in a real iframe — scripts execute properly.
# st.markdown() strips <script> tags silently, which caused the raw HTML bug.
# All styles are inline here because the parent's CSS classes don't reach
# inside an iframe. The JS posts to window.parent for the theme toggle.

_banner_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:100%; overflow:hidden; background:#0A1628; }}

/* ── BANNER ROOT ── */
.banner {{
  position: relative;
  width: 100%;
  min-height: 220px;
  background: linear-gradient(110deg, #060E1D 0%, #0D2040 35%, #1A375E 70%, #0F2848 100%);
  overflow: hidden;
  display: flex;
  align-items: flex-start;
  padding: 32px 48px 28px 48px;
  border-bottom: 2px solid #C89A1A;
}}

/* ── ANIMATED GRID BACKGROUND ── */
.grid {{
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(200,154,26,0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(200,154,26,0.06) 1px, transparent 1px);
  background-size: 48px 48px;
  animation: gridMove 20s linear infinite;
  z-index: 0;
}}
@keyframes gridMove {{
  0%   {{ background-position: 0 0; }}
  100% {{ background-position: 48px 48px; }}
}}

/* ── RADIAL GLOW ── */
.glow {{
  position: absolute;
  top: -60px; left: 20%;
  width: 500px; height: 300px;
  background: radial-gradient(ellipse, rgba(26,55,94,0.8) 0%, transparent 70%);
  z-index: 0;
  animation: glowPulse 4s ease-in-out infinite;
}}
@keyframes glowPulse {{
  0%,100% {{ opacity: 0.6; transform: scale(1); }}
  50%      {{ opacity: 1;   transform: scale(1.1); }}
}}

/* ── FLOATING PARTICLES ── */
.particles {{ position:absolute; inset:0; z-index:0; pointer-events:none; }}
.p {{
  position: absolute;
  border-radius: 50%;
  background: rgba(200,154,26,0.5);
  animation: float linear infinite;
}}
@keyframes float {{
  0%   {{ transform: translateY(100%) translateX(0); opacity:0; }}
  10%  {{ opacity:0.8; }}
  90%  {{ opacity:0.4; }}
  100% {{ transform: translateY(-20px) translateX(20px); opacity:0; }}
}}

/* ── SCAN LINE ── */
.scanline {{
  position: absolute;
  left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(200,154,26,0.4), transparent);
  animation: scan 6s linear infinite;
  z-index: 1;
}}
@keyframes scan {{
  0%   {{ top: 0%;   opacity: 0; }}
  5%   {{ opacity: 1; }}
  95%  {{ opacity: 1; }}
  100% {{ top: 100%; opacity: 0; }}
}}

/* ── SHIELD LOGO ── */
.logo-wrap {{
  position: relative;
  flex-shrink: 0;
  z-index: 2;
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
}}
.logo {{
  width: 76px;
  height: 76px;
  filter: drop-shadow(0 0 16px rgba(200,154,26,0.5)) drop-shadow(0 2px 12px rgba(0,0,0,0.4));
  animation: shieldPulse 3s ease-in-out infinite;
}}
@keyframes shieldPulse {{
  0%,100% {{ filter: drop-shadow(0 0 12px rgba(200,154,26,0.4)) drop-shadow(0 2px 12px rgba(0,0,0,0.4)); }}
  50%      {{ filter: drop-shadow(0 0 28px rgba(200,154,26,0.8)) drop-shadow(0 2px 20px rgba(0,0,0,0.5)); }}
}}
.logo-ring {{
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 96px; height: 96px;
  border-radius: 50%;
  border: 1px solid rgba(200,154,26,0.25);
  animation: ringExpand 2.5s ease-out infinite;
}}
.logo-ring2 {{
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 116px; height: 116px;
  border-radius: 50%;
  border: 1px solid rgba(200,154,26,0.12);
  animation: ringExpand 2.5s ease-out 0.8s infinite;
}}
@keyframes ringExpand {{
  0%   {{ opacity:0.8; transform:translate(-50%,-50%) scale(0.85); }}
  100% {{ opacity:0;   transform:translate(-50%,-50%) scale(1.4); }}
}}

/* ── TEXT CONTENT ── */
.content {{
  flex: 1;
  z-index: 2;
  position: relative;
}}
.title-row {{
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 14px;
}}
.eyebrow {{
  font-family: 'Inter', sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #C89A1A;
  margin-bottom: 8px;
  opacity: 0;
  animation: fadeUp 0.6s ease 0.2s forwards;
}}
.title {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 42px;
  font-weight: 700;
  color: #FFFFFF;
  line-height: 1.06;
  letter-spacing: -0.025em;
  margin: 0;
  text-shadow: 0 2px 20px rgba(0,0,0,0.4);
  opacity: 0;
  animation: fadeUp 0.7s ease 0.35s forwards;
}}
/* Animated gradient on "AI" */
.title .ai {{
  background: linear-gradient(90deg, #C89A1A, #F0CC6A, #C89A1A);
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 3s linear infinite;
}}
@keyframes shimmer {{
  0%   {{ background-position: 0% center; }}
  100% {{ background-position: 200% center; }}
}}
.desc {{
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  color: #9BB5CC;
  line-height: 1.7;
  max-width: 660px;
  margin-bottom: 22px;
  opacity: 0;
  animation: fadeUp 0.7s ease 0.5s forwards;
}}
.desc strong {{ color: #E0B94A; font-weight: 600; }}
@keyframes fadeUp {{
  from {{ opacity:0; transform:translateY(14px); }}
  to   {{ opacity:1; transform:translateY(0); }}
}}

/* ── STATS ROW ── */
.stats {{
  display: flex;
  gap: 0;
  border-top: 1px solid rgba(255,255,255,0.1);
  padding-top: 16px;
  opacity: 0;
  animation: fadeUp 0.7s ease 0.7s forwards;
}}
.stat {{
  display: flex;
  flex-direction: column;
  padding-right: 28px;
  margin-right: 28px;
  border-right: 1px solid rgba(255,255,255,0.1);
}}
.stat:last-child {{ border-right: none; margin-right: 0; padding-right: 0; }}
.stat-num {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 26px;
  font-weight: 700;
  color: #E0B94A;
  line-height: 1.1;
}}
.stat-label {{
  font-size: 10px;
  color: #6A8BA6;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 3px;
}}

/* ── FRAMEWORK PILLS ── */
.pills {{
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  opacity: 0;
  animation: fadeUp 0.7s ease 0.6s forwards;
}}
.pill {{
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: #C89A1A;
  border: 1px solid rgba(200,154,26,0.35);
  background: rgba(200,154,26,0.08);
  padding: 3px 10px;
  border-radius: 20px;
  letter-spacing: 0.04em;
  transition: background 0.2s, border-color 0.2s;
  cursor: default;
}}
.pill:hover {{
  background: rgba(200,154,26,0.18);
  border-color: rgba(200,154,26,0.7);
}}

/* Theme toggle is a real Streamlit button outside this iframe — see app.py CSS */

/* ── CORNER ACCENTS ── */
.corner {{
  position: absolute;
  width: 24px; height: 24px;
  z-index: 1;
  opacity: 0.4;
}}
.corner-tl {{ top:12px; left:12px; border-top:2px solid #C89A1A; border-left:2px solid #C89A1A; }}
.corner-tr {{ top:12px; right:12px; border-top:2px solid #C89A1A; border-right:2px solid #C89A1A; }}
.corner-bl {{ bottom:12px; left:12px; border-bottom:2px solid #C89A1A; border-left:2px solid #C89A1A; }}
.corner-br {{ bottom:12px; right:12px; border-bottom:2px solid #C89A1A; border-right:2px solid #C89A1A; }}

/* ── VERSION BADGE ── */
.badge {{
  position: absolute;
  bottom: 14px; right: 24px;
  font-family: 'Inter', sans-serif;
  font-size: 10px;
  color: rgba(255,255,255,0.25);
  letter-spacing: 0.1em;
  z-index: 2;
}}
</style>
</head>
<body>
<div class="banner">

  <!-- Animated background layers -->
  <div class="grid"></div>
  <div class="glow"></div>
  <div class="scanline"></div>

  <!-- Corner accents -->
  <div class="corner corner-tl"></div>
  <div class="corner corner-tr"></div>
  <div class="corner corner-bl"></div>
  <div class="corner corner-br"></div>

  <!-- Floating particles (created by JS) -->
  <div class="particles" id="particles"></div>

  <!-- Text content — logo sits inside, left of the title text -->
  <div class="content">
    <p class="eyebrow">Saudi Arabia &amp; Gulf Compliance Platform</p>
    <div class="title-row">
      <div class="logo-wrap">
        <div class="logo-ring"></div>
        <div class="logo-ring2"></div>
        <img src="{LOGO_DATA_URI}" class="logo" alt="Logo"/>
      </div>
      <h1 class="title"><span class="ai">AI</span> GRC Audit Suite</h1>
    </div>
    <div class="pills">
      <span class="pill">NCA ECC</span>
      <span class="pill">SAMA CSF</span>
      <span class="pill">SDAIA PDPL</span>
      <span class="pill">NCA CCC</span>
      <span class="pill">SAMA BCM</span>
      <span class="pill">CITC</span>
      <span class="pill">Vision 2030</span>
    </div>
    <p class="desc">
      Seven AI-assisted modules that turn a multi-week audit cycle into a same-day one —
      policies, risk registers, gap assessments, vendor reports, IR playbooks, and the
      final board report, each framework-mapped and client-ready.
    </p>
    <div class="stats">
      <div class="stat"><span class="stat-num" data-target="7">0</span><span class="stat-label">Audit modules</span></div>
      <div class="stat"><span class="stat-num" data-target="8">0</span><span class="stat-label">Frameworks</span></div>
      <div class="stat"><span class="stat-num" data-target="3">0</span><span class="stat-label">Output formats</span></div>
      <div class="stat"><span class="stat-num" data-target="70">0</span><span class="stat-label">Controls mapped</span></div>
    </div>
  </div>

  <!-- Version -->
  <div class="badge">v1.0.0 · Phase 1: Saudi Arabia</div>
</div>



<script>
// ── Floating particles ──────────────────────────────────────────────────────
var container = document.getElementById('particles');
for (var i = 0; i < 18; i++) {{
  var p = document.createElement('div');
  p.className = 'p';
  var size = Math.random() * 3 + 1;
  p.style.cssText = [
    'width:'  + size + 'px',
    'height:' + size + 'px',
    'left:'   + Math.random() * 100 + '%',
    'bottom:  0',
    'animation-duration:' + (Math.random() * 8 + 6) + 's',
    'animation-delay:'    + (Math.random() * 6)     + 's',
    'opacity: 0'
  ].join(';');
  container.appendChild(p);
}}

// ── Animated stat counters ──────────────────────────────────────────────────
function animateCounters() {{
  var nums = document.querySelectorAll('.stat-num[data-target]');
  nums.forEach(function(el) {{
    var target = parseInt(el.getAttribute('data-target'));
    var start  = 0;
    var dur    = 1400;
    var step   = 16;
    var steps  = dur / step;
    var inc    = target / steps;
    var current = 0;
    var timer = setInterval(function() {{
      current += inc;
      if (current >= target) {{
        el.textContent = target + (target === 70 ? '+' : '');
        clearInterval(timer);
      }} else {{
        el.textContent = Math.floor(current);
      }}
    }}, step);
  }});
}}
setTimeout(animateCounters, 900);


</script>
</body>
</html>
"""

components.html(_banner_html, height=260, scrolling=False)

# ── Theme toggle: columns trick to push button to the right ──────────────────
# Using st.columns is the only reliable way to right-align a widget in Streamlit.



# =============================================================
# REGION SELECTOR
# Tab-based: Gulf | India
# Gulf expands to: Saudi Arabia | UAE
# Only Saudi Arabia is active in Phase 1
# =============================================================

# ── Region + Country selector — single clean dropdown ────────────────────────
# Replaces the nested tabs which looked plain and took up too much vertical space.
# Options show status clearly. Saudi Arabia auto-selects since it's the only
# active region. Coming-soon options are shown but disabled via a note.

_REGION_OPTIONS = {
    "🇸🇦  Saudi Arabia":          "saudi",
    "🇦🇪  UAE  (Coming Soon)":    "uae",
    "🇮🇳  India  (Coming Soon)":  "india",
}

st.markdown(
    f"<p style=\"font-size:13px;font-weight:600;"
    f"color:{'#8AAABF' if _is_dark else '#5B6472'};"
    "letter-spacing:0.06em;text-transform:uppercase;"
    "margin:0 0 6px 0;\">Select your Country</p>",
    unsafe_allow_html=True,
)
_region_col1, _region_col2 = st.columns([3, 5])
with _region_col1:
    _region_choice = st.selectbox(
        "Select your Country",
        options=list(_REGION_OPTIONS.keys()),
        index=0,
        key="region_selector",
        label_visibility="collapsed",
        help="Saudi Arabia is active. UAE and India coming soon.",
    )

_region_key = _REGION_OPTIONS[_region_choice]

if _region_key == "uae":
    st.info(
        "**UAE frameworks are coming in Phase 2.**  "
        "Planned: UAE IA Regulations, CBUAE cybersecurity framework, "
        "ADIO standards, DIFC data protection law, DESC requirements."
    )

elif _region_key == "india":
    st.info(
        "**India frameworks are coming in Phase 3.**  "
        "Planned: CERT-In guidelines, RBI cybersecurity framework, "
        "DPDP Act, SEBI cybersecurity circular, IRDAI guidelines."
    )

elif _region_key == "saudi":
    # Saudi Arabia — FULLY ACTIVE
    # Everything below this point is the real app

    # =============================================================
    # COMPANY PROFILE FORM
    # Collected once here — passed to every module as a dict.
    # This is the core UX principle: fill it once, use it everywhere.
    # =============================================================

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="grc-section-label"><span class="grc-section-num">2</span>'
        '<h4 style="margin:0;">Company profile</h4></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Fill this in once. All 7 modules read from here automatically — "
        "you will never be asked for your company name again inside a module."
    )

    with st.form("company_profile_form"):
        prof_col1, prof_col2 = st.columns(2)

        with prof_col1:
            company_name = st.text_input(
                "Company name *",
                value=st.session_state.get("cp_company_name", ""),
                placeholder="e.g. Al Rajhi Technologies",
            )
            industry = st.selectbox(
                "Industry *",
                options=INDUSTRY_OPTIONS,
                index=INDUSTRY_OPTIONS.index(
                    st.session_state.get("cp_industry", INDUSTRY_OPTIONS[0])
                ) if st.session_state.get("cp_industry") in INDUSTRY_OPTIONS else 0,
            )
            company_size = st.selectbox(
                "Company size",
                options=COMPANY_SIZE_OPTIONS,
                index=COMPANY_SIZE_OPTIONS.index(
                    st.session_state.get("cp_company_size", "SME")
                ) if st.session_state.get("cp_company_size") in COMPANY_SIZE_OPTIONS else 1,
            )

        with prof_col2:
            city = st.selectbox(
                "City",
                options=CITY_OPTIONS_SAUDI,
                index=CITY_OPTIONS_SAUDI.index(
                    st.session_state.get("cp_city", "Riyadh")
                ) if st.session_state.get("cp_city") in CITY_OPTIONS_SAUDI else 0,
            )
            auditor_name = st.text_input(
                "Auditor / consultant name *",
                value=st.session_state.get("cp_auditor_name", ""),
                placeholder="e.g. Ahmed Al-Shahrani",
            )
            engagement_date = st.date_input(
                "Engagement date",
                value=st.session_state.get("cp_engagement_date", date.today()),
            )

        # Multi-select for target frameworks
        # Returns list of framework IDs that the auditor is working against
        fw_options_for_multiselect = {
            fw_id: f"{meta['name']} — {meta['full_name']}"
            for fw_id, meta in FRAMEWORKS.items()
        }

        target_frameworks = st.multiselect(
            "Target frameworks (select all that apply)",
            options=list(fw_options_for_multiselect.keys()),
            default=st.session_state.get("cp_target_frameworks", ["NCA_ECC"]),
            format_func=lambda k: fw_options_for_multiselect[k],
            help="Select all frameworks in scope for this engagement.",
        )

        save_profile = st.form_submit_button(
            "Save company profile",
            type="primary",
            use_container_width=True,
        )

    # --- Process form submission ---
    if save_profile:
        # Validate required fields
        if not company_name.strip():
            st.error("Company name is required.")
        elif not auditor_name.strip():
            st.error("Auditor name is required.")
        else:
            # Save to session state so modules can read it
            st.session_state["cp_company_name"]     = company_name.strip()
            st.session_state["cp_industry"]         = industry
            st.session_state["cp_company_size"]     = company_size
            st.session_state["cp_city"]             = city
            st.session_state["cp_auditor_name"]     = auditor_name.strip()
            st.session_state["cp_engagement_date"]  = engagement_date
            st.session_state["cp_target_frameworks"] = target_frameworks
            st.session_state["company_profile_saved"] = True
            st.success("Company profile saved. You can now use all 7 modules below.")

    # --- Build the company_profile dict to pass to modules ---
    # Always build from session state so it persists across tab switches
    company_profile = {
        "company_name":      st.session_state.get("cp_company_name", ""),
        "industry":          st.session_state.get("cp_industry", ""),
        "company_size":      st.session_state.get("cp_company_size", "SME"),
        "country":           "Saudi Arabia",
        "city":              st.session_state.get("cp_city", "Riyadh"),
        "target_frameworks": st.session_state.get("cp_target_frameworks", []),
        "auditor_name":      st.session_state.get("cp_auditor_name", ""),
        "engagement_date":   str(st.session_state.get("cp_engagement_date", date.today())),
    }

    # Show a compact profile summary once saved
    if st.session_state.get("company_profile_saved"):
        with st.expander("Active profile — click to view", expanded=False):
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.markdown(f"**{company_profile['company_name']}**")
                st.caption(company_profile["industry"])
            with sc2:
                st.markdown(f"**{company_profile['auditor_name']}**")
                st.caption(company_profile["city"] + ", Saudi Arabia")
            with sc3:
                st.markdown(f"**{company_profile['engagement_date']}**")
                fw_names = [
                    FRAMEWORKS[fwid]["name"]
                    for fwid in company_profile["target_frameworks"]
                    if fwid in FRAMEWORKS
                ]
                st.caption(", ".join(fw_names) if fw_names else "No frameworks selected")

    # =============================================================
    # MODULE TABS
    # One tab per module. render() functions handle all UI inside.
    # =============================================================

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.divider()
    st.markdown(
        '<div class="grc-section-label"><span class="grc-section-num">3</span>'
        '<h4 style="margin:0;">Audit modules</h4></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "All 7 modules read your company profile automatically. "
        "Save your profile above before using the modules."
    )

    (
        tab_policy,
        tab_risk,
        tab_checklist,
        tab_gap,
        tab_vendor,
        tab_playbook,
        tab_report,
    ) = st.tabs([
        "1 · Policy",
        "2 · Risk register",
        "3 · Checklist",
        "4 · Gap assessment",
        "5 · Vendor risk",
        "6 · IR playbook",
        "7 · Audit report",
    ])

    with tab_policy:
        render_policy(company_profile)

    with tab_risk:
        render_risk(company_profile)

    with tab_checklist:
        render_checklist(company_profile)

    with tab_gap:
        render_gap(company_profile)

    with tab_vendor:
        render_vendor(company_profile)

    with tab_playbook:
        render_playbook(company_profile)

    with tab_report:
        render_report(company_profile)

    # =============================================================
    # FOOTER
    # =============================================================

    st.markdown(
        f'''
        <div class="grc-footer">
            <span class="grc-footer-text">AI GRC Audit Suite — Phase 1: Saudi Arabia</span>
            <span class="grc-footer-text">v{APP_VERSION}</span>
        </div>
        ''',
        unsafe_allow_html=True,
    )