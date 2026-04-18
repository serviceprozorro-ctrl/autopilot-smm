"""Root entry for Streamlit Cloud — loads the dashboard with full error capture."""
import sys
import os
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(ROOT, "dashboard")
sys.path.insert(0, DASH)
os.chdir(DASH)

import streamlit as st

try:
    import app  # runs dashboard/app.py
except SystemExit:
    raise
except Exception:
    try:
        st.set_page_config(page_title="AutoPilot — Ошибка", page_icon="⚠️", layout="wide")
    except Exception:
        pass
    st.error("⚠️ Ошибка при запуске приложения. Подробности ниже:")
    st.code(traceback.format_exc(), language="python")
    st.info("Сделайте скриншот и пришлите разработчику.")
