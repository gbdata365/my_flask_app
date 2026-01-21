# -*- coding: utf-8 -*-
"""
기업체현황 엑셀 데이터 처리 스크립트 (연간/월간/분기 통합)
==========================================================

여러 시트의 엑셀 데이터를 하나로 합쳐서 PostgreSQL에 저장합니다.
- 공통 데이터: fact_business_status (기존)
- 연령그룹별: fact_business_age_group (신규 - 연간/월간)
- 업력구분: fact_business_tenure (신규 - 연간)

사용법:
    python read_xlsx_all.py --file data/(수정)집계표_연간(2023년).xlsx
    python read_xlsx_all.py --file data/(수정)집계표_월간(2025년10월).xlsx
    python read_xlsx_all.py --all --init --insert  # 모든 파일 처리
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import Optional, Tuple, Dict, List

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

# 수치형통계 컬럼 (공통)
STATS_MAP: Dict[str, str] = {
    # 기업 단위 (공통)
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
    # 사업체 단위 (연간 전용)
    '사업체종사자수_건수': 'biz_emp_count',
    '사업체종사자수_합계': 'biz_emp_total',
    '사업체종사자수_평균': 'biz_emp_avg',
    '사업체종사자수_공백건수': 'biz_emp_null_count',
    '사업체매출금액_건수': 'biz_revenue_count',
    '사업체매출금액_합계': 'biz_revenue_total',
    '사업체매출금액_평균': 'biz_revenue_avg',
    '사업체매출금액_공백건수': 'biz_revenue_null_count',
}

# 연령그룹별 컬럼 (연간/월간 전용)
# 실제 컬럼: ~19세이하, 20대초/20대말, 30대초/30대말, ... 80세이상
AGE_GROUP_MAP: Dict[str, str] = {
    '~19세이하': 'age_under_19',
    '~19세': 'age_under_19',
    '20대초': 'age_20_early',
    '20대말': 'age_20_late',
    '30대초': 'age_30_early',
    '30대말': 'age_30_late',
    '40대초': 'age_40_early',
    '40대말': 'age_40_late',
    '50대초': 'age_50_early',
    '50대말': 'age_50_late',
    '60대초': 'age_60_early',
    '60대말': 'age_60_late',
    '70대초': 'age_70_early',
    '70대말': 'age_70_late',
    '80세이상': 'age_80_over',
    '(공백)': 'age_unknown',
    'blank': 'age_unknown',
    '합계': 'age_total',
}

# 기업규모별 컬럼 (연간 전용)
BIZ_SIZE_MAP: Dict[str, str] = {
    '(공백)': 'size_unknown',
    'blank': 'size_unknown',
    '기타대기업': 'size_large_etc',
    '상출기업': 'size_listed',
    '소기업': 'size_small',
    '소상공인': 'size_micro',
    '중견기업': 'size_mid_large',
    '중기업': 'size_medium',
    '판정제외': 'size_excluded',
    '합계': 'size_total',
}

# 시트별 접두사
SHEET_PREFIX_MAP: Dict[str, str] = {
    '조직형태별': 'org',
    '대표자성별별': 'gender',
    '폐업여부별': 'status',
    '산업분류별': 'ind',
    '대표사업체별': 'main_biz',
    '수치형통계': 'stats',
    '연령그룹별': 'age',
    '기업규모별': 'size',
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
    # 사업체 단위 (연간 전용)
    'biz_emp_count': '사업체종사자_건수',
    'biz_emp_total': '사업체종사자_합계',
    'biz_emp_avg': '사업체종사자_평균',
    'biz_emp_null_count': '사업체종사자_공백',
    'biz_revenue_count': '사업체매출_건수',
    'biz_revenue_total': '사업체매출_합계',
    'biz_revenue_avg': '사업체매출_평균',
    'biz_revenue_null_count': '사업체매출_공백',

    # 연령그룹별
    'age_under_19': '19세이하',
    'age_20_early': '20대초',
    'age_20_late': '20대말',
    'age_30_early': '30대초',
    'age_30_late': '30대말',
    'age_40_early': '40대초',
    'age_40_late': '40대말',
    'age_50_early': '50대초',
    'age_50_late': '50대말',
    'age_60_early': '60대초',
    'age_60_late': '60대말',
    'age_70_early': '70대초',
    'age_70_late': '70대말',
    'age_80_over': '80세이상',
    'age_unknown': '연령미상',
    'age_total': '연령_합계',

    # 기업규모별
    'size_unknown': '규모미상',
    'size_large_etc': '기타대기업',
    'size_listed': '상출기업',
    'size_small': '소기업',
    'size_micro': '소상공인',
    'size_mid_large': '중견기업',
    'size_medium': '중기업',
    'size_excluded': '판정제외',
    'size_total': '규모_합계',
}


# =============================================================================
# 설정
# =============================================================================

# 공통 시트 (fact_business_status)
COMMON_SHEETS = [
    '조직형태별',
    '대표자성별별',
    '폐업여부별',
    '산업분류별',
    '대표사업체별',
    '수치형통계',
]

COMMON_COLUMNS = ['기준시기', '시도명', '시군구명']

# 테이블명
TABLE_MAIN = 'fact_business_status'
TABLE_AGE_GROUP = 'fact_business_age_group'
TABLE_BIZ_SIZE = 'fact_business_size'


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
    elif sheet_name == '연령그룹별':
        col_map = AGE_GROUP_MAP
    elif sheet_name == '기업규모별':
        col_map = BIZ_SIZE_MAP
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
                non_null = df[col].dropna()
                if len(non_null) > 0:
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


def add_period_columns(df: pd.DataFrame) -> pd.DataFrame:
    """기준년월, 구분 컬럼 추가"""
    df['base_ym'] = ''
    df['period_type'] = ''
    df['year'] = ''

    for idx, row in df.iterrows():
        base_ym, period_type, year = parse_period(row['period_str'])
        df.at[idx, 'base_ym'] = base_ym
        df.at[idx, 'period_type'] = period_type
        df.at[idx, 'year'] = year

    return df


def merge_common_sheets(file_path: str) -> pd.DataFrame:
    """공통 시트를 하나의 DataFrame으로 병합 (fact_business_status)"""
    logger.info(f"공통 시트 병합 시작: {file_path}")

    xl = pd.ExcelFile(file_path)
    available_sheets = xl.sheet_names
    merged_df = None

    for sheet_name in COMMON_SHEETS:
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
    merged_df = add_period_columns(merged_df)

    # 컬럼 순서 정리
    priority_cols = ['base_ym', 'year', 'period_type', 'period_str', 'sido_nm', 'sigungu_nm']
    other_cols = [c for c in merged_df.columns if c not in priority_cols]
    merged_df = merged_df[priority_cols + other_cols]

    logger.info(f"공통 데이터 병합 완료: {len(merged_df)} 행, {len(merged_df.columns)} 컬럼")
    return merged_df


def read_age_group_sheet(file_path: str) -> Optional[pd.DataFrame]:
    """연령그룹별 시트 읽기 (fact_business_age_group)"""
    xl = pd.ExcelFile(file_path)

    if '연령그룹별' not in xl.sheet_names:
        logger.info("연령그룹별 시트 없음 (분기 데이터)")
        return None

    df = read_sheet(file_path, '연령그룹별')
    df = add_period_columns(df)

    # 컬럼 순서 정리
    priority_cols = ['base_ym', 'year', 'period_type', 'period_str', 'sido_nm', 'sigungu_nm']
    other_cols = [c for c in df.columns if c not in priority_cols]
    df = df[priority_cols + other_cols]

    logger.info(f"연령그룹별 데이터: {len(df)} 행, {len(df.columns)} 컬럼")
    return df


def read_biz_size_sheet(file_path: str) -> Optional[pd.DataFrame]:
    """기업규모별 시트 읽기 (fact_business_size)"""
    xl = pd.ExcelFile(file_path)

    if '기업규모별' not in xl.sheet_names:
        logger.info("기업규모별 시트 없음 (분기/월간 데이터)")
        return None

    df = read_sheet(file_path, '기업규모별')
    df = add_period_columns(df)

    # 컬럼 순서 정리
    priority_cols = ['base_ym', 'year', 'period_type', 'period_str', 'sido_nm', 'sigungu_nm']
    other_cols = [c for c in df.columns if c not in priority_cols]
    df = df[priority_cols + other_cols]

    logger.info(f"기업규모별 데이터: {len(df)} 행, {len(df.columns)} 컬럼")
    return df


def show_dataframe_info(df: pd.DataFrame, title: str = "데이터"):
    """DataFrame 정보 출력"""
    print("\n" + "=" * 70)
    print(f"{title} 요약")
    print("=" * 70)
    print(f"총 행 수: {len(df):,}")
    print(f"총 컬럼 수: {len(df.columns)}")

    print("\n=== 컬럼 목록 (영문 → 한글) ===")
    for i, col in enumerate(df.columns, 1):
        dtype = df[col].dtype
        non_null = df[col].notna().sum()
        display = get_display_name(col)
        print(f"{i:3}. {col:30} → {display:20} | {str(dtype):10} | {non_null:,} 유효값")


# =============================================================================
# 데이터베이스 함수
# =============================================================================

def create_table_main(df: pd.DataFrame):
    """fact_business_status 테이블 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_MAIN} CASCADE")

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
        CREATE TABLE {TABLE_MAIN} (
            id SERIAL PRIMARY KEY,
            {', '.join(col_definitions)},
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        cursor.execute(create_sql)

        # 인덱스 생성
        cursor.execute(f'CREATE INDEX idx_{TABLE_MAIN}_base_ym ON {TABLE_MAIN}("base_ym")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_MAIN}_period_type ON {TABLE_MAIN}("period_type")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_MAIN}_sido ON {TABLE_MAIN}("sido_nm")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_MAIN}_sigungu ON {TABLE_MAIN}("sigungu_nm")')

        conn.commit()
        logger.info(f"테이블 생성 완료: {TABLE_MAIN}")

    except Exception as e:
        conn.rollback()
        logger.error(f"테이블 생성 실패: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def create_table_age_group():
    """fact_business_age_group 테이블 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_AGE_GROUP} CASCADE")

        create_sql = f"""
        CREATE TABLE {TABLE_AGE_GROUP} (
            id SERIAL PRIMARY KEY,
            base_ym VARCHAR(6),
            year VARCHAR(4),
            period_type VARCHAR(10),
            period_str VARCHAR(100),
            sido_nm VARCHAR(100),
            sigungu_nm VARCHAR(100),
            age_under_19 BIGINT,
            age_20_early BIGINT,
            age_20_late BIGINT,
            age_30_early BIGINT,
            age_30_late BIGINT,
            age_40_early BIGINT,
            age_40_late BIGINT,
            age_50_early BIGINT,
            age_50_late BIGINT,
            age_60_early BIGINT,
            age_60_late BIGINT,
            age_70_early BIGINT,
            age_70_late BIGINT,
            age_80_over BIGINT,
            age_unknown BIGINT,
            age_total BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        cursor.execute(create_sql)

        # 인덱스 생성
        cursor.execute(f'CREATE INDEX idx_{TABLE_AGE_GROUP}_base_ym ON {TABLE_AGE_GROUP}("base_ym")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_AGE_GROUP}_period_type ON {TABLE_AGE_GROUP}("period_type")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_AGE_GROUP}_sido ON {TABLE_AGE_GROUP}("sido_nm")')

        conn.commit()
        logger.info(f"테이블 생성 완료: {TABLE_AGE_GROUP}")

    except Exception as e:
        conn.rollback()
        logger.error(f"테이블 생성 실패: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def create_table_biz_size():
    """fact_business_size 테이블 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_BIZ_SIZE} CASCADE")

        create_sql = f"""
        CREATE TABLE {TABLE_BIZ_SIZE} (
            id SERIAL PRIMARY KEY,
            base_ym VARCHAR(6),
            year VARCHAR(4),
            period_type VARCHAR(10),
            period_str VARCHAR(100),
            sido_nm VARCHAR(100),
            sigungu_nm VARCHAR(100),
            size_unknown BIGINT,
            size_large_etc BIGINT,
            size_listed BIGINT,
            size_small BIGINT,
            size_micro BIGINT,
            size_mid_large BIGINT,
            size_medium BIGINT,
            size_excluded BIGINT,
            size_total BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        cursor.execute(create_sql)

        # 인덱스 생성
        cursor.execute(f'CREATE INDEX idx_{TABLE_BIZ_SIZE}_base_ym ON {TABLE_BIZ_SIZE}("base_ym")')
        cursor.execute(f'CREATE INDEX idx_{TABLE_BIZ_SIZE}_sido ON {TABLE_BIZ_SIZE}("sido_nm")')

        conn.commit()
        logger.info(f"테이블 생성 완료: {TABLE_BIZ_SIZE}")

    except Exception as e:
        conn.rollback()
        logger.error(f"테이블 생성 실패: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def insert_data(df: pd.DataFrame, table_name: str):
    """데이터 삽입"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        columns = df.columns.tolist()
        col_names = ', '.join([f'"{c}"' for c in columns])
        placeholders = ', '.join(['%s'] * len(columns))

        insert_sql = f'INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})'

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
        logger.info(f"{table_name} 데이터 삽입 완료: {inserted:,} 행")

    except Exception as e:
        conn.rollback()
        logger.error(f"데이터 삽입 실패: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def delete_existing_data(table_name: str, base_ym: str):
    """기존 데이터 삭제"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f'DELETE FROM {table_name} WHERE "base_ym" = %s', (base_ym,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted > 0:
            logger.info(f"{table_name}에서 {base_ym} 데이터 {deleted}건 삭제")
    except:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def check_existing_data(table_name: str, base_ym: str) -> int:
    """기존 데이터 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name} WHERE "base_ym" = %s', (base_ym,))
        count = cursor.fetchone()[0]
        return count
    except:
        return 0
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# 파일 탐색 함수
# =============================================================================

def find_excel_files(data_dir: str) -> Dict[str, List[str]]:
    """데이터 디렉토리에서 엑셀 파일 찾기"""
    files = {
        '분기': [],
        '연간': [],
        '월간': [],
    }

    for f in Path(data_dir).glob('*.xlsx'):
        filename = f.name
        if '집계표' not in filename:
            continue

        if '분기' in filename:
            files['분기'].append(str(f))
        elif '연간' in filename:
            files['연간'].append(str(f))
        elif '월간' in filename:
            files['월간'].append(str(f))

    return files


# =============================================================================
# 메인 함수
# =============================================================================

def process_single_file(file_path: str, do_insert: bool = False):
    """단일 파일 처리"""
    logger.info(f"\n{'='*70}")
    logger.info(f"파일 처리: {file_path}")
    logger.info(f"{'='*70}")

    # 공통 데이터 (fact_business_status)
    df_main = merge_common_sheets(file_path)
    show_dataframe_info(df_main, "공통 데이터 (fact_business_status)")

    if do_insert:
        base_ym = df_main['base_ym'].iloc[0]
        existing = check_existing_data(TABLE_MAIN, base_ym)
        if existing > 0:
            delete_existing_data(TABLE_MAIN, base_ym)
        insert_data(df_main, TABLE_MAIN)

    # 연령그룹별 데이터 (fact_business_age_group)
    df_age = read_age_group_sheet(file_path)
    if df_age is not None:
        show_dataframe_info(df_age, "연령그룹별 데이터 (fact_business_age_group)")

        if do_insert:
            base_ym = df_age['base_ym'].iloc[0]
            existing = check_existing_data(TABLE_AGE_GROUP, base_ym)
            if existing > 0:
                delete_existing_data(TABLE_AGE_GROUP, base_ym)
            insert_data(df_age, TABLE_AGE_GROUP)

    # 기업규모별 데이터 (fact_business_size)
    df_size = read_biz_size_sheet(file_path)
    if df_size is not None:
        show_dataframe_info(df_size, "기업규모별 데이터 (fact_business_size)")

        if do_insert:
            base_ym = df_size['base_ym'].iloc[0]
            existing = check_existing_data(TABLE_BIZ_SIZE, base_ym)
            if existing > 0:
                delete_existing_data(TABLE_BIZ_SIZE, base_ym)
            insert_data(df_size, TABLE_BIZ_SIZE)

    return df_main, df_age, df_size


def main():
    parser = argparse.ArgumentParser(description='기업체현황 엑셀 데이터 처리 (연간/월간/분기 통합)')
    parser.add_argument('--file', '-f', help='엑셀 파일 경로')
    parser.add_argument('--all', action='store_true', help='data 폴더의 모든 파일 처리')
    parser.add_argument('--init', action='store_true', help='테이블 초기화')
    parser.add_argument('--insert', action='store_true', help='데이터 삽입')
    parser.add_argument('--output', '-o', help='CSV 출력 파일 접두사')

    args = parser.parse_args()
    os.chdir(Path(__file__).parent)

    # 테이블 초기화
    if args.init:
        logger.info("테이블 초기화...")

        # 먼저 샘플 파일로 공통 테이블 구조 확인
        sample_files = list(Path('data').glob('*집계표*분기*.xlsx'))
        if sample_files:
            df_sample = merge_common_sheets(str(sample_files[0]))
            create_table_main(df_sample)

        create_table_age_group()
        create_table_biz_size()

    # 단일 파일 처리
    if args.file:
        if not Path(args.file).exists():
            logger.error(f"파일 없음: {args.file}")
            return

        process_single_file(args.file, args.insert)

    # 모든 파일 처리
    elif args.all:
        files = find_excel_files('data')

        logger.info(f"\n발견된 파일:")
        logger.info(f"  분기: {len(files['분기'])}개")
        logger.info(f"  연간: {len(files['연간'])}개")
        logger.info(f"  월간: {len(files['월간'])}개")

        # 분기 파일 처리
        for f in sorted(files['분기']):
            process_single_file(f, args.insert)

        # 연간 파일 처리
        for f in sorted(files['연간']):
            process_single_file(f, args.insert)

        # 월간 파일 처리
        for f in sorted(files['월간']):
            process_single_file(f, args.insert)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
