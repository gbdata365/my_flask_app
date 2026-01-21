# -*- coding: utf-8 -*-
"""
전체 데이터 확인
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from module.db import get_db_connection

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = get_db_connection()

print("=" * 80)
print("분기별 데이터 확인")
print("=" * 80)

query = """
    SELECT
        "CRTR_YR" as 연도,
        "QU_SE_CD" as 분기,
        COUNT(*) as 지역수,
        SUM("ORG_합계") as 총사업체수,
        SUM("STATS_기업종사자수_합계") as 총종사자수
    FROM sbr_quarter_summary
    GROUP BY "CRTR_YR", "QU_SE_CD"
    ORDER BY "CRTR_YR", "QU_SE_CD"
"""
df = pd.read_sql(query, conn)
print(df.to_string(index=False))

print(f"\n총 데이터 건수: {df['지역수'].sum()}")

conn.close()
