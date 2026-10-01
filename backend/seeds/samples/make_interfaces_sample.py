"""Regenerates interfaces-sample.xlsx: 15 fictional interfaces used by demos and E2E."""

from pathlib import Path

from app.modules.interfaces.excel import build_workbook

INTERFACES = [
    [
        "IF-MES-001",
        "작업지시 수신",
        "ERP",
        "MES",
        "DB Link",
        "1시간",
        "작업지시번호, 품목, 수량",
        300,
        "김생산",
        "운영",
        None,
    ],
    [
        "IF-MES-002",
        "생산실적 송신",
        "MES",
        "ERP",
        "DB Link",
        "1시간",
        "실적번호, 양품, 불량",
        1200,
        "김생산",
        "운영",
        None,
    ],
    ["IF-MES-003", "자재 투입 실적", "MES", "ERP", "API", "실시간", "LOT, 투입량", 5000, "김생산", "운영", None],
    [
        "IF-MES-004",
        "설비 상태 수집",
        "SCADA",
        "MES",
        "MQ",
        "실시간",
        "설비ID, 상태, 알람",
        80000,
        "박설비",
        "운영",
        None,
    ],
    ["IF-MES-005", "공정 검사 의뢰", "MES", "LIMS", "API", "실시간", "검사의뢰번호, 시료", 150, "이품질", "운영", None],
    ["IF-LIMS-001", "검사 결과 회신", "LIMS", "MES", "API", "실시간", "판정, 측정값", 150, "이품질", "운영", None],
    ["IF-LIMS-002", "출하 검사 성적서", "LIMS", "ERP", "File", "일 1회", "성적서 PDF", 40, "이품질", "운영", None],
    ["IF-WMS-001", "입고 예정 정보", "ERP", "WMS", "EAI", "30분", "PO, 품목, 수량", 200, "최물류", "운영", None],
    ["IF-WMS-002", "입고 확정", "WMS", "ERP", "EAI", "30분", "입고번호, 위치", 200, "최물류", "운영", None],
    ["IF-WMS-003", "출하 지시", "ERP", "WMS", "EAI", "30분", "출하번호, 고객", 120, "최물류", "운영", None],
    ["IF-WMS-004", "완제품 입고", "MES", "WMS", "DB Link", "1시간", "LOT, 수량", 400, "최물류", "개발", "2차 오픈"],
    ["IF-ERP-001", "원가 마감 데이터", "ERP", "그룹웨어", "File", "월 1회", "원가 요약", 1, "정재무", "운영", None],
    ["IF-ERP-002", "결재 상신", "ERP", "그룹웨어", "API", "실시간", "결재문서", 60, "정재무", "운영", None],
    [
        "IF-SCADA-001",
        "에너지 사용량",
        "SCADA",
        "ERP",
        "File",
        "일 1회",
        "전력, 용수",
        24,
        "박설비",
        "계획",
        "에너지 관리 과제",
    ],
    [
        "IF-LIMS-003",
        "표준 시험법 동기화",
        "LIMS",
        "MES",
        "DB Link",
        "주 1회",
        "시험법 마스터",
        10,
        "이품질",
        "폐기",
        "LIMS 교체로 중단",
    ],
]
SYSTEMS = [
    ["MES", None, "MES", "생산팀", "온프레미스", "MSSQL", "10.0.*.*", None],
    ["ERP", None, "ERP", "재무팀", "온프레미스", "Oracle", "10.0.*.*", None],
    ["LIMS", None, "LIMS", "품질팀", "온프레미스", "PostgreSQL", "10.1.*.*", None],
    ["WMS", None, "WMS", "물류팀", "클라우드", "MySQL", "***", None],
    ["SCADA", None, "SCADA", "설비팀", "온프레미스", "기타", "***", "OT망"],
    ["그룹웨어", "GW", "그룹웨어", "IT팀", "클라우드", None, "***", None],
]

if __name__ == "__main__":
    out = Path(__file__).with_name("interfaces-sample.xlsx")
    out.write_bytes(build_workbook(INTERFACES, SYSTEMS))
    print(out)
