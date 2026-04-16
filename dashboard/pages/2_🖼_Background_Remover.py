import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from PIL import Image, ImageFilter
import io

st.set_page_config(page_title="Удаление фона", page_icon="🖼", layout="wide")
st.title("🖼 Удаление фона")
st.markdown("Удалите фон с изображения. Поддерживается PNG, JPG, WEBP.")

col_upload, col_result = st.columns(2)

with col_upload:
    uploaded = st.file_uploader("Загрузите изображение", type=["png", "jpg", "jpeg", "webp"])
    method = st.radio(
        "Метод удаления фона",
        ["🤖 AI (rembg)", "🎨 По цвету фона (быстро)"],
        help="AI — точнее, но медленнее. По цвету — мгновенно, работает лучше на однотонном фоне."
    )

    if method == "🎨 По цвету фона (быстро)":
        threshold = st.slider("Порог чувствительности", 10, 100, 30,
                              help="Выше = удаляет больше похожих пикселей")
        bg_color = st.color_picker("Цвет фона для удаления", "#FFFFFF")

if uploaded:
    img = Image.open(uploaded).convert("RGBA")

    with col_upload:
        st.image(img, caption="Оригинал", use_container_width=True)

    if st.button("🚀 Убрать фон", type="primary", use_container_width=True):
        with st.spinner("Обрабатываю..."):
            try:
                if method == "🤖 AI (rembg)":
                    from rembg import remove
                    output = remove(img)
                else:
                    # Color-based removal
                    r, g, b = int(bg_color[1:3], 16), int(bg_color[3:5], 16), int(bg_color[5:7], 16)
                    data = img.getdata()
                    new_data = []
                    for item in data:
                        dist = abs(item[0] - r) + abs(item[1] - g) + abs(item[2] - b)
                        if dist < threshold * 3:
                            new_data.append((255, 255, 255, 0))  # transparent
                        else:
                            new_data.append(item)
                    output = Image.new("RGBA", img.size)
                    output.putdata(new_data)

                with col_result:
                    st.image(output, caption="Результат (фон удалён)", use_container_width=True)

                    buf = io.BytesIO()
                    output.save(buf, format="PNG")
                    st.download_button(
                        "⬇️ Скачать PNG",
                        data=buf.getvalue(),
                        file_name="no_background.png",
                        mime="image/png",
                        use_container_width=True,
                    )

            except ImportError:
                st.error("❌ Библиотека rembg не установлена. Используйте метод 'По цвету фона'.")
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
else:
    with col_result:
        st.info("⬆️ Загрузите изображение слева и нажмите кнопку")
