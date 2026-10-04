# SQL Server(MSSQL) 지원

SQLite(기본)·PostgreSQL과 같은 코드·마이그레이션으로 SQL Server 2019+를 쓴다. 드라이버는 `pyodbc` + Microsoft ODBC Driver 18.

## 연결 설정

```bash
DB_TYPE=mssql
DATABASE_URL='mssql+pyodbc://<user>:<password>@<host>:1433/<database>?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
```

- 사내 인증서를 쓰는 서버라면 `TrustServerCertificate=yes` 대신 `Encrypt=yes`와 신뢰된 인증서를 쓴다.
- 비밀번호에 `@`, `:`, `/` 등이 있으면 URL 인코딩한다.
- 데이터베이스 생성 권한이 있는 계정이면 `python -m app.cli create-db`가 없는 DB를 만든다(Docker 기동 시 자동 실행, 다른 DB에서는 아무 일도 하지 않음). 권한이 없으면 DBA가 미리 만든다. 정렬 규칙(collation)은 서버 기본값을 그대로 써도 된다.

## 호환 처리 (`backend/app/db/mssql.py`)

| SQL Server 제약 | 처리 |
| --- | --- |
| `VARCHAR`는 서버 코드 페이지로 저장되어 한글이 `?`로 깨짐 | `String`/`Text`를 `NVARCHAR(n)`/`NVARCHAR(max)`로 생성하고, 바인드 파라미터도 `SQL_WVARCHAR`로 보낸다 |
| 같은 테이블로 가는 CASCADE 경로가 여럿이면 FK 생성 거부(오류 1785) — 모든 테넌트 테이블이 `tenants`로 CASCADE하므로 해당 | DDL에서 `ON DELETE`를 빼고, ORM이 행을 삭제하기 직전에 메타데이터에 선언된 `CASCADE`/`SET NULL`을 같은 트랜잭션에서 적용한다 |
| `IS 1` 불리언 비교 불가 | 불리언 컬럼은 `.is_(True)` 대신 컬럼 자체를 조건으로 쓴다 |

ORM 세션을 거치지 않은 코어 `DELETE`(예: `delete(Parent)`)는 SQL Server에서 자식 행을 지우지 않으므로, 부모를 지울 때는 ORM `db.delete(obj)`(리포지토리 `delete`)를 쓴다. 근거는 [ADR 0002](adr/0002-mssql-on-delete-emulation.md).

## Docker Compose

백엔드 이미지는 기본적으로 ODBC 드라이버를 넣지 않는다. `WITH_MSSQL=true`로 빌드하면 빌드 시점에 Microsoft 저장소에서 `msodbcsql18`과 `pyodbc`를 설치한다(실행 시 외부 통신 없음). 폐쇄망이면 인터넷이 되는 곳에서 이미지를 빌드해 `docker save`/`docker load`로 반입한다.

```bash
# 동봉된 SQL Server 컨테이너 사용
WITH_MSSQL=true DB_TYPE=mssql MSSQL_SA_PASSWORD='<강한 비밀번호>' \
DATABASE_URL='mssql+pyodbc://sa:<강한 비밀번호>@mssql:1433/fde?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes' \
  docker compose --profile mssql up -d --build

# 고객사 기존 SQL Server 사용: --profile 없이 DATABASE_URL만 해당 서버로
```

## 개발·테스트

```bash
# Ubuntu: ODBC Driver 18 설치
curl -fsSL -o /tmp/ms.deb "https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/packages-microsoft-prod.deb"
sudo dpkg -i /tmp/ms.deb && sudo apt-get update && sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc

cd backend && .venv/bin/pip install -e ".[dev,mssql]"
docker run -d --name fde-mssql -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD='Fde-Test-Pass-123' -p 1433:1433 \
  mcr.microsoft.com/mssql/server:2022-latest
export TEST_DATABASE_URL='mssql+pyodbc://sa:Fde-Test-Pass-123@localhost:1433/fde_test?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
DATABASE_URL="$TEST_DATABASE_URL" SECRET_KEY=x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x ENCRYPTION_KEY=x-x-x-x-x-x-x-x \
  .venv/bin/python -m app.cli create-db
.venv/bin/pytest
```

CI의 `backend (mssql)` 잡이 같은 절차를 SQL Server 2022 서비스 컨테이너로 실행한다.

## 고객사 SQL Server 수동 검증 절차

컨테이너를 쓸 수 없는 현장(예: 고객사 DBA가 관리하는 SQL Server)에서는 아래 순서로 확인하고 결과를 과제 기록에 남긴다. 운영 DB가 아닌 빈 검증용 DB를 쓴다.

1. 검증용 DB와 계정 준비: `db_owner`(또는 DDL·DML 권한) 계정, 빈 DB `fde_verify`.
2. 연결 확인: `python -c "import pyodbc; print(pyodbc.drivers())"`에 `ODBC Driver 18 for SQL Server`가 보이는지.
3. 마이그레이션: `DB_TYPE=mssql DATABASE_URL=... python -m app.cli migrate` → `database at head`.
4. 스키마 확인: `SELECT DATA_TYPE, COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS GROUP BY DATA_TYPE` 결과에 `varchar`/`text`가 없어야 한다.
5. 자동 테스트: 같은 서버의 별도 빈 DB를 `TEST_DATABASE_URL`로 지정해 `pytest` 전체 통과(테스트는 매번 모든 테이블을 비운다 — 검증용 DB에서만 실행).
6. 수동 시나리오: `init-admin` → `seed-assets` → `seed-demo` 후 브라우저에서
   - 고객사·과제 이름, DiscoveryQ 답변, OntoMap 용어·부서별 호칭에 한글을 입력하고 새로고침 후 그대로 보이는지,
   - I/F 엑셀 업로드·반영, 용어 사전 엑셀 가져오기·내보내기,
   - 과제 삭제 시 하위 DiscoveryQ 세션·DevTracker 프로젝트가 함께 지워지는지,
   - 관리자 화면에서 검증용 고객사 삭제가 204로 끝나고 다른 고객사 데이터는 남는지.
7. 정리: 검증용 DB 삭제.
