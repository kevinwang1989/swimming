"""Shared styles for the Streamlit app — v1.4 World Aquatics–inspired theme.

Palette, typography and components modelled after https://www.worldaquatics.com/swimming
Brand blue: #0282c6. English display font: Oswald. CJK body: Noto Sans SC.
"""

import streamlit as st


def apply_style():
    st.markdown("""
    <style>
    /* ---------------------------------------------------------------- */
    /*  Fonts                                                            */
    /* ---------------------------------------------------------------- */
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap');

    :root {
        --wa-blue: #0282c6;
        --wa-blue-dark: #026aa3;
        --wa-navy: #003a5d;
        --wa-bg: #ffffff;
        --wa-bg-alt: #f5f7fa;
        --wa-text: #1a1a2e;
        --wa-muted: #5b6b7d;
        --wa-border: #e3e8ef;
    }

    /* ---- CJK body text ---- */
    html, body, [class*="st-"] {
        font-family: 'Noto Sans SC', sans-serif;
        color: var(--wa-text);
    }

    /* Restore Material Symbols on icon spans (keep fix from v1.1). */
    span.material-symbols-rounded,
    span.material-symbols-outlined,
    span.material-icons,
    span.material-icons-outlined,
    [data-testid="stExpander"] [class*="material"],
    [class*="material-symbols"],
    [class*="material-icons"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                     'Material Icons', 'Material Icons Outlined' !important;
    }

    /* ---------------------------------------------------------------- */
    /*  Headings — Oswald display                                        */
    /* ---------------------------------------------------------------- */
    h1, h2, .wa-display {
        font-family: 'Oswald', 'Noto Sans SC', sans-serif;
        font-weight: 700;
        letter-spacing: 0.02em;
        color: var(--wa-navy);
    }
    h1 {
        font-size: 2.4rem;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }
    h2 {
        font-size: 1.5rem;
        text-transform: uppercase;
        border-bottom: 3px solid var(--wa-blue);
        padding-bottom: 0.35rem;
        display: inline-block;
        margin-top: 2.5rem;
    }
    h3 {
        font-family: 'Noto Sans SC', sans-serif;
        font-weight: 600;
        color: var(--wa-navy);
    }

    /* ---- Header area ---- */
    .stMainBlockContainer {
        padding-top: 2rem;
    }

    /* ---------------------------------------------------------------- */
    /*  Hero banner (homepage)                                           */
    /* ---------------------------------------------------------------- */
    .wa-hero {
        position: relative;
        min-height: 280px;
        border-radius: 6px;
        overflow: hidden;
        background:
            linear-gradient(135deg, rgba(0,58,93,0.92) 0%, rgba(2,130,198,0.88) 100%);
        /* To add a real photo later, uncomment the next line and drop a file at
           assets/hero_pool.jpg:
           , url('./assets/hero_pool.jpg') center/cover;
           background-blend-mode: multiply; */
        padding: 3rem 3rem 2.5rem;
        margin-bottom: 2.5rem;
        color: #ffffff;
        box-shadow: 0 4px 20px rgba(0,58,93,0.15);
    }
    .wa-hero-kicker {
        font-family: 'Oswald', sans-serif;
        font-size: 0.85rem;
        letter-spacing: 0.22em;
        opacity: 0.9;
        text-transform: uppercase;
    }
    .wa-hero-title {
        font-family: 'Oswald', sans-serif;
        font-size: 3rem;
        font-weight: 700;
        line-height: 1.05;
        text-transform: uppercase;
        margin: 0.4rem 0 0.8rem;
        color: #ffffff;
    }
    .wa-hero-sub {
        font-size: 1rem;
        opacity: 0.92;
        max-width: 680px;
        line-height: 1.6;
    }
    .wa-hero-meta {
        margin-top: 1.2rem;
        font-family: 'Oswald', sans-serif;
        font-size: 0.85rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        opacity: 0.85;
    }

    /* ---------------------------------------------------------------- */
    /*  Compact page header (sub-pages)                                  */
    /* ---------------------------------------------------------------- */
    .wa-page-header {
        position: relative;
        border-radius: 6px;
        overflow: hidden;
        background: linear-gradient(135deg, var(--wa-navy) 0%, var(--wa-blue) 100%);
        padding: 1.6rem 2rem 1.4rem;
        margin-bottom: 2rem;
        color: #ffffff;
        box-shadow: 0 3px 14px rgba(0,58,93,0.12);
        border-left: 4px solid #ffffff;
    }
    .wa-page-header-kicker {
        font-family: 'Oswald', sans-serif;
        font-size: 0.72rem;
        letter-spacing: 0.2em;
        opacity: 0.85;
        text-transform: uppercase;
    }
    .wa-page-header-title {
        font-family: 'Oswald', 'Noto Sans SC', sans-serif;
        font-size: 1.85rem;
        font-weight: 700;
        line-height: 1.1;
        text-transform: uppercase;
        margin: 0.25rem 0 0.4rem;
        color: #ffffff;
    }
    .wa-page-header-sub {
        font-size: 0.88rem;
        opacity: 0.92;
        max-width: 720px;
        line-height: 1.5;
    }

    /* ---------------------------------------------------------------- */
    /*  Stat card (Streamlit metric override)                            */
    /* ---------------------------------------------------------------- */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid var(--wa-border);
        border-left: 4px solid var(--wa-blue);
        border-radius: 6px;
        padding: 1.1rem 1.3rem;
        box-shadow: none;
    }
    [data-testid="stMetricLabel"] p {
        font-size: 0.78rem;
        font-weight: 500;
        color: var(--wa-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Oswald', sans-serif;
        font-size: 2rem;
        font-weight: 700;
        color: var(--wa-navy);
    }

    /* ---------------------------------------------------------------- */
    /*  Generic editorial card                                           */
    /* ---------------------------------------------------------------- */
    .wa-card {
        background: #ffffff;
        border: 1px solid var(--wa-border);
        border-radius: 6px;
        padding: 1.4rem 1.5rem;
        transition: all 0.2s ease;
        height: 100%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .wa-card:hover {
        border-color: var(--wa-blue);
        box-shadow: 0 6px 20px rgba(2,130,198,0.12);
        transform: translateY(-2px);
    }
    .wa-card-kicker {
        font-family: 'Oswald', sans-serif;
        font-size: 0.7rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: var(--wa-blue);
        font-weight: 600;
    }
    .wa-card h3 {
        font-family: 'Oswald', sans-serif;
        text-transform: uppercase;
        color: var(--wa-navy);
        margin: 0.4rem 0 0.5rem;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 0.03em;
    }
    .wa-card p {
        color: var(--wa-muted);
        font-size: 0.88rem;
        margin: 0;
        line-height: 1.55;
    }
    .wa-card .wa-card-meta {
        margin-top: 0.7rem;
        font-family: 'Oswald', sans-serif;
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--wa-muted);
    }

    /* ---------------------------------------------------------------- */
    /*  Sidebar — WA navy nav look                                       */
    /* ---------------------------------------------------------------- */
    section[data-testid="stSidebar"] {
        background: var(--wa-navy);
    }
    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
        border-radius: 4px;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {
        background: rgba(255,255,255,0.10);
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLinkActive"],
    section[data-testid="stSidebar"] [aria-current="page"] {
        background: var(--wa-blue) !important;
    }

    /* ---- Rename the auto-generated "app" entry to "🏠 首页" ---- */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li:first-child a > span,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] > li:first-child a > span,
    section[data-testid="stSidebar"] ul[data-testid="stSidebarNav"] > li:first-child a > span {
        font-size: 0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li:first-child a > span::after,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] > li:first-child a > span::after,
    section[data-testid="stSidebar"] ul[data-testid="stSidebarNav"] > li:first-child a > span::after {
        content: "🏠  首页";
        font-size: 0.95rem;
        font-weight: 500;
    }

    /* ---------------------------------------------------------------- */
    /*  DataFrame — flatter                                              */
    /* ---------------------------------------------------------------- */
    .stDataFrame {
        border: 1px solid var(--wa-border);
        border-radius: 4px;
        box-shadow: none;
        overflow: hidden;
    }

    /* ---------------------------------------------------------------- */
    /*  Selectbox & multiselect                                          */
    /* ---------------------------------------------------------------- */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        border-radius: 4px;
    }

    /* ---------------------------------------------------------------- */
    /*  Buttons — WA primary                                             */
    /* ---------------------------------------------------------------- */
    .stButton > button {
        background: var(--wa-blue);
        color: #ffffff;
        border: none;
        border-radius: 4px;
        font-family: 'Oswald', sans-serif;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
        padding: 0.55rem 1.4rem;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: var(--wa-navy);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,58,93,0.25);
        color: #ffffff;
    }

    /* ---------------------------------------------------------------- */
    /*  Tabs — underline style                                           */
    /* ---------------------------------------------------------------- */
    .stTabs [data-baseweb="tab-list"] {
        border-bottom: 2px solid var(--wa-border);
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 0;
        padding: 0.65rem 1.4rem;
        font-family: 'Oswald', sans-serif;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--wa-muted);
    }
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid var(--wa-blue) !important;
        color: var(--wa-blue) !important;
    }

    /* ---------------------------------------------------------------- */
    /*  Alerts — subtle                                                  */
    /* ---------------------------------------------------------------- */
    .stAlert {
        border-radius: 4px;
    }

    /* ---------------------------------------------------------------- */
    /*  Sidebar collapse control fixes (keep from v1.1)                  */
    /* ---------------------------------------------------------------- */
    [data-testid="stSidebarCollapsedControl"] *,
    [data-testid="collapsedControl"] *,
    [data-testid="stSidebarCollapseButton"] * {
        font-size: 0 !important;
        line-height: 0 !important;
    }
    [data-testid="stSidebarCollapsedControl"] button::before {
        content: '▶';
        font-size: 1rem !important;
        color: var(--wa-navy) !important;
    }
    [data-testid="stSidebarCollapseButton"] button::before {
        content: '✕';
        font-size: 1rem !important;
        color: #ffffff !important;
    }

    /* ---------------------------------------------------------------- */
    /*  Hide Streamlit branding                                          */
    /* ---------------------------------------------------------------- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", kicker: str = ""):
    """Render a compact WA-style hero banner at the top of a sub-page.

    Drop-in replacement for the common ``st.title(...) + st.caption(...)``
    pattern. Pass an English ``kicker`` (e.g. "EVENT DETAILS") for the
    small uppercase line above the title; leave empty to omit.
    """
    import streamlit as st

    kicker_html = f'<div class="wa-page-header-kicker">{kicker}</div>' if kicker else ""
    sub_html = f'<div class="wa-page-header-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="wa-page-header">
            {kicker_html}
            <div class="wa-page-header-title">{title}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
