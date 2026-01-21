# -*- coding: utf-8 -*-
"""인구 테이블 컬럼 확인"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from module.db import get_db_connection

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = get_db_connection()

# fact_population_basic 컬럼 확인
query = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'fact_population_basic'
    ORDER BY ordinal_position
"""
df = pd.read_sql(query, conn)
print("fact_population_basic 컬럼:")
print(df.to_string(index=False))

# 샘플 데이터
print("\n\n샘플 데이터:")
df2 = pd.read_sql("SELECT * FROM fact_population_basic LIMIT 3", conn)
print(df2.to_string(index=False))

conn.close()
