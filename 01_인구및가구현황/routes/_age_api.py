# -*- coding: utf-8 -*-
"""
연령별 인구 통계 Flask Blueprint 모듈
=====================================

이 모듈은 연령별 인구 데이터를 조회하고 시각화하는 Flask Blueprint를 제공합니다.
인구 피라미드 차트와 연령대별 인구 분석 기능을 포함합니다.

주요 기능:
    1. 연령별 인구 데이터 조회 (10세 단위 그룹화)
    2. 인구 피라미드 차트 데이터 API
    3. 시도/시군구별 연령대 인구 테이블

Blueprint 등록:
    >>> from routes.age import age_bp
    >>> app.register_blueprint(age_bp, url_prefix="/01_population")

API 엔드포인트:
    - GET /age              : 연령별 통계 메인 페이지
    - GET /api/age_pyramid  : 연령별 피라미드 차트 데이터
    - GET /api/age_table    : 연령대별 인구 테이블 데이터

데이터베이스 테이블:
    - fact_population_by_age: 1세별 인구 데이터 (Wide 형식, 컬럼 225개)
    - dim_admin_area: 행정구역 정보

Author: Claude AI Agent
Created: 2024-12-18
"""

from flask import Blueprint, render_template, request, jsonify
import pandas as pd
import sys
from pathlib import Path

# 상위 디렉토리의 module 패키지를 import하기 위해 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_connection

# Blueprint 생성
age_bp = Blueprint('age', __name__)


# =============================================================================
# 헬퍼 함수
# =============================================================================

def get_filter_options():
    """
    필터 옵션(기준시기, 시도 목록)을 조회합니다.
    """
    conn = get_db_connection()
    try:
        # 기준시기 목록 (fact_population_by_age 테이블에서)
        base_ym_df = pd.read_sql("""
            SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as base_ym
            FROM fact_population_by_age
            ORDER BY TO_CHAR(base_ym, 'YYYYMM') DESC
        """, conn)

        # 시도 목록
        sido_df = pd.read_sql("""
            SELECT DISTINCT sido_nm
            FROM dim_admin_area
            WHERE sido_nm IS NOT NULL
            ORDER BY MIN(admin_code) OVER (PARTITION BY sido_nm)
        """, conn)

        return {
            'base_ym_list': base_ym_df['base_ym'].tolist(),
            'sido_list': sido_df['sido_nm'].tolist()
        }
    finally:
        conn.close()


def load_age_population_data(base_ym=None, sido=None, sigungu=None):
    """
    연령별 인구 데이터를 조회합니다.

    Args:
        base_ym (str): 기준시기 (YYYYMM)
        sido (str): 시도명
        sigungu (str): 시군구명

    Returns:
        pd.DataFrame: 10세 단위로 집계된 연령별 인구 데이터
    """
    conn = get_db_connection()
    try:
        # 10세 단위로 집계하기 위한 쿼리
        query = """
            SELECT
                d.sido_nm,
                d.sigungu_nm,
                TO_CHAR(p.base_ym, 'YYYYMM') as base_ym,
                SUM(p.total_pop) as total_pop,
                SUM(p.male_total) as male_total,
                SUM(p.female_total) as female_total,
                SUM(p.male_age_0 + p.male_age_1 + p.male_age_2 + p.male_age_3 + p.male_age_4 +
                    p.male_age_5 + p.male_age_6 + p.male_age_7 + p.male_age_8 + p.male_age_9) as male_0_9,
                SUM(p.male_age_10 + p.male_age_11 + p.male_age_12 + p.male_age_13 + p.male_age_14 +
                    p.male_age_15 + p.male_age_16 + p.male_age_17 + p.male_age_18 + p.male_age_19) as male_10_19,
                SUM(p.male_age_20 + p.male_age_21 + p.male_age_22 + p.male_age_23 + p.male_age_24 +
                    p.male_age_25 + p.male_age_26 + p.male_age_27 + p.male_age_28 + p.male_age_29) as male_20_29,
                SUM(p.male_age_30 + p.male_age_31 + p.male_age_32 + p.male_age_33 + p.male_age_34 +
                    p.male_age_35 + p.male_age_36 + p.male_age_37 + p.male_age_38 + p.male_age_39) as male_30_39,
                SUM(p.male_age_40 + p.male_age_41 + p.male_age_42 + p.male_age_43 + p.male_age_44 +
                    p.male_age_45 + p.male_age_46 + p.male_age_47 + p.male_age_48 + p.male_age_49) as male_40_49,
                SUM(p.male_age_50 + p.male_age_51 + p.male_age_52 + p.male_age_53 + p.male_age_54 +
                    p.male_age_55 + p.male_age_56 + p.male_age_57 + p.male_age_58 + p.male_age_59) as male_50_59,
                SUM(p.male_age_60 + p.male_age_61 + p.male_age_62 + p.male_age_63 + p.male_age_64 +
                    p.male_age_65 + p.male_age_66 + p.male_age_67 + p.male_age_68 + p.male_age_69) as male_60_69,
                SUM(p.male_age_70 + p.male_age_71 + p.male_age_72 + p.male_age_73 + p.male_age_74 +
                    p.male_age_75 + p.male_age_76 + p.male_age_77 + p.male_age_78 + p.male_age_79) as male_70_79,
                SUM(p.male_age_80 + p.male_age_81 + p.male_age_82 + p.male_age_83 + p.male_age_84 +
                    p.male_age_85 + p.male_age_86 + p.male_age_87 + p.male_age_88 + p.male_age_89) as male_80_89,
                SUM(p.male_age_90 + p.male_age_91 + p.male_age_92 + p.male_age_93 + p.male_age_94 +
                    p.male_age_95 + p.male_age_96 + p.male_age_97 + p.male_age_98 + p.male_age_99 +
                    p.male_age_100 + p.male_age_101 + p.male_age_102 + p.male_age_103 + p.male_age_104 +
                    p.male_age_105 + p.male_age_106 + p.male_age_107 + p.male_age_108 + p.male_age_109 +
                    p.male_age_110_over) as male_90_over,
                SUM(p.female_age_0 + p.female_age_1 + p.female_age_2 + p.female_age_3 + p.female_age_4 +
                    p.female_age_5 + p.female_age_6 + p.female_age_7 + p.female_age_8 + p.female_age_9) as female_0_9,
                SUM(p.female_age_10 + p.female_age_11 + p.female_age_12 + p.female_age_13 + p.female_age_14 +
                    p.female_age_15 + p.female_age_16 + p.female_age_17 + p.female_age_18 + p.female_age_19) as female_10_19,
                SUM(p.female_age_20 + p.female_age_21 + p.female_age_22 + p.female_age_23 + p.female_age_24 +
                    p.female_age_25 + p.female_age_26 + p.female_age_27 + p.female_age_28 + p.female_age_29) as female_20_29,
                SUM(p.female_age_30 + p.female_age_31 + p.female_age_32 + p.female_age_33 + p.female_age_34 +
                    p.female_age_35 + p.female_age_36 + p.female_age_37 + p.female_age_38 + p.female_age_39) as female_30_39,
                SUM(p.female_age_40 + p.female_age_41 + p.female_age_42 + p.female_age_43 + p.female_age_44 +
                    p.female_age_45 + p.female_age_46 + p.female_age_47 + p.female_age_48 + p.female_age_49) as female_40_49,
                SUM(p.female_age_50 + p.female_age_51 + p.female_age_52 + p.female_age_53 + p.female_age_54 +
                    p.female_age_55 + p.female_age_56 + p.female_age_57 + p.female_age_58 + p.female_age_59) as female_50_59,
                SUM(p.female_age_60 + p.female_age_61 + p.female_age_62 + p.female_age_63 + p.female_age_64 +
                    p.female_age_65 + p.female_age_66 + p.female_age_67 + p.female_age_68 + p.female_age_69) as female_60_69,
                SUM(p.female_age_70 + p.female_age_71 + p.female_age_72 + p.female_age_73 + p.female_age_74 +
                    p.female_age_75 + p.female_age_76 + p.female_age_77 + p.female_age_78 + p.female_age_79) as female_70_79,
                SUM(p.female_age_80 + p.female_age_81 + p.female_age_82 + p.female_age_83 + p.female_age_84 +
                    p.female_age_85 + p.female_age_86 + p.female_age_87 + p.female_age_88 + p.female_age_89) as female_80_89,
                SUM(p.female_age_90 + p.female_age_91 + p.female_age_92 + p.female_age_93 + p.female_age_94 +
                    p.female_age_95 + p.female_age_96 + p.female_age_97 + p.female_age_98 + p.female_age_99 +
                    p.female_age_100 + p.female_age_101 + p.female_age_102 + p.female_age_103 + p.female_age_104 +
                    p.female_age_105 + p.female_age_106 + p.female_age_107 + p.female_age_108 + p.female_age_109 +
                    p.female_age_110_over) as female_90_over
            FROM fact_population_by_age p
            JOIN dim_admin_area d ON p.admin_code = d.admin_code
            WHERE 1=1
        """
        params = []

        if base_ym:
            query += " AND TO_CHAR(p.base_ym, 'YYYYMM') = %s"
            params.append(base_ym)
        if sido:
            query += " AND d.sido_nm = %s"
            params.append(sido)
        if sigungu:
            query += " AND d.sigungu_nm = %s"
            params.append(sigungu)

        query += " GROUP BY d.sido_nm, d.sigungu_nm, TO_CHAR(p.base_ym, 'YYYYMM')"

        df = pd.read_sql(query, conn, params=params if params else None)
        return df
    finally:
        conn.close()


# =============================================================================
# 라우트 핸들러
# =============================================================================

@age_bp.route('/age')
def index():
    """연령별 통계 메인 페이지를 렌더링합니다."""
    filters = get_filter_options()
    return render_template('population_age.html',
                          filters=filters,
                          title='연령별 인구 통계')


@age_bp.route('/api/age_pyramid')
def api_age_pyramid():
    """
    연령별 인구 피라미드 데이터 API.

    Query Parameters:
        base_ym (str, optional): 기준시기 (YYYYMM)
        sido (str, optional): 시도명
        sigungu (str, optional): 시군구명

    Returns:
        JSON: 연령대별 남녀 인구 데이터 (Chart.js 형식)
    """
    base_ym = request.args.get('base_ym')
    sido = request.args.get('sido')
    sigungu = request.args.get('sigungu')

    df = load_age_population_data(base_ym, sido, sigungu)

    if df.empty:
        return jsonify({'success': False, 'error': '데이터가 없습니다'})

    age_groups = ['0_9', '10_19', '20_29', '30_39', '40_49', '50_59', '60_69', '70_79', '80_89', '90_over']
    labels = ['0-9세', '10-19세', '20-29세', '30-39세', '40-49세', '50-59세', '60-69세', '70-79세', '80-89세', '90세+']

    male_data = []
    female_data = []

    for ag in age_groups:
        male_sum = df[f'male_{ag}'].sum() / 10000
        female_sum = df[f'female_{ag}'].sum() / 10000
        male_data.append(round(-male_sum, 1))  # 피라미드용 음수
        female_data.append(round(female_sum, 1))

    return jsonify({
        'success': True,
        'labels': labels,
        'datasets': [
            {'label': '남자', 'data': male_data, 'backgroundColor': 'rgba(54, 162, 235, 0.8)'},
            {'label': '여자', 'data': female_data, 'backgroundColor': 'rgba(255, 99, 132, 0.8)'}
        ],
        'summary': {
            'total_pop': round(df['total_pop'].sum() / 10000, 1),
            'male_total': round(df['male_total'].sum() / 10000, 1),
            'female_total': round(df['female_total'].sum() / 10000, 1)
        }
    })


@age_bp.route('/api/age_table')
def api_age_table():
    """
    연령대별 인구 테이블 데이터 API.

    Query Parameters:
        base_ym (str, optional): 기준시기 (YYYYMM)
        sido (str, optional): 시도명

    Returns:
        JSON: 지역별 연령대 인구 현황
    """
    base_ym = request.args.get('base_ym')
    sido = request.args.get('sido')

    df = load_age_population_data(base_ym, sido)

    if df.empty:
        return jsonify({'success': False, 'error': '데이터가 없습니다'})

    age_groups = ['0_9', '10_19', '20_29', '30_39', '40_49', '50_59', '60_69', '70_79', '80_89', '90_over']

    if sido:
        # 특정 시도의 시군구별 집계
        result = df.groupby('sigungu_nm').agg({
            'total_pop': 'sum',
            **{f'male_{ag}': 'sum' for ag in age_groups},
            **{f'female_{ag}': 'sum' for ag in age_groups}
        }).reset_index()
        result['region'] = result['sigungu_nm']
    else:
        # 시도별 집계
        result = df.groupby('sido_nm').agg({
            'total_pop': 'sum',
            **{f'male_{ag}': 'sum' for ag in age_groups},
            **{f'female_{ag}': 'sum' for ag in age_groups}
        }).reset_index()
        result['region'] = result['sido_nm']

    # 연령대별 합계 및 비율 계산
    table_data = []
    for _, row in result.iterrows():
        row_data = {'region': row['region'], 'total_pop': int(row['total_pop'])}
        for ag in age_groups:
            total = int(row[f'male_{ag}'] + row[f'female_{ag}'])
            ratio = round(total / row['total_pop'] * 100, 1) if row['total_pop'] > 0 else 0
            row_data[ag] = total
            row_data[f'{ag}_ratio'] = ratio
        table_data.append(row_data)

    return jsonify({
        'success': True,
        'data': table_data,
        'age_groups': age_groups,
        'labels': ['0-9세', '10-19세', '20-29세', '30-39세', '40-49세', '50-59세', '60-69세', '70-79세', '80-89세', '90세+']
    })


@age_bp.route('/api/sigungu')
def api_sigungu():
    """시군구 목록 API (연령별 페이지용)."""
    sido = request.args.get('sido')
    if not sido:
        return jsonify({'success': False, 'error': '시도를 선택하세요'})

    conn = get_db_connection()
    try:
        df = pd.read_sql("""
            SELECT DISTINCT sigungu_nm
            FROM dim_admin_area
            WHERE sido_nm = %s AND sigungu_nm IS NOT NULL
            ORDER BY MIN(admin_code) OVER (PARTITION BY sigungu_nm)
        """, conn, params=[sido])

        return jsonify({'success': True, 'data': df['sigungu_nm'].tolist()})
    finally:
        conn.close()
