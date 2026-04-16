import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import json
import csv
import io
from faker import Faker

st.set_page_config(page_title="Генератор тестовых данных", page_icon="💻", layout="wide")
st.title("💻 Генератор тестовых данных")
st.markdown("Генератор реалистичных тестовых данных")

LOCALES = {
    "🇷🇺 Русский": "ru_RU", "🇺🇸 English": "en_US", "🇩🇪 Deutsch": "de_DE",
    "🇫🇷 Français": "fr_FR", "🇯🇵 日本語": "ja_JP", "🇨🇳 中文": "zh_CN",
}

col_settings, col_result = st.columns([1, 2])

with col_settings:
    locale_label = st.selectbox("Язык / Locale", list(LOCALES.keys()))
    locale = LOCALES[locale_label]

    count = st.slider("Количество записей", 1, 500, 20)

    _FIELD_LABELS = {
        "name": "Имя",
        "email": "Email",
        "phone_number": "Телефон",
        "address": "Адрес",
        "company": "Компания",
        "job": "Должность",
        "username": "Username",
        "password": "Пароль",
        "date_of_birth": "Дата рождения",
        "ssn": "SSN",
        "credit_card_number": "Номер карты",
        "iban": "IBAN",
        "user_agent": "User-Agent",
        "ipv4": "IP-адрес",
        "url": "URL",
        "text": "Текст",
        "color_name": "Цвет",
        "country": "Страна",
    }
    fields = st.multiselect(
        "Поля для генерации",
        list(_FIELD_LABELS.keys()),
        default=["name", "email", "phone_number", "username", "company"],
        format_func=lambda x: _FIELD_LABELS.get(x, x),
    )

    output_format = st.radio("Формат вывода", ["Таблица", "JSON", "CSV", "SQL INSERT"])

    if st.button("🎲 Сгенерировать", type="primary", use_container_width=True):
        fake = Faker(locale)
        Faker.seed(0)

        data = []
        for _ in range(count):
            row = {}
            for field in fields:
                try:
                    val = getattr(fake, field)()
                    row[field] = str(val)
                except AttributeError:
                    row[field] = "N/A"
            data.append(row)

        st.session_state["fake_data"] = data
        st.session_state["fake_format"] = output_format
        st.session_state["fake_fields"] = fields

with col_result:
    if "fake_data" in st.session_state:
        data = st.session_state["fake_data"]
        fmt = st.session_state["fake_format"]
        fields = st.session_state["fake_fields"]

        st.markdown(f"✅ Сгенерировано **{len(data)}** записей")

        if fmt == "Таблица":
            st.dataframe(data, use_container_width=True, hide_index=True)
            csv_buf = io.StringIO()
            writer = csv.DictWriter(csv_buf, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
            st.download_button("⬇️ Скачать CSV", csv_buf.getvalue(), "fake_data.csv", "text/csv")

        elif fmt == "JSON":
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            st.code(json_str[:3000] + ("..." if len(json_str) > 3000 else ""), language="json")
            st.download_button("⬇️ Скачать JSON", json_str, "fake_data.json", "application/json")

        elif fmt == "CSV":
            csv_buf = io.StringIO()
            writer = csv.DictWriter(csv_buf, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
            csv_str = csv_buf.getvalue()
            st.code(csv_str[:2000] + ("..." if len(csv_str) > 2000 else ""), language="text")
            st.download_button("⬇️ Скачать CSV", csv_str, "fake_data.csv", "text/csv")

        elif fmt == "SQL INSERT":
            table = "users"
            lines = [f"INSERT INTO {table} ({', '.join(fields)}) VALUES"]
            for i, row in enumerate(data):
                vals = ", ".join(f"'{v.replace(chr(39), chr(39)*2)}'" for v in row.values())
                sep = "," if i < len(data) - 1 else ";"
                lines.append(f"  ({vals}){sep}")
            sql = "\n".join(lines)
            st.code(sql[:4000] + ("..." if len(sql) > 4000 else ""), language="sql")
            st.download_button("⬇️ Скачать SQL", sql, "fake_data.sql", "text/plain")
    else:
        st.info("Настройте параметры слева и нажмите «Сгенерировать»")
