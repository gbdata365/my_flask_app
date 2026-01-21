# -*- coding: utf-8 -*-
"""
데이터베이스 데이터 확인 스크립트
"""

import sys
from pathlib import Path
import pandas as pd

# 상위 디렉토리의 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from module.db import get_db_connection

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_data():
    """데이터 확인"""
    conn = get_db_connection()

    print("=" * 100)
    print("1. 테이블 정보")
    print("=" * 100)

    # 테이블 존재 확인
    query = """
        SELECT table_name,
               (SELECT COUNT(*) FROM sbr_quarter_summary) as row_count
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'sbr_quarter_summary'
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("2. 컬럼 정보 (일부)")
    print("=" * 100)

    query = """
        SELECT column_name, data_type,
               COALESCE(character_maximum_length, numeric_precision) as max_length
        FROM information_schema.columns
        WHERE table_name = 'sbr_quarter_summary'
        ORDER BY ordinal_position
        LIMIT 20
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("3. 기본 통계")
    print("=" * 100)

    query = """
        SELECT
            "CRTR_YR" as 기준연도,
            "QU_SE_CD" as 분기,
            COUNT(*) as 지역수,
            SUM("ORG_합계") as 총사업체수,
            SUM("STATS_기업종사자수_합계") as 총종사자수,
            ROUND(AVG("STATS_기업종사자수_평균")::numeric, 2) as 평균종사자수
        FROM sbr_quarter_summary
        GROUP BY "CRTR_YR", "QU_SE_CD"
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("4. 시도별 통계")
    print("=" * 100)

    query = """
        SELECT
            "CTPV_NM" as 시도명,
            COUNT(*) as 시군구수,
            SUM("ORG_합계") as 총사업체수,
            SUM("ORG_개인사업체") as 개인사업체,
            SUM("ORG_회사법인") as 회사법인,
            SUM("STATS_기업종사자수_합계") as 총종사자수
        FROM sbr_quarter_summary
        GROUP BY "CTPV_NM"
        ORDER BY SUM("ORG_합계") DESC
        LIMIT 10
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("5. 상위 10개 시군구 (사업체수 기준)")
    print("=" * 100)

    query = """
        SELECT
            "CTPV_NM" || ' ' || "SGG_NM" as 지역,
            "ADCLSF_CTPV_CD" as 시도코드,
            "ADCLSF_SGG_CD" as 시군구코드,
            "ORG_합계" as 총사업체수,
            "STATS_기업종사자수_합계" as 총종사자수,
            "STATS_기업매출금액_합계" as 총매출액_백만원
        FROM sbr_quarter_summary
        WHERE "ORG_합계" IS NOT NULL
        ORDER BY "ORG_합계" DESC
        LIMIT 10
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("6. 산업분류별 통계 (전국)")
    print("=" * 100)

    query = """
        SELECT
            SUM("IND_제조업") as 제조업,
            SUM("IND_건설업") as 건설업,
            SUM("IND_도매및소매업") as 도소매업,
            SUM("IND_숙박및음식점업") as 숙박음식점,
            SUM("IND_부동산업") as 부동산업
        FROM sbr_quarter_summary
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("7. 성별 통계 (전국)")
    print("=" * 100)

    query = """
        SELECT
            SUM("GENDER_남자") as 남성대표,
            SUM("GENDER_여자") as 여성대표,
            SUM("GENDER_(공백)") as 미상,
            ROUND(SUM("GENDER_여자")::numeric / NULLIF(SUM("GENDER_합계")::numeric, 0) * 100, 2) as 여성비율
        FROM sbr_quarter_summary
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("8. 영업상태 통계 (전국)")
    print("=" * 100)

    query = """
        SELECT
            SUM("STATUS_영업중") as 영업중,
            SUM("STATUS_폐업") as 폐업,
            ROUND(SUM("STATUS_폐업")::numeric / NULLIF(SUM("STATUS_합계")::numeric, 0) * 100, 2) as 폐업률
        FROM sbr_quarter_summary
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("9. 샘플 데이터 (3건)")
    print("=" * 100)

    query = """
        SELECT
            "CRTR_YR", "QU_SE_CD", "CTPV_NM", "SGG_NM",
            "ADCLSF_CTPV_CD", "ADCLSF_SGG_CD",
            "ORG_합계", "STATS_기업종사자수_합계"
        FROM sbr_quarter_summary
        ORDER BY "ORG_합계" DESC
        LIMIT 3
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    print("\n" + "=" * 100)
    print("10. 코드 매핑 확인 (NULL 체크)")
    print("=" * 100)

    query = """
        SELECT
            COUNT(*) as 총건수,
            COUNT("ADCLSF_CTPV_CD") as 시도코드_있음,
            COUNT("ADCLSF_SGG_CD") as 시군구코드_있음,
            COUNT(*) - COUNT("ADCLSF_CTPV_CD") as 시도코드_없음,
            COUNT(*) - COUNT("ADCLSF_SGG_CD") as 시군구코드_없음
        FROM sbr_quarter_summary
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

    conn.close()

if __name__ == '__main__':
    check_data()
