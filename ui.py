"""UI helpers for consistent styling across pages."""

import streamlit as st


BASE_CSS = """
<style>
    .stApp {
        background-color: #1a1a2e;
    }
    h1, h2, h3, h4 {
        color: #e94560 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    .metric-card {
        background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
        border: 1px solid #e94560;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
</style>
"""


def apply_base_styles(extra_css: str = "") -> None:
    """Apply base CSS styles and optional extra CSS overrides."""
    css = BASE_CSS
    if extra_css:
        css = css.replace("</style>", f"\n{extra_css}\n</style>")
    st.markdown(css, unsafe_allow_html=True)
