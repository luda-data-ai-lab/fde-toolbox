# LUDA FDE Toolbox — 개발 지시서 (Devin.md)

- 대상: Devin (AI 소프트웨어 엔지니어)
- 문서 버전: v0.2 — OntoMap(온톨로지) 모듈 추가
- 레포: `luda-data-ai-lab/fde-toolbox` (신규)
- 기획 명세: [Spec.md](./Spec.md) — **작업 시작 전 반드시 전체를 읽을 것**

---

## 0. 먼저 읽을 것

이 프로젝트는 FDE가 고객사 현장에서 쓰는 통합 툴박스다. 기능 자체보다 다음 세 가지가 더 중요하다. 이 셋을 어기는 구현은 기능이 동작해도 완료로 인정하지 않는다.

1. **고객사 데이터 격리**: 어떤 경로(화면, API, 내보내기, 검색, 로그)로도 한 고객사 데이터가 다른 고객사에 노출되면 안 된다.
2. **외부 통신 금지**: `backend/app/adapters/` 밖의 코드는 네트워크 호출을 하지 않는다. 프론트엔드도 외부 CDN, 외부 폰트, 원격 분석을 쓰지 않는다.
3. **LUDA 자산과 고객 데이터의 분리**: 자산 테이블에는 고객 데이터가, 고객 데이터 테이블에는 자산 원본이 들어가지 않는다. 고객 데이터는 자산의 특정 버전을 ID로 참조한다.

명세가 모호하거나 이 원칙과 충돌하는 상황이 생기면 추측으로 구현하지 말고 질문하라.

---

## 1. 기술 스택

### Backend
- Python 3.12
- FastAPI, Pydantic v2
- SQLAlchemy 2.0 (typed ORM), Alembic (마이그레이션)
- DB: `DB_TYPE` 환경변수로 `sqlite`(기본) / `postgresql` / `mssql` 전환. Phase 0은 sqlite·postgresql, Phase 1에서 mssql(pyodbc) 추가
- 엑셀: openpyxl (읽기 시 `keep_vba=False`, 수식 분석 시 `data_only=False`), pandas
- 온톨로지 내보내기: rdflib (Turtle, JSON-LD 직렬화만 사용, 원격 로딩 기능 사용 금지)
- 이름 유사도: rapidfuzz (용어·개념 병합 후보 탐지)
- 인증: argon2-cffi, JWT(httpOnly 쿠키)
- 암호화: cryptography(Fernet) — 어댑터 인증 정보 저장용
- 테스트: pytest, pytest-cov, httpx(TestClient 용도로만)
- 품질: ruff, mypy(strict는 `app/core`만)

### Frontend
- React 18, Vite, TypeScript(strict)
- Tailwind CSS (로컬 빌드, CDN 금지)
- React Router, TanStack Query, Zustand
- React Flow(`@xyflow/react`): FlowDesk, I/F 연결 그래프, OntoMap 개념 그래프
- Recharts: 대시보드 차트
- 폰트: Pretendard를 패키지로 번들 (외부 폰트 로딩 금지)
- i18n: react-i18next, 기본 `ko`, `en` 키 구조만 준비
- 테스트: Vitest, Testing Library, Playwright(핵심 시나리오 E2E만)

### 배포
- Docker Compose (backend, frontend(nginx 정적 서빙), 선택적 postgres)
- 단독 실행 스크립트: `scripts/run_standalone.sh`, `scripts/run_standalone.ps1` (uvicorn + 빌드된 정적 파일)

---

## 2. 레포 구조

```
fde-toolbox/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py              # 환경변수 (pydantic-settings)
│   │   ├── db/                    # 엔진, 세션, base, mixins
│   │   ├── core/                  # 공통 코어
│   │   │   ├── tenancy/           # 테넌트 컨텍스트, 필터, 의존성
│   │   │   ├── auth/
│   │   │   ├── users/
│   │   │   ├── tenants/           # 고객사, 과제(engagement)
│   │   │   ├── systems/           # 시스템 레지스트리
│   │   │   ├── assets/            # LUDA 자산 라이브러리
│   │   │   ├── audit/
│   │   │   ├── files/             # 첨부파일 저장소
│   │   │   ├── transfer/          # 가져오기·내보내기
│   │   │   └── promote/           # 승격 (Phase 3)
│   │   ├── modules/
│   │   │   ├── discoveryq/
│   │   │   ├── flowdesk/
│   │   │   ├── interfaces/        # I/F 관리
│   │   │   ├── exmigrate/
│   │   │   ├── ontomap/
│   │   │   ├── specforge/
│   │   │   ├── devtracker/
│   │   │   └── agenthub/
│   │   └── adapters/              # 외부 통신은 여기서만
│   │       ├── base.py
│   │       ├── registry.py
│   │       ├── llm/
│   │       ├── agent_runtime/     # 인터페이스만
│   │       └── git/               # 인터페이스만
│   ├── alembic/
│   ├── seeds/                     # 초기 자산, 데모 데이터
│   └── tests/
│       ├── isolation/             # 테넌트 격리 테스트
│       ├── architecture/          # 외부 통신 금지 등 구조 테스트
│       └── modules/
├── frontend/
│   └── src/
│       ├── app/                   # 라우팅, 레이아웃, 테넌트 전환기
│       ├── core/                  # 공통 화면 (고객사, 과제, 시스템, 자산, 감사)
│       ├── modules/<module>/
│       ├── components/            # 공통 UI
│       ├── api/                   # API 클라이언트 (TanStack Query 훅)
│       └── i18n/
├── docs/
│   ├── Spec.md
│   ├── Devin.md
│   ├── adr/                       # 설계 결정 기록
│   ├── schemas/                   # 가져오기·내보내기 JSON 스키마
│   └── CHANGELOG.md
├── scripts/
├── docker-compose.yml
└── README.md
```

모듈은 서로의 내부 코드를 import 하지 않는다. 모듈 간 연결은 `core`의 서비스와 ID 참조로만 한다.

---

## 3. 테넌시 구현

### 3.1 테이블 분류

| 분류 | 규칙 | 예 |
|---|---|---|
| 테넌트 데이터 | `TenantScopedMixin` 사용: `tenant_id`(NOT NULL, FK, 인덱스) | 과제, 시스템, 세션, 흐름도, I/F, 작업, 에이전트 인스턴스 |
| 자산 | `AssetMixin` 사용: `tenant_id` 컬럼 없음, `asset_id` + `version` | 질문, 흐름 템플릿, 상위 온톨로지, 명세 템플릿, 규칙팩, 에이전트 템플릿 |
| 전역 | 둘 다 아님 | 사용자, 고객사 자체, 전역 설정 |

### 3.2 강제 방식
- 요청마다 `TenantContext`(현재 사용자, 허용된 tenant_id 목록, 현재 tenant_id)를 FastAPI 의존성으로 만든다.
- 테넌트 데이터 조회는 반드시 `TenantScopedRepository`를 통해 한다. 이 레포지토리는 모든 쿼리에 `tenant_id` 조건을 자동으로 붙이고, 생성 시 `tenant_id`를 컨텍스트에서 채운다. 요청 본문의 `tenant_id`는 무시한다.
- SQLAlchemy `do_orm_execute` 이벤트로 `TenantScopedMixin` 테이블에 `tenant_id` 조건이 없는 SELECT가 실행되면 개발·테스트 환경에서 예외를 던진다.
- 다른 테넌트의 리소스 ID로 접근하면 403이 아니라 **404**를 반환한다(존재 여부 노출 방지).
- Phase 3 호스팅 모드: PostgreSQL RLS 정책을 Alembic 마이그레이션으로 추가하고, 세션 시작 시 `SET app.tenant_id`를 설정한다.

### 3.3 격리 테스트 (필수, Phase 0부터)
`tests/isolation/`에 다음을 구현하고 이후 모든 신규 엔드포인트에 적용한다.
- 고객사 A, B와 각 사용자를 만드는 픽스처.
- 등록된 모든 라우트를 순회하며 A 사용자로 B 리소스 ID에 접근 시 404인지 검사하는 **자동 순회 테스트**.
- 목록 API가 다른 고객사 데이터를 포함하지 않는지 검사.
- 내보내기 파일에 다른 고객사 데이터가 없는지 검사.
- 신규 모델이 `TenantScopedMixin`/`AssetMixin`/전역 목록 중 하나로 분류되지 않으면 실패하는 테스트.

### 3.4 외부 통신 금지 테스트 (필수)
`tests/architecture/`에 다음을 구현한다.
- `app/adapters/` 밖의 파이썬 파일에서 `httpx`, `requests`, `urllib.request`, `aiohttp`, `socket`, `anthropic` import 시 실패.
- 프론트엔드 빌드 결과물(`dist/`)에 `http://`·`https://`로 시작하는 외부 자원 참조(script, link, font, img)가 있으면 실패. 허용 목록은 빈 목록에서 시작.

---

## 4. 데이터 모델 (핵심)

필드는 최소 기준이다. 모든 테이블은 `id`(UUID), `created_at`, `updated_at`, `created_by`를 가진다.

### 4.1 공통 코어
- `tenants`: name, code, status(active/archived), deployment_mode, notes
- `users`: email, password_hash, name, role(luda_admin/fde/client_admin/client_user), home_tenant_id(nullable), is_active
- `user_tenant_assignments`: user_id, tenant_id
- `engagements` (T): name, status, start_date, end_date, lead_fde_id, description
- `systems` (T): name, short_name, type, owner_dept, hosting, db_type, notes
- `asset_items` (A): asset_type(question_bank/flow_template/if_template/upper_ontology/glossary_template/spec_template/rule_pack/agent_template), asset_key, version, title, payload(JSON), status(draft/published/deprecated), change_note
- `audit_logs` (T 또는 전역): tenant_id(nullable), actor_id, action, target_type, target_id, detail(JSON), ip, at — UPDATE/DELETE 금지(애플리케이션 계층에서 차단, 테스트 포함)
- `files` (T): owner_type, owner_id, filename, mime, size, storage_path, sha256
- `adapter_settings` (T): adapter_key, enabled, approved_by, approved_at, approval_note, encrypted_credentials, config(JSON)

(T) = TenantScopedMixin, (A) = AssetMixin

### 4.2 모듈 (요약)
- DiscoveryQ: `discovery_subjects`(T), `discovery_sessions`(T: engagement_id, type(interview/coaching), subject_id, date), `discovery_session_questions`(T: question_ref(자산 ID+버전) 또는 custom_text, answer), `discovery_insights`(T), `discovery_action_items`(T), `discovery_custom_questions`(T)
- FlowDesk: `flows`(T: engagement_id, kind(as_is/to_be), pair_id, perspective, title), `flow_snapshots`(T: flow_id, graph(JSON), note)
  - 그래프 JSON: `{ schema_version, nodes:[{id,type,label,lane,system_id?,position,data}], edges:[{id,source,target,label}], lanes:[...] }`
- I/F 관리: `interfaces`(T: if_code, name, source_system_id, target_system_id, link_type, schedule, description, owner, status, notes), `interface_uploads`(T: file_id, result(JSON))
- ExMigrate: `xl_analyses`(T: engagement_id, file_id, status, report(JSON)), `xl_erd_drafts`(T: analysis_id, erd(JSON), confirmed)
- OntoMap:
  - `onto_terms`(T: term, definition, abbreviation, status(candidate/confirmed/deprecated), concept_id(nullable), source_type, source_id)
  - `onto_term_aliases`(T: term_id, alias, department)
  - `onto_concepts`(T: name, definition, parent_ref — 상위 온톨로지 `{asset_id, version, concept_key}` 또는 `parent_concept_id` 중 하나, id_attribute_id, owner_dept, status)
  - `onto_attributes`(T: concept_id, name, data_type, unit, required, constraints(JSON))
  - `onto_relations`(T: source_concept_id, name, target_concept_id, cardinality, inverse_name)
  - `onto_mappings`(T: target_kind(concept/attribute/relation), target_id, system_id, table_name, column_name, interface_id, origin(manual/exmigrate/interface))
  - `onto_candidates`(T: kind(term/concept/attribute/relation), name, payload(JSON), source_type, source_id, status(open/accepted/merged/ignored), resolved_into_id)
  - 상위 온톨로지 자산 payload: `{ schema_version, concepts:[{concept_key, name, definition, parent_key?, attributes:[...], relations:[...]}] }` — `concept_key`는 버전이 바뀌어도 유지되는 안정 식별자
- SpecForge: `spec_documents`(T: engagement_id, doc_type(spec/devin), title, template_ref, rule_pack_refs, source_refs(JSON), status), `spec_versions`(T: document_id, version, content_md, note)
- DevTracker: `dev_projects`(T: engagement_id, name, status, stack, repo_url, env_notes, deploy_notes, spec_document_ids), `dev_tasks`(T: project_id, title, status, priority, assignee_id, due, pause_note, resume_note), `dev_prompts`(T: task_id, tool, prompt, result_summary, at), `dev_issues`(T), `dev_test_records`(T), `dev_costs`(T), `dev_docs`(T)
- AgentHub: 템플릿은 `asset_items`(asset_type=agent_template)의 payload로 저장. 평가 세트와 평가 결과는 자산 버전에 종속되지만 **고객사에서 수행한 평가 결과는 테넌트 데이터**로 분리: `agent_eval_cases`(A 소속, 템플릿 버전 참조), `agent_eval_runs`(T: template_ref, run_at, results(JSON), evidence_file_ids), `agent_instances`(T: template_ref, engagement_id, deployment, system_ids, overrides(JSON), concept_bindings(JSON: `{concept_key: onto_concept_id}`), status, owner_id, dev_project_id). 템플릿 payload에는 `concepts: [concept_key...]`(상위 온톨로지 기준)를 둔다, `agent_ops_records`(T: instance_id, period_start, period_end, runs, success, failure, incidents, cost, feedback)

자산 참조(`template_ref`, `question_ref` 등)는 `{asset_id, version}` 형태로 저장하고, 참조한 버전이 폐기되어도 고객 데이터가 깨지지 않게 한다.

---

## 5. API 규칙

- 테넌트 데이터: `/api/v1/t/{tenant_id}/...` — 경로의 tenant_id는 `TenantContext`의 허용 목록으로 검증한다.
- 자산: `/api/v1/assets/...` — 조회는 인증 사용자 전체, 수정은 luda_admin.
- 관리: `/api/v1/admin/...` — luda_admin 전용.
- 어댑터: `/api/v1/t/{tenant_id}/adapters/...`
- 목록 API는 페이지네이션(`limit`, `cursor`)과 기본 정렬을 가진다.
- 오류 형식: `{ "error": { "code": "...", "message": "..." } }`, 메시지는 i18n 키로.
- 모든 쓰기 요청은 감사 로그를 남긴다(서비스 계층 데코레이터로 일관 적용).
- OpenAPI 스펙에서 프론트엔드 타입을 생성한다(`openapi-typescript`).

---

## 6. 어댑터 구현

### 6.1 인터페이스
```python
class Adapter(Protocol):
    key: str                    # "llm", "agent_runtime", "git"
    display_name: str
    def data_egress_notice(self) -> EgressNotice: ...   # 반출 데이터 종류, 목적지, 사용 기능
    def validate_config(self, config: dict, credentials: dict) -> None: ...
    def health_check(self, ctx: AdapterContext) -> HealthResult: ...
```
- `AdapterRegistry`가 어댑터를 등록·조회한다.
- 기능 코드는 `get_adapter(ctx, "llm")`로 어댑터를 얻으며, 비활성이면 `AdapterDisabled` 예외가 발생하고 기능은 대체 경로로 전환한다.
- 전역 설정 `ADAPTERS_ALLOWED=false`이면 레지스트리가 아무 어댑터도 반환하지 않고, 프론트엔드는 어댑터 메뉴를 숨긴다.
- 모든 외부 호출은 `AdapterContext.record_call()`로 감사 로그를 남긴다(요청 본문 전체는 저장하지 않고 크기·기능·결과만).

### 6.2 LLM 어댑터 (Phase 2)
- Anthropic Python SDK 사용. 모델명은 어댑터 config에서 읽고 코드에 하드코딩하지 않는다.
- 제공 메서드: `generate_json(prompt, schema)`, `generate_markdown(prompt)`.
- JSON 응답은 스키마로 검증하고 실패 시 1회 재시도 후 오류를 사용자에게 보여준다.
- 타임아웃, 최대 토큰은 config로.

### 6.3 프롬프트 복사 모드 (LLM 비활성 시 대체 경로)
- 같은 프롬프트 빌더를 사용해 프롬프트 문자열을 화면에 보여주고 복사 버튼을 제공한다.
- 사용자가 결과를 붙여넣으면 LLM 응답과 동일한 파서·검증기로 처리한다.
- 즉 **프롬프트 빌더와 결과 파서는 어댑터와 독립된 모듈 코드**이고, 어댑터는 전송만 담당한다.

### 6.4 agent_runtime, git 어댑터
- Protocol과 설정 화면 항목만 만든다. 실제 구현은 하지 않으며 활성화 시도 시 "미구현" 안내.


---

## 7. OntoMap 구현 규칙
- 후보 추출기는 모듈별 소스(ExMigrate ERD, I/F, FlowDesk, DiscoveryQ)를 읽는 **순수 함수**로 구현하고, 결과는 항상 `onto_candidates`에 쌓는다. 추출기가 확정 데이터를 직접 만들지 않는다.
- LLM 결과(용어 추출, 관계 제안, 정의 초안)도 같은 후보 형식으로 변환해 후보 목록에 넣는다. 프롬프트 빌더·결과 파서는 6.3절의 규칙을 따른다.
- 같은 소스를 다시 추출하면 이미 처리된 후보는 다시 만들지 않는다(source_type + source_id + name 기준 멱등성).
- 병합 후보 탐지: 정규화(공백·특수문자·대소문자 제거) 후 rapidfuzz 유사도 기준값 이상인 기존 항목을 제시. 기준값은 설정으로.
- 검증기(순환 상속, 고아 개념, 정의 없는 확정 용어, 미매핑 개념, 중복 이름)는 저장을 막지 않고 경고 목록을 반환한다. 순환 상속만 저장을 막는다.
- OWL(Turtle)·JSON-LD 내보내기의 네임스페이스는 `DEPLOYMENT_BASE_IRI` + 고객사 코드로 만든다. 상위 온톨로지 개념은 LUDA 네임스페이스로, 고객사 개념은 `rdfs:subClassOf`로 연결한다. 내보내기에 매핑 정보는 선택 옵션으로 포함한다.
- 격리: 상위 온톨로지는 자산이므로 모든 고객사가 조회하지만, 고객사 개념·용어·매핑은 테넌트 데이터다. 승격 없이 고객사 개념이 상위 온톨로지에 들어가는 경로가 없어야 한다(테스트 포함).

---

## 8. 프론트엔드 규칙

- 레이아웃: 좌측 내비게이션(단계별 모듈 그룹: 진단/분석/설계/구축/운영 + 공통), 상단 고객사·과제 선택기.
- 현재 고객사가 바뀌면 TanStack Query 캐시를 고객사 키로 분리해 이전 고객사 데이터가 화면에 잠시라도 보이지 않게 한다.
- 모듈 간 "다음 단계로 보내기"는 대상 모듈의 생성 화면을 입력값이 채워진 상태로 여는 방식으로 구현한다.
- 모든 문자열은 i18n 키 사용. 하드코딩 금지.
- 반응형: 데스크톱 우선, 태블릿까지 사용 가능. 캔버스 화면은 데스크톱 전용 안내 허용.
- 접근성: 폼 라벨, 키보드 이동, 대비 기준 준수.

---

## 9. 초기 데이터 (seeds)

- LUDA 관리자 초기화 명령: `python -m app.cli init-admin`
- 자산:
  - DiscoveryQ 질문 뱅크: 8개 카테고리 × 카테고리당 최소 8문항 (한국어)
  - 흐름 템플릿 2종: "도료 제조 수주→생산→출하", "품질 검사 및 부적합 처리"
  - I/F 엑셀 템플릿: "인터페이스 리스트", "시스템 연동정보" 두 시트
  - Spec 템플릿, Devin 템플릿 각 1종 (이 문서들의 구조를 기반으로)
  - 기본 규칙팩 1종 (Spec.md 6.6절)
  - 상위 온톨로지 "제조 공통" v1: 약 20개 개념(제품, 원자재, 배합·레시피, 공정, 설비, 작업지시, 로트, 품질검사, 검사항목, 부적합, 고객, 주문, 출하, 공급사, 입고, 창고, 재고, 작업자, 교대, 규격)과 주요 속성·관계
  - 용어 사전 엑셀 템플릿: 표준 용어, 정의, 부서별 호칭, 약어 컬럼
  - 에이전트 템플릿 예시 1종 (예: "생산 일보 요약 에이전트") + 평가 케이스 3건
- 데모 명령: `python -m app.cli seed-demo` — "데모 제조사" 고객사, 과제 1건, 시스템 6개, I/F 15건, 용어 20개(부서별 호칭 포함), 도료 제조 특화 개념 3개(예: 배합비, 점도 규격, 도막 검사)와 일부 매핑, FDE·고객사 사용자 각 1명

---

## 10. 단계별 작업

각 단계는 여러 개의 작은 PR로 나눈다. 단계 완료 기준을 모두 실행 증거로 보여야 다음 단계로 넘어간다.

### Phase 0 — 코어, DevTracker MVP, AgentHub 레지스트리
1. 레포 초기화: 구조, 린트, 포매터, CI(GitHub Actions: backend 테스트, frontend 테스트·빌드, 아키텍처 테스트), docker-compose, README
2. DB 계층: 엔진·세션, `TenantScopedMixin`/`AssetMixin`, Alembic 초기 마이그레이션, sqlite·postgresql 양쪽 CI 테스트
3. 인증·사용자·배정, `TenantContext`, 권한 의존성
4. 고객사·과제·시스템 레지스트리 CRUD
5. 격리 테스트 프레임워크(3.3)와 외부 통신 금지 테스트(3.4)
6. 감사 로그, 첨부파일 저장소
7. 자산 라이브러리 기본(CRUD, 버전, 자산 패키지 가져오기·내보내기)
8. 고객사 전체 내보내기·가져오기(ZIP)
9. 프론트엔드 셸: 로그인, 레이아웃, 고객사·과제 선택기, 공통 화면
10. DevTracker: 프로젝트, 작업(칸반·목록), 중단·재개 메모, 프롬프트 기록, 프로젝트 대시보드
11. AgentHub: 템플릿 등록·버전·diff, 평가 케이스, 평가 결과 수동 입력, 인스턴스 등록·상태 관리
12. 홈 대시보드(역할별)

**완료 기준**
- 고객사 A·B 생성 후 격리 자동 순회 테스트 통과
- 외부 통신 금지 테스트 통과, 빌드 결과물에 외부 자원 참조 0건
- 에이전트 템플릿 v1·v2 등록, v2로 A에 인스턴스 기록, B 사용자에게 보이지 않음을 E2E로 확인
- `docker compose up` 한 번으로 실행되고 `init-admin`, `seed-demo`가 동작

### Phase 1 — I/F 관리, DiscoveryQ, OntoMap 용어 사전, MSSQL
1. I/F 엑셀 템플릿 다운로드·업로드·검증 결과 화면·미등록 시스템 처리
2. I/F 목록 CRUD, 대시보드, 연결 그래프
3. DiscoveryQ 질문 뱅크 탐색, 대상자, 세션 워크시트, 인사이트, 액션 아이템, 고객사 전용 질문
4. 세션 Markdown 내보내기, 액션 아이템 CSV
5. OntoMap 용어 사전: 용어 CRUD, 부서별 호칭, 엑셀 템플릿 가져오기·내보내기, DiscoveryQ 세션 워크시트에서 텍스트 선택 → "용어로 등록"(후보 생성)
6. MSSQL 지원 및 CI(가능하면 컨테이너로, 불가하면 수동 검증 절차 문서화)

**완료 기준**: 샘플 엑셀 업로드 → 그래프 확인, 인터뷰 세션 기록 → 세션에서 용어 3건 등록 → 용어 사전에서 확정 → 엑셀 내보내기가 E2E로 통과

### Phase 2 — FlowDesk, ExMigrate, SpecForge, LLM 어댑터
1. 어댑터 프레임워크, 활성화 절차(반출 범위 고지·승인·암호화 저장), 호출 감사
2. LLM 어댑터, 프롬프트 복사 모드
3. FlowDesk 캔버스, 템플릿 시작, 시스템 레지스트리 연결, As-Is/To-Be 짝, 스냅샷, 내보내기(JSON/PNG/SVG/Mermaid)
4. FlowDesk 생성: 프롬프트 빌더와 결과 파서, 관점별 프롬프트
5. ExMigrate 구조 분석, 1·2단계 수식 분석, ERD 초안·확정, DDL·적재 스크립트 생성
6. SpecForge 템플릿 매핑, 규칙팩 삽입, 용어 사전 섹션 삽입, 편집기·버전·diff, 보강(LLM/복사 모드)
7. 모듈 간 보내기: DiscoveryQ→FlowDesk, 각 모듈→SpecForge, SpecForge→DevTracker, AgentHub 운영→DevTracker 이슈

**완료 기준**: 데모 과제에서 인사이트 → 흐름도 → Spec/Devin.md → DevTracker 프로젝트까지 E2E 통과. LLM 어댑터 **비활성** 경로는 CI에서, 활성 경로는 실제 키로 수동 검증 후 증거 첨부

### Phase 3 — OntoMap 개념 모델, 승격, 운영 기록, 호스팅 모드
1. OntoMap 개념·속성·관계 CRUD, 상위 온톨로지 상속, 검증기
2. OntoMap 데이터 매핑(시스템·테이블·컬럼·I/F), 커버리지 표시
3. OntoMap 후보 추출기(ExMigrate ERD, I/F, FlowDesk), 후보 목록 화면(확정·병합·무시), LLM 제안(어댑터/복사 모드)
4. OntoMap 개념 그래프, 내보내기(Turtle, JSON-LD, Mermaid, Markdown)
5. SpecForge 개념 모델 섹션·개념-테이블 매핑표 삽입, AgentHub 개념 바인딩과 미바인딩 경고
6. 승격 절차(식별 정보 의심 표시, 체크리스트, 관리자 검토, 새 버전 반영)
7. AgentHub 운영 기록 입력·CSV 가져오기·대시보드
8. 통합 검색(현재 고객사 범위 내에서만)
9. PDF 내보내기(서버 측 렌더링, 외부 서비스 금지)
10. PostgreSQL RLS, 호스팅 모드 설정
11. 백업·복원 명령

**완료 기준**: 데모 과제 ERD·I/F에서 후보를 추출해 개념 10개를 확정·매핑하고 Turtle 내보내기가 rdflib로 다시 파싱됨. 에이전트 인스턴스의 개념 바인딩 완료. A 인스턴스 개선을 템플릿 v3로 승격 → B에 v3 인스턴스 기록, 승격된 자산에 A 식별 정보 없음. RLS 활성 상태에서 격리 테스트 전체 통과

---

## 11. 작업 규칙

1. **완료는 실행 증거로만 선언한다.** PR 설명에 테스트 실행 결과, 필요 시 스크린샷이나 E2E 녹화를 첨부한다. "구현했습니다"만으로는 완료가 아니다.
2. **작게 나눈다.** PR 하나는 하나의 목적만 가진다. 리팩터링과 기능 추가를 섞지 않는다.
3. **명세에 없는 기능, 라이브러리, 외부 호출을 추가하지 않는다.** 필요하다고 판단되면 PR 설명에 제안으로만 적는다.
4. **대안을 비교할 때**는 합의되는 사실, 갈리는 지점, 그 전제, 판단 근거를 분리해 `docs/adr/`에 기록한다.
5. **질문을 먼저 한다.** 명세 모호, 원칙 충돌, 범위 확대가 필요한 경우 구현 전에 질문한다.
6. **문서를 함께 갱신한다.** 동작이 바뀌면 `docs/CHANGELOG.md`, 가져오기·내보내기 형식이 바뀌면 `docs/schemas/`와 `schema_version`을 갱신한다.
7. **비밀 정보를 커밋하지 않는다.** `.env.example`만 커밋한다.
8. 커밋 메시지: `type(scope): 설명` (feat, fix, refactor, test, docs, chore). scope는 모듈명 또는 `core`.

---

## 12. 완료 정의 (Definition of Done)

모든 PR은 다음을 만족해야 한다.
- 백엔드·프론트엔드 테스트 통과, 신규 코드 커버리지 80% 이상(core는 90%)
- 격리 테스트·외부 통신 금지 테스트 통과
- 신규 엔드포인트가 권한·테넌트 검사와 감사 로그를 가짐
- 신규 UI 문자열이 i18n 키로 관리됨
- ruff, mypy, eslint, tsc 오류 0건
- 실행 증거가 PR 설명에 첨부됨

---

## 13. 환경 변수

| 변수 | 설명 | 기본값 |
|---|---|---|
| `DB_TYPE` | sqlite / postgresql / mssql | sqlite |
| `DATABASE_URL` | DB 연결 문자열 | `sqlite:///./data/fde.db` |
| `DATA_DIR` | 첨부파일·백업 저장 경로 | `./data` |
| `SECRET_KEY` | JWT 서명 키 | (필수) |
| `ENCRYPTION_KEY` | 어댑터 인증 정보 암호화 키(Fernet) | (필수) |
| `DEPLOYMENT_MODE` | standalone / hosted | standalone |
| `ADAPTERS_ALLOWED` | 어댑터 기능 전체 허용 여부 | false |
| `MAX_UPLOAD_MB` | 업로드 최대 크기 | 20 |
| `DEFAULT_LOCALE` | 기본 언어 | ko |
| `DEPLOYMENT_BASE_IRI` | 온톨로지 내보내기 네임스페이스 기준 IRI | `https://ludaresearch.org/onto/` |

---

## 14. 참고 — 기존 기획과의 관계

이 툴박스는 기존에 개별 앱으로 기획한 CoachQ(현 DiscoveryQ), BusinessFlowDesk, 인터페이스 관리, ExMigrate, DevTracker를 통합한다. 기존 문서와 이 문서가 충돌하면 **이 문서가 우선**한다. 주요 변경점은 다음과 같다.
- 백엔드를 FastAPI로 통일 (DevTracker·CoachQ의 Express 계획 폐기)
- 인터페이스 관리의 시스템 정보를 공통 코어의 시스템 레지스트리로 승격
- BusinessFlowDesk는 FlowDesk로 이름을 줄이고, LLM 호출을 선택형 어댑터로 전환
- ExMigrate는 외부 DB 적재 대신 스크립트 생성까지로 범위 조정, 3단계 수식 해석은 범위 외
- 인터페이스 관리의 감사 로그·인증을 공통 코어로 이동
- OntoMap(온톨로지) 모듈 신규 추가 — 용어 사전은 Phase 1, 개념 모델·매핑은 Phase 3
