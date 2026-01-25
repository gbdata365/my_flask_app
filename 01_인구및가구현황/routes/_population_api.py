# -*- coding: utf-8 -*-
"""
인구통계 분석 Flask Blueprint 모듈
==================================

이 모듈은 인구통계 데이터를 조회하고 시각화하는 Flask Blueprint를 제공합니다.
대시보드 페이지와 다양한 API 엔드포인트를 포함합니다.

주요 기능:
    1. 인구 데이터 조회 (시도/시군구/읍면동 수준)
    2. 1인세대 데이터 조회 및 비율 계산
    3. 필터링 (기준시기, 시도, 시군구)
    4. Chart.js용 차트 데이터 API

Blueprint 등록:
    >>> from routes.population_routes import population_bp
    >>> app.register_blueprint(population_bp, url_prefix="/01_population")

API 엔드포인트:
    - GET /                      : 대시보드 메인 페이지
    - GET /api/sigungu           : 시군구 목록 조회
    - GET /api/summary           : 요약 통계
    - GET /api/sido_data         : 시도별 데이터
    - GET /api/sigungu_data      : 시군구별 데이터
    - GET /api/emd_data          : 읍면동별 데이터
    - GET /api/chart/sido_pop    : 시도별 인구 차트
    - GET /api/chart/single_ratio: 1인세대 비율 차트
    - GET /api/chart/gender_pie  : 성별 인구 파이차트
    - GET /api/chart/household_pie: 세대 구성 파이차트
    - GET /api/chart/sigungu_top10: 시군구 Top10 차트

데이터베이스 테이블:
    - fact_population_basic: 기본 인구통계 (인구, 세대, 내외국인)
    - fact_single_household: 1인세대 데이터
    - dim_admin_area: 행정구역 (시도, 시군구, 읍면동)

Author: Claude AI Agent
Created: 2024-12-18
"""

from flask import Blueprint, render_template, request, jsonify
import pandas as pd
import os
import sys
from pathlib import Path

# 상위 디렉토리의 module 패키지를 import하기 위해 경로 추가
# 예: 01_population/routes/ → 01_claude_project/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_connection
from module.menu_generator import MenuGenerator

# 01_population 폴더 경로 (메뉴 생성용)
POP_BASE = Path(__file__).parent.parent

# =============================================================================
# Blueprint 생성
# =============================================================================

population_bp = Blueprint(
    'population',                       # Blueprint 이름 (url_for에서 사용)
    __name__,
    template_folder='../templates',     # 템플릿 폴더 (상대 경로)
    static_folder='../images',          # 정적 파일 폴더
    static_url_path='/population/images'  # 정적 파일 URL 경로
)
"""Blueprint: 인구통계 Flask Blueprint 인스턴스

이 Blueprint는 다음 기능을 제공합니다:
- 인구통계 대시보드 페이지
- 데이터 조회 REST API
- Chart.js용 차트 데이터 API

등록 예시:
    >>> app.register_blueprint(population_bp, url_prefix="/01_population")
"""


# =============================================================================
# 헬퍼 함수 (데이터 조회)
# =============================================================================

def get_filter_options():
    """
    대시보드 필터 옵션(기준시기, 시도)을 조회합니다.

    데이터베이스에서 사용 가능한 기준시기(base_ym)와
    시도(sido_nm) 목록을 조회하여 반환합니다.

    Returns:
        dict: 필터 옵션 딕셔너리
            - base_ym_list (list[str]): 기준시기 목록 (내림차순)
                예: ['202411', '202410', '202409', ...]
            - sido_list (list[str]): 시도명 목록 (행정코드 순)
                예: ['서울특별시', '부산광역시', ...]

    Examples:
        >>> options = get_filter_options()
        >>> print(options['base_ym_list'][:3])
        ['202411', '202410', '202409']
        >>> print(options['sido_list'][:3])
        ['서울특별시', '부산광역시', '대구광역시']

    Note:
        - base_ym_list는 최신순(내림차순) 정렬
        - sido_list는 행정코드(admin_code) 기준 정렬
    """
    conn = get_db_connection()
    try:
        # 기준시기 목록 조회 (최신순 정렬) - date를 YYYYMM 문자열로 변환
        base_ym_df = pd.read_sql("""
            SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as base_ym
            FROM fact_population_basic
            ORDER BY base_ym DESC
        """, conn)

        # 시도 목록 조회 (행정코드 순 정렬)
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


def get_sigungu_list(sido_nm):
    """
    특정 시도의 시군구 목록을 조회합니다.

    시도명을 기준으로 해당 시도에 속한 시군구 목록을 반환합니다.
    필터 드롭다운의 캐스케이딩(연동)에 사용됩니다.

    Args:
        sido_nm (str): 시도명.
            예: '서울특별시', '경기도'

    Returns:
        list[str]: 시군구명 목록 (행정코드 순)
            예: ['종로구', '중구', '용산구', ...]

    Examples:
        >>> sigungu_list = get_sigungu_list('서울특별시')
        >>> print(sigungu_list[:3])
        ['종로구', '중구', '용산구']

        >>> sigungu_list = get_sigungu_list('경기도')
        >>> print(len(sigungu_list))  # 31개 시군

    Note:
        - 행정코드(admin_code) 기준 정렬
        - sigungu_nm이 NULL인 행은 제외
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql("""
            SELECT DISTINCT sigungu_nm, MIN(admin_code) as sort_key
            FROM dim_admin_area
            WHERE sido_nm = %s AND sigungu_nm IS NOT NULL
            GROUP BY sigungu_nm
            ORDER BY sort_key
        """, conn, params=(sido_nm,))
        return df['sigungu_nm'].tolist()
    finally:
        conn.close()


def load_population_data(base_ym=None, sido=None, sigungu=None):
    """
    기본 인구 데이터를 조회합니다.

    fact_population_basic 테이블에서 인구 데이터를 조회하고,
    dim_admin_area와 조인하여 행정구역 정보를 포함합니다.

    Args:
        base_ym (str, optional): 기준시기 필터.
            예: '202411'
            None이면 전체 기간 조회

        sido (str, optional): 시도 필터.
            예: '서울특별시'
            None이면 전국 조회

        sigungu (str, optional): 시군구 필터.
            예: '강남구'
            None이면 해당 시도 전체 조회

    Returns:
        pd.DataFrame: 인구 데이터프레임
            컬럼:
            - base_ym (str): 기준시기 ('202411')
            - sido_nm (str): 시도명 ('서울특별시')
            - sigungu_nm (str): 시군구명 ('강남구')
            - admin_nm (str): 읍면동명 ('역삼1동')
            - total_pop (int): 총인구
            - male_pop (int): 남자인구
            - female_pop (int): 여자인구
            - household_cnt (int): 세대수
            - korean_pop (int): 내국인인구
            - foreign_pop (int): 외국인인구

    Examples:
        >>> # 전국 전체 조회
        >>> df = load_population_data()
        >>> print(len(df))  # 수만 건

        >>> # 특정 시기, 특정 시도
        >>> df = load_population_data('202411', '서울특별시')
        >>> print(df['sido_nm'].unique())  # ['서울특별시']

        >>> # 특정 시군구까지 필터
        >>> df = load_population_data('202411', '서울특별시', '강남구')
        >>> print(df['sigungu_nm'].unique())  # ['강남구']

    Note:
        - 파라미터 바인딩(%s)으로 SQL 인젝션 방지
        - 결과는 admin_code 순으로 정렬
    """
    conn = get_db_connection()
    try:
        # 기본 쿼리 (fact_population_basic + dim_admin_area 조인)
        query = """
            SELECT
                d.admin_code,
                p.base_ym,
                d.sido_nm,
                d.sigungu_nm,
                d.eupmyeondong_nm,
                p.total_pop,
                p.male_pop,
                p.female_pop,
                p.household_cnt
            FROM fact_population_basic p
            JOIN dim_admin_area d ON p.admin_code = d.admin_code
            WHERE 1=1
        """
        params = []

        # 동적 필터 추가 (base_ym은 YYYYMM 문자열을 date로 변환하여 비교)
        if base_ym:
            query += " AND TO_CHAR(p.base_ym, 'YYYYMM') = %s"
            params.append(base_ym)
        if sido:
            query += " AND d.sido_nm = %s"
            params.append(sido)
        if sigungu:
            query += " AND d.sigungu_nm = %s"
            params.append(sigungu)

        # 정렬
        query += " ORDER BY d.admin_code"

        # 쿼리 실행
        df = pd.read_sql(query, conn, params=params if params else None)
        return df
    finally:
        conn.close()


def load_single_household_data(base_ym=None, sido=None, sigungu=None):
    """
    1인세대 데이터를 조회합니다.

    fact_single_household 테이블에서 1인세대 수를 조회하고,
    dim_admin_area와 조인하여 행정구역 정보를 포함합니다.

    Args:
        base_ym (str, optional): 기준시기 필터 ('202411')
        sido (str, optional): 시도 필터 ('서울특별시')
        sigungu (str, optional): 시군구 필터 ('강남구')

    Returns:
        pd.DataFrame: 1인세대 데이터프레임
            컬럼:
            - base_ym (str): 기준시기
            - sido_nm (str): 시도명
            - sigungu_nm (str): 시군구명
            - admin_nm (str): 읍면동명
            - single_household_cnt (int): 1인세대수

    Examples:
        >>> hh_df = load_single_household_data('202411', '서울특별시')
        >>> print(hh_df['single_household_cnt'].sum())
        1500000  # 서울시 1인세대 수 (예시)

    Note:
        - 인구 데이터와 별도 테이블이므로 조인 시 주의
        - 읍면동 단위로 데이터 제공
    """
    conn = get_db_connection()
    try:
        query = """
            SELECT
                d.admin_code,
                s.base_ym,
                d.sido_nm,
                d.sigungu_nm,
                d.eupmyeondong_nm,
                s.total_cnt as single_household_cnt
            FROM fact_single_household s
            JOIN dim_admin_area d ON s.admin_code = d.admin_code
            WHERE 1=1
        """
        params = []

        # base_ym은 YYYYMM 문자열을 date로 변환하여 비교
        if base_ym:
            query += " AND TO_CHAR(s.base_ym, 'YYYYMM') = %s"
            params.append(base_ym)
        if sido:
            query += " AND d.sido_nm = %s"
            params.append(sido)
        if sigungu:
            query += " AND d.sigungu_nm = %s"
            params.append(sigungu)

        query += " ORDER BY d.admin_code"

        df = pd.read_sql(query, conn, params=params if params else None)
        return df
    finally:
        conn.close()


def aggregate_sido(df):
    """
    데이터프레임을 시도별로 집계합니다.

    읍면동 수준 데이터를 시도 수준으로 합산합니다.
    총인구, 남녀인구, 세대수를 집계하고 시도코드(admin_code 앞 2자리) 순으로 정렬합니다.

    Args:
        df (pd.DataFrame): 읍면동 수준 인구 데이터프레임.
            sido_nm, admin_code, total_pop, male_pop, female_pop, household_cnt 컬럼 필요

    Returns:
        pd.DataFrame: 시도별 집계 데이터프레임 (시도코드 오름차순)
            컬럼: sido_nm, sido_code, total_pop, male_pop, female_pop, household_cnt

    Examples:
        >>> pop_df = load_population_data('202411')
        >>> sido_df = aggregate_sido(pop_df)
        >>> print(sido_df.head())
        #         sido_nm sido_code  total_pop  ...
        # 0    서울특별시        11   9500000  ...
        # 1    부산광역시        26   3300000  ...
    """
    result = df.groupby('sido_nm').agg({
        'admin_code': 'first',
        'total_pop': 'sum',
        'male_pop': 'sum',
        'female_pop': 'sum',
        'household_cnt': 'sum'
    }).reset_index()

    # 시도코드 추출 및 정렬
    result['sido_code'] = result['admin_code'].str[:2]
    result = result.sort_values('sido_code')
    return result


def add_sigungu_consolidated(df):
    """
    시군구통합 코드를 추가합니다.

    행정동코드 5자리(시군구코드) 기준으로:
    - 5번째 자리가 0이 아니면: 4자리로 그룹화 (구가 있는 시 → 시로 통합)
    - 5번째 자리가 0이면: 5자리 유지 (단독 시/군/구)

    예시:
    - 41111 (수원시 장안구) → 4111 (5번째 자리 '1' != 0)
    - 41113 (수원시 권선구) → 4111 (5번째 자리 '3' != 0)
    - 41820 (가평군) → 41820 (5번째 자리 '0' == 0)

    Args:
        df (pd.DataFrame): admin_code 컬럼이 있는 데이터프레임

    Returns:
        pd.DataFrame: sigungu_code 컬럼이 추가된 데이터프레임
    """
    df = df.copy()
    # 5번째 자리가 0이 아니면 4자리, 0이면 5자리
    df['sigungu_code'] = df['admin_code'].apply(
        lambda x: x[:4] if len(str(x)) >= 5 and str(x)[4] != '0' else str(x)[:5]
    )
    return df


def get_sigungu_consolidated_name(df):
    """
    시군구통합명을 생성합니다.

    sigungu_nm에서 구 이름을 제거하여 통합된 시군구명을 생성합니다.
    sigungu_code가 4자리인 경우(통합 대상)만 구 이름을 제거합니다.

    Args:
        df (pd.DataFrame): sigungu_nm, sigungu_code 컬럼이 있는 데이터프레임

    Returns:
        pd.DataFrame: sigungu_consolidated_nm 컬럼이 추가된 데이터프레임
    """
    import re
    df = df.copy()

    # 구 이름 패턴 (일반시의 구)
    gu_pattern = (
        r'\s*(장안구|권선구|팔달구|영통구|'  # 수원시
        r'수정구|중원구|분당구|'              # 성남시
        r'만안구|동안구|'                    # 안양시
        r'부평구|계양구|남동구|연수구|중구|동구|미추홀구|서구|강화군|옹진군|'  # 인천은 광역시라 제외하지만 참고용
        r'덕양구|일산동구|일산서구|'          # 고양시
        r'처인구|기흥구|수지구|'              # 용인시
        r'상당구|서원구|청원구|흥덕구|'        # 청주시
        r'동구|서구|유성구|대덕구|중구|'       # 대전은 광역시라 제외
        r'동남구|서북구|'                    # 천안시
        r'북구|남구|'                        # 포항시
        r'원미구|소사구|오정구)$'             # 부천시
    )

    def consolidate_name(row):
        if 'sigungu_code' in row and len(str(row['sigungu_code'])) == 4:
            return re.sub(gu_pattern, '', str(row['sigungu_nm'])).strip()
        return row['sigungu_nm']

    df['sigungu_consolidated_nm'] = df.apply(consolidate_name, axis=1)
    return df


def aggregate_sigungu(df, sido=None, consolidated=False):
    """
    데이터프레임을 시군구별로 집계합니다.

    읍면동 수준 데이터를 시군구 수준으로 합산합니다.
    특정 시도를 지정하면 해당 시도만 집계합니다.

    Args:
        df (pd.DataFrame): 읍면동 수준 인구 데이터프레임

        sido (str, optional): 시도 필터.
            지정하면 해당 시도의 시군구만 집계.
            None이면 전국 시군구 집계.

        consolidated (bool, optional): 시군구통합 여부 (기본: False)
            - True: admin_code 앞 4자리로 그룹화 (수원시 장안구+권선구+... → 수원시)
            - False: admin_code 앞 5자리로 그룹화 (기존 방식)

    Returns:
        pd.DataFrame: 시군구별 집계 데이터프레임
            컬럼: sigungu_code, sido_nm, sigungu_nm, total_pop, male_pop, female_pop, household_cnt
            (consolidated=True일 경우 sigungu_consolidated_nm 추가)

    Examples:
        >>> pop_df = load_population_data('202411', '경기도')
        >>> sigungu_df = aggregate_sigungu(pop_df, '경기도', consolidated=True)
        # 수원시가 한 행으로 통합됨
    """
    if sido:
        df = df[df['sido_nm'] == sido]

    if consolidated and 'admin_code' in df.columns:
        # 시군구통합 적용
        df = add_sigungu_consolidated(df)
        df = get_sigungu_consolidated_name(df)

        result = df.groupby(['sido_nm', 'sigungu_code']).agg({
            'sigungu_consolidated_nm': 'first',
            'admin_code': 'first',
            'total_pop': 'sum',
            'male_pop': 'sum',
            'female_pop': 'sum',
            'household_cnt': 'sum'
        }).reset_index()

        # 행정코드 오름차순 정렬
        result = result.sort_values('sigungu_code')
        result['sigungu_nm'] = result['sigungu_consolidated_nm']
        return result
    else:
        # 기존 방식 (5자리)
        result = df.groupby(['sido_nm', 'sigungu_nm']).agg({
            'admin_code': 'first',
            'total_pop': 'sum',
            'male_pop': 'sum',
            'female_pop': 'sum',
            'household_cnt': 'sum'
        }).reset_index()

        # 행정코드 오름차순 정렬
        result['sigungu_code'] = result['admin_code'].str[:5]
        result = result.sort_values('sigungu_code')
        return result


# =============================================================================
# 라우트 핸들러 (페이지)
# =============================================================================

@population_bp.route('/')
def index():
    """
    인구통계 대시보드 메인 페이지를 렌더링합니다.

    필터 옵션(기준시기, 시도)을 조회하여 템플릿에 전달합니다.
    사용자는 필터를 선택하여 데이터를 조회할 수 있습니다.

    Returns:
        str: 렌더링된 population_dashboard.html

    Route:
        GET /01_population/

    Examples:
        브라우저에서 http://localhost:5000/01_population/ 접속
    """
    filters = get_filter_options()
    menu_items = MenuGenerator.get_category_menu_items(POP_BASE)
    return render_template('population_dashboard.html',
                          filters=filters,
                          menu_items=menu_items,
                          title='인구통계 분석')


# =============================================================================
# API 핸들러 (데이터 조회)
# =============================================================================

@population_bp.route('/api/sigungu')
def api_sigungu():
    """
    시군구 목록 API.

    시도명을 받아 해당 시도의 시군구 목록을 반환합니다.
    필터 드롭다운의 캐스케이딩(시도→시군구)에 사용됩니다.

    Query Parameters:
        sido (str, required): 시도명. 예: '서울특별시'

    Returns:
        JSON: 시군구 목록
            - success (bool): 성공 여부
            - data (list[str]): 시군구명 목록 (성공 시)
            - error (str): 에러 메시지 (실패 시)

    Route:
        GET /01_population/api/sigungu?sido=서울특별시

    Examples:
        >>> response = requests.get('/01_population/api/sigungu?sido=서울특별시')
        >>> print(response.json())
        {'success': True, 'data': ['종로구', '중구', '용산구', ...]}
    """
    sido = request.args.get('sido')
    if not sido:
        return jsonify({'success': False, 'error': '시도를 선택하세요'})

    sigungu_list = get_sigungu_list(sido)
    return jsonify({'success': True, 'data': sigungu_list})


@population_bp.route('/api/summary')
def api_summary():
    """
    요약 통계 API.

    선택된 필터에 따른 요약 통계를 반환합니다.
    대시보드 상단의 요약 카드에 표시됩니다.

    Query Parameters:
        base_ym (str, optional): 기준시기 ('202411')
        sido (str, optional): 시도명 ('서울특별시')
        sigungu (str, optional): 시군구명 ('강남구')

    Returns:
        JSON: 요약 통계
            - success (bool): 성공 여부
            - data (dict): 통계 데이터 (성공 시)
                - total_pop (int): 총인구
                - male_pop (int): 남자인구
                - female_pop (int): 여자인구
                - household_cnt (int): 세대수
                - single_household_cnt (int): 1인세대수
                - single_ratio (float): 1인세대 비율(%)
                - sex_ratio (float): 성비 (여자 100명당 남자 수)
                - area_count (int): 읍면동 수
            - error (str): 에러 메시지 (실패 시)

    Route:
        GET /01_population/api/summary?base_ym=202411&sido=서울특별시

    Examples:
        >>> response = requests.get('/01_population/api/summary?base_ym=202411')
        >>> data = response.json()['data']
        >>> print(f"총인구: {data['total_pop']:,}명")
        총인구: 51,000,000명
    """
    # 쿼리 파라미터 추출
    base_ym = request.args.get('base_ym')
    sido = request.args.get('sido')
    sigungu = request.args.get('sigungu')

    # 데이터 로드
    pop_df = load_population_data(base_ym, sido, sigungu)
    hh_df = load_single_household_data(base_ym, sido, sigungu)

    if pop_df.empty:
        return jsonify({'success': False, 'error': '데이터가 없습니다'})

    # 전체 요약 계산
    summary = {
        'total_pop': int(pop_df['total_pop'].sum()),
        'male_pop': int(pop_df['male_pop'].sum()),
        'female_pop': int(pop_df['female_pop'].sum()),
        'household_cnt': int(pop_df['household_cnt'].sum()),
        'single_household_cnt': int(hh_df['single_household_cnt'].sum()) if not hh_df.empty else 0,
        'area_count': len(pop_df),
    }

    # 1인세대 비율 계산
    if summary['household_cnt'] > 0:
        summary['single_ratio'] = round(summary['single_household_cnt'] / summary['household_cnt'] * 100, 1)
    else:
        summary['single_ratio'] = 0

    # 성비 계산 (여자 100명당 남자 수)
    if summary['female_pop'] > 0:
        summary['sex_ratio'] = round(summary['male_pop'] / summary['female_pop'] * 100, 1)
    else:
        summary['sex_ratio'] = 0

    return jsonify({'success': True, 'data': summary})


@population_bp.route('/api/sido_data')
def api_sido_data():
    """
    시도별 데이터 API.

    전국 17개 시도별 인구 및 세대 데이터를 반환합니다.
    시도별 테이블에 표시됩니다.

    Query Parameters:
        base_ym (str, optional): 기준시기 ('202411')

    Returns:
        JSON: 시도별 데이터
            - success (bool): 성공 여부
            - data (list[dict]): 시도별 데이터 목록
                각 항목: sido_nm, total_pop, total_pop_man, male_pop,
                        female_pop, household_cnt, single_household_cnt, single_ratio
            - columns (list[str]): 컬럼 순서

    Route:
        GET /01_population/api/sido_data?base_ym=202411

    Examples:
        >>> response = requests.get('/01_population/api/sido_data?base_ym=202411')
        >>> data = response.json()['data']
        >>> for row in data[:3]:
        ...     print(f"{row['sido_nm']}: {row['total_pop_man']}만명")
        서울특별시: 950만명
        경기도: 1350만명
    """
    base_ym = request.args.get('base_ym')

    # 데이터 로드
    pop_df = load_population_data(base_ym)
    hh_df = load_single_household_data(base_ym)

    # 시도별 집계
    sido_pop = aggregate_sido(pop_df)
    sido_hh = hh_df.groupby('sido_nm')['single_household_cnt'].sum().reset_index()

    # 병합
    result = sido_pop.merge(sido_hh, on='sido_nm', how='left').fillna(0)
    result['single_household_cnt'] = result['single_household_cnt'].astype(int)

    # 1인세대 비율 계산
    result['single_ratio'] = (result['single_household_cnt'] / result['household_cnt'] * 100).round(1)

    # 만 단위 변환 (표시용)
    result['total_pop_man'] = (result['total_pop'] / 10000).round(1)

    return jsonify({
        'success': True,
        'data': result.to_dict('records'),
        'columns': ['sido_nm', 'total_pop', 'total_pop_man', 'male_pop', 'female_pop',
                   'household_cnt', 'single_household_cnt', 'single_ratio']
    })


@population_bp.route('/api/sigungu_data')
def api_sigungu_data():
    """
    시군구별 데이터 API.

    특정 시도의 시군구별 인구 및 세대 데이터를 반환합니다.

    Query Parameters:
        base_ym (str, optional): 기준시기 ('202411')
        sido (str, required): 시도명 ('서울특별시')
        consolidated (str, optional): 시군구통합 여부 ('true' 또는 'false', 기본: 'true')
            - 'true': admin_code 앞 4자리로 그룹화 (수원시 장안구+권선구+... → 수원시)
            - 'false': admin_code 앞 5자리로 그룹화 (기존 방식)

    Returns:
        JSON: 시군구별 데이터
            - success (bool): 성공 여부
            - data (list[dict]): 시군구별 데이터 목록 (행정코드 오름차순)
            - columns (list[str]): 컬럼 순서
            - error (str): 에러 메시지 (실패 시)

    Route:
        GET /01_population/api/sigungu_data?base_ym=202411&sido=경기도&consolidated=true

    Note:
        sido 파라미터는 필수입니다.
    """
    base_ym = request.args.get('base_ym')
    sido = request.args.get('sido')
    consolidated = request.args.get('consolidated', 'true').lower() == 'true'

    if not sido:
        return jsonify({'success': False, 'error': '시도를 선택하세요'})

    # 데이터 로드
    pop_df = load_population_data(base_ym, sido)
    hh_df = load_single_household_data(base_ym, sido)

    # 시군구별 집계 (시군구통합 옵션 적용)
    sigungu_pop = aggregate_sigungu(pop_df, sido, consolidated=consolidated)

    # 1인세대 집계 (시군구통합 옵션 적용)
    if consolidated and 'admin_code' in hh_df.columns:
        hh_df = add_sigungu_consolidated(hh_df)
        sigungu_hh = hh_df.groupby('sigungu_code')['single_household_cnt'].sum().reset_index()
        result = sigungu_pop.merge(sigungu_hh, on='sigungu_code', how='left').fillna(0)
    else:
        sigungu_hh = hh_df.groupby(['sido_nm', 'sigungu_nm'])['single_household_cnt'].sum().reset_index()
        result = sigungu_pop.merge(sigungu_hh, on=['sido_nm', 'sigungu_nm'], how='left').fillna(0)

    result['single_household_cnt'] = result['single_household_cnt'].astype(int)

    # 1인세대 비율 계산
    result['single_ratio'] = (result['single_household_cnt'] / result['household_cnt'] * 100).round(1)

    # 만 단위 변환
    result['total_pop_man'] = (result['total_pop'] / 10000).round(1)

    # 행정코드 오름차순 정렬 (이미 aggregate_sigungu에서 정렬됨)
    result = result.sort_values('sigungu_code')

    return jsonify({
        'success': True,
        'data': result.to_dict('records'),
        'columns': ['sigungu_nm', 'sigungu_code', 'total_pop', 'total_pop_man', 'male_pop', 'female_pop',
                   'household_cnt', 'single_household_cnt', 'single_ratio']
    })


@population_bp.route('/api/emd_data')
def api_emd_data():
    """
    읍면동별 데이터 API.

    선택된 지역의 읍면동별 인구 및 세대 데이터를 반환합니다.

    Query Parameters:
        base_ym (str, optional): 기준시기 ('202411')
        sido (str, optional): 시도명 ('서울특별시')
        sigungu (str, optional): 시군구명 ('강남구')

    Returns:
        JSON: 읍면동별 데이터
            - success (bool): 성공 여부
            - data (list[dict]): 읍면동별 데이터 목록
            - columns (list[str]): 컬럼 순서
            - error (str): 에러 메시지 (실패 시)

    Route:
        GET /01_population/api/emd_data?base_ym=202411&sido=서울특별시&sigungu=강남구

    Note:
        데이터가 많을 수 있으므로 가급적 시군구까지 필터링 권장
    """
    base_ym = request.args.get('base_ym')
    sido = request.args.get('sido')
    sigungu = request.args.get('sigungu')

    # 데이터 로드
    pop_df = load_population_data(base_ym, sido, sigungu)
    hh_df = load_single_household_data(base_ym, sido, sigungu)

    if pop_df.empty:
        return jsonify({'success': False, 'error': '데이터가 없습니다'})

    # 인구 데이터와 1인세대 데이터 병합
    result = pop_df.merge(
        hh_df[['base_ym', 'eupmyeondong_nm', 'single_household_cnt']],
        on=['base_ym', 'eupmyeondong_nm'],
        how='left'
    ).fillna(0)

    # 데이터 타입 변환 및 비율 계산
    result['single_household_cnt'] = result['single_household_cnt'].astype(int)
    result['single_ratio'] = (result['single_household_cnt'] / result['household_cnt'] * 100).round(1)
    result['total_pop_man'] = (result['total_pop'] / 10000).round(2)

    return jsonify({
        'success': True,
        'data': result.to_dict('records'),
        'columns': ['sido_nm', 'sigungu_nm', 'eupmyeondong_nm', 'total_pop', 'total_pop_man',
                   'male_pop', 'female_pop', 'household_cnt', 'single_household_cnt', 'single_ratio']
    })


# =============================================================================
# API 핸들러 (차트 데이터)
# =============================================================================

@population_bp.route('/api/chart/sido_pop')
def api_chart_sido_pop():
    """
    시도별 성별 인구 차트 데이터 API.

    17개 시도별 남녀 인구를 막대 차트 형태로 반환합니다.
    Chart.js의 Stacked Bar Chart에 사용됩니다.

    Query Parameters:
        base_ym (str, optional): 기준시기 ('202411')

    Returns:
        JSON: Chart.js 데이터 포맷
            - success (bool): 성공 여부
            - labels (list[str]): 시도명 목록 (X축)
            - datasets (list[dict]): 데이터셋 (남자, 여자)
                각 데이터셋: label, data, backgroundColor, borderColor, borderWidth

    Route:
        GET /01_population/api/chart/sido_pop?base_ym=202411

    Note:
        인구 데이터는 만 단위로 변환하여 반환
    """
    base_ym = request.args.get('base_ym')

    pop_df = load_population_data(base_ym)
    sido_pop = aggregate_sido(pop_df)

    # 인구 많은 순 정렬
    sido_pop = sido_pop.sort_values('total_pop', ascending=False)

    return jsonify({
        'success': True,
        'labels': sido_pop['sido_nm'].tolist(),
        'datasets': [
            {
                'label': '남자',
                'data': (sido_pop['male_pop'] / 10000).round(1).tolist(),
                'backgroundColor': 'rgba(74, 144, 217, 0.7)',  # 파란색
                'borderColor': 'rgba(74, 144, 217, 1)',
                'borderWidth': 1
            },
            {
                'label': '여자',
                'data': (sido_pop['female_pop'] / 10000).round(1).tolist(),
                'backgroundColor': 'rgba(229, 115, 115, 0.7)',  # 빨간색
                'borderColor': 'rgba(229, 115, 115, 1)',
                'borderWidth': 1
            }
        ]
    })


@population_bp.route('/api/chart/single_ratio')
def api_chart_single_ratio():
    """
    시도별 1인세대 비율 차트 데이터 API.

    17개 시도별 1인세대 비율을 막대 차트 형태로 반환합니다.

    Query Parameters:
        base_ym (str, optional): 기준시기 ('202411')

    Returns:
        JSON: Chart.js 데이터 포맷
            - success (bool): 성공 여부
            - labels (list[str]): 시도명 목록 (X축)
            - datasets (list[dict]): 1인세대 비율 데이터

    Route:
        GET /01_population/api/chart/single_ratio?base_ym=202411

    Note:
        1인세대 비율 높은 순으로 정렬
    """
    base_ym = request.args.get('base_ym')

    pop_df = load_population_data(base_ym)
    hh_df = load_single_household_data(base_ym)

    sido_pop = aggregate_sido(pop_df)
    sido_hh = hh_df.groupby('sido_nm')['single_household_cnt'].sum().reset_index()

    result = sido_pop.merge(sido_hh, on='sido_nm', how='left').fillna(0)
    result['single_ratio'] = (result['single_household_cnt'] / result['household_cnt'] * 100).round(1)

    # 1인세대 비율 높은 순 정렬
    result = result.sort_values('single_ratio', ascending=False)

    return jsonify({
        'success': True,
        'labels': result['sido_nm'].tolist(),
        'datasets': [{
            'label': '1인세대 비율(%)',
            'data': result['single_ratio'].tolist(),
            'backgroundColor': 'rgba(156, 39, 176, 0.7)',  # 보라색
            'borderColor': 'rgba(156, 39, 176, 1)',
            'borderWidth': 1
        }]
    })


@population_bp.route('/api/chart/gender_pie')
def api_chart_gender_pie():
    """
    성별 인구 파이 차트 데이터 API.

    선택된 지역의 남녀 인구 비율을 파이 차트 형태로 반환합니다.

    Query Parameters:
        base_ym (str, optional): 기준시기
        sido (str, optional): 시도명
        sigungu (str, optional): 시군구명

    Returns:
        JSON: Chart.js 파이 차트 데이터 포맷
            - success (bool): 성공 여부
            - labels (list[str]): ['남자', '여자']
            - datasets (list[dict]): 인구수 데이터

    Route:
        GET /01_population/api/chart/gender_pie?base_ym=202411&sido=서울특별시
    """
    base_ym = request.args.get('base_ym')
    sido = request.args.get('sido')
    sigungu = request.args.get('sigungu')

    pop_df = load_population_data(base_ym, sido, sigungu)

    male = int(pop_df['male_pop'].sum())
    female = int(pop_df['female_pop'].sum())

    return jsonify({
        'success': True,
        'labels': ['남자', '여자'],
        'datasets': [{
            'data': [male, female],
            'backgroundColor': ['rgba(74, 144, 217, 0.8)', 'rgba(229, 115, 115, 0.8)'],
            'borderColor': ['rgba(74, 144, 217, 1)', 'rgba(229, 115, 115, 1)'],
            'borderWidth': 2
        }]
    })


@population_bp.route('/api/chart/household_pie')
def api_chart_household_pie():
    """
    세대 구성 파이 차트 데이터 API.

    선택된 지역의 1인세대/다인세대 비율을 파이 차트 형태로 반환합니다.

    Query Parameters:
        base_ym (str, optional): 기준시기
        sido (str, optional): 시도명
        sigungu (str, optional): 시군구명

    Returns:
        JSON: Chart.js 파이 차트 데이터 포맷
            - success (bool): 성공 여부
            - labels (list[str]): ['1인세대', '다인세대']
            - datasets (list[dict]): 세대수 데이터

    Route:
        GET /01_population/api/chart/household_pie?base_ym=202411
    """
    base_ym = request.args.get('base_ym')
    sido = request.args.get('sido')
    sigungu = request.args.get('sigungu')

    pop_df = load_population_data(base_ym, sido, sigungu)
    hh_df = load_single_household_data(base_ym, sido, sigungu)

    total_hh = int(pop_df['household_cnt'].sum())
    single_hh = int(hh_df['single_household_cnt'].sum()) if not hh_df.empty else 0
    other_hh = total_hh - single_hh  # 다인세대 = 전체 - 1인세대

    return jsonify({
        'success': True,
        'labels': ['1인세대', '다인세대'],
        'datasets': [{
            'data': [single_hh, other_hh],
            'backgroundColor': ['rgba(156, 39, 176, 0.8)', 'rgba(102, 187, 106, 0.8)'],
            'borderColor': ['rgba(156, 39, 176, 1)', 'rgba(102, 187, 106, 1)'],
            'borderWidth': 2
        }]
    })


@population_bp.route('/api/chart/sigungu_top10')
def api_chart_sigungu_top10():
    """
    시군구 인구 Top 10/20 차트 데이터 API.

    인구가 가장 많은 상위 시군구를 막대 차트로 반환합니다.

    Query Parameters:
        base_ym (str, optional): 기준시기
        sido (str, optional): 시도명 (지정하면 해당 시도 내 Top N)
        consolidated (str, optional): 시군구통합 여부 ('true' 또는 'false', 기본: 'true')
            - 'true': admin_code 앞 4자리로 그룹화 (수원시 장안구+권선구+... → 수원시)
            - 'false': admin_code 앞 5자리로 그룹화 (기존 방식)
        top_n (int, optional): 상위 N개 (기본: 10, 최대: 50)

    Returns:
        JSON: Chart.js 막대 차트 데이터 포맷
            - success (bool): 성공 여부
            - labels (list[str]): 시군구명 목록 (Top N)
            - datasets (list[dict]): 인구수 데이터 (만 단위)

    Route:
        GET /01_population/api/chart/sigungu_top10?base_ym=202411&consolidated=true
        GET /01_population/api/chart/sigungu_top10?base_ym=202411&sido=경기도&top_n=20

    Note:
        sido를 지정하지 않으면 전국 시군구 중 Top N
        sido를 지정하면 해당 시도 내 시군구 Top N
        consolidated=true일 경우 수원시 전체가 하나로 합산됨
    """
    base_ym = request.args.get('base_ym')
    sido = request.args.get('sido')
    consolidated = request.args.get('consolidated', 'true').lower() == 'true'
    top_n = min(int(request.args.get('top_n', 10)), 50)

    pop_df = load_population_data(base_ym, sido)

    if consolidated and 'admin_code' in pop_df.columns:
        # 시군구통합 적용
        pop_df = add_sigungu_consolidated(pop_df)
        pop_df = get_sigungu_consolidated_name(pop_df)

        if sido:
            # 특정 시도 내 시군구통합별 집계
            sigungu_pop = pop_df.groupby('sigungu_code').agg({
                'sigungu_consolidated_nm': 'first',
                'total_pop': 'sum'
            }).reset_index()
            sigungu_pop['sigungu_nm'] = sigungu_pop['sigungu_consolidated_nm']
        else:
            # 전국: 시도+시군구통합명 결합
            pop_df['sigungu_full'] = pop_df['sido_nm'] + ' ' + pop_df['sigungu_consolidated_nm']
            sigungu_pop = pop_df.groupby(['sigungu_code', 'sigungu_full'])['total_pop'].sum().reset_index()
            sigungu_pop = sigungu_pop.rename(columns={'sigungu_full': 'sigungu_nm'})
    else:
        if sido:
            # 특정 시도 내 시군구별 집계 (기존 방식)
            sigungu_pop = pop_df.groupby('sigungu_nm')['total_pop'].sum().reset_index()
            sigungu_pop['sigungu_code'] = pop_df.groupby('sigungu_nm')['admin_code'].first().str[:5].values
        else:
            # 전국: 시도+시군구 결합 (구분을 위해)
            pop_df['sigungu_full'] = pop_df['sido_nm'] + ' ' + pop_df['sigungu_nm']
            sigungu_pop = pop_df.groupby('sigungu_full').agg({
                'admin_code': 'first',
                'total_pop': 'sum'
            }).reset_index()
            sigungu_pop = sigungu_pop.rename(columns={'sigungu_full': 'sigungu_nm'})
            sigungu_pop['sigungu_code'] = sigungu_pop['admin_code'].str[:5]

    # Top N 추출 (인구 내림차순)
    top_n_df = sigungu_pop.nlargest(top_n, 'total_pop')

    # 행정코드 오름차순으로 재정렬 (표시 순서)
    top_n_df = top_n_df.sort_values('sigungu_code')

    return jsonify({
        'success': True,
        'labels': top_n_df['sigungu_nm'].tolist(),
        'datasets': [{
            'label': '인구(만)',
            'data': (top_n_df['total_pop'] / 10000).round(1).tolist(),
            'backgroundColor': 'rgba(33, 150, 243, 0.7)',  # 파란색
            'borderColor': 'rgba(33, 150, 243, 1)',
            'borderWidth': 1
        }]
    })


# =============================================================================
# 보고서 저장 API
# =============================================================================

@population_bp.route('/api/save_report', methods=['POST'])
def api_save_report():
    """
    대시보드 보고서를 Markdown 파일로 저장합니다.

    차트 이미지는 output/images/ 폴더에 PNG로 저장하고,
    보고서 본문은 output/dashreport.md로 저장합니다.

    Request Body (JSON):
        filters: 필터 조건 (base_ym, sido, sigungu, consolidated)
        summary: 요약 카드 데이터
        chartImages: 차트 이미지 (Base64)
        sidoTable: 시도별 테이블 데이터
        generated_at: 생성 시각

    Returns:
        JSON: 저장 결과
            - success (bool): 성공 여부
            - filename (str): 저장된 파일명
            - error (str): 에러 메시지 (실패 시)
    """
    import os
    import base64
    from datetime import datetime

    try:
        data = request.get_json()

        # 출력 디렉토리 생성
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base_dir, 'output')
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)

        # 필터 정보
        filters = data.get('filters', {})
        base_ym = filters.get('base_ym', '전체')
        sido = filters.get('sido', '전체')
        sigungu = filters.get('sigungu', '전체')

        # 요약 데이터
        summary = data.get('summary', {})

        # 차트 이미지 저장
        chart_images = data.get('chartImages', {})
        chart_files = {}
        chart_names = {
            'chartSidoPop': '시도별_남녀인구',
            'chartSingleRatio': '시도별_1인세대비율',
            'chartTop10': '인구_Top10_시군구',
            'chartGenderPie': '성별_인구비율',
            'chartHouseholdPie': '세대_구성비율'
        }

        for chart_id, base64_data in chart_images.items():
            if base64_data and ',' in base64_data:
                # Base64 데이터에서 헤더 제거 후 디코딩
                img_data = base64.b64decode(base64_data.split(',')[1])
                filename = f"{chart_names.get(chart_id, chart_id)}.png"
                filepath = os.path.join(images_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                chart_files[chart_id] = f"images/{filename}"

        # 시도별 테이블 데이터
        sido_table = data.get('sidoTable', [])

        # Markdown 보고서 생성
        report_lines = [
            f"# 인구통계 대시보드 보고서",
            f"",
            f"**생성일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 조회 조건",
            f"",
            f"| 항목 | 값 |",
            f"|------|-----|",
            f"| 기준시기 | {base_ym if base_ym else '전체'} |",
            f"| 시도 | {sido if sido else '전체'} |",
            f"| 시군구 | {sigungu if sigungu else '전체'} |",
            f"",
            f"## 요약 통계",
            f"",
            f"| 항목 | 값 |",
            f"|------|-----|",
            f"| 총 인구 | {summary.get('total_pop', '-')} 만 명 |",
            f"| 남자 인구 | {summary.get('male_pop', '-')} 만 명 |",
            f"| 여자 인구 | {summary.get('female_pop', '-')} 만 명 |",
            f"| 세대수 | {summary.get('household_cnt', '-')} 만 세대 |",
            f"| 1인세대 | {summary.get('single_household', '-')} 만 세대 |",
            f"| 1인세대율 | {summary.get('single_ratio', '-')} % |",
            f"| 성비 | {summary.get('sex_ratio', '-')} (여100당) |",
            f"| 행정구역 수 | {summary.get('area_count', '-')} 개 |",
            f"",
            f"## 차트",
            f"",
        ]

        # 차트 이미지 추가
        if chart_files.get('chartSidoPop'):
            report_lines.extend([
                f"### 시도별 남녀 인구",
                f"![시도별 남녀 인구]({chart_files['chartSidoPop']})",
                f"",
            ])

        if chart_files.get('chartSingleRatio'):
            report_lines.extend([
                f"### 시도별 1인세대 비율",
                f"![시도별 1인세대 비율]({chart_files['chartSingleRatio']})",
                f"",
            ])

        if chart_files.get('chartTop10'):
            report_lines.extend([
                f"### 인구 Top 10 시군구",
                f"![인구 Top10 시군구]({chart_files['chartTop10']})",
                f"",
            ])

        if chart_files.get('chartGenderPie'):
            report_lines.extend([
                f"### 성별 인구 비율",
                f"![성별 인구 비율]({chart_files['chartGenderPie']})",
                f"",
            ])

        if chart_files.get('chartHouseholdPie'):
            report_lines.extend([
                f"### 세대 구성 비율",
                f"![세대 구성 비율]({chart_files['chartHouseholdPie']})",
                f"",
            ])

        # 시도별 테이블 추가
        if sido_table:
            report_lines.extend([
                f"## 시도별 인구 현황",
                f"",
                f"| 시도 | 총인구 | 남자 | 여자 | 세대수 | 1인세대 | 1인세대율 |",
                f"|------|--------|------|------|--------|---------|-----------|",
            ])
            for row in sido_table:
                report_lines.append(
                    f"| {row.get('sido_nm', '')} | {row.get('total_pop', '')} | "
                    f"{row.get('male_pop', '')} | {row.get('female_pop', '')} | "
                    f"{row.get('household_cnt', '')} | {row.get('single_household_cnt', '')} | "
                    f"{row.get('single_ratio', '')} |"
                )
            report_lines.append("")

        # 보고서 파일 저장
        report_path = os.path.join(output_dir, 'dashreport.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        return jsonify({
            'success': True,
            'filename': 'output/dashreport.md',
            'images_saved': len(chart_files)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


# =============================================================================
# 유틸리티 함수
# =============================================================================

def render():
    """
    main_app.py 호환용 render 함수.

    직접 호출 시 대시보드 페이지를 렌더링합니다.
    레거시 코드와의 호환성을 위해 제공됩니다.

    Returns:
        str: 렌더링된 population_dashboard.html

    Examples:
        >>> from routes.population_routes import render
        >>> html = render()
    """
    filters = get_filter_options()
    return render_template('population_dashboard.html',
                          filters=filters,
                          title='인구통계 분석')


# =============================================================================
# 연령별 통계 라우트 및 API
# =============================================================================

@population_bp.route('/age')
def age_stats():
    """연령별 통계 페이지를 렌더링합니다."""
    filters = get_filter_options()
    return render_template('population_age.html',
                          filters=filters,
                          title='연령별 인구 통계')


def load_age_population_data(base_ym=None, sido=None, sigungu=None):
    """
    연령별 인구 데이터를 조회합니다.

    Args:
        base_ym (str): 기준시기 (YYYYMM)
        sido (str): 시도명
        sigungu (str): 시군구명

    Returns:
        pd.DataFrame: 연령별 인구 데이터
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


@population_bp.route('/api/age_pyramid')
def api_age_pyramid():
    """연령별 인구 피라미드 데이터 API."""
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
