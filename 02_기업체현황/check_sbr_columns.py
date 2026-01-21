# -*- coding: utf-8 -*-
"""
SBR 테이블 구조 및 샘플 데이터 확인
산업별 컬럼, 매출액, 종사자수 등을 확인하기 위한 스크립트
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

# sbr_quarter_summary 컬럼 확인
print("=" * 80)
print("sbr_quarter_summary 테이블 컬럼 정보")
print("=" * 80)
query = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'sbr_quarter_summary'
    ORDER BY ordinal_position
"""
df = pd.read_sql(query, conn)
print(df.to_string(index=False))

# 샘플 데이터 1개만 확인
print("\n\n" + "=" * 80)
print("샘플 데이터 (1행)")
print("=" * 80)
df2 = pd.read_sql("SELECT * FROM sbr_quarter_summary LIMIT 1", conn)
# 전치하여 세로로 출력
for col in df2.columns:
    print(f"{col}: {df2[col].iloc[0]}")

# 산업 관련 컬럼 찾기 (INDUTY_ 로 시작하는 컬럼)
print("\n\n" + "=" * 80)
print("산업 관련 컬럼 (INDUTY_ 로 시작)")
print("=" * 80)
industry_cols = [col for col in df2.columns if col.startswith('INDUTY_')]
print(f"총 {len(industry_cols)}개 컬럼")
for col in industry_cols[:10]:  # 처음 10개만
    print(f"  - {col}")
if len(industry_cols) > 10:
    print(f"  ... 외 {len(industry_cols) - 10}개")

# 매출액, 종사자수 관련 컬럼 확인
print("\n\n" + "=" * 80)
print("매출액/종사자수 관련 컬럼")
print("=" * 80)
sales_employee_cols = [col for col in df2.columns if any(keyword in col.upper() for keyword in ['SALE', 'REVENUE', 'EMPLOYEE', 'WORKER', '매출', '종사'])]
for col in sales_employee_cols:
    print(f"  - {col}")

conn.close()
