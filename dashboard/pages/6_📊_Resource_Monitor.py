import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import psutil
import plotly.graph_objects as go
import time
from datetime import datetime

st.set_page_config(page_title="Мониторинг ресурсов", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.title("📊 Мониторинг ресурсов")

auto_refresh = st.checkbox("🔄 Автообновление каждые 3 секунды")
if auto_refresh:
    time.sleep(3)
    st.rerun()

refresh_col, _ = st.columns([1, 5])
with refresh_col:
    if st.button("🔄 Обновить"):
        st.rerun()

st.divider()

# ── CPU ───────────────────────────────────────────────────────────────────────
cpu_percent = psutil.cpu_percent(interval=0.5)
cpu_freq = psutil.cpu_freq()
cpu_count = psutil.cpu_count()

col1, col2, col3, col4 = st.columns(4)
col1.metric("🖥 Нагрузка CPU", f"{cpu_percent:.1f}%")
col2.metric("⚡ Частота", f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A")
col3.metric("🔢 Ядра (логич.)", cpu_count)
col4.metric("🔢 Ядра (физич.)", psutil.cpu_count(logical=False))

# Per-core breakdown
per_core = psutil.cpu_percent(interval=0.1, percpu=True)
cols = st.columns(min(len(per_core), 8))
for i, (pct, col) in enumerate(zip(per_core[:8], cols)):
    with col:
        color = "🔴" if pct > 80 else "🟡" if pct > 50 else "🟢"
        st.metric(f"{color} Ядро {i}", f"{pct:.0f}%")

st.divider()

# ── RAM ───────────────────────────────────────────────────────────────────────
ram = psutil.virtual_memory()
swap = psutil.swap_memory()

col1, col2, col3, col4 = st.columns(4)
col1.metric("💾 RAM Использовано", f"{ram.used / 1e9:.1f} GB")
col2.metric("💾 RAM Всего", f"{ram.total / 1e9:.1f} GB")
col3.metric("💾 RAM Свободно", f"{ram.available / 1e9:.1f} GB")
col4.metric("🔄 SWAP", f"{swap.used / 1e9:.1f} / {swap.total / 1e9:.1f} GB")

fig_ram = go.Figure(go.Bar(
    x=["Использовано", "Свободно", "SWAP (использовано)"],
    y=[ram.used / 1e9, ram.available / 1e9, swap.used / 1e9],
    marker_color=["#7C3AED", "#059669", "#D97706"],
))
fig_ram.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#E2E8F0", height=200, margin=dict(t=10, b=10, l=10, r=10),
    yaxis_title="GB",
)
st.plotly_chart(fig_ram, use_container_width=True)

st.divider()

# ── Disk ──────────────────────────────────────────────────────────────────────
st.subheader("💿 Дисковое пространство")
partitions = psutil.disk_partitions()
for part in partitions:
    try:
        usage = psutil.disk_usage(part.mountpoint)
        pct = usage.percent
        color = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{color} {part.mountpoint}** ({part.fstype})")
            st.progress(int(pct) / 100)
        with col2:
            st.markdown(f"{usage.used / 1e9:.1f} / {usage.total / 1e9:.1f} GB ({pct:.0f}%)")
    except PermissionError:
        pass

st.divider()

# ── Network ───────────────────────────────────────────────────────────────────
st.subheader("🌐 Сеть")
net = psutil.net_io_counters()
col1, col2, col3, col4 = st.columns(4)
col1.metric("⬆️ Отправлено", f"{net.bytes_sent / 1e6:.1f} MB")
col2.metric("⬇️ Получено", f"{net.bytes_recv / 1e6:.1f} MB")
col3.metric("📦 Пакеты отпр.", f"{net.packets_sent:,}")
col4.metric("📦 Пакеты получ.", f"{net.packets_recv:,}")

st.divider()

# ── Top Processes ─────────────────────────────────────────────────────────────
st.subheader("⚙️ Топ процессов по CPU")
procs = []
for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
    try:
        procs.append(proc.info)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
top = procs[:15]

rows = [{
    "PID": p["pid"],
    "Процесс": p["name"],
    "CPU %": f"{p['cpu_percent']:.1f}",
    "RAM %": f"{p['memory_percent']:.1f}" if p["memory_percent"] else "0.0",
    "Статус": p["status"],
} for p in top]
st.dataframe(rows, use_container_width=True, hide_index=True)

st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")
