# -*- coding: utf-8 -*-
"""데이터베이스 테이블 확인"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from module.db import get_db_connection

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = get_db_connection()

# 인구/가구 관련 테이블 조회
query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE '%fact_%' OR table_name LIKE '%dim_%' OR table_name LIKE '%pop%' OR table_name LIKE '%household%'
    ORDER BY table_name
"""
df = pd.read_sql(query, conn)
print("인구/가구 관련 테이블:")
print(df.to_string(index=False))

# dim_admin_area 샘플 데이터
print("\n\ndim_admin_area 샘플:")
df2 = pd.read_sql("SELECT * FROM dim_admin_area LIMIT 5", conn)
print(df2.to_string(index=False))

conn.close()
