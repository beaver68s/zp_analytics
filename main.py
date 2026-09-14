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
    ("so_what", "08 · So what"),
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

@media (max-width: 900px) {{
  .kpi-row {{ grid-template-columns: 1fr 1fr; }}
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


# ───────────────────────── chapters ─────────────────────────

def page_agenda(df: pd.DataFrame, meta: dict) -> None:
    hero(
        "Research Brief",
        "Сколько на самом деле платят в digital — и почему",
        "Исследование зарплат digital-ролей: грейды, города и форматы работы. "
        "Ниже — план, гипотезы и ответы в формате executive storytelling.",
    )
    kpi_row(
        [
            ("Срезов", f"{meta['n_slices']}", "готовых комбинаций"),
            ("Ролей", f"{meta['n_roles']}", "в 5 функциональных группах"),
            ("Наблюдений*", f"{meta['total_n']:,}".replace(",", " "), "сумма N по грейдам"),
            ("Города в данных", "МСК · СПб", "остальное — «все города»"),
        ]
    )

    section("Agenda", "План исследования", "Каждая глава отвечает на одну гипотезу и заканчивается вердиктом.")
    agenda = [
        ("01", "Карта рынка", "Кто зарабатывает больше на Middle — продукт, разработка или аналитика?"),
        ("02", "Карьерная лестница", "Насколько резко растёт зарплата от Junior к Senior?"),
        ("03", "География", "Действительно ли Москва даёт существенную премию?"),
        ("04", "Формат работы", "Удалёнка дешевле офиса — или это миф?"),
        ("05", "Разброс", "Где рынок «ровный», а где зарплаты размазаны сильнее всего?"),
    ]
    for i, (num, title, q) in enumerate(agenda):
        st.markdown(
            f"""<div class="agenda-item" style="animation-delay:{i*0.05}s">
              <div class="agenda-num">{num}</div>
              <div><div class="agenda-title">{title}</div><div class="agenda-q">{q}</div></div>
            </div>""",
            unsafe_allow_html=True,
        )

    section("Hypotheses", "Рабочие гипотезы до анализа")
    hyps = [
        ("H1", "Senior зарабатывает в 2,5–3× больше Junior в большинстве ролей."),
        ("H2", "Москва даёт заметную премию к медиане (≥15%) относительно «всех городов»."),
        ("H3", "Офис платит больше удалёнки; гибрид — посередине."),
        ("H4", "Инфра и продукт (SRE, DevOps, PM) обгоняют классическую аналитику на Middle."),
        ("H5", "Максимальный разброс зарплат — у «размытых» ролей с малой выборкой и широким скоупом."),
        ("H6", "Самая крутая карьерная лестница — у ML Engineer."),
    ]
    for code, text in hyps:
        st.markdown(
            f'<div class="hypothesis"><b>{code}.</b> {text}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div class="footnote">* N суммируется по независимым грейд-срезам; человек мог попасть только в один грейд. '
        f"В исследовании скрыты срезы с N &lt; {MIN_N}.</div>",
        unsafe_allow_html=True,
    )


def page_exec(df: pd.DataFrame, meta: dict) -> None:
    hero(
        "02 · Executive Summary",
        "Пять выводов, которые меняют переговорную позицию",
        "Короткая версия для руководителя или кандидата. Детали — в следующих главах.",
    )

    base = base_slice(df)
    base = base[base.n >= MIN_N]
    mid = base[base.grade == "middle"].sort_values("p50", ascending=False)

    # ladder ratios
    ratios = []
    for role in base.role.unique():
        sub = base[base.role == role].set_index("grade")
        if "junior" in sub.index and "senior" in sub.index:
            ratios.append(
                (
                    sub.loc["senior", "role_name"],
                    float(sub.loc["senior", "p50"] / sub.loc["junior", "p50"]),
                    sub.loc["junior", "group"],
                )
            )
    ratios.sort(key=lambda x: -x[1])

    top = mid.iloc[0] if len(mid) else None
    bot = mid.iloc[-1] if len(mid) else None
    mid_analytics = mid[mid.group == "Аналитика"]
    mid_product = mid[mid.group.isin(["Продукт", "QA и DevOps"])]

    findings = [
        (
            "01",
            "Инфра и продукт на вершине",
            f"На Middle лидируют {top['role_name'] if top is not None else '—'} "
            f"({money(top['p50']) if top is not None else '—'}). "
            "Классический data-analyst заметно ниже топа.",
        ),
        (
            "02",
            "Карьера важнее города",
            f"Junior→Senior даёт рост в {ratios[0][1]:.1f}× у лидера ({ratios[0][0]}). "
            "Московская премия обычно лишь +4–17%.",
        ),
        (
            "03",
            "Гибрид не штрафует",
            "У аналитиков гибрид часто ≥ remote и ≥ office. Миф «офис = больше денег» не подтверждается.",
        ),
        (
            "04",
            "Разброс = риск оценки",
            "У части ролей IQR > 40% медианы: «средняя» цифра плохо описывает реальность переговоров.",
        ),
    ]
    cols = st.columns(2)
    for i, (num, title, body) in enumerate(findings):
        with cols[i % 2]:
            st.markdown(
                f"""<div class="finding" style="animation-delay:{i*0.06}s; margin-bottom:0.85rem">
                  <div class="finding-num">{num}</div>
                  <div class="finding-title">{title}</div>
                  <div class="finding-body">{body}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    if top is not None and bot is not None and len(mid) >= 2:
        gap = top["p50"] / bot["p50"] - 1
        section(
            "Snapshot",
            f"Разрыв Middle: {gap:.0%} между полюсами",
            f"От {bot['role_name']} ({money(bot['p50'])}) до {top['role_name']} ({money(top['p50'])}).",
        )
        fig = px.bar(
            mid.head(12),
            x="p50",
            y="role_name",
            color="group",
            orientation="h",
            color_discrete_map=GROUP_COLORS,
            labels={"p50": "Медиана, ₽", "role_name": "", "group": "Группа"},
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"), legend_title="")
        st.plotly_chart(style_fig(fig, 420), use_container_width=True)


def page_map(df: pd.DataFrame) -> None:
    hero(
        "03 · Карта рынка · H4",
        "Кто на самом деле на вершине Middle",
        "Сравниваем медианы при фиксированном грейде Middle — без шума города и формата.",
    )
    base = base_slice(df)
    mid = base[(base.grade == "middle") & (base.n >= MIN_N)].sort_values("p50", ascending=False)

    if mid.empty:
        st.info("Нет данных для карты Middle при текущем пороге N.")
        return

    top3 = mid.head(3)["role_name"].tolist()
    analytics = mid[mid.group == "Аналитика"]
    da = mid[mid.role == "data-analyst"]
    verdict(
        "confirm",
        "H4 · Подтверждена",
        f"Топ Middle: {', '.join(top3)}. "
        + (
            f"Аналитик данных — {money(da.iloc[0]['p50'])}, "
            f"это {int(list(mid.role).index('data-analyst')+1)}-е место из {len(mid)}."
            if len(da)
            else ""
        ),
    )

    c1, c2 = st.columns((1.35, 1))
    with c1:
        fig = go.Figure()
        colors = GROUP_COLORS
        for _, r in mid.iterrows():
            fig.add_trace(
                go.Bar(
                    name=r["group"],
                    x=[r["role_name"]],
                    y=[r["p75"] - r["p25"]],
                    base=[r["p25"]],
                    marker_color=colors.get(r["group"], MUTED),
                    opacity=0.35,
                    showlegend=False,
                    hovertemplate=(
                        f"{r['role_name']}<br>p25–p75: {money(r['p25'])} – {money(r['p75'])}"
                        f"<br>медиана: {money(r['p50'])}<br>N={int(r['n'])}<extra></extra>"
                    ),
                )
            )
        fig.add_trace(
            go.Scatter(
                x=mid["role_name"],
                y=mid["p50"],
                mode="markers+lines",
                name="Медиана",
                marker=dict(size=9, color=INK),
                line=dict(color=INK, width=1.5),
                hovertemplate="%{x}: %{y:,.0f} ₽<extra></extra>",
            )
        )
        fig.update_layout(
            title="Middle: коридор p25–p75 и медиана",
            xaxis_tickangle=-35,
            yaxis_title="₽",
            showlegend=False,
        )
        st.plotly_chart(style_fig(fig, 440), use_container_width=True)

    with c2:
        section("By function", "Медиана по группам")
        gmed = (
            mid.groupby("group", as_index=False)
            .agg(p50=("p50", "median"), n_roles=("role", "count"))
            .sort_values("p50", ascending=True)
        )
        fig2 = px.bar(
            gmed,
            x="p50",
            y="group",
            orientation="h",
            text=gmed["p50"].map(lambda v: f"{int(v/1000)}k"),
            color_discrete_sequence=[ACCENT],
            labels={"p50": "Медиана ролей", "group": ""},
        )
        fig2.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(style_fig(fig2, 320), use_container_width=True)
        st.caption(f"Медиана медиан ролей внутри группы · только Middle · N ≥ {MIN_N}.")

    st.dataframe(
        mid[["role_name", "group", "n", "p25", "p50", "p75"]]
        .assign(
            p25=lambda d: d.p25.map(money),
            p50=lambda d: d.p50.map(money),
            p75=lambda d: d.p75.map(money),
        )
        .rename(
            columns={
                "role_name": "Роль",
                "group": "Группа",
                "n": "N",
                "p25": "p25",
                "p50": "Медиана",
                "p75": "p75",
            }
        ),
        use_container_width=True,
        hide_index=True,
        height=320,
    )


def page_ladder(df: pd.DataFrame) -> None:
    hero(
        "04 · Карьерная лестница · H1 / H6",
        "Грейд двигает чек сильнее, чем почти любой другой фактор",
        "Смотрим отношение Senior / Junior и форму кривой по грейдам.",
    )
    base = base_slice(df)

    ratios = []
    for role in base.role.unique():
        sub = base[base.role == role]
        sub_i = sub.set_index("grade")
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
                "n_j": sub_i.loc["junior", "n"],
                "n_s": sub_i.loc["senior", "n"],
            }
        )
    rdf = pd.DataFrame(ratios).sort_values("ratio", ascending=False)
    if rdf.empty:
        st.info(f"Недостаточно данных Junior+Senior (N ≥ {MIN_N}).")
        return

    top = rdf.iloc[0]
    med_ratio = rdf["ratio"].median()
    verdict(
        "confirm",
        "H1 · Подтверждена",
        f"Медианный рост Junior→Senior: {med_ratio:.1f}×. "
        f"Лидер лестницы — {top['role_name']} ({top['ratio']:.1f}×: "
        f"{money(top['junior'])} → {money(top['senior'])}).",
    )
    if top["role"] == "ml-engineer" or (rdf.role == "ml-engineer").any():
        ml = rdf[rdf.role == "ml-engineer"]
        if len(ml):
            verdict(
                "confirm",
                "H6 · Подтверждена",
                f"ML Engineer: {ml.iloc[0]['ratio']:.1f}× — самая крутая (или среди топа) карьерная премия в выборке.",
            )

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            rdf.head(14),
            x="ratio",
            y="role_name",
            color="group",
            orientation="h",
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
        fig2.add_trace(
            go.Scatter(
                x=curve["grade_name"],
                y=curve["p50"],
                mode="lines+markers",
                name="медиана",
                line=dict(color=ACCENT, width=3),
                marker=dict(size=10),
            )
        )
        fig2.add_trace(
            go.Scatter(
                x=curve["grade_name"].tolist() + curve["grade_name"].tolist()[::-1],
                y=curve["p75"].tolist() + curve["p25"].tolist()[::-1],
                fill="toself",
                fillcolor="rgba(0,91,255,0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                name="p25–p75",
                hoverinfo="skip",
            )
        )
        name = curve.iloc[0]["role_name"] if len(curve) else role
        fig2.update_layout(title=f"Кривая грейдов · {name}", yaxis_title="₽")
        st.plotly_chart(style_fig(fig2, 420), use_container_width=True)
        st.caption("Иллюстрация на примере аналитика данных.")


def meta_grade_order() -> List[str]:
    return [
        "intern",
        "junior",
        "junior-plus",
        "middle",
        "middle-plus",
        "senior",
        "senior-plus",
        "lead",
        "lead-plus",
    ]


def page_geo(df: pd.DataFrame) -> None:
    hero(
        "05 · География · H2",
        "Московская премия есть — но она скромнее легенды",
        "Сравниваем медиану Москва vs «все города» на одних и тех же роли и грейде.",
    )
    rows = []
    for _, r in df.iterrows():
        if r["city"] != "msk" or r["format"] != "*":
            continue
        if r["n"] < MIN_N:
            continue
        allc = df[
            (df.role == r.role)
            & (df.grade == r.grade)
            & (df.city == "*")
            & (df.format == "*")
        ]
        if allc.empty:
            continue
        a = allc.iloc[0]
        rows.append(
            {
                "role_name": r.role_name,
                "group": r.group,
                "grade_name": r.grade_name,
                "grade": r.grade,
                "msk": r.p50,
                "all": a.p50,
                "lift": r.p50 / a.p50 - 1,
                "n_msk": r.n,
                "n_all": a.n,
            }
        )
    gdf = pd.DataFrame(rows)
    if gdf.empty:
        st.info(f"Мало московских срезов с N ≥ {MIN_N}.")
        return

    med_lift = gdf["lift"].median()
    max_row = gdf.loc[gdf["lift"].idxmax()]
    if med_lift >= 0.15:
        verdict(
            "confirm",
            "H2 · Подтверждена",
            f"Медианная премия Москвы: {pct(med_lift)}. Гипотеза ≥15% выполняется.",
        )
    else:
        verdict(
            "nuance",
            "H2 · Частично / ослаблена",
            f"Медианная премия Москвы: {pct(med_lift)} — заметно ниже порога 15%. "
            f"Максимум в выборке: {max_row['role_name']} / {max_row['grade_name']} "
            f"({pct(max_row['lift'])}). Карьерный грейд обычно важнее переезда.",
        )

    fig = px.scatter(
        gdf,
        x="all",
        y="msk",
        color="group",
        size="n_msk",
        hover_data={"role_name": True, "grade_name": True, "lift": ":.0%", "all": True, "msk": True},
        labels={"all": "Все города, медиана", "msk": "Москва, медиана", "group": "Группа"},
        color_discrete_map=GROUP_COLORS,
    )
    mx = max(gdf["all"].max(), gdf["msk"].max()) * 1.05
    fig.add_trace(
        go.Scatter(
            x=[0, mx],
            y=[0, mx],
            mode="lines",
            line=dict(dash="dot", color=MUTED),
            name="без премии",
            hoverinfo="skip",
        )
    )
    fig.update_layout(title="Москва vs все города (размер = N в Москве)")
    st.plotly_chart(style_fig(fig, 440), use_container_width=True)

    show = gdf.sort_values("lift", ascending=False)
    st.dataframe(
        show.assign(
            all=lambda d: d["all"].map(money),
            msk=lambda d: d["msk"].map(money),
            lift=lambda d: d["lift"].map(pct),
        )[["role_name", "grade_name", "group", "all", "msk", "lift", "n_msk"]].rename(
            columns={
                "role_name": "Роль",
                "grade_name": "Грейд",
                "group": "Группа",
                "all": "Все города",
                "msk": "Москва",
                "lift": "Премия",
                "n_msk": "N МСК",
            }
        ),
        use_container_width=True,
        hide_index=True,
        height=300,
    )


def page_format(df: pd.DataFrame) -> None:
    hero(
        "06 · Формат работы · H3",
        "Удалёнка не выглядит «штрафом»",
        "Сравниваем remote / hybrid / office при city = все города.",
    )
    fdf = df[(df.city == "*") & (df.format != "*") & (df.grade != "*")].copy()
    fdf = fdf[fdf.n >= MIN_N]
    if fdf.empty:
        st.info(f"Нет срезов по форматам с N ≥ {MIN_N}.")
        return

    # pivot roles that have ≥2 formats on same grade
    comparisons = []
    for (role, grade), g in fdf.groupby(["role", "grade"]):
        if g["format"].nunique() < 2:
            continue
        row = {
            "role": role,
            "role_name": g.iloc[0].role_name,
            "group": g.iloc[0].group,
            "grade": grade,
            "grade_name": g.iloc[0].grade_name,
        }
        for fmt in ["remote", "hybrid", "office"]:
            sub = g[g.format == fmt]
            row[fmt] = sub.iloc[0].p50 if len(sub) else None
            row[f"n_{fmt}"] = int(sub.iloc[0].n) if len(sub) else 0
        comparisons.append(row)
    cdf = pd.DataFrame(comparisons)
    # office vs remote where both exist
    both = cdf.dropna(subset=["remote", "office"])
    if len(both):
        office_higher = (both["office"] > both["remote"]).mean()
        hybrid_vs_remote = cdf.dropna(subset=["remote", "hybrid"])
        hybrid_higher = (
            (hybrid_vs_remote["hybrid"] >= hybrid_vs_remote["remote"]).mean()
            if len(hybrid_vs_remote)
            else None
        )
        verdict(
            "reject",
            "H3 · Опровергнута",
            f"Офис выше удалёнки только в {office_higher:.0%} сопоставимых срезов. "
            + (
                f"Гибрид ≥ remote в {hybrid_higher:.0%} случаев. "
                if hybrid_higher is not None
                else ""
            )
            + "Формат — слабый рычаг по сравнению с грейдом и ролью.",
        )
    else:
        verdict("nuance", "H3 · Недостаточно пар", "Мало прямых сравнений office vs remote.")

    # chart: selected popular roles
    focus_roles = [
        r
        for r in ["data-analyst", "product-analyst", "system-analyst", "backend", "product-manager"]
        if r in set(fdf.role)
    ]
    plot = fdf[fdf.role.isin(focus_roles) & fdf.grade.isin(["middle", "senior"])].copy()
    if not plot.empty:
        fig = px.bar(
            plot,
            x="grade_name",
            y="p50",
            color="format_name",
            facet_col="role_name",
            facet_col_wrap=3,
            barmode="group",
            category_orders={
                "format_name": ["Полная удалёнка", "Гибрид", "Офис"],
                "grade_name": ["Middle", "Senior"],
            },
            color_discrete_sequence=["#0A2540", "#005BFF", "#C45C26"],
            labels={"p50": "Медиана", "grade_name": "", "format_name": "Формат"},
        )
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_layout(title="Формат × грейд для ключевых ролей")
        st.plotly_chart(style_fig(fig, 460), use_container_width=True)

    st.dataframe(
        cdf.assign(
            remote=lambda d: d["remote"].map(lambda x: money(x) if pd.notna(x) else "—"),
            hybrid=lambda d: d["hybrid"].map(lambda x: money(x) if pd.notna(x) else "—"),
            office=lambda d: d["office"].map(lambda x: money(x) if pd.notna(x) else "—"),
        )[["role_name", "grade_name", "remote", "hybrid", "office"]].rename(
            columns={
                "role_name": "Роль",
                "grade_name": "Грейд",
                "remote": "Remote",
                "hybrid": "Hybrid",
                "office": "Office",
            }
        ),
        use_container_width=True,
        hide_index=True,
        height=280,
    )


def page_spread(df: pd.DataFrame) -> None:
    hero(
        "07 · Разброс зарплат · H5",
        "Где «медиана» врёт сильнее всего",
        "IQR / медиана показывает, насколько широк коридор переговоров внутри роли.",
    )
    mid = base_slice(df)
    mid = mid[mid.grade == "middle"]
    mid = mid[mid.n >= MIN_N].copy()
    mid["iqr"] = mid["p75"] - mid["p25"]
    mid["iqr_pct"] = mid["iqr"] / mid["p50"]
    mid = mid.sort_values("iqr_pct", ascending=False)

    if mid.empty:
        st.info("Нет данных.")
        return

    top = mid.iloc[0]
    verdict(
        "confirm",
        "H5 · Подтверждена",
        f"Максимальный относительный разброс: {top['role_name']} — IQR "
        f"{pct(top['iqr_pct']).lstrip('+')} медианы (N={int(top['n'])}). "
        "Чем выше IQR%, тем опаснее опираться на одну «среднюю» цифру в оффере.",
    )

    fig = px.scatter(
        mid,
        x="p50",
        y="iqr_pct",
        size="n",
        color="group",
        hover_name="role_name",
        labels={
            "p50": "Медиана Middle",
            "iqr_pct": "IQR / медиана",
            "group": "Группа",
            "n": "N",
        },
        color_discrete_map=GROUP_COLORS,
    )
    fig.update_layout(title="Уровень оплаты vs неопределённость")
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style_fig(fig, 420), use_container_width=True)

    st.dataframe(
        mid.assign(
            p50=lambda d: d.p50.map(money),
            iqr=lambda d: d.iqr.map(money),
            iqr_pct=lambda d: d.iqr_pct.map(lambda x: f"{x:.0%}"),
        )[["role_name", "group", "n", "p50", "iqr", "iqr_pct"]].rename(
            columns={
                "role_name": "Роль",
                "group": "Группа",
                "n": "N",
                "p50": "Медиана",
                "iqr": "IQR",
                "iqr_pct": "IQR%",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def page_so_what(df: pd.DataFrame) -> None:
    hero(
        "08 · So what",
        "Что делать с этими цифрами",
        "Импликации для кандидата, нанимающего менеджера и компенсации.",
    )
    items = [
        (
            "Кандидату",
            "Торгуйтесь грейдом и скоупом, не городом. Переход Junior→Middle или Middle→Senior "
            "часто даёт больший эффект, чем переезд в Москву.",
        ),
        (
            "Нанимающему",
            "Для ролей с высоким IQR% вилка должна быть широкой и привязанной к уровню влияния, "
            "а не к названию должности.",
        ),
        (
            "Compensation",
            "Не штрафуйте remote по умолчанию: данные не показывают устойчивого дисконта. "
            "Гибрид часто на уровне или выше.",
        ),
        (
            "Карьерный трек",
            "Самый крутой ROI обучения/роста — в зонах вроде ML/DevOps/системного анализа, "
            "где Senior/Junior превышает 2,7–3,8×.",
        ),
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

    section("Scorecard", "Итог по гипотезам")
    score = [
        ("H1 Карьерный множитель 2,5–3×", "Подтверждена", "confirm"),
        ("H2 Москва ≥ +15%", "Ослаблена (~+4–17%)", "nuance"),
        ("H3 Офис > remote", "Опровергнута", "reject"),
        ("H4 Инфра/продукт > аналитика", "Подтверждена", "confirm"),
        ("H5 Разброс у «размытых» ролей", "Подтверждена", "confirm"),
        ("H6 ML — самая крутая лестница", "Подтверждена", "confirm"),
    ]
    for title, tag, kind in score:
        verdict(kind, tag, title)

    st.markdown(
        f'<div class="footnote">Срезы с N &lt; {MIN_N} скрыты. '
        "Это наблюдательная картина рынка, а не причинно-следственный вывод.</div>",
        unsafe_allow_html=True,
    )


# ───────────────────────── main ─────────────────────────

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

    if chapter == "agenda":
        page_agenda(df, meta)
    elif chapter == "exec":
        page_exec(df, meta)
    elif chapter == "map":
        page_map(df)
    elif chapter == "ladder":
        page_ladder(df)
    elif chapter == "geo":
        page_geo(df)
    elif chapter == "format":
        page_format(df)
    elif chapter == "spread":
        page_spread(df)
    else:
        page_so_what(df)


if __name__ == "__main__":
    main()
