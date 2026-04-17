"""Авторизация для дашборда: вход/регистрация через API."""
import os
import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:3000")
INTERNAL_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-me")


def _api(method: str, path: str, **kw) -> tuple[int, dict]:
    try:
        r = requests.request(method, f"{API_BASE}{path}", timeout=10, **kw)
        try:
            data = r.json()
        except Exception:
            data = {"detail": r.text[:200]}
        return r.status_code, data
    except Exception as e:
        return 0, {"detail": f"Сеть недоступна: {e}"}


def register(email: str, password: str, name: str = "") -> tuple[bool, str]:
    code, data = _api("POST", "/api/auth/register",
                      json={"email": email, "password": password,
                            "name": name or None})
    if code == 200 and "token" in data:
        st.session_state.auth_token = data["token"]
        st.session_state.auth_user = data["user"]
        return True, "ok"
    return False, data.get("detail", "Ошибка регистрации")


def login(email: str, password: str) -> tuple[bool, str]:
    code, data = _api("POST", "/api/auth/login",
                      json={"email": email, "password": password})
    if code == 200 and "token" in data:
        st.session_state.auth_token = data["token"]
        st.session_state.auth_user = data["user"]
        return True, "ok"
    return False, data.get("detail", "Ошибка входа")


def google_login(google_id: str, email: str, name: str | None = None,
                 avatar_url: str | None = None) -> tuple[bool, str]:
    code, data = _api("POST", "/api/auth/google",
                      headers={"X-Internal-Secret": INTERNAL_SECRET},
                      json={"google_id": google_id, "email": email,
                            "name": name, "avatar_url": avatar_url})
    if code == 200 and "token" in data:
        st.session_state.auth_token = data["token"]
        st.session_state.auth_user = data["user"]
        return True, "ok"
    return False, data.get("detail", "Ошибка Google-входа")


def logout():
    for k in ("auth_token", "auth_user"):
        st.session_state.pop(k, None)
    try:
        st.logout()  # Streamlit native OIDC logout
    except Exception:
        pass


def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def is_authenticated() -> bool:
    return bool(st.session_state.get("auth_token") and st.session_state.get("auth_user"))


# ── Streamlit native Google OIDC интеграция ─────────────────────────────────
def try_streamlit_google() -> bool:
    """Если пользователь авторизован через st.login, синхронизируем с нашим API.
    Возвращает True если уже авторизован."""
    try:
        if not getattr(st, "user", None) or not st.user.is_logged_in:
            return False
    except Exception:
        return False

    if is_authenticated():
        return True

    u = st.user
    google_sub = getattr(u, "sub", None) or getattr(u, "id", None)
    email = getattr(u, "email", None)
    if not google_sub or not email:
        return False

    ok, _ = google_login(
        google_id=str(google_sub),
        email=email,
        name=getattr(u, "name", None),
        avatar_url=getattr(u, "picture", None),
    )
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# AUTH GATE — рендерит страницу входа если не залогинен
# ══════════════════════════════════════════════════════════════════════════════
def _has_streamlit_oidc() -> bool:
    """Настроен ли Google OIDC в .streamlit/secrets.toml?"""
    try:
        return bool(st.secrets.get("auth", {}).get("google", {}).get("client_id"))
    except Exception:
        return False


def _founder_image_b64() -> str:
    import base64, pathlib
    p = pathlib.Path(__file__).parent.parent / "static" / "founder.jpg"
    if not p.exists():
        return ""
    return base64.b64encode(p.read_bytes()).decode()


def render_login_page():
    """Рендерит страницу входа/регистрации. Останавливает выполнение страницы."""
    img_b64 = _founder_image_b64()
    img_src = f"data:image/jpeg;base64,{img_b64}" if img_b64 else ""

    st.markdown(f"""
    <style>
    [data-testid="stSidebar"] {{ display: none; }}
    [data-testid="stHeader"] {{ background: transparent; }}
    .stApp {{
        background: radial-gradient(ellipse at top left,
                    #1e1b4b 0%, #0f0f23 35%, #000 100%);
        overflow-x: hidden;
    }}
    /* Анимированные частицы фона */
    .stApp::before {{
        content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
        background-image:
          radial-gradient(circle at 20% 30%, rgba(139,92,246,.25), transparent 40%),
          radial-gradient(circle at 80% 70%, rgba(99,102,241,.22), transparent 40%),
          radial-gradient(circle at 50% 50%, rgba(236,72,153,.12), transparent 50%);
        animation: aurora 18s ease-in-out infinite alternate;
    }}
    @keyframes aurora {{
        0%   {{ transform: translate(0,0) scale(1); opacity:.85; }}
        50%  {{ transform: translate(-30px,20px) scale(1.06); opacity:1; }}
        100% {{ transform: translate(20px,-15px) scale(.98); opacity:.9; }}
    }}
    /* Звёздочки */
    .stars {{
        position:fixed; inset:0; pointer-events:none; z-index:0;
        background-image:
          radial-gradient(2px 2px at 20% 30%, #fff, transparent),
          radial-gradient(1px 1px at 60% 70%, #c7d2fe, transparent),
          radial-gradient(1.5px 1.5px at 80% 20%, #fff, transparent),
          radial-gradient(1px 1px at 30% 80%, #fbcfe8, transparent),
          radial-gradient(2px 2px at 90% 50%, #fff, transparent),
          radial-gradient(1px 1px at 10% 60%, #ddd6fe, transparent),
          radial-gradient(1.5px 1.5px at 50% 10%, #fff, transparent),
          radial-gradient(1px 1px at 70% 40%, #c4b5fd, transparent);
        background-size: 600px 600px;
        animation: twinkle 6s ease-in-out infinite alternate;
    }}
    @keyframes twinkle {{
        0% {{ opacity:.4; }} 100% {{ opacity:1; }}
    }}
    .main .block-container {{ position:relative; z-index:1; padding-top: 1rem; }}

    /* Левая колонка — фото + приветствие */
    .hero-wrap {{
        display:flex; flex-direction:column; align-items:center;
        justify-content:center; padding: 20px 10px;
        animation: fadeInLeft .9s cubic-bezier(.2,.8,.2,1) both;
    }}
    @keyframes fadeInLeft {{
        from {{ opacity:0; transform: translateX(-40px); }}
        to   {{ opacity:1; transform: translateX(0); }}
    }}
    .hero-photo {{
        width: 320px; max-width: 90%;
        border-radius: 24px; overflow:hidden;
        box-shadow: 0 30px 80px rgba(139,92,246,.35),
                    0 0 0 2px rgba(139,92,246,.4) inset;
        position:relative;
        animation: floaty 5s ease-in-out infinite alternate;
    }}
    .hero-photo::after {{
        content:""; position:absolute; inset:-3px; border-radius:24px;
        background: linear-gradient(135deg,#8b5cf6,#ec4899,#06b6d4,#8b5cf6);
        background-size: 300% 300%;
        z-index:-1; filter: blur(14px); opacity:.7;
        animation: gradient-flow 6s linear infinite;
    }}
    @keyframes gradient-flow {{
        0% {{ background-position: 0% 50%; }}
        100% {{ background-position: 300% 50%; }}
    }}
    @keyframes floaty {{
        from {{ transform: translateY(0); }}
        to   {{ transform: translateY(-10px); }}
    }}
    .hero-photo img {{ display:block; width:100%; height:auto; }}
    .hero-greet {{
        margin-top: 28px; text-align:center;
    }}
    .hero-greet .hi {{
        font-size: 14px; letter-spacing: 4px; color:#a78bfa;
        text-transform: uppercase; font-weight: 600;
    }}
    .hero-greet .name {{
        font-size: 38px; font-weight: 900; margin: 6px 0 4px 0;
        background: linear-gradient(135deg,#fff 0%,#c4b5fd 50%,#f9a8d4 100%);
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .hero-greet .role {{
        color:#94a3b8; font-size: 15px; margin-bottom: 18px;
    }}
    .hero-greet .invite {{
        font-size: 18px; color:#e2e8f0; line-height: 1.5;
        max-width: 360px; margin: 0 auto;
    }}
    .hero-greet .invite b {{
        background: linear-gradient(90deg,#8b5cf6,#ec4899);
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent; font-weight: 800;
    }}
    .typing-dot {{
        display:inline-block; width:6px; height:6px; border-radius:50%;
        background:#a78bfa; margin: 0 2px;
        animation: typing 1.4s infinite ease-in-out;
    }}
    .typing-dot:nth-child(2) {{ animation-delay: .2s; }}
    .typing-dot:nth-child(3) {{ animation-delay: .4s; }}
    @keyframes typing {{
        0%,60%,100% {{ transform: translateY(0); opacity:.4; }}
        30% {{ transform: translateY(-6px); opacity:1; }}
    }}

    /* Правая колонка — карточка авторизации */
    .auth-card {{
        background: rgba(15, 23, 42, .85);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(139,92,246,.3);
        border-radius: 22px; padding: 36px 32px;
        box-shadow: 0 20px 60px rgba(0,0,0,.5),
                    0 0 0 1px rgba(255,255,255,.04) inset;
        animation: fadeInRight .9s cubic-bezier(.2,.8,.2,1) both;
        animation-delay: .15s;
    }}
    @keyframes fadeInRight {{
        from {{ opacity:0; transform: translateX(40px); }}
        to   {{ opacity:1; transform: translateX(0); }}
    }}
    .auth-logo {{ text-align:center; font-size:42px; margin-bottom:6px;
                 filter: drop-shadow(0 0 20px rgba(139,92,246,.6)); }}
    .auth-title {{ text-align:center; font-size:26px; font-weight:900;
                  background: linear-gradient(135deg,#fff,#c4b5fd);
                  -webkit-background-clip:text; background-clip:text;
                  -webkit-text-fill-color: transparent;
                  margin-bottom:4px; }}
    .auth-sub {{ text-align:center; color:#94a3b8; font-size:13px;
                margin-bottom:22px; }}
    .auth-divider {{ display:flex; align-items:center; gap:10px;
                    color:#475569; font-size:11px; margin:16px 0;
                    letter-spacing: 2px; font-weight: 600; }}
    .auth-divider::before, .auth-divider::after {{
        content:""; flex:1; height:1px;
        background: linear-gradient(90deg, transparent, #334155, transparent);
    }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
    .stTextInput input, .stTextInput input:focus {{
        background: rgba(30,41,59,.6) !important;
        border: 1px solid rgba(139,92,246,.25) !important;
        color: #e2e8f0 !important;
    }}
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg,#8b5cf6 0%,#ec4899 100%) !important;
        border: none !important;
        font-weight: 700 !important;
        box-shadow: 0 8px 24px rgba(139,92,246,.4) !important;
        transition: transform .15s, box-shadow .15s !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 32px rgba(236,72,153,.5) !important;
    }}
    </style>
    <div class="stars"></div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="large")

    with left:
        if img_src:
            st.markdown(f"""
            <div class="hero-wrap">
                <div class="hero-photo"><img src="{img_src}" alt="Founder"/></div>
                <div class="hero-greet">
                    <div class="hi">Welcome aboard</div>
                    <div class="name">Привет, друг</div>
                    <div class="role">основатель AutoPilot · AI-инженер</div>
                    <div class="invite">
                        Заходи в <b>мир AI-автоматизации</b> — где соцсети
                        ведут себя сами, контент пишется за секунды,
                        а ты управляешь всем одной кнопкой
                        <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with right:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        st.markdown('<div class="auth-logo">🚀</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-title">AutoPilot</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="auth-sub">Войди и стань на автопилот</div>',
                    unsafe_allow_html=True)

        # ── Google ─────────────────────────────────────────────────────────
        if _has_streamlit_oidc():
            if st.button("🔐 Войти через Google", use_container_width=True,
                          type="primary"):
                try:
                    st.login("google")
                except Exception as e:
                    st.error(f"Не удалось запустить Google вход: {e}")
            st.markdown('<div class="auth-divider">ИЛИ</div>',
                        unsafe_allow_html=True)
        else:
            with st.expander("ℹ️ Включить вход через Google"):
                st.caption(
                    "Для Google OAuth нужно создать OAuth-приложение в "
                    "Google Cloud Console и добавить ключи в "
                    "`.streamlit/secrets.toml` (auth.google.client_id, "
                    "auth.google.client_secret, auth.google.redirect_uri). "
                    "Пока используйте email + пароль."
                )

        # ── Email/password tabs ────────────────────────────────────────────
        tab_login, tab_register = st.tabs(["🔑 Вход", "✨ Регистрация"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com",
                                       key="login_email")
                password = st.text_input("Пароль", type="password",
                                          key="login_pwd")
                submit = st.form_submit_button("Войти", use_container_width=True,
                                                type="primary")
                if submit:
                    if not email or not password:
                        st.error("Заполните все поля")
                    else:
                        ok, msg = login(email.strip(), password)
                        if ok:
                            st.success("Вход выполнен!")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

        with tab_register:
            with st.form("register_form"):
                r_name = st.text_input("Имя", placeholder="Иван Иванов",
                                        key="reg_name")
                r_email = st.text_input("Email", placeholder="you@example.com",
                                         key="reg_email")
                r_pwd = st.text_input("Пароль (мин. 6 символов)",
                                       type="password", key="reg_pwd")
                r_pwd2 = st.text_input("Повторите пароль", type="password",
                                        key="reg_pwd2")
                submit = st.form_submit_button("Создать аккаунт",
                                                use_container_width=True,
                                                type="primary")
                if submit:
                    if not r_email or not r_pwd:
                        st.error("Email и пароль обязательны")
                    elif len(r_pwd) < 6:
                        st.error("Пароль слишком короткий")
                    elif r_pwd != r_pwd2:
                        st.error("Пароли не совпадают")
                    else:
                        ok, msg = register(r_email.strip(), r_pwd, r_name.strip())
                        if ok:
                            st.success("✨ Аккаунт создан, вы вошли!")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("🔒 Данные защищены. Пароли хранятся в зашифрованном виде.")


def require_auth():
    """Главный гейт. Поставить в начале каждой страницы."""
    # Сначала пробуем Google OIDC если уже залогинен через st.login
    try_streamlit_google()

    if not is_authenticated():
        st.set_page_config(page_title="AutoPilot — Вход", page_icon="🔐",
                           layout="centered",
                           initial_sidebar_state="collapsed")
        render_login_page()
        st.stop()


def render_user_menu():
    """Меню текущего пользователя в сайдбаре."""
    user = current_user()
    if not user:
        return
    with st.sidebar:
        st.divider()
        cols = st.columns([1, 3])
        with cols[0]:
            avatar = user.get("avatar_url") or \
                f"https://api.dicebear.com/7.x/initials/svg?seed={user['email']}"
            st.image(avatar, width=42)
        with cols[1]:
            st.markdown(f"**{user.get('name') or user['email']}**")
            st.caption(user["email"])
        if st.button("🚪 Выйти", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()
