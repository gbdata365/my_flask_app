# -*- coding: utf-8 -*-
"""
집계표 데이터를 PostgreSQL에 업로드하는 스크립트 (파일 선택 기능)
같은 년월 데이터가 있으면 삭제 후 추가
"""

import sys
import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 환경변수 로드
load_dotenv(project_root / '.env')

from module.db_config import get_postgres_connection


def create_table(conn):
    """
    집계표 테이블 생성
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS giup_statistics (
        id SERIAL PRIMARY KEY,
        기준년월 VARCHAR(10) NOT NULL,
        시도 VARCHAR(50),
        시군구 VARCHAR(50),
        기업체수 INTEGER,
        임시및일용근로자수 INTEGER,
        상용근로자수 INTEGER,
        매출액 NUMERIC(20, 2),
        근로자수 INTEGER,
        총종사자수 INTEGER,
        평균종사자수 NUMERIC(15, 2),
        등록일자수 INTEGER,
        개업일자수 INTEGER,
        폐업일자수 INTEGER,
        기업_1 INTEGER,
        기업_2 INTEGER,
        기업_3 INTEGER,
        기업_4 INTEGER,
        기업_5 INTEGER,
        법인구분코드합계 INTEGER,
        폐업_1 INTEGER,
        폐업_2 INTEGER,
        폐업_3 INTEGER,
        폐업_4 INTEGER,
        폐업_99 INTEGER,
        산업_A INTEGER,
        산업_B INTEGER,
        산업_C INTEGER,
        산업_D INTEGER,
        산업_E INTEGER,
        산업_F INTEGER,
        산업_G INTEGER,
        산업_H INTEGER,
        산업_I INTEGER,
        산업_J INTEGER,
        산업_K INTEGER,
        산업_L INTEGER,
        산업_M INTEGER,
        산업_N INTEGER,
        산업_O INTEGER,
        산업_P INTEGER,
        산업_Q INTEGER,
        산업_R INTEGER,
        산업_S INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_giup_기준년월 ON giup_statistics(기준년월);
    CREATE INDEX IF NOT EXISTS idx_giup_시도 ON giup_statistics(시도);
    """

    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    conn.commit()
    cursor.close()
    print("[OK] 테이블 생성 완료 (또는 이미 존재)")


def find_excel_files(data_dir):
    """
    data 폴더에서 '집계표'로 시작하는 Excel 파일 찾기

    Args:
        data_dir: data 폴더 경로

    Returns:
        list: Excel 파일 경로 리스트
    """
    excel_files = sorted(data_dir.glob("집계표*.xlsx"))
    return excel_files


def display_file_list(files):
    """
    파일 목록을 탐색기처럼 표시

    Args:
        files: 파일 경로 리스트

    Returns:
        None
    """
    print("\n" + "=" * 70)
    print(" " * 20 + "[집계표 파일 목록]")
    print("=" * 70)
    print(f"{'번호':<6} {'파일명':<30} {'크기 (KB)':<12} {'수정일시'}")
    print("-" * 70)

    for idx, file_path in enumerate(files, 1):
        file_stat = file_path.stat()
        file_size = file_stat.st_size / 1024  # KB로 변환
        modified_time = pd.Timestamp.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M')

        print(f"{idx:<6} {file_path.name:<30} {file_size:>10.1f} KB  {modified_time}")

    print("=" * 70)


def select_file(files):
    """
    사용자에게 파일 선택 받기

    Args:
        files: 파일 경로 리스트

    Returns:
        Path: 선택된 파일 경로, 취소 시 None
    """
    while True:
        try:
            choice = input("\n업로드할 파일 번호를 선택하세요 (0: 취소): ").strip()

            if choice == '0':
                return None

            file_num = int(choice)
            if 1 <= file_num <= len(files):
                return files[file_num - 1]
            else:
                print(f"[ERROR] 1~{len(files)} 사이의 번호를 입력하세요.")
        except ValueError:
            print("[ERROR] 숫자를 입력하세요.")
        except KeyboardInterrupt:
            print("\n[INFO] 사용자에 의해 취소되었습니다.")
            return None


def load_excel_data(file_path):
    """
    Excel 파일에서 데이터 로드

    Args:
        file_path: Excel 파일 경로

    Returns:
        tuple: (pandas.DataFrame, str) - 데이터프레임과 기준년월
    """
    df = pd.read_excel(file_path)

    # NaN 값을 None으로 변환 (PostgreSQL NULL로 저장)
    df = df.where(pd.notnull(df), None)

    # 기준년월 추출 (첫 번째 행의 기준년월_시도 컬럼에서)
    yearmonth = str(df.iloc[0]['기준년월_시도'])[:6]

    # 컬럼명 정리 (괄호를 언더스코어로 변경)
    df.columns = [col.replace('(', '_').replace(')', '') for col in df.columns]

    print(f"[OK] Excel 파일 로드 완료: {len(df)}건")
    print(f"[INFO] 기준년월: {yearmonth}")
    return df, yearmonth


def check_existing_data(conn, yearmonth):
    """
    같은 년월의 데이터가 존재하는지 확인

    Args:
        conn: PostgreSQL 연결 객체
        yearmonth: 확인할 기준년월

    Returns:
        int: 기존 데이터 건수
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as count FROM giup_statistics WHERE 기준년월 = %s",
        (yearmonth,)
    )
    result = cursor.fetchone()
    cursor.close()
    return result['count']


def delete_existing_data(conn, yearmonth):
    """
    같은 년월의 기존 데이터 삭제

    Args:
        conn: PostgreSQL 연결 객체
        yearmonth: 삭제할 기준년월

    Returns:
        int: 삭제된 행 수
    """
    cursor = conn.cursor()
    delete_sql = "DELETE FROM giup_statistics WHERE 기준년월 = %s"
    cursor.execute(delete_sql, (yearmonth,))
    deleted_count = cursor.rowcount
    conn.commit()
    cursor.close()

    if deleted_count > 0:
        print(f"[INFO] 기존 데이터 삭제: {deleted_count}건 (기준년월: {yearmonth})")
    else:
        print(f"[INFO] 기존 데이터 없음 (기준년월: {yearmonth})")

    return deleted_count


def insert_data(conn, df, yearmonth):
    """
    데이터를 PostgreSQL에 삽입

    Args:
        conn: PostgreSQL 연결 객체
        df: 삽입할 데이터프레임
        yearmonth: 기준년월
    """
    cursor = conn.cursor()

    insert_sql = """
    INSERT INTO giup_statistics (
        기준년월, 시도, 시군구,
        기업체수, 임시및일용근로자수, 상용근로자수, 매출액, 근로자수,
        총종사자수, 평균종사자수, 등록일자수, 개업일자수, 폐업일자수,
        기업_1, 기업_2, 기업_3, 기업_4, 기업_5, 법인구분코드합계,
        폐업_1, 폐업_2, 폐업_3, 폐업_4, 폐업_99,
        산업_A, 산업_B, 산업_C, 산업_D, 산업_E, 산업_F,
        산업_G, 산업_H, 산업_I, 산업_J, 산업_K, 산업_L,
        산업_M, 산업_N, 산업_O, 산업_P, 산업_Q, 산업_R, 산업_S
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s
    )
    """

    inserted_count = 0
    error_count = 0

    for idx, row in df.iterrows():
        try:
            cursor.execute(insert_sql, (
                yearmonth, row['시도'], row['시군구'],
                row['기업체수'], row['임시및일용근로자수'], row['상용근로자수'],
                row['매출액'], row['근로자수'], row['총종사자수'], row['평균종사자수'],
                row['등록일자수'], row['개업일자수'], row['폐업일자수'],
                row['기업_1'], row['기업_2'], row['기업_3'], row['기업_4'], row['기업_5'],
                row['법인구분코드합계'],
                row['폐업_1'], row['폐업_2'], row['폐업_3'], row['폐업_4'], row['폐업_99'],
                row['산업_A'], row['산업_B'], row['산업_C'], row['산업_D'], row['산업_E'],
                row['산업_F'], row['산업_G'], row['산업_H'], row['산업_I'], row['산업_J'],
                row['산업_K'], row['산업_L'], row['산업_M'], row['산업_N'], row['산업_O'],
                row['산업_P'], row['산업_Q'], row['산업_R'], row['산업_S']
            ))
            inserted_count += 1
        except Exception as e:
            error_count += 1
            print(f"[WARNING] Row {idx} 삽입 실패: {e}")

    conn.commit()
    cursor.close()

    print(f"[OK] 데이터 삽입 완료: {inserted_count}건 성공, {error_count}건 실패")
    return inserted_count


def get_statistics(conn, yearmonth):
    """
    업로드된 데이터 통계 조회

    Args:
        conn: PostgreSQL 연결 객체
        yearmonth: 기준년월
    """
    cursor = conn.cursor()

    # 총 데이터 수
    cursor.execute(
        "SELECT COUNT(*) as total FROM giup_statistics WHERE 기준년월 = %s",
        (yearmonth,)
    )
    total_count = cursor.fetchone()['total']

    # 시도별 데이터 수
    cursor.execute(
        """
        SELECT 시도, COUNT(*) as count
        FROM giup_statistics
        WHERE 기준년월 = %s
        GROUP BY 시도
        ORDER BY 시도
        """,
        (yearmonth,)
    )
    sido_stats = cursor.fetchall()

    cursor.close()

    print("\n" + "=" * 70)
    print(" " * 25 + "[결과 요약]")
    print("=" * 70)
    print(f"기준년월: {yearmonth}")
    print(f"총 데이터 수: {total_count}건")
    print("\n[시도별 통계]")

    # 2열로 표시
    for i in range(0, len(sido_stats), 2):
        left = sido_stats[i]
        left_str = f"  {left['시도']:<15}: {left['count']:>4}건"

        if i + 1 < len(sido_stats):
            right = sido_stats[i + 1]
            right_str = f"  {right['시도']:<15}: {right['count']:>4}건"
            print(f"{left_str}    {right_str}")
        else:
            print(left_str)

    print("=" * 70)


def get_all_yearmonth_statistics(conn):
    """
    DB에 저장된 모든 년월 통계 조회

    Args:
        conn: PostgreSQL 연결 객체
    """
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 기준년월, COUNT(*) as count
        FROM giup_statistics
        GROUP BY 기준년월
        ORDER BY 기준년월 DESC
        """
    )
    results = cursor.fetchall()
    cursor.close()

    if results:
        print("\n" + "=" * 70)
        print(" " * 20 + "[DB에 저장된 전체 데이터]")
        print("=" * 70)
        for row in results:
            year = row['기준년월'][:4]
            month = row['기준년월'][4:6]
            print(f"  {year}년 {month}월: {row['count']:>4}건")
        print("=" * 70)


def main():
    """
    메인 실행 함수
    """
    sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 70)
    print(" " * 15 + "집계표 데이터 PostgreSQL 업로드")
    print("=" * 70)

    # data 폴더 확인
    data_dir = Path(__file__).parent / "data"
    if not data_dir.exists():
        print(f"[ERROR] data 폴더를 찾을 수 없습니다: {data_dir}")
        return

    # Excel 파일 찾기
    excel_files = find_excel_files(data_dir)

    if not excel_files:
        print("[ERROR] '집계표'로 시작하는 Excel 파일을 찾을 수 없습니다.")
        return

    # 파일 목록 표시
    display_file_list(excel_files)

    # 파일 선택
    selected_file = select_file(excel_files)

    if selected_file is None:
        print("\n[INFO] 업로드가 취소되었습니다.")
        return

    print(f"\n[INFO] 선택된 파일: {selected_file.name}")

    try:
        # PostgreSQL 연결
        print("\n[INFO] PostgreSQL 연결 중...")
        conn = get_postgres_connection()
        print("[OK] PostgreSQL 연결 성공")

        # 테이블 생성
        print("\n[INFO] 테이블 생성 중...")
        create_table(conn)

        # Excel 데이터 로드
        print("\n[INFO] Excel 파일 로드 중...")
        df, yearmonth = load_excel_data(selected_file)

        # 기존 데이터 확인
        existing_count = check_existing_data(conn, yearmonth)

        if existing_count > 0:
            print(f"\n[WARNING] 동일한 년월({yearmonth})의 데이터가 {existing_count}건 존재합니다.")
            confirm = input("[질문] 기존 데이터를 삭제하고 새로 업로드하시겠습니까? (y/n): ").strip().lower()

            if confirm != 'y':
                print("\n[INFO] 업로드가 취소되었습니다.")
                conn.close()
                return

            # 기존 데이터 삭제
            print("\n[INFO] 기존 데이터 삭제 중...")
            delete_existing_data(conn, yearmonth)
        else:
            print(f"\n[INFO] 새로운 데이터 추가 (기준년월: {yearmonth})")

        # 데이터 삽입
        print("\n[INFO] 데이터 삽입 중...")
        inserted_count = insert_data(conn, df, yearmonth)

        # 결과 통계
        get_statistics(conn, yearmonth)

        # 전체 DB 통계
        get_all_yearmonth_statistics(conn)

        # 연결 종료
        conn.close()
        print("\n[OK] 모든 작업 완료!")

    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
