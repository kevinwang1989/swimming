"""Shared styles for the Streamlit app."""

import streamlit as st


def apply_style():
    st.markdown("""
    <style>
    /* ---- Global font & background ---- */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Noto Sans SC', sans-serif;
    }

    /* Restore Material Symbols font for icon spans (e.g. expander chevron),
       which the broad rule above would otherwise replace and cause literal
       'keyboard_arrow_right' text to leak through. */
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

    /* ---- Header area ---- */
    .stMainBlockContainer {
        padding-top: 2rem;
    }

    /* ---- Sidebar styling ---- */
    section[data-testid="stSidebar"] {
        background: #f0f2f8;
    }

    /* ---- Metric cards ---- */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    [data-testid="stMetricLabel"] p {
        font-size: 0.9rem;
        font-weight: 500;
        color: #555;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1a237e;
    }

    /* ---- DataFrame styling ---- */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    }

    /* ---- Selectbox & multiselect ---- */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        border-radius: 8px;
    }

    /* ---- Buttons ---- */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
    }

    /* ---- Page title ---- */
    h1 {
        color: #1a237e;
    }

    /* ---- Info/success/error boxes ---- */
    .stAlert {
        border-radius: 8px;
    }

    /* ---- Fix sidebar buttons: hide broken Material Icon text ---- */
    [data-testid="stSidebarCollapsedControl"] *,
    [data-testid="collapsedControl"] *,
    [data-testid="stSidebarCollapseButton"] * {
        font-size: 0 !important;
        line-height: 0 !important;
    }
    [data-testid="stSidebarCollapsedControl"] button::before {
        content: '▶';
        font-size: 1rem !important;
    }
    [data-testid="stSidebarCollapseButton"] button::before {
        content: '✕';
        font-size: 1rem !important;
    }

    /* ---- Hide Streamlit branding ---- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
