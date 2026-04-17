# Workspace

## Recent changes (Apr 17, 2026)
- Подключён реальный TikTok-публикатор через Playwright + Nix-Chromium (`social_media_bot/core/posting/tiktok_publisher.py`).
- Cookies нормализуются из 3 форматов (Cookie Editor JSON, JSON dict, Cookie header).
- Все страницы дашборда переименованы на русский (`pages/0_⚙️_Настройки.py`, `pages/1_📱_Аккаунты.py`, и т.д.).
- В контент-плане добавлена справка по cookies TikTok и переведены фильтры статуса/платформы.
- Системные пакеты `chromium` (Nix) установлены для Playwright (`shutil.which('chromium')`).

## Overview

pnpm workspace monorepo using TypeScript for Node.js artifacts, plus a standalone Python 3.11 backend with Telegram bot.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5 (Node.js artifacts), FastAPI (Python bot)
- **Database**: PostgreSQL + Drizzle ORM (Node.js), SQLite + SQLAlchemy (Python bot)
- **Validation**: Zod (`zod/v4`), `drizzle-zod` (Node.js); Pydantic (Python)
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Key Commands (Node.js)

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

## Social Media Automation Platform (Python)

Location: `social_media_bot/`

### Architecture

```
social_media_bot/
├── main.py                  # FastAPI app + bot lifecycle (uvicorn entry point)
├── config.py                # Pydantic Settings (reads TELEGRAM_BOT_TOKEN, BOT_DATABASE_URL)
├── requirements.txt         # Python dependencies
├── api/
│   └── routes/
│       ├── accounts.py      # POST /api/accounts/add, GET /api/accounts/list, DELETE /api/accounts/{id}
│       └── stats.py         # GET /api/stats/summary
├── bot/
│   ├── bot.py               # Bot + Dispatcher factory
│   ├── handlers/
│   │   ├── start.py         # /start command + main menu callbacks
│   │   └── accounts.py      # Full account management FSM handlers
│   ├── keyboards/
│   │   ├── main_menu.py     # Main menu inline keyboard
│   │   └── accounts_kb.py   # Account-related inline keyboards
│   └── states/
│       └── add_account.py   # AddAccountFSM states (4-step flow)
├── db/
│   ├── database.py          # SQLAlchemy async engine (SQLite via aiosqlite)
│   ├── models.py            # Account ORM model
│   └── crud.py              # Async CRUD operations
├── core/
│   └── accounts/
│       └── manager.py       # High-level AccountManager business logic
└── utils/
    └── security.py          # Fernet encryption for session/cookie data
```

### Running

Workflow: **Social Media Bot**
Command: `cd social_media_bot && python3.11 -m uvicorn main:app --host 0.0.0.0 --port 3000`

### API Endpoints

- `GET /` — health check
- `POST /api/accounts/add` — add account (platform, username, auth_type, session_data)
- `GET /api/accounts/list` — list all accounts
- `DELETE /api/accounts/{id}` — delete account by ID
- `GET /api/stats/summary` — statistics summary

### Environment Variables / Secrets

- `TELEGRAM_BOT_TOKEN` — Telegram bot token (secret)
- `SESSION_SECRET` — encryption key for session data (secret)
- `BOT_DATABASE_URL` — override SQLite path (optional, defaults to `sqlite+aiosqlite:///./social_media.db`)

### Telegram Bot Features

- **Main menu**: Accounts / Stats / Autopost
- **Accounts menu**: Add / List / Delete
- **Add account FSM** (4 steps): Platform → Auth type → Username → Cookies JSON
- Cookie/session data encrypted with Fernet before storage
- All UI uses inline keyboard buttons (no commands needed after /start)

## AutoPilot Dashboard (Streamlit)

Location: `dashboard/`

### Running

Workflow: **AutoPilot Dashboard**
Command: `cd dashboard && python3.11 -m streamlit run app.py --server.port 5000`

### Pages

| Страница | Инструмент | Описание |
|----------|-----------|----------|
| `app.py` | 🏠 Дашборд | Статистика аккаунтов, метрики системы, навигация |
| `pages/1_📱_Accounts.py` | 📱 Аккаунты | Управление аккаунтами (через Bot API) |
| `pages/2_🖼_Background_Remover.py` | 🖼 Фон | Удаление фона (AI rembg или по цвету) |
| `pages/3_🧾_QR_Generator.py` | 🧾 QR | QR-коды: URL, WiFi, vCard, текст |
| `pages/4_💻_Fake_Data.py` | 💻 Faker | Тестовые данные (JSON/CSV/SQL) |
| `pages/5_📥_YouTube_Downloader.py` | 📥 YT-DL | Скачивание видео/аудио через yt-dlp |
| `pages/6_📊_Resource_Monitor.py` | 📊 Монитор | CPU, RAM, диск, сеть, процессы |
| `pages/7_🔍_Code_Analyzer.py` | 🔍 Анализ | Pylint + Pyflakes |
| `pages/8_🔗_Link_Checker.py` | 🔗 Ссылки | Параллельная проверка URL |
| `pages/9_📷_Image_Editor.py` | 📷 Фото | Яркость, контраст, эффекты, водяной знак |
| `pages/10_📝_Article_Summarizer.py` | 📝 Суммаризатор | TF-IDF суммаризация без AI |
| `pages/11_🗞_News_Reader.py` | 🗞 Новости | RSS-ленты: RBC, Habr, BBC, HN, TechCrunch |

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.

## Authentication (Stage 1 — done)
- **DB**: `User` model in `social_media_bot/db/models.py` (email, password_hash bcrypt, google_id, avatar, role, is_active, last_login_at). First registered user → `admin`.
- **API**: `social_media_bot/api/routes/auth.py` — `/api/auth/register`, `/api/auth/login`, `/api/auth/google`, `/api/auth/me`. JWT (HS256, TTL 30 days, secret = `SESSION_SECRET`). `/api/auth/google` protected by `X-Internal-Secret` header (shared with Streamlit).
- **Dashboard**: `dashboard/utils/auth.py` exposes `require_auth()` (gate) and `render_user_menu()` (sidebar avatar + logout). Every page in `dashboard/pages/*.py` and `dashboard/app.py` imports & calls them at top.
- **Google OAuth**: uses Streamlit native `st.login("google")` if `.streamlit/secrets.toml` has `[auth.google]` (client_id, client_secret, redirect_uri). Until then, only email/password works.
- **Stages remaining**: 2) PWA (manifest + service worker for installable web app), 3) Native Android APK.
