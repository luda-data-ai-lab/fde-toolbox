# LUDA FDE Toolbox

고객사 현장의 FDE(Forward Deployed Engineer)가 **진단 → 분석 → 설계 → 구축 → 운영** 단계를 하나의 과제(engagement) 안에서 이어서 다루는 오프라인 우선·멀티 테넌트 툴박스.

- 기획 명세: [docs/Spec.md](docs/Spec.md) · 개발 지시서: [docs/Devin.md](docs/Devin.md) · 변경 이력: [docs/CHANGELOG.md](docs/CHANGELOG.md)
- 가져오기·내보내기 형식: [docs/schemas/](docs/schemas/) · 설계 결정: [docs/adr/](docs/adr/)

세 가지 원칙이 기능보다 우선한다.

1. **고객사 데이터 격리** — 테넌트 테이블은 모두 `tenant_id`를 가지며, 세션 이벤트가 읽기에 테넌트 조건을 강제로 붙이고 컨텍스트 없는 쓰기를 거부한다. 다른 고객사 리소스 ID는 403이 아닌 404를 돌려준다. 모든 테넌트 경로는 `tests/isolation`에서 자동 순회 검증된다.
2. **외부 통신 금지** — 네트워크 호출은 `backend/app/adapters/` 안에서만 허용되며(`ADAPTERS_ALLOWED=false`가 기본), `tests/architecture`가 이를 강제한다. 프론트엔드는 폰트(Pretendard)까지 번들하며 빌드 결과물의 외부 참조를 `npm run check:external`로 검사한다.
3. **LUDA 자산과 고객 데이터 분리** — 자산 테이블에는 `tenant_id`가 없고, 고객 데이터는 자산을 `{asset_id, version}`으로만 참조한다.

## 현재 범위 (Phase 0)

| 영역 | 내용 |
| --- | --- |
| 코어 | 인증(Argon2 + httpOnly JWT 쿠키), 사용자·역할(`luda_admin`/`fde`/`client_admin`/`client_user`)·고객사 배정, 고객사·과제·시스템 레지스트리, 첨부파일, 추가 전용 감사 로그(CSV 내보내기), 역할별 홈 대시보드 |
| 자산 | LUDA 자산 라이브러리(버전·diff·패키지 가져오기/내보내기), 기본 자산 8종 시드 |
| 이관 | 고객사 단위 ZIP 내보내기/가져오기(ID 재발급·참조 재매핑) |
| DevTracker | 프로젝트, 태스크(칸반/목록), 중단·재개 메모, 프롬프트 기록, 프로젝트 대시보드 |
| I/F 관리 | LUDA I/F 엑셀 템플릿 다운로드·업로드·검증(미등록 시스템 등록 선택), 목록 CRUD, 대시보드, 시스템 연결 그래프(PNG 저장), 엑셀/CSV 내보내기. 샘플: `backend/seeds/samples/interfaces-sample.xlsx` |
| AgentHub | 에이전트 템플릿 버전·diff, 평가 케이스·수동 평가 결과, 고객사별 배포 인스턴스 등록·상태 관리 (실행하지 않는 레지스트리) |

## 빠른 시작 — Docker Compose

```bash
docker compose up -d --build                     # http://localhost:8080 (FDE_PORT로 변경)
docker compose exec backend python -m app.cli init-admin --email admin@example.com
docker compose exec backend python -m app.cli seed-assets
docker compose exec backend python -m app.cli seed-demo   # 선택: 데모 고객사·사용자·데이터
```

- `SECRET_KEY`/`ENCRYPTION_KEY`를 지정하지 않으면 첫 기동 시 생성해 데이터 볼륨(`/data/.secrets`)에 보관한다.
- PostgreSQL 사용:
  ```bash
  DB_TYPE=postgresql DATABASE_URL=postgresql+psycopg://fde:fde@postgres:5432/fde \
    docker compose --profile postgres up -d --build
  ```
- SQL Server 사용: [docs/mssql.md](docs/mssql.md) (`WITH_MSSQL=true`로 이미지 빌드, `--profile mssql`).
- 백엔드는 기동 시 `migrate`와 `seed-assets`(관리자 존재 시)를 자동 실행한다.

## 단독 실행 (Docker 없이)

프론트엔드를 한 번 빌드한 뒤(`cd frontend && npm ci && npm run build`) 스크립트가 가상환경 생성, `.env` 키 생성, 마이그레이션을 수행하고 uvicorn 하나로 API와 정적 파일을 서빙한다.

```bash
scripts/run_standalone.sh            # Linux/macOS — HOST, PORT 환경변수로 변경 (기본 127.0.0.1:8000)
pwsh scripts/run_standalone.ps1      # Windows PowerShell
cd backend && .venv/bin/python -m app.cli init-admin --email admin@example.com
```

## 개발

```bash
# backend
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev,postgres]"
cp .env.example .env                 # SECRET_KEY, ENCRYPTION_KEY 채우기
.venv/bin/python -m app.cli migrate
.venv/bin/uvicorn app.main:app --reload          # API 문서: http://127.0.0.1:8000/api/docs

# frontend (Node 20.19+)
cd frontend
npm ci
npm run dev                          # http://127.0.0.1:5173, /api는 8000으로 프록시
```

### 검사

| 대상 | 명령 |
| --- | --- |
| backend lint·type | `ruff check . && ruff format --check . && mypy` |
| backend test | `pytest --cov=app` (PostgreSQL: `TEST_DATABASE_URL=postgresql+psycopg://...`, SQL Server: [docs/mssql.md](docs/mssql.md)) |
| 격리·외부 통신 금지 | `pytest tests/isolation tests/architecture` |
| frontend | `npm run typecheck && npm run lint && npm run test && npm run build && npm run check:external` |
| E2E | `npx playwright install chromium && npm run e2e` (빌드된 `dist`와 `backend/.venv` 사용, 임시 DB로 서버 기동) |

CI(`.github/workflows/ci.yml`)는 위 검사를 SQLite·PostgreSQL·SQL Server에서 실행하고, 커버리지(전체 80%, `app/core` 90%)와 Docker Compose 기동을 확인한다.

## CLI

| 명령 | 설명 |
| --- | --- |
| `python -m app.cli migrate` | Alembic `head`까지 마이그레이션 |
| `python -m app.cli create-db` | SQL Server에서 `DATABASE_URL`의 DB가 없으면 생성(다른 DB는 변화 없음) |
| `python -m app.cli init-admin --email ... [--name ...] [--password ...]` | 최초 LUDA 관리자 생성(이미 있으면 거부). 비밀번호는 `FDE_ADMIN_PASSWORD` 또는 프롬프트로도 입력 |
| `python -m app.cli seed-assets` | 기본 자산 패키지(`backend/seeds/assets`) 가져오기, 재실행해도 중복 생성 없음 |
| `python -m app.cli seed-demo [--password ...]` | "데모 제조사" 고객사, FDE·고객사 관리자, 과제, 시스템 6개, DevTracker 프로젝트, AgentHub 인스턴스 생성 |

## 환경 변수

`backend/.env.example` 참고. 주요 값: `DB_TYPE`(sqlite/postgresql/mssql), `DATABASE_URL`, `DATA_DIR`, `SECRET_KEY`(필수, 32자 이상), `ENCRYPTION_KEY`(필수), `DEPLOYMENT_MODE`(standalone/hosted), `ADAPTERS_ALLOWED`(기본 false), `MAX_UPLOAD_MB`(20), `DEFAULT_LOCALE`(ko), `DEPLOYMENT_BASE_IRI`, `COOKIE_SECURE`, `STATIC_DIR`(빌드된 프론트엔드를 백엔드가 직접 서빙할 때), `FDE_SECRETS_DIR`(설정값을 파일로 읽을 디렉터리).

## 레포 구조

```
backend/app/{db,core,modules,adapters,home}   FastAPI 앱 (core: tenancy·auth·users·tenants·systems·assets·audit·files·transfer)
backend/{alembic,seeds,tests}                 마이그레이션, 기본 자산, 테스트(isolation·architecture·core·modules)
frontend/src/{app,core,modules,components,api,i18n}
frontend/e2e                                  Playwright 인수 시나리오
docs/{Spec.md,Devin.md,adr,schemas,CHANGELOG.md}
scripts/run_standalone.{sh,ps1}
```
