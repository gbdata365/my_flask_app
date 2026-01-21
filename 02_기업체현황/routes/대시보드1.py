# -*- coding: utf-8 -*-
"""
기업통계등록부(SBR) 대시보드 1 - 전체 개요
==========================================

주요 기능:
1. 주요 지표 카드: 총 사업체수, 총 종사자수, 평균 HHI, 평균 1인당 매출액
2. 시도별/권역별 사업체 현황 차트
3. 분기별 시계열 추이
4. 인구 대비 사업체 밀도
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
from datetime import datetime
from flask import request, send_file, Response, make_response
from loguru import logger
from urllib.parse import quote

# 상위 디렉토리 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_connection
from module.region_config import get_region_sido_mapping

# HWP 유틸리티 (Windows에서만 사용 가능)
try:
    from module.hwp_utils import HwpDocument, HWP_AVAILABLE
except ImportError:
    HWP_AVAILABLE = False

# PPT 유틸리티 (모든 환경에서 사용 가능)
try:
    from module.ppt_utils import create_dashboard_ppt, PPT_AVAILABLE
except ImportError:
    PPT_AVAILABLE = False


def get_filter_options():
    """
    필터 옵션 조회

    Returns:
        dict: {
            'quarters': 분기 목록 (연도 + 분기 조합),
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

    산업 다양성을 측정하는 지표로, 값이 낮을수록 산업이 다양함을 의미

    계산식: HHI = Σ (각 산업의 비중)²

    Args:
        industry_columns_dict (dict): {산업명: 사업체수} 딕셔너리

    Returns:
        float: HHI 값 (0~10000 범위, 낮을수록 다양함)
    """
    total = sum(industry_columns_dict.values())

    if total == 0:
        return 0

    # 각 산업의 비중(%) 계산 후 제곱하여 합산
    hhi = sum(((count / total) * 100) ** 2 for count in industry_columns_dict.values())

    return round(hhi, 2)


def get_aggregated_data(year, quarter, view_type, sido=None):
    """
    view_type에 따른 집계 데이터 조회 (HHI, 1인당 매출액 포함)

    Args:
        year (str): 조회 연도
        quarter (str): 조회 분기
        view_type (str): 조회 유형 ('전체', '권역별', '시도별')
        sido (str, optional): 시도명 (view_type='시도별'일 때)

    Returns:
        pandas.DataFrame: 지역별 집계 데이터 (HHI, 1인당매출액 포함)
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

    # 일반 SELECT용 (집계 없이)
    industry_cols_sql = ', '.join([f'"{col}"' for col in industry_columns])
    # 집계용 (SUM으로 감싸기)
    industry_cols_sum_sql = ', '.join([f'SUM("{col}") as "{col}"' for col in industry_columns])

    if view_type == '전체':
        # 전체: 시도별 집계
        query = f"""
            SELECT
                "CTPV_NM" as 지역명,
                SUM("ORG_합계") as 총사업체수,
                SUM("STATS_기업종사자수_합계") as 총종사자수,
                SUM("STATS_기업매출금액_합계") as 총매출액,
                ROUND(SUM("STATS_기업종사자수_합계")::numeric /
                      NULLIF(SUM("ORG_합계")::numeric, 0), 2) as 평균종사자수,
                -- 산업별 사업체수 (HHI 계산용)
                {industry_cols_sum_sql}
            FROM sbr_quarter_summary
            WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
                AND "CTPV_NM" IS NOT NULL
            GROUP BY "CTPV_NM"
            ORDER BY 총사업체수 DESC
        """
    elif view_type == '권역별':
        # 권역별: 권역으로 그룹화
        region_mapping = get_region_sido_mapping()

        # CASE 문 생성
        cases = []
        for region, sidos in region_mapping.items():
            sido_list = "','".join(sidos)
            cases.append(f"WHEN \"CTPV_NM\" IN ('{sido_list}') THEN '{region}'")

        case_sql = " ".join(cases)

        query = f"""
            SELECT
                CASE {case_sql} ELSE '기타' END as 지역명,
                SUM("ORG_합계") as 총사업체수,
                SUM("STATS_기업종사자수_합계") as 총종사자수,
                SUM("STATS_기업매출금액_합계") as 총매출액,
                ROUND(SUM("STATS_기업종사자수_합계")::numeric /
                      NULLIF(SUM("ORG_합계")::numeric, 0), 2) as 평균종사자수,
                -- 산업별 사업체수
                {industry_cols_sum_sql}
            FROM sbr_quarter_summary
            WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
                AND "CTPV_NM" IS NOT NULL
            GROUP BY CASE {case_sql} ELSE '기타' END
            ORDER BY 총사업체수 DESC
        """
    elif view_type == '시도별' and sido:
        # 시도별: 선택된 시도 내 시군구별 집계
        query = f"""
            WITH sigungu_summary AS (
                SELECT
                    LEFT("ADCLSF_SGG_CD", 4) as sigungu_code_4,
                    "SGG_NM",
                    SUM("ORG_합계") as 총사업체수,
                    SUM("STATS_기업종사자수_합계") as 총종사자수,
                    SUM("STATS_기업매출금액_합계") as 총매출액,
                    {', '.join([f'SUM("{col}") as "{col}"' for col in industry_columns])}
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
                총종사자수,
                총매출액,
                ROUND(총종사자수::numeric / NULLIF(총사업체수::numeric, 0), 2) as 평균종사자수,
                {industry_cols_sql}
            FROM sigungu_summary
            ORDER BY sigungu_code_4
        """
    else:
        # 기본값: 전국 합계
        query = f"""
            SELECT
                '전국' as 지역명,
                SUM("ORG_합계") as 총사업체수,
                SUM("STATS_기업종사자수_합계") as 총종사자수,
                SUM("STATS_기업매출금액_합계") as 총매출액,
                ROUND(SUM("STATS_기업종사자수_합계")::numeric /
                      NULLIF(SUM("ORG_합계")::numeric, 0), 2) as 평균종사자수,
                {industry_cols_sum_sql}
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

    # 1인당 매출액 계산 (백만원 단위)
    df['1인당매출액'] = df.apply(
        lambda row: round(row['총매출액'] / row['총종사자수'], 2)
        if row['총종사자수'] > 0 else None,
        axis=1
    )

    # 산업별 컬럼 제거
    df = df.drop(columns=industry_columns, errors='ignore')

    return df


def get_timeseries_data(view_type, sido=None):
    """
    시계열 데이터 조회 (모든 분기)

    Args:
        view_type (str): 조회 유형
        sido (str, optional): 시도명

    Returns:
        pandas.DataFrame: 분기별 시계열 데이터
    """
    conn = get_db_connection()

    # 필터 조건 생성
    if view_type == '전체':
        region_filter = ""
    elif view_type == '권역별':
        region_filter = ""
    elif view_type == '시도별' and sido:
        region_filter = f' AND "CTPV_NM" = \'{sido}\''
    else:
        region_filter = ""

    query = f"""
        SELECT
            "CRTR_YR" || 'Q' || "QU_SE_CD" as 분기,
            "CRTR_YR" as 연도,
            "QU_SE_CD" as 분기코드,
            SUM("ORG_합계") as 총사업체수,
            SUM("STATS_기업종사자수_합계") as 총종사자수,
            SUM("STATS_기업매출금액_합계") as 총매출액,
            SUM("GENDER_여자") as 여성대표,
            SUM("GENDER_합계") as 전체대표
        FROM sbr_quarter_summary
        WHERE 1=1 {region_filter}
        GROUP BY "CRTR_YR", "QU_SE_CD"
        ORDER BY "CRTR_YR", "QU_SE_CD"
    """

    df = pd.read_sql(query, conn)
    conn.close()

    return df


def get_population_density_data(year, quarter, view_type, sido=None):
    """
    인구 대비 사업체 밀도 데이터 조회

    Args:
        year (str): 조회 연도
        quarter (str): 조회 분기
        view_type (str): 조회 유형
        sido (str, optional): 시도명

    Returns:
        pandas.DataFrame: 인구 밀도 데이터
    """
    conn = get_db_connection()

    if view_type == '시도별' and sido:
        # 시도별: 해당 시도 내 시군구별 집계 (4자리 코드 그룹화)
        query = f"""
            WITH latest_month AS (
                SELECT MAX(base_ym) as latest_ym
                FROM fact_population_basic
            ),
            sigungu_pop AS (
                SELECT
                    d.sido_nm,
                    d.sigungu_nm,
                    LEFT(d.sigungu_code, 4) as sigungu_code_4,
                    SUM(f.total_pop) as 총인구,
                    SUM(f.household_cnt) as 총가구수
                FROM fact_population_basic f
                JOIN dim_admin_area d ON f.admin_code = d.admin_code
                JOIN latest_month lm ON f.base_ym = lm.latest_ym
                WHERE d.sido_nm = '{sido}'
                    AND d.sigungu_nm IS NOT NULL
                GROUP BY d.sido_nm, d.sigungu_nm, LEFT(d.sigungu_code, 4)
            ),
            sigungu_biz AS (
                SELECT
                    "SGG_NM" as 시군구명,
                    LEFT("ADCLSF_SGG_CD", 4) as sigungu_code_4,
                    SUM("ORG_합계") as 사업체수,
                    SUM("STATS_기업종사자수_합계") as 종사자수
                FROM sbr_quarter_summary
                WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
                    AND "CTPV_NM" = '{sido}'
                    AND "SGG_NM" IS NOT NULL
                GROUP BY "SGG_NM", LEFT("ADCLSF_SGG_CD", 4)
            )
            SELECT
                COALESCE(b.시군구명, p.sigungu_nm) as 시도명,
                COALESCE(p.총인구, 0) as 총인구,
                COALESCE(p.총가구수, 0) as 총가구수,
                COALESCE(b.사업체수, 0) as 사업체수,
                COALESCE(b.종사자수, 0) as 종사자수,
                CASE
                    WHEN COALESCE(p.총인구, 0) > 0 THEN ROUND((b.사업체수::numeric / p.총인구 * 1000), 2)
                    ELSE 0
                END as 인구천명당사업체수,
                CASE
                    WHEN COALESCE(p.총가구수, 0) > 0 THEN ROUND((b.사업체수::numeric / p.총가구수), 2)
                    ELSE 0
                END as 가구당사업체수,
                COALESCE(b.sigungu_code_4, p.sigungu_code_4) as 시군구코드
            FROM sigungu_pop p
            FULL OUTER JOIN sigungu_biz b ON p.sigungu_code_4 = b.sigungu_code_4
            WHERE COALESCE(b.사업체수, 0) > 0
            ORDER BY 시군구코드
        """
    else:
        # 전체/권역별: 시도 수준 집계
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
            sido_biz AS (
                SELECT
                    "CTPV_NM" as 시도명,
                    SUM("ORG_합계") as 사업체수,
                    SUM("STATS_기업종사자수_합계") as 종사자수
                FROM sbr_quarter_summary
                WHERE "CRTR_YR" = '{year}' AND "QU_SE_CD" = '{quarter}'
                GROUP BY "CTPV_NM"
            )
            SELECT
                COALESCE(b.시도명, p.sido_nm) as 시도명,
                COALESCE(p.총인구, 0) as 총인구,
                COALESCE(p.총가구수, 0) as 총가구수,
                COALESCE(b.사업체수, 0) as 사업체수,
                COALESCE(b.종사자수, 0) as 종사자수,
                CASE
                    WHEN p.총인구 > 0 THEN ROUND((b.사업체수::numeric / p.총인구 * 1000), 2)
                    ELSE 0
                END as 인구천명당사업체수,
                CASE
                    WHEN p.총가구수 > 0 THEN ROUND((b.사업체수::numeric / p.총가구수), 2)
                    ELSE 0
                END as 가구당사업체수
            FROM sido_pop p
            FULL OUTER JOIN sido_biz b ON p.sido_nm = b.시도명
            WHERE COALESCE(b.사업체수, 0) > 0
            ORDER BY 사업체수 DESC
        """

    df = pd.read_sql(query, conn)
    conn.close()

    return df


def generate_insights(df_aggregated, df_ts, df_pop_biz, view_type, selected_sido):
    """
    데이터 기반 인사이트 생성

    Args:
        df_aggregated: 집계 데이터 (HHI, 1인당매출액 포함)
        df_ts: 시계열 데이터
        df_pop_biz: 인구 밀도 데이터
        view_type: 조회 유형
        selected_sido: 선택된 시도

    Returns:
        list: 인사이트 딕셔너리 리스트
    """
    insights = []

    # 인사이트 1: 사업체 밀도가 가장 높은 지역
    if len(df_pop_biz) > 0:
        top_density = df_pop_biz.nlargest(1, '인구천명당사업체수').iloc[0]
        insights.append({
            'icon': '📍',
            'title': '사업체 밀도 최고 지역',
            'content': f"{top_density['시도명']}이 인구 천명당 {top_density['인구천명당사업체수']:.1f}개로 가장 높은 사업체 밀도를 보이고 있습니다."
        })

    # 인사이트 2: HHI 기반 산업 다양성
    if len(df_aggregated) > 0 and 'HHI' in df_aggregated.columns:
        avg_hhi = df_aggregated['HHI'].mean()
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
    if len(df_aggregated) > 0 and '1인당매출액' in df_aggregated.columns:
        avg_sales = df_aggregated['1인당매출액'].mean()
        insights.append({
            'icon': '💰',
            'title': '평균 1인당 매출액',
            'content': f"평균 1인당 매출액은 {avg_sales:.2f}백만원으로, 생산성 지표입니다."
        })

    # 인사이트 4: 시계열 증감률
    if len(df_ts) >= 2:
        latest = df_ts.iloc[-1]
        previous = df_ts.iloc[-2]
        growth_rate = ((latest['총사업체수'] - previous['총사업체수']) / previous['총사업체수'] * 100) if previous['총사업체수'] > 0 else 0
        direction = "증가" if growth_rate > 0 else "감소"
        region_desc = selected_sido if view_type == '시도별' else "해당 지역"
        insights.append({
            'icon': '📈' if growth_rate > 0 else '📉',
            'title': f'전분기 대비 {direction}',
            'content': f"{region_desc} 사업체수가 전분기 대비 {abs(growth_rate):.2f}% {direction}하여 {'성장세' if growth_rate > 0 else '감소세'}를 보이고 있습니다."
        })

    return insights


def render(request_args=None):
    """
    Flask에서 호출되는 렌더링 함수

    Args:
        request_args (dict, optional): Flask request.args

    Returns:
        str: 렌더링된 HTML 또는 Flask Response (HWP 다운로드 시)
    """
    # POST 요청 처리 (PPT/HWP 저장)
    try:
        if request.method == 'POST':
            action = request.form.get('action')
            logger.info(f"POST 요청 수신 - action: {action}")
            if action == 'save_hwp':
                logger.info("HWP 저장 핸들러 호출")
                return handle_hwp_save(request.form)
            elif action == 'save_ppt':
                logger.info("PPT 저장 핸들러 호출")
                return handle_ppt_save(request.form)
            else:
                logger.warning(f"알 수 없는 action: {action}")
    except RuntimeError as e:
        # request context 외부에서 호출된 경우 무시
        logger.debug(f"RuntimeError (무시됨): {e}")
        pass
    except Exception as e:
        logger.error(f"POST 처리 중 예외 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # 필터 옵션 가져오기
    filter_opts = get_filter_options()

    # 요청 파라미터 파싱 (초기값: 시도별 + 경상북도)
    request_args = request_args or {}
    selected_year = request_args.get('year', filter_opts['quarters'][0]['CRTR_YR'])
    selected_quarter = request_args.get('quarter', filter_opts['quarters'][0]['QU_SE_CD'])
    view_type = request_args.get('view_type', '시도별')
    selected_sido = request_args.get('sido', '경상북도')

    # 데이터 조회
    df_aggregated = get_aggregated_data(selected_year, selected_quarter, view_type, selected_sido)
    df_ts = get_timeseries_data(view_type, selected_sido)
    df_pop_biz = get_population_density_data(selected_year, selected_quarter, view_type, selected_sido)

    # 주요 지표 계산
    total_businesses = df_aggregated['총사업체수'].sum()
    total_employees = df_aggregated['총종사자수'].sum()
    avg_hhi = df_aggregated['HHI'].mean() if 'HHI' in df_aggregated.columns else 0
    avg_sales_per_employee = df_aggregated['1인당매출액'].mean() if '1인당매출액' in df_aggregated.columns else 0

    # 인사이트 생성
    insights = generate_insights(df_aggregated, df_ts, df_pop_biz, view_type, selected_sido)

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

    # HTML 생성
    html = generate_html(
        filter_opts, selected_year, selected_quarter, view_type, selected_sido,
        latest_quarter_label, region_label,
        total_businesses, total_employees, avg_hhi, avg_sales_per_employee,
        df_aggregated, df_ts, df_pop_biz, insights,
        HWP_AVAILABLE,  # HWP 사용 가능 여부 전달
        PPT_AVAILABLE   # PPT 사용 가능 여부 전달
    )

    return html


def handle_hwp_save(form_data):
    """
    아래아한글 저장 요청 처리

    Args:
        form_data: Flask request.form

    Returns:
        Flask Response: HWP 파일 다운로드 또는 오류 메시지
    """
    logger.info("=== HWP 저장 요청 시작 ===")
    logger.info(f"HWP_AVAILABLE: {HWP_AVAILABLE}")
    logger.info(f"form_data: {dict(form_data)}")

    if not HWP_AVAILABLE:
        logger.warning("HWP 사용 불가 - Windows 환경 또는 한글 프로그램 필요")
        return Response(
            "<script>alert('아래아한글 저장 기능은 Windows 환경에서만 사용 가능합니다.'); history.back();</script>",
            mimetype='text/html'
        )

    try:
        # 폼 데이터에서 파라미터 추출
        selected_year = form_data.get('year')
        selected_quarter = form_data.get('quarter')
        view_type = form_data.get('view_type', '시도별')
        selected_sido = form_data.get('sido', '경상북도')

        # 데이터 조회
        df_aggregated = get_aggregated_data(selected_year, selected_quarter, view_type, selected_sido)
        df_ts = get_timeseries_data(view_type, selected_sido)
        df_pop_biz = get_population_density_data(selected_year, selected_quarter, view_type, selected_sido)

        # 주요 지표 계산
        total_businesses = df_aggregated['총사업체수'].sum()
        total_employees = df_aggregated['총종사자수'].sum()
        avg_hhi = df_aggregated['HHI'].mean() if 'HHI' in df_aggregated.columns else 0
        avg_sales_per_employee = df_aggregated['1인당매출액'].mean() if '1인당매출액' in df_aggregated.columns else 0

        # 인사이트 생성
        insights = generate_insights(df_aggregated, df_ts, df_pop_biz, view_type, selected_sido)

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

        # HWP 파일 생성
        logger.info("HWP 보고서 생성 시작...")
        output_path = generate_hwp_report(
            selected_year, selected_quarter, view_type, selected_sido,
            latest_quarter_label, region_label,
            total_businesses, total_employees, avg_hhi, avg_sales_per_employee,
            df_aggregated, df_ts, df_pop_biz, insights
        )
        logger.info(f"HWP 파일 생성 완료: {output_path}")

        # 파일 존재 확인
        if not os.path.exists(output_path):
            logger.error(f"HWP 파일이 생성되지 않음: {output_path}")
            return Response(
                "<script>alert('HWP 파일 생성 실패'); history.back();</script>",
                mimetype='text/html'
            )

        # 파일명 생성 (선택 조건 포함)
        if view_type == '시도별':
            view_label = f"{selected_sido}_시군구별"
        elif view_type == '전체':
            view_label = "전국_시도별"
        else:
            view_label = view_type

        filename = f"기업통계등록부_{selected_year}년{selected_quarter}분기_{view_label}.hwp"
        logger.info(f"파일 다운로드 시작: {filename}")

        # 파일 읽기 및 응답 생성 (한글 파일명 인코딩 처리)
        with open(output_path, 'rb') as f:
            file_data = f.read()

        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/x-hwp'
        # RFC 5987 방식으로 UTF-8 파일명 인코딩
        encoded_filename = quote(filename)
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
        response.headers['Content-Length'] = len(file_data)

        return response

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"HWP 저장 오류: {str(e)}")
        logger.error(f"상세 오류:\n{error_trace}")
        return Response(
            f"<script>alert('HWP 저장 중 오류 발생: {str(e)}'); history.back();</script>",
            mimetype='text/html'
        )


def handle_ppt_save(form_data):
    """
    PPT 저장 요청 처리

    Args:
        form_data: Flask request.form

    Returns:
        Flask Response: PPT 파일 다운로드 또는 오류 메시지
    """
    logger.info("=== PPT 저장 요청 시작 ===")
    logger.info(f"PPT_AVAILABLE: {PPT_AVAILABLE}")
    logger.info(f"form_data: {dict(form_data)}")

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
        df_aggregated = get_aggregated_data(selected_year, selected_quarter, view_type, selected_sido)
        df_ts = get_timeseries_data(view_type, selected_sido)
        df_pop_biz = get_population_density_data(selected_year, selected_quarter, view_type, selected_sido)

        # 주요 지표 계산
        total_businesses = df_aggregated['총사업체수'].sum()
        total_employees = df_aggregated['총종사자수'].sum()
        avg_hhi = df_aggregated['HHI'].mean() if 'HHI' in df_aggregated.columns else 0
        avg_sales_per_employee = df_aggregated['1인당매출액'].mean() if '1인당매출액' in df_aggregated.columns else 0

        # 인사이트 생성
        insights = generate_insights(df_aggregated, df_ts, df_pop_biz, view_type, selected_sido)

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
            latest_quarter_label, region_label,
            total_businesses, total_employees, avg_hhi, avg_sales_per_employee,
            df_aggregated, df_ts, df_pop_biz, insights
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

        filename = f"기업통계등록부_{selected_year}년{selected_quarter}분기_{view_label}.pptx"
        logger.info(f"파일 다운로드 시작: {filename}")

        # 파일 읽기 및 응답 생성 (한글 파일명 인코딩 처리)
        with open(output_path, 'rb') as f:
            file_data = f.read()

        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        # RFC 5987 방식으로 UTF-8 파일명 인코딩
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
                        total_businesses, total_employees, avg_hhi, avg_sales_per_employee,
                        df_aggregated, df_ts, df_pop_biz, insights):
    """
    PPT 보고서 생성

    Args:
        ... (대시보드 데이터)

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

    # 1. 지역별 사업체 현황 차트 (모든 데이터 표시)
    # 색상: 상위 5개는 파란색 그라데이션, 나머지는 회색
    n_regions = len(df_aggregated)
    fig_height = max(6, n_regions * 0.4)  # 동적 높이 조절
    fig, ax = plt.subplots(figsize=(10, fig_height))

    # 상위 5개: 파란색 그라데이션, 나머지: 회색
    blue_gradient = ['#1243A6', '#1D64F2', '#4A90E2', '#7EB6FF', '#B8D4FF']
    gray_color = '#C0C0C0'
    colors = []
    for i in range(n_regions):
        if i < 5:
            colors.append(blue_gradient[i])
        else:
            colors.append(gray_color)

    y_pos = range(n_regions)
    ax.barh(y_pos, df_aggregated['총사업체수'], color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df_aggregated['지역명'])
    ax.set_xlabel('사업체수 (개)')
    ax.set_title(f'{region_label} 사업체 현황')
    ax.invert_yaxis()  # 1위가 위로
    for i, v in enumerate(df_aggregated['총사업체수']):
        ax.text(v + v*0.01, i, f'{int(v):,}', va='center', fontsize=8)
    plt.tight_layout()
    chart_path1 = os.path.join(temp_dir, "chart_region.png")
    plt.savefig(chart_path1, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['지역별 사업체 현황'] = chart_path1

    # 2. 시계열 추이 차트
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()
    line1 = ax1.plot(df_ts['분기'], df_ts['총사업체수'], 'b-o', label='총 사업체수', linewidth=2, markersize=6)
    line2 = ax2.plot(df_ts['분기'], df_ts['총종사자수'], 'r-s', label='총 종사자수', linewidth=2, markersize=6)
    ax1.set_xlabel('분기')
    ax1.set_ylabel('사업체수 (개)', color='blue')
    ax2.set_ylabel('종사자수 (명)', color='red')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax2.tick_params(axis='y', labelcolor='red')
    plt.xticks(rotation=45, ha='right')
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    plt.title('분기별 시계열 추이')
    plt.tight_layout()
    chart_path2 = os.path.join(temp_dir, "chart_timeseries.png")
    plt.savefig(chart_path2, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['분기별 시계열 추이'] = chart_path2

    # 3. 인구 천명당 사업체수 차트 (모든 데이터 표시)
    # 색상: 상위 5개는 파란색 그라데이션, 나머지는 회색
    n_pop_biz = len(df_pop_biz)
    fig_height_pop = max(6, n_pop_biz * 0.4)  # 동적 높이 조절
    fig, ax = plt.subplots(figsize=(10, fig_height_pop))

    # 상위 5개: 파란색 그라데이션, 나머지: 회색
    colors_pop = []
    for i in range(n_pop_biz):
        if i < 5:
            colors_pop.append(blue_gradient[i])
        else:
            colors_pop.append(gray_color)

    y_pos = range(n_pop_biz)
    ax.barh(y_pos, df_pop_biz['인구천명당사업체수'], color=colors_pop)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df_pop_biz['시도명'])
    ax.set_xlabel('인구 천명당 사업체수 (개)')
    ax.set_title('인구 대비 사업체 밀도')
    ax.invert_yaxis()
    for i, v in enumerate(df_pop_biz['인구천명당사업체수']):
        ax.text(v + 0.5, i, f'{v:.2f}', va='center', fontsize=9)
    plt.tight_layout()
    chart_path3 = os.path.join(temp_dir, "chart_density.png")
    plt.savefig(chart_path3, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths['인구 대비 사업체 밀도'] = chart_path3

    # 주요 지표 데이터
    metrics = [
        {'label': '총 사업체수', 'value': f'{total_businesses:,.0f}', 'unit': '개'},
        {'label': '총 종사자수', 'value': f'{total_employees:,.0f}', 'unit': '명'},
        {'label': '평균 HHI', 'value': f'{avg_hhi:.1f}', 'unit': '낮을수록 다양함'},
        {'label': '평균 1인당 매출액', 'value': f'{avg_sales_per_employee:.1f}', 'unit': '백만원'},
    ]

    # PPT 생성
    output_path = create_dashboard_ppt(
        title="기업통계등록부(SBR) 분석 보고서",
        subtitle=f"{latest_quarter_label} | {region_label}",
        metrics=metrics,
        df_aggregated=df_aggregated,
        df_pop_biz=df_pop_biz,
        insights=insights,
        chart_paths=chart_paths,
        output_path=os.path.join(temp_dir, "report.pptx")
    )

    return output_path


def generate_hwp_report(selected_year, selected_quarter, view_type, selected_sido,
                        latest_quarter_label, region_label,
                        total_businesses, total_employees, avg_hhi, avg_sales_per_employee,
                        df_aggregated, df_ts, df_pop_biz, insights):
    """
    HWP 보고서 생성

    Args:
        ... (대시보드 데이터)

    Returns:
        str: 생성된 HWP 파일 경로
    """
    import matplotlib.pyplot as plt
    import koreanize_matplotlib

    # 임시 디렉토리 생성
    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "report.hwp")

    with HwpDocument(visible=False) as hwp:
        # 새 문서 생성
        hwp.create_new()

        # 제목 입력
        hwp.insert_text("기업통계등록부(SBR) 분석 보고서\n")
        hwp.insert_text("=" * 50 + "\n\n")

        # 기본 정보
        hwp.insert_text(f"기준: {latest_quarter_label}\n")
        hwp.insert_text(f"지역: {region_label}\n")
        hwp.insert_text(f"작성일: {datetime.now().strftime('%Y년 %m월 %d일')}\n\n")

        # 1. 주요 지표 요약
        hwp.insert_text("-" * 50 + "\n")
        hwp.insert_text("1. 주요 지표 요약\n")
        hwp.insert_text("-" * 50 + "\n\n")
        hwp.insert_text(f"  - 총 사업체수: {total_businesses:,.0f}개\n")
        hwp.insert_text(f"  - 총 종사자수: {total_employees:,.0f}명\n")
        hwp.insert_text(f"  - 평균 HHI (산업 다양성): {avg_hhi:.1f}\n")
        hwp.insert_text(f"  - 평균 1인당 매출액: {avg_sales_per_employee:.1f}백만원\n\n")

        # 2. 지역별 현황 표
        hwp.insert_text("-" * 50 + "\n")
        hwp.insert_text("2. 지역별 현황\n")
        hwp.insert_text("-" * 50 + "\n\n")

        # 표 데이터 추가 (상위 10개)
        df_top10 = df_aggregated.head(10)[['지역명', '총사업체수', '총종사자수', 'HHI', '1인당매출액']]
        for i, row in df_top10.iterrows():
            hwp.insert_text(f"  {row['지역명']}: 사업체 {row['총사업체수']:,.0f}개, ")
            hwp.insert_text(f"종사자 {row['총종사자수']:,.0f}명, ")
            hwp.insert_text(f"HHI {row['HHI']:.1f}, ")
            sales = row['1인당매출액']
            if pd.notna(sales):
                hwp.insert_text(f"1인당매출 {sales:.1f}백만원\n")
            else:
                hwp.insert_text("1인당매출 N/A\n")
        hwp.insert_text("\n")

        # 3. 지역별 사업체 현황 차트
        hwp.insert_text("-" * 50 + "\n")
        hwp.insert_text("3. 지역별 사업체 현황 차트\n")
        hwp.insert_text("-" * 50 + "\n\n")

        # 차트 생성 및 저장
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(df_aggregated['지역명'].head(10), df_aggregated['총사업체수'].head(10), color='#667eea')
        ax.set_xlabel('지역명')
        ax.set_ylabel('사업체수 (개)')
        ax.set_title(f'{region_label} 사업체 현황')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        chart_path = os.path.join(temp_dir, "chart_region.png")
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()

        # 이미지 삽입
        hwp.insert_picture(chart_path)
        hwp.insert_text("\n\n")

        # 4. 시계열 추이 차트
        hwp.insert_text("-" * 50 + "\n")
        hwp.insert_text("4. 분기별 시계열 추이\n")
        hwp.insert_text("-" * 50 + "\n\n")

        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax2 = ax1.twinx()
        ax1.plot(df_ts['분기'], df_ts['총사업체수'], 'b-o', label='총 사업체수', linewidth=2)
        ax2.plot(df_ts['분기'], df_ts['총종사자수'], 'r-s', label='총 종사자수', linewidth=2)
        ax1.set_xlabel('분기')
        ax1.set_ylabel('사업체수 (개)', color='blue')
        ax2.set_ylabel('종사자수 (명)', color='red')
        ax1.tick_params(axis='y', labelcolor='blue')
        ax2.tick_params(axis='y', labelcolor='red')
        plt.xticks(rotation=45, ha='right')
        fig.legend(loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=2)
        plt.tight_layout()
        chart_ts_path = os.path.join(temp_dir, "chart_timeseries.png")
        plt.savefig(chart_ts_path, dpi=150, bbox_inches='tight')
        plt.close()

        hwp.insert_picture(chart_ts_path)
        hwp.insert_text("\n\n")

        # 5. 인구 대비 사업체 밀도
        hwp.insert_text("-" * 50 + "\n")
        hwp.insert_text("5. 인구 대비 사업체 밀도 (인구 천명당 사업체수)\n")
        hwp.insert_text("-" * 50 + "\n\n")

        for i, row in df_pop_biz.head(10).iterrows():
            hwp.insert_text(f"  {row['시도명']}: {row['인구천명당사업체수']:.2f}개/천명\n")
        hwp.insert_text("\n")

        # 6. 주요 인사이트
        hwp.insert_text("-" * 50 + "\n")
        hwp.insert_text("6. 주요 인사이트\n")
        hwp.insert_text("-" * 50 + "\n\n")

        for insight in insights:
            hwp.insert_text(f"  {insight['icon']} {insight['title']}\n")
            hwp.insert_text(f"     {insight['content']}\n\n")

        # 파일 저장
        hwp.save_as(output_path)

    return output_path


def generate_html(filter_opts, selected_year, selected_quarter, view_type, selected_sido,
                  latest_quarter_label, region_label,
                  total_businesses, total_employees, avg_hhi, avg_sales_per_employee,
                  df_aggregated, df_ts, df_pop_biz, insights, hwp_available=False, ppt_available=False):
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
        total_businesses: 총 사업체수
        total_employees: 총 종사자수
        avg_hhi: 평균 HHI
        avg_sales_per_employee: 평균 1인당 매출액
        df_aggregated: 집계 데이터
        df_ts: 시계열 데이터
        df_pop_biz: 인구 밀도 데이터
        insights: 인사이트 리스트
        hwp_available: HWP 저장 기능 사용 가능 여부
        ppt_available: PPT 저장 기능 사용 가능 여부

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

    # 인사이트 카드 HTML
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
    <title>기업통계등록부 대시보드 - 전체 개요</title>
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
        .save-buttons-container {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: -10px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}
        .save-form {{
            display: inline-block;
        }}
        .save-notice {{
            text-align: center;
            font-size: 0.85rem;
            color: #7f8c8d;
            margin-bottom: 20px;
        }}
        .ppt-btn {{
            background: linear-gradient(135deg, #e67e22, #f39c12);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s, background 0.2s;
        }}
        .ppt-btn:hover {{
            transform: translateY(-2px);
            background: linear-gradient(135deg, #d35400, #e67e22);
        }}
        .ppt-btn:disabled {{
            background: #bdc3c7;
            cursor: not-allowed;
            transform: none;
        }}
        .hwp-btn {{
            background: linear-gradient(135deg, #27ae60, #2ecc71);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s, background 0.2s;
        }}
        .hwp-btn:hover {{
            transform: translateY(-2px);
            background: linear-gradient(135deg, #219a52, #27ae60);
        }}
        .hwp-btn:disabled {{
            background: #bdc3c7;
            cursor: not-allowed;
            transform: none;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
        }}
        .metric-label {{
            font-size: 0.9rem;
            opacity: 0.9;
            margin-bottom: 8px;
        }}
        .metric-value {{
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .metric-unit {{
            font-size: 0.85rem;
            opacity: 0.8;
        }}
        .chart-container {{
            margin-bottom: 30px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
        }}
        .chart-title {{
            font-size: 1.3rem;
            color: #2c3e50;
            margin-bottom: 15px;
            font-weight: 600;
        }}
        .insights-container {{
            margin-top: 40px;
            padding: 30px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
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
            .metric-value {{
                font-size: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 기업통계등록부 전체 개요</h1>
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

            <div style="text-align: center; display: flex; gap: 15px; justify-content: center; flex-wrap: wrap;">
                <button type="submit" class="filter-btn">🔍 조회하기</button>
            </div>
        </form>

        <!-- 저장 버튼들 (PPT, HWP) -->
        <div class="save-buttons-container">
            <!-- PPT 저장 폼 -->
            <form method="post" class="save-form">
                <input type="hidden" name="action" value="save_ppt">
                <input type="hidden" name="year" value="{selected_year}">
                <input type="hidden" name="quarter" value="{selected_quarter}">
                <input type="hidden" name="view_type" value="{view_type}">
                <input type="hidden" name="sido" value="{selected_sido}">
                <button type="submit" class="ppt-btn" {'disabled title="python-pptx 설치 필요"' if not ppt_available else ''}>
                    📊 PPT 저장
                </button>
            </form>

            <!-- HWP 저장 폼 -->
            <form method="post" class="save-form">
                <input type="hidden" name="action" value="save_hwp">
                <input type="hidden" name="year" value="{selected_year}">
                <input type="hidden" name="quarter" value="{selected_quarter}">
                <input type="hidden" name="view_type" value="{view_type}">
                <input type="hidden" name="sido" value="{selected_sido}">
                <button type="submit" class="hwp-btn" {'disabled title="Windows + 한글 설치 환경에서만 사용 가능"' if not hwp_available else ''}>
                    📄 HWP 저장
                </button>
            </form>
        </div>
        <p class="save-notice">
            {'✅ PPT: 사용 가능' if ppt_available else '❌ PPT: python-pptx 설치 필요'} |
            {'✅ HWP: 사용 가능' if hwp_available else '❌ HWP: Windows + 한글 설치 필요'}
        </p>

        <!-- 주요 지표 카드 -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">총 사업체수</div>
                <div class="metric-value">{total_businesses:,.0f}</div>
                <div class="metric-unit">개</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">총 종사자수</div>
                <div class="metric-value">{total_employees:,.0f}</div>
                <div class="metric-unit">명</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">평균 HHI (산업 다양성)</div>
                <div class="metric-value">{avg_hhi:.1f}</div>
                <div class="metric-unit">낮을수록 다양함</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">평균 1인당 매출액</div>
                <div class="metric-value">{avg_sales_per_employee:.1f}</div>
                <div class="metric-unit">백만원 (생산성 지표)</div>
            </div>
        </div>

        <!-- 지역별 사업체 현황 -->
        <div class="chart-container">
            <h2 class="chart-title">{region_label} 사업체 현황</h2>
            <div id="chart-region"></div>
        </div>

        <!-- 분기별 시계열 추이 -->
        <div class="chart-container">
            <h2 class="chart-title">분기별 시계열 추이</h2>
            <div id="chart-timeseries"></div>
        </div>

        <!-- 인구 대비 사업체 밀도 -->
        <div class="chart-container">
            <h2 class="chart-title">시도별 인구 천명당 사업체수</h2>
            <div id="chart-density"></div>
        </div>

        <!-- HHI 및 1인당 매출액 차트 -->
        <div class="chart-container">
            <h2 class="chart-title">HHI (산업 다양성 지수)</h2>
            <div id="chart-hhi"></div>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">1인당 매출액 (생산성 지표)</h2>
            <div id="chart-sales"></div>
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

        // 지역별 사업체 현황 차트
        var trace_region = {{
            x: {df_aggregated['지역명'].tolist()},
            y: {df_aggregated['총사업체수'].tolist()},
            type: 'bar',
            marker: {{
                color: {df_aggregated['총사업체수'].tolist()},
                colorscale: 'Viridis',
                showscale: false
            }},
            text: {[f"{int(x):,}" for x in df_aggregated['총사업체수'].tolist()]},
            textposition: 'outside',
            hovertemplate: '<b>%{{x}}</b><br>사업체수: %{{y:,.0f}}개<extra></extra>'
        }};

        var layout_region = {{
            xaxis: {{ title: '지역명', tickangle: -45 }},
            yaxis: {{ title: '사업체수 (개)' }},
            margin: {{ t: 10, b: 100, l: 60, r: 30 }},
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#f8f9fa',
            font: {{ family: 'Malgun Gothic' }},
            height: 500
        }};

        Plotly.newPlot('chart-region', [trace_region], layout_region, {{responsive: true}});

        // 분기별 시계열 추이 차트
        var trace_ts1 = {{
            x: {df_ts['분기'].tolist()},
            y: {df_ts['총사업체수'].tolist()},
            type: 'scatter',
            mode: 'lines+markers',
            name: '총 사업체수',
            line: {{ color: '#667eea', width: 3 }},
            marker: {{ size: 8 }},
            yaxis: 'y1',
            hovertemplate: '<b>%{{x}}</b><br>사업체수: %{{y:,.0f}}개<extra></extra>'
        }};

        var trace_ts2 = {{
            x: {df_ts['분기'].tolist()},
            y: {df_ts['총종사자수'].tolist()},
            type: 'scatter',
            mode: 'lines+markers',
            name: '총 종사자수',
            line: {{ color: '#764ba2', width: 3 }},
            marker: {{ size: 8 }},
            yaxis: 'y2',
            hovertemplate: '<b>%{{x}}</b><br>종사자수: %{{y:,.0f}}명<extra></extra>'
        }};

        var layout_ts = {{
            xaxis: {{ title: '분기', tickangle: -45 }},
            yaxis: {{
                title: '사업체수 (개)',
                titlefont: {{ color: '#667eea' }},
                tickfont: {{ color: '#667eea' }}
            }},
            yaxis2: {{
                title: '종사자수 (명)',
                titlefont: {{ color: '#764ba2' }},
                tickfont: {{ color: '#764ba2' }},
                overlaying: 'y',
                side: 'right'
            }},
            margin: {{ t: 30, b: 80, l: 80, r: 80 }},
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#f8f9fa',
            font: {{ family: 'Malgun Gothic' }},
            legend: {{ x: 0.5, y: 1.15, xanchor: 'center', orientation: 'h' }},
            height: 450
        }};

        Plotly.newPlot('chart-timeseries', [trace_ts1, trace_ts2], layout_ts, {{responsive: true}});

        // 인구 천명당 사업체수 차트
        var trace_density = {{
            y: {df_pop_biz['시도명'].tolist()},
            x: {df_pop_biz['인구천명당사업체수'].tolist()},
            type: 'bar',
            orientation: 'h',
            marker: {{
                color: {df_pop_biz['인구천명당사업체수'].tolist()},
                colorscale: 'Blues',
                showscale: false,
                reversescale: true
            }},
            text: {[f"{x:.2f}" for x in df_pop_biz['인구천명당사업체수'].tolist()]},
            textposition: 'outside',
            hovertemplate: '<b>%{{y}}</b><br>인구 천명당: %{{x:.2f}}개<br>총인구: %{{customdata[0]:,.0f}}명<br>사업체수: %{{customdata[1]:,.0f}}개<extra></extra>',
            customdata: {[[row['총인구'], row['사업체수']] for _, row in df_pop_biz.iterrows()]}
        }};

        var layout_density = {{
            xaxis: {{ title: '인구 천명당 사업체수 (개)' }},
            yaxis: {{ title: '', automargin: true, autorange: 'reversed' }},
            margin: {{ t: 10, b: 60, l: 120, r: 80 }},
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#f8f9fa',
            font: {{ family: 'Malgun Gothic' }},
            height: 600
        }};

        Plotly.newPlot('chart-density', [trace_density], layout_density, {{responsive: true}});

        // HHI 차트
        var trace_hhi = {{
            x: {df_aggregated['지역명'].head(10).tolist()},
            y: {df_aggregated['HHI'].head(10).tolist()},
            type: 'bar',
            marker: {{ color: '#3498db' }},
            text: {[f"{x:.0f}" for x in df_aggregated['HHI'].head(10).tolist()]},
            textposition: 'outside',
            hovertemplate: '<b>%{{x}}</b><br>HHI: %{{y:.2f}}<extra></extra>'
        }};

        var layout_hhi = {{
            xaxis: {{ title: '지역명', tickangle: -45 }},
            yaxis: {{ title: 'HHI (낮을수록 다양함)' }},
            margin: {{ t: 10, b: 100, l: 60, r: 30 }},
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#f8f9fa',
            font: {{ family: 'Malgun Gothic' }},
            height: 400
        }};

        Plotly.newPlot('chart-hhi', [trace_hhi], layout_hhi, {{responsive: true}});

        // 1인당 매출액 차트
        var trace_sales = {{
            x: {df_aggregated['지역명'].head(10).tolist()},
            y: {df_aggregated['1인당매출액'].head(10).tolist()},
            type: 'bar',
            marker: {{ color: '#2ecc71' }},
            text: {[f"{x:.1f}" if pd.notna(x) else "N/A" for x in df_aggregated['1인당매출액'].head(10).tolist()]},
            textposition: 'outside',
            hovertemplate: '<b>%{{x}}</b><br>1인당 매출액: %{{y:.2f}}백만원<extra></extra>'
        }};

        var layout_sales = {{
            xaxis: {{ title: '지역명', tickangle: -45 }},
            yaxis: {{ title: '1인당 매출액 (백만원)' }},
            margin: {{ t: 10, b: 100, l: 60, r: 30 }},
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#f8f9fa',
            font: {{ family: 'Malgun Gothic' }},
            height: 400
        }};

        Plotly.newPlot('chart-sales', [trace_sales], layout_sales, {{responsive: true}});
    </script>
</body>
</html>
"""

    return html
