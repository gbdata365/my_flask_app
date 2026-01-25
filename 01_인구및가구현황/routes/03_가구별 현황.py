# -*- coding: utf-8 -*-
"""
================================================================================
가구·세대 지표 대시보드 (edu_dash9.py)
================================================================================

[목적]
- 전체가구수, 연령별 1인가구, 세대지표 현황 표시
- 다양한 집계 단위(권역별/시도별/시군구별) 지원

[주요 기능]
1. 전체가구 현황 (지역별/시도별/시군구별)
2. 연령별 1인가구 현황 (5세별/10세별)
3. 세대지표 (1인가구비율, 가구당인구수, 고령1인가구비율 등)
4. 필터: 권역, 시도, 시군구, 기준년월, 연령구분

[코드 테이블]
- code_indicator (category=2): 세대지표 정의

[기술 스택]
- Backend: Flask (Python)
- Frontend: Bootstrap 5 + JavaScript
- Database: PostgreSQL
- Chart: Matplotlib (정적 PNG)

================================================================================
"""
import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
import io
import base64
from datetime import datetime
import koreanize_matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_engine
from module.menu_generator import MenuGenerator
from module.data_query import (
    CacheDataQuery,
    get_indicators_from_db,
    build_indicator_sql_expr,
    calculate_indicator_df,
    get_indicator_by_column_name,
    get_column_labels
)
from flask import jsonify, Response, send_file, request

# 공통 내보내기 모듈
from common.export_utils import DataExporter

POP_BASE = Path(__file__).parent.parent
TEMPLATE_DIR = POP_BASE / 'templates'

# 동적 URL 생성 (하드코딩 제거)
CATEGORY_NAME = POP_BASE.name  # '01_인구및가구현황'
FILE_STEM = Path(__file__).stem  # '03_가구별 현황'
CURRENT_URL = f'/{CATEGORY_NAME}/routes/{FILE_STEM}'

# 차트 설정
try:
    from config.chart_config import (
        HOUSEHOLD_UNIT, SINGLE_AGE_UNIT, REGIONAL_SUBPLOT, ACCORDION_TABLE,
        get_unit_config, convert_value
    )
except ImportError:
    # 설정 파일 없으면 기본값
    HOUSEHOLD_UNIT = {'unit': 100, 'label': '백 가구', 'format': '{:,.0f}'}
    SINGLE_AGE_UNIT = {'unit': 100, 'label': '백 가구', 'format': '{:,.0f}'}
    REGIONAL_SUBPLOT = {'max_regions': None, 'cols': 4, 'fig_width_per_col': 4, 'fig_height_per_row': 3.5}
    ACCORDION_TABLE = {'expand_all': True}

# Jinja2 환경 설정
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


# =============================================================================
# 코드 테이블 조회 함수
# =============================================================================

def get_single_age_groups_from_db(category=1):
    """
    연령그룹 정의 조회 (1인가구용)

    Args:
        category: 1=5세별, 2=10세별
    """
    engine = get_db_engine()
    df = pd.read_sql(f"""
        SELECT
            id, category, category_name, code, code_name,
            column_name, age_start, age_end, sort_order
        FROM code_age_group
        WHERE category = {category}
          AND is_active = TRUE
        ORDER BY sort_order
    """, engine)
    return df


def get_active_household_indicators():
    """활성 세대지표 목록 조회 (category=2) - data_query 유틸리티 사용"""
    try:
        # data_query 모듈의 공통 함수 사용
        return get_indicators_from_db(category=2)
    except Exception as e:
        print(f"세대지표 조회 오류: {e}")
        # 기본 세대지표 (fallback)
        return [
            {'column_name': 'single_ratio', 'display_name': '1인가구비율',
             'description': '1인가구 / 전체가구 × 100', 'numerator': 'single_cnt',
             'denominator': 'household_cnt', 'multiplier': 100, 'decimal_places': 2},
            {'column_name': 'pop_per_house', 'display_name': '세대당인구',
             'description': '총인구 / 전체가구', 'numerator': 'total_pop',
             'denominator': 'household_cnt', 'multiplier': 1, 'decimal_places': 2},
        ]


def get_column_name_labels_local():
    """
    DB 코드 테이블에서 컬럼명 → 한글 라벨 매핑 조회
    (data_query.get_column_labels() 기반 + 로컬 기본값)
    """
    # 공통 유틸리티에서 DB 라벨 조회
    labels = get_column_labels()

    # 기본 라벨 (DB에 없는 컬럼용)
    default_labels = {
        'household_cnt': '전체가구',
        'single_cnt': '1인가구',
        'single_total': '1인가구',
        'total_pop': '총인구',
        'male_pop': '남자인구',
        'female_pop': '여자인구',
        'elderly_pop': '고령인구',
        'youth_pop': '유소년인구',
        'working_pop': '생산가능인구',
    }

    # 기본 라벨을 먼저 넣고, DB 라벨로 덮어쓰기
    return {**default_labels, **labels}


# =============================================================================
# 초기 화면 요약 테이블 생성
# =============================================================================

def generate_initial_summary_table():
    """
    초기 화면에 표시할 시도별 요약 테이블 생성 (가구/세대 현황용)
    """
    try:
        query = CacheDataQuery('cache_sigungu_indicators')

        # 최신 년월 데이터로 시도별 요약 조회
        summary_columns = ['household_cnt', 'single_cnt', 'total_pop']
        df = query.get_sido_summary(summary_columns, latest_n=1)

        if df.empty:
            return '<p class="text-muted text-center py-5">데이터가 없습니다.</p>'

        # 전국 합계 추가
        df = query.add_national_total(df, summary_columns)

        # code_indicator 기반 지표 계산 (동적)
        # 1인가구비율: single_ratio = single_cnt / household_cnt * 100
        single_ratio_def = get_indicator_by_column_name('single_ratio')
        if single_ratio_def:
            df = calculate_indicator_df(
                df, single_ratio_def['numerator'], single_ratio_def['denominator'],
                'single_ratio', single_ratio_def['multiplier'], single_ratio_def['decimal_places']
            )
        else:
            df['single_ratio'] = (df['single_cnt'] / df['household_cnt'].replace(0, float('nan')) * 100).round(1).fillna(0)

        # 세대당인구: pop_per_house = total_pop / household_cnt
        pop_per_house_def = get_indicator_by_column_name('pop_per_house')
        if pop_per_house_def:
            df = calculate_indicator_df(
                df, pop_per_house_def['numerator'], pop_per_house_def['denominator'],
                'pop_per_household', pop_per_house_def['multiplier'], pop_per_house_def['decimal_places']
            )
        else:
            df['pop_per_household'] = (df['total_pop'] / df['household_cnt'].replace(0, float('nan'))).round(2).fillna(0)

        # 최신 년월 가져오기
        latest_ym = df['base_ym'].iloc[0] if 'base_ym' in df.columns else ''
        ym_display = f"{latest_ym[:4]}.{latest_ym[4:]}" if latest_ym else ''

        # HTML 테이블 생성
        html = []
        html.append(f'<p class="text-sm text-gray-500 mb-2">기준: {ym_display} (최신)</p>')
        html.append('<table class="table table-sm table-bordered">')
        html.append('<thead class="bg-primary text-white">')
        html.append('<tr>')
        html.append('<th class="text-center" style="width:140px;">시도</th>')
        html.append('<th class="text-center">세대수</th>')
        html.append('<th class="text-center">1인가구</th>')
        html.append('<th class="text-center">1인가구비율(%)</th>')
        html.append('<th class="text-center">가구당인구</th>')
        html.append('</tr>')
        html.append('</thead>')
        html.append('<tbody>')

        for _, row in df.iterrows():
            name = row.get('name', '')
            is_total = name == '전국'
            is_highlight = name == '경상북도'

            row_class = 'bg-warning-subtle fw-bold' if is_total else ('bg-highlight' if is_highlight else '')
            html.append(f'<tr class="{row_class}">')
            html.append(f'<td class="text-center">{name}</td>')
            html.append(f'<td class="text-end num">{int(row.get("household_cnt", 0)):,}</td>')
            html.append(f'<td class="text-end num">{int(row.get("single_cnt", 0)):,}</td>')
            html.append(f'<td class="text-end num">{row.get("single_ratio", 0):.1f}</td>')
            html.append(f'<td class="text-end num">{row.get("pop_per_household", 0):.2f}</td>')
            html.append('</tr>')

        html.append('</tbody>')
        html.append('</table>')
        html.append('<p class="text-sm text-gray-400 mt-2">※ 상세 데이터는 조회 조건을 선택하고 [조회] 버튼을 클릭하세요.</p>')

        return '\n'.join(html)

    except Exception as e:
        print(f"초기 요약 테이블 생성 오류: {e}")
        return '<p class="text-muted text-center py-5">조회 버튼을 클릭하여 데이터를 불러오세요.</p>'


def get_filter_options():
    """필터 옵션 조회"""
    engine = get_db_engine()

    # 기준년월 목록
    ym_df = pd.read_sql("""
        SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as ym
        FROM cache_sigungu_indicators
        ORDER BY ym DESC
    """, engine)

    # 권역 목록
    region_df = pd.read_sql("""
        SELECT DISTINCT region_nm
        FROM dim_admin_area
        WHERE region_nm IS NOT NULL
        ORDER BY region_nm
    """, engine)

    # 시도 목록 (캐시 테이블은 이미 정규화된 시도명 사용)
    sido_df = pd.read_sql("""
        SELECT DISTINCT sido_nm, MIN(LEFT(sigungu_code, 2)) as sido_code
        FROM cache_sigungu_indicators
        GROUP BY sido_nm
        ORDER BY sido_code
    """, engine)

    # 연령 카테고리 목록
    age_categories = [
        {'id': 1, 'name': '5세별'},
        {'id': 2, 'name': '10세별'}
    ]

    return {
        'base_ym_list': ym_df['ym'].tolist(),
        'region_list': region_df['region_nm'].tolist(),
        'sido_list': sido_df['sido_nm'].tolist(),
        'age_categories': age_categories,
        'active_indicators': get_active_household_indicators()
    }


# =============================================================================
# 데이터 조회 함수
# =============================================================================

def get_household_table(base_ym_list, aggregate_type='sido', region=None, sido=None, include_sub_sigungu=False):
    """
    가구 현황 테이블 조회

    Args:
        base_ym_list: 기준년월 리스트
        aggregate_type: 집계 단위 ('region', 'sido', 'sigungu')
        region: 권역명 (권역별일 때)
        sido: 시도명 (시군구별일 때)
        include_sub_sigungu: 하위 시군구 포함 여부
    """
    engine = get_db_engine()
    results = []

    for ym in base_ym_list:
        if aggregate_type == 'region':
            # 권역별
            df = pd.read_sql(f"""
                SELECT
                    d.region_nm as name,
                    d.region_code,
                    SUM(COALESCE(c.household_cnt, 0)) as household_cnt,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                    SUM(c.total_pop) as total_pop
                FROM cache_sigungu_indicators c
                JOIN (
                    SELECT DISTINCT sigungu_code, region_nm, region_code
                    FROM dim_admin_area
                    WHERE region_nm IS NOT NULL
                ) d ON c.sigungu_code = d.sigungu_code
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                GROUP BY d.region_nm, d.region_code
                ORDER BY d.region_code
            """, engine)
        elif aggregate_type == 'sigungu' and sido:
            # 시군구별 (캐시 테이블은 이미 정규화된 시도명 사용)
            sido_cond = f"c.sido_nm = '{sido}'"

            if include_sub_sigungu:
                # 하위 시군구 포함
                df = pd.read_sql(f"""
                    SELECT
                        c.sigungu_code,
                        c.sigungu_nm as name,
                        SUM(COALESCE(c.household_cnt, 0)) as household_cnt,
                        SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                        SUM(c.total_pop) as total_pop
                    FROM cache_sigungu_indicators c
                    WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                      AND {sido_cond}
                    GROUP BY c.sigungu_code, c.sigungu_nm
                    ORDER BY c.sigungu_code
                """, engine)
            else:
                # 4자리 그룹화 (마지막자리 0)
                df = pd.read_sql(f"""
                    SELECT
                        LEFT(c.sigungu_code, 4) || '0' as sigungu_code,
                        MIN(CASE WHEN c.sigungu_code LIKE '____0' THEN c.sigungu_nm
                            ELSE REGEXP_REPLACE(c.sigungu_nm, ' .*$', '') END) as name,
                        SUM(COALESCE(c.household_cnt, 0)) as household_cnt,
                        SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                        SUM(c.total_pop) as total_pop
                    FROM cache_sigungu_indicators c
                    WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                      AND {sido_cond}
                    GROUP BY LEFT(c.sigungu_code, 4)
                    ORDER BY LEFT(c.sigungu_code, 4) || '0'
                """, engine)
        else:
            # 시도별 (sido_alias 사용 - 2자리 축약명)
            df = pd.read_sql(f"""
                SELECT
                    c.sido_alias as name,
                    MIN(LEFT(c.sigungu_code, 2)) as sido_code,
                    SUM(COALESCE(c.household_cnt, 0)) as household_cnt,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                    SUM(c.total_pop) as total_pop
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                GROUP BY c.sido_alias
                ORDER BY MIN(LEFT(c.sigungu_code, 2))
            """, engine)

        df['base_ym'] = ym
        results.append(df)

    if not results:
        return {'headers': [], 'data': []}

    combined_df = pd.concat(results, ignore_index=True)

    if combined_df.empty:
        return {'headers': [], 'data': []}

    # 정렬 기준
    if aggregate_type == 'sigungu' and 'sigungu_code' in combined_df.columns:
        pivot_household = combined_df.pivot(index='sigungu_code', columns='base_ym', values='household_cnt').fillna(0)
        pivot_single = combined_df.pivot(index='sigungu_code', columns='base_ym', values='single_cnt').fillna(0)
        pivot_pop = combined_df.pivot(index='sigungu_code', columns='base_ym', values='total_pop').fillna(0)
        code_to_name = combined_df.drop_duplicates('sigungu_code').set_index('sigungu_code')['name'].to_dict()
    elif aggregate_type == 'region' and 'region_code' in combined_df.columns:
        pivot_household = combined_df.pivot(index='region_code', columns='base_ym', values='household_cnt').fillna(0)
        pivot_single = combined_df.pivot(index='region_code', columns='base_ym', values='single_cnt').fillna(0)
        pivot_pop = combined_df.pivot(index='region_code', columns='base_ym', values='total_pop').fillna(0)
        pivot_household = pivot_household.sort_index()
        pivot_single = pivot_single.sort_index()
        pivot_pop = pivot_pop.sort_index()
        code_to_name = combined_df.drop_duplicates('region_code').set_index('region_code')['name'].to_dict()
    elif 'sido_code' in combined_df.columns:
        pivot_household = combined_df.pivot(index='sido_code', columns='base_ym', values='household_cnt').fillna(0)
        pivot_single = combined_df.pivot(index='sido_code', columns='base_ym', values='single_cnt').fillna(0)
        pivot_pop = combined_df.pivot(index='sido_code', columns='base_ym', values='total_pop').fillna(0)
        pivot_household = pivot_household.sort_index()
        pivot_single = pivot_single.sort_index()
        pivot_pop = pivot_pop.sort_index()
        code_to_name = combined_df.drop_duplicates('sido_code').set_index('sido_code')['name'].to_dict()
    else:
        pivot_household = combined_df.pivot(index='name', columns='base_ym', values='household_cnt').fillna(0)
        pivot_single = combined_df.pivot(index='name', columns='base_ym', values='single_cnt').fillna(0)
        pivot_pop = combined_df.pivot(index='name', columns='base_ym', values='total_pop').fillna(0)
        code_to_name = None

    data = []

    # 전국/합계
    total_row = {'name': '전국' if aggregate_type != 'sigungu' else '합계'}
    for i, ym in enumerate(base_ym_list):
        if ym in pivot_household.columns:
            total_row[f'household_{ym}'] = int(pivot_household[ym].sum())
            total_row[f'single_{ym}'] = int(pivot_single[ym].sum())
            # 1인가구비율
            if total_row[f'household_{ym}'] > 0:
                total_row[f'single_ratio_{ym}'] = round(total_row[f'single_{ym}'] / total_row[f'household_{ym}'] * 100, 2)
            else:
                total_row[f'single_ratio_{ym}'] = 0

            # 증감률 (가장 오래된 시점 제외)
            if i < len(base_ym_list) - 1 and base_ym_list[i+1] in pivot_household.columns:
                prev_household = int(pivot_household[base_ym_list[i+1]].sum())
                prev_single = int(pivot_single[base_ym_list[i+1]].sum())
                if prev_household > 0:
                    total_row[f'household_rate_{ym}'] = round((total_row[f'household_{ym}'] - prev_household) / prev_household * 100, 2)
                if prev_single > 0:
                    total_row[f'single_rate_{ym}'] = round((total_row[f'single_{ym}'] - prev_single) / prev_single * 100, 2)
    data.append(total_row)

    # 각 지역 행
    for idx in pivot_household.index:
        name = code_to_name.get(idx, idx) if code_to_name else idx
        row = {'name': name}

        for i, ym in enumerate(base_ym_list):
            if ym in pivot_household.columns:
                household = int(pivot_household.loc[idx, ym]) if pd.notna(pivot_household.loc[idx, ym]) else 0
                single = int(pivot_single.loc[idx, ym]) if pd.notna(pivot_single.loc[idx, ym]) else 0
                row[f'household_{ym}'] = household
                row[f'single_{ym}'] = single
                row[f'single_ratio_{ym}'] = round(single / household * 100, 2) if household > 0 else 0

                # 증감률
                if i < len(base_ym_list) - 1 and base_ym_list[i+1] in pivot_household.columns:
                    prev_household = int(pivot_household.loc[idx, base_ym_list[i+1]]) if pd.notna(pivot_household.loc[idx, base_ym_list[i+1]]) else 0
                    prev_single = int(pivot_single.loc[idx, base_ym_list[i+1]]) if pd.notna(pivot_single.loc[idx, base_ym_list[i+1]]) else 0
                    if prev_household > 0:
                        row[f'household_rate_{ym}'] = round((household - prev_household) / prev_household * 100, 2)
                    if prev_single > 0:
                        row[f'single_rate_{ym}'] = round((single - prev_single) / prev_single * 100, 2)

        data.append(row)

    return {'data': data}


def get_single_by_age_table(base_ym_list, age_category=1, aggregate_type='sido', sido=None):
    """
    연령별 1인가구 현황 테이블

    cache_sigungu_age 테이블에서 male_single_*, female_single_* 컬럼 사용
    """
    engine = get_db_engine()

    # 연령그룹 정의 조회
    age_groups = get_single_age_groups_from_db(age_category)
    if age_groups.empty:
        return {'headers': [], 'data': []}

    # 5세별/10세별에 따른 컬럼 매핑
    # DB 컬럼: male_single_0 ~ male_single_109, male_single_110_over
    age_columns = []
    for _, row in age_groups.iterrows():
        age_start = row['age_start']
        age_end = row['age_end']
        code_name = row['code_name']

        cols = []
        # age_start부터 실제 age_end까지 (최대 109) 개별 컬럼 추가
        actual_end = min(age_end, 109)
        for age in range(age_start, actual_end + 1):
            cols.append(f'male_single_{age}')
            cols.append(f'female_single_{age}')

        # age_end >= 110 이면 110_over 컬럼도 추가 (100세이상, 80세이상 등)
        if age_end >= 110:
            cols.append('male_single_110_over')
            cols.append('female_single_110_over')

        age_columns.append((code_name, age_start, age_end, cols))

    results = []

    for ym in base_ym_list:
        select_cols = []
        for code_name, age_start, age_end, cols in age_columns:
            col_sum = ' + '.join([f'COALESCE({c}, 0)' for c in cols])
            safe_name = code_name.replace('~', '_').replace('+', '_').replace('세', '')
            select_cols.append(f'SUM({col_sum}) as "single_{safe_name}"')

        cols_sql = ', '.join(select_cols)

        # 집계 유형에 따른 쿼리 생성
        if aggregate_type == 'region':
            # 권역별 집계
            df = pd.read_sql(f"""
                SELECT
                    d.region_nm as name,
                    MIN(d.region_code) as sort_code,
                    SUM(single_total) as single_total,
                    {cols_sql}
                FROM cache_sigungu_age c
                JOIN (
                    SELECT DISTINCT sigungu_code, region_nm, region_code
                    FROM dim_admin_area
                    WHERE region_nm IS NOT NULL
                ) d ON c.sigungu_code = d.sigungu_code
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                GROUP BY d.region_nm
                ORDER BY MIN(d.region_code)
            """, engine)
        elif aggregate_type == 'sigungu' and sido:
            # 시군구별 집계 (특정 시도 내)
            df = pd.read_sql(f"""
                SELECT
                    c.sigungu_nm as name,
                    MIN(c.sigungu_code) as sort_code,
                    SUM(single_total) as single_total,
                    {cols_sql}
                FROM cache_sigungu_age c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                  AND c.sido_nm = '{sido}'
                  AND c.sigungu_code LIKE '____0'
                GROUP BY c.sigungu_nm
                ORDER BY MIN(c.sigungu_code)
            """, engine)
        else:
            # 시도별 집계 (기본) - sido_alias 사용
            df = pd.read_sql(f"""
                SELECT
                    i.sido_alias as name,
                    MIN(LEFT(c.sigungu_code, 2)) as sort_code,
                    SUM(single_total) as single_total,
                    {cols_sql}
                FROM cache_sigungu_age c
                JOIN (
                    SELECT DISTINCT sigungu_code, sido_alias
                    FROM cache_sigungu_indicators
                ) i ON c.sigungu_code = i.sigungu_code
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                GROUP BY i.sido_alias
                ORDER BY MIN(LEFT(c.sigungu_code, 2))
            """, engine)

        df['base_ym'] = ym
        results.append(df)

    if not results:
        return {'headers': [], 'data': [], 'regional_data': {}}

    combined_df = pd.concat(results, ignore_index=True)

    if combined_df.empty:
        return {'headers': [], 'data': [], 'regional_data': {}}

    # 연령그룹 컬럼명 리스트
    age_group_names = []
    for code_name, _, _, _ in age_columns:
        safe_name = code_name.replace('~', '_').replace('+', '_').replace('세', '')
        age_group_names.append((code_name, f'single_{safe_name}'))

    # 전국 합계 데이터
    national_data = []
    total_row = {'age_group': '합계'}
    for i, ym in enumerate(base_ym_list):
        ym_data = combined_df[combined_df['base_ym'] == ym]
        if not ym_data.empty:
            total = int(ym_data['single_total'].sum())
            total_row[f'pop_{ym}'] = total
            if i < len(base_ym_list) - 1:
                prev_ym = base_ym_list[i + 1]
                prev_data = combined_df[combined_df['base_ym'] == prev_ym]
                if not prev_data.empty:
                    prev_total = int(prev_data['single_total'].sum())
                    if prev_total > 0:
                        total_row[f'rate_{ym}'] = round((total - prev_total) / prev_total * 100, 2)
    national_data.append(total_row)

    # 각 연령그룹별 전국 합계
    for code_name, col_name in age_group_names:
        row = {'age_group': code_name}
        for i, ym in enumerate(base_ym_list):
            ym_data = combined_df[combined_df['base_ym'] == ym]
            if not ym_data.empty and col_name in ym_data.columns:
                val = int(ym_data[col_name].sum())
                row[f'pop_{ym}'] = val
                if i < len(base_ym_list) - 1:
                    prev_ym = base_ym_list[i + 1]
                    prev_data = combined_df[combined_df['base_ym'] == prev_ym]
                    if not prev_data.empty and col_name in prev_data.columns:
                        prev_val = int(prev_data[col_name].sum())
                        if prev_val > 0:
                            row[f'rate_{ym}'] = round((val - prev_val) / prev_val * 100, 2)
        national_data.append(row)

    # 지역별 데이터 (시도별 집계)
    regional_data = {}
    regions = combined_df[combined_df['base_ym'] == base_ym_list[0]]['name'].unique()

    for region in regions:
        region_df = combined_df[combined_df['name'] == region]
        age_data = []

        # 합계 행
        total_row = {'age_group': '합계'}
        for i, ym in enumerate(base_ym_list):
            ym_data = region_df[region_df['base_ym'] == ym]
            if not ym_data.empty:
                total = int(ym_data['single_total'].iloc[0]) if 'single_total' in ym_data.columns else 0
                total_row[f'pop_{ym}'] = total
                if i < len(base_ym_list) - 1:
                    prev_ym = base_ym_list[i + 1]
                    prev_data = region_df[region_df['base_ym'] == prev_ym]
                    if not prev_data.empty:
                        prev_total = int(prev_data['single_total'].iloc[0])
                        if prev_total > 0:
                            total_row[f'rate_{ym}'] = round((total - prev_total) / prev_total * 100, 2)
        age_data.append(total_row)

        # 각 연령그룹
        for code_name, col_name in age_group_names:
            row = {'age_group': code_name}
            for i, ym in enumerate(base_ym_list):
                ym_data = region_df[region_df['base_ym'] == ym]
                if not ym_data.empty and col_name in ym_data.columns:
                    val = int(ym_data[col_name].iloc[0])
                    row[f'pop_{ym}'] = val
                    if i < len(base_ym_list) - 1:
                        prev_ym = base_ym_list[i + 1]
                        prev_data = region_df[region_df['base_ym'] == prev_ym]
                        if not prev_data.empty and col_name in prev_data.columns:
                            prev_val = int(prev_data[col_name].iloc[0])
                            if prev_val > 0:
                                row[f'rate_{ym}'] = round((val - prev_val) / prev_val * 100, 2)
            age_data.append(row)

        regional_data[region] = {'age_data': age_data}

    return {'data': national_data, 'regional_data': regional_data}


def get_household_indicator_table(base_ym_list, indicator, aggregate_type='sido', sido=None, include_sub_sigungu=False):
    """
    세대지표 테이블 조회

    Args:
        indicator: 지표 정보 dict (column_name, display_name, ...)

    numerator/denominator 컬럼으로 직접 계산 (multiplier 적용)
    """
    engine = get_db_engine()
    display_name = indicator['display_name']
    description = indicator.get('description', '')
    numerator = indicator.get('numerator', 'single_cnt')
    denominator = indicator.get('denominator', 'household_cnt')
    multiplier = indicator.get('multiplier', 100)
    decimal_places = indicator.get('decimal_places', 2)

    results = []

    for ym in base_ym_list:
        if aggregate_type == 'region':
            # 권역별 - numerator/denominator로 직접 계산
            df = pd.read_sql(f"""
                SELECT
                    d.region_nm as name,
                    d.region_code,
                    SUM(COALESCE(c.{numerator}, 0)) as numerator_value,
                    SUM(COALESCE(c.{denominator}, 0)) as denominator_value,
                    ROUND(
                        SUM(COALESCE(c.{numerator}, 0))::numeric / NULLIF(SUM(COALESCE(c.{denominator}, 0)), 0) * {multiplier},
                        {decimal_places}
                    ) as indicator_value
                FROM cache_sigungu_indicators c
                JOIN (
                    SELECT DISTINCT sigungu_code, region_nm, region_code
                    FROM dim_admin_area
                    WHERE region_nm IS NOT NULL
                ) d ON c.sigungu_code = d.sigungu_code
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                GROUP BY d.region_nm, d.region_code
                ORDER BY d.region_code
            """, engine)
        elif aggregate_type == 'sigungu' and sido:
            # 시군구별 (캐시 테이블은 이미 정규화된 시도명 사용)
            sido_cond = f"c.sido_nm = '{sido}'"

            if include_sub_sigungu:
                # 하위 시군구 포함
                df = pd.read_sql(f"""
                    SELECT
                        c.sigungu_code,
                        c.sigungu_nm as name,
                        COALESCE(c.{numerator}, 0) as numerator_value,
                        COALESCE(c.{denominator}, 0) as denominator_value,
                        ROUND(
                            COALESCE(c.{numerator}, 0)::numeric / NULLIF(COALESCE(c.{denominator}, 0), 0) * {multiplier},
                            {decimal_places}
                        ) as indicator_value
                    FROM cache_sigungu_indicators c
                    WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                      AND {sido_cond}
                    ORDER BY c.sigungu_code
                """, engine)
            else:
                # 4자리 그룹화 (마지막자리 0)
                df = pd.read_sql(f"""
                    SELECT
                        LEFT(c.sigungu_code, 4) || '0' as sigungu_code,
                        MIN(CASE WHEN c.sigungu_code LIKE '____0' THEN c.sigungu_nm
                            ELSE REGEXP_REPLACE(c.sigungu_nm, ' .*$', '') END) as name,
                        SUM(COALESCE(c.{numerator}, 0)) as numerator_value,
                        SUM(COALESCE(c.{denominator}, 0)) as denominator_value,
                        ROUND(
                            SUM(COALESCE(c.{numerator}, 0))::numeric / NULLIF(SUM(COALESCE(c.{denominator}, 0)), 0) * {multiplier},
                            {decimal_places}
                        ) as indicator_value
                    FROM cache_sigungu_indicators c
                    WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                      AND {sido_cond}
                    GROUP BY LEFT(c.sigungu_code, 4)
                    ORDER BY LEFT(c.sigungu_code, 4) || '0'
                """, engine)
        else:
            # 시도별 (sido_alias 사용 - 2자리 축약명)
            df = pd.read_sql(f"""
                SELECT
                    c.sido_alias as name,
                    MIN(LEFT(c.sigungu_code, 2)) as sido_code,
                    SUM(COALESCE(c.{numerator}, 0)) as numerator_value,
                    SUM(COALESCE(c.{denominator}, 0)) as denominator_value,
                    ROUND(
                        SUM(COALESCE(c.{numerator}, 0))::numeric / NULLIF(SUM(COALESCE(c.{denominator}, 0)), 0) * {multiplier},
                        {decimal_places}
                    ) as indicator_value
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                GROUP BY c.sido_alias
                ORDER BY MIN(LEFT(c.sigungu_code, 2))
            """, engine)

        df['base_ym'] = ym
        results.append(df)

    if not results:
        return {'title': display_name, 'description': description, 'data': []}

    combined_df = pd.concat(results, ignore_index=True)

    if combined_df.empty:
        return {'title': display_name, 'description': description, 'data': []}

    # 컬럼명 한글 라벨 조회
    column_labels = get_column_name_labels_local()
    numerator_label = column_labels.get(numerator, numerator)
    denominator_label = column_labels.get(denominator, denominator)

    # 피벗
    if 'sido_code' in combined_df.columns:
        pivot_value = combined_df.pivot(index='sido_code', columns='base_ym', values='indicator_value').fillna(0)
        pivot_numer = combined_df.pivot(index='sido_code', columns='base_ym', values='numerator_value').fillna(0)
        pivot_denom = combined_df.pivot(index='sido_code', columns='base_ym', values='denominator_value').fillna(0)
        pivot_value = pivot_value.sort_index()
        pivot_numer = pivot_numer.sort_index()
        pivot_denom = pivot_denom.sort_index()
        code_to_name = combined_df.drop_duplicates('sido_code').set_index('sido_code')['name'].to_dict()
    elif 'region_code' in combined_df.columns:
        pivot_value = combined_df.pivot(index='region_code', columns='base_ym', values='indicator_value').fillna(0)
        pivot_numer = combined_df.pivot(index='region_code', columns='base_ym', values='numerator_value').fillna(0)
        pivot_denom = combined_df.pivot(index='region_code', columns='base_ym', values='denominator_value').fillna(0)
        pivot_value = pivot_value.sort_index()
        pivot_numer = pivot_numer.sort_index()
        pivot_denom = pivot_denom.sort_index()
        code_to_name = combined_df.drop_duplicates('region_code').set_index('region_code')['name'].to_dict()
    elif 'sigungu_code' in combined_df.columns:
        pivot_value = combined_df.pivot(index='sigungu_code', columns='base_ym', values='indicator_value').fillna(0)
        pivot_numer = combined_df.pivot(index='sigungu_code', columns='base_ym', values='numerator_value').fillna(0)
        pivot_denom = combined_df.pivot(index='sigungu_code', columns='base_ym', values='denominator_value').fillna(0)
        code_to_name = combined_df.drop_duplicates('sigungu_code').set_index('sigungu_code')['name'].to_dict()
    else:
        pivot_value = combined_df.pivot(index='name', columns='base_ym', values='indicator_value').fillna(0)
        pivot_numer = combined_df.pivot(index='name', columns='base_ym', values='numerator_value').fillna(0)
        pivot_denom = combined_df.pivot(index='name', columns='base_ym', values='denominator_value').fillna(0)
        code_to_name = None

    data = []

    # 전국 합계 - 가중평균 계산
    total_row = {'name': '전국' if aggregate_type != 'sigungu' else '합계'}
    for i, ym in enumerate(base_ym_list):
        if ym in pivot_value.columns:
            # 가중평균: sum(indicator * denom) / sum(denom)
            total_numer = int(pivot_numer[ym].sum())
            total_denom = int(pivot_denom[ym].sum())
            weighted_sum = (pivot_value[ym] * pivot_denom[ym]).sum()
            weighted_avg = round(weighted_sum / total_denom, 2) if total_denom > 0 else 0
            total_row[f'value_{ym}'] = weighted_avg
            total_row[f'numer_{ym}'] = total_numer
            total_row[f'denom_{ym}'] = total_denom

            if i < len(base_ym_list) - 1 and base_ym_list[i+1] in pivot_value.columns:
                prev_ym = base_ym_list[i+1]
                prev_denom = pivot_denom[prev_ym].sum()
                prev_weighted = (pivot_value[prev_ym] * pivot_denom[prev_ym]).sum()
                prev_val = round(prev_weighted / prev_denom, 2) if prev_denom > 0 else 0
                total_row[f'change_{ym}'] = round(total_row[f'value_{ym}'] - prev_val, 2)
    data.append(total_row)

    # 각 지역 행
    for idx in pivot_value.index:
        name = code_to_name.get(idx, idx) if code_to_name else idx
        row = {'name': name}

        for i, ym in enumerate(base_ym_list):
            if ym in pivot_value.columns:
                row[f'value_{ym}'] = float(pivot_value.loc[idx, ym]) if pd.notna(pivot_value.loc[idx, ym]) else 0
                row[f'numer_{ym}'] = int(pivot_numer.loc[idx, ym]) if pd.notna(pivot_numer.loc[idx, ym]) else 0
                row[f'denom_{ym}'] = int(pivot_denom.loc[idx, ym]) if pd.notna(pivot_denom.loc[idx, ym]) else 0

                if i < len(base_ym_list) - 1 and base_ym_list[i+1] in pivot_value.columns:
                    prev_val = float(pivot_value.loc[idx, base_ym_list[i+1]]) if pd.notna(pivot_value.loc[idx, base_ym_list[i+1]]) else 0
                    row[f'change_{ym}'] = round(row[f'value_{ym}'] - prev_val, 2)

        data.append(row)

    return {
        'title': display_name,
        'description': description,
        'numerator_label': numerator_label,
        'denominator_label': denominator_label,
        'data': data
    }


# =============================================================================
# 차트 생성 함수
# =============================================================================

def add_bar_labels(ax, bars, values, is_horizontal=False, fontsize=8, format_str='{:.1f}', offset=0.3):
    """막대 차트에 레이블 추가"""
    for bar, val in zip(bars, values):
        if val == 0:
            continue
        if is_horizontal:
            ax.text(bar.get_width() + offset, bar.get_y() + bar.get_height() / 2,
                    format_str.format(val), va='center', ha='left', fontsize=fontsize, fontweight='bold')
        else:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + offset,
                    format_str.format(val), va='bottom', ha='center', fontsize=fontsize, fontweight='bold')


def create_household_chart(data, ym_list):
    """가구 현황 차트"""
    if not data or not data.get('data') or len(data['data']) < 2:
        return None

    try:
        rows = data['data'][1:]  # 전국 제외
        labels = [r.get('name', '') for r in rows]
        num_items = len(labels)

        colors = ['#1D64F2', '#F24822', '#10b981', '#f59e0b', '#8b5cf6']
        unit_val = HOUSEHOLD_UNIT['unit']
        unit_label = HOUSEHOLD_UNIT['label']
        unit_format = HOUSEHOLD_UNIT['format']

        # 10개 이상이면 가로 막대
        if num_items >= 10:
            fig_height = max(6, num_items * 0.35)
            fig, ax = plt.subplots(figsize=(10, fig_height))

            y = np.arange(len(labels))
            width = 0.8 / len(ym_list)

            for i, ym in enumerate(ym_list):
                values = [r.get(f'household_{ym}', 0) / unit_val for r in rows]
                bars = ax.barh(y + i * width - (len(ym_list) - 1) * width / 2, values,
                       width, label=f'{ym[:4]}.{ym[4:]}', color=colors[i % len(colors)])
                if i == 0:
                    add_bar_labels(ax, bars, values, is_horizontal=True, format_str=unit_format, offset=0.5)

            ax.set_ylabel('지역')
            ax.set_xlabel(f'가구수 ({unit_label})')
            ax.set_yticks(y)
            ax.set_yticklabels(labels)
            ax.legend(loc='lower right')
            ax.grid(axis='x', alpha=0.3)
            ax.invert_yaxis()
        else:
            fig, ax = plt.subplots(figsize=(12, 5))

            x = np.arange(len(labels))
            width = 0.8 / len(ym_list)

            for i, ym in enumerate(ym_list):
                values = [r.get(f'household_{ym}', 0) / unit_val for r in rows]
                bars = ax.bar(x + i * width - (len(ym_list) - 1) * width / 2, values,
                       width, label=f'{ym[:4]}.{ym[4:]}', color=colors[i % len(colors)])
                if i == 0:
                    add_bar_labels(ax, bars, values, is_horizontal=False, format_str=unit_format, offset=0.5)

            ax.set_xlabel('지역')
            ax.set_ylabel(f'가구수 ({unit_label})')
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.legend(loc='upper right')
            ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return img_base64
    except Exception as e:
        print(f"Household chart error: {e}")
        return None


def create_single_age_chart(data, ym_list):
    """연령별 1인가구 차트 (전국 + 지역별 서브플롯)"""
    if not data or not data.get('data') or len(data['data']) < 2:
        return None

    try:
        # 전국 데이터 차트
        rows = data['data'][1:]  # 합계 제외
        labels = [r.get('age_group', '') for r in rows]

        fig, ax = plt.subplots(figsize=(14, 6))
        colors = ['#1D64F2', '#F24822', '#10b981', '#f59e0b', '#8b5cf6']
        unit_val = SINGLE_AGE_UNIT['unit']
        unit_label = SINGLE_AGE_UNIT['label']
        unit_format = SINGLE_AGE_UNIT['format']

        x = np.arange(len(labels))
        width = 0.8 / len(ym_list)

        for i, ym in enumerate(ym_list):
            values = [r.get(f'pop_{ym}', 0) / unit_val for r in rows]
            bars = ax.bar(x + i * width - (len(ym_list) - 1) * width / 2, values,
                   width, label=f'{ym[:4]}.{ym[4:]}', color=colors[i % len(colors)])
            if i == 0:
                add_bar_labels(ax, bars, values, is_horizontal=False, format_str=unit_format, offset=0.3)

        ax.set_xlabel('연령대')
        ax.set_ylabel(f'1인가구 수 ({unit_label})')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.legend(loc='upper right')
        ax.grid(axis='y', alpha=0.3)
        ax.set_title('전국 연령별 1인가구 현황', fontsize=12, fontweight='bold')

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return img_base64
    except Exception as e:
        print(f"Single age chart error: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_single_age_regional_chart(data, ym_list):
    """지역별 연령대별 1인가구 서브플롯"""
    regional_data = data.get('regional_data', {})
    if not regional_data:
        return None

    try:
        # 설정에서 가져오기
        max_regions = REGIONAL_SUBPLOT.get('max_regions')  # None이면 전체
        ncols_config = REGIONAL_SUBPLOT.get('cols', 4)
        fig_w = REGIONAL_SUBPLOT.get('fig_width_per_col', 4)
        fig_h = REGIONAL_SUBPLOT.get('fig_height_per_row', 3.5)
        unit_val = SINGLE_AGE_UNIT['unit']

        # 전체 지역 또는 max_regions 개수만큼
        regions = list(regional_data.keys())
        if max_regions is not None:
            regions = regions[:max_regions]
        n_regions = len(regions)
        if n_regions == 0:
            return None

        ncols = min(ncols_config, n_regions)
        nrows = (n_regions + ncols - 1) // ncols

        fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * fig_w, nrows * fig_h))
        if n_regions == 1:
            axes = np.array([axes])
        axes = axes.flatten()

        colors = ['#1D64F2', '#F24822', '#10b981', '#f59e0b', '#8b5cf6']

        for idx, region in enumerate(regions):
            ax = axes[idx]
            region_info = regional_data[region]
            age_data = region_info.get('age_data', [])

            if len(age_data) < 2:
                ax.text(0.5, 0.5, '데이터 없음', ha='center', va='center', transform=ax.transAxes)
                ax.set_title(region, fontsize=10, fontweight='bold')
                continue

            rows = age_data[1:]  # 합계 제외
            labels = [r.get('age_group', '')[:5] for r in rows]  # 라벨 축약
            x = np.arange(len(labels))
            width = 0.8 / len(ym_list)

            for i, ym in enumerate(ym_list):
                values = [r.get(f'pop_{ym}', 0) / unit_val for r in rows]
                ax.bar(x + i * width - (len(ym_list) - 1) * width / 2, values,
                       width, label=f'{ym[:4]}.{ym[4:]}' if idx == 0 else '', color=colors[i % len(colors)])

            ax.set_title(region, fontsize=10, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
            ax.grid(axis='y', alpha=0.3)

        # 남은 빈 축 숨기기
        for idx in range(n_regions, len(axes)):
            axes[idx].set_visible(False)

        # 범례 (첫 번째 축에서)
        handles, labels_legend = axes[0].get_legend_handles_labels()
        if handles:
            fig.legend(handles, [f'{ym[:4]}.{ym[4:]}' for ym in ym_list],
                      loc='upper right', bbox_to_anchor=(0.99, 0.99))

        plt.tight_layout(rect=[0, 0, 0.95, 1])

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return img_base64
    except Exception as e:
        print(f"Regional single age chart error: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_indicator_chart(data, ym_list, indicator_name):
    """세대지표 차트"""
    if not data or not data.get('data') or len(data['data']) < 2:
        return None

    try:
        rows = data['data'][1:]  # 전국 제외
        labels = [r.get('name', '') for r in rows]
        num_items = len(labels)

        colors = ['#1D64F2', '#F24822', '#10b981', '#f59e0b', '#8b5cf6']

        # 가로 막대 그래프
        fig_height = max(6, num_items * 0.35)
        fig, ax = plt.subplots(figsize=(10, fig_height))

        y = np.arange(len(labels))
        width = 0.8 / len(ym_list)

        for i, ym in enumerate(ym_list):
            values = [r.get(f'value_{ym}', 0) for r in rows]
            bars = ax.barh(y + i * width - (len(ym_list) - 1) * width / 2, values,
                   width, label=f'{ym[:4]}.{ym[4:]}', color=colors[i % len(colors)])
            if i == 0:
                add_bar_labels(ax, bars, values, is_horizontal=True, format_str='{:.1f}', offset=0.3)

        ax.set_ylabel('지역')
        ax.set_xlabel(indicator_name)
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.legend(loc='lower right')
        ax.grid(axis='x', alpha=0.3)
        ax.invert_yaxis()

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return img_base64
    except Exception as e:
        print(f"Indicator chart error: {e}")
        return None


# =============================================================================
# 테이블 HTML 생성
# =============================================================================

def create_household_table_html(data, ym_list):
    """가구 현황 테이블 HTML"""
    if not data or not data.get('data'):
        return '<p class="text-muted">데이터가 없습니다.</p>'

    rows = data['data']

    html = ['<table class="data-table sortable-table">']

    # 헤더 1행: 년월
    html.append('<thead>')
    html.append('<tr>')
    html.append('<th rowspan="2" style="background:#1243A6;">지역</th>')
    for i, ym in enumerate(ym_list):
        divider = ' class="divider"' if i > 0 else ''
        html.append(f'<th colspan="4"{divider} class="year-header">{ym[:4]}년 {ym[4:]}월</th>')
    html.append('</tr>')

    # 헤더 2행: 지표
    html.append('<tr>')
    for i, ym in enumerate(ym_list):
        divider = ' divider' if i > 0 else ''
        html.append(f'<th class="metric-header{divider}">전체가구</th>')
        html.append(f'<th class="metric-header">1인가구</th>')
        html.append(f'<th class="metric-header">1인비율</th>')
        html.append(f'<th class="metric-header">증감률</th>')
    html.append('</tr>')
    html.append('</thead>')

    # 바디
    html.append('<tbody>')
    for row in rows:
        html.append('<tr>')
        html.append(f'<td>{row.get("name", "")}</td>')

        for i, ym in enumerate(ym_list):
            divider = ' class="divider"' if i > 0 else ''

            household = row.get(f'household_{ym}', 0)
            single = row.get(f'single_{ym}', 0)
            ratio = row.get(f'single_ratio_{ym}', 0)
            rate = row.get(f'household_rate_{ym}', None)

            html.append(f'<td{divider}>{household:,}</td>')
            html.append(f'<td>{single:,}</td>')
            html.append(f'<td>{ratio:.1f}%</td>')

            if rate is not None:
                css = 'positive' if rate > 0 else 'negative' if rate < 0 else ''
                html.append(f'<td class="{css}">{rate:.2f}%</td>')
            else:
                html.append('<td>-</td>')

        html.append('</tr>')
    html.append('</tbody>')
    html.append('</table>')

    return '\n'.join(html)


def create_single_age_table_html(data, ym_list):
    """연령별 1인가구 테이블 HTML (전국 + 지역별)"""
    if not data or not data.get('data'):
        return '<p class="text-muted">데이터가 없습니다.</p>'

    html = []

    # 전국 테이블
    html.append('<h6 class="mt-3 mb-2" style="font-weight:bold;">전국</h6>')
    html.append(_create_age_table(data['data'], ym_list))

    # 지역별 테이블
    regional_data = data.get('regional_data', {})
    if regional_data:
        expand_all = ACCORDION_TABLE.get('expand_all', True)

        # expand_all이면 data-bs-parent 제거 (각 아코디언 독립적으로 열림)
        parent_attr = '' if expand_all else 'data-bs-parent="#singleAgeRegionAccordion"'

        html.append('<h6 class="mt-4 mb-2" style="font-weight:bold;">지역별</h6>')
        html.append('<div class="accordion" id="singleAgeRegionAccordion">')

        for idx, (region, region_info) in enumerate(regional_data.items()):
            age_data = region_info.get('age_data', [])

            # 설정에 따라 전체 펼침 또는 첫 번째만 펼침
            if expand_all:
                collapsed = ''
                show = 'show'
                expanded = 'true'
            else:
                collapsed = '' if idx == 0 else 'collapsed'
                show = 'show' if idx == 0 else ''
                expanded = 'true' if idx == 0 else 'false'

            html.append(f'''
            <div class="accordion-item">
                <h2 class="accordion-header">
                    <button class="accordion-button {collapsed}" type="button" data-bs-toggle="collapse"
                            data-bs-target="#singleAge{idx}" aria-expanded="{expanded}">
                        {region}
                    </button>
                </h2>
                <div id="singleAge{idx}" class="accordion-collapse collapse {show}"
                     {parent_attr}>
                    <div class="accordion-body">
                        {_create_age_table(age_data, ym_list)}
                    </div>
                </div>
            </div>
            ''')

        html.append('</div>')

    return '\n'.join(html)


def _create_age_table(rows, ym_list):
    """연령별 테이블 생성 헬퍼"""
    if not rows:
        return '<p class="text-muted">데이터가 없습니다.</p>'

    html = ['<table class="data-table sortable-table">']

    # 헤더 1행
    html.append('<thead>')
    html.append('<tr>')
    html.append('<th rowspan="2" style="background:#4a5568;">연령대</th>')
    for i, ym in enumerate(ym_list):
        colspan = 2 if i < len(ym_list) - 1 else 1
        divider = ' class="divider"' if i > 0 else ''
        html.append(f'<th colspan="{colspan}"{divider} class="year-header">{ym[:4]}년 {ym[4:]}월</th>')
    html.append('</tr>')

    # 헤더 2행
    html.append('<tr>')
    for i, ym in enumerate(ym_list):
        divider = ' divider' if i > 0 else ''
        html.append(f'<th class="metric-header{divider}">1인가구</th>')
        if i < len(ym_list) - 1:
            html.append(f'<th class="metric-header">증감률</th>')
    html.append('</tr>')
    html.append('</thead>')

    # 바디
    html.append('<tbody>')
    for row in rows:
        html.append('<tr>')
        html.append(f'<td>{row.get("age_group", "")}</td>')

        for i, ym in enumerate(ym_list):
            divider = ' class="divider"' if i > 0 else ''

            pop = row.get(f'pop_{ym}', 0)
            rate = row.get(f'rate_{ym}', None)

            html.append(f'<td{divider}>{pop:,}</td>')

            if i < len(ym_list) - 1:
                if rate is not None:
                    css = 'positive' if rate > 0 else 'negative' if rate < 0 else ''
                    html.append(f'<td class="{css}">{rate:.2f}%</td>')
                else:
                    html.append('<td>-</td>')

        html.append('</tr>')
    html.append('</tbody>')
    html.append('</table>')

    return '\n'.join(html)


def create_indicator_table_html(data, ym_list):
    """세대지표 테이블 HTML (분자/분모 값 포함)"""
    if not data or not data.get('data'):
        return '<p class="text-muted">데이터가 없습니다.</p>'

    rows = data['data']
    numerator_label = data.get('numerator_label', '분자')
    denominator_label = data.get('denominator_label', '분모')

    html = ['<table class="data-table sortable-table">']

    # 헤더 1행
    html.append('<thead>')
    html.append('<tr>')
    html.append('<th rowspan="2" style="background:#4a5568;">지역</th>')
    for i, ym in enumerate(ym_list):
        # 지표값 + 분자 + 분모 + 증감(마지막 제외) = 4개 or 3개
        colspan = 4 if i < len(ym_list) - 1 else 3
        divider = ' class="divider"' if i > 0 else ''
        html.append(f'<th colspan="{colspan}"{divider} class="year-header">{ym[:4]}년 {ym[4:]}월</th>')
    html.append('</tr>')

    # 헤더 2행
    html.append('<tr>')
    for i, ym in enumerate(ym_list):
        divider = ' divider' if i > 0 else ''
        html.append(f'<th class="metric-header{divider}">지표값</th>')
        html.append(f'<th class="metric-header" >{numerator_label}</th>')
        html.append(f'<th class="metric-header" >{denominator_label}</th>')
        if i < len(ym_list) - 1:
            html.append(f'<th class="metric-header">증감</th>')
    html.append('</tr>')
    html.append('</thead>')

    # 바디
    html.append('<tbody>')
    for row in rows:
        html.append('<tr>')
        html.append(f'<td>{row.get("name", "")}</td>')

        for i, ym in enumerate(ym_list):
            divider = ' class="divider"' if i > 0 else ''

            value = row.get(f'value_{ym}', 0)
            numer = row.get(f'numer_{ym}', 0)
            denom = row.get(f'denom_{ym}', 0)
            change = row.get(f'change_{ym}', None)

            html.append(f'<td{divider}>{value:.2f}%</td>')
            html.append(f'<td >{numer:,}</td>')
            html.append(f'<td >{denom:,}</td>')

            if i < len(ym_list) - 1:
                if change is not None:
                    css = 'positive' if change > 0 else 'negative' if change < 0 else ''
                    html.append(f'<td class="{css}">{change:+.2f}%p</td>')
                else:
                    html.append('<td>-</td>')

        html.append('</tr>')
    html.append('</tbody>')
    html.append('</table>')

    return '\n'.join(html)


# =============================================================================
# 메인 렌더링 함수
# =============================================================================

def generate_dashboard_html(request_args):
    """대시보드 HTML 생성"""
    # 파라미터 파싱
    base_ym_str = request_args.get('base_ym_list', '')
    base_ym_list = sorted([ym.strip() for ym in base_ym_str.split(',') if ym.strip()], reverse=True)
    age_category = int(request_args.get('age_category', 1))  # 기본: 5세별
    aggregate_type = request_args.get('aggregate_type', 'sido')
    sido = request_args.get('sido', '')
    active_tab = request_args.get('active_tab', 'household')
    include_sub_sigungu = request_args.get('include_sub_sigungu', '0') == '1'

    # 필터 옵션
    filters = get_filter_options()

    # 초기 접속 시 - 요약 데이터 표시
    if not base_ym_list:
        # 12월 데이터 중 최신 2개만 선택 (최신년월, 전년도년월)
        dec_list = sorted([ym for ym in filters['base_ym_list'] if ym.endswith('12')], reverse=True)
        default_ym_list = dec_list[:2] if len(dec_list) >= 2 else sorted(filters['base_ym_list'], reverse=True)[:2]

        menu_items = MenuGenerator.get_category_menu_items(POP_BASE, '01_인구및가구현황')

        # 초기 화면용 요약 테이블 생성 (시도별 주요 지표)
        initial_summary_html = generate_initial_summary_table()

        template = jinja_env.get_template('edu_dash9.html')
        return template.render(
            filters=filters,
            selected_ym_list=default_ym_list,
            selected_age_category=age_category,
            aggregate_type=aggregate_type,
            selected_sido=sido,
            active_tab=active_tab,
            include_sub_sigungu=include_sub_sigungu,
            menu_items=menu_items,
            current_url=CURRENT_URL,
            # 초기 화면: 요약 테이블만 표시
            household_chart_img=None,
            single_age_chart_img=None,
            single_age_regional_chart_img=None,
            household_table_html=initial_summary_html,  # 시도별 요약 테이블 표시
            single_age_table_html='<p class="text-muted text-center py-5">연령별 1인가구 데이터는 조회 버튼을 클릭하세요.</p>',
            indicator_tabs=[{
                'id': ind['column_name'],
                'name': ind['display_name'],
                'description': ind.get('description', ''),
                'chart_img': None,
                'table_html': '<p class="text-muted text-center py-5">조회 버튼을 클릭하여 데이터를 불러오세요.</p>',
            } for ind in filters.get('active_indicators', [])],
            is_initial_load=True
        )

    # 데이터 조회
    household_data = get_household_table(base_ym_list, aggregate_type, None, sido, include_sub_sigungu)
    single_age_data = get_single_by_age_table(base_ym_list, age_category, aggregate_type, sido)

    # 차트 생성
    household_chart_img = create_household_chart(household_data, base_ym_list)
    single_age_chart_img = create_single_age_chart(single_age_data, base_ym_list)
    single_age_regional_chart_img = create_single_age_regional_chart(single_age_data, base_ym_list)

    # 테이블 HTML
    household_table_html = create_household_table_html(household_data, base_ym_list)
    single_age_table_html = create_single_age_table_html(single_age_data, base_ym_list)

    # 세대지표 탭
    active_indicators = filters.get('active_indicators', [])
    indicator_tabs = []

    for indicator in active_indicators:
        indicator_data = get_household_indicator_table(
            base_ym_list, indicator, aggregate_type, sido, include_sub_sigungu
        )
        indicator_chart = create_indicator_chart(indicator_data, base_ym_list, indicator['display_name'])
        indicator_table = create_indicator_table_html(indicator_data, base_ym_list)

        indicator_tabs.append({
            'id': indicator['column_name'],
            'name': indicator['display_name'],
            'description': indicator.get('description', ''),
            'chart_img': indicator_chart,
            'table_html': indicator_table,
        })

    # 메뉴 생성
    menu_items = MenuGenerator.get_category_menu_items(POP_BASE, '01_인구및가구현황')

    # 템플릿 렌더링
    template = jinja_env.get_template('edu_dash9.html')
    return template.render(
        filters=filters,
        selected_ym_list=base_ym_list,
        selected_age_category=age_category,
        aggregate_type=aggregate_type,
        selected_sido=sido,
        active_tab=active_tab,
        include_sub_sigungu=include_sub_sigungu,
        menu_items=menu_items,
        current_url=CURRENT_URL,
        # 데이터
        household_chart_img=household_chart_img,
        single_age_chart_img=single_age_chart_img,
        single_age_regional_chart_img=single_age_regional_chart_img,
        household_table_html=household_table_html,
        single_age_table_html=single_age_table_html,
        indicator_tabs=indicator_tabs,
        is_initial_load=False
    )


def handle_export(request_args):
    """내보내기 API 처리"""
    base_ym_str = request_args.get('base_ym_list', '')
    base_ym_list = sorted([ym.strip() for ym in base_ym_str.split(',') if ym.strip()], reverse=True)
    age_category = int(request_args.get('age_category', 1))
    aggregate_type = request_args.get('aggregate_type', 'sido')
    sido = request_args.get('sido', '')
    include_sub_sigungu = request_args.get('include_sub_sigungu', '0') == '1'

    # 정렬 파라미터
    sort_column = request_args.get('sort_column', '')
    sort_direction = request_args.get('sort_direction', 'asc')
    sort_config = {'column': sort_column, 'direction': sort_direction} if sort_column else None

    # 데이터 조회
    household_data = get_household_table(base_ym_list, aggregate_type, None, sido, include_sub_sigungu)
    single_age_data = get_single_by_age_table(base_ym_list, age_category, aggregate_type, sido)

    tables_data = {
        '가구현황': household_data,
        '연령별_1인가구': single_age_data,
    }

    # 차트 데이터
    charts_data = {
        '가구현황': create_household_chart(household_data, base_ym_list),
        '연령별_1인가구': create_single_age_chart(single_age_data, base_ym_list),
    }

    # 세대지표 데이터
    filters = get_filter_options()
    active_indicators = filters.get('active_indicators', [])

    for indicator in active_indicators:
        display_name = indicator['display_name'].replace(' ', '_')
        indicator_data = get_household_indicator_table(
            base_ym_list, indicator, aggregate_type, sido, include_sub_sigungu
        )
        tables_data[display_name] = indicator_data
        charts_data[display_name] = create_indicator_chart(
            indicator_data, base_ym_list, indicator['display_name']
        )

    # 출력 디렉토리
    output_dir = POP_BASE / 'output'
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    aggregate_str = aggregate_type
    sido_str = sido.replace(' ', '_') if sido else '전국'
    filename_base = f"가구세대지표_{aggregate_str}_{sido_str}_{timestamp}"

    # DataExporter 사용
    exporter = DataExporter(
        tables_data=tables_data,
        charts_data=charts_data,
        sort_config=sort_config,
        report_title="가구·세대 지표 보고서"
    )

    results = exporter.export_all(output_dir, filename_base)

    # 다운로드 링크 생성
    if results.get('success') and results.get('files'):
        download_links = []
        for file_path in results['files']:
            file_name = Path(file_path).name
            download_url = f"?api_type=download&file={file_name}"
            file_ext = Path(file_path).suffix.upper().replace('.', '')
            download_links.append({
                'name': file_name,
                'url': download_url,
                'type': file_ext
            })
        results['download_links'] = download_links

    return results


def handle_download(request_args):
    """파일 다운로드 API 처리"""
    file_name = request_args.get('file', '')
    if not file_name:
        return {'error': '파일명이 지정되지 않았습니다.'}

    output_dir = POP_BASE / 'output'
    file_path = output_dir / file_name

    if not file_path.exists():
        return {'error': f'파일을 찾을 수 없습니다: {file_name}'}

    # MIME 타입 결정
    ext = file_path.suffix.lower()
    mime_types = {
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.md': 'text/markdown',
        '.html': 'text/html',
    }
    mime_type = mime_types.get(ext, 'application/octet-stream')

    return send_file(
        file_path,
        mimetype=mime_type,
        as_attachment=True,
        download_name=file_name
    )


def render(request_args):
    """Flask 라우트 진입점"""
    api_type = request_args.get('api_type', '')

    # API 처리
    if api_type == 'export':
        return jsonify(handle_export(request_args))

    if api_type == 'download':
        return handle_download(request_args)

    # 기본: 대시보드 HTML 렌더링
    return generate_dashboard_html(request_args)
