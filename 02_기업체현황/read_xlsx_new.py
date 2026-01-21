# -*- coding: utf-8 -*-
"""
기업체현황 엑셀 데이터 처리 스크립트 (표준화 버전)
========================================================

레이아웃 파일의 표준화 컬럼명을 사용하여 데이터를 저장합니다.
- 영문 컬럼명: 레이아웃 파일의 표준화 후 영문명
- 한글 별칭: 레이아웃 파일의 표준화된 한글명
- 시도코드, 시군구코드: gb_address 테이블에서 조회

사용법:
    python read_xlsx_new.py --file data/(수정)집계표_24년1분기.xlsx --init --insert
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Optional, Dict, Tuple

import pandas as pd
import numpy as np
from loguru import logger

# 상위 디렉토리의 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from module.db import get_db_connection

# =============================================================================
# 설정
# =============================================================================

TABLE_NAME = 'sbr_quarter_summary'  # 분기 기업통계등록부 집계표

# 엑셀 시트 목록
TARGET_SHEETS = [
    '조직형태별',
    '대표자성별별',
    '폐업여부별',
    '산업분류별',
    '대표사업체별',
    '수치형통계',
]

# =============================================================================
# 유틸리티 함수
# =============================================================================

def get_address_codes(sido_nm: str, sigungu_nm: str) -> Tuple[Optional[str], Optional[str]]:
    """
    시도명, 시군구명으로 gb_address 테이블에서 코드 조회

    Args:
        sido_nm: 시도명 (예: 강원특별자치도)
        sigungu_nm: 시군구명 (예: 강릉시)

    Returns:
        (시도코드, 시군구코드) 튜플
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT DISTINCT
                SUBSTRING(CAST("행정구역코드" AS TEXT), 1, 2) as sido_cd,
                SUBSTRING(CAST("행정구역코드" AS TEXT), 1, 5) as sigungu_cd
            FROM gb_address
            WHERE "시도명" = %s AND "시군구명" = %s
            LIMIT 1
        """
        cursor.execute(query, (sido_nm, sigungu_nm))
        result = cursor.fetchone()

        if result:
            return result[0], result[1]
        else:
            logger.warning(f"주소 코드 없음: {sido_nm} {sigungu_nm}")
            return None, None

    except Exception as e:
        logger.error(f"주소 코드 조회 실패: {e}")
        return None, None
    finally:
        cursor.close()
        conn.close()


def parse_period(period_str: str) -> Tuple[str, str, str]:
    """기준시기 문자열을 파싱하여 기준년도, 분기코드 반환"""
    period_str = str(period_str).strip()

    # 분기 패턴: 2024년 1분기
    quarter_match = re.match(r'(\d{4})년\s*(\d)분기', period_str)
    if quarter_match:
        year = quarter_match.group(1)
        quarter = quarter_match.group(2)
        return year, quarter, '분기'

    logger.warning(f"기준시기 파싱 실패: {period_str}")
    return '', '', ''


def convert_star_to_null(df: pd.DataFrame) -> pd.DataFrame:
    """'*' 값을 NULL로 변환"""
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].replace('*', np.nan)
            # 숫자로 변환 시도
            try:
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    numeric_vals = pd.to_numeric(non_null, errors='coerce')
                    if numeric_vals.notna().all():
                        df[col] = pd.to_numeric(df[col], errors='coerce')
            except:
                pass
    return df


# =============================================================================
# 엑셀 처리 함수
# =============================================================================

def read_sheet(file_path: str, sheet_name: str, add_prefix: bool = True) -> pd.DataFrame:
    """개별 시트를 읽어서 정리된 DataFrame 반환"""
    logger.info(f"시트 읽기: {sheet_name}")

    df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)

    # 첫 번째 컬럼이 NaN인 경우 제거
    if df.columns[0] is None or pd.isna(df.columns[0]):
        df = df.iloc[:, 1:]

    # unnamed 컬럼 제거
    df = df[[c for c in df.columns if 'unnamed' not in str(c).lower()]]

    # NaN 행 제거
    if '시군구명' in df.columns:
        df = df.dropna(subset=['시군구명'])

    # 기준시기, 시도명 ffill
    if '기준시기' in df.columns:
        df['기준시기'] = df['기준시기'].ffill()
    if '시도명' in df.columns:
        df['시도명'] = df['시도명'].ffill()

    # '*' 값을 NULL로 변환
    df = convert_star_to_null(df)

    # 시트별 접두사 추가 (공통 컬럼 제외)
    if add_prefix:
        prefix_map = {
            '조직형태별': 'ORG_',
            '대표자성별별': 'GENDER_',
            '폐업여부별': 'STATUS_',
            '산업분류별': 'IND_',
            '대표사업체별': 'MAINBIZ_',
            '수치형통계': 'STATS_',
        }

        common_cols = ['기준시기', '시도명', '시군구명']
        prefix = prefix_map.get(sheet_name, '')

        if prefix:
            rename_dict = {}
            for col in df.columns:
                if col not in common_cols:
                    rename_dict[col] = f"{prefix}{col}"
            df = df.rename(columns=rename_dict)

    logger.info(f"  - {len(df)} 행, {len(df.columns)} 컬럼")
    return df


def merge_all_sheets(file_path: str) -> pd.DataFrame:
    """모든 시트를 하나의 DataFrame으로 병합"""
    logger.info(f"엑셀 파일 처리 시작: {file_path}")

    xl = pd.ExcelFile(file_path)
    available_sheets = xl.sheet_names
    merged_df = None

    for sheet_name in TARGET_SHEETS:
        if sheet_name not in available_sheets:
            logger.warning(f"시트 없음: {sheet_name}")
            continue

        df = read_sheet(file_path, sheet_name)

        if merged_df is None:
            merged_df = df
        else:
            merge_cols = ['기준시기', '시도명', '시군구명']
            merge_cols = [c for c in merge_cols if c in merged_df.columns and c in df.columns]
            data_cols = [c for c in df.columns if c not in merge_cols]

            merged_df = merged_df.merge(
                df[merge_cols + data_cols],
                on=merge_cols,
                how='outer'
            )

    if merged_df is None:
        raise ValueError("병합할 데이터가 없습니다.")

    # 기준년도, 분기구분코드 추가
    logger.info("기준년도, 분기구분코드 추가")

    merged_df['CRTR_YR'] = ''
    merged_df['QU_SE_CD'] = ''
    merged_df['ADCLSF_CTPV_CD'] = ''
    merged_df['ADCLSF_SGG_CD'] = ''

    for idx, row in merged_df.iterrows():
        # 기준시기 파싱
        year, quarter, period_type = parse_period(row['기준시기'])
        merged_df.at[idx, 'CRTR_YR'] = year
        merged_df.at[idx, 'QU_SE_CD'] = quarter

        # 주소 코드 조회
        sido_cd, sigungu_cd = get_address_codes(row['시도명'], row['시군구명'])
        merged_df.at[idx, 'ADCLSF_CTPV_CD'] = sido_cd
        merged_df.at[idx, 'ADCLSF_SGG_CD'] = sigungu_cd

    # 컬럼명 변경 (한글 → 영문)
    merged_df = merged_df.rename(columns={
        '시도명': 'CTPV_NM',
        '시군구명': 'SGG_NM'
    })

    # 컬럼 순서 정리
    priority_cols = ['CRTR_YR', 'QU_SE_CD', 'ADCLSF_CTPV_CD', 'ADCLSF_SGG_CD', 'CTPV_NM', 'SGG_NM']
    other_cols = [c for c in merged_df.columns if c not in priority_cols and c != '기준시기']
    merged_df = merged_df[priority_cols + other_cols]

    logger.info(f"병합 완료: {len(merged_df)} 행, {len(merged_df.columns)} 컬럼")
    return merged_df


# =============================================================================
# 데이터베이스 함수
# =============================================================================

def create_table(df: pd.DataFrame):
    """테이블 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME} CASCADE")

        col_definitions = []
        comments = []

        # 컬럼 정의 및 COMMENT
        col_map = {
            'CRTR_YR': ('CHAR(4)', '기준연도'),
            'QU_SE_CD': ('VARCHAR(1)', '분기구분코드'),
            'ADCLSF_CTPV_CD': ('VARCHAR(2)', '행정구역분류시도코드'),
            'ADCLSF_SGG_CD': ('VARCHAR(5)', '행정구역분류시군구코드'),
            'CTPV_NM': ('VARCHAR(40)', '시도명'),
            'SGG_NM': ('VARCHAR(100)', '시군구명'),
        }

        for col in df.columns:
            if col in col_map:
                col_type, comment = col_map[col]
                col_definitions.append(f'"{col}" {col_type}')
                comments.append(f'COMMENT ON COLUMN {TABLE_NAME}."{col}" IS \'{comment}\'')
            else:
                # 나머지 컬럼은 숫자형으로 가정
                dtype = df[col].dtype
                if dtype == 'int64':
                    col_type = 'BIGINT'
                elif dtype == 'float64':
                    col_type = 'NUMERIC(20, 2)'
                else:
                    col_type = 'VARCHAR(255)'

                col_definitions.append(f'"{col}" {col_type}')
                comments.append(f'COMMENT ON COLUMN {TABLE_NAME}."{col}" IS \'{col}\'')

        create_sql = f"""
        CREATE TABLE {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            {', '.join(col_definitions)},
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        cursor.execute(create_sql)

        # COMMENT 추가
        for comment_sql in comments:
            cursor.execute(comment_sql)

        # 인덱스 생성
        cursor.execute(f'CREATE INDEX idx_{TABLE_NAME}_year ON {TABLE_NAME}("CRTR_YR")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_NAME}_quarter ON {TABLE_NAME}("QU_SE_CD")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_NAME}_sido ON {TABLE_NAME}("ADCLSF_CTPV_CD")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_NAME}_sigungu ON {TABLE_NAME}("ADCLSF_SGG_CD")')

        conn.commit()
        logger.info(f"테이블 생성 완료: {TABLE_NAME}")

    except Exception as e:
        conn.rollback()
        logger.error(f"테이블 생성 실패: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def insert_data(df: pd.DataFrame):
    """데이터 삽입"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        columns = df.columns.tolist()
        col_names = ', '.join([f'"{c}"' for c in columns])
        placeholders = ', '.join(['%s'] * len(columns))

        insert_sql = f'INSERT INTO {TABLE_NAME} ({col_names}) VALUES ({placeholders})'

        inserted = 0
        for idx, row in df.iterrows():
            values = []
            for col in columns:
                val = row[col]
                if pd.isna(val):
                    values.append(None)
                else:
                    values.append(val)

            cursor.execute(insert_sql, values)
            inserted += 1

            if inserted % 100 == 0:
                logger.info(f"  {inserted:,} 행 삽입...")

        conn.commit()
        logger.info(f"데이터 삽입 완료: {inserted:,} 행")

    except Exception as e:
        conn.rollback()
        logger.error(f"데이터 삽입 실패: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# 메인 함수
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='기업체현황 엑셀 데이터 처리 (표준화 버전)')
    parser.add_argument('--file', '-f', required=True, help='엑셀 파일 경로')
    parser.add_argument('--init', action='store_true', help='테이블 초기화')
    parser.add_argument('--insert', action='store_true', help='데이터 삽입')
    parser.add_argument('--output', '-o', help='CSV 출력 파일')

    args = parser.parse_args()
    os.chdir(Path(__file__).parent)

    if not Path(args.file).exists():
        logger.error(f"파일 없음: {args.file}")
        return

    df = merge_all_sheets(args.file)

    print(f"\n병합된 데이터: {len(df)} 행, {len(df.columns)} 컬럼")
    print(f"컬럼: {df.columns.tolist()}")
    print(f"\n샘플 데이터:")
    print(df.head(3).to_string())

    if args.output:
        df.to_csv(args.output, index=False, encoding='utf-8-sig')
        logger.info(f"CSV 저장: {args.output}")

    if args.init:
        create_table(df)

    if args.insert:
        insert_data(df)


if __name__ == '__main__':
    main()
