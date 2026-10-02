# ADR 0002 — SQL Server의 ON DELETE 처리

- 상태: 채택 (Phase 1)

## 합의되는 사실
- 모든 테넌트 테이블은 `tenant_id → tenants.id ON DELETE CASCADE`를 가지며, 고객사 삭제(`delete_tenant`)와 과제·세션 삭제가 DB 연쇄 삭제에 기대고 있다.
- SQL Server는 한 테이블로 가는 연쇄 경로가 둘 이상이면 FK 생성을 거부한다(오류 1785). 예: `tenants → coach_sessions → coach_session_questions`와 `tenants → coach_session_questions`.

## 갈리는 지점
1. **SQL Server용 별도 스키마** — 연쇄 경로를 하나만 남기도록 FK를 다르게 선언. 마이그레이션이 DB별로 갈라진다.
2. **트리거(`INSTEAD OF DELETE`)** — DB 안에서 해결되지만 SQL Server 전용 SQL을 마이그레이션마다 유지해야 한다.
3. **앱 수준 대체** — SQL Server에서만 DDL의 `ON DELETE`를 빼고, ORM flush 직전에 메타데이터의 `CASCADE`/`SET NULL`을 하위 테이블부터 적용.

## 결정
3. 모델·마이그레이션은 DB와 무관하게 하나로 두고, `app/db/mssql.py`가 컴파일 훅과 `before_flush` 이벤트로 처리한다. 삭제 대상은 서브쿼리로 넘겨 파라미터 수 제한(2100)에 걸리지 않게 하고, 하위 테이블을 역위상 순서로 지워 `ON DELETE` 없는 FK(예: `interfaces.source_system_id`)와 충돌하지 않게 한다.

## 결과
- 부모 삭제는 ORM(`db.delete`)을 거쳐야 SQL Server에서도 하위 행이 지워진다. 코어 `DELETE`로 부모를 지우는 코드는 SQL Server에서 FK 오류(409)가 난다.
- SQLite·PostgreSQL에서는 기존처럼 DB가 연쇄 삭제한다. 대체 로직은 `tests/core/test_mssql.py`가 모든 DB에서, 전체 테스트가 CI `backend (mssql)` 잡에서 검증한다.
