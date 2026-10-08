# 설치 및 실행

관리자가 PC나 서버에 FDE Toolbox를 설치하고 실행하는 방법입니다. 예시는 Windows PowerShell 기준입니다.

## 필요한 프로그램

- Python 3.12 (`py -0p`로 확인, 없으면 `winget install -e --id Python.Python.3.12`)
- Node.js 20.19 이상
- Git

## 백엔드 준비

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

`notepad .env`에서 위 두 명령이 출력한 값을 각각 `SECRET_KEY`, `ENCRYPTION_KEY`에 넣습니다. 데모 데이터가 필요하면 `python -m app.cli seed-demo --password "Demo1234!"`를 실행합니다.

> `Activate.ps1` 실행이 막히면 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`를 먼저 실행하세요.

## 실행

PowerShell 창 두 개를 엽니다.

```powershell
# 창 1: 백엔드
cd D:\work\fde-toolbox\backend
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

```powershell
# 창 2: 프론트엔드
cd D:\work\fde-toolbox\frontend
npm ci
npm run dev
```

브라우저에서 `http://127.0.0.1:5173`에 접속합니다. 포트가 이미 쓰이고 있으면 백엔드를 `--port 8010`으로 띄우고, 프론트엔드는 `$env:VITE_API_PROXY="http://127.0.0.1:8010"; npm run dev -- --port 5180`으로 띄웁니다.

## 업데이트

```powershell
git pull
cd backend
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m app.cli migrate
.\.venv\Scripts\python -m app.cli seed-assets
cd ..\frontend
npm ci
```

## 그 밖의 설치 방법

- **Docker**: 저장소 루트에서 `docker compose up -d --build` 후 `http://localhost:8080`. 관리자는 `docker compose exec backend python -m app.cli init-admin --email admin@example.com`으로 만듭니다.
- **단독 실행(Docker 없이)**: `cd frontend; npm ci; npm run build` 후 `pwsh scripts/run_standalone.ps1`을 실행하고 `http://127.0.0.1:8000`에 접속합니다.
- **PostgreSQL / SQL Server**: `.env`의 `DB_TYPE`과 `DATABASE_URL`을 바꿉니다. SQL Server는 저장소의 `docs/mssql.md`를 참고하세요.

## 주요 설정(.env)

| 항목 | 설명 |
| --- | --- |
| `SECRET_KEY` | 로그인 토큰 서명 키(필수, 32자 이상) |
| `ENCRYPTION_KEY` | 외부 연동 인증 정보 암호화 키(필수) |
| `DB_TYPE`, `DATABASE_URL` | sqlite / postgresql / mssql |
| `ADAPTERS_ALLOWED` | 외부 연동 허용 여부(기본 false) |
| `MAX_UPLOAD_MB` | 업로드 크기 제한(기본 20) |
| `DEFAULT_LOCALE` | 기본 언어(ko) |
