# -*- coding: utf-8 -*-
"""
데이터베이스 주소 테이블 확인
"""

import sys
from pathlib import Path

# 상위 디렉토리의 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from module.db import get_db_connection

def check_address_table():
    """데이터베이스의 주소 관련 테이블 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 테이블 목록 조회
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE '%주소%' OR table_name LIKE '%address%' OR table_name LIKE '%addr%'
        OR table_name LIKE '%시도%' OR table_name LIKE '%시군구%' OR table_name LIKE '%행정%'
        ORDER BY table_name
    """)

    tables = cursor.fetchall()
    print("주소 관련 테이블:")
    print("=" * 80)
    for table in tables:
        print(f"  - {table[0]}")

    if not tables:
        print("  (없음)")
        print("\n모든 테이블 조회:")
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        all_tables = cursor.fetchall()
        for table in all_tables:
            print(f"  - {table[0]}")

    cursor.close()
    conn.close()

if __name__ == '__main__':
    check_address_table()
