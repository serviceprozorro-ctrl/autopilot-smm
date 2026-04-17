import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageDraw, ImageFont
import io

st.set_page_config(page_title="Редактор изображений", page_icon="📷", layout="wide")
st.title("📷 Редактор изображений")
st.markdown("Полноценный редактор фотографий: кроп, фильтры, эффекты, водяной знак и многое другое")

uploaded = st.file_uploader("📤 Загрузите изображение", type=["png", "jpg", "jpeg", "webp", "bmp"])

if not uploaded:
    st.info("Загрузите изображение чтобы начать редактирование")
    st.stop()

original = Image.open(uploaded).convert("RGBA")
img = original.copy()

col_controls, col_preview = st.columns([1, 2])

with col_controls:
    st.markdown(f"**Оригинал:** {original.width} × {original.height} px")

    tab_basic, tab_filters, tab_transform, tab_wm = st.tabs(["✏️ Базовые", "🎨 Фильтры", "🔄 Трансформ.", "💧 Водяной знак"])

    with tab_basic:
        brightness = st.slider("☀️ Яркость", 0.0, 3.0, 1.0, 0.05)
        contrast = st.slider("🌗 Контраст", 0.0, 3.0, 1.0, 0.05)
        saturation = st.slider("🎨 Насыщенность", 0.0, 3.0, 1.0, 0.05)
        sharpness = st.slider("🔪 Чёткость", 0.0, 3.0, 1.0, 0.05)

    with tab_filters:
        effect = st.selectbox("Эффект", [
            "Нет", "Оттенки серого", "Сепия", "Инвертировать", "Эмбосс",
            "Контурный", "Размытие", "Сильное размытие", "Резкость",
            "Пикселизация", "Авто-контраст",
        ])

    with tab_transform:
        resize_w = st.number_input("Ширина (px)", value=original.width, min_value=10, max_value=5000)
        resize_h = st.number_input("Высота (px)", value=original.height, min_value=10, max_value=5000)
        rotation = st.slider("🔄 Поворот (°)", -180, 180, 0)
        flip_h = st.checkbox("↔️ Отразить по горизонтали")
        flip_v = st.checkbox("↕️ Отразить по вертикали")
        crop = st.checkbox("✂️ Обрезка")
        if crop:
            cx1 = st.slider("Левый край", 0, original.width - 1, 0)
            cy1 = st.slider("Верхний край", 0, original.height - 1, 0)
            cx2 = st.slider("Правый край", 1, original.width, original.width)
            cy2 = st.slider("Нижний край", 1, original.height, original.height)

    with tab_wm:
        wm_text = st.text_input("Текст водяного знака", placeholder="© Мой бренд")
        wm_opacity = st.slider("Прозрачность", 10, 255, 128)
        wm_position = st.selectbox("Позиция", ["Центр", "Низ-право", "Низ-лево", "Верх-право", "Верх-лево"])
        wm_color = st.color_picker("Цвет текста", "#FFFFFF")

    out_format = st.selectbox("Формат сохранения", ["PNG", "JPEG", "WEBP"])
    if out_format == "JPEG":
        jpeg_quality = st.slider("Качество JPEG", 10, 100, 85)

    apply = st.button("✅ Применить всё", type="primary", use_container_width=True)

# ── Processing ────────────────────────────────────────────────────────────────
def apply_sepia(img):
    img = img.convert("RGB")
    data = img.getdata()
    new = []
    for r, g, b in data:
        nr = min(255, int(r * 0.393 + g * 0.769 + b * 0.189))
        ng = min(255, int(r * 0.349 + g * 0.686 + b * 0.168))
        nb = min(255, int(r * 0.272 + g * 0.534 + b * 0.131))
        new.append((nr, ng, nb))
    out = Image.new("RGB", img.size)
    out.putdata(new)
    return out.convert("RGBA")

def apply_pixelate(img, factor=8):
    w, h = img.size
    small = img.resize((w // factor, h // factor), Image.NEAREST)
    return small.resize((w, h), Image.NEAREST)

if apply:
    result = img.copy()

    # Basic adjustments
    rgb = result.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    rgb = ImageEnhance.Color(rgb).enhance(saturation)
    rgb = ImageEnhance.Sharpness(rgb).enhance(sharpness)
    result = rgb.convert("RGBA")

    # Effects
    effect_map = {
        "Оттенки серого": lambda i: ImageOps.grayscale(i.convert("RGB")).convert("RGBA"),
        "Сепия": apply_sepia,
        "Инвертировать": lambda i: ImageOps.invert(i.convert("RGB")).convert("RGBA"),
        "Эмбосс": lambda i: i.convert("RGB").filter(ImageFilter.EMBOSS).convert("RGBA"),
        "Контурный": lambda i: i.convert("RGB").filter(ImageFilter.CONTOUR).convert("RGBA"),
        "Размытие": lambda i: i.filter(ImageFilter.GaussianBlur(radius=2)),
        "Сильное размытие": lambda i: i.filter(ImageFilter.GaussianBlur(radius=8)),
        "Резкость": lambda i: i.filter(ImageFilter.SHARPEN),
        "Пикселизация": apply_pixelate,
        "Авто-контраст": lambda i: ImageOps.autocontrast(i.convert("RGB")).convert("RGBA"),
    }
    if effect in effect_map:
        result = effect_map[effect](result)

    # Resize
    if (resize_w, resize_h) != (original.width, original.height):
        result = result.resize((resize_w, resize_h), Image.LANCZOS)

    # Rotation
    if rotation != 0:
        result = result.rotate(-rotation, expand=True)

    # Flip
    if flip_h:
        result = ImageOps.mirror(result)
    if flip_v:
        result = ImageOps.flip(result)

    # Crop
    if crop:
        result = result.crop((cx1, cy1, cx2, cy2))

    # Watermark
    if wm_text.strip():
        draw = ImageDraw.Draw(result)
        bbox = draw.textbbox((0, 0), wm_text)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        W, H = result.size
        pos_map = {
            "Центр": ((W - tw) // 2, (H - th) // 2),
            "Низ-право": (W - tw - 20, H - th - 20),
            "Низ-лево": (20, H - th - 20),
            "Верх-право": (W - tw - 20, 20),
            "Верх-лево": (20, 20),
        }
        pos = pos_map.get(wm_position, ((W - tw) // 2, (H - th) // 2))
        r = int(wm_color[1:3], 16)
        g = int(wm_color[3:5], 16)
        b = int(wm_color[5:7], 16)
        draw.text(pos, wm_text, fill=(r, g, b, wm_opacity))

    st.session_state["edited_img"] = result
    st.session_state["edit_format"] = out_format
    st.session_state.get("jpeg_quality", 85)

with col_preview:
    st.subheader("👁 Предпросмотр")
    col_orig, col_new = st.columns(2)
    with col_orig:
        st.caption("Оригинал")
        st.image(original, use_container_width=True)
    with col_new:
        if "edited_img" in st.session_state:
            edited = st.session_state["edited_img"]
            fmt = st.session_state["edit_format"]
            st.caption(f"Результат ({edited.width}×{edited.height})")
            st.image(edited, use_container_width=True)

            buf = io.BytesIO()
            if fmt == "JPEG":
                edited.convert("RGB").save(buf, format="JPEG", quality=85)
                mime = "image/jpeg"
                ext = "jpg"
            elif fmt == "WEBP":
                edited.save(buf, format="WEBP")
                mime = "image/webp"
                ext = "webp"
            else:
                edited.save(buf, format="PNG")
                mime = "image/png"
                ext = "png"

            st.download_button(
                f"⬇️ Скачать .{ext}", buf.getvalue(),
                f"edited.{ext}", mime, use_container_width=True,
            )
        else:
            st.info("Нажмите «Применить всё» чтобы увидеть результат")
