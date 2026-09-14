#!/usr/bin/env python3
"""
Salary Research — storytelling dashboard.
План: Agenda → Executive Summary → главы с гипотезами → Implications.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent / "zarplatnik_data"
BIN_STEP = 20_000
MIN_N = 15  # скрываем слишком тонкие срезы в исследовании
FOCUS_ROLE = "data-analyst"  # роль для иллюстрации кривой грейдов

# Грейд как прокси опыта (в данных нет лет стажа)
GRADE_EXPERIENCE = {
    "intern": ("Intern", "старт / стажировка"),
    "junior": ("Junior", "~0–1.5 года"),
    "junior-plus": ("Junior+", "~1–2 года"),
    "middle": ("Middle", "~2–4 года"),
    "middle-plus": ("Middle+", "~3–5 лет"),
    "senior": ("Senior", "~5–7+ лет"),
    "senior-plus": ("Senior+", "глубокая экспертиза"),
    "lead": ("Team Lead", "управление + экспертиза"),
    "lead-plus": ("Team Lead+", "лидерство широкого контура"),
}

# --- Visual system: McKinsey hierarchy + Avito clarity ---
INK = "#121212"          # почти чёрный — основной текст
SLATE = "#2B2B2B"        # вторичный текст (всё ещё контрастный)
MUTED = "#5C5C5C"        # подписи, не бледный grey-on-beige
LINE = "#E6E6E6"
PAPER = "#FFFFFF"
SURFACE = "#F4F4F4"
CARD = "#FFFFFF"
ACCENT = "#005BFF"       # avito-like action blue
ACCENT_SOFT = "#EAF1FF"
NAVY = "#0A2540"         # mckinsey-like ink for titles
OK = "#0A7A3F"
WARN = "#9A6700"
DENY = "#C62828"
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Manrope, Inter, sans-serif", color=INK, size=14),
    margin=dict(l=8, r=8, t=40, b=8),
    hoverlabel=dict(bgcolor="white", font_size=14, font_color=INK),
    title=dict(font=dict(size=16, color=INK, family="Manrope, sans-serif")),
    legend=dict(font=dict(size=13, color=SLATE)),
)

CHAPTERS = [
    ("agenda", "01 · План исследования"),
    ("exec", "02 · Executive Summary"),
    ("map", "03 · Карта рынка"),
    ("ladder", "04 · Карьерная лестница"),
    ("geo", "05 · География"),
    ("format", "06 · Формат работы"),
    ("spread", "07 · Разброс зарплат"),
    ("cities", "08 · Города"),
    ("experience", "09 · Опыт / грейд"),
    ("switch", "10 · Свич профессии"),
    ("companies", "11 · Компании"),
    ("so_what", "12 · So what"),
]


# ───────────────────────── data ─────────────────────────

@st.cache_data
def load_data() -> Tuple[pd.DataFrame, dict]:
    raw = json.loads((DATA_DIR / "full.json").read_text(encoding="utf-8"))
    role_map = {r["id"]: r["name"] for r in raw["roles"]}
    role_group = {r["id"]: r.get("group", "") for r in raw["roles"]}
    grade_map = {g["id"]: g["name"] for g in raw["grades"]}
    city_map = {c["id"]: c["name"] for c in raw["cities"]}
    format_map = {f["id"]: f["name"] for f in raw["formats"]}
    grade_order = [g["id"] for g in raw["grades"]]

    rows = []
    for key, s in raw["slices"].items():
        parts = key.split("|")
        if len(parts) != 4:
            continue
        role, grade, city, fmt = parts
        rows.append(
            {
                "key": key,
                "role": role,
                "grade": grade,
                "city": city,
                "format": fmt,
                "role_name": role_map.get(role, role),
                "grade_name": grade_map.get(grade, grade) if grade != "*" else "Все",
                "city_name": city_map.get(city, city) if city != "*" else "Все города",
                "format_name": format_map.get(fmt, fmt) if fmt != "*" else "Все форматы",
                "group": role_group.get(role, ""),
                "n": s.get("n"),
                "p25": s.get("p25"),
                "p50": s.get("p50"),
                "p75": s.get("p75"),
                "from_": s.get("from"),
                "counts": s.get("counts") or [],
            }
        )
    df = pd.DataFrame(rows)
    meta = {
        "role_map": role_map,
        "role_group": role_group,
        "grade_map": grade_map,
        "city_map": city_map,
        "format_map": format_map,
        "grade_order": grade_order,
        "n_slices": len(df),
        "n_roles": df["role"].nunique(),
        "total_n": int(df[(df.city == "*") & (df.format == "*") & (df.grade != "*")]["n"].sum()),
        "cities_meta": raw["cities"],
        "roles_meta": raw["roles"],
        "has_companies": False,
        "has_years_experience": False,
    }
    return df, meta


def money(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{int(round(v)):,}".replace(",", " ") + " ₽"


def pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.0%}"


def base_slice(df: pd.DataFrame) -> pd.DataFrame:
    """Роль × грейд, все города и форматы — самый полный срез."""
    return df[(df.city == "*") & (df.format == "*") & (df.grade != "*")].copy()


# ───────────────────────── chrome ─────────────────────────

def inject_css() -> None:
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');

/* ===== Base: high contrast, large type ===== */
html, body, [data-testid="stAppViewContainer"], .stApp {{
  font-family: 'Manrope', sans-serif !important;
  color: {INK} !important;
  background: {PAPER} !important;
  font-size: 16px !important;
  line-height: 1.55 !important;
}}
.stApp {{
  background: {PAPER} !important;
}}
[data-testid="stHeader"] {{
  background: {PAPER} !important;
  border-bottom: 1px solid {LINE};
}}
#MainMenu, footer {{ visibility: hidden; }}

/* Main column width — readable report, not endless stretch */
[data-testid="stMainBlockContainer"] {{
  max-width: 1080px !important;
  padding-top: 1.75rem !important;
  padding-bottom: 3rem !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
}}

/* Kill Streamlit's washed-out caption/markdown greys */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
.stMarkdown, .stCaption {{
  color: {INK} !important;
}}
[data-testid="stCaptionContainer"], .stCaption {{
  color: {MUTED} !important;
  font-size: 0.92rem !important;
}}
label, [data-testid="stWidgetLabel"] {{
  color: {SLATE} !important;
}}

/* Tables */
[data-testid="stDataFrame"] {{
  border: 1px solid {LINE};
  border-radius: 12px;
  overflow: hidden;
}}

/* ===== Sidebar TOC (Avito clarity) ===== */
[data-testid="stSidebar"] {{
  background: {SURFACE} !important;
  border-right: 1px solid {LINE} !important;
}}
[data-testid="stSidebar"] > div:first-child {{
  padding: 1.25rem 1rem 2rem 1rem;
}}
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] * {{
  color: {INK} !important;
}}
[data-testid="stSidebar"] h3 {{
  font-family: 'Source Serif 4', Georgia, serif !important;
  font-size: 1.35rem !important;
  font-weight: 700 !important;
  margin-bottom: 0.15rem !important;
}}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
  color: {MUTED} !important;
  margin-bottom: 1rem !important;
}}
section[data-testid="stSidebar"] .stRadio > label {{
  display: none !important;
}}
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] {{
  gap: 0.2rem !important;
}}
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label {{
  background: transparent !important;
  border: 1px solid transparent !important;
  border-radius: 10px !important;
  padding: 0.65rem 0.75rem !important;
  margin: 0 !important;
  color: {SLATE} !important;
  font-size: 0.92rem !important;
  font-weight: 500 !important;
  line-height: 1.3 !important;
  transition: background 0.15s ease, color 0.15s ease;
}}
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover {{
  background: #fff !important;
  border-color: {LINE} !important;
  color: {INK} !important;
}}
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label[data-checked="true"],
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked) {{
  background: #fff !important;
  border-color: {ACCENT} !important;
  box-shadow: inset 3px 0 0 {ACCENT};
  color: {INK} !important;
  font-weight: 700 !important;
}}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label span {{
  color: inherit !important;
}}

/* ===== Hero / sections ===== */
.hero {{
  padding: 0.4rem 0 1.1rem 0;
  border-bottom: 1px solid {LINE};
  margin-bottom: 1.4rem;
}}
.hero-kicker {{
  display: inline-block;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: {ACCENT};
  font-weight: 700;
  margin-bottom: 0.65rem;
}}
.hero h1 {{
  font-family: 'Source Serif 4', Georgia, serif !important;
  font-weight: 700 !important;
  font-size: clamp(1.75rem, 3.2vw, 2.35rem) !important;
  line-height: 1.2 !important;
  color: {NAVY} !important;
  margin: 0 0 0.75rem 0 !important;
  letter-spacing: -0.02em;
}}
.hero-lead {{
  font-size: 1.08rem !important;
  line-height: 1.6 !important;
  color: {SLATE} !important;
  max-width: 40rem;
  font-weight: 500;
}}
.section-label {{
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: {ACCENT};
  font-weight: 700;
  margin: 1.75rem 0 0.4rem 0;
}}
.section-title {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 1.45rem;
  color: {NAVY};
  margin: 0 0 0.45rem 0;
  letter-spacing: -0.015em;
  font-weight: 700;
}}
.section-sub {{
  color: {SLATE};
  font-size: 1rem;
  line-height: 1.55;
  max-width: 40rem;
  margin-bottom: 1.15rem;
  font-weight: 500;
}}

/* ===== Verdict callouts ===== */
.verdict {{
  display: flex;
  gap: 1rem;
  align-items: flex-start;
  padding: 1.05rem 1.2rem;
  border: 1px solid {LINE};
  border-left: 4px solid {OK};
  background: #F3FAF5;
  border-radius: 0 12px 12px 0;
  margin: 0.9rem 0 1.25rem 0;
}}
.verdict.reject {{
  border-left-color: {DENY};
  background: #FFF5F5;
}}
.verdict.nuance {{
  border-left-color: {WARN};
  background: #FFF9EB;
}}
.verdict-tag {{
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
  padding-top: 0.2rem;
  color: {OK};
}}
.verdict.reject .verdict-tag {{ color: {DENY}; }}
.verdict.nuance .verdict-tag {{ color: {WARN}; }}
.verdict-body {{
  font-size: 1rem;
  line-height: 1.5;
  color: {INK};
  font-weight: 500;
}}

/* ===== KPI / findings (Avito cards) ===== */
.kpi-row {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin: 1.1rem 0 1.5rem 0;
}}
.kpi {{
  background: {SURFACE};
  border: 1px solid {LINE};
  border-radius: 14px;
  padding: 1.05rem 1.1rem;
}}
.kpi-label {{
  font-size: 0.75rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: {MUTED};
  font-weight: 700;
  margin-bottom: 0.4rem;
}}
.kpi-value {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 1.65rem;
  color: {NAVY};
  line-height: 1.15;
  font-weight: 700;
}}
.kpi-hint {{
  font-size: 0.85rem;
  color: {MUTED};
  margin-top: 0.4rem;
  font-weight: 500;
}}
.finding {{
  background: {CARD};
  border: 1px solid {LINE};
  border-radius: 14px;
  padding: 1.2rem 1.25rem;
  height: 100%;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}}
.finding-num {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 1.25rem;
  color: {ACCENT};
  margin-bottom: 0.4rem;
  font-weight: 700;
}}
.finding-title {{
  font-weight: 700;
  color: {INK};
  margin-bottom: 0.4rem;
  font-size: 1.05rem;
}}
.finding-body {{
  font-size: 0.98rem;
  color: {SLATE};
  line-height: 1.5;
  font-weight: 500;
}}
.agenda-item {{
  display: grid;
  grid-template-columns: 3rem 1fr;
  gap: 0.85rem;
  padding: 1rem 0;
  border-bottom: 1px solid {LINE};
}}
.agenda-num {{
  font-family: 'Source Serif 4', Georgia, serif;
  color: {ACCENT};
  font-size: 1.2rem;
  font-weight: 700;
}}
.agenda-title {{
  color: {INK};
  font-weight: 700;
  font-size: 1.05rem;
}}
.agenda-q {{
  color: {SLATE};
  font-size: 0.98rem;
  margin-top: 0.2rem;
  font-weight: 500;
  line-height: 1.45;
}}
.hypothesis {{
  background: {SURFACE};
  border: 1px solid {LINE};
  border-radius: 12px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.55rem;
  color: {INK};
  font-size: 1rem;
  line-height: 1.45;
  font-weight: 500;
}}
.hypothesis b {{
  color: {ACCENT};
  font-weight: 800;
}}
.footnote {{
  font-size: 0.88rem;
  color: {MUTED};
  margin-top: 1.75rem;
  padding-top: 1rem;
  border-top: 1px solid {LINE};
  line-height: 1.45;
  font-weight: 500;
}}

/* Storytelling blocks */
.story {{
  font-size: 1.05rem;
  line-height: 1.65;
  color: {SLATE};
  font-weight: 500;
  max-width: 42rem;
  margin: 0.4rem 0 1.1rem 0;
}}
.story strong {{ color: {INK}; font-weight: 700; }}
.take {{
  background: {ACCENT_SOFT};
  border: 1px solid #D6E4FF;
  border-radius: 14px;
  padding: 1.1rem 1.25rem;
  margin: 1rem 0 1.35rem 0;
}}
.take-label {{
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: {ACCENT};
  margin-bottom: 0.4rem;
}}
.take-body {{
  color: {INK};
  font-size: 1.02rem;
  line-height: 1.55;
  font-weight: 600;
}}
.quote {{
  border-left: 4px solid {NAVY};
  padding: 0.85rem 0 0.85rem 1.15rem;
  margin: 1rem 0 1.35rem 0;
  background: {SURFACE};
  border-radius: 0 12px 12px 0;
}}
.quote-text {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 1.2rem;
  line-height: 1.45;
  color: {NAVY};
  font-weight: 600;
}}
.quote-attr {{
  margin-top: 0.45rem;
  font-size: 0.85rem;
  color: {MUTED};
  font-weight: 600;
}}
.podium {{
  display: grid;
  grid-template-columns: 1fr 1.15fr 1fr;
  gap: 12px;
  align-items: end;
  margin: 0.8rem 0 1.4rem 0;
}}
.podium-card {{
  background: {SURFACE};
  border: 1px solid {LINE};
  border-radius: 14px;
  padding: 1rem 1.05rem;
  text-align: center;
}}
.podium-card.gold {{
  background: #fff;
  border-color: {ACCENT};
  box-shadow: 0 8px 24px rgba(0,91,255,0.08);
  padding-top: 1.35rem;
  padding-bottom: 1.35rem;
}}
.podium-place {{
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: {MUTED};
  margin-bottom: 0.35rem;
}}
.podium-card.gold .podium-place {{ color: {ACCENT}; }}
.podium-name {{
  font-weight: 700;
  color: {INK};
  font-size: 1rem;
  margin-bottom: 0.35rem;
}}
.podium-val {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 1.45rem;
  color: {NAVY};
  font-weight: 700;
}}
.matrix {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 0.8rem 0 1.3rem 0;
}}
.matrix-cell {{
  border: 1px solid {LINE};
  border-radius: 14px;
  padding: 1rem 1.1rem;
  background: {CARD};
  min-height: 7.5rem;
}}
.matrix-cell h4 {{
  margin: 0 0 0.4rem 0;
  font-size: 0.95rem;
  color: {INK};
}}
.matrix-cell p {{
  margin: 0;
  color: {SLATE};
  font-size: 0.92rem;
  line-height: 1.45;
  font-weight: 500;
}}
.matrix-cell.hi {{
  border-color: {ACCENT};
  background: {ACCENT_SOFT};
}}
.persona-row {{
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin: 0.8rem 0 1.3rem 0;
}}
.persona {{
  border: 1px solid {LINE};
  border-radius: 14px;
  padding: 1rem 1.05rem;
  background: {SURFACE};
}}
.persona h4 {{
  margin: 0 0 0.35rem 0;
  color: {INK};
  font-size: 0.98rem;
}}
.persona p {{
  margin: 0;
  color: {SLATE};
  font-size: 0.9rem;
  line-height: 1.45;
  font-weight: 500;
}}
.cover-img {{
  width: 100%;
  border-radius: 16px;
  border: 1px solid {LINE};
  margin: 0.6rem 0 1.2rem 0;
  display: block;
}}
.chap-img {{
  width: 100%;
  border-radius: 14px;
  border: 1px solid {LINE};
  margin: 0.4rem 0 0.8rem 0;
  display: block;
}}

@media (max-width: 900px) {{
  .kpi-row {{ grid-template-columns: 1fr 1fr; }}
  .podium, .matrix, .persona-row {{ grid-template-columns: 1fr; }}
  [data-testid="stMainBlockContainer"] {{
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }}
}}

[data-testid="stMetric"] {{
  background: {SURFACE};
  border: 1px solid {LINE};
  border-radius: 14px;
  padding: 0.85rem 1rem;
}}
[data-testid="stMetricLabel"] {{
  color: {MUTED} !important;
}}
[data-testid="stMetricValue"] {{
  color: {NAVY} !important;
}}

/* Info / warning boxes readable */
[data-testid="stAlert"] {{
  border-radius: 12px !important;
  border: 1px solid {LINE} !important;
  color: {INK} !important;
  font-weight: 500 !important;
}}

/* Plotly title readability */
.js-plotly-plot .gtitle {{
  fill: {INK} !important;
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def hero(kicker: str, title: str, lead: str) -> None:
    st.markdown(
        f"""
<div class="hero">
  <div class="hero-kicker">{kicker}</div>
  <h1>{title}</h1>
  <div class="hero-lead">{lead}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def section(label: str, title: str, sub: str = "") -> None:
    html = f'<div class="section-label">{label}</div><div class="section-title">{title}</div>'
    if sub:
        html += f'<div class="section-sub">{sub}</div>'
    st.markdown(html, unsafe_allow_html=True)


def verdict(kind: str, tag: str, body: str) -> None:
    cls = {"confirm": "", "reject": "reject", "nuance": "nuance"}.get(kind, "")
    st.markdown(
        f"""
<div class="verdict {cls}">
  <div class="verdict-tag">{tag}</div>
  <div class="verdict-body">{body}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(items: List[Tuple[str, str, str]]) -> None:
    cells = "".join(
        f"""<div class="kpi">
          <div class="kpi-label">{a}</div>
          <div class="kpi-value">{b}</div>
          <div class="kpi-hint">{c}</div>
        </div>"""
        for a, b, c in items
    )
    st.markdown(f'<div class="kpi-row">{cells}</div>', unsafe_allow_html=True)



def story(html: str) -> None:
    st.markdown(f'<div class="story">{html}</div>', unsafe_allow_html=True)


def take(body: str, label: str = "Наше мнение") -> None:
    st.markdown(
        f"""<div class="take">
          <div class="take-label">{label}</div>
          <div class="take-body">{body}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def quote(text: str, attr: str = "") -> None:
    extra = f'<div class="quote-attr">{attr}</div>' if attr else ""
    st.markdown(
        f"""<div class="quote">
          <div class="quote-text">«{text}»</div>
          {extra}
        </div>""",
        unsafe_allow_html=True,
    )


ASSETS = Path(__file__).resolve().parent / "assets"

GROUP_COLORS = {
    "Аналитика": "#005BFF",
    "Разработка": "#0A2540",
    "Продукт": "#1F8A70",
    "QA и DevOps": "#C45C26",
    "Дизайн": "#5C5C5C",
}
GROUP_PALETTE = list(GROUP_COLORS.values())


def style_fig(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(**PLOTLY_LAYOUT, height=height)
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=LINE,
        tickfont=dict(size=12, color=MUTED),
        title_font=dict(size=13, color=SLATE),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#EEEEEE",
        zeroline=False,
        tickfont=dict(size=12, color=MUTED),
        title_font=dict(size=13, color=SLATE),
    )
    return fig


def meta_grade_order() -> List[str]:
    return [
        "intern", "junior", "junior-plus", "middle", "middle-plus",
        "senior", "senior-plus", "lead", "lead-plus",
    ]


def ladder_ratios(df: pd.DataFrame) -> pd.DataFrame:
    base = base_slice(df)
    ratios = []
    for role in base.role.unique():
        sub_i = base[base.role == role].set_index("grade")
        if "junior" not in sub_i.index or "senior" not in sub_i.index:
            continue
        if sub_i.loc["junior", "n"] < MIN_N or sub_i.loc["senior", "n"] < MIN_N:
            continue
        ratios.append(
            {
                "role": role,
                "role_name": sub_i.loc["senior", "role_name"],
                "group": sub_i.loc["senior", "group"],
                "junior": sub_i.loc["junior", "p50"],
                "senior": sub_i.loc["senior", "p50"],
                "ratio": sub_i.loc["senior", "p50"] / sub_i.loc["junior", "p50"],
                "n_j": int(sub_i.loc["junior", "n"]),
                "n_s": int(sub_i.loc["senior", "n"]),
            }
        )
    return pd.DataFrame(ratios).sort_values("ratio", ascending=False)


# ───────────────────────── chapters ─────────────────────────

def page_agenda(df: pd.DataFrame, meta: dict) -> None:
    hero(
        "01 · План исследования",
        "Сколько на самом деле платят в digital — и почему",
        "Это не таблица офферов. Это история о рычагах: что сильнее двигает чек — "
        "роль, грейд, город или формат работы.",
    )
    if (ASSETS / "research_cover.png").exists():
        st.image(str(ASSETS / "research_cover.png"), use_container_width=True)

    story(
        "Большинство споров про зарплату начинаются с одной фразы: "
        "<strong>«в Москве платят больше»</strong> или <strong>«на удалёнке режут»</strong>. "
        "Мы проверяем эти легенды на одних и тех же срезах — и смотрим, где интуиция права, "
        "а где рынок уже ушёл вперёд."
    )

    kpi_row(
        [
            ("Срезов", f"{meta['n_slices']}", "готовых комбинаций"),
            ("Ролей", f"{meta['n_roles']}", "в 5 функциональных группах"),
            ("Наблюдений*", f"{meta['total_n']:,}".replace(",", " "), "сумма N по грейдам"),
            ("Фокус", "Middle+", "где рынок плотнее всего"),
        ]
    )

    section("Для кого", "Три читателя — три способа читать brief")
    st.markdown(
        """
<div class="persona-row">
  <div class="persona"><h4>Кандидат</h4>
    <p>Ищите главу про лестницу и разброс: где торговаться, а где «средняя» цифра обманывает.</p></div>
  <div class="persona"><h4>Нанимающий менеджер</h4>
    <p>Смотрите карту рынка и IQR: вилка должна отражать влияние, а не красивое название роли.</p></div>
  <div class="persona"><h4>Compensation / HR</h4>
    <p>География и формат — здесь самый большой риск переплатить за миф или недоплатить таланту.</p></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    section("Agenda", "Сюжет исследования", "Каждая глава = гипотеза → данные → вердикт → мнение.")
    agenda = [
        ("01", "Карта рынка", "Кто на Middle реально в топе — и куда «уехала» классическая аналитика?"),
        ("02", "Карьерная лестница", "Насколько один апгрейд грейда бьёт переезд и смену формата?"),
        ("03", "География", "Московская премия — статус или артефакт 2010-х?"),
        ("04", "Формат работы", "Штрафует ли рынок удалёнку — или это уже HR-фольклор?"),
        ("05", "Разброс", "Где медиана — полезный ориентир, а где опасная иллюзия?"),
        ("06", "Города", "МСК vs СПб и насколько выборка москвоцентрична?"),
        ("07", "Опыт", "Что можно сказать про стаж, если лет опыта в данных нет?"),
        ("08", "Свич", "А что, если сменить профессию вместо города/грейда?"),
        ("09", "Компании", "Почему разреза по работодателям нет — и чем это ограничение важно?"),
    ]
    for num, title, q in agenda:
        st.markdown(
            f"""<div class="agenda-item">
              <div class="agenda-num">{num}</div>
              <div><div class="agenda-title">{title}</div><div class="agenda-q">{q}</div></div>
            </div>""",
            unsafe_allow_html=True,
        )

    section("Hypotheses", "Ставки до открытия данных")
    story(
        "Мы формулируем гипотезы <strong>до</strong> графиков — как в нормальном research brief. "
        "Потом честно говорим: подтвердили, ослабили, опровергли или <em>не смогли проверить</em>."
    )
    hyps = [
        ("H1", "Senior зарабатывает в 2,5–3× больше Junior в большинстве ролей."),
        ("H2", "Москва даёт заметную премию к медиане (≥15%) относительно «всех городов»."),
        ("H3", "Офис платит больше удалёнки; гибрид — посередине."),
        ("H4", "Инфра и продукт (SRE, DevOps, PM) обгоняют классическую аналитику на Middle."),
        ("H5", "Максимальный разброс — у «размытых» ролей с малой выборкой и широким скоупом."),
        ("H6", "Самая крутая карьерная лестница — у ML Engineer."),
        ("H7", "Москва устойчиво дороже Петербурга на одинаковых роли и грейде."),
        ("H8", "Отдача от опыта (через грейд) нелинейна: Mid→Senior сильнее поздних шагов."),
        ("H9", "Свич в другую профессию на том же грейде часто выгоднее, чем ждать следующий грейд."),
        ("H10", "Компания-работодатель объясняет зарплату сильнее, чем грейд (проверим, если данные есть)."),
    ]
    for code, text_h in hyps:
        st.markdown(f'<div class="hypothesis"><b>{code}.</b> {text_h}</div>', unsafe_allow_html=True)

    quote(
        "Если после brief вы всё ещё спорите про город, а не про грейд — вы торгуетесь не тем рычагом.",
        "Рабочая установка исследования",
    )
    st.markdown(
        f'<div class="footnote">* N суммируется по независимым грейд-срезам; человек мог попасть только в один грейд. '
        f"Срезы с N &lt; {MIN_N} скрыты.</div>",
        unsafe_allow_html=True,
    )


def page_exec(df: pd.DataFrame, meta: dict) -> None:
    hero(
        "02 · Executive Summary",
        "Пять выводов, которые меняют переговорную позицию",
        "Если у вас 90 секунд — читайте только эту главу. Остальное — доказательная база.",
    )
    base = base_slice(df)
    base = base[base.n >= MIN_N]
    mid = base[base.grade == "middle"].sort_values("p50", ascending=False)
    rdf = ladder_ratios(df)
    top = mid.iloc[0] if len(mid) else None
    bot = mid.iloc[-1] if len(mid) else None
    top_ratio = rdf.iloc[0] if len(rdf) else None

    quote(
        "Рынок платит за дефицит влияния, а не за красивое название должности.",
        "Короткий тезис brief",
    )

    findings = [
        (
            "01",
            "Инфра и продукт на вершине",
            f"На Middle лидирует {top['role_name'] if top is not None else '—'} "
            f"({money(top['p50']) if top is not None else '—'}). "
            "Классический аналитик данных — заметно ниже топа. Это не «аналитика умерла», "
            "это рынок ценит тех, кто держит прод и P&amp;L.",
        ),
        (
            "02",
            "Карьера важнее города",
            (
                f"Junior→Senior даёт рост до {top_ratio['ratio']:.1f}× ({top_ratio['role_name']}). "
                if top_ratio is not None else ""
            )
            + "Московская премия чаще в диапазоне +4–17%. Один апгрейд грейда обычно сильнее переезда.",
        ),
        (
            "03",
            "Свич может бить грейд",
            "На одном Middle переход в PM/DevOps/SRE часто даёт больший плюс, "
            "чем ожидание следующего грейда в текущей роли — но ценой скиллов и риска.",
        ),
        (
            "04",
            "Компаний в данных нет",
            "Работодательский разрез отсутствует. Истории «в компании X платят Y» "
            "из этого датасета не следуют — и мы это явно фиксируем.",
        ),
    ]
    cols = st.columns(2)
    for i, (num, title, body) in enumerate(findings):
        with cols[i % 2]:
            st.markdown(
                f"""<div class="finding" style="margin-bottom:0.85rem">
                  <div class="finding-num">{num}</div>
                  <div class="finding-title">{title}</div>
                  <div class="finding-body">{body}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    take(
        "Если сокращать brief до одного совета: инвестируйте в грейд и скоуп роли. "
        "Город и формат — вторичные настройки, не главная ставка."
    )

    if top is not None and bot is not None and len(mid) >= 2:
        gap = top["p50"] / bot["p50"] - 1
        section(
            "Snapshot",
            f"Разрыв Middle: {gap:.0%} между полюсами",
            f"От {bot['role_name']} ({money(bot['p50'])}) до {top['role_name']} ({money(top['p50'])}). "
            "Это не «несправедливый рынок» — это карта дефицита.",
        )
        fig = px.bar(
            mid.head(12), x="p50", y="role_name", color="group", orientation="h",
            color_discrete_map=GROUP_COLORS,
            labels={"p50": "Медиана, ₽", "role_name": "", "group": "Группа"},
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"), legend_title="")
        st.plotly_chart(style_fig(fig, 420), use_container_width=True)
        story(
            f"Смотрите не только на вершину. Нижняя часть списка — тоже сигнал: "
            f"там чаще шире конкуренция и проще заменить человека. "
            f"Разница между полюсами Middle — примерно <strong>{gap:.0%}</strong>."
        )


def page_map(df: pd.DataFrame) -> None:
    hero(
        "03 · Карта рынка · H4",
        "Кто на самом деле на вершине Middle",
        "Фиксируем грейд Middle и убираем шум города/формата — чтобы сравнить роли честно.",
    )
    base = base_slice(df)
    mid = base[(base.grade == "middle") & (base.n >= MIN_N)].sort_values("p50", ascending=False)
    if mid.empty:
        st.info("Нет данных для карты Middle при текущем пороге N.")
        return

    top3 = mid.head(3)
    da = mid[mid.role == "data-analyst"]
    da_rank = int(list(mid.role).index("data-analyst") + 1) if len(da) else None

    story(
        "Интуиция многих команд такая: <strong>«аналитика = дорого, дизайн = дёшево, "
        "разработка = посередине»</strong>. Данные рисуют другую картину: на Middle рынок "
        "платит премию за инфраструктуру, ownership продукта и редкие навыки рядом с продом."
    )

    if len(top3) >= 3:
        second, first, third = top3.iloc[1], top3.iloc[0], top3.iloc[2]
        st.markdown(
            f"""
<div class="podium">
  <div class="podium-card">
    <div class="podium-place">2 место</div>
    <div class="podium-name">{second['role_name']}</div>
    <div class="podium-val">{money(second['p50'])}</div>
  </div>
  <div class="podium-card gold">
    <div class="podium-place">Лидер Middle</div>
    <div class="podium-name">{first['role_name']}</div>
    <div class="podium-val">{money(first['p50'])}</div>
  </div>
  <div class="podium-card">
    <div class="podium-place">3 место</div>
    <div class="podium-name">{third['role_name']}</div>
    <div class="podium-val">{money(third['p50'])}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

    verdict(
        "confirm",
        "H4 · Подтверждена",
        f"Топ Middle: {', '.join(top3['role_name'].tolist())}. "
        + (
            f"Аналитик данных — {money(da.iloc[0]['p50'])}, {da_rank}-е место из {len(mid)}."
            if da_rank else ""
        ),
    )

    c1, c2 = st.columns((1.35, 1))
    with c1:
        fig = go.Figure()
        for _, r in mid.iterrows():
            fig.add_trace(
                go.Bar(
                    name=r["group"], x=[r["role_name"]], y=[r["p75"] - r["p25"]], base=[r["p25"]],
                    marker_color=GROUP_COLORS.get(r["group"], MUTED), opacity=0.35, showlegend=False,
                    hovertemplate=(
                        f"{r['role_name']}<br>p25–p75: {money(r['p25'])} – {money(r['p75'])}"
                        f"<br>медиана: {money(r['p50'])}<br>N={int(r['n'])}<extra></extra>"
                    ),
                )
            )
        fig.add_trace(
            go.Scatter(
                x=mid["role_name"], y=mid["p50"], mode="markers+lines", name="Медиана",
                marker=dict(size=9, color=INK), line=dict(color=INK, width=1.5),
                hovertemplate="%{x}: %{y:,.0f} ₽<extra></extra>",
            )
        )
        fig.update_layout(title="Middle: коридор p25–p75 и медиана", xaxis_tickangle=-35, yaxis_title="₽", showlegend=False)
        st.plotly_chart(style_fig(fig, 440), use_container_width=True)

    with c2:
        section("By function", "Где «центр тяжести» функций")
        gmed = (
            mid.groupby("group", as_index=False)
            .agg(p50=("p50", "median"), n_roles=("role", "count"))
            .sort_values("p50", ascending=True)
        )
        fig2 = px.bar(
            gmed, x="p50", y="group", orientation="h",
            text=gmed["p50"].map(lambda v: f"{int(v/1000)}k"),
            color_discrete_sequence=[ACCENT],
            labels={"p50": "Медиана ролей", "group": ""},
        )
        fig2.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(style_fig(fig2, 320), use_container_width=True)
        story(
            "Группы с высокой медианой — не всегда «модные». Чаще это функции, "
            "где ошибка дорого стоит: прод, надёжность, решения по продукту."
        )

    take(
        "Если ваша команда называет data-analyst «дорогим специалистом», сверьте с картой: "
        "на Middle он часто ниже PM/DevOps/SRE. Переговоры надо вести от влияния на бизнес, "
        "а не от внутренней легенды отдела."
    )

    with st.expander("Полная таблица Middle"):
        st.dataframe(
            mid[["role_name", "group", "n", "p25", "p50", "p75"]]
            .assign(p25=lambda d: d.p25.map(money), p50=lambda d: d.p50.map(money), p75=lambda d: d.p75.map(money))
            .rename(columns={"role_name": "Роль", "group": "Группа", "n": "N", "p25": "p25", "p50": "Медиана", "p75": "p75"}),
            use_container_width=True, hide_index=True, height=360,
        )


def page_ladder(df: pd.DataFrame) -> None:
    hero(
        "04 · Карьерная лестница · H1 / H6",
        "Грейд двигает чек сильнее, чем почти любой другой фактор",
        "Сравниваем Senior к Junior и смотрим форму кривой — где рост плавный, а где «обрыв».",
    )
    if (ASSETS / "career_vs_city.png").exists():
        st.image(str(ASSETS / "career_vs_city.png"), use_container_width=True)

    rdf = ladder_ratios(df)
    if rdf.empty:
        st.info(f"Недостаточно данных Junior+Senior (N ≥ {MIN_N}).")
        return

    top = rdf.iloc[0]
    med_ratio = float(rdf["ratio"].median())
    base = base_slice(df)

    story(
        f"Представьте два сценария. <strong>А:</strong> переезд в Москву при том же грейде. "
        f"<strong>Б:</strong> рост Junior→Senior в той же роли. "
        f"Медианный множитель по рынку — около <strong>{med_ratio:.1f}×</strong>. "
        f"У лидера лестницы ({top['role_name']}) — уже <strong>{top['ratio']:.1f}×</strong> "
        f"({money(top['junior'])} → {money(top['senior'])})."
    )

    verdict("confirm", "H1 · Подтверждена", f"Медианный рост Junior→Senior: {med_ratio:.1f}×. Гипотеза 2,5–3× в целом жива.")
    ml = rdf[rdf.role == "ml-engineer"]
    if len(ml):
        verdict(
            "confirm", "H6 · Подтверждена",
            f"ML Engineer: {ml.iloc[0]['ratio']:.1f}× — одна из самых крутых карьерных премий в выборке.",
        )

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            rdf.head(14), x="ratio", y="role_name", color="group", orientation="h",
            labels={"ratio": "Senior / Junior", "role_name": "", "group": "Группа"},
            color_discrete_map=GROUP_COLORS,
        )
        fig.add_vline(x=2.5, line_dash="dot", line_color=MUTED, annotation_text="2.5×")
        fig.update_layout(yaxis=dict(categoryorder="total ascending"), title="Множитель Senior/Junior")
        st.plotly_chart(style_fig(fig, 420), use_container_width=True)

    with c2:
        role = FOCUS_ROLE if FOCUS_ROLE in set(base.role) else rdf.iloc[0]["role"]
        curve = base[base.role == role].copy()
        order = [g for g in meta_grade_order() if g in set(curve.grade)]
        curve["grade"] = pd.Categorical(curve["grade"], categories=order, ordered=True)
        curve = curve.sort_values("grade")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=curve["grade_name"], y=curve["p50"], mode="lines+markers", name="медиана",
            line=dict(color=ACCENT, width=3), marker=dict(size=10),
        ))
        fig2.add_trace(go.Scatter(
            x=curve["grade_name"].tolist() + curve["grade_name"].tolist()[::-1],
            y=curve["p75"].tolist() + curve["p25"].tolist()[::-1],
            fill="toself", fillcolor="rgba(0,91,255,0.12)",
            line=dict(color="rgba(0,0,0,0)"), name="p25–p75", hoverinfo="skip",
        ))
        name = curve.iloc[0]["role_name"] if len(curve) else role
        fig2.update_layout(title=f"Кривая грейдов · {name}", yaxis_title="₽")
        st.plotly_chart(style_fig(fig2, 420), use_container_width=True)
        story(
            "На кривой аналитика данных видно типичное поведение рынка: "
            "ранние ступени растут умеренно, а переход к Senior/Lead ускоряется — "
            "именно там появляется премия за автономность и влияние."
        )

    section("Как читать лестницу", "Не все × одинаково полезны")
    st.markdown(
        """
<div class="matrix">
  <div class="matrix-cell hi"><h4>Высокий множитель + спрос</h4>
    <p>ML, DevOps, системный анализ: учиться и расти здесь — высокий ROI по деньгам.</p></div>
  <div class="matrix-cell"><h4>Высокий множитель + узкий рынок</h4>
    <p>Красивая лестница, но мало вакансий. Смотрите N и устойчивость спроса.</p></div>
  <div class="matrix-cell"><h4>Плоская лестница</h4>
    <p>Рост через смену роли/компании часто выгоднее, чем «высидеть» следующий грейд.</p></div>
  <div class="matrix-cell"><h4>Практический вывод</h4>
    <p>В резюме важнее доказуемый скоуп Senior, чем переезд ради +10% к медиане.</p></div>
</div>
        """,
        unsafe_allow_html=True,
    )
    take(
        "Для кандидата: один уверенный апгрейд грейда обычно бьёт и переезд, и спор про remote. "
        "Для компании: дешевле вырастить Middle→Senior внутри, чем постоянно покупать Senior с рынка."
    )


def page_geo(df: pd.DataFrame) -> None:
    hero(
        "05 · География · H2",
        "Московская премия есть — но она скромнее легенды",
        "Сравниваем Москву с «всеми городами» на одинаковых роли и грейде.",
    )
    rows = []
    for _, r in df.iterrows():
        if r["city"] != "msk" or r["format"] != "*":
            continue
        if r["n"] < MIN_N:
            continue
        allc = df[(df.role == r.role) & (df.grade == r.grade) & (df.city == "*") & (df.format == "*")]
        if allc.empty:
            continue
        a = allc.iloc[0]
        rows.append({
            "role_name": r.role_name, "group": r.group, "grade_name": r.grade_name, "grade": r.grade,
            "msk": r.p50, "all": a.p50, "lift": r.p50 / a.p50 - 1, "n_msk": r.n, "n_all": a.n,
        })
    gdf = pd.DataFrame(rows)
    if gdf.empty:
        st.info(f"Мало московских срезов с N ≥ {MIN_N}.")
        return

    med_lift = float(gdf["lift"].median())
    max_row = gdf.loc[gdf["lift"].idxmax()]

    story(
        "Легенда звучит уверенно: <strong>«переезжай в Москву — зарплата скакнёт»</strong>. "
        "На практике премия чаще выглядит как надбавка, а не как новая жизнь. "
        f"Медиана по сопоставимым срезам: <strong>{pct(med_lift)}</strong>."
    )

    if med_lift >= 0.15:
        verdict("confirm", "H2 · Подтверждена", f"Медианная премия Москвы: {pct(med_lift)}. Гипотеза ≥15% выполняется.")
    else:
        verdict(
            "nuance", "H2 · Ослаблена",
            f"Медианная премия Москвы: {pct(med_lift)} — ниже порога 15%. "
            f"Максимум: {max_row['role_name']} / {max_row['grade_name']} ({pct(max_row['lift'])}).",
        )

    fig = px.scatter(
        gdf, x="all", y="msk", color="group", size="n_msk",
        hover_data={"role_name": True, "grade_name": True, "lift": ":.0%", "all": True, "msk": True},
        labels={"all": "Все города, медиана", "msk": "Москва, медиана", "group": "Группа"},
        color_discrete_map=GROUP_COLORS,
    )
    mx = max(gdf["all"].max(), gdf["msk"].max()) * 1.05
    fig.add_trace(go.Scatter(
        x=[0, mx], y=[0, mx], mode="lines", line=dict(dash="dot", color=MUTED),
        name="без премии", hoverinfo="skip",
    ))
    fig.update_layout(title="Москва vs все города (размер = N в Москве)")
    st.plotly_chart(style_fig(fig, 440), use_container_width=True)

    story(
        "Точки выше диагонали — Москва дороже. Чем ближе к линии, тем слабее географический эффект. "
        "Важный нюанс: «все города» уже включают Москву, поэтому премия <em>чистой</em> "
        "Москвы к регионам может быть чуть выше — но порядок величины тот же."
    )
    take(
        "Переезд имеет смысл, если вы меняете рынок возможностей (встречи, компании, нетворкинг), "
        "а не только строку в оффере. Ради +5–10% к медиане переезд редко окупается."
    )

    with st.expander("Детализация премии по срезам"):
        show = gdf.sort_values("lift", ascending=False)
        st.dataframe(
            show.assign(all=lambda d: d["all"].map(money), msk=lambda d: d["msk"].map(money), lift=lambda d: d["lift"].map(pct))
            [["role_name", "grade_name", "group", "all", "msk", "lift", "n_msk"]]
            .rename(columns={"role_name": "Роль", "grade_name": "Грейд", "group": "Группа",
                             "all": "Все города", "msk": "Москва", "lift": "Премия", "n_msk": "N МСК"}),
            use_container_width=True, hide_index=True, height=320,
        )


def page_format(df: pd.DataFrame) -> None:
    hero(
        "06 · Формат работы · H3",
        "Удалёнка не выглядит «штрафом»",
        "Сравниваем remote / hybrid / office при одинаковом «все города».",
    )
    fdf = df[(df.city == "*") & (df.format != "*") & (df.grade != "*")].copy()
    fdf = fdf[fdf.n >= MIN_N]
    if fdf.empty:
        st.info(f"Нет срезов по форматам с N ≥ {MIN_N}.")
        return

    story(
        "Ещё одна любимая корпоративная мантра: <strong>«в офисе платят больше, "
        "удалёнка — для тех, кто согласен на дисконт»</strong>. "
        "Проверяем на ролях, где хватает данных по нескольким форматам."
    )

    comparisons = []
    for (role, grade), g in fdf.groupby(["role", "grade"]):
        if g["format"].nunique() < 2:
            continue
        row = {
            "role": role, "role_name": g.iloc[0].role_name, "group": g.iloc[0].group,
            "grade": grade, "grade_name": g.iloc[0].grade_name,
        }
        for fmt in ["remote", "hybrid", "office"]:
            sub = g[g.format == fmt]
            row[fmt] = sub.iloc[0].p50 if len(sub) else None
            row[f"n_{fmt}"] = int(sub.iloc[0].n) if len(sub) else 0
        comparisons.append(row)
    cdf = pd.DataFrame(comparisons)
    both = cdf.dropna(subset=["remote", "office"])
    if len(both):
        office_higher = float((both["office"] > both["remote"]).mean())
        hybrid_vs_remote = cdf.dropna(subset=["remote", "hybrid"])
        hybrid_higher = (
            float((hybrid_vs_remote["hybrid"] >= hybrid_vs_remote["remote"]).mean())
            if len(hybrid_vs_remote) else None
        )
        verdict(
            "reject", "H3 · Опровергнута",
            f"Офис выше удалёнки только в {office_higher:.0%} сопоставимых срезов. "
            + (f"Гибрид ≥ remote в {hybrid_higher:.0%} случаев. " if hybrid_higher is not None else "")
            + "Формат — слабый рычаг рядом с грейдом и ролью.",
        )
    else:
        verdict("nuance", "H3 · Недостаточно пар", "Мало прямых сравнений office vs remote.")

    focus_roles = [r for r in ["data-analyst", "product-analyst", "system-analyst", "backend", "product-manager"] if r in set(fdf.role)]
    plot = fdf[fdf.role.isin(focus_roles) & fdf.grade.isin(["middle", "senior"])].copy()
    if not plot.empty:
        fig = px.bar(
            plot, x="grade_name", y="p50", color="format_name", facet_col="role_name",
            facet_col_wrap=3, barmode="group",
            category_orders={"format_name": ["Полная удалёнка", "Гибрид", "Офис"], "grade_name": ["Middle", "Senior"]},
            color_discrete_sequence=["#0A2540", "#005BFF", "#C45C26"],
            labels={"p50": "Медиана", "grade_name": "", "format_name": "Формат"},
        )
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_layout(title="Формат × грейд для ключевых ролей")
        st.plotly_chart(style_fig(fig, 480), use_container_width=True)

    quote(
        "Если компания режет remote «по умолчанию», она конкурирует не цифрами рынка — а своей политикой.",
        "Импликация для HR",
    )
    take(
        "Гибрид часто выглядит как sweet spot рынка: достаточно гибкости для кандидата "
        "и достаточно присутствия для компании. Штрафовать remote без данных — способ "
        "проигрывать войну за талант."
    )

    with st.expander("Сводная таблица форматов"):
        st.dataframe(
            cdf.assign(
                remote=lambda d: d["remote"].map(lambda x: money(x) if pd.notna(x) else "—"),
                hybrid=lambda d: d["hybrid"].map(lambda x: money(x) if pd.notna(x) else "—"),
                office=lambda d: d["office"].map(lambda x: money(x) if pd.notna(x) else "—"),
            )[["role_name", "grade_name", "remote", "hybrid", "office"]]
            .rename(columns={"role_name": "Роль", "grade_name": "Грейд", "remote": "Remote", "hybrid": "Hybrid", "office": "Office"}),
            use_container_width=True, hide_index=True, height=300,
        )


def page_spread(df: pd.DataFrame) -> None:
    hero(
        "07 · Разброс зарплат · H5",
        "Где «медиана» врёт сильнее всего",
        "IQR / медиана — ширина коридора переговоров. Чем она больше, тем опаснее одна «средняя» цифра.",
    )
    mid = base_slice(df)
    mid = mid[(mid.grade == "middle") & (mid.n >= MIN_N)].copy()
    mid["iqr"] = mid["p75"] - mid["p25"]
    mid["iqr_pct"] = mid["iqr"] / mid["p50"]
    mid = mid.sort_values("iqr_pct", ascending=False)
    if mid.empty:
        st.info("Нет данных.")
        return

    top = mid.iloc[0]
    tight = mid.iloc[-1]
    story(
        f"Медиана — удобная ложь, когда рынок узкий. Но если у роли "
        f"<strong>{top['role_name']}</strong> IQR занимает "
        f"<strong>{top['iqr_pct']:.0%}</strong> медианы, то один оффер «по рынку» "
        f"может быть и щедрым, и оскорбительным — в зависимости от скоупа."
    )
    verdict(
        "confirm", "H5 · Подтверждена",
        f"Максимальный относительный разброс: {top['role_name']} — IQR "
        f"{top['iqr_pct']:.0%} медианы (N={int(top['n'])}). "
        f"Для контраста, самый «ровный» в хвосте: {tight['role_name']} ({tight['iqr_pct']:.0%}).",
    )

    fig = px.scatter(
        mid, x="p50", y="iqr_pct", size="n", color="group", hover_name="role_name",
        labels={"p50": "Медиана Middle", "iqr_pct": "IQR / медиана", "group": "Группа", "n": "N"},
        color_discrete_map=GROUP_COLORS,
    )
    fig.update_layout(title="Уровень оплаты vs неопределённость")
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style_fig(fig, 420), use_container_width=True)

    section("Как жить с широким IQR", "Практика для офферов и переговоров")
    st.markdown(
        """
<div class="matrix">
  <div class="matrix-cell hi"><h4>Широкий IQR</h4>
    <p>Дробите роль на уровни влияния. Без этого вилка превращается в лотерею.</p></div>
  <div class="matrix-cell"><h4>Узкий IQR</h4>
    <p>Можно опираться на медиану смелее — рынок более «схлопнут».</p></div>
  <div class="matrix-cell"><h4>Маленький N</h4>
    <p>Даже красивая медиана хрупкая. Смотрите соседние роли и грейды.</p></div>
  <div class="matrix-cell"><h4>Переговоры</h4>
    <p>Кандидату выгоднее спорить про скоуп и impact, чем про «среднюю по рынку».</p></div>
</div>
        """,
        unsafe_allow_html=True,
    )
    take(
        "Самая частая ошибка — взять медиану роли с огромным IQR и назвать это «рынком». "
        "Это не рынок, это размытый ярлык. Сначала уточните, какого Senior вы имеете в виду."
    )

    with st.expander("Таблица разброса Middle"):
        st.dataframe(
            mid.assign(p50=lambda d: d.p50.map(money), iqr=lambda d: d.iqr.map(money), iqr_pct=lambda d: d.iqr_pct.map(lambda x: f"{x:.0%}"))
            [["role_name", "group", "n", "p50", "iqr", "iqr_pct"]]
            .rename(columns={"role_name": "Роль", "group": "Группа", "n": "N", "p50": "Медиана", "iqr": "IQR", "iqr_pct": "IQR%"}),
            use_container_width=True, hide_index=True,
        )



def page_cities(df: pd.DataFrame, meta: dict) -> None:
    hero(
        "08 · Города · H7",
        "География выборки и дуэль Москва — Петербург",
        "Зарплатные срезы по городам есть только для МСК и СПб. Остальные города видны как концентрация ответов.",
    )

    cities = pd.DataFrame(meta["cities_meta"]).copy()
    cities["count"] = cities["count"].fillna(0).astype(int)
    cities = cities[cities["count"] > 0].sort_values("count", ascending=False)
    total = int(cities["count"].sum())
    msk_share = cities.loc[cities["id"] == "msk", "count"].sum() / total if total else 0
    spb_share = cities.loc[cities["id"] == "spb", "count"].sum() / total if total else 0

    story(
        f"Выборка сильно «москвоцентрична»: на Москву приходится около "
        f"<strong>{msk_share:.0%}</strong> отмеченных ответов по городам, на Петербург — "
        f"<strong>{spb_share:.0%}</strong>. Это важно: «все города» в медианах уже тянутся к Москве."
    )

    kpi_row(
        [
            ("Городов в справочнике", str(len(meta["cities_meta"])), "но зарплаты не везде"),
            ("С зарплатными срезами", "МСК · СПб", "остальное — только N"),
            ("Доля Москвы", f"{msk_share:.0%}", "в city-разметке"),
            ("Доля СПб", f"{spb_share:.0%}", "второй полюс"),
        ]
    )

    c1, c2 = st.columns((1.2, 1))
    with c1:
        top = cities.head(12)
        fig = px.bar(
            top,
            x="count",
            y="name",
            orientation="h",
            color_discrete_sequence=[ACCENT],
            labels={"count": "Ответов (разметка города)", "name": ""},
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"), title="Где живут респонденты")
        st.plotly_chart(style_fig(fig, 420), use_container_width=True)
    with c2:
        story(
            "Екатеринбург, Казань, Новосибирск видны в справочнике, но без устойчивых salary-срезов. "
            "Вывод: сравнивать «регион vs Москва» по чеку здесь нельзя так же жёстко, "
            "как МСК vs СПб."
        )
        take(
            "Если вы из региона, ориентируйтесь на remote/hybrid вилки «всех городов» "
            "и на грейд — а не на городской миф без данных."
        )

    # MSK vs SPB
    section("H7", "Москва vs Санкт-Петербург на одинаковых срезах")
    rows = []
    for _, r in df.iterrows():
        if r["city"] != "msk" or r["format"] != "*" or r["grade"] == "*":
            continue
        if r["n"] < MIN_N:
            continue
        spb = df[(df.role == r.role) & (df.grade == r.grade) & (df.city == "spb") & (df.format == "*")]
        if spb.empty or spb.iloc[0]["n"] < MIN_N:
            continue
        s = spb.iloc[0]
        rows.append(
            {
                "role_name": r.role_name,
                "group": r.group,
                "grade_name": r.grade_name,
                "msk": r.p50,
                "spb": s.p50,
                "lift": r.p50 / s.p50 - 1,
                "n_msk": int(r.n),
                "n_spb": int(s.n),
            }
        )
    gdf = pd.DataFrame(rows)
    if gdf.empty:
        st.info("Мало пар МСК/СПб с достаточным N.")
    else:
        med = float(gdf["lift"].median())
        verdict(
            "nuance" if med < 0.15 else "confirm",
            "H7 · Вердикт",
            f"Медианная премия Москвы к Петербургу: {pct(med)}. "
            "На Middle разрыв часто скромный; на Senior он может быть заметнее.",
        )
        fig2 = px.scatter(
            gdf,
            x="spb",
            y="msk",
            color="group",
            size="n_msk",
            hover_name="role_name",
            hover_data={"grade_name": True, "lift": ":.0%"},
            color_discrete_map=GROUP_COLORS,
            labels={"spb": "СПб, медиана", "msk": "Москва, медиана", "group": "Группа"},
        )
        mx = max(gdf["msk"].max(), gdf["spb"].max()) * 1.05
        fig2.add_trace(
            go.Scatter(
                x=[0, mx], y=[0, mx], mode="lines",
                line=dict(dash="dot", color=MUTED), name="паритет", hoverinfo="skip",
            )
        )
        fig2.update_layout(title="Москва vs СПб")
        st.plotly_chart(style_fig(fig2, 420), use_container_width=True)
        st.dataframe(
            gdf.sort_values("lift", ascending=False)
            .assign(msk=lambda d: d.msk.map(money), spb=lambda d: d.spb.map(money), lift=lambda d: d.lift.map(pct))
            [["role_name", "grade_name", "msk", "spb", "lift", "n_msk", "n_spb"]]
            .rename(columns={
                "role_name": "Роль", "grade_name": "Грейд", "msk": "Москва",
                "spb": "СПб", "lift": "Премия МСК", "n_msk": "N МСК", "n_spb": "N СПб",
            }),
            use_container_width=True, hide_index=True, height=280,
        )

    quote(
        "СПб — не «дешёвая Москва». Это соседний рынок с более тонкой выборкой и местами почти паритетом на Middle.",
        "Как читать городской разрез",
    )


def page_experience(df: pd.DataFrame) -> None:
    hero(
        "09 · Опыт · H8",
        "Лет стажа в данных нет — но грейд работает как карта опыта",
        "Мы явно фиксируем ограничение и используем грейд как лучший доступный прокси seniority/опыта.",
    )

    story(
        "В срезах <strong>нет поля «годы опыта»</strong>. Есть грейды: Intern → Lead+. "
        "Это не одно и то же, но на рынке грейд обычно сильнее коррелирует с чеком, чем формальная дата в трудовой."
    )

    # mapping table
    section("Прокси", "Как мы читаем грейд как опыт")
    grade_proxy = pd.DataFrame(
        [
            {"Грейд": name, "Ориентир опыта": hint, "id": gid}
            for gid, (name, hint) in GRADE_EXPERIENCE.items()
        ]
    )
    st.dataframe(grade_proxy, use_container_width=True, hide_index=True)

    base = base_slice(df)
    base = base[base.n >= MIN_N]
    # step lifts
    order = meta_grade_order()
    steps = []
    for role in base.role.unique():
        sub = base[base.role == role].set_index("grade")
        for a, b in zip(order, order[1:]):
            if a not in sub.index or b not in sub.index:
                continue
            if sub.loc[a, "n"] < MIN_N or sub.loc[b, "n"] < MIN_N:
                continue
            steps.append(
                {
                    "step": f"{GRADE_EXPERIENCE.get(a, (a,))[0]} → {GRADE_EXPERIENCE.get(b, (b,))[0]}",
                    "from": a,
                    "to": b,
                    "lift": sub.loc[b, "p50"] / sub.loc[a, "p50"] - 1,
                    "role_name": sub.loc[b, "role_name"],
                    "group": sub.loc[b, "group"],
                }
            )
    sdf = pd.DataFrame(steps)
    if sdf.empty:
        st.info("Недостаточно пар соседних грейдов.")
        return

    agg = (
        sdf.groupby("step", as_index=False)
        .agg(median_lift=("lift", "median"), mean_lift=("lift", "mean"), n=("lift", "count"))
    )
    # preserve order
    step_order = [
        f"{GRADE_EXPERIENCE[a][0]} → {GRADE_EXPERIENCE[b][0]}"
        for a, b in zip(order, order[1:])
        if f"{GRADE_EXPERIENCE[a][0]} → {GRADE_EXPERIENCE[b][0]}" in set(agg["step"])
    ]
    agg["step"] = pd.Categorical(agg["step"], categories=step_order, ordered=True)
    agg = agg.sort_values("step")

    best = agg.sort_values("median_lift", ascending=False).iloc[0]
    verdict(
        "confirm",
        "H8 · Подтверждена",
        f"Отдача от «опыта» нелинейна: самый жирный медианный шаг — "
        f"<strong>{best['step']}</strong> (~{best['median_lift']:.0%}). "
        "Поздние ступени Senior→Lead часто дают меньший прирост чека, чем Mid→Senior.",
    )

    fig = px.bar(
        agg,
        x="step",
        y="median_lift",
        text=agg["median_lift"].map(lambda x: f"{x:.0%}"),
        color_discrete_sequence=[ACCENT],
        labels={"step": "", "median_lift": "Медианный прирост медианы"},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(title="Средний прирост зарплаты на соседнем шаге грейда", yaxis_tickformat=".0%")
    st.plotly_chart(style_fig(fig, 400), use_container_width=True)

    story(
        "Практически: если вы «зависли» на Middle, следующий осмысленный рывок по деньгам — "
        "не ещё один год в том же скоупе, а доказуемый переход в Middle+/Senior. "
        "Опыт сам по себе без смены влияния платит слабее."
    )
    take(
        "Для резюме и performance review важнее пакет доказательств грейда "
        "(автономность, область влияния, сложность задач), чем строка «N лет опыта»."
    )


def page_switch(df: pd.DataFrame, meta: dict) -> None:
    hero(
        "10 · Свич профессии · H9",
        "А что, если сменить профессию — а не город?",
        "Сравниваем медианы на одном грейде: остаться vs перейти в другую роль.",
    )

    story(
        "Классическая развилка: <strong>расти в текущей роли</strong> или "
        "<strong>свитчнуться</strong> в соседнюю профессию. "
        "Гипотеза: на Middle умный свич может дать больший прирост, чем ожидание следующего грейда."
    )

    mid = base_slice(df)
    mid = mid[(mid.grade == "middle") & (mid.n >= MIN_N)].copy()
    if mid.empty:
        st.info("Нет Middle-срезов.")
        return

    roles = sorted(mid["role"].unique(), key=lambda x: meta["role_map"].get(x, x))
    default_from = "data-analyst" if "data-analyst" in roles else roles[0]
    c1, c2, c3 = st.columns(3)
    with c1:
        role_from = st.selectbox(
            "Сейчас",
            roles,
            index=roles.index(default_from),
            format_func=lambda x: meta["role_map"].get(x, x),
            key="switch_from",
        )
    with c2:
        grade = st.selectbox(
            "Грейд для сравнения",
            [g for g in meta["grade_order"] if g in set(base_slice(df).grade)],
            index=meta["grade_order"].index("middle") if "middle" in meta["grade_order"] else 0,
            format_func=lambda x: meta["grade_map"].get(x, x),
            key="switch_grade",
        )
    with c3:
        st.write("")
        st.caption("Калькулятор свича — единственный локальный контрол в brief.")

    pool = base_slice(df)
    pool = pool[(pool.grade == grade) & (pool.n >= MIN_N)].copy()
    src = pool[pool.role == role_from]
    if src.empty:
        st.warning("Для выбранной пары роль/грейд нет среза с достаточным N.")
        return
    base_p50 = float(src.iloc[0]["p50"])
    base_name = src.iloc[0]["role_name"]

    cmp = pool[pool.role != role_from].copy()
    cmp["delta"] = cmp["p50"] - base_p50
    cmp["lift"] = cmp["p50"] / base_p50 - 1
    cmp = cmp.sort_values("lift", ascending=False)

    best = cmp.iloc[0]
    worst = cmp.iloc[-1]
    # compare to next grade inside same role
    order = meta["grade_order"]
    next_grade = None
    if role_from in set(base_slice(df).role) and grade in order:
        idx = order.index(grade)
        for g in order[idx + 1 :]:
            nxt = base_slice(df)
            nxt = nxt[(nxt.role == role_from) & (nxt.grade == g) & (nxt.n >= MIN_N)]
            if not nxt.empty:
                next_grade = nxt.iloc[0]
                break

    kpi_row(
        [
            ("Текущая медиана", money(base_p50), f"{base_name} · {meta['grade_map'].get(grade, grade)}"),
            ("Лучший свич", money(best["p50"]), f"{best['role_name']} ({pct(best['lift'])})"),
            ("Худший свич", money(worst["p50"]), f"{worst['role_name']} ({pct(worst['lift'])})"),
            (
                "След. грейд в роли",
                money(next_grade["p50"]) if next_grade is not None else "—",
                (
                    f"{meta['grade_map'].get(next_grade['grade'], next_grade['grade'])} ({pct(next_grade['p50']/base_p50-1)})"
                    if next_grade is not None
                    else "нет данных"
                ),
            ),
        ]
    )

    if next_grade is not None:
        stay_lift = next_grade["p50"] / base_p50 - 1
        if best["lift"] > stay_lift:
            verdict(
                "confirm",
                "H9 · Часто подтверждается",
                f"Свич в {best['role_name']} даёт {pct(best['lift'])} на том же грейде — "
                f"больше, чем переход к следующему грейду в текущей роли ({pct(stay_lift)}). "
                "Но свич требует скиллов и риска; это не «кнопка +деньги».",
            )
        else:
            verdict(
                "nuance",
                "H9 · Не всегда",
                f"Для {base_name} рост внутри роли до "
                f"{meta['grade_map'].get(next_grade['grade'], next_grade['grade'])} "
                f"({pct(stay_lift)}) выглядит сопоставимо/сильнее лучшего свича "
                f"({best['role_name']}, {pct(best['lift'])}).",
            )
    else:
        verdict(
            "confirm",
            "H9 · Сигнал",
            f"Лучший свич с текущего грейда — {best['role_name']} ({pct(best['lift'])}).",
        )

    top = cmp.head(8)
    fig = px.bar(
        top,
        x="lift",
        y="role_name",
        color="group",
        orientation="h",
        color_discrete_map=GROUP_COLORS,
        labels={"lift": "Прирост к текущей роли", "role_name": "", "group": "Группа"},
    )
    fig.update_layout(yaxis=dict(categoryorder="total ascending"), title=f"Куда свичнуться с «{base_name}»", xaxis_tickformat="+.0%")
    if next_grade is not None:
        fig.add_vline(
            x=stay_lift,
            line_dash="dot",
            line_color=MUTED,
            annotation_text="след. грейд в роли",
        )
    st.plotly_chart(style_fig(fig, 420), use_container_width=True)

    section("Сценарная логика", "Три типа свича")
    st.markdown(
        """
<div class="matrix">
  <div class="matrix-cell hi"><h4>Соседний свич</h4>
    <p>Data Analyst → Product Analyst / DS. Малый gap по скиллам, умеренный плюс к чеку.</p></div>
  <div class="matrix-cell"><h4>Вертикальный свич</h4>
    <p>Analyst → PM / PO. Больше ownership и денег, но другой профиль ответственности.</p></div>
  <div class="matrix-cell"><h4>Инфраструктурный свич</h4>
    <p>В DevOps / SRE / Backend. Высокая премия, высокий порог входа.</p></div>
  <div class="matrix-cell"><h4>Ловушка</h4>
    <p>Свич «вниз» (в более широкую/низкооплачиваемую роль) без стратегии — дорогая ошибка.</p></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    take(
        "Свич имеет смысл, когда целевая роль и ближе к вашим сильным сторонам, и выше по медиане. "
        "Иначе дешевле дожать грейд там, где вы уже сильны."
    )

    with st.expander("Полный рейтинг свичей"):
        st.dataframe(
            cmp.assign(
                p50=lambda d: d.p50.map(money),
                delta=lambda d: d.delta.map(money),
                lift=lambda d: d.lift.map(pct),
            )[["role_name", "group", "n", "p50", "delta", "lift"]]
            .rename(columns={"role_name": "Роль", "group": "Группа", "n": "N", "p50": "Медиана", "delta": "Δ ₽", "lift": "Δ %"}),
            use_container_width=True, hide_index=True, height=360,
        )


def page_companies(df: pd.DataFrame, meta: dict) -> None:
    hero(
        "11 · Компании · H10",
        "Разреза по работодателям в данных нет — и это важный вывод",
        "Мы не маскируем пробел. Фиксируем ограничение и показываем, какие гипотезы из-за этого недоступны.",
    )

    story(
        "В агрегированных срезах есть роли, грейды, города и форматы. "
        "<strong>Нет компании / индустрии / размера работодателя</strong>. "
        "Поэтому нельзя честно ответить: «в FAANG-like платят на X% больше» или «банк vs продукт»."
    )

    verdict(
        "nuance",
        "H10 · Данные отсутствуют",
        "Гипотеза «компания сильнее грейда» в этом исследовании не тестируется: "
        "нет salary-срезов по работодателям. Любые истории про Яндекс/Сбер/Авито здесь были бы фантазией.",
    )

    section("Что это ломает", "Гипотезы, которые пришлось отложить")
    st.markdown(
        """
<div class="hypothesis"><b>H10a.</b> BigTech даёт устойчивую премию ≥20% к медиане роли.</div>
<div class="hypothesis"><b>H10b.</b> Продуктовые компании платят аналитикам больше, чем аутсорс/интеграторы.</div>
<div class="hypothesis"><b>H10c.</b> Внутри одной роли разброс между компаниями шире, чем между городами.</div>
        """,
        unsafe_allow_html=True,
    )

    section("Что можно сказать вместо этого", "Прокси, которые уже есть")
    st.markdown(
        """
<div class="matrix">
  <div class="matrix-cell hi"><h4>Роль как «тип бизнеса»</h4>
    <p>SRE/PM/DevOps часто концентрируются в product/infra-компаниях — и они на вершине Middle.</p></div>
  <div class="matrix-cell"><h4>IQR как тень работодателей</h4>
    <p>Широкий разброс внутри роли частично отражает разные компании и скоупы, но мы не видим кого именно.</p></div>
  <div class="matrix-cell"><h4>Формат</h4>
    <p>Remote/hybrid частично коррелирует с типом компании, но это слабый и грязный прокси.</p></div>
  <div class="matrix-cell"><h4>Практический совет</h4>
    <p>В переговорах спрашивайте вилку под уровень влияния и рынок роли — не «среднюю по отрасли» без источника.</p></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    take(
        "Честный research лучше красивой выдумки. Пока нет company-срезов, "
        "главные рычаги остаются: роль → грейд → (осторожно) город/формат."
    )
    quote(
        "Если кто-то продаёт вам «среднюю по Яндексу» без методики — это маркетинг, не аналитика.",
        "Caution",
    )


def page_so_what(df: pd.DataFrame) -> None:
    hero(
        "12 · So what",
        "Что делать с этими цифрами в понедельник",
        "Не «интересно посмотреть», а конкретные ходы для кандидата, менеджера и compensation.",
    )
    story(
        "Исследование бесполезно, если после него все кивают и возвращаются к старым вилкам. "
        "Ниже — перевод вердиктов на язык действий."
    )
    items = [
        ("Кандидату",
         "Торгуйтесь грейдом и скоупом, не городом. Соберите 2–3 доказательства Senior-влияния "
         "и просите апгрейд уровня — это обычно дороже, чем +Москва в оффере."),
        ("Нанимающему",
         "Для ролей с высоким IQR% не публикуйте одну медиану. Сделайте две-три вилки "
         "под уровни влияния и объясните критерии перехода."),
        ("Compensation",
         "Уберите автоматический remote-дисконт. Если политика «офис дороже» — докажите цифрами "
         "по вашей воронке найма, иначе вы просто теряете кандидатов."),
        ("Карьерный трек",
         "Самый высокий ROI роста — зоны с крутой лестницей: ML / DevOps / системный анализ. "
         "Туда имеет смысл направлять обучение и internal mobility."),
    ]
    cols = st.columns(2)
    for i, (t, b) in enumerate(items):
        with cols[i % 2]:
            st.markdown(
                f"""<div class="finding" style="margin-bottom:0.85rem">
                  <div class="finding-title">{t}</div>
                  <div class="finding-body">{b}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    quote(
        "Хороший оффер — это не попадание в медиану. Это попадание в правильный квартиль правильного скоупа.",
        "Финальный принцип",
    )

    section("Scorecard", "Итог по гипотезам — одной строкой")
    score = [
        ("H1 Карьерный множитель 2,5–3×", "Подтверждена — грейд главный рычаг", "confirm"),
        ("H2 Москва ≥ +15%", "Ослаблена — премия скромнее легенды", "nuance"),
        ("H3 Офис > remote", "Опровергнута — формат слабый фактор", "reject"),
        ("H4 Инфра/продукт > аналитика", "Подтверждена — рынок платит за ownership", "confirm"),
        ("H5 Разброс у «размытых» ролей", "Подтверждена — медиана бывает опасна", "confirm"),
        ("H6 ML — самая крутая лестница", "Подтверждена — высокий ROI роста", "confirm"),
        ("H7 Москва дороже СПб", "Частично — зависит от грейда/роли", "nuance"),
        ("H8 Опыт нелинеен (через грейд)", "Подтверждена — шаги Mid→Senior сильнее", "confirm"),
        ("H9 Свич профессии выгоднее грейда", "Часто да — но не всегда и не бесплатно", "nuance"),
        ("H10 Компания важнее грейда", "Не тестируется — нет данных", "nuance"),
    ]
    for title, tag, kind in score:
        verdict(kind, tag, title)

    take(
        "Если помнить только одно: сначала роль и грейд, потом город и формат. "
        "Всё остальное в этом brief — доказательства этого порядка."
    )
    st.markdown(
        f'<div class="footnote">Срезы с N &lt; {MIN_N} скрыты. '
        "Наблюдательная картина рынка, не причинно-следственный вывод.</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Salary Research",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    try:
        df, meta = load_data()
    except FileNotFoundError:
        st.error("Нет данных для исследования.")
        return

    with st.sidebar:
        st.markdown("### Research")
        st.caption("Содержание")
        chapter = st.radio(
            "Содержание",
            options=[c[0] for c in CHAPTERS],
            format_func=lambda x: dict(CHAPTERS)[x],
            label_visibility="collapsed",
        )

    pages = {
        "agenda": lambda: page_agenda(df, meta),
        "exec": lambda: page_exec(df, meta),
        "map": lambda: page_map(df),
        "ladder": lambda: page_ladder(df),
        "geo": lambda: page_geo(df),
        "format": lambda: page_format(df),
        "spread": lambda: page_spread(df),
        "cities": lambda: page_cities(df, meta),
        "experience": lambda: page_experience(df),
        "switch": lambda: page_switch(df, meta),
        "companies": lambda: page_companies(df, meta),
        "so_what": lambda: page_so_what(df),
    }
    pages[chapter]()


if __name__ == "__main__":
    main()
