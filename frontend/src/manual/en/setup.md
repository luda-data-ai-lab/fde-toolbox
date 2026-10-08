# Installation and running

How an administrator installs and runs FDE Toolbox on a PC or server. Examples use Windows PowerShell.

## Prerequisites

- Python 3.12 (check with `py -0p`; install with `winget install -e --id Python.Python.3.12` if missing)
- Node.js 20.19 or later
- Git

## Backend setup

```powershell
cd D:\work\fde-toolbox\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
notepad .env
New-Item -ItemType Directory -Force data
python -m app.cli migrate
python -m app.cli init-admin --email admin@example.com --password "Admin1234!"
python -m app.cli seed-assets
```

In `notepad .env`, paste the two printed values into `SECRET_KEY` and `ENCRYPTION_KEY`. For demo data, run `python -m app.cli seed-demo --password "Demo1234!"`.

> If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.

## Running

Open two PowerShell windows.

```powershell
# Window 1: backend
cd D:\work\fde-toolbox\backend
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

```powershell
# Window 2: frontend
cd D:\work\fde-toolbox\frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173` in a browser. If a port is taken, start the backend with `--port 8010` and the frontend with `$env:VITE_API_PROXY="http://127.0.0.1:8010"; npm run dev -- --port 5180`.

## Updating

```powershell
git pull
cd backend
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m app.cli migrate
.\.venv\Scripts\python -m app.cli seed-assets
cd ..\frontend
npm ci
```

## Other ways to run

- **Docker**: run `docker compose up -d --build` in the repository root and open `http://localhost:8080`. Create the admin with `docker compose exec backend python -m app.cli init-admin --email admin@example.com`.
- **Standalone (no Docker)**: run `cd frontend; npm ci; npm run build`, then `pwsh scripts/run_standalone.ps1`, and open `http://127.0.0.1:8000`.
- **PostgreSQL / SQL Server**: change `DB_TYPE` and `DATABASE_URL` in `.env`. For SQL Server see `docs/mssql.md` in the repository.

## Key settings (.env)

| Setting | Meaning |
| --- | --- |
| `SECRET_KEY` | Signs login tokens (required, 32+ characters) |
| `ENCRYPTION_KEY` | Encrypts integration credentials (required) |
| `DB_TYPE`, `DATABASE_URL` | sqlite / postgresql / mssql |
| `ADAPTERS_ALLOWED` | Allow external integrations (default false) |
| `MAX_UPLOAD_MB` | Upload size limit (default 20) |
| `DEFAULT_LOCALE` | Default language (ko) |
