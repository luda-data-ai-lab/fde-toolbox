# ADR 0001 — 테넌트 격리 강제 방식

- 상태: 채택 (Phase 0)

## 합의되는 사실
- 고객사 데이터는 어떤 경로로도 다른 고객사에 노출되면 안 된다(Devin.md §0, §3).
- 테넌트 테이블은 `TenantScopedMixin`(`tenant_id` NOT NULL, 인덱스, FK)을 가진다.
- 교차 테넌트 리소스 ID 요청은 404, 요청 본문의 `tenant_id`는 무시한다.

## 갈리는 지점
1. **리포지토리 계층만으로 필터링** — 단순하지만 개발자가 세션을 직접 쓰면 누락된다.
2. **ORM 세션 이벤트로 강제** — `do_orm_execute`에서 `with_loader_criteria`로 모든 테넌트 모델 조회에 조건을 붙이고, flush 시 컨텍스트와 다른 `tenant_id` 쓰기를 거부한다. 누락 위험이 낮지만 코어 SQL(`select(table)`)은 대상이 아니다.
3. **PostgreSQL RLS** — DB 수준에서 가장 강하지만 SQLite 기본 배포에서 쓸 수 없다(Phase 3 과제).

## 전제
- 기본 배포는 SQLite 단독 실행이며 PostgreSQL은 선택이다.
- 코어 SQL 사용은 이관(export/import) 서비스로 한정하며, 여기서는 `tenant_id` 조건을 명시한다.

## 결정
2(세션 이벤트) + 1(`TenantScopedRepository`)을 함께 쓰고, 자동 라우트 순회 테스트(`tests/isolation`)로 모든 `/api/v1/t/{tenant_id}/...` 경로를 A/B 고객사로 검증한다. RLS는 Phase 3에서 PostgreSQL 배포에 추가한다.
