import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import subprocess
import tempfile

st.set_page_config(page_title="Анализатор кода", page_icon="🔍", layout="wide")
st.title("🔍 Анализатор кода")
st.markdown("Анализ Python-кода через **Pylint** и **Pyflakes**")

col_left, col_right = st.columns(2)

EXAMPLE_CODE = '''def calculate(x, y):
    result=x+y  # missing spaces
    unused_var = 42
    return result

def bad_function():
    import os  # import inside function
    print("hello")
    x = 1
    y = 2
    return  # missing return value
'''

with col_left:
    code = st.text_area(
        "Введите Python-код для анализа",
        value=EXAMPLE_CODE,
        height=350,
        placeholder="def my_function():\n    pass",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        use_pylint = st.checkbox("Pylint", value=True, help="Подробный анализ стиля, ошибок, code smells")
    with col_b:
        use_pyflakes = st.checkbox("Pyflakes", value=True, help="Быстрая проверка синтаксических ошибок")

    pylint_score = st.empty()

    if st.button("🔍 Анализировать", type="primary", use_container_width=True):
        if not code.strip():
            st.warning("Введите код для анализа")
        else:
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
                f.write(code)
                tmp_path = f.name

            with col_right:
                if use_pylint:
                    st.subheader("📋 Pylint")
                    try:
                        result = subprocess.run(
                            [sys.executable, "-m", "pylint", tmp_path,
                             "--output-format=text", "--score=yes", "--disable=C0114,C0115,C0116"],
                            capture_output=True, text=True, timeout=30
                        )
                        output = result.stdout or result.stderr
                        # Extract score
                        for line in output.split("\n"):
                            if "Your code has been rated" in line:
                                score_part = line.strip()
                                st.info(f"🎯 {score_part}")
                                break

                        # Color-code output
                        lines = output.split("\n")
                        formatted = []
                        for line in lines:
                            if "E " in line or "error" in line.lower():
                                formatted.append(f"🔴 {line}")
                            elif "W " in line or "warning" in line.lower():
                                formatted.append(f"🟡 {line}")
                            elif "C " in line or "convention" in line.lower():
                                formatted.append(f"🔵 {line}")
                            elif "R " in line or "refactor" in line.lower():
                                formatted.append(f"🟣 {line}")
                            else:
                                formatted.append(line)
                        st.code("\n".join(formatted[:80]), language="text")
                    except FileNotFoundError:
                        st.error("Pylint не установлен: `pip install pylint`")
                    except subprocess.TimeoutExpired:
                        st.error("⏰ Анализ занял слишком долго")

                if use_pyflakes:
                    st.subheader("⚡ Pyflakes")
                    try:
                        result = subprocess.run(
                            [sys.executable, "-m", "pyflakes", tmp_path],
                            capture_output=True, text=True, timeout=15
                        )
                        output = result.stdout or result.stderr
                        if not output.strip():
                            st.success("✅ Ошибок не найдено!")
                        else:
                            # Remove temp file path from output
                            clean = output.replace(tmp_path + ":", "Line ")
                            st.code(clean, language="text")
                    except FileNotFoundError:
                        st.error("Pyflakes не установлен: `pip install pyflakes`")

            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    else:
        with col_right:
            st.info("⬅️ Введите код и нажмите «Анализировать»")

with col_right:
    st.divider()
    st.subheader("🎨 Легенда")
    st.markdown("🔴 **E** — Error (ошибки)")
    st.markdown("🟡 **W** — Warning (предупреждения)")
    st.markdown("🔵 **C** — Convention (стиль кода)")
    st.markdown("🟣 **R** — Refactor (предложения по рефакторингу)")
