# -*- coding: utf-8 -*-
"""
기업체현황 엑셀 데이터 처리 스크립트
====================================

여러 시트의 엑셀 데이터를 하나로 합쳐서 PostgreSQL에 저장합니다.
- 컬럼명은 영문으로 저장
- 표시할 때는 한글명 사용
- '*' 값(통계적 비밀보호)은 NULL로 처리

사용법:
    python read_xlsx.py --file data/(수정)집계표_24년1분기.xlsx
    python read_xlsx.py --file data/파일명.xlsx --init --insert
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import Optional, Tuple, Dict

import pandas as pd
import numpy as np
from loguru import logger

# 상위 디렉토리의 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from module.db import get_db_connection


# =============================================================================
# 컬럼 매핑 설정 (한글 → 영문)
# =============================================================================

# 기본 컬럼 매핑
BASE_COLUMN_MAP: Dict[str, str] = {
    '기준시기': 'period_str',
    '시도명': 'sido_nm',
    '시군구명': 'sigungu_nm',
}

# 조직형태별 컬럼
ORG_TYPE_MAP: Dict[str, str] = {
    '개인사업체': 'org_individual',
    '국가지방자치단체': 'org_government',
    '비법인단체': 'org_unincorporated',
    '회사법인': 'org_corporation',
    '회사이외법인': 'org_nonprofit_corp',
    '합계': 'org_total',
}

# 대표자성별별 컬럼
GENDER_MAP: Dict[str, str] = {
    '(공백)': 'gender_unknown',
    'blank': 'gender_unknown',
    '남자': 'gender_male',
    '여자': 'gender_female',
    '합계': 'gender_total',
}

# 폐업여부별 컬럼
STATUS_MAP: Dict[str, str] = {
    '영업중': 'status_active',
    '폐업': 'status_closed',
    '합계': 'status_total',
}

# 산업분류별 컬럼 (한국표준산업분류)
INDUSTRY_MAP: Dict[str, str] = {
    '(공백)': 'ind_unknown',
    'blank': 'ind_unknown',
    '농업,임업,어업': 'ind_agriculture',
    '농업_임업_어업': 'ind_agriculture',
    '광업': 'ind_mining',
    '제조업': 'ind_manufacturing',
    '전기가스공급업': 'ind_utilities',
    '수도하수폐기물': 'ind_water_waste',
    '건설업': 'ind_construction',
    '도매및소매업': 'ind_wholesale_retail',
    '운수및창고업': 'ind_transportation',
    '숙박및음식점업': 'ind_accommodation_food',
    '정보통신업': 'ind_ict',
    '금융및보험업': 'ind_finance',
    '부동산업': 'ind_real_estate',
    '전문과학기술서비스': 'ind_professional',
    '사업시설관리': 'ind_admin_support',
    '공공행정': 'ind_public_admin',
    '교육서비스업': 'ind_education',
    '보건사회복지': 'ind_health_welfare',
    '예술스포츠여가': 'ind_arts_sports',
    '협회및개인서비스': 'ind_other_services',
    '가구내고용활동': 'ind_household',
    '국제외국기관': 'ind_international',
    '합계': 'ind_total',
}

# 대표사업체별 컬럼
MAIN_BIZ_MAP: Dict[str, str] = {
    '(공백)': 'main_biz_unknown',
    'blank': 'main_biz_unknown',
    '합계': 'main_biz_total',
}

# 수치형통계 컬럼
STATS_MAP: Dict[str, str] = {
    '기업종사자수_건수': 'emp_count',
    '기업종사자수_합계': 'emp_total',
    '기업종사자수_평균': 'emp_avg',
    '기업종사자수_공백건수': 'emp_null_count',
    '기업매출금액_건수': 'revenue_count',
    '기업매출금액_합계': 'revenue_total',
    '기업매출금액_평균': 'revenue_avg',
    '기업매출금액_공백건수': 'revenue_null_count',
    '기업상용근로자수_건수': 'regular_emp_count',
    '기업상용근로자수_합계': 'regular_emp_total',
    '기업상용근로자수_평균': 'regular_emp_avg',
    '기업상용근로자수_공백건수': 'regular_emp_null_count',
    '기업임시일용근로자수_건수': 'temp_emp_count',
    '기업임시일용근로자수_합계': 'temp_emp_total',
    '기업임시일용근로자수_평균': 'temp_emp_avg',
    '기업임시일용근로자수_공백건수': 'temp_emp_null_count',
}

# 시트별 접두사
SHEET_PREFIX_MAP: Dict[str, str] = {
    '조직형태별': 'org',
    '대표자성별별': 'gender',
    '폐업여부별': 'status',
    '산업분류별': 'ind',
    '대표사업체별': 'main_biz',
    '수치형통계': 'stats',
}

# 영문 → 한글 역매핑 (표시용)
DISPLAY_NAME_MAP: Dict[str, str] = {
    # 기본 컬럼
    'base_ym': '기준년월',
    'year': '연도',
    'period_type': '구분',
    'period_str': '기준시기',
    'sido_nm': '시도명',
    'sigungu_nm': '시군구명',

    # 조직형태별
    'org_individual': '개인사업체',
    'org_government': '국가지방자치단체',
    'org_unincorporated': '비법인단체',
    'org_corporation': '회사법인',
    'org_nonprofit_corp': '회사이외법인',
    'org_total': '조직형태_합계',

    # 대표자성별별
    'gender_unknown': '성별미상',
    'gender_male': '남성대표',
    'gender_female': '여성대표',
    'gender_total': '성별_합계',

    # 폐업여부별
    'status_active': '영업중',
    'status_closed': '폐업',
    'status_total': '영업상태_합계',

    # 산업분류별
    'ind_unknown': '산업미분류',
    'ind_agriculture': '농림어업',
    'ind_mining': '광업',
    'ind_manufacturing': '제조업',
    'ind_utilities': '전기가스공급',
    'ind_water_waste': '수도하수폐기물',
    'ind_construction': '건설업',
    'ind_wholesale_retail': '도소매업',
    'ind_transportation': '운수창고업',
    'ind_accommodation_food': '숙박음식점',
    'ind_ict': '정보통신업',
    'ind_finance': '금융보험업',
    'ind_real_estate': '부동산업',
    'ind_professional': '전문과학기술',
    'ind_admin_support': '사업시설관리',
    'ind_public_admin': '공공행정',
    'ind_education': '교육서비스',
    'ind_health_welfare': '보건복지',
    'ind_arts_sports': '예술스포츠여가',
    'ind_other_services': '협회개인서비스',
    'ind_household': '가구내고용',
    'ind_international': '국제기관',
    'ind_total': '산업_합계',

    # 대표사업체별
    'main_biz_unknown': '대표사업체미상',
    'main_biz_total': '대표사업체_합계',

    # 수치형통계
    'emp_count': '종사자수_건수',
    'emp_total': '종사자수_합계',
    'emp_avg': '종사자수_평균',
    'emp_null_count': '종사자수_공백',
    'revenue_count': '매출금액_건수',
    'revenue_total': '매출금액_합계',
    'revenue_avg': '매출금액_평균',
    'revenue_null_count': '매출금액_공백',
    'regular_emp_count': '상용근로자_건수',
    'regular_emp_total': '상용근로자_합계',
    'regular_emp_avg': '상용근로자_평균',
    'regular_emp_null_count': '상용근로자_공백',
    'temp_emp_count': '임시일용_건수',
    'temp_emp_total': '임시일용_합계',
    'temp_emp_avg': '임시일용_평균',
    'temp_emp_null_count': '임시일용_공백',
}


# =============================================================================
# 설정
# =============================================================================

TARGET_SHEETS = [
    '조직형태별',
    '대표자성별별',
    '폐업여부별',
    '산업분류별',
    '대표사업체별',
    '수치형통계',
]

COMMON_COLUMNS = ['기준시기', '시도명', '시군구명']
TABLE_NAME = 'fact_business_status'


# =============================================================================
# 유틸리티 함수
# =============================================================================

def parse_period(period_str: str) -> Tuple[str, str, str]:
    """기준시기 문자열을 파싱하여 기준년월, 구분 반환"""
    period_str = str(period_str).strip()

    # 분기 패턴
    quarter_match = re.match(r'(\d{4})년\s*(\d)분기', period_str)
    if quarter_match:
        year = quarter_match.group(1)
        quarter = int(quarter_match.group(2))
        month = str(quarter * 3).zfill(2)
        return f"{year}{month}", '분기', year

    # 월간 패턴
    month_match = re.match(r'(\d{4})년\s*(\d{1,2})월', period_str)
    if month_match:
        year = month_match.group(1)
        month = month_match.group(2).zfill(2)
        return f"{year}{month}", '월간', year

    # 연간 패턴
    year_match = re.match(r'(\d{4})년', period_str)
    if year_match:
        year = year_match.group(1)
        return f"{year}12", '연간', year

    logger.warning(f"기준시기 파싱 실패: {period_str}")
    return '', '', ''


def clean_column_name(col_name: str) -> str:
    """컬럼명 정리"""
    if pd.isna(col_name):
        return 'unknown'
    col_name = str(col_name).strip()
    if col_name == '(공백)':
        return 'blank'
    col_name = re.sub(r'[,\(\)\s\-/]', '_', col_name)
    col_name = re.sub(r'_+', '_', col_name)
    col_name = col_name.strip('_')
    return col_name


def convert_to_english_column(korean_col: str, sheet_name: str) -> str:
    """한글 컬럼명을 영문으로 변환"""
    # 공통 컬럼 처리
    if korean_col in BASE_COLUMN_MAP:
        return BASE_COLUMN_MAP[korean_col]

    # 시트별 매핑 선택
    if sheet_name == '조직형태별':
        col_map = ORG_TYPE_MAP
    elif sheet_name == '대표자성별별':
        col_map = GENDER_MAP
    elif sheet_name == '폐업여부별':
        col_map = STATUS_MAP
    elif sheet_name == '산업분류별':
        col_map = INDUSTRY_MAP
    elif sheet_name == '대표사업체별':
        col_map = MAIN_BIZ_MAP
    elif sheet_name == '수치형통계':
        col_map = STATS_MAP
    else:
        col_map = {}

    # 매핑 찾기
    clean_col = clean_column_name(korean_col)

    # 직접 매핑
    if korean_col in col_map:
        return col_map[korean_col]
    if clean_col in col_map:
        return col_map[clean_col]

    # 수치형통계는 특별 처리 (언더스코어로 연결된 컬럼명)
    if sheet_name == '수치형통계':
        for k, v in STATS_MAP.items():
            if k in clean_col or clean_col in k:
                return v

    # 매핑 못 찾으면 원본 반환
    logger.warning(f"매핑 없음: {sheet_name}/{korean_col}")
    return clean_col.lower()


def convert_star_to_null(df: pd.DataFrame) -> pd.DataFrame:
    """'*' 값을 NULL로 변환하고 숫자형으로 변환"""
    for col in df.columns:
        if df[col].dtype == 'object':
            # '*' 값을 NaN으로 변환
            df[col] = df[col].replace('*', np.nan)

            # 숫자로 변환 가능한지 확인
            try:
                # 숫자가 아닌 값이 있는지 확인
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    # 숫자로 변환 시도
                    numeric_vals = pd.to_numeric(non_null, errors='coerce')
                    if numeric_vals.notna().all():
                        df[col] = pd.to_numeric(df[col], errors='coerce')
            except:
                pass

    return df


def get_display_name(english_col: str) -> str:
    """영문 컬럼명을 한글 표시명으로 변환"""
    return DISPLAY_NAME_MAP.get(english_col, english_col)


# =============================================================================
# 엑셀 처리 함수
# =============================================================================

def read_sheet(file_path: str, sheet_name: str) -> pd.DataFrame:
    """개별 시트를 읽어서 정리된 DataFrame 반환"""
    logger.info(f"시트 읽기: {sheet_name}")

    df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)

    # 첫 번째 컬럼이 NaN인 경우 제거 (수치형통계)
    if df.columns[0] is None or pd.isna(df.columns[0]):
        df = df.iloc[:, 1:]

    # 컬럼명을 영문으로 변환
    original_cols = df.columns.tolist()
    new_cols = []

    for col in original_cols:
        if col in COMMON_COLUMNS:
            eng_col = BASE_COLUMN_MAP.get(col, col)
        else:
            eng_col = convert_to_english_column(col, sheet_name)
        new_cols.append(eng_col)

    df.columns = new_cols

    # unnamed, unknown 컬럼 제거
    df = df[[c for c in df.columns if 'unnamed' not in c.lower()]]

    # NaN 행 제거
    if 'sigungu_nm' in df.columns:
        df = df.dropna(subset=['sigungu_nm'])

    # 기준시기, 시도명 ffill
    if 'period_str' in df.columns:
        df['period_str'] = df['period_str'].ffill()
    if 'sido_nm' in df.columns:
        df['sido_nm'] = df['sido_nm'].ffill()

    # '*' 값을 NULL로 변환
    df = convert_star_to_null(df)

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
            merge_cols = ['period_str', 'sido_nm', 'sigungu_nm']
            merge_cols = [c for c in merge_cols if c in merged_df.columns and c in df.columns]
            data_cols = [c for c in df.columns if c not in merge_cols]

            merged_df = merged_df.merge(
                df[merge_cols + data_cols],
                on=merge_cols,
                how='outer'
            )

    if merged_df is None:
        raise ValueError("병합할 데이터가 없습니다.")

    # 기준년월, 구분 컬럼 추가
    logger.info("기준년월, 구분 컬럼 추가")

    merged_df['base_ym'] = ''
    merged_df['period_type'] = ''
    merged_df['year'] = ''

    for idx, row in merged_df.iterrows():
        base_ym, period_type, year = parse_period(row['period_str'])
        merged_df.at[idx, 'base_ym'] = base_ym
        merged_df.at[idx, 'period_type'] = period_type
        merged_df.at[idx, 'year'] = year

    # 컬럼 순서 정리
    priority_cols = ['base_ym', 'year', 'period_type', 'period_str', 'sido_nm', 'sigungu_nm']
    other_cols = [c for c in merged_df.columns if c not in priority_cols]
    merged_df = merged_df[priority_cols + other_cols]

    logger.info(f"병합 완료: {len(merged_df)} 행, {len(merged_df.columns)} 컬럼")
    return merged_df


def show_dataframe_info(df: pd.DataFrame):
    """DataFrame 정보 출력"""
    print("\n" + "=" * 70)
    print("병합된 데이터 요약")
    print("=" * 70)
    print(f"총 행 수: {len(df):,}")
    print(f"총 컬럼 수: {len(df.columns)}")

    print("\n=== 컬럼 목록 (영문 → 한글) ===")
    for i, col in enumerate(df.columns, 1):
        dtype = df[col].dtype
        non_null = df[col].notna().sum()
        display = get_display_name(col)
        print(f"{i:3}. {col:30} → {display:20} | {str(dtype):10} | {non_null:,} 유효값")

    print("\n=== 샘플 데이터 (처음 3행) ===")
    print(df[['base_ym', 'sido_nm', 'sigungu_nm', 'org_total', 'ind_total']].head(3).to_string())

    print("\n=== 시도별 데이터 수 ===")
    if 'sido_nm' in df.columns:
        print(df['sido_nm'].value_counts())


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
        for col in df.columns:
            dtype = df[col].dtype

            if col == 'base_ym':
                col_def = f'"{col}" VARCHAR(6)'
            elif col in ['year']:
                col_def = f'"{col}" VARCHAR(4)'
            elif col in ['period_type', 'period_str', 'sido_nm', 'sigungu_nm']:
                col_def = f'"{col}" VARCHAR(100)'
            elif dtype == 'int64':
                col_def = f'"{col}" BIGINT'
            elif dtype == 'float64':
                col_def = f'"{col}" NUMERIC(20, 2)'
            else:
                col_def = f'"{col}" VARCHAR(255)'

            col_definitions.append(col_def)

        create_sql = f"""
        CREATE TABLE {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            {', '.join(col_definitions)},
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        cursor.execute(create_sql)

        # 인덱스 생성
        cursor.execute(f'CREATE INDEX idx_{TABLE_NAME}_base_ym ON {TABLE_NAME}("base_ym")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_NAME}_sido ON {TABLE_NAME}("sido_nm")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_NAME}_sigungu ON {TABLE_NAME}("sigungu_nm")')

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


def check_existing_data(base_ym: str) -> int:
    """기존 데이터 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f'SELECT COUNT(*) FROM {TABLE_NAME} WHERE "base_ym" = %s', (base_ym,))
        count = cursor.fetchone()[0]
        return count
    except:
        return 0
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# 메인 함수
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='기업체현황 엑셀 데이터 처리')
    parser.add_argument('--file', '-f', help='엑셀 파일 경로')
    parser.add_argument('--init', action='store_true', help='테이블 초기화')
    parser.add_argument('--insert', action='store_true', help='데이터 삽입')
    parser.add_argument('--output', '-o', help='CSV 출력 파일')

    args = parser.parse_args()
    os.chdir(Path(__file__).parent)

    if args.file:
        if not Path(args.file).exists():
            logger.error(f"파일 없음: {args.file}")
            return

        df = merge_all_sheets(args.file)
        show_dataframe_info(df)

        if args.output:
            df.to_csv(args.output, index=False, encoding='utf-8-sig')
            logger.info(f"CSV 저장: {args.output}")

        if args.init:
            create_table(df)

        if args.insert:
            base_ym = df['base_ym'].iloc[0] if len(df) > 0 else ''
            existing = check_existing_data(base_ym)

            if existing > 0:
                logger.warning(f"기존 데이터 존재: {base_ym} ({existing}건)")
                confirm = input("삭제 후 저장? (y/N): ")
                if confirm.lower() != 'y':
                    return

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(f'DELETE FROM {TABLE_NAME} WHERE "base_ym" = %s', (base_ym,))
                conn.commit()
                cursor.close()
                conn.close()

            insert_data(df)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
