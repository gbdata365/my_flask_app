# -*- coding: utf-8 -*-
"""
gb_address 테이블 구조 및 데이터 확인
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

def check_gb_address():
    """gb_address 테이블 확인"""
    conn = get_db_connection()

    # 테이블 구조 확인
    print("\n" + "=" * 80)
    print("gb_address 테이블 구조")
    print("=" * 80)
    query = """
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'gb_address'
        ORDER BY ordinal_position
    """
    df_schema = pd.read_sql(query, conn)
    print(df_schema.to_string(index=False))

    # 데이터 샘플 확인
    print("\n" + "=" * 80)
    print("gb_address 샘플 데이터 (시도별)")
    print("=" * 80)
    query = "SELECT * FROM gb_address LIMIT 20"
    df_sample = pd.read_sql(query, conn)
    print(df_sample.to_string(index=False))

    # 시도 목록
    print("\n" + "=" * 80)
    print("시도 목록")
    print("=" * 80)
    query = """
        SELECT DISTINCT "시도명",
               SUBSTRING(CAST("행정구역코드" AS TEXT), 1, 2) as 시도코드
        FROM gb_address
        WHERE "시도명" IS NOT NULL
        ORDER BY 시도코드
    """
    df_sido = pd.read_sql(query, conn)
    print(df_sido.to_string(index=False))

    # 시군구 샘플
    print("\n" + "=" * 80)
    print("시군구 샘플 (강원특별자치도)")
    print("=" * 80)
    query = """
        SELECT "시도명", "시군구명",
               SUBSTRING(CAST("행정구역코드" AS TEXT), 1, 2) as 시도코드,
               SUBSTRING(CAST("행정구역코드" AS TEXT), 1, 5) as 시군구코드
        FROM gb_address
        WHERE "시도명" LIKE '%강원%'
        AND "시군구명" IS NOT NULL
        GROUP BY "시도명", "시군구명", "행정구역코드"
        ORDER BY 시군구코드
        LIMIT 20
    """
    df_sigungu = pd.read_sql(query, conn)
    print(df_sigungu.to_string(index=False))

    conn.close()

if __name__ == '__main__':
    check_gb_address()
