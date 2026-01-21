# -*- coding: utf-8 -*-
"""
기업통계등록부(SBR) 대시보드 3 - 지역 분석
==========================================

주요 기능:
1. 지역별 성장률 분석 (QoQ)
2. 상위/하위 지역 순위
3. 폐업률 분석
4. 인구 밀도 대비 사업체 현황
5. HHI 및 1인당 매출액 분석

필터: 라디오버튼(전체/권역별/시도별) + 시도 선택
초기값: 시도별 + 경상북도
"""

import sys
import os
import tempfile
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from loguru import logger

# 상위 디렉토리 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_connection
from module.region_config import get_region_sido_mapping

# PPT 관련 임포트
try:
    from module.ppt_utils import create_dashboard_ppt, PPT_AVAILABLE
except ImportError:
    PPT_AVAILABLE = False

# Flask 관련 임포트 (POST 처리용)
try:
    from flask import request, Response, send_file, make_response
except ImportError:
    pass

from urllib.parse import quote


def get_filter_options():
    """
    필터 옵션 조회

    Returns:
        dict: {
            'quarters': 분기 목록,
            'sido_list': 시도 목록
        }
    """
    conn = get_db_connection()

    # 분기 목록 조회 (최신 순)
    query_quarters = """
        SELECT DISTINCT "CRTR_YR", "QU_SE_CD",
               "CRTR_YR" || 'Q' || "QU_SE_CD" as quarter_label
        FROM sbr_quarter_summary
        ORDER BY "CRTR_YR" DESC, "QU_SE_CD" DESC
    """
    df_quarters = pd.read_sql(query_quarters, conn)

    # 시도 목록 조회 (가나다순)
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


def calculate_hhi(industry_columns_dict):
    """
    허핀달-허쉬만 지수(HHI) 계산

    Args:
        industry_columns_dict (dict): {산업명: 사업체수}

    Returns:
        float: HHI 값 (0~10000, 낮을수록 다양)
    """
    total = sum(industry_columns_dict.values())
    if total == 0:
        return 0
    hhi = sum(((count / total) * 100) ** 2 for count in industry_columns_dict.values())
    return round(hhi, 2)


def get_aggregated_data(year, quarter, view_type, sido=None):
    """
    집계 데이터 조회 (HHI, 1인당 매출액 포함)

    Args:
        year: 조회 연도
        quarter: 조회 분기
        view_type: 조회 유형 ('전체', '권역별', '시도별')
        sido: 시도명 (view_type='시도별'일 때)

    Returns:
        pandas.DataFrame: 지역별 집계 데이터
    """
    conn = get_db_connection()

    # 산업별 컬럼 목록
    industry_columns = [
        'IND_농업,임업,어업', 'IND_광업', 'IND_제조업', 'IND_전기가스공급업',
        'IND_수도하수폐기물', 'IND_건설업', 'IND_도매및소매업', 'IND_운수및창고업',
        'IND_숙박및음식점업', 'IND_정보통신업', 'IND_금융및보험업', 'IND_부동산업',
        'IND_전문과학기술서비스', 'IND_사업시설관리', 'IND_공공행정', 'IND_교육서비스업',
        'IND_보건사회복지', 'IND_예술스포츠여가', 'IND_협회및개인서비스',
        'IND_가구내고용활동', 'IND_국제외국기관'
    ]

    industry_cols_sql = ', '.join([f'"{col}"' for col in industry_columns])

    # NULL 값 처리: 개인정보 보호로 3개 미만은 1로 표시
    # COALESCE를 사용하여 NULL을 1로 변환
    def wrap_coalesce(col):
        return f'COALESCE({col}, 1)'

    # 산업별 컬럼 SUM SQL 문자열 미리 생성 (f-string 중첩 방지)
    industry_sum_cols = ', '.join([f'SUM(COALESCE("{col}", 1)) as "{col}"' for col in industry_columns])

    if view_type == '전체':
        # 전체: 시도별 집계
        query = f"""
            SELECT
                "CTPV_NM" as 지역명,
                SUM({wrap_coalesce('"ORG_합계"')}) as 총사업체수,
                SUM({wrap_coalesce('"STATUS_영업중"')}) as 영업중,
                SUM({wrap_coalesce('"STATUS_폐업"')}) as 폐업,
                ROUND(SUM({wrap_coalesce('"STATUS_폐업"')})::numeric /
                      NULLIF(SUM({wrap_coalesce('"ORG_합계"')}), 0) * 100, 2) as 폐업률,
                SUM({wrap_coalesce('"STATS_기업매출금액_합계"')}) as 총매출액,
                SUM({wrap_coalesce('"STATS_기업종사자수_합계"')}) as 총종사자수,
                {industry_sum_cols}
            FROM sbr_quarter_summary
            WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
                AND "CTPV_NM" IS NOT NULL
            GROUP BY "CTPV_NM"
            ORDER BY 총사업체수 DESC
        """
    elif view_type == '권역별':
        # 권역별 집계
        region_mapping = get_region_sido_mapping()
        cases = []
        for region, sidos in region_mapping.items():
            sido_list = "','".join(sidos)
            cases.append(f"WHEN \"CTPV_NM\" IN ('{sido_list}') THEN '{region}'")
        case_sql = " ".join(cases)

        query = f"""
            SELECT
                CASE {case_sql} ELSE '기타' END as 지역명,
                SUM({wrap_coalesce('"ORG_합계"')}) as 총사업체수,
                SUM({wrap_coalesce('"STATUS_영업중"')}) as 영업중,
                SUM({wrap_coalesce('"STATUS_폐업"')}) as 폐업,
                ROUND(SUM({wrap_coalesce('"STATUS_폐업"')})::numeric /
                      NULLIF(SUM({wrap_coalesce('"ORG_합계"')}), 0) * 100, 2) as 폐업률,
                SUM({wrap_coalesce('"STATS_기업매출금액_합계"')}) as 총매출액,
                SUM({wrap_coalesce('"STATS_기업종사자수_합계"')}) as 총종사자수,
                {industry_sum_cols}
            FROM sbr_quarter_summary
            WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
                AND "CTPV_NM" IS NOT NULL
            GROUP BY CASE {case_sql} ELSE '기타' END
            ORDER BY 총사업체수 DESC
        """
    elif view_type == '시도별' and sido:
        # 시도별: 시군구별 집계
        query = f"""
            WITH sigungu_summary AS (
                SELECT
                    LEFT("ADCLSF_SGG_CD", 4) as sigungu_code_4,
                    "SGG_NM",
                    SUM({wrap_coalesce('"ORG_합계"')}) as 총사업체수,
                    SUM({wrap_coalesce('"STATUS_영업중"')}) as 영업중,
                    SUM({wrap_coalesce('"STATUS_폐업"')}) as 폐업,
                    SUM({wrap_coalesce('"STATS_기업매출금액_합계"')}) as 총매출액,
                    SUM({wrap_coalesce('"STATS_기업종사자수_합계"')}) as 총종사자수,
                    {industry_sum_cols}
                FROM sbr_quarter_summary
                WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
                    AND "CTPV_NM" = '{sido}'
                    AND "SGG_NM" IS NOT NULL
                GROUP BY LEFT("ADCLSF_SGG_CD", 4), "SGG_NM"
            )
            SELECT
                "SGG_NM" as 지역명,
                sigungu_code_4 as 시군구코드,
                총사업체수,
                영업중,
                폐업,
                ROUND(폐업::numeric / NULLIF(총사업체수, 0) * 100, 2) as 폐업률,
                총매출액,
                총종사자수,
                {industry_cols_sql}
            FROM sigungu_summary
            ORDER BY sigungu_code_4
        """
    else:
        # 기본값: 전국 합계
        query = f"""
            SELECT
                '전국' as 지역명,
                SUM({wrap_coalesce('"ORG_합계"')}) as 총사업체수,
                SUM({wrap_coalesce('"STATUS_영업중"')}) as 영업중,
                SUM({wrap_coalesce('"STATUS_폐업"')}) as 폐업,
                ROUND(SUM({wrap_coalesce('"STATUS_폐업"')})::numeric /
                      NULLIF(SUM({wrap_coalesce('"ORG_합계"')}), 0) * 100, 2) as 폐업률,
                SUM({wrap_coalesce('"STATS_기업매출금액_합계"')}) as 총매출액,
                SUM({wrap_coalesce('"STATS_기업종사자수_합계"')}) as 총종사자수,
                {industry_sum_cols}
            FROM sbr_quarter_summary
            WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
        """

    df = pd.read_sql(query, conn)
    conn.close()

    # HHI 계산
    hhi_values = []
    for idx, row in df.iterrows():
        industry_dict = {}
        for col in industry_columns:
            if col in df.columns:
                val = row[col]
                if pd.notna(val) and val > 0:
                    industry_dict[col] = val
        hhi = calculate_hhi(industry_dict)
        hhi_values.append(hhi)

    df['HHI'] = hhi_values

    # 1인당 매출액 계산
    df['1인당매출액'] = df.apply(
        lambda row: round(row['총매출액'] / row['총종사자수'], 2)
        if row['총종사자수'] > 0 else None,
        axis=1
    )

    # 산업별 컬럼 제거
    df = df.drop(columns=industry_columns, errors='ignore')

    return df


def generate_insights(df, view_type, sido):
    """
    인사이트 생성

    Args:
        df: 집계 데이터
        view_type: 조회 유형
        sido: 선택된 시도

    Returns:
        list: 인사이트 딕셔너리 리스트
    """
    insights = []

    if len(df) == 0:
        return insights

    # 인사이트 1: 최고 폐업률 지역
    if '폐업률' in df.columns:
        top_closure = df.nlargest(1, '폐업률').iloc[0]
        insights.append({
            'icon': '⚠️',
            'title': '최고 폐업률 지역',
            'content': f"{top_closure['지역명']}이 {top_closure['폐업률']:.2f}%로 가장 높은 폐업률을 보이고 있습니다."
        })

    # 인사이트 2: HHI 기반 산업 다양성
    if 'HHI' in df.columns:
        avg_hhi = df['HHI'].mean()
        if avg_hhi < 1500:
            diversity_level = "매우 다양한 산업 구조"
        elif avg_hhi < 2500:
            diversity_level = "중간 수준의 산업 다양성"
        else:
            diversity_level = "특정 산업에 집중된 구조"

        insights.append({
            'icon': '📊',
            'title': '산업 다양성 (HHI)',
            'content': f"평균 HHI는 {avg_hhi:.2f}로, {diversity_level}를 보입니다."
        })

    # 인사이트 3: 1인당 매출액
    if '1인당매출액' in df.columns:
        avg_sales = df['1인당매출액'].mean()
        top_sales = df.nlargest(1, '1인당매출액').iloc[0]
        insights.append({
            'icon': '💰',
            'title': '최고 생산성 지역',
            'content': f"{top_sales['지역명']}이 1인당 매출액 {top_sales['1인당매출액']:.2f}백만원으로 가장 높은 생산성을 보입니다. (평균: {avg_sales:.2f}백만원)"
        })

    return insights


def render(request_args=None, request_form=None, method='GET'):
    """
    Flask에서 호출되는 렌더링 함수

    Args:
        request_args: Flask request.args
        request_form: Flask request.form (POST 요청 시)
        method: HTTP 메서드 ('GET' 또는 'POST')

    Returns:
        str: 렌더링된 HTML 또는 Response 객체
    """
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

    # 필터 옵션
    filter_opts = get_filter_options()

    # 파라미터 파싱 (초기값: 시도별 + 경상북도)
    request_args = request_args or {}
    selected_year = request_args.get('year', filter_opts['quarters'][0]['CRTR_YR'])
    selected_quarter = request_args.get('quarter', filter_opts['quarters'][0]['QU_SE_CD'])
    view_type = request_args.get('view_type', '시도별')
    selected_sido = request_args.get('sido', '경상북도')

    # 데이터 조회
    df = get_aggregated_data(selected_year, selected_quarter, view_type, selected_sido)

    # 인사이트 생성
    insights = generate_insights(df, view_type, selected_sido)

    # 레이블 생성
    latest_quarter_label = f"{selected_year}년 {selected_quarter}분기"
    if view_type == '전체':
        region_label = "전국 (시도별)"
    elif view_type == '권역별':
        region_label = "권역별"
    elif view_type == '시도별':
        region_label = f"{selected_sido} (시군구별)"
    else:
        region_label = "전국"

    # 전년도 계산 (매출금액 주석용)
    prev_year = int(selected_year) - 1

    # HTML 생성
    html = generate_html(
        filter_opts, selected_year, selected_quarter, view_type, selected_sido,
        latest_quarter_label, region_label, prev_year, df, insights,
        PPT_AVAILABLE
    )

    return html


def generate_html(filter_opts, selected_year, selected_quarter, view_type, selected_sido,
                  latest_quarter_label, region_label, prev_year, df, insights,
                  ppt_available=False):
    """
    HTML 생성

    Args:
        filter_opts: 필터 옵션
        selected_year: 선택된 연도
        selected_quarter: 선택된 분기
        view_type: 조회 유형
        selected_sido: 선택된 시도
        latest_quarter_label: 표시용 분기 레이블
        region_label: 표시용 지역 레이블
        prev_year: 전년도 (매출금액 기준)
        df: 집계 데이터
        insights: 인사이트 리스트

    Returns:
        str: HTML 문서
    """
    # 필터 옵션 HTML
    year_options = ''.join([f'<option value="{q["CRTR_YR"]}" {"selected" if str(q["CRTR_YR"]) == str(selected_year) else ""}>{q["CRTR_YR"]}년</option>'
                           for q in filter_opts['quarters']])

    quarter_options = ''.join([f'<option value="{i}" {"selected" if str(i) == str(selected_quarter) else ""}>{i}분기</option>'
                              for i in range(1, 5)])

    sido_options = ''.join([f'<option value="{sido}" {"selected" if sido == selected_sido else ""}>{sido}</option>'
                           for sido in filter_opts['sido_list']])

    # 인사이트 HTML
    insights_html = ''.join([f'''
        <div class="insight-card">
            <div class="insight-icon">{insight['icon']}</div>
            <div class="insight-content">
                <div class="insight-title">{insight['title']}</div>
                <div class="insight-text">{insight['content']}</div>
            </div>
        </div>
    ''' for insight in insights])

    # 테이블 HTML
    if len(df) > 0:
        table_headers = ''.join([f'<th>{col}</th>' for col in df.columns])
        table_rows = []
        for _, row in df.iterrows():
            cells = []
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    formatted_val = '-'
                elif col in ['총사업체수', '영업중', '폐업', '총종사자수']:
                    formatted_val = f"{int(val):,}"
                elif col in ['총매출액']:
                    formatted_val = f"{int(val):,}"
                elif col in ['폐업률', 'HHI', '1인당매출액']:
                    formatted_val = f"{val:.2f}"
                else:
                    formatted_val = str(val)
                cells.append(f'<td>{formatted_val}</td>')
            table_rows.append(f'<tr>{"".join(cells)}</tr>')

        table_body = ''.join(table_rows)
        table_html = f'''
            <table class="data-table">
                <thead><tr>{table_headers}</tr></thead>
                <tbody>{table_body}</tbody>
            </table>
            <div class="table-notes">
                <p>※ 매출금액은 전년도({prev_year}년) 재무제표 기준입니다.</p>
                <p>※ 개인정보 보호를 위해 3개 미만 값은 비식별화(최소값 1로 표시)되었습니다.</p>
            </div>
        '''
    else:
        table_html = '<p class="no-data">조회된 데이터가 없습니다.</p>'

    html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>기업통계등록부 대시보드 - 지역 분석</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2rem;
        }}
        .subtitle {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 20px;
            font-size: 1rem;
        }}
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
            cursor: pointer;
        }}
        .radio-group {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 15px;
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
            cursor: pointer;
            width: 18px;
            height: 18px;
        }}
        .sido-select {{
            margin-bottom: 15px;
        }}
        .filter-btn {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s;
            width: 100%;
            max-width: 200px;
        }}
        .filter-btn:hover {{
            transform: translateY(-2px);
        }}
        .table-container {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 30px;
            overflow-x: auto;
        }}
        .table-title {{
            font-size: 1.3rem;
            color: #2c3e50;
            margin-bottom: 15px;
            font-weight: 600;
            text-align: center;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            font-size: 0.85rem;
        }}
        .data-table thead {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }}
        .data-table th {{
            padding: 12px 8px;
            text-align: center;
            font-weight: 600;
            font-size: 0.9rem;
            border: 1px solid #ddd;
            white-space: nowrap;
        }}
        .data-table td {{
            padding: 10px 8px;
            text-align: right;
            border: 1px solid #e0e0e0;
        }}
        .data-table td:first-child {{
            text-align: left;
            font-weight: 500;
            color: #2c3e50;
        }}
        .data-table tbody tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        .data-table tbody tr:hover {{
            background: #e3f2fd;
        }}
        .table-notes {{
            margin-top: 15px;
            padding: 10px;
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            border-radius: 4px;
        }}
        .table-notes p {{
            font-size: 0.85rem;
            color: #856404;
            margin: 5px 0;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
            font-size: 1.1rem;
        }}
        .insights-container {{
            margin-top: 40px;
            padding: 30px;
            background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
            border-radius: 12px;
        }}
        .insights-title {{
            font-size: 1.5rem;
            color: #2c3e50;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 700;
        }}
        .insights-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        .insight-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            display: flex;
            align-items: start;
            gap: 15px;
            transition: transform 0.3s;
        }}
        .insight-card:hover {{
            transform: translateY(-3px);
        }}
        .insight-icon {{
            font-size: 2.5rem;
            flex-shrink: 0;
        }}
        .insight-content {{
            flex: 1;
        }}
        .insight-title {{
            font-size: 1.1rem;
            color: #2c3e50;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .insight-text {{
            font-size: 0.95rem;
            color: #555;
            line-height: 1.5;
        }}
        @media (max-width: 768px) {{
            .container {{
                padding: 15px;
            }}
            h1 {{
                font-size: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 기업통계등록부 지역 분석</h1>
        <p class="subtitle">기준: {latest_quarter_label} | 지역: {region_label}</p>

        <!-- 필터 영역 -->
        <form method="get" class="filter-container">
            <div class="filter-row">
                <div class="filter-group">
                    <label for="year">📅 연도</label>
                    <select name="year" id="year">
                        {year_options}
                    </select>
                </div>
                <div class="filter-group">
                    <label for="quarter">📅 분기</label>
                    <select name="quarter" id="quarter">
                        {quarter_options}
                    </select>
                </div>
            </div>

            <!-- 라디오버튼 -->
            <div class="filter-group">
                <label>🗺️ 조회 구분</label>
                <div class="radio-group">
                    <label class="radio-label">
                        <input type="radio" name="view_type" value="전체" {"checked" if view_type == "전체" else ""} onchange="toggleSidoSelect()"> 전체 (시도별)
                    </label>
                    <label class="radio-label">
                        <input type="radio" name="view_type" value="권역별" {"checked" if view_type == "권역별" else ""} onchange="toggleSidoSelect()"> 권역별
                    </label>
                    <label class="radio-label">
                        <input type="radio" name="view_type" value="시도별" {"checked" if view_type == "시도별" else ""} onchange="toggleSidoSelect()"> 시도별
                    </label>
                </div>
            </div>

            <!-- 시도 선택 -->
            <div class="sido-select" id="sido-select-group" style="display: {'block' if view_type == '시도별' else 'none'};">
                <div class="filter-group">
                    <label for="sido">📍 시도 선택</label>
                    <select name="sido" id="sido">
                        {sido_options}
                    </select>
                </div>
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

        <!-- 테이블 영역 -->
        <div class="table-container">
            <h2 class="table-title">📋 {region_label} 상세 현황</h2>
            {table_html}
        </div>

        <!-- 인사이트 섹션 -->
        <div class="insights-container">
            <h2 class="insights-title">💡 주요 인사이트</h2>
            <div class="insights-grid">
                {insights_html}
            </div>
        </div>
    </div>

    <script>
        /**
         * 시도 선택 영역 토글
         */
        function toggleSidoSelect() {{
            const viewType = document.querySelector('input[name="view_type"]:checked').value;
            const sidoGroup = document.getElementById('sido-select-group');

            if (viewType === '시도별') {{
                sidoGroup.style.display = 'block';
            }} else {{
                sidoGroup.style.display = 'none';
            }}
        }}

        // 페이지 로드 시 초기화
        window.addEventListener('DOMContentLoaded', function() {{
            toggleSidoSelect();
        }});
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
    logger.info("=== PPT 저장 요청 시작 (대시보드3) ===")

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
        df = get_aggregated_data(selected_year, selected_quarter, view_type, selected_sido)

        # 인사이트 생성
        insights = generate_insights(df, view_type, selected_sido)

        # 레이블 생성
        latest_quarter_label = f"{selected_year}년 {selected_quarter}분기"
        if view_type == '전체':
            region_label = "전국 (시도별)"
        elif view_type == '권역별':
            region_label = "권역별"
        elif view_type == '시도별':
            region_label = f"{selected_sido} (시군구별)"
        else:
            region_label = "전국"

        # PPT 파일 생성
        logger.info("PPT 보고서 생성 시작...")
        output_path = generate_ppt_report(
            selected_year, selected_quarter, view_type, selected_sido,
            latest_quarter_label, region_label, df, insights
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

        filename = f"지역분석_{selected_year}년{selected_quarter}분기_{view_label}.pptx"
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
                        latest_quarter_label, region_label, df, insights):
    """
    PPT 보고서 생성

    Args:
        selected_year, selected_quarter: 기준 년/분기
        view_type, selected_sido: 지역 필터
        latest_quarter_label, region_label: 표시 레이블
        df: 지역별 데이터프레임
        insights: 인사이트 목록

    Returns:
        str: 생성된 PPT 파일 경로
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import koreanize_matplotlib

    temp_dir = tempfile.mkdtemp()
    chart_paths = {}

    # 1. 지역별 사업체 현황 차트
    n_regions = len(df)
    fig_height = max(6, n_regions * 0.4)
    fig, ax = plt.subplots(figsize=(10, fig_height))

    blue_gradient = ['#1243A6', '#1D64F2', '#4A90E2', '#7EB6FF', '#B8D4FF']
    gray_color = '#C0C0C0'
    colors = [blue_gradient[i] if i < 5 else gray_color for i in range(n_regions)]

    y_pos = range(n_regions)
    ax.barh(y_pos, df['총사업체수'], color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df['지역명'])
    ax.set_xlabel('사업체수 (개)')
    ax.set_title(f'{region_label} 사업체 현황')
    ax.invert_yaxis()
    for i, v in enumerate(df['총사업체수']):
        ax.text(v + v*0.01, i, f'{int(v):,}', va='center', fontsize=8)
    plt.tight_layout()
    chart_path1 = os.path.join(temp_dir, "chart_region.png")
    plt.savefig(chart_path1, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['지역별 사업체 현황'] = chart_path1

    # 2. 성장률 비교 차트 (성장률 컬럼이 있는 경우)
    if 'QoQ증감률' in df.columns:
        fig, ax = plt.subplots(figsize=(10, 6))
        colors_growth = ['#27AE60' if v >= 0 else '#E74C3C' for v in df['QoQ증감률']]
        ax.barh(range(len(df)), df['QoQ증감률'], color=colors_growth)
        ax.set_yticks(range(len(df)))
        ax.set_yticklabels(df['지역명'])
        ax.set_xlabel('전분기 대비 증감률 (%)')
        ax.set_title(f'{region_label} 성장률 현황')
        ax.axvline(x=0, color='black', linewidth=0.5)
        ax.invert_yaxis()
        plt.tight_layout()
        chart_path2 = os.path.join(temp_dir, "chart_growth.png")
        plt.savefig(chart_path2, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths['성장률 현황'] = chart_path2

    # 3. HHI 분포 차트 (HHI 컬럼이 있는 경우)
    if 'HHI' in df.columns:
        fig, ax = plt.subplots(figsize=(10, 6))
        colors_hhi = ['#667eea' for _ in range(len(df))]
        ax.barh(range(len(df)), df['HHI'], color=colors_hhi)
        ax.set_yticks(range(len(df)))
        ax.set_yticklabels(df['지역명'])
        ax.set_xlabel('HHI (낮을수록 산업 다양)')
        ax.set_title(f'{region_label} HHI 분포')
        ax.invert_yaxis()
        plt.tight_layout()
        chart_path3 = os.path.join(temp_dir, "chart_hhi.png")
        plt.savefig(chart_path3, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths['HHI 분포'] = chart_path3

    # 주요 지표
    total_biz = df['총사업체수'].sum() if not df.empty else 0
    total_emp = df['총종사자수'].sum() if '총종사자수' in df.columns and not df.empty else 0
    top_region = df.iloc[0]['지역명'] if not df.empty else '-'

    metrics = [
        {'label': '총 사업체수', 'value': f'{total_biz:,.0f}', 'unit': '개'},
        {'label': '총 종사자수', 'value': f'{total_emp:,.0f}', 'unit': '명'},
        {'label': '1위 지역', 'value': top_region, 'unit': ''},
    ]

    # PPT 생성
    output_path = create_dashboard_ppt(
        title="기업체 지역 분석 보고서",
        subtitle=f"{latest_quarter_label} | {region_label}",
        metrics=metrics,
        df_aggregated=df,
        df_pop_biz=None,
        insights=insights,
        chart_paths=chart_paths,
        output_path=os.path.join(temp_dir, "report.pptx")
    )

    return output_path
