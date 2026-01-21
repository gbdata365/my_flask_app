# -*- coding: utf-8 -*-
"""
================================================================================
연령대별 인구-1인가구 특이점 발견 대시보드 (edu_dash1.py)
================================================================================

[목적]
- 인구 변화와 1인가구 변화의 **차이(괴리)**를 탐지
- 예: 인구는 감소하는데 1인가구는 증가하는 지역 = 정책 우선 대상
- 연령대별 특이점 자동 발견
- 5개의 자동 생성 인사이트 제공

[기술 스택]
- Backend: Flask (Python)
- Frontend: Tailwind CSS + Plotly.js (클라이언트 차트) + DataTables
- Server-side Charts: matplotlib (이미지로 생성)
- Database: PostgreSQL

[주요 테이블]
1. cache_sigungu_indicators
   - 시군구별 인구/1인가구 지표 캐시 테이블
   - 컬럼: base_ym, sigungu_code, sigungu_nm, sido_nm, region_nm,
           total_pop, single_cnt, elderly_pop, pop_0_4~pop_100_over 등

2. dim_admin_area
   - 행정구역 마스터 테이블
   - 컬럼: sigungu_code, sigungu_nm, sido_code, sido_nm, region_code, region_nm

3. code_age_group
   - 연령 그룹 정의 테이블
   - 컬럼: category(1=5세별,2=10세별,3=정책연령), code_name, column_name 등

4. fact_single_household_by_age (선택적)
   - 연령별 1인가구 팩트 테이블
   - 컬럼: base_ym, admin_code, age, male_cnt, female_cnt

[시군구코드 규칙]
- 5자리: 앞2자리(시도) + 중간2자리(시군) + 마지막1자리(구분)
- 마지막 0: 대표 시군구, 1~9: 하위 구/읍면
- 예: 47110(경북포항시-대표), 47111(포항남구), 47113(포항북구)

[함수 흐름]
render() → api_type이 있으면 handle_api_request(), 없으면 generate_html()
handle_api_request() → api_type에 따라 각 데이터 조회/차트 생성 함수 호출

[문서 참조]
- 상세 아키텍처: edu_dash1_architecture.md
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

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_engine
from module.menu_generator import MenuGenerator
from flask import jsonify, Response

POP_BASE = Path(__file__).parent.parent


def get_filter_options():
    """
    ============================================================================
    필터 옵션 조회 (화면 초기 로드 시 사용)
    ============================================================================

    [역할]
    - 대시보드 화면의 필터 드롭다운에 표시할 옵션들을 조회
    - 페이지 최초 로드 시 한 번 호출됨

    [반환값]
    {
        'base_ym_list': ['202412', '202411', ...],  # 기준년월 목록 (내림차순)
        'sido_list': ['서울특별시', '경기도', ...],   # 시도 목록
        'region_list': ['동부권', '서부권', ...],    # 권역 목록 (경북 기준)
        'age_categories': [                         # 연령 카테고리
            {'category': 1, 'category_name': '5세별'},
            {'category': 2, 'category_name': '10세별'},
            {'category': 3, 'category_name': '정책연령'}
        ]
    }

    [사용되는 테이블]
    - cache_sigungu_indicators: 기준년월 목록
    - dim_admin_area: 시도/권역 목록
    - code_age_group: 연령 카테고리
    ============================================================================
    """
    engine = get_db_engine()

    # 기준년월 목록 (cache_sigungu_indicators에서)
    base_ym_df = pd.read_sql("""
        SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as base_ym
        FROM cache_sigungu_indicators
        ORDER BY base_ym DESC
    """, engine)

    # 시도 목록
    sido_df = pd.read_sql("""
        SELECT DISTINCT sido_nm, MIN(sido_code) as sort_key
        FROM dim_admin_area
        WHERE sido_nm IS NOT NULL
        GROUP BY sido_nm
        ORDER BY sort_key
    """, engine)

    # 권역 목록 (경상북도 기준)
    region_df = pd.read_sql("""
        SELECT DISTINCT region_nm, MIN(region_code) as sort_key
        FROM dim_admin_area
        WHERE region_nm IS NOT NULL
        GROUP BY region_nm
        ORDER BY sort_key
    """, engine)

    # 연령 그룹 카테고리 조회
    age_cat_df = pd.read_sql("""
        SELECT DISTINCT category, category_name
        FROM code_age_group
        WHERE is_active = TRUE
        ORDER BY category
    """, engine)

    return {
        'base_ym_list': base_ym_df['base_ym'].tolist(),
        'sido_list': sido_df['sido_nm'].tolist(),
        'region_list': region_df['region_nm'].tolist(),
        'age_categories': age_cat_df.to_dict('records')
    }


def get_age_groups_from_db(category=3):
    """연령 그룹 코드 DB에서 조회"""
    engine = get_db_engine()
    df = pd.read_sql(f"""
        SELECT code, code_name, column_name, age_start, age_end, sort_order
        FROM code_age_group
        WHERE category = {category}
          AND is_active = TRUE
        ORDER BY sort_order
    """, engine)
    return df


def get_regions_by_sido(sido_nm):
    """시도별 권역 목록 조회"""
    engine = get_db_engine()
    df = pd.read_sql("""
        SELECT DISTINCT region_code, region_nm
        FROM dim_admin_area
        WHERE sido_nm = %s
          AND region_nm IS NOT NULL
        ORDER BY region_code
    """, engine, params=(sido_nm,))
    return df.to_dict('records')


def get_sigungu_by_sido(sido_nm, region_nm=None, include_sub=False):
    """시도/권역별 시군구 목록 조회"""
    engine = get_db_engine()

    where_clauses = ["sido_nm = %s", "eupmyeondong_nm IS NULL"]
    params = [sido_nm]

    if region_nm:
        where_clauses.append("region_nm = %s")
        params.append(region_nm)

    if not include_sub:
        where_clauses.append("sigungu_code LIKE '____0'")

    where_sql = " AND ".join(where_clauses)

    df = pd.read_sql(f"""
        SELECT DISTINCT sigungu_code, sigungu_nm
        FROM dim_admin_area
        WHERE {where_sql}
        ORDER BY sigungu_code
    """, engine, params=params)
    return df.to_dict('records')


def get_summary_data(base_ym, compare_ym, sido=None, region_nm=None, sigungu_codes=None, sigungu_level='basic'):
    """
    ============================================================================
    요약 카드 데이터 조회 (api=summary)
    ============================================================================

    [역할]
    - 대시보드 상단 요약 카드에 표시할 핵심 지표 계산
    - 기준시점과 비교시점의 인구/1인가구 변화율 계산

    [매개변수]
    - base_ym: 기준년월 (예: '202412')
    - compare_ym: 비교년월 (예: '202312')
    - sido: 시도명 (예: '경상북도', 빈값이면 전국)
    - region_nm: 권역명 (예: '__all_regions__'이면 권역별 집계)
    - sigungu_codes: 시군구코드 목록 (현재 미사용)
    - sigungu_level: 'basic'(대표만) 또는 'detail'(하위포함)

    [반환값]
    {
        'total_pop': 51000000,       # 기준시점 총인구
        'pop_change_rate': -0.35,    # 인구변화율 (%)
        'single_cnt': 9500000,       # 기준시점 1인가구수
        'single_change_rate': 2.1,   # 1인가구변화율 (%)
        'elderly_ratio': 18.5,       # 고령화율 (65세이상/총인구*100)
        'single_ratio': 33.2         # 1인가구비율 (1인가구/총세대*100) - 현재 근사치
    }

    [주의사항]
    - 데이터가 없으면 모든 값이 0으로 반환됨
    - 기준년월/비교년월에 데이터가 있는지 먼저 확인 필요
    ============================================================================
    """
    engine = get_db_engine()

    where_clauses = ["1=1"]
    if sido:
        where_clauses.append(f"sido_nm = '{sido}'")
    if region_nm:
        where_clauses.append(f"sigungu_code IN (SELECT sigungu_code FROM dim_admin_area WHERE region_nm = '{region_nm}' AND eupmyeondong_nm IS NULL)")
    if sigungu_codes:
        codes_str = ",".join([f"'{c}'" for c in sigungu_codes])
        where_clauses.append(f"LEFT(sigungu_code, 4) IN ({codes_str})")

    where_sql = " AND ".join(where_clauses)

    # 기준 시점 데이터 (기본 모드: 4자리 그룹화)
    base_df = pd.read_sql(f"""
        SELECT
            SUM(total_pop) as total_pop,
            SUM(COALESCE(elderly_pop, 0)) as elderly_pop,
            SUM(COALESCE(single_cnt, 0)) as single_cnt
        FROM cache_sigungu_indicators
        WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}' AND {where_sql}
    """, engine)

    # 비교 시점 데이터
    compare_df = pd.read_sql(f"""
        SELECT
            SUM(total_pop) as total_pop,
            SUM(COALESCE(elderly_pop, 0)) as elderly_pop,
            SUM(COALESCE(single_cnt, 0)) as single_cnt
        FROM cache_sigungu_indicators
        WHERE TO_CHAR(base_ym, 'YYYYMM') = '{compare_ym}' AND {where_sql}
    """, engine)

    def safe_change_rate(current, previous):
        if previous and previous > 0:
            return round((current - previous) / previous * 100, 2)
        return 0

    base_pop = int(base_df['total_pop'].iloc[0] or 0)
    compare_pop = int(compare_df['total_pop'].iloc[0] or 0)
    base_single = int(base_df['single_cnt'].iloc[0] or 0)
    compare_single = int(compare_df['single_cnt'].iloc[0] or 0)
    base_elderly = int(base_df['elderly_pop'].iloc[0] or 0)

    # 비율 계산
    elderly_ratio = round(base_elderly / base_pop * 100, 1) if base_pop > 0 else 0
    single_ratio = round(base_single / base_pop * 100, 1) if base_pop > 0 else 0

    return {
        'total_pop': base_pop,
        'pop_change_rate': safe_change_rate(base_pop, compare_pop),
        'single_cnt': base_single,
        'single_change_rate': safe_change_rate(base_single, compare_single),
        'elderly_ratio': elderly_ratio,
        'single_ratio': single_ratio,
        'base_ym': base_ym,
        'compare_ym': compare_ym
    }


def get_age_group_change(base_ym, compare_ym, sido=None, region_nm=None, sigungu_codes=None, sigungu_level='basic', age_category=3):
    """
    ============================================================================
    연령대별 인구 변화율 데이터 조회 (api=age_change, api=bar_chart에서 사용)
    ============================================================================

    [역할]
    - 연령그룹별 인구 변화율 계산
    - code_age_group 테이블에서 연령그룹 정의를 동적으로 조회
    - 연령 카테고리에 따라 다른 컬럼 사용

    [매개변수]
    - age_category: 1(5세별), 2(10세별), 3(정책연령)

    [처리 흐름]
    1. get_age_groups_from_db(age_category) 호출
       → code_age_group에서 해당 카테고리의 연령그룹 정보 조회
       → 반환: code_name(레이블), column_name(컬럼명), age_start/end

    2. 각 연령그룹별로 기준/비교 시점 인구수 조회
       → cache_sigungu_indicators의 해당 컬럼(예: pop_0_4) 합계

    3. 변화율 계산: (기준값 - 비교값) / 비교값 * 100

    [반환값]
    [
        {'age_group': '0-4세', 'base_value': 1000, 'compare_value': 1100,
         'change': -100, 'change_rate': -9.09},
        {'age_group': '5-9세', ...},
        ...
    ]

    [연령 카테고리별 컬럼 예시]
    - category=1 (5세별): pop_0_4, pop_5_9, pop_10_14, ... (21개)
    - category=2 (10세별): pop_under10, pop_10s, pop_20s_early, ... (15개)
    - category=3 (정책연령): preschool_pop, elementary_pop, ... (15개)
    ============================================================================
    """
    engine = get_db_engine()

    where_clauses = ["1=1"]
    if sido:
        where_clauses.append(f"sido_nm = '{sido}'")
    if sigungu_level == 'basic':
        where_clauses.append("sigungu_code LIKE '____0'")

    where_sql = " AND ".join(where_clauses)

    # DB에서 연령그룹 조회
    age_groups = get_age_groups_from_db(age_category)

    results = []
    for _, grp in age_groups.iterrows():
        col = grp['column_name']
        label = grp['code_name']

        try:
            base_df = pd.read_sql(f"""
                SELECT SUM(COALESCE({col}, 0)) as val
                FROM cache_sigungu_indicators
                WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}' AND {where_sql}
            """, engine)

            compare_df = pd.read_sql(f"""
                SELECT SUM(COALESCE({col}, 0)) as val
                FROM cache_sigungu_indicators
                WHERE TO_CHAR(base_ym, 'YYYYMM') = '{compare_ym}' AND {where_sql}
            """, engine)

            base_val = float(base_df['val'].iloc[0] or 0)
            compare_val = float(compare_df['val'].iloc[0] or 0)

            change_rate = round((base_val - compare_val) / compare_val * 100, 2) if compare_val > 0 else 0

            results.append({
                'age_group': label,
                'column': col,
                'base_value': base_val,
                'compare_value': compare_val,
                'change': base_val - compare_val,
                'change_rate': change_rate
            })
        except Exception:
            continue

    return results


def get_age_group_single_household(base_ym, compare_ym, sido=None, region_nm=None, sigungu_level='basic', age_category=3):
    """연령대별 1인가구 변화율 데이터 - fact_single_household_by_age에서 조회"""
    engine = get_db_engine()

    # DB에서 연령그룹 조회
    age_groups = get_age_groups_from_db(age_category)

    # 지역 필터 구성
    where_clauses = ["1=1"]
    if sido:
        where_clauses.append(f"d.sido_nm = '{sido}'")
    if sigungu_level == 'basic':
        where_clauses.append("LEFT(s.admin_code, 5) LIKE '____0'")

    where_sql = " AND ".join(where_clauses)

    results = []
    for _, grp in age_groups.iterrows():
        age_start = int(grp.get('age_start', 0))
        age_end = int(grp.get('age_end', 100))
        label = grp['code_name']

        try:
            # 기준시점 데이터
            base_df = pd.read_sql(f"""
                SELECT COALESCE(SUM(s.male_cnt + s.female_cnt), 0) as val
                FROM fact_single_household_by_age s
                JOIN dim_admin_area d ON LEFT(s.admin_code, 5) = d.sigungu_code
                WHERE TO_CHAR(s.base_ym, 'YYYYMM') = '{base_ym}'
                  AND s.age BETWEEN {age_start} AND {age_end}
                  AND {where_sql}
            """, engine)

            # 비교시점 데이터
            compare_df = pd.read_sql(f"""
                SELECT COALESCE(SUM(s.male_cnt + s.female_cnt), 0) as val
                FROM fact_single_household_by_age s
                JOIN dim_admin_area d ON LEFT(s.admin_code, 5) = d.sigungu_code
                WHERE TO_CHAR(s.base_ym, 'YYYYMM') = '{compare_ym}'
                  AND s.age BETWEEN {age_start} AND {age_end}
                  AND {where_sql}
            """, engine)

            base_val = float(base_df['val'].iloc[0] or 0)
            compare_val = float(compare_df['val'].iloc[0] or 0)

            change_rate = round((base_val - compare_val) / compare_val * 100, 2) if compare_val > 0 else 0

            results.append({
                'age_group': label,
                'base_value': base_val,
                'compare_value': compare_val,
                'change': base_val - compare_val,
                'change_rate': change_rate
            })
        except Exception:
            continue

    return results


def create_age_bar_chart(pop_data, single_data, age_category_name, base_ym, compare_ym):
    """연령대별 인구/1인가구 묶음 막대그래프 생성 (matplotlib)"""
    fig, ax = plt.subplots(figsize=(14, 6))

    # 데이터 준비
    labels = [d['age_group'] for d in pop_data]
    pop_rates = [d['change_rate'] for d in pop_data]

    # 1인가구 데이터 매핑 (연령그룹이 같은 것 찾기)
    single_dict = {d['age_group']: d['change_rate'] for d in single_data}
    single_rates = [single_dict.get(label, 0) for label in labels]

    x = np.arange(len(labels))
    width = 0.35

    # 막대 그래프
    bars1 = ax.bar(x - width/2, pop_rates, width, label='인구 변화율', color='#3B82F6', edgecolor='white')
    bars2 = ax.bar(x + width/2, single_rates, width, label='1인가구 변화율', color='#F97316', edgecolor='white')

    # 기준선
    ax.axhline(y=0, color='#666', linestyle='-', linewidth=0.8)

    # 제목 및 라벨
    ax.set_title(f'연령대별 인구 및 1인가구 변화율 ({age_category_name})\n기준: {base_ym[:4]}.{base_ym[4:]} vs 비교: {compare_ym[:4]}.{compare_ym[4:]}',
                 fontsize=12, fontweight='bold', pad=15)
    ax.set_xlabel('연령대', fontsize=10)
    ax.set_ylabel('변화율 (%)', fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)

    # 범례
    ax.legend(loc='upper right', fontsize=9)

    # 그리드
    ax.grid(axis='y', alpha=0.3)
    ax.set_axisbelow(True)

    # 값 표시 (막대 위에)
    for bar, val in zip(bars1, pop_rates):
        if abs(val) > 0.5:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                   f'{val:.1f}', ha='center', va='bottom', fontsize=7, color='#3B82F6')
    for bar, val in zip(bars2, single_rates):
        if abs(val) > 0.5:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                   f'{val:.1f}', ha='center', va='bottom', fontsize=7, color='#F97316')

    plt.tight_layout()

    # 이미지로 변환
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)

    return img_base64


def get_age_5year_data(base_ym, sido=None, region_nm=None, sigungu_level='basic'):
    """5세별 인구/1인가구 현황 데이터"""
    engine = get_db_engine()

    # 지역 필터
    where_clauses = ["1=1"]
    if sido:
        where_clauses.append(f"c.sido_nm = '{sido}'")
    if sigungu_level == 'basic':
        where_clauses.append("c.sigungu_code LIKE '____0'")
    where_sql = " AND ".join(where_clauses)

    # 5세별 인구 컬럼 (category=1)
    age_groups_5 = get_age_groups_from_db(1)  # 5세별

    pop_data = []
    single_data = []

    for _, grp in age_groups_5.iterrows():
        col = grp['column_name']
        label = grp['code_name']
        age_start = int(grp.get('age_start', 0))
        age_end = int(grp.get('age_end', 100))

        try:
            # 인구 데이터
            pop_df = pd.read_sql(f"""
                SELECT SUM(COALESCE({col}, 0)) as val
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{base_ym}' AND {where_sql}
            """, engine)
            pop_val = int(pop_df['val'].iloc[0] or 0)
            pop_data.append({'label': label, 'value': pop_val, 'age_start': age_start, 'age_end': age_end})

            # 1인가구 데이터 (fact_single_household_by_age에서)
            single_where = []
            if sido:
                single_where.append(f"d.sido_nm = '{sido}'")
            if sigungu_level == 'basic':
                single_where.append("LEFT(s.admin_code, 5) LIKE '____0'")
            single_where_sql = " AND ".join(single_where) if single_where else "1=1"

            single_df = pd.read_sql(f"""
                SELECT COALESCE(SUM(s.male_cnt + s.female_cnt), 0) as val
                FROM fact_single_household_by_age s
                JOIN dim_admin_area d ON LEFT(s.admin_code, 5) = d.sigungu_code
                WHERE TO_CHAR(s.base_ym, 'YYYYMM') = '{base_ym}'
                  AND s.age BETWEEN {age_start} AND {age_end}
                  AND {single_where_sql}
            """, engine)
            single_val = int(single_df['val'].iloc[0] or 0)
            single_data.append({'label': label, 'value': single_val, 'age_start': age_start, 'age_end': age_end})
        except Exception:
            continue

    return pop_data, single_data


def get_gender_age_data(base_ym, sido=None, region_nm=None, sigungu_level='basic'):
    """연령별 남녀 인구/1인가구 데이터"""
    engine = get_db_engine()

    # 지역 필터
    single_where = []
    if sido:
        single_where.append(f"d.sido_nm = '{sido}'")
    if sigungu_level == 'basic':
        single_where.append("LEFT(s.admin_code, 5) LIKE '____0'")
    single_where_sql = " AND ".join(single_where) if single_where else "1=1"

    # 연령별(5세 단위) 남녀 1인가구 데이터
    df = pd.read_sql(f"""
        SELECT
            CASE
                WHEN s.age < 5 THEN '0-4세'
                WHEN s.age < 10 THEN '5-9세'
                WHEN s.age < 15 THEN '10-14세'
                WHEN s.age < 20 THEN '15-19세'
                WHEN s.age < 25 THEN '20-24세'
                WHEN s.age < 30 THEN '25-29세'
                WHEN s.age < 35 THEN '30-34세'
                WHEN s.age < 40 THEN '35-39세'
                WHEN s.age < 45 THEN '40-44세'
                WHEN s.age < 50 THEN '45-49세'
                WHEN s.age < 55 THEN '50-54세'
                WHEN s.age < 60 THEN '55-59세'
                WHEN s.age < 65 THEN '60-64세'
                WHEN s.age < 70 THEN '65-69세'
                WHEN s.age < 75 THEN '70-74세'
                WHEN s.age < 80 THEN '75-79세'
                WHEN s.age < 85 THEN '80-84세'
                WHEN s.age < 90 THEN '85-89세'
                WHEN s.age < 95 THEN '90-94세'
                WHEN s.age < 100 THEN '95-99세'
                ELSE '100세이상'
            END as age_group,
            MIN(s.age) as age_start,
            SUM(s.male_cnt) as male_single,
            SUM(s.female_cnt) as female_single
        FROM fact_single_household_by_age s
        JOIN dim_admin_area d ON LEFT(s.admin_code, 5) = d.sigungu_code
        WHERE TO_CHAR(s.base_ym, 'YYYYMM') = '{base_ym}'
          AND {single_where_sql}
        GROUP BY
            CASE
                WHEN s.age < 5 THEN '0-4세'
                WHEN s.age < 10 THEN '5-9세'
                WHEN s.age < 15 THEN '10-14세'
                WHEN s.age < 20 THEN '15-19세'
                WHEN s.age < 25 THEN '20-24세'
                WHEN s.age < 30 THEN '25-29세'
                WHEN s.age < 35 THEN '30-34세'
                WHEN s.age < 40 THEN '35-39세'
                WHEN s.age < 45 THEN '40-44세'
                WHEN s.age < 50 THEN '45-49세'
                WHEN s.age < 55 THEN '50-54세'
                WHEN s.age < 60 THEN '55-59세'
                WHEN s.age < 65 THEN '60-64세'
                WHEN s.age < 70 THEN '65-69세'
                WHEN s.age < 75 THEN '70-74세'
                WHEN s.age < 80 THEN '75-79세'
                WHEN s.age < 85 THEN '80-84세'
                WHEN s.age < 90 THEN '85-89세'
                WHEN s.age < 95 THEN '90-94세'
                WHEN s.age < 100 THEN '95-99세'
                ELSE '100세이상'
            END
        ORDER BY MIN(s.age)
    """, engine)

    return df.to_dict('records')


def create_donut_charts(pop_data, single_data, region_name, base_ym):
    """5세별 인구/1인가구 도넛 차트 생성"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))

    # 색상 팔레트
    colors = plt.cm.tab20.colors

    # 총인구, 총1인가구 계산
    total_pop = sum(d['value'] for d in pop_data) if pop_data else 0
    total_single = sum(d['value'] for d in single_data) if single_data else 0

    # 인구 도넛 차트
    ax1 = axes[0]
    labels1 = [d['label'] for d in pop_data if d['value'] > 0]
    values1 = [d['value'] for d in pop_data if d['value'] > 0]

    if values1:
        pcts1 = [v/total_pop*100 if total_pop > 0 else 0 for v in values1]
        wedges1, texts1, autotexts1 = ax1.pie(
            values1, labels=None, autopct='',
            colors=colors[:len(values1)], startangle=90,
            wedgeprops=dict(width=0.5, edgecolor='white')
        )
        legend_labels1 = [f'{labels1[i]} ({pcts1[i]:.1f}%, {values1[i]:,}명)' for i in range(len(labels1))]
        ax1.legend(wedges1, legend_labels1, loc='center left', bbox_to_anchor=(-0.3, 0.5), fontsize=7)
    else:
        ax1.text(0.5, 0.5, '데이터 없음', ha='center', va='center', transform=ax1.transAxes, fontsize=14)

    ax1.text(0, 0, f'총인구\n{total_pop:,}명', ha='center', va='center', fontsize=12, fontweight='bold')
    ax1.set_title(f'5세별 인구 구성', fontsize=11, fontweight='bold', pad=10)

    # 1인가구 도넛 차트
    ax2 = axes[1]
    labels2 = [d['label'] for d in single_data if d['value'] > 0]
    values2 = [d['value'] for d in single_data if d['value'] > 0]

    if values2:
        pcts2 = [v/total_single*100 if total_single > 0 else 0 for v in values2]
        wedges2, texts2, autotexts2 = ax2.pie(
            values2, labels=None, autopct='',
            colors=colors[:len(values2)], startangle=90,
            wedgeprops=dict(width=0.5, edgecolor='white')
        )
        legend_labels2 = [f'{labels2[i]} ({pcts2[i]:.1f}%, {values2[i]:,}명)' for i in range(len(labels2))]
        ax2.legend(wedges2, legend_labels2, loc='center left', bbox_to_anchor=(1.05, 0.5), fontsize=7)
    else:
        ax2.text(0.5, 0.5, '데이터 없음', ha='center', va='center', transform=ax2.transAxes, fontsize=14)

    ax2.text(0, 0, f'1인가구\n{total_single:,}명', ha='center', va='center', fontsize=12, fontweight='bold')
    ax2.set_title(f'5세별 1인가구 구성', fontsize=11, fontweight='bold', pad=10)

    fig.suptitle(f'5세별 인구/1인가구 구성 ({region_name})', fontsize=13, fontweight='bold', y=1.02)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)

    return img_base64


def create_population_pyramid(gender_data, region_name, base_ym):
    """인구 피라미드 차트 생성"""
    fig, ax = plt.subplots(figsize=(10, 8))

    if not gender_data:
        ax.text(0.5, 0.5, '데이터 없음', ha='center', va='center', transform=ax.transAxes, fontsize=14)
        ax.set_title(f'연령별 성별 피라미드 ({region_name})', fontsize=12, fontweight='bold', pad=15)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        return img_base64

    labels = [d['age_group'] for d in gender_data]
    male = [-int(d.get('male_single', 0) or 0) for d in gender_data]  # 왼쪽으로 표시
    female = [int(d.get('female_single', 0) or 0) for d in gender_data]

    y = np.arange(len(labels))
    height = 0.8

    ax.barh(y, male, height, label='남자', color='#3B82F6', edgecolor='white')
    ax.barh(y, female, height, label='여자', color='#EF4444', edgecolor='white')

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel('1인가구 수', fontsize=10)

    # x축 라벨을 절대값으로 표시
    max_val = max(max(abs(m) for m in male) if male else 1, max(female) if female else 1)
    ticks = ax.get_xticks()
    ax.set_xticklabels([f'{abs(int(t)):,}' for t in ticks])

    ax.legend(loc='upper right', fontsize=9)
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.grid(axis='x', alpha=0.3)

    ax.set_title(f'연령별 성별 피라미드 ({region_name})', fontsize=12, fontweight='bold', pad=15)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)

    return img_base64


def create_age_comparison_chart(pop_data, single_data, region_name, base_ym):
    """연령별 인구 vs 1인가구 비교 차트 (막대 + 라인)"""
    fig, ax1 = plt.subplots(figsize=(14, 6))

    if not pop_data:
        ax1.text(0.5, 0.5, '데이터 없음', ha='center', va='center', transform=ax1.transAxes, fontsize=14)
        ax1.set_title(f'연령별 인구 vs 1인가구 비교 ({region_name})', fontsize=12, fontweight='bold', pad=15)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        return img_base64

    labels = [d['label'] for d in pop_data]
    pop_values = [d['value'] for d in pop_data]

    # 1인가구 데이터 매핑
    single_dict = {d['label']: d['value'] for d in single_data} if single_data else {}
    single_values = [single_dict.get(label, 0) for label in labels]

    # 1인가구 비율 계산
    single_ratio = [s/p*100 if p > 0 else 0 for p, s in zip(pop_values, single_values)]

    x = np.arange(len(labels))
    width = 0.35

    # 인구 막대 (파란색)
    bars1 = ax1.bar(x - width/2, pop_values, width, label='인구수', color='#3B82F6', alpha=0.8)
    # 1인가구 막대 (주황색)
    bars2 = ax1.bar(x + width/2, single_values, width, label='1인가구수', color='#F97316', alpha=0.8)

    ax1.set_xlabel('연령대', fontsize=10)
    ax1.set_ylabel('인구/1인가구 수', fontsize=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax1.tick_params(axis='y')

    # 1인가구 비율 라인 (보조 Y축)
    ax2 = ax1.twinx()
    line = ax2.plot(x, single_ratio, color='#EF4444', marker='o', linewidth=2, markersize=4, label='1인가구비율(%)')
    ax2.set_ylabel('1인가구 비율 (%)', fontsize=10, color='#EF4444')
    ax2.tick_params(axis='y', labelcolor='#EF4444')
    max_ratio = max(single_ratio) if single_ratio and max(single_ratio) > 0 else 100
    ax2.set_ylim(0, max_ratio * 1.2)

    # 범례
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=9)

    ax1.set_title(f'연령별 인구 vs 1인가구 비교 ({region_name})', fontsize=12, fontweight='bold', pad=15)
    ax1.grid(axis='y', alpha=0.3)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)

    return img_base64


def create_gender_detail_charts(gender_data, region_name, base_ym):
    """연령별 남녀 1인가구 상세 차트"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    if not gender_data:
        axes[0].text(0.5, 0.5, '데이터 없음', ha='center', va='center', transform=axes[0].transAxes, fontsize=14)
        axes[1].text(0.5, 0.5, '데이터 없음', ha='center', va='center', transform=axes[1].transAxes, fontsize=14)
        axes[0].set_title(f'연령별 남녀 1인가구 ({region_name})', fontsize=10, fontweight='bold')
        axes[1].set_title(f'연령별 1인가구 성비 ({region_name})', fontsize=10, fontweight='bold')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        return img_base64

    labels = [d['age_group'] for d in gender_data]
    male = [int(d.get('male_single', 0) or 0) for d in gender_data]
    female = [int(d.get('female_single', 0) or 0) for d in gender_data]

    x = np.arange(len(labels))
    width = 0.35

    # 왼쪽: 남녀 1인가구 비교
    ax1 = axes[0]
    ax1.bar(x - width/2, male, width, label='남자', color='#3B82F6')
    ax1.bar(x + width/2, female, width, label='여자', color='#EF4444')
    ax1.set_xlabel('연령대', fontsize=9)
    ax1.set_ylabel('1인가구 수', fontsize=9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
    ax1.legend(loc='upper right', fontsize=8)
    ax1.set_title(f'연령별 남녀 1인가구 ({region_name})', fontsize=10, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)

    # 오른쪽: 성비 (남/여 비율)
    ax2 = axes[1]
    total_by_age = [m + f for m, f in zip(male, female)]
    male_ratio = [m/t*100 if t > 0 else 50 for m, t in zip(male, total_by_age)]
    female_ratio = [f/t*100 if t > 0 else 50 for f, t in zip(female, total_by_age)]

    ax2.bar(x, male_ratio, width=0.6, label='남자 비율', color='#3B82F6')
    ax2.bar(x, female_ratio, width=0.6, bottom=male_ratio, label='여자 비율', color='#EF4444')
    ax2.axhline(y=50, color='black', linestyle='--', linewidth=1, alpha=0.5)
    ax2.set_xlabel('연령대', fontsize=9)
    ax2.set_ylabel('성별 비율 (%)', fontsize=9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
    ax2.legend(loc='upper right', fontsize=8)
    ax2.set_title(f'연령별 1인가구 성비 ({region_name})', fontsize=10, fontweight='bold')
    ax2.set_ylim(0, 100)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)

    return img_base64


def get_divergence_data(base_ym, compare_ym, sido=None, region_nm=None, sigungu_level='basic'):
    """인구-1인가구 차이 데이터 (사분면용)"""
    engine = get_db_engine()

    # 전국 선택 시 시도별 집계
    if not sido and not region_nm:
        df = pd.read_sql(f"""
            WITH sido_master AS (
                SELECT sido_nm, MIN(sido_code) as sido_code
                FROM dim_admin_area
                WHERE sido_code IS NOT NULL
                GROUP BY sido_nm
            ),
            base_data AS (
                SELECT c.sido_nm,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                    SUM(COALESCE(c.elderly_pop, 0)) as elderly_pop
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{base_ym}'
                GROUP BY c.sido_nm
            ),
            compare_data AS (
                SELECT c.sido_nm,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{compare_ym}'
                GROUP BY c.sido_nm
            )
            SELECT COALESCE(s.sido_code, '00') as sigungu_code, b.sido_nm as sigungu_nm,
                b.total_pop as base_pop, c.total_pop as compare_pop,
                b.single_cnt as base_single, c.single_cnt as compare_single, b.elderly_pop,
                ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) as pop_change_rate,
                ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2) as single_change_rate
            FROM base_data b
            JOIN compare_data c ON b.sido_nm = c.sido_nm
            LEFT JOIN sido_master s ON b.sido_nm = s.sido_nm
            ORDER BY s.sido_code
        """, engine)
    # 권역별 선택 시 권역별 집계
    elif region_nm == '__all_regions__':
        df = pd.read_sql(f"""
            WITH region_master AS (
                SELECT DISTINCT region_code, region_nm
                FROM dim_admin_area
                WHERE region_code IS NOT NULL AND region_nm IS NOT NULL
            ),
            base_data AS (
                SELECT d.region_code, d.region_nm,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                    SUM(COALESCE(c.elderly_pop, 0)) as elderly_pop
                FROM cache_sigungu_indicators c
                JOIN dim_admin_area d ON c.sigungu_code = d.sigungu_code
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{base_ym}' AND d.region_nm IS NOT NULL
                GROUP BY d.region_code, d.region_nm
            ),
            compare_data AS (
                SELECT d.region_code,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt
                FROM cache_sigungu_indicators c
                JOIN dim_admin_area d ON c.sigungu_code = d.sigungu_code
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{compare_ym}' AND d.region_nm IS NOT NULL
                GROUP BY d.region_code
            )
            SELECT b.region_code as sigungu_code, b.region_nm as sigungu_nm,
                b.total_pop as base_pop, c.total_pop as compare_pop,
                b.single_cnt as base_single, c.single_cnt as compare_single, b.elderly_pop,
                ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) as pop_change_rate,
                ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2) as single_change_rate
            FROM base_data b
            JOIN compare_data c ON b.region_code = c.region_code
            ORDER BY b.region_code
        """, engine)
    # 시도 선택 시 시군구별 집계
    elif sigungu_level == 'basic':
        df = pd.read_sql(f"""
            WITH base_data AS (
                SELECT LEFT(c.sigungu_code, 4) as sigungu_group,
                    MIN(CASE WHEN c.sigungu_code LIKE '____0' THEN c.sigungu_nm END) as sigungu_nm,
                    MIN(c.sigungu_code) as sigungu_code,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                    SUM(COALESCE(c.elderly_pop, 0)) as elderly_pop
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{base_ym}' AND c.sido_nm = '{sido}'
                GROUP BY LEFT(c.sigungu_code, 4)
            ),
            compare_data AS (
                SELECT LEFT(c.sigungu_code, 4) as sigungu_group,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{compare_ym}' AND c.sido_nm = '{sido}'
                GROUP BY LEFT(c.sigungu_code, 4)
            )
            SELECT b.sigungu_code, COALESCE(b.sigungu_nm, b.sigungu_group) as sigungu_nm,
                b.total_pop as base_pop, c.total_pop as compare_pop,
                b.single_cnt as base_single, c.single_cnt as compare_single, b.elderly_pop,
                ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) as pop_change_rate,
                ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2) as single_change_rate
            FROM base_data b
            JOIN compare_data c ON b.sigungu_group = c.sigungu_group
            ORDER BY b.sigungu_code
        """, engine)
    else:
        # 하위포함 모드
        df = pd.read_sql(f"""
            SELECT c1.sigungu_code, c1.sigungu_nm,
                c1.total_pop as base_pop, c2.total_pop as compare_pop,
                COALESCE(c1.single_cnt, 0) as base_single, COALESCE(c2.single_cnt, 0) as compare_single,
                COALESCE(c1.elderly_pop, 0) as elderly_pop,
                ROUND((c1.total_pop - c2.total_pop)::numeric / NULLIF(c2.total_pop, 0) * 100, 2) as pop_change_rate,
                ROUND((COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0))::numeric / NULLIF(COALESCE(c2.single_cnt, 0), 0) * 100, 2) as single_change_rate
            FROM cache_sigungu_indicators c1
            JOIN cache_sigungu_indicators c2 ON c1.sigungu_code = c2.sigungu_code
            WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
              AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
              AND c1.sido_nm = '{sido}'
            ORDER BY c1.sigungu_code
        """, engine)

    df = df.fillna(0)

    # 차이지수 계산 (|인구변화율 - 1인가구변화율|)
    df['divergence_index'] = abs(df['pop_change_rate'] - df['single_change_rate'])

    # 사분면 분류
    def classify_quadrant(row):
        if row['pop_change_rate'] >= 0 and row['single_change_rate'] >= 0:
            return '1사분면(인구+,1인가구+)'
        elif row['pop_change_rate'] < 0 and row['single_change_rate'] >= 0:
            return '2사분면(인구-,1인가구+)'
        elif row['pop_change_rate'] < 0 and row['single_change_rate'] < 0:
            return '3사분면(인구-,1인가구-)'
        else:
            return '4사분면(인구+,1인가구-)'

    df['quadrant'] = df.apply(classify_quadrant, axis=1)

    return df.to_dict('records')


def get_trend_data(sido=None, region_nm=None, sigungu_level='basic'):
    """4개 시점 추이 데이터 (전체 추세이므로 지역 필터만 적용)"""
    engine = get_db_engine()

    where_clauses = ["1=1"]
    # 전국 또는 권역별 선택 시 전체 데이터
    # 시도 선택 시 해당 시도 필터
    if sido and region_nm != '__all_regions__':
        where_clauses.append(f"sido_nm = '{sido}'")
    if sigungu_level == 'basic':
        where_clauses.append("sigungu_code LIKE '____0'")

    where_sql = " AND ".join(where_clauses)

    df = pd.read_sql(f"""
        SELECT
            base_ym,
            SUM(total_pop) as total_pop,
            SUM(COALESCE(single_cnt, 0)) as single_cnt,
            AVG(elderly_ratio) as elderly_ratio,
            AVG(COALESCE(single_ratio, 0)) as single_ratio
        FROM cache_sigungu_indicators
        WHERE {where_sql}
        GROUP BY base_ym
        ORDER BY base_ym
    """, engine)

    return df.to_dict('records')


def get_heatmap_data(base_ym, compare_ym, sido=None, region_nm=None, sigungu_level='basic', age_category=3):
    """히트맵 데이터 (지역 x 연령대) - DB에서 연령그룹 조회"""
    engine = get_db_engine()

    # DB에서 연령그룹 조회
    age_groups = get_age_groups_from_db(age_category)
    age_cols = age_groups['column_name'].tolist()
    age_labels = age_groups['code_name'].tolist()

    # 전국 선택 시 시도별 집계
    if not sido and not region_nm:
        select_parts = ["c1.sido_nm as region"]
        for col in age_cols:
            select_parts.append(f"""
                ROUND((SUM(COALESCE(c1.{col}, 0)) - SUM(COALESCE(c2.{col}, 0)))::numeric /
                      NULLIF(SUM(COALESCE(c2.{col}, 0)), 0) * 100, 2) as {col}_change
            """)
        select_sql = ", ".join(select_parts)

        df = pd.read_sql(f"""
            SELECT {select_sql}
            FROM cache_sigungu_indicators c1
            JOIN cache_sigungu_indicators c2
                ON c1.sigungu_code = c2.sigungu_code
            WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
              AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
            GROUP BY c1.sido_nm
            ORDER BY c1.sido_nm
        """, engine)

    # 권역별 선택 시 권역별 집계
    elif region_nm == '__all_regions__':
        select_parts = ["c1.region_nm as region"]
        for col in age_cols:
            select_parts.append(f"""
                ROUND((SUM(COALESCE(c1.{col}, 0)) - SUM(COALESCE(c2.{col}, 0)))::numeric /
                      NULLIF(SUM(COALESCE(c2.{col}, 0)), 0) * 100, 2) as {col}_change
            """)
        select_sql = ", ".join(select_parts)

        df = pd.read_sql(f"""
            SELECT {select_sql}
            FROM cache_sigungu_indicators c1
            JOIN cache_sigungu_indicators c2
                ON c1.sigungu_code = c2.sigungu_code
            WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
              AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
            GROUP BY c1.region_nm
            ORDER BY c1.region_nm
        """, engine)

    # 시도 선택 시 시군구별 집계
    else:
        where_clauses = ["1=1"]
        if sido:
            where_clauses.append(f"c1.sido_nm = '{sido}'")
        if sigungu_level == 'basic':
            where_clauses.append("c1.sigungu_code LIKE '____0'")
        where_sql = " AND ".join(where_clauses)

        select_parts = ["c1.sigungu_nm as region"]
        for col in age_cols:
            select_parts.append(f"""
                ROUND((COALESCE(c1.{col}, 0) - COALESCE(c2.{col}, 0))::numeric /
                      NULLIF(COALESCE(c2.{col}, 0), 0) * 100, 2) as {col}_change
            """)
        select_sql = ", ".join(select_parts)

        df = pd.read_sql(f"""
            SELECT {select_sql}
            FROM cache_sigungu_indicators c1
            JOIN cache_sigungu_indicators c2
                ON c1.sigungu_code = c2.sigungu_code
            WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
              AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
              AND {where_sql}
            ORDER BY c1.sigungu_nm
        """, engine)

    regions = df['region'].tolist()
    data = []
    for i, col in enumerate(age_cols):
        for j, region in enumerate(regions):
            val = df.iloc[j][f'{col}_change']
            data.append({
                'x': i,
                'y': j,
                'value': float(val) if pd.notna(val) else 0,
                'age_group': age_labels[i],
                'region': region
            })

    return {
        'regions': regions,
        'age_groups': age_labels,
        'data': data
    }


def generate_insights(base_ym, compare_ym, sido=None, region_nm=None, sigungu_level='basic'):
    """
    ============================================================================
    인사이트 자동 생성 함수 (generate_insights)
    ============================================================================

    대시보드의 "자동 인사이트" 섹션에 표시될 5개의 분석 결과를 생성합니다.
    데이터 패턴을 자동으로 분석하여 정책 담당자에게 유의미한 인사이트를 제공합니다.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                           인사이트 생성 로직                              │
    ├─────────────────────────────────────────────────────────────────────────┤
    │  1. 인구↓ 1인가구↑ 불일치 탐지                                           │
    │     → 인구는 감소하지만 1인가구는 증가하는 지역 (괴리 현상)               │
    │                                                                         │
    │  2. 1인가구 급증 (가구 분화 가속)                                        │
    │     → 1인가구 증가율이 인구 증가율의 2배 이상인 지역                      │
    │                                                                         │
    │  3. 1인가구 비중 위험 수준                                               │
    │     → 1인가구 비율이 50% 이상인 위험 지역                                │
    │                                                                         │
    │  4. 지역 간 고령화 격차                                                  │
    │     → 고령화율 최고/최저 지역 및 격차 분석                               │
    │                                                                         │
    │  5. 청년인구 추세                                                        │
    │     → 19~34세 청년층의 연속 감소/증가 패턴 탐지                          │
    └─────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         집계 레벨 결정 로직                               │
    ├─────────────────────────────────────────────────────────────────────────┤
    │  조건                          │  집계 기준      │  region_col          │
    │ ──────────────────────────────┼─────────────────┼────────────────────── │
    │  sido=None, region_nm=None    │  시도별 집계    │  sido_nm             │
    │  region_nm='__all_regions__'  │  권역별 집계    │  region_nm           │
    │  sido='서울특별시' 등         │  시군구별 집계  │  sigungu_nm          │
    └─────────────────────────────────────────────────────────────────────────┘

    Args:
        base_ym (str): 기준 시점 (YYYYMM 형식, 예: '202409')
        compare_ym (str): 비교 시점 (YYYYMM 형식, 예: '202309')
        sido (str, optional): 시도명. None이면 전국
        region_nm (str, optional): 권역명. '__all_regions__'면 권역별 집계
        sigungu_level (str): 'basic'=대표 시군구만, 'include_sub'=하위 포함

    Returns:
        list: 인사이트 딕셔너리 리스트 (항상 5개 반환)
              [
                  {
                      'icon': '1',           # 인사이트 번호
                      'title': '제목',       # 인사이트 제목
                      'content': '내용',     # 상세 내용 (• 로 시작하는 문단)
                      'suggestion': '제안'   # 정책 제안
                  },
                  ...
              ]

    SQL 쿼리 구조:
        - 전국/권역별: CTE로 시도/권역별 합계 후 변화율 계산
        - 시도 선택: WHERE 조건으로 시군구 필터링 후 개별 계산

    ★ 주의사항:
        - 인사이트가 5개 미만이면 "추가 분석 필요" 기본 인사이트로 채움
        - 데이터가 없는 경우에도 항상 5개의 인사이트 반환
        - CTE 쿼리(전국/권역)와 직접 쿼리(시도 선택)가 다른 구조 사용
    """
    engine = get_db_engine()

    # =========================================================================
    # STEP 1: 집계 레벨 및 WHERE 조건 결정
    # =========================================================================
    # 지역 선택에 따라 어떤 컬럼으로 그룹화하고 어떤 조건을 적용할지 결정
    #
    # ┌──────────────────┬───────────────┬─────────────────────────────────┐
    # │ 지역 선택        │ region_col    │ 용도                            │
    # ├──────────────────┼───────────────┼─────────────────────────────────┤
    # │ 전국 (기본)      │ sido_nm       │ 시도별로 그룹화하여 비교        │
    # │ 권역 선택        │ region_nm     │ 권역별로 그룹화하여 비교        │
    # │ 특정 시도 선택   │ sigungu_nm    │ 해당 시도 내 시군구별 비교      │
    # └──────────────────┴───────────────┴─────────────────────────────────┘

    if not sido and not region_nm:
        # 【전국】 sido와 region_nm 모두 없음 → 시도별 집계
        # 17개 시도를 비교하여 인사이트 생성
        region_col = "sido_nm"
        where_clauses = ["1=1"]  # 조건 없음 (전체 데이터 사용)
    elif region_nm == '__all_regions__':
        # 【권역별】 수도권/충청권/영남권/호남권/강원제주권 5개 권역 비교
        region_col = "region_nm"
        where_clauses = ["1=1"]
    else:
        # 【시도 선택】 특정 시도 내 시군구들을 비교
        region_col = "sigungu_nm"
        where_clauses = ["1=1"]
        if sido:
            # 해당 시도만 필터링
            where_clauses.append(f"c1.sido_nm = '{sido}'")
        if sigungu_level == 'basic':
            where_clauses.append("c1.sigungu_code LIKE '____0'")

    where_sql = " AND ".join(where_clauses)

    # =========================================================================
    # STEP 2: 인사이트 기반 쿼리(CTE) 생성
    # =========================================================================
    # 전국/권역별 선택 시: CTE(Common Table Expression)로 집계 후 변화율 계산
    # 시도 선택 시: 직접 JOIN 쿼리로 시군구별 변화율 계산
    #
    # 쿼리 구조 비교:
    # ┌─────────────────────────────────────────────────────────────────────────┐
    # │ 【CTE 방식 (전국/권역)】                                                │
    # │  WITH agg_data AS (                                                    │
    # │    SELECT region_nm, SUM(인구), SUM(1인가구)                           │
    # │    FROM c1 JOIN c2 ON 시군구코드                                       │
    # │    GROUP BY region_nm  -- 시도명 또는 권역명                           │
    # │  )                                                                     │
    # │  SELECT region_nm, 인구변화율, 1인가구변화율 FROM agg_data             │
    # ├─────────────────────────────────────────────────────────────────────────┤
    # │ 【직접 쿼리 방식 (시도 선택)】                                          │
    # │  SELECT sigungu_nm, 인구변화율, 1인가구변화율                          │
    # │  FROM c1 JOIN c2 ON 시군구코드                                         │
    # │  WHERE c1.sido_nm = '선택된시도' AND ...                               │
    # └─────────────────────────────────────────────────────────────────────────┘

    if not sido and not region_nm:
        # 【전국 선택】 시도별 집계 CTE 쿼리
        # c1(기준시점)과 c2(비교시점)를 같은 시군구코드로 JOIN 후 시도별 합산
        insight_base_sql = f"""
            WITH agg_data AS (
                SELECT c1.{region_col} as region_nm,
                    SUM(c1.total_pop) as base_pop,
                    SUM(c2.total_pop) as compare_pop,
                    SUM(COALESCE(c1.single_cnt, 0)) as base_single,
                    SUM(COALESCE(c2.single_cnt, 0)) as compare_single
                FROM cache_sigungu_indicators c1
                JOIN cache_sigungu_indicators c2 ON c1.sigungu_code = c2.sigungu_code
                WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
                  AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
                GROUP BY c1.{region_col}
            )
            SELECT region_nm,
                ROUND((base_pop - compare_pop)::numeric / NULLIF(compare_pop, 0) * 100, 2) as pop_change,
                ROUND((base_single - compare_single)::numeric / NULLIF(compare_single, 0) * 100, 2) as single_change
            FROM agg_data
        """
    elif region_nm == '__all_regions__':
        # 권역별 집계 쿼리
        insight_base_sql = f"""
            WITH agg_data AS (
                SELECT c1.{region_col} as region_nm,
                    SUM(c1.total_pop) as base_pop,
                    SUM(c2.total_pop) as compare_pop,
                    SUM(COALESCE(c1.single_cnt, 0)) as base_single,
                    SUM(COALESCE(c2.single_cnt, 0)) as compare_single
                FROM cache_sigungu_indicators c1
                JOIN cache_sigungu_indicators c2 ON c1.sigungu_code = c2.sigungu_code
                WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
                  AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
                GROUP BY c1.{region_col}
            )
            SELECT region_nm,
                ROUND((base_pop - compare_pop)::numeric / NULLIF(compare_pop, 0) * 100, 2) as pop_change,
                ROUND((base_single - compare_single)::numeric / NULLIF(compare_single, 0) * 100, 2) as single_change
            FROM agg_data
        """
    else:
        # 【시도 선택】 CTE 사용하지 않고 직접 쿼리 (insight_base_sql = None)
        insight_base_sql = None

    # =========================================================================
    # STEP 3: 5가지 인사이트 생성
    # =========================================================================
    insights = []  # 최종 반환할 인사이트 리스트 (최대 5개)

    # -------------------------------------------------------------------------
    # 인사이트 1: 인구↓ 1인가구↑ 불일치 탐지 (Divergence Detection)
    # -------------------------------------------------------------------------
    # 조건: 인구는 감소(-) BUT 1인가구는 증가(+)
    # 의미: 기존 가구가 1인가구로 분화되는 현상 (이혼, 사별, 분가 등)
    #       → 인구 감소에도 불구하고 돌봄 수요는 오히려 증가할 수 있음
    # 정렬: 1인가구 증가율이 높은 순으로 상위 3개 지역 추출
    if insight_base_sql:
        df = pd.read_sql(f"""
            {insight_base_sql}
            WHERE (base_pop - compare_pop) < 0
              AND (base_single - compare_single) > 0
            ORDER BY (base_single - compare_single)::numeric / NULLIF(compare_single, 0) DESC
            LIMIT 3
        """, engine)
    else:
        df = pd.read_sql(f"""
            SELECT
                c1.{region_col} as region_nm,
                ROUND((c1.total_pop - c2.total_pop)::numeric / NULLIF(c2.total_pop, 0) * 100, 2) as pop_change,
                ROUND((COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0))::numeric /
                      NULLIF(COALESCE(c2.single_cnt, 0), 0) * 100, 2) as single_change
            FROM cache_sigungu_indicators c1
            JOIN cache_sigungu_indicators c2
                ON c1.sigungu_code = c2.sigungu_code
            WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
              AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
              AND {where_sql}
              AND (c1.total_pop - c2.total_pop) < 0
              AND (COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0)) > 0
            ORDER BY (COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0))::numeric /
                     NULLIF(COALESCE(c2.single_cnt, 0), 0) DESC
            LIMIT 3
        """, engine)

    if len(df) > 0:
        top_data = []
        for _, row in df.head(3).iterrows():
            top_data.append(f"{row['region_nm']}(인구{row['pop_change']:+.1f}%/1인{row['single_change']:+.1f}%)")
        insights.append({
            'icon': '1',
            'title': '인구↓ 1인가구↑ 불일치 발생',
            'content': f'• 해당 지역: {", ".join(top_data)}\n• 인구는 줄지만 1인가구는 늘어나는 현상 발생',
            'suggestion': '• 남은 주민의 독립 증가 → 돌봄 서비스 확대 검토'
        })

    # -------------------------------------------------------------------------
    # 인사이트 2: 급격한 가구 분화 (Rapid Household Fragmentation)
    # -------------------------------------------------------------------------
    # 조건: 1인가구 증가율 > 인구 증가율 × 2
    # 의미: 인구 증가 속도보다 1인가구가 훨씬 빠르게 증가
    #       → 가구 분화 가속화 (청년 독립, 고령층 단독화 등)
    # 정책 시사점: 1인가구 맞춤형 주거/복지 정책 우선 적용 필요
    if insight_base_sql:
        df2 = pd.read_sql(f"""
            {insight_base_sql}
            WHERE (base_single - compare_single)::numeric / NULLIF(compare_single, 0) >
                  (base_pop - compare_pop)::numeric / NULLIF(compare_pop, 0) * 2
            LIMIT 3
        """, engine)
    else:
        df2 = pd.read_sql(f"""
            SELECT
                c1.{region_col} as region_nm,
                ROUND((c1.total_pop - c2.total_pop)::numeric / NULLIF(c2.total_pop, 0) * 100, 2) as pop_change,
                ROUND((COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0))::numeric /
                      NULLIF(COALESCE(c2.single_cnt, 0), 0) * 100, 2) as single_change
            FROM cache_sigungu_indicators c1
            JOIN cache_sigungu_indicators c2
                ON c1.sigungu_code = c2.sigungu_code
            WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
              AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
              AND {where_sql}
              AND (COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0))::numeric /
                  NULLIF(COALESCE(c2.single_cnt, 0), 0) >
                  (c1.total_pop - c2.total_pop)::numeric / NULLIF(c2.total_pop, 0) * 2
            LIMIT 3
        """, engine)

    if len(df2) > 0:
        top_data2 = []
        for _, row in df2.head(3).iterrows():
            top_data2.append(f"{row['region_nm']}(인구{row['pop_change']:+.1f}%/1인{row['single_change']:+.1f}%)")
        insights.append({
            'icon': '2',
            'title': '1인가구 급증',
            'content': f'• 해당 지역: {", ".join(top_data2)}\n• 1인가구 증가 속도가 인구 증가의 2배 이상',
            'suggestion': '• 1인가구 맞춤형 주거/복지 정책 우선 추진'
        })

    # -------------------------------------------------------------------------
    # 인사이트 3: 1인가구 비중 위험 수준 (High Single Household Ratio Alert)
    # -------------------------------------------------------------------------
    # 조건: 1인가구 비율(single_ratio) >= 50%
    # 의미: 전체 가구의 절반 이상이 1인가구인 지역
    #       → 독거 돌봄 위험 증가, 지역 커뮤니티 약화
    # 임계값: 50%는 정책적으로 위험 수준으로 간주하는 기준점
    # 정책 시사점: 긴급 돌봄 대응 체계, 사회적 연대 프로그램 필요
    if not sido and not region_nm:
        df3 = pd.read_sql(f"""
            SELECT sido_nm as region_nm, AVG(COALESCE(single_ratio, 0)) as single_ratio
            FROM cache_sigungu_indicators
            WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}'
            GROUP BY sido_nm
            HAVING AVG(COALESCE(single_ratio, 0)) >= 50
            ORDER BY AVG(single_ratio) DESC
            LIMIT 5
        """, engine)
    elif region_nm == '__all_regions__':
        df3 = pd.read_sql(f"""
            SELECT region_nm, AVG(COALESCE(single_ratio, 0)) as single_ratio
            FROM cache_sigungu_indicators
            WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}'
            GROUP BY region_nm
            HAVING AVG(COALESCE(single_ratio, 0)) >= 50
            ORDER BY AVG(single_ratio) DESC
            LIMIT 5
        """, engine)
    else:
        df3 = pd.read_sql(f"""
            SELECT {region_col} as region_nm, single_ratio
            FROM cache_sigungu_indicators
            WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}'
              AND {where_sql.replace('c1.', '')}
              AND COALESCE(single_ratio, 0) >= 50
            ORDER BY single_ratio DESC
            LIMIT 5
        """, engine)

    if len(df3) > 0:
        regions = ", ".join(df3['region_nm'].tolist()[:3])
        max_ratio = df3['single_ratio'].max()
        insights.append({
            'icon': '3',
            'title': '1인가구 비중 위험 수준',
            'content': f'• 해당 지역: {regions} 등 {len(df3)}개\n• 1인가구 비중 50% 이상 (최고 {max_ratio}%)',
            'suggestion': '• 독거 돌봄 위험 → 긴급 대응 체계 마련 필요'
        })

    # -------------------------------------------------------------------------
    # 인사이트 4: 지역 간 고령화 격차 (Regional Aging Disparity)
    # -------------------------------------------------------------------------
    # 분석: 고령화율(elderly_ratio) 최고/최저 지역 비교
    # 목적: 지역 간 고령화 불균형 심각성 파악
    # 계산: 격차(gap) = 최고 고령화율 - 최저 고령화율
    # 정책 시사점: 격차가 클수록 지역별 맞춤 정책 필요
    #             (예: 고령화 심각 지역 → 노인 돌봄 강화
    #                  고령화 낮은 지역 → 경제활동 지원)
    if not sido and not region_nm:
        df4 = pd.read_sql(f"""
            SELECT sido_nm as region_nm, AVG(elderly_ratio) as elderly_ratio
            FROM cache_sigungu_indicators
            WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}'
            GROUP BY sido_nm
            ORDER BY AVG(elderly_ratio) DESC
        """, engine)
    elif region_nm == '__all_regions__':
        df4 = pd.read_sql(f"""
            SELECT region_nm, AVG(elderly_ratio) as elderly_ratio
            FROM cache_sigungu_indicators
            WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}'
            GROUP BY region_nm
            ORDER BY AVG(elderly_ratio) DESC
        """, engine)
    else:
        df4 = pd.read_sql(f"""
            SELECT {region_col} as region_nm, elderly_ratio
            FROM cache_sigungu_indicators
            WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}'
              AND {where_sql.replace('c1.', '')}
            ORDER BY elderly_ratio DESC
        """, engine)

    if len(df4) > 2:
        max_region = df4.iloc[0]['region_nm']
        max_val = df4.iloc[0]['elderly_ratio']
        min_region = df4.iloc[-1]['region_nm']
        min_val = df4.iloc[-1]['elderly_ratio']
        gap = round(max_val - min_val, 1)

        insights.append({
            'icon': '4',
            'title': '지역 간 고령화 차이',
            'content': f'• 최고: {max_region} ({max_val}%)\n• 최저: {min_region} ({min_val}%)\n• 차이: {gap}%p',
            'suggestion': '• 지역별 맞춤 정책 적용 검토'
        })

    # -------------------------------------------------------------------------
    # 인사이트 5: 청년인구 추세 (Youth Population Trend)
    # -------------------------------------------------------------------------
    # 분석: young_adult_pop (19~34세 청년층) 시계열 추세
    # 조건: 최근 3개 시점의 청년인구 변화 방향 분석
    #       - 연속 감소: 청년 유출 심각 → 경고
    #       - 연속 증가: 청년 유입 긍정적 → 정착 지원 강화
    # 특징: 이 인사이트는 전체 데이터 기준으로 시계열 분석
    #       (지역 필터가 있어도 해당 지역 전체 청년인구 추세 분석)
    if not sido and not region_nm:
        where_filter = "1=1"  # 전국 전체
    elif region_nm == '__all_regions__':
        where_filter = "1=1"  # 권역 전체
    else:
        # 시도 선택 시 해당 시도만 필터 (c1. 접두사 제거)
        where_filter = where_sql.replace('c1.', '')

    # 시점별 청년인구 합계 조회 (시계열 분석용)
    df5 = pd.read_sql(f"""
        SELECT
            base_ym,
            SUM(COALESCE(young_adult_pop, 0)) as young_adult_pop
        FROM cache_sigungu_indicators
        WHERE {where_filter}
        GROUP BY base_ym
        ORDER BY base_ym
    """, engine)

    # 최소 3개 시점 데이터가 있어야 추세 분석 가능
    if len(df5) >= 3:
        recent = df5.tail(3)['young_adult_pop'].tolist()
        recent_ym = df5.tail(3)['base_ym'].tolist()
        first_pop = int(recent[0])
        last_pop = int(recent[-1])
        change_pct = round((last_pop - first_pop) / first_pop * 100, 2) if first_pop > 0 else 0
        if all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
            insights.append({
                'icon': '5',
                'title': '청년인구 계속 감소',
                'content': f'• 대상: 19~34세 청년층\n• 최근 3개 시점 연속 감소 ({change_pct:+.2f}%)\n• {first_pop:,}명 → {last_pop:,}명',
                'suggestion': '• 청년 유출 방지 및 유입 정책 시급'
            })
        elif all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
            insights.append({
                'icon': '5',
                'title': '청년인구 증가 추세',
                'content': f'• 대상: 19~34세 청년층\n• 최근 3개 시점 연속 증가 ({change_pct:+.2f}%)\n• {first_pop:,}명 → {last_pop:,}명',
                'suggestion': '• 청년 정착 지원 정책 강화로 추세 유지'
            })

    # -------------------------------------------------------------------------
    # 기본 인사이트 채우기 (Fallback Insights)
    # -------------------------------------------------------------------------
    # 인사이트가 5개 미만이면 "추가 분석 필요" 기본 인사이트로 채움
    # → 항상 5개의 인사이트를 반환하여 UI 레이아웃 일관성 유지
    while len(insights) < 5:
        insights.append({
            'icon': str(len(insights) + 1),
            'title': '추가 분석 필요',
            'content': '• 현재 조건에서 특이점 없음',
            'suggestion': '• 기간/지역 범위 변경 후 재분석'
        })

    # 최대 5개만 반환 (혹시 5개 초과 시 잘라냄)
    return insights[:5]


def get_detail_table(base_ym, compare_ym, sido=None, region_nm=None, sigungu_level='basic'):
    """
    ============================================================================
    상세 테이블 데이터 조회 함수 (get_detail_table)
    ============================================================================

    대시보드 하단의 상세 테이블에 표시할 데이터를 조회합니다.
    DataTables.js로 렌더링되며, 인구/1인가구 변화량과 관련 지표를 포함합니다.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         집계 레벨 결정 로직                               │
    ├─────────────────────────────────────────────────────────────────────────┤
    │  조건                          │  결과                                   │
    │ ──────────────────────────────┼───────────────────────────────────────── │
    │  sido=None, region_nm=None    │  전국 → 17개 시도별 집계                │
    │  region_nm='__all_regions__'  │  권역별 → 5개 권역별 집계               │
    │  sido='서울특별시' 등         │  시도 → 해당 시도의 시군구별 집계       │
    └─────────────────────────────────────────────────────────────────────────┘

    반환 컬럼:
        - 시도코드/시군구코드: 행정구역 코드 (정렬 기준)
        - 시도명/시군구명: 행정구역명
        - 현재인구, 비교인구: 기준/비교 시점 총인구
        - 인구변화, 인구변화율: 인구 증감 (명, %)
        - 현재1인가구, 비교1인가구: 기준/비교 시점 1인가구수
        - 1인가구변화, 1인가구변화율: 1인가구 증감 (가구, %)
        - 차이지수: |인구변화율 - 1인가구변화율| (괴리 정도)
        - 고령화율: 65세 이상 인구 비율 (%)
        - 1인가구비율: 1인가구 / 총인구 (%)

    Args:
        base_ym (str): 기준 시점 (YYYYMM)
        compare_ym (str): 비교 시점 (YYYYMM)
        sido (str, optional): 시도명 필터
        region_nm (str, optional): 권역명 필터
        sigungu_level (str): 'basic' 또는 'include_sub'

    Returns:
        list[dict]: 테이블 데이터 (딕셔너리 리스트, DataTables 형식)
    """
    engine = get_db_engine()

    # 전국 선택 시 시도별 집계 (dim_admin_area에서 sido_code 조회)
    if not sido and not region_nm:
        df = pd.read_sql(f"""
            WITH sido_master AS (
                SELECT sido_nm, MIN(sido_code) as sido_code
                FROM dim_admin_area
                WHERE sido_code IS NOT NULL
                GROUP BY sido_nm
            ),
            base_data AS (
                SELECT
                    c.sido_nm,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                    SUM(COALESCE(c.elderly_pop, 0)) as elderly_pop
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{base_ym}'
                GROUP BY c.sido_nm
            ),
            compare_data AS (
                SELECT
                    c.sido_nm,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{compare_ym}'
                GROUP BY c.sido_nm
            )
            SELECT
                COALESCE(s.sido_code, '00') as "시도코드",
                b.sido_nm as "시도명",
                b.total_pop as "현재인구",
                c.total_pop as "비교인구",
                b.total_pop - c.total_pop as "인구변화",
                ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) as "인구변화율",
                b.single_cnt as "현재1인가구",
                c.single_cnt as "비교1인가구",
                b.single_cnt - c.single_cnt as "1인가구변화",
                ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2) as "1인가구변화율",
                ABS(ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) -
                    ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2)) as "차이지수",
                ROUND(b.elderly_pop::numeric / NULLIF(b.total_pop, 0) * 100, 1) as "고령화율",
                ROUND(b.single_cnt::numeric / NULLIF(b.total_pop, 0) * 100, 1) as "1인가구비율"
            FROM base_data b
            JOIN compare_data c ON b.sido_nm = c.sido_nm
            LEFT JOIN sido_master s ON b.sido_nm = s.sido_nm
            ORDER BY s.sido_code
        """, engine)
    # 권역별 선택 시 권역별 집계 (dim_admin_area에서 region 정보 조회)
    elif region_nm == '__all_regions__':
        df = pd.read_sql(f"""
            WITH region_master AS (
                SELECT DISTINCT region_code, region_nm
                FROM dim_admin_area
                WHERE region_nm IS NOT NULL
            ),
            base_data AS (
                SELECT
                    a.region_code,
                    a.region_nm,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                    SUM(COALESCE(c.elderly_pop, 0)) as elderly_pop
                FROM cache_sigungu_indicators c
                JOIN dim_admin_area a ON c.sigungu_code = a.sigungu_code
                    AND a.eupmyeondong_nm IS NULL
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{base_ym}'
                  AND a.region_nm IS NOT NULL
                GROUP BY a.region_code, a.region_nm
            ),
            compare_data AS (
                SELECT
                    a.region_code,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt
                FROM cache_sigungu_indicators c
                JOIN dim_admin_area a ON c.sigungu_code = a.sigungu_code
                    AND a.eupmyeondong_nm IS NULL
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{compare_ym}'
                  AND a.region_nm IS NOT NULL
                GROUP BY a.region_code
            )
            SELECT
                b.region_code as "권역코드",
                b.region_nm as "권역명",
                b.total_pop as "현재인구",
                c.total_pop as "비교인구",
                b.total_pop - c.total_pop as "인구변화",
                ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) as "인구변화율",
                b.single_cnt as "현재1인가구",
                c.single_cnt as "비교1인가구",
                b.single_cnt - c.single_cnt as "1인가구변화",
                ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2) as "1인가구변화율",
                ABS(ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) -
                    ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2)) as "차이지수",
                ROUND(b.elderly_pop::numeric / NULLIF(b.total_pop, 0) * 100, 1) as "고령화율",
                ROUND(b.single_cnt::numeric / NULLIF(b.total_pop, 0) * 100, 1) as "1인가구비율"
            FROM base_data b
            JOIN compare_data c ON b.region_code = c.region_code
            ORDER BY b.region_code
        """, engine)
    # 시도 선택 시 시군구별 집계
    elif sigungu_level == 'basic':
        # 기본 모드: 4자리 그룹화 후 dim_admin_area에서 이름 조회
        df = pd.read_sql(f"""
            WITH base_data AS (
                SELECT
                    LEFT(c.sigungu_code, 4) as sigungu_group,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt,
                    SUM(COALESCE(c.elderly_pop, 0)) as elderly_pop
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{base_ym}'
                  AND c.sido_nm = '{sido}'
                GROUP BY LEFT(c.sigungu_code, 4)
            ),
            compare_data AS (
                SELECT
                    LEFT(c.sigungu_code, 4) as sigungu_group,
                    SUM(c.total_pop) as total_pop,
                    SUM(COALESCE(c.single_cnt, 0)) as single_cnt
                FROM cache_sigungu_indicators c
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{compare_ym}'
                  AND c.sido_nm = '{sido}'
                GROUP BY LEFT(c.sigungu_code, 4)
            ),
            area_names AS (
                SELECT DISTINCT ON (LEFT(sigungu_code, 4))
                    LEFT(sigungu_code, 4) as sigungu_group,
                    sigungu_code,
                    SPLIT_PART(sigungu_nm, ' ', 1) as sigungu_nm
                FROM dim_admin_area
                WHERE sigungu_code LIKE '____0'
                ORDER BY LEFT(sigungu_code, 4), sigungu_code
            )
            SELECT
                COALESCE(a.sigungu_code, b.sigungu_group || '0') as "시군구코드",
                COALESCE(a.sigungu_nm, b.sigungu_group || '0') as "시군구",
                b.total_pop as "현재인구",
                c.total_pop as "비교인구",
                b.total_pop - c.total_pop as "인구변화",
                ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) as "인구변화율",
                b.single_cnt as "현재1인가구",
                c.single_cnt as "비교1인가구",
                b.single_cnt - c.single_cnt as "1인가구변화",
                ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2) as "1인가구변화율",
                ABS(ROUND((b.total_pop - c.total_pop)::numeric / NULLIF(c.total_pop, 0) * 100, 2) -
                    ROUND((b.single_cnt - c.single_cnt)::numeric / NULLIF(c.single_cnt, 0) * 100, 2)) as "차이지수",
                ROUND(b.elderly_pop::numeric / NULLIF(b.total_pop, 0) * 100, 1) as "고령화율",
                ROUND(b.single_cnt::numeric / NULLIF(b.total_pop, 0) * 100, 1) as "1인가구비율"
            FROM base_data b
            JOIN compare_data c ON b.sigungu_group = c.sigungu_group
            LEFT JOIN area_names a ON b.sigungu_group = a.sigungu_group
            ORDER BY COALESCE(a.sigungu_code, b.sigungu_group || '0')
        """, engine)
    else:
        # 하위포함 모드
        df = pd.read_sql(f"""
            SELECT
                c1.sigungu_code as "시군구코드",
                c1.sigungu_nm as "시군구",
                c1.total_pop as "현재인구",
                c2.total_pop as "비교인구",
                c1.total_pop - c2.total_pop as "인구변화",
                ROUND((c1.total_pop - c2.total_pop)::numeric / NULLIF(c2.total_pop, 0) * 100, 2) as "인구변화율",
                COALESCE(c1.single_cnt, 0) as "현재1인가구",
                COALESCE(c2.single_cnt, 0) as "비교1인가구",
                COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0) as "1인가구변화",
                ROUND((COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0))::numeric /
                      NULLIF(COALESCE(c2.single_cnt, 0), 0) * 100, 2) as "1인가구변화율",
                ABS(ROUND((c1.total_pop - c2.total_pop)::numeric / NULLIF(c2.total_pop, 0) * 100, 2) -
                    ROUND((COALESCE(c1.single_cnt, 0) - COALESCE(c2.single_cnt, 0))::numeric /
                          NULLIF(COALESCE(c2.single_cnt, 0), 0) * 100, 2)) as "차이지수",
                c1.elderly_ratio as "고령화율",
                COALESCE(c1.single_ratio, 0) as "1인가구비율"
            FROM cache_sigungu_indicators c1
            JOIN cache_sigungu_indicators c2
                ON c1.sigungu_code = c2.sigungu_code
            WHERE TO_CHAR(c1.base_ym, 'YYYYMM') = '{base_ym}'
              AND TO_CHAR(c2.base_ym, 'YYYYMM') = '{compare_ym}'
              AND c1.sido_nm = '{sido}'
            ORDER BY c1.sigungu_code
        """, engine)

    df = df.fillna(0)
    return df.to_dict('records')


def render(request_args=None):
    """대시보드 렌더링"""
    if request_args is None:
        request_args = {}

    # API 요청 처리
    api_type = request_args.get('api')
    if api_type:
        return handle_api_request(api_type, request_args)

    # 필터 옵션
    filters = get_filter_options()
    base_ym_list = filters['base_ym_list']
    sido_list = filters['sido_list']
    region_list = filters['region_list']
    age_categories = filters['age_categories']

    # 메뉴 아이템
    menu_items = MenuGenerator.get_category_menu_items(POP_BASE)

    # 기본값 설정
    default_base_ym = base_ym_list[0] if base_ym_list else '202512'
    default_compare_ym = base_ym_list[1] if len(base_ym_list) > 1 else '202412'

    # HTML 반환
    return generate_html(base_ym_list, sido_list, region_list, age_categories, default_base_ym, default_compare_ym, menu_items)


def export_dashboard_results(base_ym, compare_ym, sido, region_nm, sigungu_level, age_category):
    """대시보드 결과를 이미지, MD, HTML 파일로 내보내기"""
    try:
        # 출력 폴더 생성
        output_dir = POP_BASE / 'output'
        images_dir = output_dir / 'images'
        output_dir.mkdir(exist_ok=True)
        images_dir.mkdir(exist_ok=True)

        # 타임스탬프와 지역명 설정
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        region_name = sido if sido else ('권역별' if region_nm == '__all_regions__' else '전국')
        file_prefix = f"edu_dash1_{region_name}_{base_ym}_{timestamp}"

        # 데이터 수집
        # 1. 요약 데이터
        summary = get_summary_data(base_ym, compare_ym, sido, region_nm, None, sigungu_level)

        # 2. 연령대별 변화 차트 (matplotlib)
        age_cat_names = {1: '5세별', 2: '10세별', 3: '정책연령'}
        age_cat_name = age_cat_names.get(age_category, '정책연령')
        pop_change = get_age_group_change(base_ym, compare_ym, sido, region_nm, None, sigungu_level, age_category)
        single_change = get_age_group_single_household(base_ym, compare_ym, sido, region_nm, sigungu_level, age_category)
        bar_chart_img = create_age_bar_chart(pop_change, single_change, age_cat_name, base_ym, compare_ym)

        # 3. 인사이트
        insights = generate_insights(base_ym, compare_ym, sido, region_nm, sigungu_level)

        # 4. 상세 테이블
        detail_data = get_detail_table(base_ym, compare_ym, sido, region_nm, sigungu_level)

        # 5. 현황 차트 (5세별, matplotlib) - 테이블이 없을 수 있으므로 예외 처리
        try:
            pop_data_5, single_data_5 = get_age_5year_data(base_ym, sido, region_nm, sigungu_level)
            gender_data = get_gender_age_data(base_ym, sido, region_nm, sigungu_level)
            donut_chart_img = create_donut_charts(pop_data_5, single_data_5, region_name, base_ym)
            pyramid_chart_img = create_population_pyramid(gender_data, region_name, base_ym)
            comparison_chart_img = create_age_comparison_chart(pop_data_5, single_data_5, region_name, base_ym)
            gender_detail_chart_img = create_gender_detail_charts(gender_data, region_name, base_ym)
        except Exception as e:
            print(f"[export] 현황 차트 생성 오류 (무시): {e}")
            donut_chart_img = None
            pyramid_chart_img = None
            comparison_chart_img = None
            gender_detail_chart_img = None

        # 이미지 저장 (matplotlib으로 생성된 차트만)
        saved_images = {}
        chart_images = {
            'bar_chart': bar_chart_img,
            'donut_chart': donut_chart_img,
            'pyramid_chart': pyramid_chart_img,
            'comparison_chart': comparison_chart_img,
            'gender_detail_chart': gender_detail_chart_img
        }

        for chart_name, img_base64 in chart_images.items():
            if img_base64:
                img_path = images_dir / f"{file_prefix}_{chart_name}.png"
                img_data = base64.b64decode(img_base64)
                with open(img_path, 'wb') as f:
                    f.write(img_data)
                saved_images[chart_name] = str(img_path.relative_to(output_dir))

        # 연령 카테고리명
        age_cat_names = {1: '5세별', 2: '10세별', 3: '정책연령'}
        age_cat_name = age_cat_names.get(age_category, '정책연령')

        # MD 파일 생성
        md_content = generate_export_md(
            region_name, base_ym, compare_ym, age_cat_name, sigungu_level,
            summary, insights, detail_data, saved_images, timestamp
        )
        md_path = output_dir / f"{file_prefix}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        # HTML 파일 생성
        html_content = generate_export_html(
            region_name, base_ym, compare_ym, age_cat_name, sigungu_level,
            summary, insights, detail_data, chart_images, timestamp
        )
        html_path = output_dir / f"{file_prefix}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return {
            'success': True,
            'message': f'내보내기 완료',
            'files': {
                'md': str(md_path.relative_to(POP_BASE)),
                'html': str(html_path.relative_to(POP_BASE)),
                'images': list(saved_images.values())
            },
            'output_dir': str(output_dir)
        }

    except Exception as e:
        import traceback
        print(f"[export] 오류: {e}")
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def generate_export_md(region_name, base_ym, compare_ym, age_cat_name, sigungu_level, summary, insights, detail_data, saved_images, timestamp):
    """내보내기용 마크다운 생성"""
    sigungu_text = '기본(대표)' if sigungu_level == 'basic' else '하위포함'
    base_ym_fmt = f"{base_ym[:4]}.{base_ym[4:]}"
    compare_ym_fmt = f"{compare_ym[:4]}.{compare_ym[4:]}"

    md = f"""# 연령대별 인구-1인가구 특이점 발견 대시보드

**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 조회 조건

| 항목 | 값 |
|------|-----|
| 지역 | {region_name} |
| 기준시점 | {base_ym_fmt} |
| 비교시점 | {compare_ym_fmt} |
| 연령구분 | {age_cat_name} |
| 시군구구분 | {sigungu_text} |

---

## 요약 지표

| 지표 | 값 |
|------|-----|
| 총인구 | {summary.get('total_pop', 0):,}명 |
| 인구변화율 | {summary.get('pop_change_rate', 0):.2f}% |
| 1인가구수 | {summary.get('single_cnt', 0):,}가구 |
| 1인가구변화율 | {summary.get('single_change_rate', 0):.2f}% |
| 고령화율 | {summary.get('elderly_ratio', 0):.1f}% |
| 1인가구비율 | {summary.get('single_ratio', 0):.1f}% |

---

## 주요 인사이트

"""
    for i, insight in enumerate(insights, 1):
        if isinstance(insight, dict):
            title = insight.get('title', '')
            content = insight.get('content', '').replace('\n', ' ')
            suggestion = insight.get('suggestion', '').replace('\n', ' ')
            md += f"{i}. **{title}**: {content} {suggestion}\n"
        else:
            md += f"{i}. {insight}\n"

    md += "\n---\n\n## 차트\n\n"

    chart_titles = {
        'bar_chart': '연령대별 인구 vs 1인가구 변화율',
        'donut_chart': '5세별 인구/1인가구 구성',
        'pyramid_chart': '인구 피라미드',
        'comparison_chart': '연령별 인구 vs 1인가구 비교',
        'gender_detail_chart': '연령별 남녀 1인가구 상세'
    }

    # 차트 순서 지정
    chart_order = ['bar_chart', 'donut_chart', 'pyramid_chart', 'comparison_chart', 'gender_detail_chart']
    for chart_name in chart_order:
        img_path = saved_images.get(chart_name)
        if not img_path:
            continue
        title = chart_titles.get(chart_name, chart_name)
        md += f"### {title}\n\n"
        md += f"![{title}]({img_path})\n\n"

    md += "---\n\n## 상세 데이터\n\n"

    if detail_data:
        # 테이블 헤더
        headers = list(detail_data[0].keys())
        md += "| " + " | ".join(headers) + " |\n"
        md += "|" + "|".join(["---"] * len(headers)) + "|\n"

        # 테이블 데이터 (상위 20개)
        for row in detail_data[:20]:
            values = []
            for h in headers:
                val = row.get(h, '')
                if isinstance(val, (int, float)):
                    if 'rate' in h.lower() or '율' in h or '지수' in h:
                        values.append(f"{val:.2f}")
                    else:
                        values.append(f"{val:,}" if isinstance(val, int) else f"{val:.0f}")
                else:
                    values.append(str(val))
            md += "| " + " | ".join(values) + " |\n"

        if len(detail_data) > 20:
            md += f"\n*... 외 {len(detail_data) - 20}개 항목*\n"

    md += "\n---\n\n*본 보고서는 연령대별 인구-1인가구 특이점 발견 대시보드에서 자동 생성되었습니다.*\n"

    return md


def generate_export_html(region_name, base_ym, compare_ym, age_cat_name, sigungu_level, summary, insights, detail_data, chart_images, timestamp):
    """내보내기용 HTML 생성"""
    sigungu_text = '기본(대표)' if sigungu_level == 'basic' else '하위포함'
    base_ym_fmt = f"{base_ym[:4]}.{base_ym[4:]}"
    compare_ym_fmt = f"{compare_ym[:4]}.{compare_ym[4:]}"

    # 인사이트 HTML
    insights_items = []
    for insight in insights:
        if isinstance(insight, dict):
            title = insight.get('title', '')
            content = insight.get('content', '').replace('\n', '<br>')
            suggestion = insight.get('suggestion', '').replace('\n', '<br>')
            insights_items.append(f'<li class="mb-2"><strong>{title}</strong>: {content} <em>{suggestion}</em></li>')
        else:
            insights_items.append(f'<li class="mb-2">{insight}</li>')
    insights_html = '\n'.join(insights_items)

    # 차트 이미지 HTML
    chart_titles = {
        'bar_chart': '연령대별 인구 vs 1인가구 변화율',
        'donut_chart': '5세별 인구/1인가구 구성',
        'pyramid_chart': '인구 피라미드',
        'comparison_chart': '연령별 인구 vs 1인가구 비교',
        'gender_detail_chart': '연령별 남녀 1인가구 상세'
    }

    charts_html = ""
    chart_order = ['bar_chart', 'donut_chart', 'pyramid_chart', 'comparison_chart', 'gender_detail_chart']
    for chart_name in chart_order:
        img_base64 = chart_images.get(chart_name)
        if img_base64:
            title = chart_titles.get(chart_name, chart_name)
            charts_html += f'''
            <div class="chart-section">
                <h3>{title}</h3>
                <img src="data:image/png;base64,{img_base64}" alt="{title}" style="max-width:100%;">
            </div>
            '''

    # 테이블 HTML
    table_html = ""
    if detail_data:
        headers = list(detail_data[0].keys())
        header_row = ''.join([f'<th>{h}</th>' for h in headers])

        rows_html = ""
        for row in detail_data[:30]:
            cells = []
            for h in headers:
                val = row.get(h, '')
                if isinstance(val, (int, float)):
                    if 'rate' in h.lower() or '율' in h or '지수' in h:
                        cells.append(f'<td>{val:.2f}</td>')
                    else:
                        cells.append(f'<td>{val:,.0f}</td>' if isinstance(val, int) else f'<td>{val:.0f}</td>')
                else:
                    cells.append(f'<td>{val}</td>')
            rows_html += '<tr>' + ''.join(cells) + '</tr>\n'

        table_html = f'''
        <table class="data-table">
            <thead><tr>{header_row}</tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        '''
        if len(detail_data) > 30:
            table_html += f'<p class="text-muted">... 외 {len(detail_data) - 30}개 항목</p>'

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>연령대별 인구-1인가구 특이점 발견 대시보드 - {region_name}</title>
    <style>
        :root {{
            --primary: #1D64F2;
            --primary-dark: #1243A6;
            --dark: #011C40;
            --accent: #F24822;
        }}
        body {{
            font-family: 'Pretendard', 'Noto Sans KR', -apple-system, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: var(--primary-dark);
            border-bottom: 3px solid var(--primary);
            padding-bottom: 10px;
        }}
        h2 {{
            color: var(--primary);
            margin-top: 30px;
            border-left: 4px solid var(--primary);
            padding-left: 10px;
        }}
        h3 {{
            color: var(--dark);
            margin-top: 20px;
        }}
        .meta-info {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .meta-info table {{
            width: 100%;
        }}
        .meta-info td {{
            padding: 5px 10px;
        }}
        .meta-info td:first-child {{
            font-weight: bold;
            width: 120px;
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card .label {{
            font-size: 0.85rem;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 1.5rem;
            font-weight: bold;
            margin-top: 5px;
        }}
        .insights-list {{
            background: #fff8e1;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #ffc107;
        }}
        .insights-list li {{
            margin-bottom: 10px;
        }}
        .chart-section {{
            margin: 30px 0;
            text-align: center;
        }}
        .chart-section img {{
            max-width: 100%;
            border: 1px solid #eee;
            border-radius: 8px;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 0.85rem;
        }}
        .data-table th, .data-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: right;
        }}
        .data-table th {{
            background: var(--primary);
            color: white;
            text-align: center;
        }}
        .data-table tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        .data-table td:first-child, .data-table td:nth-child(2) {{
            text-align: left;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 0.85rem;
        }}
        .text-muted {{
            color: #666;
            font-size: 0.9rem;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .container {{ box-shadow: none; }}
            .chart-section {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 연령대별 인구-1인가구 특이점 발견 대시보드</h1>

        <div class="meta-info">
            <table>
                <tr><td>지역</td><td>{region_name}</td></tr>
                <tr><td>기준시점</td><td>{base_ym_fmt}</td></tr>
                <tr><td>비교시점</td><td>{compare_ym_fmt}</td></tr>
                <tr><td>연령구분</td><td>{age_cat_name}</td></tr>
                <tr><td>시군구구분</td><td>{sigungu_text}</td></tr>
                <tr><td>생성일시</td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>
        </div>

        <h2>📈 요약 지표</h2>
        <div class="summary-cards">
            <div class="summary-card">
                <div class="label">총인구</div>
                <div class="value">{summary.get('total_pop', 0):,}</div>
            </div>
            <div class="summary-card">
                <div class="label">인구변화율</div>
                <div class="value">{summary.get('pop_change_rate', 0):.2f}%</div>
            </div>
            <div class="summary-card">
                <div class="label">1인가구수</div>
                <div class="value">{summary.get('single_cnt', 0):,}</div>
            </div>
            <div class="summary-card">
                <div class="label">1인가구변화율</div>
                <div class="value">{summary.get('single_change_rate', 0):.2f}%</div>
            </div>
            <div class="summary-card">
                <div class="label">고령화율</div>
                <div class="value">{summary.get('elderly_ratio', 0):.1f}%</div>
            </div>
            <div class="summary-card">
                <div class="label">1인가구비율</div>
                <div class="value">{summary.get('single_ratio', 0):.1f}%</div>
            </div>
        </div>

        <h2>💡 주요 인사이트</h2>
        <div class="insights-list">
            <ol>{insights_html}</ol>
        </div>

        <h2>📊 분석 차트</h2>
        {charts_html}

        <h2>📋 상세 데이터</h2>
        {table_html}

        <div class="footer">
            <p>본 보고서는 연령대별 인구-1인가구 특이점 발견 대시보드에서 자동 생성되었습니다.</p>
        </div>
    </div>
</body>
</html>'''

    return html


def handle_api_request(api_type, request_args):
    """API 요청 처리"""
    base_ym = request_args.get('base_ym', '202512')
    compare_ym = request_args.get('compare_ym', '202412')
    sido = request_args.get('sido', '')
    region_nm = request_args.get('region_nm', '')
    sigungu_level = request_args.get('sigungu_level', 'basic')
    age_category = int(request_args.get('age_category', '3'))  # 카테고리 번호 (1=5세별, 2=10세별, 3=정책연령)

    try:
        if api_type == 'filters_regions':
            data = get_regions_by_sido(sido)
        elif api_type == 'filters_sigungu':
            data = get_sigungu_by_sido(sido, region_nm, sigungu_level == 'detail')
        elif api_type == 'filters_age_categories':
            filters = get_filter_options()
            data = filters['age_categories']
        elif api_type == 'summary':
            data = get_summary_data(base_ym, compare_ym, sido, region_nm, None, sigungu_level)
        elif api_type == 'age_change':
            data = get_age_group_change(base_ym, compare_ym, sido, region_nm, None, sigungu_level, age_category)
        elif api_type == 'divergence':
            data = get_divergence_data(base_ym, compare_ym, sido, region_nm, sigungu_level)
        elif api_type == 'trend':
            data = get_trend_data(sido, region_nm, sigungu_level)
        elif api_type == 'heatmap':
            data = get_heatmap_data(base_ym, compare_ym, sido, region_nm, sigungu_level, age_category)
        elif api_type == 'insights':
            data = generate_insights(base_ym, compare_ym, sido, region_nm, sigungu_level)
        elif api_type == 'detail':
            data = get_detail_table(base_ym, compare_ym, sido, region_nm, sigungu_level)
        elif api_type == 'bar_chart':
            # 연령대별 인구/1인가구 묶음 막대그래프 (matplotlib)
            pop_data = get_age_group_change(base_ym, compare_ym, sido, region_nm, None, sigungu_level, age_category)
            single_data = get_age_group_single_household(base_ym, compare_ym, sido, region_nm, sigungu_level, age_category)
            age_cat_names = {1: '5세별', 2: '10세별', 3: '정책연령'}
            age_cat_name = age_cat_names.get(age_category, '정책연령')
            img_base64 = create_age_bar_chart(pop_data, single_data, age_cat_name, base_ym, compare_ym)
            data = {
                'image': img_base64,
                'pop_data': pop_data,
                'single_data': single_data
            }
        elif api_type == 'age_table':
            # 연령대별 인구/1인가구 테이블 데이터
            pop_data = get_age_group_change(base_ym, compare_ym, sido, region_nm, None, sigungu_level, age_category)
            single_data = get_age_group_single_household(base_ym, compare_ym, sido, region_nm, sigungu_level, age_category)
            single_dict = {d['age_group']: d for d in single_data}
            table_data = []
            for p in pop_data:
                s = single_dict.get(p['age_group'], {})
                table_data.append({
                    '연령대': p['age_group'],
                    '인구(기준)': int(p.get('base_value', 0)),
                    '인구(비교)': int(p.get('compare_value', 0)),
                    '인구변화': int(p.get('change', 0)),
                    '인구변화율': p.get('change_rate', 0),
                    '1인가구(기준)': int(s.get('base_value', 0)),
                    '1인가구(비교)': int(s.get('compare_value', 0)),
                    '1인가구변화': int(s.get('change', 0)),
                    '1인가구변화율': s.get('change_rate', 0)
                })
            data = table_data
        elif api_type == 'status_charts':
            # 현황 차트 데이터 (도넛, 피라미드, 비교, 상세)
            region_name = sido if sido else ('권역별' if region_nm == '__all_regions__' else '전국')

            # 5세별 데이터
            try:
                pop_data, single_data = get_age_5year_data(base_ym, sido, region_nm, sigungu_level)
            except Exception as e:
                print(f"[status_charts] get_age_5year_data 오류: {e}")
                pop_data, single_data = [], []

            # 성별 데이터
            try:
                gender_data = get_gender_age_data(base_ym, sido, region_nm, sigungu_level)
            except Exception as e:
                print(f"[status_charts] get_gender_age_data 오류: {e}")
                gender_data = []

            print(f"[status_charts] pop_data: {len(pop_data)}건, single_data: {len(single_data)}건, gender_data: {len(gender_data)}건")

            # 차트 생성
            try:
                donut_chart = create_donut_charts(pop_data, single_data, region_name, base_ym)
            except Exception as e:
                print(f"[status_charts] donut_chart 오류: {e}")
                donut_chart = None
            try:
                pyramid_chart = create_population_pyramid(gender_data, region_name, base_ym)
            except Exception as e:
                print(f"[status_charts] pyramid_chart 오류: {e}")
                pyramid_chart = None
            try:
                comparison_chart = create_age_comparison_chart(pop_data, single_data, region_name, base_ym)
            except Exception as e:
                print(f"[status_charts] comparison_chart 오류: {e}")
                comparison_chart = None
            try:
                gender_detail_chart = create_gender_detail_charts(gender_data, region_name, base_ym)
            except Exception as e:
                print(f"[status_charts] gender_detail_chart 오류: {e}")
                gender_detail_chart = None

            data = {
                'donut_chart': donut_chart,
                'pyramid_chart': pyramid_chart,
                'comparison_chart': comparison_chart,
                'gender_detail_chart': gender_detail_chart,
                'region_name': region_name,
                'total_pop': sum(d['value'] for d in pop_data) if pop_data else 0,
                'total_single': sum(d['value'] for d in single_data) if single_data else 0
            }
        elif api_type == 'export':
            # 내보내기 기능 - 이미지, MD, HTML 파일 저장
            data = export_dashboard_results(base_ym, compare_ym, sido, region_nm, sigungu_level, age_category)
        else:
            data = {'error': 'Unknown API type'}

        return Response(
            json.dumps(data, ensure_ascii=False, default=str),
            mimetype='application/json; charset=utf-8'
        )
    except Exception as e:
        return Response(
            json.dumps({'error': str(e)}, ensure_ascii=False),
            mimetype='application/json; charset=utf-8'
        )


def generate_html(base_ym_list, sido_list, region_list, age_categories, default_base_ym, default_compare_ym, menu_items):
    """HTML 페이지 생성"""

    # 기준년월 옵션
    base_ym_options = '\n'.join([
        f'<option value="{ym}" {"selected" if ym == default_base_ym else ""}>{ym[:4]}.{ym[4:]}</option>'
        for ym in base_ym_list
    ])

    compare_ym_options = '\n'.join([
        f'<option value="{ym}" {"selected" if ym == default_compare_ym else ""}>{ym[:4]}.{ym[4:]}</option>'
        for ym in base_ym_list
    ])

    # 지역범위 옵션 (전국 + 권역별 + 시도별)
    sido_options = '<option value="">전국</option>\n'
    sido_options += '<option value="__all_regions__">권역별</option>\n'
    sido_options += '\n'.join([f'<option value="{s}">{s}</option>' for s in sido_list])

    # 연령 카테고리 옵션 (DB에서 조회)
    age_category_options = '\n'.join([
        f'<option value="{cat["category"]}" {"selected" if cat["category"] == 3 else ""}>{cat["category_name"]}</option>'
        for cat in age_categories
    ])

    # 메뉴 HTML 생성
    menu_html = ''.join([
        f'''<a href="{item['url']}" class="px-3 py-1 text-sm {'bg-white/20' if 'edu_dash1' in item['url'] else 'hover:bg-white/10'} rounded transition">{item['name']}</a>'''
        for item in menu_items
    ])

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>연령대별 인구-1인가구 특이점 발견 대시보드</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <style>
        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; }}
        .card {{ background: white; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        .metric-value {{ font-size: 1.75rem; font-weight: 700; }}
        .metric-change.positive {{ color: #10B981; }}
        .metric-change.negative {{ color: #EF4444; }}
        .insight-card {{ border-left: 4px solid #3B82F6; }}
        .text-right {{ text-align: right !important; }}
        .plotly-chart {{ width: 100%; min-height: 350px; }}
        .dataTables_wrapper {{ overflow-x: auto; }}
        #detailTable {{ width: 100% !important; }}
        #heatmapTable th, #heatmapTable td {{ font-size: 11px; white-space: nowrap; }}
        /* 전체 화면 로딩 오버레이 (대시보드1.py 스타일) */
        .loading-overlay {{ display: flex; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.95); z-index: 9999; justify-content: center; align-items: center; flex-direction: column; }}
        .loading-overlay.hidden {{ display: none; }}
        .loading-spinner {{ width: 50px; height: 50px; border: 5px solid #e0e0e0; border-top: 5px solid #3B82F6; border-radius: 50%; animation: spin 1s linear infinite; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .loading-text {{ margin-top: 1rem; font-size: 1rem; color: #333; font-weight: 500; }}
        .loading-subtext {{ margin-top: 0.5rem; font-size: 0.85rem; color: #666; }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <!-- 로딩 오버레이 -->
    <div id="loadingOverlay" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">대시보드를 준비하고 있습니다</div>
        <div class="loading-subtext">데이터를 불러오는 중입니다. 잠시만 기다려주세요...</div>
    </div>

    <!-- 헤더 -->
    <header class="bg-gradient-to-r from-blue-800 to-blue-600 text-white py-3 px-6 shadow-lg">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-between items-center">
                <h1 class="text-lg font-bold">연령대별 인구-1인가구 특이점 발견 대시보드</h1>
                <div class="flex items-center gap-2">
                    <nav class="flex gap-1">{menu_html}</nav>
                    <a href="/" class="bg-white/20 hover:bg-white/30 px-3 py-1 rounded text-sm transition">홈</a>
                </div>
            </div>
        </div>
    </header>

    <!-- 필터 영역 -->
    <div class="bg-white shadow-md sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 py-4">
            <div class="flex flex-wrap gap-4 items-end">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">기준시점</label>
                    <select id="baseYm" class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
                        {base_ym_options}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">비교시점</label>
                    <select id="compareYm" class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
                        {compare_ym_options}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">지역범위</label>
                    <select id="sido" class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
                        {sido_options}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">시군구구분</label>
                    <div class="flex gap-3">
                        <label class="inline-flex items-center">
                            <input type="radio" name="sigunguLevel" value="basic" checked class="text-blue-600">
                            <span class="ml-1 text-sm">기본(대표)</span>
                        </label>
                        <label class="inline-flex items-center">
                            <input type="radio" name="sigunguLevel" value="detail" class="text-blue-600">
                            <span class="ml-1 text-sm">하위포함</span>
                        </label>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">연령구분</label>
                    <select id="ageCategory" class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
                        {age_category_options}
                    </select>
                </div>
                <button id="searchBtn" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg text-sm font-medium transition">
                    조회
                </button>
                <button id="exportBtn" class="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg text-sm font-medium transition ml-2">
                    📥 내보내기
                </button>
            </div>
        </div>
    </div>

    <!-- 메인 컨텐츠 -->
    <main class="max-w-7xl mx-auto px-6 py-6">
        <!-- 요약 카드 -->
        <div id="summaryCards" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="card p-4">
                <div class="text-sm text-gray-500 mb-1">총인구</div>
                <div class="metric-value text-blue-600" id="totalPop">-</div>
                <div class="metric-change text-sm" id="popChange">-</div>
            </div>
            <div class="card p-4">
                <div class="text-sm text-gray-500 mb-1">1인가구수</div>
                <div class="metric-value text-green-600" id="singleCnt">-</div>
                <div class="metric-change text-sm" id="singleChange">-</div>
            </div>
            <div class="card p-4">
                <div class="text-sm text-gray-500 mb-1">고령화율</div>
                <div class="metric-value text-orange-600" id="elderlyRatio">-</div>
                <div class="text-xs text-gray-400">65세 이상</div>
            </div>
            <div class="card p-4">
                <div class="text-sm text-gray-500 mb-1">1인가구비율</div>
                <div class="metric-value text-purple-600" id="singleRatio">-</div>
                <div class="text-xs text-gray-400">전체 세대 대비</div>
            </div>
        </div>

        <!-- 현황 차트 섹션 -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">📊 5세별 인구/1인가구 구성 <span id="statusRegionName" class="text-blue-600"></span></h2>
            <div id="donutChartContainer" class="text-center">
                <img id="donutChartImg" src="" alt="5세별 도넛차트" style="max-width: 100%; height: auto;">
            </div>
        </div>

        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">📈 인구 피라미드 <span id="pyramidRegionName" class="text-blue-600"></span></h2>
            <div id="pyramidChartContainer" class="text-center">
                <img id="pyramidChartImg" src="" alt="인구 피라미드" style="max-width: 100%; height: auto;">
            </div>
        </div>

        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">📉 연령별 인구 vs 1인가구 비교 <span id="comparisonRegionName" class="text-blue-600"></span></h2>
            <div id="comparisonChartContainer" class="text-center">
                <img id="comparisonChartImg" src="" alt="연령별 비교 차트" style="max-width: 100%; height: auto;">
            </div>
            <p class="text-sm text-gray-600 mt-3 bg-gray-50 p-3 rounded">
                <span class="font-semibold">읽는 방법</span><br>
                • 파란색 막대 = 인구수 / 주황색 막대 = 1인가구수 / 빨간색 라인 = 1인가구 비율<br>
                <span class="font-semibold">핵심 포인트</span><br>
                • 라인이 높은 연령대 = 해당 연령대 1인가구 비율이 높음
            </p>
        </div>

        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">👥 연령별 남녀 1인가구 상세 <span id="genderRegionName" class="text-blue-600"></span></h2>
            <div id="genderDetailChartContainer" class="text-center">
                <img id="genderDetailChartImg" src="" alt="남녀 1인가구 상세" style="max-width: 100%; height: auto;">
            </div>
        </div>

        <!-- 차트 영역 1: 이중 막대그래프 (matplotlib) -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">연령대별 인구 vs 1인가구 변화율</h2>
            <div id="barChartContainer" class="text-center">
                <img id="barChartImg" src="" alt="연령대별 차트" style="max-width: 100%; height: auto;">
            </div>
            <p class="text-sm text-gray-600 mt-3 bg-gray-50 p-3 rounded">
                <span class="font-semibold">읽는 방법</span><br>
                • 파란색 = 인구 변화율 / 주황색 = 1인가구 변화율<br>
                • 두 막대의 방향·크기 차이가 클수록 변화 차이가 큼<br>
                <span class="font-semibold">핵심 포인트</span><br>
                • 인구↓(파란색) + 1인가구↑(주황색) 연령대 = 정책 우선 대상
            </p>
            <!-- 연령대별 테이블 -->
            <div class="mt-6">
                <h3 class="text-md font-semibold mb-3 text-gray-700">연령대별 인구 및 1인가구 상세</h3>
                <div class="overflow-x-auto">
                    <table id="ageTable" class="min-w-full text-sm border-collapse">
                        <thead class="bg-gray-100">
                            <tr>
                                <th class="px-3 py-2 border text-left">연령대</th>
                                <th class="px-3 py-2 border text-right">인구(기준)</th>
                                <th class="px-3 py-2 border text-right">인구(비교)</th>
                                <th class="px-3 py-2 border text-right">인구변화</th>
                                <th class="px-3 py-2 border text-right">인구변화율(%)</th>
                                <th class="px-3 py-2 border text-right">1인가구(기준)</th>
                                <th class="px-3 py-2 border text-right">1인가구(비교)</th>
                                <th class="px-3 py-2 border text-right">1인가구변화</th>
                                <th class="px-3 py-2 border text-right">1인가구변화율(%)</th>
                            </tr>
                        </thead>
                        <tbody id="ageTableBody">
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- 차트 영역 2: 추이 라인차트 -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">시점별 인구/1인가구 추이</h2>
            <div id="trendChart" class="plotly-chart"></div>
            <p class="text-sm text-gray-600 mt-3 bg-gray-50 p-3 rounded">
                <span class="font-semibold">읽는 방법</span><br>
                • 파란선 = 총인구 / 주황선 = 1인가구수<br>
                • 선의 방향(기울기)이 중요함<br>
                <span class="font-semibold">핵심 포인트</span><br>
                • 두 선이 벌어지거나 교차하는 시점 = 구조 변화 신호
            </p>
        </div>

        <!-- 차트 영역 3: 사분면 차트 -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">인구변화 vs 1인가구변화 사분면 분석</h2>
            <div id="quadrantChart" class="plotly-chart"></div>
            <p class="text-sm text-gray-600 mt-3 bg-gray-50 p-3 rounded">
                <span class="font-semibold">읽는 방법</span><br>
                • X축 = 인구 변화율 / Y축 = 1인가구 변화율<br>
                • 좌상단(빨강) = 인구↓ + 1인가구↑ → 불일치 지역<br>
                <span class="font-semibold">핵심 포인트</span><br>
                • 좌상단 지역 = 독립세대 증가 빠름 → 주거/복지 정책 시급
            </p>
        </div>

        <!-- 차트 영역 4: 차이지수 막대 -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">지역별 차이지수 (인구변화율 - 1인가구변화율)</h2>
            <div id="divergenceChart" class="plotly-chart"></div>
            <p class="text-sm text-gray-600 mt-3 bg-gray-50 p-3 rounded">
                <span class="font-semibold">읽는 방법</span><br>
                • 차이지수 = |인구변화율 - 1인가구변화율|<br>
                • 빨간색 = 인구↓ + 1인가구↑인 지역<br>
                <span class="font-semibold">핵심 포인트</span><br>
                • 막대가 길수록 인구와 1인가구 변화 차이가 큼
            </p>
        </div>

        <!-- 차트 영역 5: 히트맵 + 데이터 표 -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">지역 x 연령대 변화율 히트맵</h2>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div>
                    <div id="heatmapChart" class="plotly-chart"></div>
                </div>
                <div>
                    <div class="text-sm font-medium text-gray-700 mb-2">히트맵 데이터 표</div>
                    <div class="overflow-auto max-h-96">
                        <table id="heatmapTable" class="text-xs w-full border-collapse">
                            <thead class="bg-gray-100 sticky top-0"></thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </div>
            </div>
            <p class="text-sm text-gray-600 mt-3 bg-gray-50 p-3 rounded">
                <span class="font-semibold">읽는 방법</span><br>
                • 빨간색 = 증가 / 파란색 = 감소<br>
                • 색이 진할수록 변화 폭이 큼 (행=지역, 열=연령대)<br>
                <span class="font-semibold">핵심 포인트</span><br>
                • 특정 지역·연령대만 색이 진하면 = 집중 관리 대상
            </p>
        </div>

        <!-- 인사이트 -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">자동 생성 인사이트</h2>
            <div id="insights" class="space-y-4"></div>
        </div>

        <!-- 상세 테이블 -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">상세 데이터 테이블</h2>
            <div class="overflow-x-auto">
                <table id="detailTable" class="display compact stripe hover" style="width:100%">
                    <thead>
                        <tr>
                            <th>시군구코드</th>
                            <th>시군구</th>
                            <th>현재인구</th>
                            <th>비교인구</th>
                            <th>인구변화</th>
                            <th>인구변화율(%)</th>
                            <th>현재1인가구</th>
                            <th>비교1인가구</th>
                            <th>1인가구변화</th>
                            <th>1인가구변화율(%)</th>
                            <th>차이지수</th>
                            <th>고령화율(%)</th>
                            <th>1인가구비율(%)</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </main>

    <script>
        // 현재 페이지 URL 기반 API 경로
        const API_BASE = window.location.pathname;

        // 숫자 포맷
        function formatNumber(num) {{
            if (num === null || num === undefined) return '-';
            return Number(num).toLocaleString('ko-KR');
        }}

        // 변화율 표시
        function formatChange(rate) {{
            if (rate === null || rate === undefined || isNaN(rate)) return '-';
            const sign = rate >= 0 ? '+' : '';
            const cls = rate >= 0 ? 'positive' : 'negative';
            return `<span class="metric-change ${{cls}}">${{sign}}${{rate.toFixed(2)}}%</span>`;
        }}

        // API 호출
        async function fetchAPI(apiType, params = {{}}) {{
            const sidoValue = document.getElementById('sido').value;
            let sido = '';
            let regionNm = '';

            // 권역별 선택 처리
            if (sidoValue === '__all_regions__') {{
                regionNm = '__all_regions__';
            }} else {{
                sido = sidoValue;
            }}

            const queryParams = new URLSearchParams({{
                api: apiType,
                base_ym: document.getElementById('baseYm').value,
                compare_ym: document.getElementById('compareYm').value,
                sido: sido,
                region_nm: regionNm,
                sigungu_level: document.querySelector('input[name="sigunguLevel"]:checked').value,
                age_category: document.getElementById('ageCategory').value,
                ...params
            }});

            const response = await fetch(`${{API_BASE}}?${{queryParams}}`);
            return response.json();
        }}

        // 요약 카드 업데이트
        async function updateSummary() {{
            const data = await fetchAPI('summary');
            document.getElementById('totalPop').textContent = formatNumber(data.total_pop);
            document.getElementById('popChange').innerHTML = formatChange(data.pop_change_rate);
            document.getElementById('singleCnt').textContent = formatNumber(data.single_cnt);
            document.getElementById('singleChange').innerHTML = formatChange(data.single_change_rate);
            document.getElementById('elderlyRatio').textContent = data.elderly_ratio + '%';
            document.getElementById('singleRatio').textContent = data.single_ratio + '%';
        }}

        // 막대 차트 (연령대별 변화율) - matplotlib 이미지 + 테이블
        async function updateBarChart() {{
            const ageCatSelect = document.getElementById('ageCategory');
            const ageCatName = ageCatSelect.options[ageCatSelect.selectedIndex].text;

            // 차트 이미지 API 호출
            const chartData = await fetchAPI('bar_chart');
            if (!chartData || !chartData.image) {{
                document.getElementById('barChartImg').src = '';
                document.getElementById('ageTableBody').innerHTML = '<tr><td colspan="9" class="text-center text-gray-500 py-4">데이터가 없습니다.</td></tr>';
                return;
            }}

            // 이미지 업데이트
            document.getElementById('barChartImg').src = 'data:image/png;base64,' + chartData.image;
            console.log(`[barChart] 연령구분: ${{ageCatName}}, 인구데이터: ${{chartData.pop_data.length}}개, 1인가구데이터: ${{chartData.single_data.length}}개`);

            // 테이블 데이터 API 호출
            const tableData = await fetchAPI('age_table');
            if (tableData && tableData.length > 0) {{
                const tbody = document.getElementById('ageTableBody');
                tbody.innerHTML = tableData.map(row => `
                    <tr class="hover:bg-gray-50">
                        <td class="px-3 py-2 border">${{row['연령대']}}</td>
                        <td class="px-3 py-2 border text-right">${{row['인구(기준)'].toLocaleString()}}</td>
                        <td class="px-3 py-2 border text-right">${{row['인구(비교)'].toLocaleString()}}</td>
                        <td class="px-3 py-2 border text-right ${{row['인구변화'] > 0 ? 'text-blue-600' : row['인구변화'] < 0 ? 'text-red-600' : ''}}">${{row['인구변화'].toLocaleString()}}</td>
                        <td class="px-3 py-2 border text-right ${{row['인구변화율'] > 0 ? 'text-blue-600' : row['인구변화율'] < 0 ? 'text-red-600' : ''}}">${{row['인구변화율'].toFixed(2)}}</td>
                        <td class="px-3 py-2 border text-right">${{row['1인가구(기준)'].toLocaleString()}}</td>
                        <td class="px-3 py-2 border text-right">${{row['1인가구(비교)'].toLocaleString()}}</td>
                        <td class="px-3 py-2 border text-right ${{row['1인가구변화'] > 0 ? 'text-orange-600' : row['1인가구변화'] < 0 ? 'text-green-600' : ''}}">${{row['1인가구변화'].toLocaleString()}}</td>
                        <td class="px-3 py-2 border text-right ${{row['1인가구변화율'] > 0 ? 'text-orange-600' : row['1인가구변화율'] < 0 ? 'text-green-600' : ''}}">${{row['1인가구변화율'].toFixed(2)}}</td>
                    </tr>
                `).join('');
            }}
        }}

        // 추이 차트
        async function updateTrendChart() {{
            const data = await fetchAPI('trend');

            const trace1 = {{
                x: data.map(d => d.base_ym.substring(0,4) + '.' + d.base_ym.substring(4)),
                y: data.map(d => d.total_pop),
                type: 'scatter',
                mode: 'lines+markers',
                name: '총인구',
                yaxis: 'y',
                line: {{ color: '#3B82F6', width: 2 }}
            }};

            const trace2 = {{
                x: data.map(d => d.base_ym.substring(0,4) + '.' + d.base_ym.substring(4)),
                y: data.map(d => d.single_cnt),
                type: 'scatter',
                mode: 'lines+markers',
                name: '1인가구수',
                yaxis: 'y2',
                line: {{ color: '#10B981', width: 2 }}
            }};

            const layout = {{
                yaxis: {{ title: '총인구', titlefont: {{ color: '#3B82F6' }}, tickfont: {{ color: '#3B82F6' }} }},
                yaxis2: {{ title: '1인가구수', titlefont: {{ color: '#10B981' }}, tickfont: {{ color: '#10B981' }}, overlaying: 'y', side: 'right' }},
                margin: {{ t: 30, l: 80, r: 80, b: 50 }},
                legend: {{ x: 0.5, y: 1.1, xanchor: 'center', orientation: 'h' }},
                font: {{ family: 'Malgun Gothic' }}
            }};

            Plotly.newPlot('trendChart', [trace1, trace2], layout, {{responsive: true}});
        }}

        // 사분면 차트
        async function updateQuadrantChart() {{
            const data = await fetchAPI('divergence');

            const colors = data.map(d => {{
                if (d.pop_change_rate >= 0 && d.single_change_rate >= 0) return '#3B82F6';
                if (d.pop_change_rate < 0 && d.single_change_rate >= 0) return '#EF4444';
                if (d.pop_change_rate < 0 && d.single_change_rate < 0) return '#6B7280';
                return '#10B981';
            }});

            const trace = {{
                x: data.map(d => d.pop_change_rate),
                y: data.map(d => d.single_change_rate),
                text: data.map(d => d.sigungu_nm),
                mode: 'markers+text',
                type: 'scatter',
                textposition: 'top center',
                textfont: {{ size: 10 }},
                marker: {{ size: 12, color: colors }}
            }};

            const layout = {{
                xaxis: {{ title: '인구 변화율 (%)', zeroline: true, zerolinecolor: '#ccc', zerolinewidth: 2 }},
                yaxis: {{ title: '1인가구 변화율 (%)', zeroline: true, zerolinecolor: '#ccc', zerolinewidth: 2 }},
                margin: {{ t: 30, l: 60, r: 30, b: 60 }},
                font: {{ family: 'Malgun Gothic' }},
                annotations: [
                    {{ x: 5, y: 5, text: '인구+/1인가구+', showarrow: false, font: {{ size: 11, color: '#3B82F6' }} }},
                    {{ x: -5, y: 5, text: '인구-/1인가구+', showarrow: false, font: {{ size: 11, color: '#EF4444' }} }},
                    {{ x: -5, y: -5, text: '인구-/1인가구-', showarrow: false, font: {{ size: 11, color: '#6B7280' }} }},
                    {{ x: 5, y: -5, text: '인구+/1인가구-', showarrow: false, font: {{ size: 11, color: '#10B981' }} }}
                ]
            }};

            Plotly.newPlot('quadrantChart', [trace], layout, {{responsive: true}});
        }}

        // 차이지수 차트
        async function updateDivergenceChart() {{
            const data = await fetchAPI('divergence');
            const sorted = data.sort((a, b) => b.divergence_index - a.divergence_index).slice(0, 15);

            // 빨간색: 인구감소+1인가구증가 (불일치), 파란색: 그 외
            const divergenceData = sorted.filter(d => d.pop_change_rate < 0 && d.single_change_rate > 0);
            const normalData = sorted.filter(d => !(d.pop_change_rate < 0 && d.single_change_rate > 0));

            const traces = [];
            if (divergenceData.length > 0) {{
                traces.push({{
                    x: divergenceData.map(d => d.sigungu_nm),
                    y: divergenceData.map(d => d.divergence_index),
                    type: 'bar',
                    name: '인구↓ 1인가구↑',
                    marker: {{ color: '#EF4444' }}
                }});
            }}
            if (normalData.length > 0) {{
                traces.push({{
                    x: normalData.map(d => d.sigungu_nm),
                    y: normalData.map(d => d.divergence_index),
                    type: 'bar',
                    name: '그 외',
                    marker: {{ color: '#3B82F6' }}
                }});
            }}

            const layout = {{
                xaxis: {{ title: '지역', tickangle: -45, categoryorder: 'total descending' }},
                yaxis: {{ title: '차이지수 (|인구변화율 - 1인가구변화율|)' }},
                margin: {{ t: 50, l: 60, r: 30, b: 100 }},
                font: {{ family: 'Malgun Gothic' }},
                showlegend: true,
                legend: {{ x: 0.7, y: 1.15, orientation: 'h' }},
                barmode: 'overlay'
            }};

            Plotly.newPlot('divergenceChart', traces, layout, {{responsive: true}});
        }}

        // 히트맵 차트 + 데이터 표
        async function updateHeatmapChart() {{
            const data = await fetchAPI('heatmap');

            // 데이터를 2D 배열로 변환
            const zData = [];
            const nRegions = data.regions.length;
            const nAgeGroups = data.age_groups.length;

            for (let j = 0; j < nRegions; j++) {{
                const row = [];
                for (let i = 0; i < nAgeGroups; i++) {{
                    const item = data.data.find(d => d.x === i && d.y === j);
                    row.push(item ? item.value : 0);
                }}
                zData.push(row);
            }}

            const trace = {{
                z: zData,
                x: data.age_groups,
                y: data.regions,
                type: 'heatmap',
                colorscale: [
                    [0, '#EF4444'],
                    [0.5, '#FFFFFF'],
                    [1, '#10B981']
                ],
                zmid: 0,
                colorbar: {{ title: '변화율(%)' }}
            }};

            const layout = {{
                xaxis: {{ title: '연령대', side: 'bottom' }},
                yaxis: {{ title: '지역', autorange: 'reversed' }},
                margin: {{ t: 30, l: 100, r: 80, b: 80 }},
                font: {{ family: 'Malgun Gothic' }}
            }};

            Plotly.newPlot('heatmapChart', [trace], layout, {{responsive: true}});

            // 데이터 표 생성
            const table = document.getElementById('heatmapTable');
            const thead = table.querySelector('thead');
            const tbody = table.querySelector('tbody');

            // 헤더 생성
            thead.innerHTML = `<tr><th class="border p-1 text-left">지역</th>${{data.age_groups.map(ag => `<th class="border p-1 text-center">${{ag}}</th>`).join('')}}</tr>`;

            // 본문 생성
            tbody.innerHTML = data.regions.map((region, j) => {{
                const cells = zData[j].map(val => {{
                    const color = val > 0 ? `rgba(239, 68, 68, ${{Math.min(Math.abs(val)/10, 1)}})` :
                                  val < 0 ? `rgba(16, 185, 129, ${{Math.min(Math.abs(val)/10, 1)}})` : '';
                    return `<td class="border p-1 text-center" style="background:${{color}}">${{val.toFixed(1)}}</td>`;
                }}).join('');
                return `<tr><td class="border p-1 font-medium">${{region}}</td>${{cells}}</tr>`;
            }}).join('');
        }}

        // 인사이트 업데이트 (간결한 레이아웃)
        async function updateInsights() {{
            const data = await fetchAPI('insights');
            const container = document.getElementById('insights');

            // 5개 인사이트를 하나의 카드에 표시
            const insightItems = data.map(insight => `
                <div class="flex items-start gap-2 py-2 border-b border-gray-200 last:border-b-0">
                    <span class="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-xs flex-shrink-0">${{insight.icon}}</span>
                    <div class="flex-1">
                        <span class="font-medium text-gray-800">${{insight.title}}</span>
                        <span class="text-gray-600 text-sm ml-2">${{insight.content.replace(/\\n/g, ' | ')}}</span>
                    </div>
                </div>
            `).join('');

            // 마지막에 제안 모음
            const suggestions = data.filter(d => d.suggestion && !d.suggestion.includes('특이점 없음'))
                .map(d => d.suggestion.replace(/^• /, '')).join(' / ');

            container.innerHTML = `
                <div class="space-y-1">${{insightItems}}</div>
                ${{suggestions ? `<div class="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-blue-700"><span class="font-semibold">제안:</span> ${{suggestions}}</div>` : ''}}
            `;
        }}

        // DataTable 초기화
        let detailDataTable = null;

        async function updateDetailTable() {{
            const data = await fetchAPI('detail');
            const sidoValue = document.getElementById('sido').value;

            if (detailDataTable) {{
                detailDataTable.destroy();
            }}

            // 지역 선택에 따라 첫 두 컬럼 동적 설정
            let col1Key, col1Title, col2Key, col2Title;
            if (!sidoValue) {{
                // 전국 선택 → 시도코드/시도명
                col1Key = '시도코드'; col1Title = '시도코드';
                col2Key = '시도명'; col2Title = '시도명';
            }} else if (sidoValue === '__all_regions__') {{
                // 권역별 선택 → 권역코드/권역명
                col1Key = '권역코드'; col1Title = '권역코드';
                col2Key = '권역명'; col2Title = '권역명';
            }} else {{
                // 시도 선택 → 시군구코드/시군구
                col1Key = '시군구코드'; col1Title = '시군구코드';
                col2Key = '시군구'; col2Title = '시군구';
            }}

            // 테이블 헤더 동적 업데이트
            const thead = document.querySelector('#detailTable thead tr');
            thead.innerHTML = `
                <th>${{col1Title}}</th>
                <th>${{col2Title}}</th>
                <th>현재인구</th>
                <th>비교인구</th>
                <th>인구변화</th>
                <th>인구변화율(%)</th>
                <th>현재1인가구</th>
                <th>비교1인가구</th>
                <th>1인가구변화</th>
                <th>1인가구변화율(%)</th>
                <th>차이지수</th>
                <th>고령화율(%)</th>
                <th>1인가구비율(%)</th>
            `;

            detailDataTable = $('#detailTable').DataTable({{
                data: data,
                columns: [
                    {{ data: col1Key }},
                    {{ data: col2Key }},
                    {{ data: '현재인구', render: d => formatNumber(d) }},
                    {{ data: '비교인구', render: d => formatNumber(d) }},
                    {{ data: '인구변화', render: d => formatNumber(d) }},
                    {{ data: '인구변화율', render: d => d ? d.toFixed(2) : '-' }},
                    {{ data: '현재1인가구', render: d => formatNumber(d) }},
                    {{ data: '비교1인가구', render: d => formatNumber(d) }},
                    {{ data: '1인가구변화', render: d => formatNumber(d) }},
                    {{ data: '1인가구변화율', render: d => d ? d.toFixed(2) : '-' }},
                    {{ data: '차이지수', render: d => d ? d.toFixed(2) : '-' }},
                    {{ data: '고령화율', render: d => d ? d.toFixed(1) : '-' }},
                    {{ data: '1인가구비율', render: d => d ? d.toFixed(1) : '-' }}
                ],
                columnDefs: [
                    {{ targets: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], className: 'text-right' }}
                ],
                order: [[0, 'asc']],
                paging: false,
                searching: false,
                info: false,
                scrollX: true
            }});
        }}

        // 로딩 오버레이 표시/숨김 (대시보드1.py 스타일)
        function showLoading(message = '데이터를 불러오는 중...', subtext = '잠시만 기다려주세요.') {{
            const overlay = document.getElementById('loadingOverlay');
            overlay.querySelector('.loading-text').textContent = message;
            overlay.querySelector('.loading-subtext').textContent = subtext;
            overlay.classList.remove('hidden');
        }}

        function hideLoading() {{
            document.getElementById('loadingOverlay').classList.add('hidden');
        }}

        // 현황 차트 업데이트
        async function updateStatusCharts() {{
            const data = await fetchAPI('status_charts');
            if (!data || data.error) {{
                console.log('[statusCharts] 데이터 없음');
                return;
            }}

            // 지역명 표시
            const regionName = '(' + data.region_name + ')';
            document.getElementById('statusRegionName').textContent = regionName;
            document.getElementById('pyramidRegionName').textContent = regionName;
            document.getElementById('comparisonRegionName').textContent = regionName;
            document.getElementById('genderRegionName').textContent = regionName;

            // 차트 이미지 업데이트
            if (data.donut_chart) {{
                document.getElementById('donutChartImg').src = 'data:image/png;base64,' + data.donut_chart;
            }}
            if (data.pyramid_chart) {{
                document.getElementById('pyramidChartImg').src = 'data:image/png;base64,' + data.pyramid_chart;
            }}
            if (data.comparison_chart) {{
                document.getElementById('comparisonChartImg').src = 'data:image/png;base64,' + data.comparison_chart;
            }}
            if (data.gender_detail_chart) {{
                document.getElementById('genderDetailChartImg').src = 'data:image/png;base64,' + data.gender_detail_chart;
            }}

            console.log(`[statusCharts] 로드 완료 - 지역: ${{data.region_name}}, 총인구: ${{data.total_pop?.toLocaleString()}}, 1인가구: ${{data.total_single?.toLocaleString()}}`);
        }}

        // 전체 데이터 로드
        async function loadAllData() {{
            showLoading('데이터를 조회하고 있습니다', '선택한 조건에 맞는 데이터를 불러오고 있습니다.');

            const ageCat = document.getElementById('ageCategory').value;
            console.log('[loadAllData] 시작 - age_category:', ageCat);

            try {{
                // 병렬로 모든 API 호출
                const results = await Promise.allSettled([
                    updateSummary(),
                    updateStatusCharts(),
                    updateBarChart(),
                    updateTrendChart(),
                    updateQuadrantChart(),
                    updateDivergenceChart(),
                    updateHeatmapChart(),
                    updateInsights(),
                    updateDetailTable()
                ]);

                // 실패한 항목 로깅
                results.forEach((result, index) => {{
                    const names = ['summary', 'statusCharts', 'barChart', 'trendChart', 'quadrantChart', 'divergenceChart', 'heatmapChart', 'insights', 'detailTable'];
                    if (result.status === 'rejected') {{
                        console.error(`[${{names[index]}}] 실패:`, result.reason);
                    }}
                }});

            }} catch(e) {{
                console.error('loadAllData error:', e);
                alert('데이터 로딩 중 오류가 발생했습니다.');
            }} finally {{
                // 항상 로딩 숨김
                hideLoading();
            }}
        }}

        // 내보내기 함수
        async function exportDashboard() {{
            showLoading('내보내기 중...', '이미지와 보고서를 생성하고 있습니다.');

            try {{
                const data = await fetchAPI('export');

                if (data.success) {{
                    hideLoading();
                    alert(`내보내기 완료!\\n\\n저장 위치: ${{data.output_dir}}\\n\\n생성된 파일:\\n- ${{data.files.md}}\\n- ${{data.files.html}}\\n- 이미지 ${{data.files.images.length}}개`);
                }} else {{
                    hideLoading();
                    alert('내보내기 실패: ' + (data.error || '알 수 없는 오류'));
                }}
            }} catch (e) {{
                hideLoading();
                console.error('Export error:', e);
                alert('내보내기 중 오류가 발생했습니다.');
            }}
        }}

        // 이벤트 리스너
        document.getElementById('searchBtn').addEventListener('click', loadAllData);
        document.getElementById('exportBtn').addEventListener('click', exportDashboard);

        // 초기 로드 (페이지 완전 로드 후)
        window.addEventListener('load', function() {{
            loadAllData();
        }});
    </script>
</body>
</html>'''

    return html
