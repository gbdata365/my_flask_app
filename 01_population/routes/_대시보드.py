# -*- coding: utf-8 -*-
"""
인구통계 대시보드 - matplotlib 시각화
"""
import sys
import io
import base64
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # GUI 없이 이미지 생성 (tkinter 에러 방지)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import koreanize_matplotlib


def is_numeric(val):
    """숫자 타입 여부 확인 (Python int/float, numpy 숫자 타입 포함)"""
    return isinstance(val, (int, float, np.integer, np.floating))

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_connection
from module.menu_generator import MenuGenerator

POP_BASE = Path(__file__).parent.parent


def get_filter_options():
    """필터 옵션 조회"""
    conn = get_db_connection()
    try:
        base_ym_df = pd.read_sql("""
            SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as base_ym
            FROM fact_population_basic
            ORDER BY base_ym DESC
        """, conn)

        sido_df = pd.read_sql("""
            SELECT DISTINCT sido_nm, MIN(admin_code) as sort_key
            FROM dim_admin_area
            WHERE sido_nm IS NOT NULL
            GROUP BY sido_nm
            ORDER BY sort_key
        """, conn)

        return {
            'base_ym_list': base_ym_df['base_ym'].tolist(),
            'sido_list': sido_df['sido_nm'].tolist()
        }
    finally:
        conn.close()


def get_region_data(base_ym=None):
    """권역별 데이터 조회"""
    conn = get_db_connection()
    try:
        where_clause = ""
        if base_ym:
            where_clause = f"AND TO_CHAR(f.base_ym, 'YYYYMM') = '{base_ym}'"

        df = pd.read_sql(f"""
            SELECT
                d.region_code as 코드,
                d.region_nm as 권역,
                SUM(f.total_pop) as 총인구,
                SUM(f.male_pop) as 남자,
                SUM(f.female_pop) as 여자,
                SUM(f.household_cnt) as 세대수
            FROM fact_population_basic f
            JOIN dim_admin_area d ON f.admin_code = d.admin_code
            WHERE d.region_nm IS NOT NULL
            {where_clause}
            GROUP BY d.region_nm, d.region_code
            ORDER BY d.region_code
        """, conn)
        return df
    finally:
        conn.close()


def get_sido_data(base_ym=None):
    """시도별 데이터 조회"""
    conn = get_db_connection()
    try:
        where_clause = ""
        if base_ym:
            where_clause = f"AND TO_CHAR(f.base_ym, 'YYYYMM') = '{base_ym}'"

        df = pd.read_sql(f"""
            SELECT
                d.sido_code as 코드,
                d.sido_nm as 시도,
                SUM(f.total_pop) as 총인구,
                SUM(f.male_pop) as 남자,
                SUM(f.female_pop) as 여자,
                SUM(f.household_cnt) as 세대수
            FROM fact_population_basic f
            JOIN dim_admin_area d ON f.admin_code = d.admin_code
            WHERE d.sido_nm IS NOT NULL
            {where_clause}
            GROUP BY d.sido_nm, d.sido_code
            ORDER BY d.sido_code
        """, conn)
        return df
    finally:
        conn.close()


def get_sigungu_data(sido_nm, base_ym=None, include_sub_district=False):
    """시군구별 데이터 조회"""
    conn = get_db_connection()
    try:
        base_ym_clause = ""
        if base_ym:
            base_ym_clause = f"AND TO_CHAR(f.base_ym, 'YYYYMM') = '{base_ym}'"

        if include_sub_district:
            # 하위시군구 구분 (개별 표시)
            df = pd.read_sql(f"""
                SELECT
                    d.sigungu_code as 코드,
                    d.sigungu_nm as 시군구,
                    SUM(f.total_pop) as 총인구,
                    SUM(f.male_pop) as 남자,
                    SUM(f.female_pop) as 여자,
                    SUM(f.household_cnt) as 세대수
                FROM fact_population_basic f
                JOIN dim_admin_area d ON f.admin_code = d.admin_code
                WHERE d.sido_nm = '{sido_nm}'
                AND d.sigungu_nm IS NOT NULL
                {base_ym_clause}
                GROUP BY d.sigungu_nm, d.sigungu_code
                ORDER BY d.sigungu_code
            """, conn)
        else:
            # 하위시군구 합산: sigungu_code 5번째 자리가 '0'인 것의 이름 사용
            df = pd.read_sql(f"""
                WITH parent_sigungu AS (
                    SELECT DISTINCT
                        sigungu_code,
                        sigungu_nm
                    FROM dim_admin_area
                    WHERE sido_nm = '{sido_nm}'
                    AND SUBSTRING(sigungu_code, 5, 1) = '0'
                )
                SELECT
                    ps.sigungu_code as 코드,
                    ps.sigungu_nm as 시군구,
                    SUM(f.total_pop) as 총인구,
                    SUM(f.male_pop) as 남자,
                    SUM(f.female_pop) as 여자,
                    SUM(f.household_cnt) as 세대수
                FROM fact_population_basic f
                JOIN dim_admin_area d ON f.admin_code = d.admin_code
                JOIN parent_sigungu ps ON ps.sigungu_code = LEFT(d.sigungu_code, 4) || '0'
                WHERE d.sido_nm = '{sido_nm}'
                AND d.sigungu_nm IS NOT NULL
                {base_ym_clause}
                GROUP BY ps.sigungu_code, ps.sigungu_nm
                ORDER BY ps.sigungu_code
            """, conn)
        return df
    finally:
        conn.close()


def create_bar_chart(df, x_col, y_col, title):
    """막대 차트 생성 후 base64 반환"""
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = plt.cm.Blues(range(50, 250, int(200/len(df))))
    bars = ax.bar(df[x_col], df[y_col], color=colors)

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel(x_col, fontsize=11)
    ax.set_ylabel(y_col, fontsize=11)

    # Y축 천 단위 콤마 포맷
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: format(int(x), ',')))

    # 값 표시 (천 단위 콤마)
    for bar, val in zip(bars, df[y_col]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{val:,.0f}', ha='center', va='bottom', fontsize=8)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def render(request_args=None):
    """대시보드 렌더링"""
    if request_args is None:
        request_args = {}

    filters = get_filter_options()
    menu_items = MenuGenerator.get_category_menu_items(POP_BASE)

    # 파라미터
    base_ym = request_args.get('base_ym', filters['base_ym_list'][0] if filters['base_ym_list'] else '')
    view_type = request_args.get('view_type', 'sigungu')  # 기본값: 시군구별
    sido_nm = request_args.get('sido', '경상북도')  # 기본값: 경상북도
    include_sub = request_args.get('include_sub', '') == 'on'
    sort_col = request_args.get('sort', '')
    sort_dir = request_args.get('dir', 'asc')

    # 데이터 조회
    if view_type == 'region':
        df = get_region_data(base_ym)
        x_col = '권역'
        title = '권역별 인구'
    elif view_type == 'sigungu' and sido_nm:
        df = get_sigungu_data(sido_nm, base_ym, include_sub)
        x_col = '시군구'
        title = f'{sido_nm} 시군구별 인구'
    else:
        df = get_sido_data(base_ym)
        x_col = '시도'
        title = '시도별 인구'
        view_type = 'sido'

    # 정렬
    if sort_col and sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=(sort_dir == 'asc'))

    # 차트 생성
    chart_img = create_bar_chart(df, x_col, '총인구', title) if not df.empty else ''

    # 기준년월 옵션
    base_ym_options = ''.join([
        f'<option value="{ym}" {"selected" if ym == base_ym else ""}>{ym[:4]}.{ym[4:]}</option>'
        for ym in filters['base_ym_list']
    ])

    # 시도 옵션
    sido_options = '<option value="">-- 시도 선택 --</option>' + ''.join([
        f'<option value="{s}" {"selected" if s == sido_nm else ""}>{s}</option>'
        for s in filters['sido_list']
    ])

    # 메뉴 HTML
    menu_html = ''.join([
        f'''<a href="{item['url']}" class="nav-link {'active' if '대시보드' in item['name'] else ''}">{item['name']}</a>'''
        for item in menu_items
    ])

    # 테이블 HTML
    def sort_icon(col):
        if sort_col == col:
            arrow = '▲' if sort_dir == 'asc' else '▼'
            next_dir = 'desc' if sort_dir == 'asc' else 'asc'
        else:
            arrow = '⇅'
            next_dir = 'asc'
        return f'<a href="?view_type={view_type}&base_ym={base_ym}&sido={sido_nm}&include_sub={"on" if include_sub else ""}&sort={col}&dir={next_dir}" class="sort-icon">{arrow}</a>'

    table_header = ''.join([f'<th>{col} {sort_icon(col)}</th>' for col in df.columns])

    # 셀 포맷 함수
    def format_cell(val, bold=False):
        """숫자는 천 단위 콤마, 그 외는 그대로"""
        if is_numeric(val):
            formatted = f'{val:,.0f}'
        else:
            formatted = str(val) if val is not None else ''
        return f'<td><strong>{formatted}</strong></td>' if bold else f'<td>{formatted}</td>'

    # 합계 행 생성 (숫자 컬럼은 동적으로 합산)
    total_row = ''
    if not df.empty:
        total_cells = []
        for i, col in enumerate(df.columns):
            if i == 0:
                total_cells.append('<td><strong>합계</strong></td>')
            elif pd.api.types.is_numeric_dtype(df[col]):
                total_cells.append(f'<td><strong>{df[col].sum():,.0f}</strong></td>')
            else:
                total_cells.append('<td><strong></strong></td>')
        total_row = '<tr class="total-row">' + ''.join(total_cells) + '</tr>'

    # 데이터 행 생성
    table_rows = total_row + ''.join([
        '<tr>' + ''.join([format_cell(v) for v in row]) + '</tr>'
        for row in df.values
    ])

    # sigungu-options 표시 여부
    show_sigungu_opts = "flex" if view_type == "sigungu" else "none"

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>인구통계 대시보드</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Malgun Gothic', sans-serif; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #1243A6, #1D64F2); color: white; padding: 1rem; }}
        .header-content {{ display: flex; justify-content: space-between; align-items: center; max-width: 1400px; margin: 0 auto; }}
        .header h1 {{ font-size: 1.3rem; }}
        .main-nav {{ display: flex; gap: 0.5rem; }}
        .nav-link {{ color: rgba(255,255,255,0.8); text-decoration: none; padding: 0.5rem 1rem; border-radius: 4px; }}
        .nav-link:hover, .nav-link.active {{ background: rgba(255,255,255,0.2); color: white; }}
        .btn-home {{ background: rgba(255,255,255,0.2); color: white; padding: 0.5rem 1rem; border-radius: 4px; text-decoration: none; }}

        .filter-section {{ background: white; padding: 1rem; border-bottom: 1px solid #ddd; }}
        .filter-row {{ display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap; max-width: 1400px; margin: 0 auto; }}
        .filter-group {{ display: flex; align-items: center; gap: 0.5rem; }}
        .filter-group label {{ font-weight: 500; font-size: 0.9rem; white-space: nowrap; }}
        .filter-group select {{ padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; min-width: 120px; }}
        .filter-group input[type="radio"] {{ margin-right: 4px; }}
        .filter-group input[type="checkbox"] {{ margin-right: 4px; }}
        .radio-group {{ display: flex; gap: 1rem; }}
        .radio-label {{ display: flex; align-items: center; cursor: pointer; }}
        .btn-search {{ background: #1D64F2; color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 4px; cursor: pointer; }}
        .btn-search:hover {{ background: #1243A6; }}

        .main-content {{ max-width: 1400px; margin: 1rem auto; padding: 0 1rem; }}
        .card {{ background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem; }}
        .card-header {{ padding: 1rem; border-bottom: 1px solid #eee; font-weight: 600; }}
        .card-body {{ padding: 1rem; }}

        .data-table {{ width: 100%; border-collapse: collapse; }}
        .data-table th {{ background: #1243A6; color: white; padding: 0.75rem; text-align: left; white-space: nowrap; }}
        .data-table th:not(:first-child) {{ text-align: right; }}
        .data-table td {{ padding: 0.75rem; border-bottom: 1px solid #eee; }}
        .data-table td:not(:first-child) {{ text-align: right; }}
        .data-table tbody tr:hover {{ background: #f0f7ff; }}
        .data-table tbody tr.total-row {{ background: #e8f4fd; border-bottom: 2px solid #1243A6; }}
        .data-table tbody tr.total-row:hover {{ background: #d0e8f9; }}
        .sort-icon {{ color: white; text-decoration: none; margin-left: 5px; }}
        .sort-icon:hover {{ color: #ffd700; }}

        .chart-container {{ text-align: center; }}
        .chart-container img {{ max-width: 100%; height: auto; }}

        .sigungu-options {{ display: {show_sigungu_opts}; gap: 1rem; align-items: center; }}

        @media (max-width: 768px) {{
            .filter-row {{ flex-direction: column; align-items: flex-start; }}
            .main-nav {{ display: none; }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>인구통계 대시보드</h1>
            <nav class="main-nav">{menu_html}</nav>
            <a href="/" class="btn-home">홈</a>
        </div>
    </header>

    <form class="filter-section" method="get">
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

            <button type="submit" class="btn-search">조회</button>
        </div>
    </form>

    <main class="main-content">
        <div class="card">
            <div class="card-header">
                {title} ({base_ym[:4]}.{base_ym[4:]}) - {len(df)}건
            </div>
            <div class="card-body">
                <table class="data-table">
                    <thead><tr>{table_header}</tr></thead>
                    <tbody>{table_rows if not df.empty else '<tr><td colspan="6" style="text-align:center">데이터가 없습니다</td></tr>'}</tbody>
                </table>
            </div>
        </div>

        {"<div class='card'><div class='card-header'>차트</div><div class='card-body chart-container'><img src='" + chart_img + "' alt='차트'></div></div>" if chart_img else ""}
    </main>

    <script>
        // 시도별/시군구/권역별 전환 시 시군구 옵션 표시/숨김
        document.querySelectorAll('input[name="view_type"]').forEach(radio => {{
            radio.addEventListener('change', function() {{
                document.querySelector('.sigungu-options').style.display =
                    this.value === 'sigungu' ? 'flex' : 'none';
            }});
        }});
    </script>
</body>
</html>'''
    return html
