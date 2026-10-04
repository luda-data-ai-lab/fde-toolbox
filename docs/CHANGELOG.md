# Changelog

형식: [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/). 가져오기·내보내기 형식이 바뀌면 `docs/schemas/`와 `schema_version`을 함께 올린다.

## [Unreleased]

### Added — Phase 1
- I/F 관리: `interfaces`·`interface_uploads` 모델(마이그레이션 0002), I/F 엑셀 템플릿(`인터페이스 리스트`/`시스템 연동정보`) 다운로드·업로드·행 단위 검증·미등록 시스템 선택 등록 후 반영, 목록 CRUD·필터, 대시보드, 연결 그래프, 엑셀/CSV 내보내기(수식 주입 방지), 15건 샘플 워크북.
- CoachQ: 질문 뱅크 탐색, 인터뷰 대상자, 세션 워크시트(질문·답변·인사이트·태그), 액션 아이템, 직접 질문, 세션 Markdown·액션 아이템 CSV 내보내기(마이그레이션 0003).
- OntoMap 용어 사전: 표준 용어·부서별 호칭·약어, 용어 사전 엑셀 가져오기/내보내기·CSV 내보내기, CoachQ 답변에서 용어 후보 등록 후 확정·병합·무시(마이그레이션 0004).
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
