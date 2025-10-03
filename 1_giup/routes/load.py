# -*- coding: utf-8 -*-
"""
집계표 데이터를 PostgreSQL에 업로드하는 스크립트
같은 년월 데이터가 있으면 삭제 후 추가
"""

import sys
import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# 프로젝트 루트를 sys.path에 추가 (routes 폴더 기준)
project_root = Path(__file__).parent.parent.parent
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

    print("\n" + "=" * 60)
    print("[결과 요약]")
    print("=" * 60)
    print(f"기준년월: {yearmonth}")
    print(f"총 데이터 수: {total_count}건")
    print("\n[시도별 통계]")
    for row in sido_stats:
        print(f"  - {row['시도']}: {row['count']}건")
    print("=" * 60)


def render():
    """
    동적 라우트 시스템에서 호출되는 메인 함수 - 데이터 업로드 실행 후 결과 HTML 반환
    """
    from flask import request

    # POST 요청이면 실행, 아니면 안내 페이지
    if request and request.method == 'POST':
        return execute_and_show_result()
    else:
        return show_upload_page()


def show_upload_page():
    """업로드 페이지 HTML 반환"""
    html = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PostgreSQL 데이터 업로드</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f5f5f5; }
            .container { max-width: 900px; margin-top: 50px; }
            .card { box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .btn-upload { background-color: #1243A6; border-color: #1243A6; }
            .btn-upload:hover { background-color: #0d3280; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h3 class="mb-0">📊 집계표 데이터 PostgreSQL 업로드</h3>
                </div>
                <div class="card-body">
                    <p class="text-muted">집계표_202312.xlsx 파일을 PostgreSQL 데이터베이스에 업로드합니다.</p>
                    <form method="POST" action="">
                        <button type="submit" class="btn btn-primary btn-upload btn-lg w-100">데이터 업로드 시작</button>
                    </form>
                    <p class="text-warning mt-3">⚠️ Cloudtype에 배포 후 사용하세요 (로컬 환경에서는 타임아웃 발생 가능)</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def execute_and_show_result():
    """데이터 업로드 실행 후 결과 HTML 반환"""
    logs = []
    success = False
    message = ""
    yearmonth = ""
    inserted_count = 0
    total_count = 0

    try:
        # Excel 파일 경로
        excel_file = Path(__file__).parent.parent / "data" / "집계표_202312.xlsx"

        if not excel_file.exists():
            message = f'Excel 파일을 찾을 수 없습니다: {excel_file}'
        else:
            # PostgreSQL 연결
            logs.append("PostgreSQL 연결 중...")
            conn = get_postgres_connection()
            logs.append("PostgreSQL 연결 성공")

            # 테이블 생성
            logs.append("테이블 생성 중...")
            create_table(conn)
            logs.append("테이블 생성 완료")

            # Excel 데이터 로드
            logs.append("Excel 파일 로드 중...")
            df, yearmonth = load_excel_data(excel_file)
            logs.append(f"Excel 파일 로드 완료: {len(df)}건")

            # 기존 데이터 삭제
            logs.append("기존 데이터 확인 중...")
            deleted_count = delete_existing_data(conn, yearmonth)
            if deleted_count > 0:
                logs.append(f"기존 데이터 삭제: {deleted_count}건")

            # 데이터 삽입
            logs.append("데이터 삽입 중...")
            inserted_count = insert_data(conn, df, yearmonth)
            logs.append(f"데이터 삽입 완료: {inserted_count}건")

            # 통계 조회
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as total FROM giup_statistics WHERE 기준년월 = %s",
                (yearmonth,)
            )
            total_count = cursor.fetchone()['total']
            cursor.close()
            conn.close()

            success = True
            message = "데이터 업로드 완료"
            logs.append("모든 작업 완료!")

    except Exception as e:
        message = str(e)
        logs.append(f"오류 발생: {str(e)}")

    # 결과 HTML 생성
    logs_html = "<br>".join(logs)
    result_class = "success" if success else "danger"
    result_icon = "✅" if success else "❌"

    html = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>업로드 결과</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f5f5f5; }}
            .container {{ max-width: 900px; margin-top: 50px; }}
            .card {{ box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .log-container {{ background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 15px; max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h3 class="mb-0">📊 업로드 결과</h3>
                </div>
                <div class="card-body">
                    <div class="alert alert-{result_class}">
                        <h5>{result_icon} {message}</h5>
                        {"<p class='mb-0'>기준년월: " + yearmonth + " | 삽입: " + str(inserted_count) + "건 | 총: " + str(total_count) + "건</p>" if success else ""}
                    </div>

                    <div class="log-container">
                        <h5>실행 로그:</h5>
                        {logs_html}
                    </div>

                    <a href="" class="btn btn-primary mt-3">다시 업로드</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def main():
    """
    커맨드라인 실행 함수
    """
    sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 60)
    print("집계표 데이터 PostgreSQL 업로드")
    print("=" * 60)

    # Excel 파일 경로 (routes 폴더 기준 -> 상위 폴더의 data)
    excel_file = Path(__file__).parent.parent / "data" / "집계표_202312.xlsx"

    if not excel_file.exists():
        print(f"[ERROR] Excel 파일을 찾을 수 없습니다: {excel_file}")
        return

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
        df, yearmonth = load_excel_data(excel_file)

        # 기존 데이터 삭제
        print("\n[INFO] 기존 데이터 확인 중...")
        deleted_count = delete_existing_data(conn, yearmonth)

        # 데이터 삽입
        print("\n[INFO] 데이터 삽입 중...")
        inserted_count = insert_data(conn, df, yearmonth)

        # 결과 통계
        get_statistics(conn, yearmonth)

        # 연결 종료
        conn.close()
        print("\n[OK] 모든 작업 완료!")

    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
