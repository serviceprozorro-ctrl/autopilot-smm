import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import re
from collections import Counter
import math

st.set_page_config(page_title="Суммаризатор статей", page_icon="📝", layout="wide")
st.title("📝 Суммаризатор статей")
st.markdown("Краткое изложение статей и текстов. Работает без AI — полностью локально.")

EXAMPLE = """Искусственный интеллект (ИИ) — это имитация человеческого интеллекта в машинах, 
запрограммированных мыслить и учиться как люди. Термин также может применяться к любой машине, 
которая демонстрирует признаки, связанные с человеческим разумом, такие как обучение и решение задач.

Идеальная характеристика искусственного интеллекта — это его способность рационализировать 
и предпринимать действия, которые имеют наибольшие шансы на достижение конкретной цели. 
Подраздел искусственного интеллекта — машинное обучение — относится к концепции, согласно которой 
компьютерные программы могут автоматически учиться на новых данных и адаптироваться к ним без 
помощи человека.

Методы глубокого обучения обеспечивают эту автоматическую обучаемость, поглощая огромные 
количества неструктурированных данных, таких как текст, изображения или видео. Искусственный 
интеллект постоянно развивается, принося пользу самым разным отраслям.

Машины автоматизированы и могут думать и действовать лучше людей, а также могут выполнять 
задачи точнее и с меньшими ошибками, чем люди. Такие отрасли, как здравоохранение, финансы, 
образование и маркетинг, получают огромную пользу от ИИ."""

col_input, col_output = st.columns([1, 1])

def extract_summary(text: str, num_sentences: int, lang: str = "ru") -> tuple[str, dict]:
    """Extractive summarization using TF-IDF-like scoring."""
    # Clean and split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences:
        return "Текст слишком короткий.", {}

    # Stopwords
    stop_ru = {"и", "в", "на", "с", "по", "за", "из", "к", "о", "от", "до", "при", "под",
               "над", "это", "что", "как", "все", "для", "он", "она", "они", "мы", "вы",
               "а", "но", "или", "да", "же", "бы", "не", "ни", "то", "ли", "уже", "еще",
               "также", "такие", "такой", "такая", "такое", "его", "её", "их", "её"}
    stop_en = {"the", "a", "an", "in", "on", "at", "to", "of", "for", "with", "and", "or",
               "but", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
               "do", "does", "did", "it", "that", "this", "these", "those", "as", "by", "from"}
    stop_words = stop_ru | stop_en

    def tokenize(text: str) -> list:
        return [w.lower() for w in re.findall(r'\b\w+\b', text) if w.lower() not in stop_words and len(w) > 2]

    # TF: word frequencies in full text
    all_words = tokenize(text)
    word_freq = Counter(all_words)
    max_freq = max(word_freq.values()) if word_freq else 1

    # IDF-like: sentences containing each word
    sent_word_sets = [set(tokenize(s)) for s in sentences]
    n = len(sentences)
    idf = {w: math.log(n / (1 + sum(1 for ws in sent_word_sets if w in ws))) for w in word_freq}

    # Score sentences by TF-IDF sum
    scores = []
    for i, sent in enumerate(sentences):
        words = tokenize(sent)
        if not words:
            scores.append(0.0)
            continue
        score = sum((word_freq.get(w, 0) / max_freq) * idf.get(w, 0) for w in words)
        # Bonus for first/last sentences (position bias)
        if i == 0:
            score *= 1.5
        elif i == len(sentences) - 1:
            score *= 1.2
        scores.append(score / len(words))

    # Pick top-N sentences, preserve order
    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    top_indices = sorted([i for i, _ in indexed[:num_sentences]])
    summary = " ".join(sentences[i] for i in top_indices)

    stats = {
        "Исходных предложений": len(sentences),
        "Уникальных слов": len(word_freq),
        "Предложений в выжимке": min(num_sentences, len(sentences)),
        "Сжатие": f"{100 - int(len(summary) / max(len(text), 1) * 100)}%",
    }
    return summary, stats


with col_input:
    text = st.text_area("📄 Вставьте текст статьи", value=EXAMPLE, height=350)
    num_sentences = st.slider("Количество предложений в выжимке", 1, 10, 3)
    lang = st.radio("Язык текста", ["🇷🇺 Русский", "🇺🇸 English"], horizontal=True)

    if st.button("📝 Сделать выжимку", type="primary", use_container_width=True):
        if not text.strip():
            st.warning("Введите текст для суммаризации")
        else:
            summary, stats = extract_summary(text, num_sentences, "ru" if "Русский" in lang else "en")
            st.session_state["summary"] = summary
            st.session_state["summary_stats"] = stats

with col_output:
    st.subheader("📋 Результат")
    if "summary" in st.session_state:
        st.success(st.session_state["summary"])
        st.divider()
        st.subheader("📊 Статистика")
        stats = st.session_state["summary_stats"]
        for k, v in stats.items():
            col_k, col_v = st.columns([2, 1])
            col_k.markdown(k)
            col_v.markdown(f"**{v}**")
        st.divider()
        st.download_button(
            "⬇️ Скачать выжимку",
            st.session_state["summary"],
            "summary.txt", "text/plain",
            use_container_width=True,
        )
    else:
        st.info("Нажмите «Сделать выжимку» чтобы увидеть результат")
