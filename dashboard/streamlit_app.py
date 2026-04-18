"""Production-safe entry for Streamlit Cloud — wraps the real app and shows errors."""
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

st.set_page_config(
    page_title="AutoPilot",
    page_icon="🚀",
    layout="wide",
)

try:
    import app  # noqa: F401  — runs dashboard/app.py top-level
except SystemExit:
    pass
except Exception:
    st.error("⚠️ Ошибка при запуске приложения. Подробности ниже:")
    st.code(traceback.format_exc(), language="python")
    st.info(
        "Если вы видите эту страницу — приложение запустилось, "
        "но в коде есть ошибка. Передайте текст выше разработчику."
    )
