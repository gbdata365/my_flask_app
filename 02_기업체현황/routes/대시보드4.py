# -*- coding: utf-8 -*-
"""
기업통계등록부(SBR) 대시보드 4 - 상세 분석
==========================================

주요 기능:
1. 산업별 현황: 21개 산업 분포, 파이차트/막대그래프
2. 영업상태 분석: 영업중 vs 폐업 비율, 추이
3. 조직형태별 분석: 개인사업체, 회사법인 등 비율
4. 인구/가구 연계 심화 분석
5. 데이터 테이블 표시

필터: 라디오버튼(전체/권역별/시도별) + 시도 선택
"""

import sys
import os
import tempfile
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from flask import request, Response, send_file, make_response
from loguru import logger
from urllib.parse import quote

# 상위 디렉토리 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_connection
from module.region_config import get_region_sido_mapping

# PPT 관련 임포트
try:
    from module.ppt_utils import create_dashboard_ppt, PPT_AVAILABLE
except ImportError:
    PPT_AVAILABLE = False


def get_filter_options():
    """필터 옵션 조회"""
    conn = get_db_connection()

    query_quarters = """
        SELECT DISTINCT "CRTR_YR", "QU_SE_CD",
               "CRTR_YR" || 'Q' || "QU_SE_CD" as quarter_label
        FROM sbr_quarter_summary
        ORDER BY "CRTR_YR" DESC, "QU_SE_CD" DESC
    """
    df_quarters = pd.read_sql(query_quarters, conn)

    query_sido = """
        SELECT DISTINCT "CTPV_NM"
        FROM sbr_quarter_summary
        WHERE "CTPV_NM" IS NOT NULL
        ORDER BY "CTPV_NM"
    """
    df_sido = pd.read_sql(query_sido, conn)

    conn.close()

    return {
        'quarters': df_quarters.to_dict('records'),
        'sido_list': df_sido['CTPV_NM'].tolist()
    }


def get_industry_data(year, quarter, view_type, sido=None):
    """산업별 현황 데이터 조회"""
    conn = get_db_connection()

    industry_columns = [
        'IND_농업,임업,어업', 'IND_광업', 'IND_제조업', 'IND_전기가스공급업',
        'IND_수도하수폐기물', 'IND_건설업', 'IND_도매및소매업', 'IND_운수및창고업',
        'IND_숙박및음식점업', 'IND_정보통신업', 'IND_금융및보험업', 'IND_부동산업',
        'IND_전문과학기술서비스', 'IND_사업시설관리', 'IND_공공행정', 'IND_교육서비스업',
        'IND_보건사회복지', 'IND_예술스포츠여가', 'IND_협회및개인서비스',
        'IND_가구내고용활동', 'IND_국제외국기관'
    ]

    industry_cols_sum = ', '.join([f'SUM("{col}") as "{col}"' for col in industry_columns])

    if view_type == '시도별' and sido:
        region_filter = f"AND \"CTPV_NM\" = '{sido}'"
    else:
        region_filter = ""

    query = f"""
        SELECT {industry_cols_sum}
        FROM sbr_quarter_summary
        WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
            AND "CTPV_NM" IS NOT NULL
            {region_filter}
    """

    df = pd.read_sql(query, conn)
    conn.close()

    result = []
    for col in industry_columns:
        industry_name = col.replace('IND_', '')
        value = df[col].iloc[0] if col in df.columns else 0
        if pd.notna(value) and value > 0:
            result.append({'산업': industry_name, '사업체수': int(value)})

    df_result = pd.DataFrame(result)
    df_result = df_result.sort_values('사업체수', ascending=False)
    df_result['비율'] = (df_result['사업체수'] / df_result['사업체수'].sum() * 100).round(2)

    return df_result


def get_org_type_data(year, quarter, view_type, sido=None):
    """조직형태별 데이터 조회"""
    conn = get_db_connection()

    org_columns = ['ORG_개인사업체', 'ORG_회사법인', 'ORG_회사이외법인', 'ORG_비법인단체', 'ORG_국가지방자치단체']
    org_cols_sum = ', '.join([f'SUM("{col}") as "{col}"' for col in org_columns])

    if view_type == '시도별' and sido:
        region_filter = f"AND \"CTPV_NM\" = '{sido}'"
    else:
        region_filter = ""

    query = f"""
        SELECT {org_cols_sum}
        FROM sbr_quarter_summary
        WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
            AND "CTPV_NM" IS NOT NULL
            {region_filter}
    """

    df = pd.read_sql(query, conn)
    conn.close()

    result = []
    for col in org_columns:
        org_name = col.replace('ORG_', '')
        value = df[col].iloc[0] if col in df.columns else 0
        if pd.notna(value) and value > 0:
            result.append({'조직형태': org_name, '사업체수': int(value)})

    df_result = pd.DataFrame(result)
    df_result = df_result.sort_values('사업체수', ascending=False)
    df_result['비율'] = (df_result['사업체수'] / df_result['사업체수'].sum() * 100).round(2)

    return df_result


def get_status_data(year, quarter, view_type, sido=None):
    """영업상태 데이터 조회"""
    conn = get_db_connection()

    if view_type == '시도별' and sido:
        region_filter = f"AND \"CTPV_NM\" = '{sido}'"
    else:
        region_filter = ""

    query = f"""
        SELECT
            SUM("STATUS_영업중") as 영업중,
            SUM("STATUS_폐업") as 폐업,
            SUM("STATUS_합계") as 전체
        FROM sbr_quarter_summary
        WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
            AND "CTPV_NM" IS NOT NULL
            {region_filter}
    """

    df = pd.read_sql(query, conn)
    conn.close()

    return df


def get_status_timeseries(view_type, sido=None):
    """영업상태 시계열 데이터"""
    conn = get_db_connection()

    if view_type == '시도별' and sido:
        region_filter = f"AND \"CTPV_NM\" = '{sido}'"
    else:
        region_filter = ""

    query = f"""
        SELECT
            "CRTR_YR" || 'Q' || "QU_SE_CD" as 분기,
            "CRTR_YR" as 연도,
            "QU_SE_CD" as 분기코드,
            SUM("STATUS_영업중") as 영업중,
            SUM("STATUS_폐업") as 폐업
        FROM sbr_quarter_summary
        WHERE 1=1 {region_filter}
        GROUP BY "CRTR_YR", "QU_SE_CD"
        ORDER BY "CRTR_YR", "QU_SE_CD"
    """

    df = pd.read_sql(query, conn)
    conn.close()

    df['폐업률'] = (df['폐업'] / (df['영업중'] + df['폐업']) * 100).round(2)

    return df


def get_population_industry_data(year, quarter, view_type, sido=None):
    """인구/가구 연계 산업별 데이터"""
    conn = get_db_connection()

    industry_columns = [
        'IND_제조업', 'IND_도매및소매업', 'IND_숙박및음식점업',
        'IND_건설업', 'IND_부동산업', 'IND_보건사회복지'
    ]

    industry_cols_sum = ', '.join([f'SUM(s."{col}") as "{col}"' for col in industry_columns])

    query = f"""
        WITH latest_month AS (
            SELECT MAX(base_ym) as latest_ym
            FROM fact_population_basic
        ),
        sido_pop AS (
            SELECT
                d.sido_nm,
                SUM(f.total_pop) as 총인구,
                SUM(f.household_cnt) as 총가구수
            FROM fact_population_basic f
            JOIN dim_admin_area d ON f.admin_code = d.admin_code
            JOIN latest_month lm ON f.base_ym = lm.latest_ym
            WHERE d.sido_nm IS NOT NULL
            GROUP BY d.sido_nm
        ),
        sido_ind AS (
            SELECT
                s."CTPV_NM" as 시도명,
                {industry_cols_sum}
            FROM sbr_quarter_summary s
            WHERE s."CRTR_YR" = '{year}' AND s."QU_SE_CD" = '{quarter}'
            GROUP BY s."CTPV_NM"
        )
        SELECT
            COALESCE(i.시도명, p.sido_nm) as 시도명,
            COALESCE(p.총인구, 0) as 총인구,
            COALESCE(p.총가구수, 0) as 총가구수,
            {', '.join([f'COALESCE(i."{col}", 0) as "{col}"' for col in industry_columns])}
        FROM sido_pop p
        FULL OUTER JOIN sido_ind i ON p.sido_nm = i.시도명
        WHERE COALESCE(p.총인구, 0) > 0
        ORDER BY 총인구 DESC
    """

    df = pd.read_sql(query, conn)
    conn.close()

    for col in industry_columns:
        new_col = col.replace('IND_', '') + '_밀도'
        df[new_col] = (df[col] / df['총인구'] * 1000).round(2)

    return df


def get_regional_detail_data(year, quarter, view_type, sido=None):
    """지역별 상세 데이터 (표용)"""
    conn = get_db_connection()

    if view_type == '시도별' and sido:
        group_col = '"SGG_NM"'
        region_filter = f"AND \"CTPV_NM\" = '{sido}' AND \"SGG_NM\" IS NOT NULL"
        order_col = '"SGG_NM"'
    elif view_type == '권역별':
        region_mapping = get_region_sido_mapping()
        cases = []
        for region, sidos in region_mapping.items():
            sido_list = "','".join(sidos)
            cases.append(f"WHEN \"CTPV_NM\" IN ('{sido_list}') THEN '{region}'")
        case_sql = " ".join(cases)
        group_col = f"CASE {case_sql} ELSE '기타' END"
        region_filter = ""
        order_col = "1"
    else:
        group_col = '"CTPV_NM"'
        region_filter = ""
        order_col = '"CTPV_NM"'

    query = f"""
        SELECT
            {group_col} as 지역명,
            SUM("ORG_합계") as 총사업체수,
            SUM("STATUS_영업중") as 영업중,
            SUM("STATUS_폐업") as 폐업,
            ROUND(SUM("STATUS_폐업")::numeric / NULLIF(SUM("STATUS_합계")::numeric, 0) * 100, 2) as 폐업률,
            SUM("ORG_개인사업체") as 개인사업체,
            SUM("ORG_회사법인") as 회사법인,
            SUM("STATS_기업종사자수_합계") as 총종사자수,
            ROUND(SUM("STATS_기업종사자수_합계")::numeric / NULLIF(SUM("ORG_합계")::numeric, 0), 1) as 평균종사자수,
            ROUND(SUM("STATS_기업매출금액_합계")::numeric / NULLIF(SUM("STATS_기업종사자수_합계")::numeric, 0), 1) as 인당매출액
        FROM sbr_quarter_summary
        WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
            AND "CTPV_NM" IS NOT NULL
            {region_filter}
        GROUP BY {group_col}
        ORDER BY {order_col}
    """

    df = pd.read_sql(query, conn)
    conn.close()

    return df


def render(request_args=None, request_form=None, method='GET'):
    """Flask에서 호출되는 렌더링 함수"""
    # POST 요청 처리 (PPT 저장)
    try:
        if method == 'POST' and request_form:
            action = request_form.get('action')
            logger.info(f"POST 요청 수신 - action: {action}")
            if action == 'save_ppt':
                logger.info("PPT 저장 핸들러 호출")
                return handle_ppt_save(request_form)
    except Exception as e:
        logger.error(f"POST 처리 중 예외 발생: {e}")

    filter_opts = get_filter_options()

    request_args = request_args or {}
    selected_year = request_args.get('year', filter_opts['quarters'][0]['CRTR_YR'])
    selected_quarter = request_args.get('quarter', filter_opts['quarters'][0]['QU_SE_CD'])
    view_type = request_args.get('view_type', '시도별')
    selected_sido = request_args.get('sido', '경상북도')

    df_industry = get_industry_data(selected_year, selected_quarter, view_type, selected_sido)
    df_org = get_org_type_data(selected_year, selected_quarter, view_type, selected_sido)
    df_status = get_status_data(selected_year, selected_quarter, view_type, selected_sido)
    df_status_ts = get_status_timeseries(view_type, selected_sido)
    df_pop_ind = get_population_industry_data(selected_year, selected_quarter, view_type, selected_sido)
    df_detail = get_regional_detail_data(selected_year, selected_quarter, view_type, selected_sido)

    latest_quarter_label = f"{selected_year}년 {selected_quarter}분기"
    if view_type == '전체':
        region_label = "전국"
    elif view_type == '권역별':
        region_label = "권역별"
    elif view_type == '시도별':
        region_label = f"{selected_sido}"
    else:
        region_label = "전국"

    active_count = int(df_status['영업중'].iloc[0]) if df_status['영업중'].iloc[0] else 0
    closed_count = int(df_status['폐업'].iloc[0]) if df_status['폐업'].iloc[0] else 0
    total_count = active_count + closed_count
    closure_rate = round(closed_count / total_count * 100, 2) if total_count > 0 else 0

    html = generate_html(
        filter_opts, selected_year, selected_quarter, view_type, selected_sido,
        latest_quarter_label, region_label,
        df_industry, df_org, df_status, df_status_ts, df_pop_ind, df_detail,
        active_count, closed_count, closure_rate,
        PPT_AVAILABLE
    )

    return html


def generate_html(filter_opts, selected_year, selected_quarter, view_type, selected_sido,
                  latest_quarter_label, region_label,
                  df_industry, df_org, df_status, df_status_ts, df_pop_ind, df_detail,
                  active_count, closed_count, closure_rate,
                  ppt_available=False):
    """HTML 생성"""

    year_options = ''.join([f'<option value="{q["CRTR_YR"]}" {"selected" if str(q["CRTR_YR"]) == str(selected_year) else ""}>{q["CRTR_YR"]}년</option>'
                           for q in filter_opts['quarters']])
    quarter_options = ''.join([f'<option value="{i}" {"selected" if str(i) == str(selected_quarter) else ""}>{i}분기</option>'
                              for i in range(1, 5)])
    sido_options = ''.join([f'<option value="{sido}" {"selected" if sido == selected_sido else ""}>{sido}</option>'
                           for sido in filter_opts['sido_list']])

    # 상세 테이블 HTML
    table_rows = ''
    for _, row in df_detail.iterrows():
        table_rows += f'''
            <tr>
                <td>{row['지역명']}</td>
                <td class="number">{int(row['총사업체수']):,}</td>
                <td class="number">{int(row['영업중']):,}</td>
                <td class="number">{int(row['폐업']):,}</td>
                <td class="number {'red' if row['폐업률'] > 30 else ''}">{row['폐업률']:.1f}%</td>
                <td class="number">{int(row['개인사업체']):,}</td>
                <td class="number">{int(row['회사법인']):,}</td>
                <td class="number">{int(row['총종사자수']):,}</td>
                <td class="number">{row['평균종사자수']:.1f}</td>
                <td class="number">{row['인당매출액']:.1f}</td>
            </tr>
        '''

    # 산업별 테이블 HTML
    industry_table_rows = ''
    for idx, row in df_industry.head(15).iterrows():
        industry_table_rows += f'''
            <tr>
                <td>{idx + 1}</td>
                <td>{row['산업']}</td>
                <td class="number">{int(row['사업체수']):,}</td>
                <td class="number">{row['비율']:.1f}%</td>
            </tr>
        '''

    html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>기업통계등록부 대시보드 - 상세 분석</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        h1 {{ color: #2c3e50; text-align: center; margin-bottom: 10px; font-size: 2rem; }}
        .subtitle {{ text-align: center; color: #7f8c8d; margin-bottom: 20px; font-size: 1rem; }}
        .filter-container {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 30px;
        }}
        .filter-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }}
        .filter-group {{
            display: flex;
            flex-direction: column;
        }}
        .filter-group label {{
            font-size: 0.9rem;
            color: #2c3e50;
            margin-bottom: 5px;
            font-weight: 600;
        }}
        .filter-group select {{
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 1rem;
            background: white;
        }}
        .radio-group {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .radio-label {{
            display: flex;
            align-items: center;
            cursor: pointer;
            font-size: 1rem;
            color: #2c3e50;
            font-weight: 500;
        }}
        .radio-label input {{
            margin-right: 6px;
            width: 18px;
            height: 18px;
        }}
        .filter-btn {{
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            font-weight: 600;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .metric-card.green {{ background: linear-gradient(135deg, #27ae60, #2ecc71); color: white; }}
        .metric-card.red {{ background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; }}
        .metric-card.blue {{ background: linear-gradient(135deg, #3498db, #2980b9); color: white; }}
        .metric-card.purple {{ background: linear-gradient(135deg, #9b59b6, #8e44ad); color: white; }}
        .metric-label {{ font-size: 0.9rem; opacity: 0.9; margin-bottom: 8px; }}
        .metric-value {{ font-size: 2rem; font-weight: bold; margin-bottom: 5px; }}
        .metric-unit {{ font-size: 0.85rem; opacity: 0.8; }}
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            margin-bottom: 30px;
        }}
        .chart-container {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
        }}
        .chart-container.full-width {{
            grid-column: 1 / -1;
        }}
        .chart-title {{
            font-size: 1.2rem;
            color: #2c3e50;
            margin-bottom: 15px;
            font-weight: 600;
            border-left: 4px solid #3498db;
            padding-left: 12px;
        }}
        .two-col-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            margin-bottom: 30px;
        }}
        .table-container {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            overflow-x: auto;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        .data-table th {{
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            padding: 12px 8px;
            text-align: center;
            font-weight: 600;
            white-space: nowrap;
        }}
        .data-table td {{
            padding: 10px 8px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .data-table td.number {{
            text-align: right;
            font-family: 'Consolas', monospace;
        }}
        .data-table td.red {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .data-table tr:hover {{
            background-color: #f0f7ff;
        }}
        .data-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        @media (max-width: 1200px) {{
            .chart-grid, .two-col-grid {{ grid-template-columns: 1fr; }}
            .metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        @media (max-width: 768px) {{
            .metrics-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 기업통계등록부 상세 분석</h1>
        <p class="subtitle">기준: {latest_quarter_label} | 지역: {region_label}</p>

        <!-- 필터 -->
        <form method="get" class="filter-container">
            <div class="filter-row">
                <div class="filter-group">
                    <label>📅 연도</label>
                    <select name="year">{year_options}</select>
                </div>
                <div class="filter-group">
                    <label>📅 분기</label>
                    <select name="quarter">{quarter_options}</select>
                </div>
            </div>
            <div class="filter-group" style="margin-bottom: 15px;">
                <label>🗺️ 조회 구분</label>
                <div class="radio-group">
                    <label class="radio-label"><input type="radio" name="view_type" value="전체" {"checked" if view_type == "전체" else ""} onchange="toggleSidoSelect()"> 전체</label>
                    <label class="radio-label"><input type="radio" name="view_type" value="권역별" {"checked" if view_type == "권역별" else ""} onchange="toggleSidoSelect()"> 권역별</label>
                    <label class="radio-label"><input type="radio" name="view_type" value="시도별" {"checked" if view_type == "시도별" else ""} onchange="toggleSidoSelect()"> 시도별</label>
                </div>
            </div>
            <div class="filter-group" id="sido-select-group" style="display: {'block' if view_type == '시도별' else 'none'}; margin-bottom: 15px;">
                <label>📍 시도 선택</label>
                <select name="sido">{sido_options}</select>
            </div>
            <div style="text-align: center;">
                <button type="submit" class="filter-btn">🔍 조회하기</button>
            </div>
        </form>

        <!-- 저장 버튼 -->
        <div class="save-section" style="margin: 1rem 0; text-align: right;">
            {f'''
            <form method="post" style="display: inline-block;">
                <input type="hidden" name="action" value="save_ppt">
                <input type="hidden" name="year" value="{selected_year}">
                <input type="hidden" name="quarter" value="{selected_quarter}">
                <input type="hidden" name="view_type" value="{view_type}">
                <input type="hidden" name="sido" value="{selected_sido}">
                <button type="submit" class="save-btn" style="
                    background: linear-gradient(135deg, #D24726, #F5B041);
                    color: white;
                    border: none;
                    padding: 0.6rem 1.2rem;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 0.95rem;
                    font-weight: 500;
                    box-shadow: 0 2px 8px rgba(210, 71, 38, 0.3);
                    transition: all 0.3s ease;
                ">📊 PPT 저장</button>
            </form>
            ''' if ppt_available else '<span style="color: #888; font-size: 0.85rem;">PPT 저장 기능을 사용하려면 python-pptx를 설치하세요</span>'}
        </div>

        <!-- 주요 지표 -->
        <div class="metrics-grid">
            <div class="metric-card green">
                <div class="metric-label">영업중 사업체</div>
                <div class="metric-value">{active_count:,}</div>
                <div class="metric-unit">개</div>
            </div>
            <div class="metric-card red">
                <div class="metric-label">폐업 사업체</div>
                <div class="metric-value">{closed_count:,}</div>
                <div class="metric-unit">개</div>
            </div>
            <div class="metric-card blue">
                <div class="metric-label">폐업률</div>
                <div class="metric-value">{closure_rate:.1f}</div>
                <div class="metric-unit">%</div>
            </div>
            <div class="metric-card purple">
                <div class="metric-label">활성 산업</div>
                <div class="metric-value">{len(df_industry)}</div>
                <div class="metric-unit">개 산업</div>
            </div>
        </div>

        <!-- 차트 영역 -->
        <div class="chart-grid">
            <div class="chart-container">
                <h3 class="chart-title">산업별 사업체 분포</h3>
                <div id="chart-industry-pie"></div>
            </div>
            <div class="chart-container">
                <h3 class="chart-title">조직형태별 분포</h3>
                <div id="chart-org-pie"></div>
            </div>
            <div class="chart-container full-width">
                <h3 class="chart-title">산업별 사업체 현황 (Top 15)</h3>
                <div id="chart-industry-bar"></div>
            </div>
            <div class="chart-container full-width">
                <h3 class="chart-title">영업상태 시계열 추이</h3>
                <div id="chart-status-trend"></div>
            </div>
            <div class="chart-container full-width">
                <h3 class="chart-title">시도별 인구 천명당 주요 산업 밀도</h3>
                <div id="chart-pop-industry"></div>
            </div>
        </div>

        <!-- 테이블 영역 -->
        <div class="two-col-grid">
            <div class="table-container">
                <h3 class="chart-title">산업별 현황표</h3>
                <table class="data-table">
                    <thead>
                        <tr><th>순위</th><th>산업</th><th>사업체수</th><th>비율</th></tr>
                    </thead>
                    <tbody>{industry_table_rows}</tbody>
                </table>
            </div>
            <div class="table-container">
                <h3 class="chart-title">조직형태별 현황표</h3>
                <table class="data-table">
                    <thead>
                        <tr><th>조직형태</th><th>사업체수</th><th>비율</th></tr>
                    </thead>
                    <tbody>
                        {''.join([f"<tr><td>{row['조직형태']}</td><td class='number'>{int(row['사업체수']):,}</td><td class='number'>{row['비율']:.1f}%</td></tr>" for _, row in df_org.iterrows()])}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 지역별 상세 테이블 -->
        <div class="table-container" style="margin-top: 20px;">
            <h3 class="chart-title">지역별 상세 현황</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>지역</th><th>총사업체수</th><th>영업중</th><th>폐업</th><th>폐업률</th>
                        <th>개인사업체</th><th>회사법인</th><th>총종사자수</th><th>평균종사자</th><th>인당매출(백만)</th>
                    </tr>
                </thead>
                <tbody>{table_rows}</tbody>
            </table>
        </div>
    </div>

    <script>
        function toggleSidoSelect() {{
            const viewType = document.querySelector('input[name="view_type"]:checked').value;
            document.getElementById('sido-select-group').style.display = viewType === '시도별' ? 'block' : 'none';
        }}

        // 산업별 파이차트
        Plotly.newPlot('chart-industry-pie', [{{
            labels: {df_industry['산업'].head(10).tolist()},
            values: {df_industry['사업체수'].head(10).tolist()},
            type: 'pie', hole: 0.4, textinfo: 'percent', textposition: 'outside',
            marker: {{ colors: ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e', '#e67e22', '#16a085', '#8e44ad'] }}
        }}], {{ margin: {{ t: 30, b: 30, l: 30, r: 30 }}, showlegend: true, legend: {{ orientation: 'h', y: -0.2 }}, height: 400 }}, {{responsive: true}});

        // 조직형태별 파이차트
        Plotly.newPlot('chart-org-pie', [{{
            labels: {df_org['조직형태'].tolist()},
            values: {df_org['사업체수'].tolist()},
            type: 'pie', hole: 0.4, textinfo: 'percent+label', textposition: 'outside',
            marker: {{ colors: ['#27ae60', '#3498db', '#9b59b6', '#e67e22', '#e74c3c'] }}
        }}], {{ margin: {{ t: 30, b: 30, l: 30, r: 30 }}, showlegend: false, height: 400 }}, {{responsive: true}});

        // 산업별 막대차트
        Plotly.newPlot('chart-industry-bar', [{{
            x: {df_industry['산업'].head(15).tolist()},
            y: {df_industry['사업체수'].head(15).tolist()},
            type: 'bar',
            marker: {{ color: {df_industry['사업체수'].head(15).tolist()}, colorscale: 'Blues' }},
            text: {[f"{x:,}" for x in df_industry['사업체수'].head(15).tolist()]},
            textposition: 'outside'
        }}], {{ xaxis: {{ tickangle: -45 }}, yaxis: {{ title: '사업체수' }}, margin: {{ t: 30, b: 120, l: 80, r: 30 }}, height: 450 }}, {{responsive: true}});

        // 영업상태 추이
        Plotly.newPlot('chart-status-trend', [
            {{ x: {df_status_ts['분기'].tolist()}, y: {df_status_ts['영업중'].tolist()}, type: 'scatter', mode: 'lines+markers', name: '영업중', line: {{ color: '#27ae60', width: 2 }}, yaxis: 'y1' }},
            {{ x: {df_status_ts['분기'].tolist()}, y: {df_status_ts['폐업'].tolist()}, type: 'scatter', mode: 'lines+markers', name: '폐업', line: {{ color: '#e74c3c', width: 2 }}, yaxis: 'y1' }},
            {{ x: {df_status_ts['분기'].tolist()}, y: {df_status_ts['폐업률'].tolist()}, type: 'scatter', mode: 'lines+markers', name: '폐업률(%)', line: {{ color: '#f39c12', width: 3, dash: 'dash' }}, yaxis: 'y2' }}
        ], {{ xaxis: {{ tickangle: -45 }}, yaxis: {{ title: '사업체수', side: 'left' }}, yaxis2: {{ title: '폐업률(%)', overlaying: 'y', side: 'right' }}, legend: {{ orientation: 'h', y: 1.1 }}, margin: {{ t: 50, b: 80, l: 80, r: 80 }}, height: 400 }}, {{responsive: true}});

        // 인구 대비 산업별 밀도 히트맵
        Plotly.newPlot('chart-pop-industry', [{{
            z: [
                {df_pop_ind['제조업_밀도'].head(10).tolist()},
                {df_pop_ind['도매및소매업_밀도'].head(10).tolist()},
                {df_pop_ind['숙박및음식점업_밀도'].head(10).tolist()},
                {df_pop_ind['건설업_밀도'].head(10).tolist()},
                {df_pop_ind['부동산업_밀도'].head(10).tolist()},
                {df_pop_ind['보건사회복지_밀도'].head(10).tolist()}
            ],
            x: {df_pop_ind['시도명'].head(10).tolist()},
            y: ['제조업', '도매및소매업', '숙박및음식점업', '건설업', '부동산업', '보건사회복지'],
            type: 'heatmap', colorscale: 'YlOrRd', showscale: true, colorbar: {{ title: '밀도' }}
        }}], {{ xaxis: {{ tickangle: -45 }}, margin: {{ t: 30, b: 100, l: 120, r: 50 }}, height: 350 }}, {{responsive: true}});
    </script>
</body>
</html>
"""
    return html


def handle_ppt_save(form_data):
    """
    PPT 저장 요청 처리

    Args:
        form_data: Flask request.form

    Returns:
        Flask Response: PPT 파일 다운로드 또는 오류 메시지
    """
    logger.info("=== PPT 저장 요청 시작 (대시보드4) ===")

    if not PPT_AVAILABLE:
        logger.warning("PPT 사용 불가 - python-pptx 설치 필요")
        return Response(
            "<script>alert('PPT 저장 기능을 사용하려면 python-pptx를 설치하세요. (pip install python-pptx)'); history.back();</script>",
            mimetype='text/html'
        )

    try:
        # 폼 데이터에서 파라미터 추출
        selected_year = form_data.get('year')
        selected_quarter = form_data.get('quarter')
        view_type = form_data.get('view_type', '시도별')
        selected_sido = form_data.get('sido', '경상북도')

        # 데이터 조회
        df_industry = get_industry_data(selected_year, selected_quarter, view_type, selected_sido)
        df_org = get_org_type_data(selected_year, selected_quarter, view_type, selected_sido)
        df_status = get_status_data(selected_year, selected_quarter, view_type, selected_sido)
        df_detail = get_regional_detail_data(selected_year, selected_quarter, view_type, selected_sido)

        # 레이블 생성
        latest_quarter_label = f"{selected_year}년 {selected_quarter}분기"
        if view_type == '전체':
            region_label = "전국"
        elif view_type == '권역별':
            region_label = "권역별"
        elif view_type == '시도별':
            region_label = selected_sido
        else:
            region_label = "전국"

        # 지표 계산
        active_count = int(df_status['영업중'].iloc[0]) if df_status['영업중'].iloc[0] else 0
        closed_count = int(df_status['폐업'].iloc[0]) if df_status['폐업'].iloc[0] else 0
        total_count = active_count + closed_count
        closure_rate = round(closed_count / total_count * 100, 2) if total_count > 0 else 0

        # PPT 파일 생성
        logger.info("PPT 보고서 생성 시작...")
        output_path = generate_ppt_report(
            selected_year, selected_quarter, view_type, selected_sido,
            latest_quarter_label, region_label,
            df_industry, df_org, df_status, df_detail,
            active_count, closed_count, closure_rate
        )
        logger.info(f"PPT 파일 생성 완료: {output_path}")

        # 파일 존재 확인
        if not os.path.exists(output_path):
            logger.error(f"PPT 파일이 생성되지 않음: {output_path}")
            return Response(
                "<script>alert('PPT 파일 생성 실패'); history.back();</script>",
                mimetype='text/html'
            )

        # 파일명 생성 (선택 조건 포함)
        if view_type == '시도별':
            view_label = f"{selected_sido}_시군구별"
        elif view_type == '전체':
            view_label = "전국_시도별"
        else:
            view_label = view_type

        filename = f"상세분석_{selected_year}년{selected_quarter}분기_{view_label}.pptx"
        logger.info(f"파일 다운로드 시작: {filename}")

        # 파일 읽기 및 응답 생성 (한글 파일명 인코딩 처리)
        with open(output_path, 'rb') as f:
            file_data = f.read()

        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        encoded_filename = quote(filename)
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
        response.headers['Content-Length'] = len(file_data)

        return response

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"PPT 저장 오류: {str(e)}")
        logger.error(f"상세 오류:\n{error_trace}")
        return Response(
            f"<script>alert('PPT 저장 중 오류 발생: {str(e)}'); history.back();</script>",
            mimetype='text/html'
        )


def generate_ppt_report(selected_year, selected_quarter, view_type, selected_sido,
                        latest_quarter_label, region_label,
                        df_industry, df_org, df_status, df_detail,
                        active_count, closed_count, closure_rate):
    """
    PPT 보고서 생성

    Args:
        selected_year, selected_quarter: 기준 년/분기
        view_type, selected_sido: 지역 필터
        latest_quarter_label, region_label: 표시 레이블
        df_industry, df_org, df_status, df_detail: 데이터프레임
        active_count, closed_count, closure_rate: 영업상태 지표

    Returns:
        str: 생성된 PPT 파일 경로
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import koreanize_matplotlib

    temp_dir = tempfile.mkdtemp()
    chart_paths = {}

    # 1. 산업별 분포 차트
    n_industries = len(df_industry)
    fig_height = max(6, n_industries * 0.4)
    fig, ax = plt.subplots(figsize=(10, fig_height))

    blue_gradient = ['#1243A6', '#1D64F2', '#4A90E2', '#7EB6FF', '#B8D4FF']
    gray_color = '#C0C0C0'
    colors = [blue_gradient[i] if i < 5 else gray_color for i in range(n_industries)]

    y_pos = range(n_industries)
    ax.barh(y_pos, df_industry['사업체수'], color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df_industry['산업명'])
    ax.set_xlabel('사업체수 (개)')
    ax.set_title(f'{region_label} 산업별 분포')
    ax.invert_yaxis()
    for i, v in enumerate(df_industry['사업체수']):
        ax.text(v + v*0.01, i, f'{int(v):,}', va='center', fontsize=8)
    plt.tight_layout()
    chart_path1 = os.path.join(temp_dir, "chart_industry.png")
    plt.savefig(chart_path1, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['산업별 분포'] = chart_path1

    # 2. 영업상태 파이 차트
    fig, ax = plt.subplots(figsize=(8, 6))
    labels = ['영업중', '폐업']
    sizes = [active_count, closed_count]
    colors_status = ['#27AE60', '#E74C3C']
    explode = (0.05, 0)
    ax.pie(sizes, explode=explode, labels=labels, colors=colors_status,
           autopct='%1.1f%%', startangle=90, shadow=True)
    ax.set_title(f'{region_label} 영업상태 분포')
    plt.tight_layout()
    chart_path2 = os.path.join(temp_dir, "chart_status.png")
    plt.savefig(chart_path2, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['영업상태 분포'] = chart_path2

    # 3. 조직형태별 분포 차트
    fig, ax = plt.subplots(figsize=(8, 6))
    colors_org = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe']
    ax.pie(df_org['사업체수'], labels=df_org['조직형태'], autopct='%1.1f%%',
           colors=colors_org[:len(df_org)], startangle=90)
    ax.set_title(f'{region_label} 조직형태별 분포')
    plt.tight_layout()
    chart_path3 = os.path.join(temp_dir, "chart_org.png")
    plt.savefig(chart_path3, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['조직형태별 분포'] = chart_path3

    # 주요 지표
    metrics = [
        {'label': '영업중 사업체', 'value': f'{active_count:,}', 'unit': '개'},
        {'label': '폐업 사업체', 'value': f'{closed_count:,}', 'unit': '개'},
        {'label': '폐업률', 'value': f'{closure_rate:.1f}', 'unit': '%'},
    ]

    # PPT 생성
    output_path = create_dashboard_ppt(
        title="기업체 상세 분석 보고서",
        subtitle=f"{latest_quarter_label} | {region_label}",
        metrics=metrics,
        df_aggregated=df_detail.rename(columns={'지역명': '지역명', '총사업체수': '총사업체수'}),
        df_pop_biz=None,
        insights=[],
        chart_paths=chart_paths,
        output_path=os.path.join(temp_dir, "report.pptx")
    )

    return output_path
