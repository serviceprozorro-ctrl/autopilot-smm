import streamlit as st

  st.set_page_config(page_title="AutoPilot Test", page_icon="🚀")
  st.title("🚀 AutoPilot работает!")
  st.success("Базовая версия Streamlit запущена. Сейчас подключаем основной код.")
  st.write("Если вы видите это — значит платформа работает корректно.")

  import sys, os, traceback
  ROOT = os.path.dirname(os.path.abspath(__file__))
  DASH = os.path.join(ROOT, "dashboard")
  sys.path.insert(0, DASH)

  with st.expander("🔍 Диагностика", expanded=True):
      st.write(f"Python: {sys.version}")
      st.write(f"Working dir: {os.getcwd()}")
      st.write(f"Dashboard exists: {os.path.isdir(DASH)}")
      if os.path.isdir(DASH):
          st.write(f"Files in dashboard: {os.listdir(DASH)[:10]}")

  st.divider()
  st.subheader("Загрузка основного приложения...")

  try:
      os.chdir(DASH)
      import app
  except SystemExit:
      pass
  except Exception:
      st.error("Ошибка при импорте dashboard/app.py:")
      st.code(traceback.format_exc(), language="python")
  