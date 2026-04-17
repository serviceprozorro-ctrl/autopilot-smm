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


def render_login_page():
    """Рендерит страницу входа/регистрации. Останавливает выполнение страницы."""
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .auth-card {
        max-width: 460px; margin: 40px auto;
        background: #0f172a; border: 1px solid #1e293b;
        border-radius: 18px; padding: 36px 32px;
        box-shadow: 0 12px 40px rgba(0,0,0,.4);
    }
    .auth-logo { text-align:center; font-size:48px; margin-bottom:8px; }
    .auth-title { text-align:center; font-size:24px; font-weight:800;
                  color:#e2e8f0; margin-bottom:6px; }
    .auth-sub { text-align:center; color:#94a3b8; font-size:14px;
                margin-bottom:24px; }
    .auth-divider { display:flex; align-items:center; gap:10px;
                    color:#475569; font-size:12px; margin:18px 0; }
    .auth-divider::before, .auth-divider::after {
        content:""; flex:1; height:1px; background:#1e293b;
    }
    </style>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        st.markdown('<div class="auth-logo">🚀</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-title">AutoPilot</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-sub">Платформа управления SMM</div>',
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
