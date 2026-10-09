# Changelog

형식: [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/). 가져오기·내보내기 형식이 바뀌면 `docs/schemas/`와 `schema_version`을 함께 올린다.

## [Unreleased]

### Changed
- CoachQ를 DiscoveryQ로 이름 변경: 화면·문서, API 경로 `/coachq` → `/discoveryq`, 모듈, 테이블 `coach_*` → `discovery_*`(마이그레이션 0005, 데이터 이전·되돌리기 지원), OntoMap 후보 출처 `coach_session` → `discovery_session`, 질문 뱅크 자산 키 `discoveryq-question-bank`. 이전 경로 별칭은 두지 않으며, 이름 변경 전에 만든 고객사 ZIP은 다시 가져올 수 없다.

### Added — Phase 2
- 사용자 매뉴얼(한/영, 앱 위쪽 **매뉴얼** 버튼 → 지금 보는 화면의 설명서, `/manual/:topic`): 시작하기, DiscoveryQ, I/F 관리, OntoMap, FlowDesk, DevTracker, AgentHub, 공통 화면, 외부 연동, 고객사·사용자 관리, 설치 및 실행. 원문은 `frontend/src/manual/{ko,en}/*.md`이며 화면 언어를 따르고, 외부 링크 없이 번들됨. 기능을 추가·변경하면 같은 PR에서 매뉴얼도 갱신한다.
- 어댑터 프레임워크(`app/adapters/`): `Adapter` 프로토콜·레지스트리, `ADAPTERS_ALLOWED=false`이면 목록이 비고 `get_adapter`가 `AdapterDisabled`(오프라인 경로 사용)를 던짐. 고객사별 활성화 `adapter_activations`(마이그레이션 0006): FDE 요청 → 반출 범위(전송 대상·데이터·기능) 확인 후 고객사 관리자 승인(고객사 관리자가 없으면 LUDA 관리자가 사유와 함께 승인) → 활성, 반려·비활성화 시 인증 정보 삭제. 인증 정보는 `ENCRYPTION_KEY`로 Fernet 암호화하며 API 응답·감사 로그·고객사 ZIP에 포함하지 않음(가져온 활성화는 비활성으로 표시). 요청·승인·반려·비활성화·외부 호출(`adapter.call`: 기능, 요청/응답 바이트, 결과, 소요 시간, 본문 미저장)을 감사 로그에 기록.
- LLM 어댑터(Anthropic SDK, 모델·최대 토큰·타임아웃 설정): `generate_markdown`, 스키마 검증 `generate_json`(실패 시 1회 재요청 후 `llm_invalid_response`), 연결 확인. 프롬프트 빌더·결과 파서(`app/core/prompting.py`)는 전송과 분리되어 프롬프트 복사 모드에서도 같은 파서를 쓴다. Agent Runtime·Git 어댑터는 규격과 설정 항목만 둠.
- 어댑터 설정 화면(공통 › 외부 연동, `ADAPTERS_ALLOWED=true`일 때만 표시): 반출 범위 고지, 활성화 요청, 승인·반려·비활성화, 연결 확인.
- FlowDesk 캔버스(설계 › FlowDesk, `@xyflow/react`): `flows`·`flow_snapshots`(마이그레이션 0007), 그래프 JSON `schema_version: 1` 검증(노드·연결선·스윔레인, 시스템 레지스트리 참조는 같은 고객사만), 게시된 `flow_template` 자산으로 시작(레인·열 자동 배치), As-Is/To-Be 짝(기존 흐름 연결 또는 그래프 복사로 짝 생성, 삭제·해제 시 짝 정리), 스냅샷 저장·복원(버전 번호), 내보내기 JSON·Mermaid(서버, 감사 로그 기록)·SVG·PNG(브라우저, 외부 리소스 없음), JSON 가져오기. E2E `e2e/flowdesk.spec.ts`.
- FlowDesk 흐름 생성: 관점별(현업·PM·개발자·경영진·컨설턴트) 프롬프트 빌더(업무 설명, 선택한 DiscoveryQ 인사이트, 시스템 레지스트리 이름, 결과 JSON 스키마), 결과 파서·정규화(알 수 없는 노드 유형→업무, 중복 노드·끊긴 연결선 제거, 시스템 이름/약칭→레지스트리 연결, 연결 순서 기반 자동 배치). `GET /flowdesk/insights`, `POST /flowdesk/generate/prompt`, `POST /flowdesk/generate`(`answer`가 있으면 프롬프트 복사 모드, 없으면 LLM 어댑터; 비활성 시 `adapter_disabled`, 형식 오류 시 `flow_result_invalid`). 감사 로그 `flowdesk.flow_generate`(방식·관점·인사이트 수·노드 수). E2E `e2e/flowdesk-generate.spec.ts`.

### Added — Phase 1
- DiscoveryQ Word 보고서(`python-docx`, 오프라인 생성): 세션 보고서 `GET /discoveryq/sessions/{id}/report.docx`, 인게이지먼트 진단 보고서 `GET /discoveryq/engagements/{id}/report.docx`(ko/en, 내보내기 권한, 감사 로그 기록).
- I/F 관리: `interfaces`·`interface_uploads` 모델(마이그레이션 0002), I/F 엑셀 템플릿(`인터페이스 리스트`/`시스템 연동정보`) 다운로드·업로드·행 단위 검증·미등록 시스템 선택 등록 후 반영, 목록 CRUD·필터, 대시보드, 연결 그래프, 엑셀/CSV 내보내기(수식 주입 방지), 15건 샘플 워크북.
- DiscoveryQ: 질문 뱅크 탐색, 인터뷰 대상자, 세션 워크시트(질문·답변·인사이트·태그), 액션 아이템, 직접 질문, 세션 Markdown·액션 아이템 CSV 내보내기(마이그레이션 0003).
- OntoMap 용어 사전: 표준 용어·부서별 호칭·약어, 용어 사전 엑셀 가져오기/내보내기·CSV 내보내기, DiscoveryQ 답변에서 용어 후보 등록 후 확정·병합·무시(마이그레이션 0004).
- 데모 시드 확장: `seed-demo`가 샘플 워크북으로 I/F 15건을 업로드·반영하고, 도료 제조 용어 20개(배합비·점도 규격·도막 검사 포함, 부서별 호칭)를 확정 상태로 생성(`backend/seeds/samples/demo-glossary.json`).
- Phase 1 인수 E2E(`e2e/phase1.spec.ts`): 샘플 엑셀 업로드 → 연결 그래프 확인 → 인터뷰 세션 기록 → 세션에서 용어 3건 등록 → 용어 사전에서 확정 → 엑셀 내보내기 내용 확인.
- SQL Server 지원(`pip install ".[mssql]"`, ODBC Driver 18): 문자열 `NVARCHAR` 생성·바인드, 연쇄 삭제 앱 수준 대체(ADR 0002), `create-db` CLI, Docker `WITH_MSSQL` 빌드 인자와 `mssql` 프로필, CI `backend (mssql)` 잡, 수동 검증 절차(`docs/mssql.md`).
- 다른 데이터가 참조 중인 행 삭제 등 무결성 위반은 `409 conflict`로 응답.

### Added — Phase 0
- 공통 코어: 인증(Argon2, httpOnly JWT 쿠키), 사용자·역할·고객사 배정, `TenantContext`와 권한 의존성, 테넌트 세션 가드(읽기 조건 자동 부여·컨텍스트 없는 쓰기 거부), 교차 테넌트 404.
- 고객사·과제·시스템 레지스트리 CRUD, 첨부파일 저장소, 추가 전용 감사 로그와 CSV 내보내기, 역할별 홈 대시보드 API.
- LUDA 자산 라이브러리: 자산 CRUD, 버전·diff, 자산 패키지 가져오기/내보내기(`asset_package` v1), 기본 자산 8종 시드.
- 고객사 ZIP 내보내기/가져오기(`tenant_export` v1, ID 재발급·참조 재매핑).
- DevTracker MVP: 프로젝트, 태스크, 중단·재개 메모, 프롬프트 기록, 대시보드.
- AgentHub 레지스트리: 템플릿 버전·diff, 평가 케이스·수동 평가 결과, 인스턴스 등록·상태 관리.
- CLI: `migrate`, `init-admin`, `seed-assets`, `seed-demo`.
- 프론트엔드: 로그인, 단계별 내비게이션, 고객사·과제 선택기(고객사별 캐시 분리), 공통 화면, DevTracker, AgentHub, 역할별 홈, ko/en i18n, Pretendard 번들.
- 테스트: 라우트 자동 순회 격리 테스트, 외부 통신 금지 아키텍처 테스트, 빌드 산출물 외부 참조 검사, Playwright 인수 시나리오.
- 배포: Docker Compose(backend, nginx frontend, 선택적 PostgreSQL), 단독 실행 스크립트(sh/ps1), GitHub Actions CI.
