# SplitLang — Secure Bill-Splitting Custom DSL (React + FastAPI + MySQL + ANTLR 4.9.2)

**Course:** Principles of Programming Languages (VNU-HCM International University — SCSE)  
**Stack:** ANTLR 4.9.2 · Python 3 (FastAPI) · React 19 + Vite · MySQL 8.x/9.x · Argon2id · Fernet AES

---

## 1. Overview

**SplitLang** is a deterministic Domain-Specific Language (DSL) for splitting group bills (equal, exact, percentage, weighted ratio, itemized `bill { ... }` blocks, proportional discount/tax/tip, Largest-Remainder rounding, and Greedy Minimum Cash Flow debt simplification), paired with a hardened **React + FastAPI + MySQL** web application and a live **5-Stage PPL Inspector**.

---

## 2. Project Structure

```text
bill splitting app/
├── .gitignore                    # Blocks .env, keys, DB dumps, node_modules, dist, caches
├── .env.example                  # Safe configuration template (NEVER commit .env!)
├── main.py                       # FastAPI/Uvicorn entry point (http://127.0.0.1:8000)
├── cli.py                        # Offline interactive REPL & .split script runner
├── sql/
│   └── init_mysql.sql            # MySQL 8/9 schema + least-privilege `splitlang_app` user
├── api/
│   ├── server.py                 # Hardened FastAPI REST API + SPA static server
│   ├── schemas.py                # Strict Pydantic v2 models (extra="forbid")
│   └── middleware.py             # Security headers (CSP, HSTS, X-Frame-Options) + Force HTTPS
├── frontend/                     # React 19 + Vite SPA
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── api/client.js         # Credentials-included fetch + X-CSRF-Token
│       ├── components/           # AuthScreen, HeaderBar, ConsolePanel, BalancesTab, ExpensesTab, PPLInspectorTab
│       └── App.jsx
├── controller/
│   └── Response.py               # 5-stage ANTLR 4.9.2 pipeline orchestrator
├── module/
│   ├── config.py                 # Server-side .env settings loader
│   ├── security.py               # Argon2id, Fernet encryption, rate limiter, bot guard, upload validator
│   ├── Database.py               # Row-level-secured MySQL (PyMySQL) + SQLite test fallback
│   ├── ASTGeneration.py          # Custom ANTLR4 Visitor (Parse Tree -> AST Ops)
│   ├── ASTutils.py               # AST Op nodes
│   └── utilFunction.py           # Decimal split engine, Largest-Remainder rounding, Min Cash Flow
├── parserAnalyzer/
│   ├── SplitLang.g4              # ANTLR4 Lexer & Parser grammar
│   ├── run.py                    # Regenerate CompiledFiles/
│   └── CompiledFiles/            # ANTLR 4.9.2 generated Python Lexer/Parser/Visitor
├── scripts/
│   ├── generate_secrets.py       # Generate strong SECRET_KEY & DATA_ENCRYPTION_KEY
│   └── security_check.py         # Git secret hygiene & hardcoded-secret scanner
├── examples/                     # dinner_demo.split, usd_trip_demo.split
├── tests/                        # Lexer/Parser, AST/Visitor, Domain Logic & 20 Security Controls
└── docs/                         # Report template (<= 5 pages) & architecture diagram
```

---

## 3. Setup & Running with Local MySQL + React

### Step 1: Initialize MySQL Database & Least-Privilege App User
Open `sql/init_mysql.sql`, change `ChangeMe_StrongAppPass!2026` to your own strong password, then run:
```powershell
& "C:\Program Files\MySQL\MySQL Server 9.4\bin\mysql.exe" -u root -p < sql\init_mysql.sql
```

### Step 2: Create Your Local `.env` (Never Committed to Git)
```powershell
Copy-Item .env.example .env
python scripts/generate_secrets.py
```
Paste the generated `SECRET_KEY`, `DATA_ENCRYPTION_KEY`, and your `MYSQL_PASSWORD` into `.env`.

### Step 3: Install Dependencies & Build React Frontend
```powershell
pip install -r requirements.txt
npm --prefix frontend install
npm --prefix frontend run build
```

### Step 4: Launch the App
```powershell
python main.py
```
Open **http://127.0.0.1:8000** (or run `npm --prefix frontend run dev` on port `5173` during React development).

---

## 4. Security Controls Implemented (20/20)

| # | Control | Implementation |
|---|---|---|
| 1 | **Hide API keys** | All secrets loaded strictly server-side from `.env` (`module/config.py`); zero secrets in React bundle. |
| 2 | **Purge Git secrets** | Strict `.gitignore` + `scripts/security_check.py` scanning for tracked `.env` or hardcoded keys. |
| 3 | **Least-privilege DB access** | Dedicated `splitlang_app` MySQL user (`sql/init_mysql.sql`); React FE never touches DB directly. |
| 4 | **Row-level security** | Every table & query filters strictly by `owner_user_id`. |
| 5 | **Encrypt sensitive data** | Fernet (AES + HMAC-SHA256) encrypts emails, descriptions, itemized bills, notes, and logs at rest. |
| 6 | **Server-side auth** | `get_current_session` validates opaque session cookie against MySQL `sessions` on every protected route. |
| 7 | **Lock record access (IDOR)** | `_assert_group_owner()` blocks cross-user group reads/writes/resets with `403 Forbidden`. |
| 8 | **Block field tampering** | All Pydantic request schemas enforce `ConfigDict(extra="forbid")`. |
| 9 | **Secure session cookies** | `HttpOnly`, `SameSite=Lax`, `Secure` (prod), SHA-256 hashed DB token, plus constant-time `X-CSRF-Token`. |
| 10 | **Hash passwords** | `Argon2id` (`argon2-cffi`, 64 MiB memory cost) + password strength policy. |
| 11 | **Rate limit login** | `SlidingWindowRateLimiter` on `/api/auth/login`, `/api/auth/register`, `/api/execute` (`429` + `Retry-After`). |
| 12 | **Bot protection** | Hidden honeypot field + HMAC-signed single-use arithmetic challenge (`GET /api/auth/challenge`). |
| 13 | **Parameterize queries** | 100% `%s` / `?` parameterized SQL queries across `module/Database.py`. |
| 14 | **Validate all input** | Strict Pydantic bounds/regexes + ANTLR 4.9.2 CFG parser + Stage 5 semantic validation. |
| 15 | **Escape user content** | React JSX auto-escaping (zero `dangerouslySetInnerHTML`) + server-side control-character stripping. |
| 16 | **Restrict file uploads** | `POST /api/upload` accepts `.split` UTF-8 plain text only, `<= 64 KB`, blocks path traversal & null bytes, parsed in memory. |
| 17 | **Trim API responses** | Explicit public response models (`UserPublic`, trimmed dashboard state) + generic `500` handler hiding stack traces. |
| 18 | **Security headers** | Strict `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store`. |
| 19 | **Force HTTPS** | `FORCE_HTTPS=true` enforces HTTP→HTTPS `307` redirect (respecting `X-Forwarded-Proto`) + `Strict-Transport-Security`. |
| 20 | **Scan dependencies** | `npm --prefix frontend audit` + `python scripts/security_check.py`. |

---

## 5. Testing & Auditing

```powershell
# Run all 64 unit, grammar, domain & security tests
python -m pytest -v

# Check Git secret hygiene
python scripts/security_check.py

# Audit React dependencies
npm --prefix frontend audit
```
