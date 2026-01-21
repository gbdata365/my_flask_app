# -*- coding: utf-8 -*-
"""
기업통계등록부(SBR) 대시보드 2 - 산업 분석
==========================================

주요 기능:
1. 산업별 사업체 분포: 상위 15개 산업의 사업체수를 가로 막대 차트로 표시
2. 조직형태별 분포: 개인사업체, 회사법인 등 조직형태별 비중을 파이 차트로 표시
3. 대표자 성별 분포: 남성/여성/미상 대표자 비율을 도넛 차트로 시각화
4. 영업상태별 분포: 영업중/폐업 사업체수 비교

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


def get_industry_data(year, quarter, view_type, sido=None):
    """
    산업별 사업체 분포 데이터 조회

    Args:
        year: 조회 연도
        quarter: 조회 분기
        view_type: 조회 유형 ('전체', '권역별', '시도별')
        sido: 시도명 (view_type='시도별'일 때)

    Returns:
        pandas.DataFrame: 산업별 사업체수 데이터
    """
    conn = get_db_connection()

    industry_columns = [
        'IND_농업,임업,어업', 'IND_광업', 'IND_제조업', 'IND_전기가스공급업',
        'IND_수도하수폐기물', 'IND_건설업', 'IND_도매및소매업', 'IND_운수및창고업',
        'IND_숙박및음식점업', 'IND_정보통신업', 'IND_금융및보험업', 'IND_부동산업',
        'IND_전문과학기술서비스', 'IND_사업시설관리', 'IND_공공행정', 'IND_교육서비스업',
        'IND_보건사회복지', 'IND_예술스포츠여가', 'IND_협회및개인서비스',
        'IND_가구내고용활동', 'IND_국제외국기관'
    ]

    industry_cols_sum = ', '.join([f'SUM(COALESCE("{col}", 0)) as "{col}"' for col in industry_columns])

    if view_type == '시도별' and sido:
        region_filter = f"AND \"CTPV_NM\" = '{sido}'"
    elif view_type == '권역별':
        region_filter = ""  # 권역별은 전체를 가져와서 Python에서 처리
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
    if len(df_result) > 0:
        df_result = df_result.sort_values('사업체수', ascending=False)
        df_result['비율'] = (df_result['사업체수'] / df_result['사업체수'].sum() * 100).round(2)

    return df_result


def get_organization_data(year, quarter, view_type, sido=None):
    """
    조직형태별 분포 데이터 조회

    Args:
        year: 조회 연도
        quarter: 조회 분기
        view_type: 조회 유형
        sido: 시도명

    Returns:
        pandas.DataFrame: 조직형태별 사업체수 데이터
    """
    conn = get_db_connection()

    org_columns = {
        'ORG_개인사업체': '개인사업체',
        'ORG_회사법인': '회사법인',
        'ORG_회사이외법인': '회사이외법인',
        'ORG_비법인단체': '비법인단체',
        'ORG_국가지방자치단체': '국가/지자체'
    }

    org_cols_sum = ', '.join([f'SUM(COALESCE("{col}", 0)) as "{col}"' for col in org_columns.keys()])

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
    for col, name in org_columns.items():
        value = df[col].iloc[0] if col in df.columns else 0
        if pd.notna(value) and value > 0:
            result.append({'조직형태': name, '사업체수': int(value)})

    df_result = pd.DataFrame(result)
    if len(df_result) > 0:
        df_result['비율'] = (df_result['사업체수'] / df_result['사업체수'].sum() * 100).round(2)

    return df_result


def get_gender_data(year, quarter, view_type, sido=None):
    """
    대표자 성별 분포 데이터 조회

    Args:
        year: 조회 연도
        quarter: 조회 분기
        view_type: 조회 유형
        sido: 시도명

    Returns:
        pandas.DataFrame: 성별 사업체수 데이터
    """
    conn = get_db_connection()

    gender_columns = {
        'GENDER_남자': '남성',
        'GENDER_여자': '여성',
        'GENDER_(공백)': '미상'
    }

    gender_cols_sum = ', '.join([f'SUM(COALESCE("{col}", 0)) as "{col}"' for col in gender_columns.keys()])

    if view_type == '시도별' and sido:
        region_filter = f"AND \"CTPV_NM\" = '{sido}'"
    else:
        region_filter = ""

    query = f"""
        SELECT {gender_cols_sum}
        FROM sbr_quarter_summary
        WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
            AND "CTPV_NM" IS NOT NULL
            {region_filter}
    """

    df = pd.read_sql(query, conn)
    conn.close()

    result = []
    for col, name in gender_columns.items():
        value = df[col].iloc[0] if col in df.columns else 0
        if pd.notna(value) and value > 0:
            result.append({'성별': name, '사업체수': int(value)})

    df_result = pd.DataFrame(result)
    if len(df_result) > 0:
        df_result['비율'] = (df_result['사업체수'] / df_result['사업체수'].sum() * 100).round(2)

    return df_result


def get_status_data(year, quarter, view_type, sido=None):
    """
    영업상태별 분포 데이터 조회

    Args:
        year: 조회 연도
        quarter: 조회 분기
        view_type: 조회 유형
        sido: 시도명

    Returns:
        pandas.DataFrame: 영업상태별 사업체수 데이터
    """
    conn = get_db_connection()

    status_columns = {
        'STATUS_영업중': '영업중',
        'STATUS_폐업': '폐업'
    }

    status_cols_sum = ', '.join([f'SUM(COALESCE("{col}", 0)) as "{col}"' for col in status_columns.keys()])

    if view_type == '시도별' and sido:
        region_filter = f"AND \"CTPV_NM\" = '{sido}'"
    else:
        region_filter = ""

    query = f"""
        SELECT {status_cols_sum}
        FROM sbr_quarter_summary
        WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
            AND "CTPV_NM" IS NOT NULL
            {region_filter}
    """

    df = pd.read_sql(query, conn)
    conn.close()

    result = []
    for col, name in status_columns.items():
        value = df[col].iloc[0] if col in df.columns else 0
        if pd.notna(value) and value > 0:
            result.append({'영업상태': name, '사업체수': int(value)})

    df_result = pd.DataFrame(result)
    if len(df_result) > 0:
        df_result['비율'] = (df_result['사업체수'] / df_result['사업체수'].sum() * 100).round(2)

    return df_result


def create_industry_chart(df):
    """
    산업별 사업체 분포 가로 막대 차트 생성

    Args:
        df: 산업별 데이터

    Returns:
        str: Plotly 차트 HTML
    """
    if len(df) == 0:
        return "<p class='no-data'>데이터가 없습니다.</p>"

    # 상위 15개 산업
    df_top = df.head(15)

    fig = go.Figure(go.Bar(
        y=df_top['산업'].tolist()[::-1],
        x=df_top['사업체수'].tolist()[::-1],
        orientation='h',
        marker_color='#667eea',
        text=[f"{x:,}" for x in df_top['사업체수'].tolist()[::-1]],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>사업체수: %{x:,.0f}<extra></extra>'
    ))

    fig.update_layout(
        title=None,
        xaxis_title='사업체수',
        yaxis_title='산업',
        height=500,
        margin=dict(l=150, r=80, t=30, b=50),
        xaxis=dict(tickformat=','),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Malgun Gothic, sans-serif")
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id='industry-chart')


def create_organization_chart(df):
    """
    조직형태별 파이 차트 생성

    Args:
        df: 조직형태별 데이터

    Returns:
        str: Plotly 차트 HTML
    """
    if len(df) == 0:
        return "<p class='no-data'>데이터가 없습니다.</p>"

    colors = ['#667eea', '#764ba2', '#f24822', '#2ecc71', '#3498db']

    fig = go.Figure(go.Pie(
        labels=df['조직형태'].tolist(),
        values=df['사업체수'].tolist(),
        marker_colors=colors[:len(df)],
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>사업체수: %{value:,.0f}<br>비율: %{percent}<extra></extra>'
    ))

    fig.update_layout(
        title=None,
        height=350,
        margin=dict(l=30, r=30, t=30, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Malgun Gothic, sans-serif"),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5)
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id='org-chart')


def create_gender_chart(df):
    """
    대표자 성별 도넛 차트 생성

    Args:
        df: 성별 데이터

    Returns:
        str: Plotly 차트 HTML
    """
    if len(df) == 0:
        return "<p class='no-data'>데이터가 없습니다.</p>"

    colors = {'남성': '#3498db', '여성': '#e74c3c', '미상': '#95a5a6'}
    chart_colors = [colors.get(label, '#667eea') for label in df['성별'].tolist()]

    fig = go.Figure(go.Pie(
        labels=df['성별'].tolist(),
        values=df['사업체수'].tolist(),
        hole=0.5,
        marker_colors=chart_colors,
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>사업체수: %{value:,.0f}<br>비율: %{percent}<extra></extra>'
    ))

    fig.update_layout(
        title=None,
        height=350,
        margin=dict(l=30, r=30, t=30, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Malgun Gothic, sans-serif"),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
        annotations=[dict(text='성별', x=0.5, y=0.5, font_size=14, showarrow=False)]
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id='gender-chart')


def create_status_chart(df):
    """
    영업상태별 막대 차트 생성

    Args:
        df: 영업상태별 데이터

    Returns:
        str: Plotly 차트 HTML
    """
    if len(df) == 0:
        return "<p class='no-data'>데이터가 없습니다.</p>"

    colors = {'영업중': '#2ecc71', '폐업': '#e74c3c'}
    chart_colors = [colors.get(label, '#667eea') for label in df['영업상태'].tolist()]

    fig = go.Figure(go.Bar(
        x=df['영업상태'].tolist(),
        y=df['사업체수'].tolist(),
        marker_color=chart_colors,
        text=[f"{x:,} ({r:.1f}%)" for x, r in zip(df['사업체수'].tolist(), df['비율'].tolist())],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>사업체수: %{y:,.0f}<extra></extra>'
    ))

    fig.update_layout(
        title=None,
        xaxis_title='영업상태',
        yaxis_title='사업체수',
        height=350,
        margin=dict(l=50, r=30, t=50, b=50),
        yaxis=dict(tickformat=','),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Malgun Gothic, sans-serif")
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id='status-chart')


def generate_insights(industry_df, org_df, gender_df, status_df, view_type, sido):
    """
    인사이트 생성

    Args:
        industry_df: 산업별 데이터
        org_df: 조직형태별 데이터
        gender_df: 성별 데이터
        status_df: 영업상태별 데이터
        view_type: 조회 유형
        sido: 선택된 시도

    Returns:
        list: 인사이트 딕셔너리 리스트
    """
    insights = []
    region_label = sido if view_type == '시도별' else "전국"

    # 인사이트 1: 주력 산업
    if len(industry_df) > 0:
        top_industry = industry_df.iloc[0]
        insights.append({
            'icon': '🏭',
            'title': f'{region_label} 주력 산업',
            'content': f"{top_industry['산업']}이 {top_industry['사업체수']:,}개 ({top_industry['비율']:.1f}%)로 가장 많은 비중을 차지합니다."
        })

    # 인사이트 2: 조직형태
    if len(org_df) > 0:
        top_org = org_df.iloc[0]
        insights.append({
            'icon': '🏢',
            'title': '조직형태 특성',
            'content': f"{top_org['조직형태']}이 {top_org['비율']:.1f}%로 가장 높은 비중입니다."
        })

    # 인사이트 3: 여성 대표자 비율
    if len(gender_df) > 0:
        female_row = gender_df[gender_df['성별'] == '여성']
        if len(female_row) > 0:
            female_ratio = female_row.iloc[0]['비율']
            insights.append({
                'icon': '👩',
                'title': '여성 대표자 비율',
                'content': f"여성 대표자 비율은 {female_ratio:.1f}%입니다."
            })

    # 인사이트 4: 폐업률
    if len(status_df) > 0:
        closed_row = status_df[status_df['영업상태'] == '폐업']
        if len(closed_row) > 0:
            closed_ratio = closed_row.iloc[0]['비율']
            insights.append({
                'icon': '📊',
                'title': '폐업률',
                'content': f"폐업 사업체 비율은 {closed_ratio:.1f}%입니다."
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
    industry_df = get_industry_data(selected_year, selected_quarter, view_type, selected_sido)
    org_df = get_organization_data(selected_year, selected_quarter, view_type, selected_sido)
    gender_df = get_gender_data(selected_year, selected_quarter, view_type, selected_sido)
    status_df = get_status_data(selected_year, selected_quarter, view_type, selected_sido)

    # 차트 생성
    industry_chart = create_industry_chart(industry_df)
    org_chart = create_organization_chart(org_df)
    gender_chart = create_gender_chart(gender_df)
    status_chart = create_status_chart(status_df)

    # 인사이트 생성
    insights = generate_insights(industry_df, org_df, gender_df, status_df, view_type, selected_sido)

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

    # HTML 생성
    html = generate_html(
        filter_opts, selected_year, selected_quarter, view_type, selected_sido,
        latest_quarter_label, region_label,
        industry_chart, org_chart, gender_chart, status_chart, insights,
        PPT_AVAILABLE
    )

    return html


def generate_html(filter_opts, selected_year, selected_quarter, view_type, selected_sido,
                  latest_quarter_label, region_label,
                  industry_chart, org_chart, gender_chart, status_chart, insights,
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
        industry_chart: 산업별 차트 HTML
        org_chart: 조직형태별 차트 HTML
        gender_chart: 성별 차트 HTML
        status_chart: 영업상태별 차트 HTML
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

    html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>기업통계등록부 대시보드 - 산업 분석</title>
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
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }}
        .chart-card {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        .chart-title {{
            font-size: 1.2rem;
            color: #2c3e50;
            margin-bottom: 15px;
            font-weight: 600;
            text-align: center;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
            font-size: 1rem;
        }}
        .insights-container {{
            margin-top: 30px;
            padding: 25px;
            background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
            border-radius: 12px;
        }}
        .insights-title {{
            font-size: 1.4rem;
            color: #2c3e50;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 700;
        }}
        .insights-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 15px;
        }}
        .insight-card {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            display: flex;
            align-items: start;
            gap: 12px;
            transition: transform 0.3s;
        }}
        .insight-card:hover {{
            transform: translateY(-3px);
        }}
        .insight-icon {{
            font-size: 2rem;
            flex-shrink: 0;
        }}
        .insight-content {{
            flex: 1;
        }}
        .insight-title {{
            font-size: 1rem;
            color: #2c3e50;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        .insight-text {{
            font-size: 0.9rem;
            color: #555;
            line-height: 1.4;
        }}
        @media (max-width: 768px) {{
            .container {{
                padding: 15px;
            }}
            h1 {{
                font-size: 1.5rem;
            }}
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏭 기업통계등록부 산업 분석</h1>
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
                        <input type="radio" name="view_type" value="전체" {"checked" if view_type == "전체" else ""} onchange="toggleSidoSelect()"> 전체
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

        <!-- 차트 영역 -->
        <div class="chart-grid">
            <!-- 산업별 사업체 분포 -->
            <div class="chart-card" style="grid-column: span 2;">
                <h3 class="chart-title">📊 산업별 사업체 분포 (상위 15개)</h3>
                {industry_chart}
            </div>

            <!-- 조직형태별 분포 -->
            <div class="chart-card">
                <h3 class="chart-title">🏢 조직형태별 분포</h3>
                {org_chart}
            </div>

            <!-- 대표자 성별 분포 -->
            <div class="chart-card">
                <h3 class="chart-title">👥 대표자 성별 분포</h3>
                {gender_chart}
            </div>

            <!-- 영업상태별 분포 -->
            <div class="chart-card">
                <h3 class="chart-title">📈 영업상태별 분포</h3>
                {status_chart}
            </div>
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
    logger.info("=== PPT 저장 요청 시작 (대시보드2) ===")

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
        industry_df = get_industry_data(selected_year, selected_quarter, view_type, selected_sido)
        org_df = get_organization_data(selected_year, selected_quarter, view_type, selected_sido)
        gender_df = get_gender_data(selected_year, selected_quarter, view_type, selected_sido)
        status_df = get_status_data(selected_year, selected_quarter, view_type, selected_sido)

        # 인사이트 생성
        insights = generate_insights(industry_df, org_df, gender_df, status_df, view_type, selected_sido)

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

        # PPT 파일 생성
        logger.info("PPT 보고서 생성 시작...")
        output_path = generate_ppt_report(
            selected_year, selected_quarter, view_type, selected_sido,
            latest_quarter_label, region_label,
            industry_df, org_df, gender_df, status_df, insights
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

        filename = f"산업분석_{selected_year}년{selected_quarter}분기_{view_label}.pptx"
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
                        industry_df, org_df, gender_df, status_df, insights):
    """
    PPT 보고서 생성

    Args:
        selected_year, selected_quarter: 기준 년/분기
        view_type, selected_sido: 지역 필터
        latest_quarter_label, region_label: 표시 레이블
        industry_df, org_df, gender_df, status_df: 데이터프레임
        insights: 인사이트 목록

    Returns:
        str: 생성된 PPT 파일 경로
    """
    import matplotlib
    matplotlib.use('Agg')  # GUI 없이 사용
    import matplotlib.pyplot as plt
    import koreanize_matplotlib

    # 임시 디렉토리 생성
    temp_dir = tempfile.mkdtemp()

    # 차트 이미지 생성
    chart_paths = {}

    # 1. 산업별 사업체 분포 차트 (상위 15개)
    # 색상: 상위 5개는 파란색 그라데이션, 나머지는 회색
    n_industries = len(industry_df)
    fig_height = max(6, n_industries * 0.4)
    fig, ax = plt.subplots(figsize=(10, fig_height))

    blue_gradient = ['#1243A6', '#1D64F2', '#4A90E2', '#7EB6FF', '#B8D4FF']
    gray_color = '#C0C0C0'
    colors = [blue_gradient[i] if i < 5 else gray_color for i in range(n_industries)]

    y_pos = range(n_industries)
    ax.barh(y_pos, industry_df['사업체수'], color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(industry_df['산업명'])
    ax.set_xlabel('사업체수 (개)')
    ax.set_title(f'{region_label} 산업별 사업체 분포')
    ax.invert_yaxis()
    for i, v in enumerate(industry_df['사업체수']):
        ax.text(v + v*0.01, i, f'{int(v):,}', va='center', fontsize=8)
    plt.tight_layout()
    chart_path1 = os.path.join(temp_dir, "chart_industry.png")
    plt.savefig(chart_path1, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['산업별 사업체 분포'] = chart_path1

    # 2. 조직형태별 분포 파이 차트
    fig, ax = plt.subplots(figsize=(8, 6))
    colors_org = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe']
    ax.pie(org_df['사업체수'], labels=org_df['조직형태'], autopct='%1.1f%%',
           colors=colors_org[:len(org_df)], startangle=90)
    ax.set_title(f'{region_label} 조직형태별 분포')
    plt.tight_layout()
    chart_path2 = os.path.join(temp_dir, "chart_org.png")
    plt.savefig(chart_path2, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['조직형태별 분포'] = chart_path2

    # 3. 대표자 성별 분포 도넛 차트
    fig, ax = plt.subplots(figsize=(8, 6))
    colors_gender = ['#4A90E2', '#E94B8A', '#95a5a6']
    wedges, texts, autotexts = ax.pie(gender_df['사업체수'], labels=gender_df['성별'],
                                       autopct='%1.1f%%', colors=colors_gender[:len(gender_df)],
                                       startangle=90, wedgeprops=dict(width=0.5))
    ax.set_title(f'{region_label} 대표자 성별 분포')
    plt.tight_layout()
    chart_path3 = os.path.join(temp_dir, "chart_gender.png")
    plt.savefig(chart_path3, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['대표자 성별 분포'] = chart_path3

    # 4. 영업상태별 분포 막대 차트
    fig, ax = plt.subplots(figsize=(8, 5))
    colors_status = ['#27AE60', '#E74C3C', '#F39C12']
    ax.bar(status_df['영업상태'], status_df['사업체수'], color=colors_status[:len(status_df)])
    ax.set_xlabel('영업상태')
    ax.set_ylabel('사업체수 (개)')
    ax.set_title(f'{region_label} 영업상태별 분포')
    for i, v in enumerate(status_df['사업체수']):
        ax.text(i, v + v*0.01, f'{int(v):,}', ha='center', fontsize=10)
    plt.tight_layout()
    chart_path4 = os.path.join(temp_dir, "chart_status.png")
    plt.savefig(chart_path4, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['영업상태별 분포'] = chart_path4

    # 주요 지표 데이터
    total_biz = industry_df['사업체수'].sum() if not industry_df.empty else 0
    top_industry = industry_df.iloc[0]['산업명'] if not industry_df.empty else '-'
    top_org = org_df.iloc[0]['조직형태'] if not org_df.empty else '-'

    metrics = [
        {'label': '총 사업체수', 'value': f'{total_biz:,.0f}', 'unit': '개'},
        {'label': '최다 산업', 'value': top_industry, 'unit': ''},
        {'label': '주요 조직형태', 'value': top_org, 'unit': ''},
    ]

    # PPT 생성
    output_path = create_dashboard_ppt(
        title="기업체 산업 분석 보고서",
        subtitle=f"{latest_quarter_label} | {region_label}",
        metrics=metrics,
        df_aggregated=industry_df.rename(columns={'산업명': '지역명', '사업체수': '총사업체수'}),
        df_pop_biz=None,
        insights=insights,
        chart_paths=chart_paths,
        output_path=os.path.join(temp_dir, "report.pptx")
    )

    return output_path
