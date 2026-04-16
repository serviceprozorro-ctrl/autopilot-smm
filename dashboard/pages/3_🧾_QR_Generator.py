import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import RadialGradiantColorMask, SquareGradiantColorMask
from PIL import Image
import io

st.set_page_config(page_title="QR-генератор", page_icon="🧾", layout="wide")
st.title("🧾 QR-генератор")

tab_url, tab_wifi, tab_vcard, tab_text = st.tabs(["🔗 URL / Текст", "📶 WiFi", "👤 vCard", "💬 Произвольный текст"])

def generate_qr(data: str, fill_color: str, back_color: str, error_correction: str, box_size: int) -> Image.Image:
    ec_map = {"L": qrcode.constants.ERROR_CORRECT_L, "M": qrcode.constants.ERROR_CORRECT_M,
              "Q": qrcode.constants.ERROR_CORRECT_Q, "H": qrcode.constants.ERROR_CORRECT_H}
    qr = qrcode.QRCode(
        version=None, error_correction=ec_map.get(error_correction, qrcode.constants.ERROR_CORRECT_M),
        box_size=box_size, border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color=fill_color, back_color=back_color).convert("RGBA")


def show_qr_result(data: str, filename: str = "qr_code"):
    col_settings, col_preview = st.columns([1, 1])
    with col_settings:
        fill_color = st.color_picker("Цвет QR", "#000000", key=f"fill_{filename}")
        back_color = st.color_picker("Цвет фона", "#FFFFFF", key=f"back_{filename}")
        error_correction = st.select_slider("Коррекция ошибок", ["L", "M", "Q", "H"], value="M", key=f"ec_{filename}")
        box_size = st.slider("Размер", 5, 20, 10, key=f"size_{filename}")

    if st.button("🔨 Создать QR", type="primary", key=f"gen_{filename}"):
        img = generate_qr(data, fill_color, back_color, error_correction, box_size)
        with col_preview:
            st.image(img, caption="Ваш QR-код", use_container_width=True)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.download_button("⬇️ Скачать PNG", buf.getvalue(), f"{filename}.png", "image/png",
                               use_container_width=True, key=f"dl_{filename}")

with tab_url:
    url = st.text_input("Введите URL или текст", placeholder="https://example.com")
    if url:
        show_qr_result(url, "qr_url")

with tab_wifi:
    col1, col2 = st.columns(2)
    ssid = col1.text_input("Название сети (SSID)")
    password = col2.text_input("Пароль", type="password")
    security = st.selectbox("Тип защиты", ["WPA", "WEP", "nopass"])
    hidden = st.checkbox("Скрытая сеть")
    if ssid:
        wifi_data = f"WIFI:T:{security};S:{ssid};P:{password};H:{'true' if hidden else 'false'};;"
        st.code(wifi_data, language="text")
        show_qr_result(wifi_data, "qr_wifi")

with tab_vcard:
    col1, col2 = st.columns(2)
    name = col1.text_input("Имя", placeholder="Иван Иванов")
    phone = col2.text_input("Телефон", placeholder="+7 999 000 00 00")
    email = col1.text_input("Email", placeholder="ivan@example.com")
    org = col2.text_input("Организация", placeholder="ООО Компания")
    url_v = st.text_input("Сайт", placeholder="https://example.com")
    if name:
        vcard = (
            f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL:{phone}\n"
            f"EMAIL:{email}\nORG:{org}\nURL:{url_v}\nEND:VCARD"
        )
        show_qr_result(vcard, "qr_vcard")

with tab_text:
    text = st.text_area("Произвольный текст", height=120, placeholder="Любой текст до 1000 символов...")
    if text:
        show_qr_result(text, "qr_text")
