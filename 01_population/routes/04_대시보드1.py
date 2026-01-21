# -*- coding: utf-8 -*-
"""
인구통계 대시보드1 - 연령별 인구 및 1인가구 분석
- 고령화율, 유소년율, 생산가능인구율 등 주요 지표
- 연령 그룹별 인구 분석 (라디오버튼으로 그룹 선택)
- 1인가구 분석
- matplotlib 시각화 (막대, 도넛 차트 등)
"""
import sys
import io
import base64
from pathlib import Path

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import koreanize_matplotlib

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_engine
from module.menu_generator import MenuGenerator
from module.report_generator import DashboardReport
from datetime import datetime
from flask import make_response
from urllib.parse import quote
import tempfile

POP_BASE = Path(__file__).parent.parent


def export_dashboard_ppt(title, subtitle, indicators, combined_df, pivot_df, charts, source_file):
    """대시보드를 PPT로 내보내기"""
    # DashboardReport 객체 생성
    report = DashboardReport(
        title=title,
        subtitle=subtitle,
        source_file=source_file
    )

    # 주요 지표 추가
    report.add_metrics([
        {'label': '총인구', 'value': f"{indicators['total_pop']:,}", 'unit': '명'},
        {'label': '총세대수', 'value': f"{indicators['household_cnt']:,}", 'unit': '세대'},
        {'label': '고령화율', 'value': f"{indicators['elderly_ratio']}", 'unit': '% (65세 이상)'},
        {'label': '유소년율', 'value': f"{indicators['youth_ratio']}", 'unit': '% (0-14세)'},
        {'label': '생산가능인구', 'value': f"{indicators['working_ratio']}", 'unit': '% (15-64세)'},
        {'label': '1인가구 비율', 'value': f"{indicators['single_ratio']}", 'unit': '%'},
    ])

    # 테이블 추가
    if not combined_df.empty:
        table_df = combined_df[['code_name', 'total_pop', 'male_pop', 'female_pop', 'total_cnt', 'single_ratio']].copy()
        table_df.columns = ['연령그룹', '총인구', '남자', '여자', '1인가구', '1인가구비율(%)']
        report.add_table("연령별 인구 및 1인가구 현황", table_df, max_rows=15)

    # 피벗 테이블 추가 (지역별 연령그룹 현황)
    if not pivot_df.empty:
        # 주요 컬럼만 선택하여 표시
        pivot_cols = ['region_name', '총인구', '총1인가구', '총비율']
        pivot_display = pivot_df[pivot_cols].copy()
        pivot_display.columns = ['지역명', '총인구', '총1인가구', '1인가구비율(%)']
        report.add_table("지역별 인구 및 1인가구 현황", pivot_display, max_rows=25)

    # base64 차트를 이미지 파일로 저장 (영구 폴더에)
    image_dir = Path(source_file).parent / "image"
    image_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    chart_paths = {}  # 절대경로 저장

    chart_titles = {
        'pyramid': '인구 피라미드',
        'combined': '연령별 인구 vs 1인가구 비교',
        'age_bar': '연령별 남녀 인구',
        'single_bar': '연령별 1인가구',
        'age_donut': '연령대별 인구 구성',
        'single_donut': '연령대별 1인가구 구성'
    }

    for chart_name, chart_data in charts.items():
        if chart_data and chart_data.startswith('data:image/png;base64,'):
            img_data = base64.b64decode(chart_data.split(',')[1])
            img_filename = f"{chart_name}_{timestamp}.png"
            img_path = image_dir / img_filename
            img_path.write_bytes(img_data)
            chart_paths[chart_name] = {
                'absolute': str(img_path),
                'relative': f"image/{img_filename}",
                'title': chart_titles.get(chart_name, chart_name)
            }

    # 인사이트 추가 (이모지 대신 ■ 사용)
    report.add_insight(
        "■", "고령화 현황",
        f"고령화율 {indicators['elderly_ratio']}%, 유소년율 {indicators['youth_ratio']}%로 노령화지수는 {indicators['aging_index']}입니다."
    )
    report.add_insight(
        "■", "1인가구 현황",
        f"전체 세대 중 {indicators['single_ratio']}%가 1인가구입니다. 세대당 평균 {indicators['pop_per_house']}명이 거주합니다."
    )

    # MD 파일 저장 (상대 경로 사용)
    for chart_info in chart_paths.values():
        report.add_chart(chart_info['title'], chart_info['relative'])
    md_path = report.save_markdown()

    # PPT 파일 저장 (절대 경로 사용)
    # 차트 경로를 절대 경로로 업데이트
    report.charts.clear()
    for chart_info in chart_paths.values():
        report.add_chart(chart_info['title'], chart_info['absolute'])

    ppt_filename = f"인구통계_대시보드_{timestamp}.pptx"
    ppt_path = Path(source_file).parent / ppt_filename
    report.save_ppt(str(ppt_path))

    # 파일 다운로드 응답 반환
    with open(ppt_path, 'rb') as f:
        file_data = f.read()

    response = make_response(file_data)
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    encoded_filename = quote(ppt_filename)
    response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"

    return response


def is_numeric(val):
    """숫자 타입 여부 확인"""
    return isinstance(val, (int, float, np.integer, np.floating))


def get_filter_options():
    """필터 옵션 조회"""
    engine = get_db_engine()

    base_ym_df = pd.read_sql("""
        SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as base_ym
        FROM fact_population_basic
        ORDER BY base_ym DESC
    """, engine)

    sido_df = pd.read_sql("""
        SELECT DISTINCT sido_nm, MIN(admin_code) as sort_key
        FROM dim_admin_area
        WHERE sido_nm IS NOT NULL
        GROUP BY sido_nm
        ORDER BY sort_key
    """, engine)

    # 연령 그룹 카테고리 조회
    age_cat_df = pd.read_sql("""
        SELECT DISTINCT category, category_name
        FROM code_age_group
        ORDER BY category
    """, engine)

    return {
        'base_ym_list': base_ym_df['base_ym'].tolist(),
        'sido_list': sido_df['sido_nm'].tolist(),
        'age_categories': age_cat_df.to_dict('records')
    }


def get_age_groups(category=1):
    """연령 그룹 코드 조회"""
    engine = get_db_engine()
    df = pd.read_sql(f"""
        SELECT code, code_name, age_start, age_end, sort_order
        FROM code_age_group
        WHERE category = {category}
        ORDER BY sort_order
    """, engine)
    return df


def get_summary_indicators(base_ym=None, view_type='sigungu', sido_nm=None, include_sub=False):
    """주요 지표 조회 (고령화율, 유소년율 등)"""
    engine = get_db_engine()

    # 기본 WHERE 절 생성
    where_clauses = ["1=1"]
    if base_ym:
        where_clauses.append(f"TO_CHAR(f.base_ym, 'YYYYMM') = '{base_ym}'")

    # view_type에 따른 필터링
    if view_type == 'region':
        pass  # 전국
    elif view_type == 'sido' and sido_nm:
        where_clauses.append(f"d.sido_nm = '{sido_nm}'")
    elif view_type == 'sigungu' and sido_nm:
        where_clauses.append(f"d.sido_nm = '{sido_nm}'")

    where_sql = " AND ".join(where_clauses)

    # 기본 인구 통계
    basic_df = pd.read_sql(f"""
        SELECT
            SUM(f.total_pop) as total_pop,
            SUM(f.male_pop) as male_pop,
            SUM(f.female_pop) as female_pop,
            SUM(f.household_cnt) as household_cnt
        FROM fact_population_basic f
        JOIN dim_admin_area d ON f.admin_code = d.admin_code
        WHERE {where_sql}
    """, engine)

    # 1인가구 통계
    single_df = pd.read_sql(f"""
        SELECT
            SUM(s.total_cnt) as single_household_cnt
        FROM fact_single_household s
        JOIN dim_admin_area d ON s.admin_code = d.admin_code
        WHERE {where_sql.replace('f.base_ym', 's.base_ym')}
    """, engine)

    # 연령별 인구 (정책지표용: 0-14, 15-64, 65+)
    age_df = pd.read_sql(f"""
        SELECT
            SUM(male_total + female_total) as total_pop,
            SUM(
                male_age_0 + male_age_1 + male_age_2 + male_age_3 + male_age_4 +
                male_age_5 + male_age_6 + male_age_7 + male_age_8 + male_age_9 +
                male_age_10 + male_age_11 + male_age_12 + male_age_13 + male_age_14 +
                female_age_0 + female_age_1 + female_age_2 + female_age_3 + female_age_4 +
                female_age_5 + female_age_6 + female_age_7 + female_age_8 + female_age_9 +
                female_age_10 + female_age_11 + female_age_12 + female_age_13 + female_age_14
            ) as youth_pop,
            SUM(
                male_age_65 + male_age_66 + male_age_67 + male_age_68 + male_age_69 +
                male_age_70 + male_age_71 + male_age_72 + male_age_73 + male_age_74 +
                male_age_75 + male_age_76 + male_age_77 + male_age_78 + male_age_79 +
                male_age_80 + male_age_81 + male_age_82 + male_age_83 + male_age_84 +
                male_age_85 + male_age_86 + male_age_87 + male_age_88 + male_age_89 +
                male_age_90 + male_age_91 + male_age_92 + male_age_93 + male_age_94 +
                male_age_95 + male_age_96 + male_age_97 + male_age_98 + male_age_99 +
                male_age_100 + male_age_101 + male_age_102 + male_age_103 + male_age_104 +
                male_age_105 + male_age_106 + male_age_107 + male_age_108 + male_age_109 +
                male_age_110_over +
                female_age_65 + female_age_66 + female_age_67 + female_age_68 + female_age_69 +
                female_age_70 + female_age_71 + female_age_72 + female_age_73 + female_age_74 +
                female_age_75 + female_age_76 + female_age_77 + female_age_78 + female_age_79 +
                female_age_80 + female_age_81 + female_age_82 + female_age_83 + female_age_84 +
                female_age_85 + female_age_86 + female_age_87 + female_age_88 + female_age_89 +
                female_age_90 + female_age_91 + female_age_92 + female_age_93 + female_age_94 +
                female_age_95 + female_age_96 + female_age_97 + female_age_98 + female_age_99 +
                female_age_100 + female_age_101 + female_age_102 + female_age_103 + female_age_104 +
                female_age_105 + female_age_106 + female_age_107 + female_age_108 + female_age_109 +
                female_age_110_over
            ) as elderly_pop
        FROM fact_population_by_age a
        JOIN dim_admin_area d ON a.admin_code = d.admin_code
        WHERE {where_sql.replace('f.base_ym', 'a.base_ym')}
    """, engine)

    # 지표 계산
    total_pop = int(basic_df['total_pop'].iloc[0] or 0)
    male_pop = int(basic_df['male_pop'].iloc[0] or 0)
    female_pop = int(basic_df['female_pop'].iloc[0] or 0)
    household_cnt = int(basic_df['household_cnt'].iloc[0] or 0)
    single_cnt = int(single_df['single_household_cnt'].iloc[0] or 0)

    age_total = int(age_df['total_pop'].iloc[0] or 0)
    youth_pop = int(age_df['youth_pop'].iloc[0] or 0)
    elderly_pop = int(age_df['elderly_pop'].iloc[0] or 0)
    working_pop = age_total - youth_pop - elderly_pop

    return {
        'total_pop': total_pop,
        'male_pop': male_pop,
        'female_pop': female_pop,
        'household_cnt': household_cnt,
        'single_household_cnt': single_cnt,
        'youth_pop': youth_pop,
        'elderly_pop': elderly_pop,
        'working_pop': working_pop,
        # 비율 계산
        'sex_ratio': round(male_pop / female_pop * 100, 1) if female_pop > 0 else 0,
        'pop_per_house': round(total_pop / household_cnt, 2) if household_cnt > 0 else 0,
        'single_ratio': round(single_cnt / household_cnt * 100, 1) if household_cnt > 0 else 0,
        'youth_ratio': round(youth_pop / age_total * 100, 1) if age_total > 0 else 0,
        'elderly_ratio': round(elderly_pop / age_total * 100, 1) if age_total > 0 else 0,
        'working_ratio': round(working_pop / age_total * 100, 1) if age_total > 0 else 0,
        'aging_index': round(elderly_pop / youth_pop * 100, 1) if youth_pop > 0 else 0,
    }


def get_age_population(base_ym=None, view_type='sigungu', sido_nm=None, include_sub=False, age_category=1):
    """연령 그룹별 인구 조회"""
    engine = get_db_engine()
    age_groups = get_age_groups(age_category)

    where_clauses = ["1=1"]
    if base_ym:
        where_clauses.append(f"TO_CHAR(a.base_ym, 'YYYYMM') = '{base_ym}'")

    if view_type == 'sido' and sido_nm:
        where_clauses.append(f"d.sido_nm = '{sido_nm}'")
    elif view_type == 'sigungu' and sido_nm:
        where_clauses.append(f"d.sido_nm = '{sido_nm}'")

    where_sql = " AND ".join(where_clauses)

    results = []
    for _, grp in age_groups.iterrows():
        age_start = grp['age_start']
        age_end = min(grp['age_end'], 110)

        # 동적 컬럼 생성
        male_cols = []
        female_cols = []
        for age in range(age_start, age_end + 1):
            if age >= 110:
                male_cols.append("male_age_110_over")
                female_cols.append("female_age_110_over")
                break
            male_cols.append(f"male_age_{age}")
            female_cols.append(f"female_age_{age}")

        male_sum = " + ".join(male_cols)
        female_sum = " + ".join(female_cols)

        query = f"""
            SELECT
                SUM({male_sum}) as male_pop,
                SUM({female_sum}) as female_pop
            FROM fact_population_by_age a
            JOIN dim_admin_area d ON a.admin_code = d.admin_code
            WHERE {where_sql}
        """
        df = pd.read_sql(query, engine)

        male = int(df['male_pop'].iloc[0] or 0)
        female = int(df['female_pop'].iloc[0] or 0)

        results.append({
            'code_name': grp['code_name'],
            'age_range': f"{age_start}~{grp['age_end']}세",
            'male_pop': male,
            'female_pop': female,
            'total_pop': male + female,
            'sort_order': grp['sort_order']
        })

    return pd.DataFrame(results).sort_values('sort_order')


def get_single_household_by_age(base_ym=None, view_type='sigungu', sido_nm=None, include_sub=False, age_category=1):
    """연령 그룹별 1인가구 조회"""
    engine = get_db_engine()
    age_groups = get_age_groups(age_category)

    where_clauses = ["1=1"]
    if base_ym:
        where_clauses.append(f"TO_CHAR(s.base_ym, 'YYYYMM') = '{base_ym}'")

    if view_type == 'sido' and sido_nm:
        where_clauses.append(f"d.sido_nm = '{sido_nm}'")
    elif view_type == 'sigungu' and sido_nm:
        where_clauses.append(f"d.sido_nm = '{sido_nm}'")

    where_sql = " AND ".join(where_clauses)

    results = []
    for _, grp in age_groups.iterrows():
        age_start = grp['age_start']
        age_end = min(grp['age_end'], 110)

        male_cols = []
        female_cols = []
        for age in range(age_start, age_end + 1):
            if age >= 110:
                male_cols.append("male_age_110_over")
                female_cols.append("female_age_110_over")
                break
            male_cols.append(f"male_age_{age}")
            female_cols.append(f"female_age_{age}")

        male_sum = " + ".join(male_cols)
        female_sum = " + ".join(female_cols)

        query = f"""
            SELECT
                SUM({male_sum}) as male_cnt,
                SUM({female_sum}) as female_cnt
            FROM fact_single_household s
            JOIN dim_admin_area d ON s.admin_code = d.admin_code
            WHERE {where_sql}
        """
        df = pd.read_sql(query, engine)

        male = int(df['male_cnt'].iloc[0] or 0)
        female = int(df['female_cnt'].iloc[0] or 0)

        results.append({
            'code_name': grp['code_name'],
            'age_range': f"{age_start}~{grp['age_end']}세",
            'male_cnt': male,
            'female_cnt': female,
            'total_cnt': male + female,
            'sort_order': grp['sort_order']
        })

    return pd.DataFrame(results).sort_values('sort_order')


def get_combined_age_data(base_ym=None, view_type='sigungu', sido_nm=None, include_sub=False, age_category=1):
    """연령 그룹별 인구 + 1인가구 통합 조회"""
    pop_df = get_age_population(base_ym, view_type, sido_nm, include_sub, age_category)
    single_df = get_single_household_by_age(base_ym, view_type, sido_nm, include_sub, age_category)

    # 두 데이터프레임 병합
    combined = pop_df.merge(
        single_df[['code_name', 'male_cnt', 'female_cnt', 'total_cnt']],
        on='code_name',
        how='left'
    )

    # 1인가구 비율 계산 (1인가구 / 인구 * 100)
    combined['single_ratio'] = (combined['total_cnt'] / combined['total_pop'] * 100).round(1)
    combined['single_ratio'] = combined['single_ratio'].fillna(0)

    return combined


def get_pivot_data_by_region(base_ym=None, view_type='sigungu', sido_nm=None, age_category=1):
    """지역별 행, 연령그룹별 컬럼 피벗 데이터 조회 (최적화 버전)"""
    engine = get_db_engine()
    age_groups = get_age_groups(age_category)

    # 기본 WHERE 조건
    where_clauses = ["1=1"]
    if base_ym:
        where_clauses.append(f"TO_CHAR(a.base_ym, 'YYYYMM') = '{base_ym}'")

    # view_type에 따른 그룹핑 및 필터
    if view_type == 'region':
        group_col = "d.sido_nm"
    elif view_type == 'sido':
        group_col = "d.sido_nm"
    else:  # sigungu
        group_col = "d.sigungu_nm"
        if sido_nm:
            where_clauses.append(f"d.sido_nm = '{sido_nm}'")

    where_sql = " AND ".join(where_clauses)

    # 연령그룹별 SUM 컬럼 동적 생성
    age_sum_cols = []
    for _, grp in age_groups.iterrows():
        age_start = grp['age_start']
        age_end = min(grp['age_end'], 110)
        code_name = grp['code_name']

        cols = []
        for age in range(age_start, age_end + 1):
            if age >= 110:
                cols.append("male_age_110_over + female_age_110_over")
                break
            cols.append(f"male_age_{age} + female_age_{age}")

        sum_expr = " + ".join(cols)
        age_sum_cols.append(f"SUM({sum_expr}) as \"{code_name}\"")

    age_select = ", ".join(age_sum_cols)

    # 인구 데이터 한 번에 조회
    pop_query = f"""
        SELECT {group_col} as region_name, {age_select}
        FROM fact_population_by_age a
        JOIN dim_admin_area d ON a.admin_code = d.admin_code
        WHERE {where_sql}
        GROUP BY {group_col}
        ORDER BY {group_col}
    """
    pop_df = pd.read_sql(pop_query, engine)

    # 1인가구 데이터 한 번에 조회
    single_query = f"""
        SELECT {group_col} as region_name, {age_select}
        FROM fact_single_household s
        JOIN dim_admin_area d ON s.admin_code = d.admin_code
        WHERE {where_sql.replace('a.base_ym', 's.base_ym')}
        GROUP BY {group_col}
        ORDER BY {group_col}
    """
    single_df = pd.read_sql(single_query, engine)

    # 결과 병합 및 피벗
    age_names = age_groups['code_name'].tolist()
    results = []

    for _, pop_row in pop_df.iterrows():
        region = pop_row['region_name']
        if not region:
            continue

        row_data = {'region_name': region}
        total_pop = 0
        total_single = 0

        # 해당 지역의 1인가구 데이터 찾기
        single_row = single_df[single_df['region_name'] == region]

        for code_name in age_names:
            pop = int(pop_row[code_name] or 0)
            single_cnt = int(single_row[code_name].iloc[0] or 0) if len(single_row) > 0 else 0

            ratio = round(single_cnt / pop * 100, 1) if pop > 0 else 0

            row_data[f'{code_name}_인구'] = pop
            row_data[f'{code_name}_1인가구'] = single_cnt
            row_data[f'{code_name}_비율'] = ratio

            total_pop += pop
            total_single += single_cnt

        row_data['총인구'] = total_pop
        row_data['총1인가구'] = total_single
        row_data['총비율'] = round(total_single / total_pop * 100, 1) if total_pop > 0 else 0

        results.append(row_data)

    return pd.DataFrame(results), age_names


def create_bar_chart(df, x_col, y_cols, title, colors=None, labels=None):
    """막대 차트 생성"""
    fig, ax = plt.subplots(figsize=(12, 5))

    x = np.arange(len(df))
    width = 0.35

    if colors is None:
        colors = ['#4A90D9', '#E57373']

    if labels is None:
        labels = y_cols

    if len(y_cols) == 2:
        bars1 = ax.bar(x - width/2, df[y_cols[0]], width, label=labels[0], color=colors[0])
        bars2 = ax.bar(x + width/2, df[y_cols[1]], width, label=labels[1], color=colors[1])
    else:
        bars1 = ax.bar(x, df[y_cols[0]], width, label=labels[0], color=colors[0])

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(df[x_col], rotation=45, ha='right')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: format(int(v), ',')))
    ax.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def create_combined_chart(df, x_col, title):
    """인구 + 1인가구 통합 차트 (이중 축)"""
    fig, ax1 = plt.subplots(figsize=(14, 6))

    x = np.arange(len(df))
    width = 0.35

    # 왼쪽 축: 인구수
    bars1 = ax1.bar(x - width/2, df['total_pop'] / 10000, width, label='인구수', color='#4A90D9', alpha=0.8)
    bars2 = ax1.bar(x + width/2, df['total_cnt'] / 10000, width, label='1인가구수', color='#66BB6A', alpha=0.8)

    ax1.set_xlabel('연령그룹')
    ax1.set_ylabel('인원 (만 명)', color='#333')
    ax1.set_xticks(x)
    ax1.set_xticklabels(df[x_col], rotation=45, ha='right')
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f'{v:.0f}'))
    ax1.tick_params(axis='y', labelcolor='#333')

    # 오른쪽 축: 1인가구 비율
    ax2 = ax1.twinx()
    line = ax2.plot(x, df['single_ratio'], 'ro-', linewidth=2, markersize=6, label='1인가구비율(%)')
    ax2.set_ylabel('1인가구 비율 (%)', color='#E53935')
    ax2.tick_params(axis='y', labelcolor='#E53935')
    ax2.set_ylim(0, max(df['single_ratio'].max() * 1.2, 10))

    # 범례 통합
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    ax1.set_title(title, fontsize=14, fontweight='bold')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def create_pyramid_chart(df, title):
    """인구 피라미드 차트 생성"""
    fig, ax = plt.subplots(figsize=(10, 6))

    y = np.arange(len(df))
    male_pop = df['male_pop'].values / 10000  # 만 명 단위
    female_pop = df['female_pop'].values / 10000

    ax.barh(y, -male_pop, height=0.7, color='#4A90D9', label='남자')
    ax.barh(y, female_pop, height=0.7, color='#E57373', label='여자')

    ax.set_yticks(y)
    ax.set_yticklabels(df['code_name'])
    ax.set_xlabel('인구 (만 명)')
    ax.set_title(title, fontsize=14, fontweight='bold')

    # x축 라벨 절대값으로
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f'{abs(v):.0f}'))
    ax.legend(loc='upper right')
    ax.axvline(0, color='black', linewidth=0.5)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def create_donut_chart(values, labels, title, center_text='', sub_text='', colors=None):
    """도넛 차트 생성 (중앙에 총합계 표시)"""
    fig, ax = plt.subplots(figsize=(7, 7))

    if colors is None:
        colors = ['#66BB6A', '#42A5F5', '#FFA726', '#EF5350', '#AB47BC', '#78909C', '#FF7043', '#26A69A']

    total = sum(values)

    # 비율+수량 표시 함수
    def make_autopct(values):
        def my_autopct(pct):
            val = int(round(pct * total / 100.0))
            return f'{pct:.1f}%\n({val:,}명)'
        return my_autopct

    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors[:len(values)],
        autopct=make_autopct(values), startangle=90, pctdistance=0.75,
        wedgeprops=dict(width=0.5), textprops={'fontsize': 9}
    )

    # 중앙 텍스트 (총합계, 지역명)
    ax.text(0, 0.1, center_text, ha='center', va='center', fontsize=16, fontweight='bold', color='#1243A6')
    ax.text(0, -0.15, f'{total:,}명', ha='center', va='center', fontsize=14, fontweight='bold', color='#333')
    if sub_text:
        ax.text(0, -0.35, sub_text, ha='center', va='center', fontsize=11, color='#666')

    ax.set_title(title, fontsize=14, fontweight='bold')

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def render(request_args=None):
    """대시보드1 렌더링"""
    if request_args is None:
        request_args = {}

    filters = get_filter_options()
    menu_items = MenuGenerator.get_category_menu_items(POP_BASE)

    # 파라미터
    base_ym = request_args.get('base_ym', filters['base_ym_list'][0] if filters['base_ym_list'] else '')
    view_type = request_args.get('view_type', 'sigungu')
    sido_nm = request_args.get('sido', '경상북도')
    include_sub = request_args.get('include_sub', '') == 'on'
    age_category = int(request_args.get('age_cat', '1'))

    # 정렬 파라미터
    sort_col = request_args.get('sort', 'region_name')
    sort_dir = request_args.get('dir', 'asc')

    # 선택된 컬럼 타입 (인구, 1인가구, 비율)
    show_pop = request_args.get('show_pop', 'on') == 'on'
    show_single = request_args.get('show_single', 'on') == 'on'
    show_ratio = request_args.get('show_ratio', 'on') == 'on'

    # 선택된 연령그룹 (다중선택)
    selected_ages = request_args.getlist('ages') if hasattr(request_args, 'getlist') else request_args.get('ages', [])
    if isinstance(selected_ages, str):
        selected_ages = [selected_ages] if selected_ages else []

    # 데이터 조회
    indicators = get_summary_indicators(base_ym, view_type, sido_nm if sido_nm else None, include_sub)
    combined_df = get_combined_age_data(base_ym, view_type, sido_nm if sido_nm else None, include_sub, age_category)

    # 피벗 데이터 조회 (지역별 행, 연령그룹별 컬럼)
    pivot_df, age_group_names = get_pivot_data_by_region(base_ym, view_type, sido_nm if sido_nm else None, age_category)

    # 선택된 연령그룹을 현재 카테고리의 유효한 그룹으로 필터링
    selected_ages = [age for age in selected_ages if age in age_group_names]
    # 선택된 연령그룹이 없으면 전체 선택
    if not selected_ages:
        selected_ages = age_group_names.copy()

    # 비율 계산
    total_pop = combined_df['total_pop'].sum()
    combined_df['pop_ratio'] = (combined_df['total_pop'] / total_pop * 100).round(1) if total_pop > 0 else 0

    total_single = combined_df['total_cnt'].sum()
    combined_df['cnt_ratio'] = (combined_df['total_cnt'] / total_single * 100).round(1) if total_single > 0 else 0

    # 지역 레이블 생성
    if view_type == 'region':
        region_label = '전국'
    elif view_type == 'sido':
        region_label = sido_nm if sido_nm else '시도별'
    else:  # sigungu
        region_label = f'{sido_nm} 시군구' if sido_nm else '시군구'

    # 차트 생성
    pyramid_chart = create_pyramid_chart(combined_df, f'연령별 인구 피라미드 ({region_label})')
    combined_chart = create_combined_chart(combined_df, 'code_name', f'연령별 인구 vs 1인가구 비교 ({region_label})')
    age_bar_chart = create_bar_chart(combined_df, 'code_name', ['male_pop', 'female_pop'], f'연령별 남녀 인구 ({region_label})', labels=['남자', '여자'])
    single_bar_chart = create_bar_chart(combined_df, 'code_name', ['male_cnt', 'female_cnt'], f'연령별 1인가구 ({region_label})', colors=['#66BB6A', '#FFA726'], labels=['남자', '여자'])

    # 도넛 차트 - 선택한 연령그룹 카테고리 사용
    age_cat_name = next((c['category_name'] for c in filters['age_categories'] if c['category'] == age_category), '연령그룹')
    donut_values = combined_df['total_pop'].tolist()
    donut_labels = combined_df['code_name'].tolist()

    age_donut = create_donut_chart(
        donut_values,
        donut_labels,
        f'{age_cat_name} 인구 구성',
        center_text='총인구',
        sub_text=region_label
    )

    # 1인가구 도넛 차트
    single_donut_values = combined_df['total_cnt'].tolist()
    single_donut = create_donut_chart(
        single_donut_values,
        donut_labels,
        f'{age_cat_name} 1인가구 구성',
        center_text='1인가구',
        sub_text=region_label
    )

    # HTML 옵션 생성
    base_ym_options = ''.join([
        f'<option value="{ym}" {"selected" if ym == base_ym else ""}>{ym[:4]}.{ym[4:]}</option>'
        for ym in filters['base_ym_list']
    ])

    sido_options = '<option value="">-- 시도 선택 --</option>' + ''.join([
        f'<option value="{s}" {"selected" if s == sido_nm else ""}>{s}</option>'
        for s in filters['sido_list']
    ])

    age_cat_radios = ''.join([
        f'''<label class="radio-label">
            <input type="radio" name="age_cat" value="{cat['category']}"
                   {"checked" if cat['category'] == age_category else ""}
                   onchange="this.form.submit()"> {cat['category_name']}
        </label>'''
        for cat in filters['age_categories']
    ])

    menu_html = ''.join([
        f'''<a href="{item['url']}" class="nav-link {'active' if '대시보드1' in item['name'] else ''}">{item['name']}</a>'''
        for item in menu_items
    ])

    # 정렬 URL 생성 함수
    def sort_url(col, table_id):
        next_dir = 'desc' if sort_col == col and sort_dir == 'asc' else 'asc'
        ages_param = '&'.join([f'ages={age}' for age in selected_ages])
        show_params = f"&show_pop={'on' if show_pop else ''}&show_single={'on' if show_single else ''}&show_ratio={'on' if show_ratio else ''}"
        return f"?view_type={view_type}&base_ym={base_ym}&sido={sido_nm}&include_sub={'on' if include_sub else ''}&age_cat={age_category}&{ages_param}{show_params}&sort={col}&dir={next_dir}#{table_id}"

    def sort_icon(col):
        if sort_col == col:
            return '▲' if sort_dir == 'asc' else '▼'
        return '⇅'

    # 테이블 생성 함수 (정렬 기능 포함)
    def make_table(df, cols, headers, table_id):
        # 정렬 적용
        if sort_col and sort_col in df.columns:
            df = df.sort_values(sort_col, ascending=(sort_dir == 'asc'))

        header_html = ''.join([
            f'<th>{h} <a href="{sort_url(cols[i], table_id)}" class="sort-icon">{sort_icon(cols[i])}</a></th>'
            for i, h in enumerate(headers)
        ])

        # 합계 행
        total_cells = []
        for i, c in enumerate(cols):
            if i == 0:
                total_cells.append('<td><strong>합계</strong></td>')
            elif pd.api.types.is_numeric_dtype(df[c]):
                total_cells.append(f'<td><strong>{df[c].sum():,.0f}</strong></td>')
            else:
                total_cells.append('<td></td>')
        total_row = '<tr class="total-row">' + ''.join(total_cells) + '</tr>'

        rows_html = ''
        for _, row in df.iterrows():
            cells = ''.join([
                f'<td>{row[c]:,.0f}</td>' if is_numeric(row[c]) else f'<td>{row[c]}</td>'
                for c in cols
            ])
            rows_html += f'<tr>{cells}</tr>'
        return f'<thead><tr>{header_html}</tr></thead><tbody>{total_row}{rows_html}</tbody>'

    # 피벗 테이블 생성 함수 (지역별 행, 연령그룹별 컬럼)
    def make_pivot_table(df, age_groups, selected_ages, show_pop, show_single, show_ratio, table_id):
        """지역별 피벗 테이블 생성"""
        if df.empty:
            return '<p>데이터가 없습니다.</p>'

        # 정렬 적용
        if sort_col and sort_col in df.columns:
            df = df.sort_values(sort_col, ascending=(sort_dir == 'asc'))

        # 헤더 생성
        headers = ['<th rowspan="2">지역명 <a href="' + sort_url('region_name', table_id) + '" class="sort-icon">' + sort_icon('region_name') + '</a></th>']

        # 총계 컬럼
        sub_headers_total = []
        if show_pop:
            sub_headers_total.append('<th>인구</th>')
        if show_single:
            sub_headers_total.append('<th>1인가구</th>')
        if show_ratio:
            sub_headers_total.append('<th>비율(%)</th>')

        total_colspan = len(sub_headers_total)
        if total_colspan > 0:
            headers.append(f'<th colspan="{total_colspan}">총계</th>')

        # 연령그룹별 컬럼 (구분선 클래스 추가)
        for age in selected_ages:
            sub_count = 0
            if show_pop:
                sub_count += 1
            if show_single:
                sub_count += 1
            if show_ratio:
                sub_count += 1
            if sub_count > 0:
                headers.append(f'<th colspan="{sub_count}" class="group-start">{age}</th>')

        # 서브 헤더 (인구/1인가구/비율) - 첫 번째 컬럼에 구분선
        sub_headers = sub_headers_total.copy()
        for idx, age in enumerate(selected_ages):
            first_col = True
            if show_pop:
                col_name = f'{age}_인구'
                cls = ' class="group-start"' if first_col else ''
                sub_headers.append(f'<th{cls}>인구 <a href="{sort_url(col_name, table_id)}" class="sort-icon">{sort_icon(col_name)}</a></th>')
                first_col = False
            if show_single:
                col_name = f'{age}_1인가구'
                cls = ' class="group-start"' if first_col else ''
                sub_headers.append(f'<th{cls}>1인가구 <a href="{sort_url(col_name, table_id)}" class="sort-icon">{sort_icon(col_name)}</a></th>')
                first_col = False
            if show_ratio:
                col_name = f'{age}_비율'
                cls = ' class="group-start"' if first_col else ''
                sub_headers.append(f'<th{cls}>비율(%) <a href="{sort_url(col_name, table_id)}" class="sort-icon">{sort_icon(col_name)}</a></th>')

        header_html = f'<tr>{"".join(headers)}</tr><tr>{"".join(sub_headers)}</tr>'

        # 합계 행
        total_cells = ['<td><strong>합계</strong></td>']
        if show_pop:
            total_cells.append(f'<td class="num"><strong>{df["총인구"].sum():,.0f}</strong></td>')
        if show_single:
            total_cells.append(f'<td class="num"><strong>{df["총1인가구"].sum():,.0f}</strong></td>')
        if show_ratio:
            avg_ratio = round(df["총1인가구"].sum() / df["총인구"].sum() * 100, 1) if df["총인구"].sum() > 0 else 0
            total_cells.append(f'<td class="num"><strong>{avg_ratio}</strong></td>')

        for age in selected_ages:
            first_col = True
            if show_pop:
                col = f'{age}_인구'
                cls = 'num group-start' if first_col else 'num'
                total_cells.append(f'<td class="{cls}"><strong>{df[col].sum():,.0f}</strong></td>')
                first_col = False
            if show_single:
                col = f'{age}_1인가구'
                cls = 'num group-start' if first_col else 'num'
                total_cells.append(f'<td class="{cls}"><strong>{df[col].sum():,.0f}</strong></td>')
                first_col = False
            if show_ratio:
                pop_col = f'{age}_인구'
                single_col = f'{age}_1인가구'
                avg = round(df[single_col].sum() / df[pop_col].sum() * 100, 1) if df[pop_col].sum() > 0 else 0
                cls = 'num group-start' if first_col else 'num'
                total_cells.append(f'<td class="{cls}"><strong>{avg}</strong></td>')

        total_row = '<tr class="total-row">' + ''.join(total_cells) + '</tr>'

        # 데이터 행
        rows_html = ''
        for _, row in df.iterrows():
            cells = [f'<td>{row["region_name"]}</td>']

            if show_pop:
                cells.append(f'<td class="num">{row["총인구"]:,.0f}</td>')
            if show_single:
                cells.append(f'<td class="num">{row["총1인가구"]:,.0f}</td>')
            if show_ratio:
                cells.append(f'<td class="num">{row["총비율"]}</td>')

            for age in selected_ages:
                first_col = True
                if show_pop:
                    col = f'{age}_인구'
                    cls = 'num group-start' if first_col else 'num'
                    cells.append(f'<td class="{cls}">{row[col]:,.0f}</td>')
                    first_col = False
                if show_single:
                    col = f'{age}_1인가구'
                    cls = 'num group-start' if first_col else 'num'
                    cells.append(f'<td class="{cls}">{row[col]:,.0f}</td>')
                    first_col = False
                if show_ratio:
                    col = f'{age}_비율'
                    cls = 'num group-start' if first_col else 'num'
                    cells.append(f'<td class="{cls}">{row[col]}</td>')

            rows_html += '<tr>' + ''.join(cells) + '</tr>'

        return f'<thead>{header_html}</thead><tbody>{total_row}{rows_html}</tbody>'

    pivot_table = make_pivot_table(pivot_df, age_group_names, selected_ages, show_pop, show_single, show_ratio, 'pivot-table')

    # 연령그룹 체크박스 생성
    age_checkboxes = ''.join([
        f'''<label class="checkbox-label">
            <input type="checkbox" name="ages" value="{age}"
                   {"checked" if age in selected_ages else ""}> {age}
        </label>'''
        for age in age_group_names
    ])

    # 시군구 옵션 표시 여부
    show_sigungu_opts = "flex" if view_type in ["sigungu", "sido"] else "none"

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>인구통계 대시보드 - 연령별/1인가구 분석</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Malgun Gothic', sans-serif; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #1243A6, #1D64F2); color: white; padding: 1rem; }}
        .header-content {{ display: flex; justify-content: space-between; align-items: center; max-width: 1400px; margin: 0 auto; }}
        .header h1 {{ font-size: 1.3rem; }}
        .main-nav {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
        .nav-link {{ color: rgba(255,255,255,0.8); text-decoration: none; padding: 0.5rem 1rem; border-radius: 4px; font-size: 0.9rem; }}
        .nav-link:hover, .nav-link.active {{ background: rgba(255,255,255,0.2); color: white; }}
        .btn-home {{ background: rgba(255,255,255,0.2); color: white; padding: 0.5rem 1rem; border-radius: 4px; text-decoration: none; }}
        .btn-export {{ background: #28a745; color: white; padding: 0.5rem 1rem; border-radius: 4px; text-decoration: none; cursor: pointer; border: none; font-size: 0.9rem; margin-right: 0.5rem; }}
        .btn-export:hover {{ background: #218838; }}
        .header-buttons {{ display: flex; gap: 0.5rem; align-items: center; }}

        .filter-section {{ background: white; padding: 1rem; border-bottom: 1px solid #ddd; }}
        .filter-row {{ display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap; max-width: 1400px; margin: 0 auto; }}
        .filter-group {{ display: flex; align-items: center; gap: 0.5rem; }}
        .filter-group label {{ font-weight: 500; font-size: 0.9rem; white-space: nowrap; }}
        .filter-group select {{ padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; min-width: 120px; }}
        .radio-group {{ display: flex; gap: 0.75rem; flex-wrap: wrap; }}
        .radio-label {{ display: flex; align-items: center; cursor: pointer; font-size: 0.9rem; }}
        .radio-label input {{ margin-right: 4px; }}
        .btn-search {{ background: #1D64F2; color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 4px; cursor: pointer; }}
        .btn-search:hover {{ background: #1243A6; }}

        .sigungu-options {{ display: {show_sigungu_opts}; gap: 1rem; align-items: center; }}

        .main-content {{ max-width: 1400px; margin: 1rem auto; padding: 0 1rem; }}

        /* 카드 그리드 */
        .indicator-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
        .indicator-card {{ background: white; border-radius: 8px; padding: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
        .indicator-card .label {{ font-size: 0.85rem; color: #666; margin-bottom: 0.5rem; }}
        .indicator-card .value {{ font-size: 1.5rem; font-weight: 700; color: #1243A6; }}
        .indicator-card .unit {{ font-size: 0.75rem; color: #888; }}
        .indicator-card.highlight {{ background: linear-gradient(135deg, #1243A6, #1D64F2); color: white; }}
        .indicator-card.highlight .label {{ color: rgba(255,255,255,0.8); }}
        .indicator-card.highlight .value {{ color: white; }}
        .indicator-card.highlight .unit {{ color: rgba(255,255,255,0.7); }}

        .section {{ background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1.5rem; padding: 1.5rem; }}
        .section-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #1243A6; }}

        .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem; }}
        .chart-container {{ text-align: center; }}
        .chart-container img {{ max-width: 100%; height: auto; }}

        /* 테이블 스크롤 컨테이너 */
        .table-scroll-container {{ position: relative; }}
        .table-scroll-wrapper {{ overflow-x: auto; max-width: 100%; scrollbar-width: thin; }}
        .table-scroll-wrapper::-webkit-scrollbar {{ height: 12px; }}
        .table-scroll-wrapper::-webkit-scrollbar-track {{ background: #f1f1f1; border-radius: 6px; }}
        .table-scroll-wrapper::-webkit-scrollbar-thumb {{ background: #1D64F2; border-radius: 6px; }}
        .table-scroll-wrapper::-webkit-scrollbar-thumb:hover {{ background: #1243A6; }}
        .scroll-buttons {{ display: flex; justify-content: flex-end; gap: 0.5rem; margin-bottom: 0.5rem; }}
        .scroll-btn {{ background: #1D64F2; color: white; border: none; padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }}
        .scroll-btn:hover {{ background: #1243A6; }}

        .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; min-width: 800px; }}
        .data-table th {{ background: #1243A6; color: white; padding: 0.5rem; text-align: right; white-space: nowrap; }}
        .data-table th:first-child {{ text-align: left; position: sticky; left: 0; z-index: 2; background: #1243A6; }}
        .data-table td {{ padding: 0.5rem; border-bottom: 1px solid #eee; text-align: right; }}
        .data-table td:first-child {{ text-align: left; position: sticky; left: 0; z-index: 1; background: white; }}
        .data-table tbody tr:hover td {{ background: #f0f7ff; }}
        .data-table tbody tr:hover td:first-child {{ background: #f0f7ff; }}
        .data-table tbody tr.total-row td {{ background: #e8f4fd; }}
        .data-table tbody tr.total-row td:first-child {{ background: #e8f4fd; }}
        .data-table tbody tr.total-row {{ border-bottom: 2px solid #1243A6; }}
        .data-table td.num {{ text-align: right; }}
        .sort-icon {{ color: white; text-decoration: none; margin-left: 3px; font-size: 0.8rem; }}
        .sort-icon:hover {{ color: #ffd700; }}
        /* 연령그룹 구분선 */
        .data-table th.group-start {{ border-left: 2px solid #0a2a6e; }}
        .data-table td.group-start {{ border-left: 2px solid #ccc; }}

        /* 컬럼 선택 영역 */
        .column-selector {{ background: #f8f9fa; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
        .column-selector-title {{ font-weight: 600; margin-bottom: 0.75rem; color: #333; }}
        .checkbox-group {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem; }}
        .checkbox-label {{ display: inline-flex; align-items: center; background: white; padding: 0.3rem 0.6rem; border-radius: 4px; border: 1px solid #ddd; cursor: pointer; font-size: 0.85rem; }}
        .checkbox-label:hover {{ border-color: #1D64F2; }}
        .checkbox-label input {{ margin-right: 4px; }}
        .checkbox-label input:checked + span {{ color: #1D64F2; font-weight: 500; }}
        .data-type-selector {{ display: flex; gap: 1rem; align-items: center; }}
        .data-type-label {{ display: inline-flex; align-items: center; cursor: pointer; font-size: 0.9rem; padding: 0.4rem 0.8rem; background: white; border: 1px solid #ddd; border-radius: 4px; }}
        .data-type-label:hover {{ border-color: #1D64F2; }}
        .data-type-label input:checked ~ span {{ color: #1D64F2; font-weight: 600; }}
        .btn-apply {{ background: #1D64F2; color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 4px; cursor: pointer; margin-left: 1rem; }}
        .btn-apply:hover {{ background: #1243A6; }}
        .btn-select-all {{ background: #6c757d; color: white; border: none; padding: 0.3rem 0.8rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; margin-left: 0.5rem; }}
        .btn-select-all:hover {{ background: #5a6268; }}

        /* 로딩 인디케이터 - 초기에 표시, 페이지 로드 후 숨김 */
        .loading-overlay {{ display: flex; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.95); z-index: 9999; justify-content: center; align-items: center; flex-direction: column; }}
        .loading-overlay.hidden {{ display: none; }}
        .loading-spinner {{ width: 50px; height: 50px; border: 5px solid #e0e0e0; border-top: 5px solid #1D64F2; border-radius: 50%; animation: spin 1s linear infinite; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        .loading-text {{ margin-top: 1rem; font-size: 1rem; color: #333; font-weight: 500; }}
        .loading-subtext {{ margin-top: 0.5rem; font-size: 0.85rem; color: #666; }}

        @media (max-width: 768px) {{
            .main-nav {{ display: none; }}
            .filter-row {{ flex-direction: column; align-items: flex-start; }}
            .chart-grid {{ grid-template-columns: 1fr; }}
            .checkbox-group {{ max-height: 150px; overflow-y: auto; }}
        }}
    </style>
</head>
<body>
    <!-- 로딩 인디케이터 - 초기 로딩 시 표시 -->
    <div id="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">대시보드를 준비하고 있습니다</div>
        <div class="loading-subtext">데이터를 불러오는 중입니다. 잠시만 기다려주세요...</div>
    </div>

    <header class="header">
        <div class="header-content">
            <h1>연령별/1인가구 분석</h1>
            <nav class="main-nav">{menu_html}</nav>
            <div class="header-buttons">
                <button type="button" class="btn-export" onclick="exportPPT()">PPT 저장</button>
                <a href="/" class="btn-home">홈</a>
            </div>
        </div>
    </header>

    <form id="mainForm" method="get" onsubmit="showLoading()">
    <div class="filter-section">
        <div class="filter-row">
            <div class="filter-group">
                <label>기준년월</label>
                <select name="base_ym">{base_ym_options}</select>
            </div>

            <div class="filter-group radio-group">
                <label class="radio-label">
                    <input type="radio" name="view_type" value="region" {"checked" if view_type == "region" else ""} onchange="this.form.submit()"> 권역별
                </label>
                <label class="radio-label">
                    <input type="radio" name="view_type" value="sido" {"checked" if view_type == "sido" else ""} onchange="this.form.submit()"> 시도별
                </label>
                <label class="radio-label">
                    <input type="radio" name="view_type" value="sigungu" {"checked" if view_type == "sigungu" else ""} onchange="this.form.submit()"> 시군구
                </label>
            </div>

            <div class="sigungu-options">
                <div class="filter-group">
                    <label>시도</label>
                    <select name="sido" onchange="this.form.submit()">{sido_options}</select>
                </div>
                <label class="radio-label">
                    <input type="checkbox" name="include_sub" {"checked" if include_sub else ""} onchange="this.form.submit()"> 하위시군구 구분
                </label>
            </div>

            <div class="filter-group">
                <label>연령그룹</label>
                <div class="radio-group">{age_cat_radios}</div>
            </div>

            <button type="submit" class="btn-search">조회</button>
        </div>
    </div>

    <main class="main-content">
        <!-- 주요 지표 카드 -->
        <div class="indicator-grid">
            <div class="indicator-card">
                <div class="label">총인구</div>
                <div class="value">{indicators['total_pop']:,}</div>
                <div class="unit">명</div>
            </div>
            <div class="indicator-card">
                <div class="label">총세대수</div>
                <div class="value">{indicators['household_cnt']:,}</div>
                <div class="unit">세대</div>
            </div>
            <div class="indicator-card highlight">
                <div class="label">고령화율</div>
                <div class="value">{indicators['elderly_ratio']}</div>
                <div class="unit">% (65세 이상)</div>
            </div>
            <div class="indicator-card">
                <div class="label">유소년율</div>
                <div class="value">{indicators['youth_ratio']}</div>
                <div class="unit">% (0-14세)</div>
            </div>
            <div class="indicator-card">
                <div class="label">생산가능인구</div>
                <div class="value">{indicators['working_ratio']}</div>
                <div class="unit">% (15-64세)</div>
            </div>
            <div class="indicator-card highlight">
                <div class="label">1인가구 비율</div>
                <div class="value">{indicators['single_ratio']}</div>
                <div class="unit">%</div>
            </div>
            <div class="indicator-card">
                <div class="label">노령화지수</div>
                <div class="value">{indicators['aging_index']}</div>
                <div class="unit">유소년 100명당</div>
            </div>
            <div class="indicator-card">
                <div class="label">세대당 인구</div>
                <div class="value">{indicators['pop_per_house']}</div>
                <div class="unit">명</div>
            </div>
        </div>

        <!-- 연령대별 구성 -->
        <div class="section">
            <div class="section-title">{age_cat_name} 인구/1인가구 구성 ({region_label})</div>
            <div class="chart-grid">
                <div class="chart-container">
                    <img src="{age_donut}" alt="연령대별 인구 구성">
                </div>
                <div class="chart-container">
                    <img src="{single_donut}" alt="연령대별 1인가구 구성">
                </div>
            </div>
        </div>

        <!-- 인구 피라미드 -->
        <div class="section">
            <div class="section-title">인구 피라미드 ({region_label})</div>
            <div class="chart-container" style="max-width: 800px; margin: 0 auto;">
                <img src="{pyramid_chart}" alt="인구 피라미드">
            </div>
        </div>

        <!-- 연령별 인구 vs 1인가구 비교 차트 -->
        <div class="section">
            <div class="section-title">연령별 인구 vs 1인가구 비교 ({region_label})</div>
            <div class="chart-container">
                <img src="{combined_chart}" alt="인구 vs 1인가구 비교">
            </div>
        </div>

        <!-- 연령 그룹별 상세 차트 -->
        <div class="section">
            <div class="section-title">연령별 남녀 인구 / 1인가구 상세</div>
            <div class="chart-grid">
                <div class="chart-container">
                    <img src="{age_bar_chart}" alt="연령별 인구">
                </div>
                <div class="chart-container">
                    <img src="{single_bar_chart}" alt="연령별 1인가구">
                </div>
            </div>
        </div>

        <!-- 지역별 연령그룹 피벗 테이블 -->
        <div class="section" id="pivot-table">
            <div class="section-title">지역별 연령 그룹 현황 ({region_label})</div>

            <!-- 컬럼 선택 영역 -->
            <div class="column-selector">
                <div class="column-selector-title">표시할 데이터 선택</div>
                <div class="data-type-selector">
                    <label class="data-type-label">
                        <input type="checkbox" name="show_pop" {"checked" if show_pop else ""}>
                        <span>인구수</span>
                    </label>
                    <label class="data-type-label">
                        <input type="checkbox" name="show_single" {"checked" if show_single else ""}>
                        <span>1인가구수</span>
                    </label>
                    <label class="data-type-label">
                        <input type="checkbox" name="show_ratio" {"checked" if show_ratio else ""}>
                        <span>1인가구비율(%)</span>
                    </label>
                </div>

                <div class="column-selector-title" style="margin-top: 1rem;">
                    표시할 연령그룹 선택
                    <button type="button" class="btn-select-all" onclick="selectAllAges(true)">전체선택</button>
                    <button type="button" class="btn-select-all" onclick="selectAllAges(false)">전체해제</button>
                </div>
                <div class="checkbox-group">
                    {age_checkboxes}
                </div>

                <button type="submit" class="btn-apply">적용</button>
            </div>

            <div class="table-scroll-container">
                <div class="scroll-buttons">
                    <button type="button" class="scroll-btn" onclick="scrollTable(-300)">◀ 왼쪽</button>
                    <button type="button" class="scroll-btn" onclick="scrollTable(300)">오른쪽 ▶</button>
                </div>
                <div class="table-scroll-wrapper" id="tableWrapper">
                    <table class="data-table">{pivot_table}</table>
                </div>
            </div>
        </div>
    </main>
    </form>

    <script>
        // 페이지 로드 완료 시 로딩 화면 숨김
        window.addEventListener('load', function() {{
            setTimeout(function() {{
                document.getElementById('loading').classList.add('hidden');
            }}, 100);
        }});

        // 시도별/시군구/권역별 전환 시 시군구 옵션 표시/숨김
        document.querySelectorAll('input[name="view_type"]').forEach(radio => {{
            radio.addEventListener('change', function() {{
                document.querySelector('.sigungu-options').style.display =
                    (this.value === 'sigungu' || this.value === 'sido') ? 'flex' : 'none';
            }});
        }});

        // 연령그룹 전체선택/해제
        function selectAllAges(checked) {{
            document.querySelectorAll('input[name="ages"]').forEach(cb => {{
                cb.checked = checked;
            }});
        }}

        // 테이블 좌우 스크롤
        function scrollTable(amount) {{
            var wrapper = document.getElementById('tableWrapper');
            wrapper.scrollBy({{ left: amount, behavior: 'smooth' }});
        }}

        // 로딩 표시
        function showLoading() {{
            var loadingEl = document.getElementById('loading');
            loadingEl.classList.remove('hidden');
            // 로딩 메시지 업데이트
            loadingEl.querySelector('.loading-text').textContent = '데이터를 불러오는 중...';
            loadingEl.querySelector('.loading-subtext').textContent = '조회 조건에 맞는 데이터를 가져오고 있습니다.';
        }}

        // 페이지 전환 시 로딩 표시
        document.querySelectorAll('select[onchange], input[onchange]').forEach(el => {{
            el.addEventListener('change', showLoading);
        }});

        // 링크 클릭 시 로딩 (정렬 등)
        document.querySelectorAll('a.sort-icon').forEach(link => {{
            link.addEventListener('click', showLoading);
        }});

        // 폼 제출 시 로딩 표시
        document.getElementById('mainForm').addEventListener('submit', showLoading);

        // PPT 내보내기 함수
        function exportPPT() {{
            showLoading();
            var loadingEl = document.getElementById('loading');
            loadingEl.querySelector('.loading-text').textContent = 'PPT 파일 생성 중...';
            loadingEl.querySelector('.loading-subtext').textContent = '보고서를 생성하고 있습니다. 잠시만 기다려주세요.';

            // 현재 파라미터를 가져와서 export 요청 (iframe 사용)
            var params = new URLSearchParams(window.location.search);
            params.set('action', 'export_ppt');
            var downloadUrl = window.location.pathname + '?' + params.toString();

            // 숨겨진 iframe으로 다운로드 (페이지 이동 없이)
            var iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = downloadUrl;
            document.body.appendChild(iframe);

            // 다운로드 완료 후 로딩 화면 숨김 (3초 후)
            setTimeout(function() {{
                loadingEl.classList.add('hidden');
                document.body.removeChild(iframe);
            }}, 3000);
        }}
    </script>
</body>
</html>'''

    # PPT 내보내기 처리
    if request_args.get('action') == 'export_ppt':
        return export_dashboard_ppt(
            title="인구통계 대시보드 - 연령별/1인가구 분석",
            subtitle=f"{region_label} | {base_ym[:4]}.{base_ym[4:]}",
            indicators=indicators,
            combined_df=combined_df,
            pivot_df=pivot_df,
            charts={
                'pyramid': pyramid_chart,
                'combined': combined_chart,
                'age_bar': age_bar_chart,
                'single_bar': single_bar_chart,
                'age_donut': age_donut,
                'single_donut': single_donut
            },
            source_file=__file__
        )

    return html
