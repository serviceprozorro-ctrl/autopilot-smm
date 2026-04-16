# Workspace

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

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.
