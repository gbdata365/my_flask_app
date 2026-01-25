# -*- coding: utf-8 -*-
"""
================================================================================
공통 데이터 조회 모듈 (data_query.py)
================================================================================

캐시 테이블에서 데이터를 조회하는 공통 기능을 제공합니다.
인구, 가구, 기업체 등 다양한 분야에서 재사용할 수 있습니다.

주요 기능:
    1. 필터 옵션 조회 (기준년월, 시도 목록)
    2. 시도/시군구/권역별 집계 데이터 조회
    3. 초기 화면용 요약 데이터 조회

사용 예시:
    from module.data_query import CacheDataQuery

    # 인구 데이터 조회
    query = CacheDataQuery('cache_sigungu_indicators')
    filters = query.get_filter_options()
    sido_data = query.get_sido_data(['202412'], ['total_pop', 'household_cnt'])

주의사항:
    - 캐시 테이블의 sido_nm은 이미 정규화되어 있음 (강원특별자치도 등)
    - CASE문 변환 불필요

Author: Claude AI Agent
Created: 2025-01-23
================================================================================
"""

import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import sys

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))
from module.db import get_db_engine


class CacheDataQuery:
    """
    캐시 테이블 데이터 조회 클래스

    다양한 분야의 캐시 테이블에서 데이터를 조회하는 공통 기능을 제공합니다.
    시도명은 캐시 테이블에 이미 정규화되어 있으므로 CASE문 변환이 불필요합니다.

    Attributes:
        table_name (str): 조회할 캐시 테이블명
        engine: SQLAlchemy 엔진

    Example:
        >>> query = CacheDataQuery('cache_sigungu_indicators')
        >>> filters = query.get_filter_options()
        >>> data = query.get_sido_data(['202412'], ['total_pop', 'single_cnt'])
    """

    def __init__(self, table_name: str, engine=None):
        """
        초기화

        Args:
            table_name: 캐시 테이블명 (예: 'cache_sigungu_indicators')
            engine: SQLAlchemy 엔진 (None이면 자동 생성)
        """
        self.table_name = table_name
        self.engine = engine or get_db_engine()
        self._column_cache = None

    # =========================================================================
    # 메타데이터 조회
    # =========================================================================

    def get_columns(self) -> List[str]:
        """테이블 컬럼 목록 조회 (캐싱)"""
        if self._column_cache is None:
            df = pd.read_sql(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{self.table_name}'
                ORDER BY ordinal_position
            """, self.engine)
            self._column_cache = df['column_name'].tolist()
        return self._column_cache

    def has_column(self, column_name: str) -> bool:
        """특정 컬럼 존재 여부 확인"""
        return column_name in self.get_columns()

    # =========================================================================
    # 필터 옵션 조회
    # =========================================================================

    def get_filter_options(self) -> Dict[str, Any]:
        """
        필터 옵션 조회 (기준년월, 시도 목록 등)

        Returns:
            dict: {
                'base_ym_list': ['202512', '202411', ...],
                'sido_list': ['서울특별시', '부산광역시', ...],
                'latest_ym': '202512'
            }
        """
        # 기준년월 목록 (내림차순)
        ym_df = pd.read_sql(f"""
            SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as ym
            FROM {self.table_name}
            ORDER BY ym DESC
        """, self.engine)
        base_ym_list = ym_df['ym'].tolist()

        # 시도 목록 (시도코드 순)
        sido_df = pd.read_sql(f"""
            SELECT DISTINCT sido_nm, MIN(LEFT(sigungu_code, 2)) as sido_code
            FROM {self.table_name}
            GROUP BY sido_nm
            ORDER BY sido_code
        """, self.engine)
        sido_list = sido_df['sido_nm'].tolist()

        return {
            'base_ym_list': base_ym_list,
            'sido_list': sido_list,
            'latest_ym': base_ym_list[0] if base_ym_list else None
        }

    def get_sigungu_list(self, sido: str) -> List[str]:
        """
        특정 시도의 시군구 목록 조회

        Args:
            sido: 시도명 (예: '경상북도')

        Returns:
            시군구명 리스트
        """
        df = pd.read_sql(f"""
            SELECT DISTINCT sigungu_nm
            FROM {self.table_name}
            WHERE sido_nm = '{sido}'
            ORDER BY sigungu_code
        """, self.engine)
        return df['sigungu_nm'].tolist()

    # =========================================================================
    # 시도별 집계 데이터 조회
    # =========================================================================

    def get_sido_data(
        self,
        base_ym_list: List[str],
        columns: List[str],
        aggregation: str = 'sum'
    ) -> pd.DataFrame:
        """
        시도별 집계 데이터 조회

        Args:
            base_ym_list: 기준년월 리스트 (예: ['202412', '202512'])
            columns: 조회할 컬럼 리스트 (예: ['total_pop', 'household_cnt'])
            aggregation: 집계 방식 ('sum', 'avg', 'count')

        Returns:
            DataFrame: 시도별 집계 데이터

        Example:
            >>> df = query.get_sido_data(['202412'], ['total_pop', 'single_cnt'])
        """
        agg_func = aggregation.upper()

        # 컬럼별 집계 SQL 생성
        col_sql = ', '.join([f"{agg_func}(COALESCE({col}, 0)) as {col}" for col in columns])

        all_data = []
        for ym in base_ym_list:
            df = pd.read_sql(f"""
                SELECT
                    sido_nm as name,
                    MIN(LEFT(sigungu_code, 2)) as sido_code,
                    {col_sql}
                FROM {self.table_name}
                WHERE TO_CHAR(base_ym, 'YYYYMM') = '{ym}'
                GROUP BY sido_nm
                ORDER BY MIN(LEFT(sigungu_code, 2))
            """, self.engine)
            df['base_ym'] = ym
            all_data.append(df)

        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    def get_sido_summary(
        self,
        columns: List[str],
        latest_n: int = 1
    ) -> pd.DataFrame:
        """
        초기 화면용 시도별 요약 데이터 (최신 N개 년월)

        Args:
            columns: 조회할 컬럼 리스트
            latest_n: 최신 몇 개 년월 (기본 1)

        Returns:
            DataFrame: 시도별 요약 데이터
        """
        # 최신 년월 조회
        ym_df = pd.read_sql(f"""
            SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as ym
            FROM {self.table_name}
            ORDER BY ym DESC
            LIMIT {latest_n}
        """, self.engine)
        base_ym_list = ym_df['ym'].tolist()

        if not base_ym_list:
            return pd.DataFrame()

        return self.get_sido_data(base_ym_list, columns)

    # =========================================================================
    # 시군구별 데이터 조회
    # =========================================================================

    def get_sigungu_data(
        self,
        base_ym_list: List[str],
        columns: List[str],
        sido: Optional[str] = None,
        consolidated: bool = True
    ) -> pd.DataFrame:
        """
        시군구별 데이터 조회

        Args:
            base_ym_list: 기준년월 리스트
            columns: 조회할 컬럼 리스트
            sido: 시도명 (None이면 전체)
            consolidated: True면 통합시군구(4자리 그룹화), False면 개별 시군구

        Returns:
            DataFrame: 시군구별 데이터
        """
        # 컬럼 SQL
        col_sql = ', '.join([f"COALESCE({col}, 0) as {col}" for col in columns])

        # 시도 조건
        sido_cond = f"AND sido_nm = '{sido}'" if sido else ""

        all_data = []
        for ym in base_ym_list:
            if consolidated:
                # 4자리 그룹화 (통합 시군구)
                agg_col_sql = ', '.join([f"SUM(COALESCE({col}, 0)) as {col}" for col in columns])
                df = pd.read_sql(f"""
                    SELECT
                        LEFT(sigungu_code, 4) || '0' as sigungu_code,
                        MIN(CASE WHEN sigungu_code LIKE '____0' THEN sigungu_nm
                            ELSE REGEXP_REPLACE(sigungu_nm, ' .*$', '') END) as name,
                        MIN(sido_nm) as sido_nm,
                        {agg_col_sql}
                    FROM {self.table_name}
                    WHERE TO_CHAR(base_ym, 'YYYYMM') = '{ym}'
                    {sido_cond}
                    GROUP BY LEFT(sigungu_code, 4)
                    ORDER BY LEFT(sigungu_code, 4) || '0'
                """, self.engine)
            else:
                # 개별 시군구
                df = pd.read_sql(f"""
                    SELECT
                        sigungu_code,
                        sigungu_nm as name,
                        sido_nm,
                        {col_sql}
                    FROM {self.table_name}
                    WHERE TO_CHAR(base_ym, 'YYYYMM') = '{ym}'
                    {sido_cond}
                    ORDER BY sigungu_code
                """, self.engine)

            df['base_ym'] = ym
            all_data.append(df)

        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    # =========================================================================
    # 권역별 집계 데이터 조회
    # =========================================================================

    def get_region_data(
        self,
        base_ym_list: List[str],
        columns: List[str]
    ) -> pd.DataFrame:
        """
        권역별 집계 데이터 조회

        dim_admin_area 테이블의 region_nm을 사용하여 권역별 집계

        Args:
            base_ym_list: 기준년월 리스트
            columns: 조회할 컬럼 리스트

        Returns:
            DataFrame: 권역별 집계 데이터
        """
        # 컬럼별 집계 SQL
        col_sql = ', '.join([f"SUM(COALESCE(c.{col}, 0)) as {col}" for col in columns])

        all_data = []
        for ym in base_ym_list:
            df = pd.read_sql(f"""
                SELECT
                    d.region_nm as name,
                    d.region_code,
                    {col_sql}
                FROM {self.table_name} c
                JOIN (
                    SELECT DISTINCT sigungu_code, region_nm, region_code
                    FROM dim_admin_area
                    WHERE region_nm IS NOT NULL
                ) d ON c.sigungu_code = d.sigungu_code
                WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '{ym}'
                GROUP BY d.region_nm, d.region_code
                ORDER BY d.region_code
            """, self.engine)
            df['base_ym'] = ym
            all_data.append(df)

        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    # =========================================================================
    # 지표 계산 (비율 등)
    # =========================================================================

    def calculate_ratio(
        self,
        df: pd.DataFrame,
        numerator: str,
        denominator: str,
        result_col: str,
        multiplier: float = 100,
        decimal_places: int = 2
    ) -> pd.DataFrame:
        """
        비율 계산

        Args:
            df: 데이터프레임
            numerator: 분자 컬럼명
            denominator: 분모 컬럼명
            result_col: 결과 컬럼명
            multiplier: 곱할 값 (기본 100 = 백분율)
            decimal_places: 소수점 자릿수

        Returns:
            비율 컬럼이 추가된 DataFrame
        """
        df = df.copy()
        df[result_col] = (df[numerator] / df[denominator].replace(0, float('nan')) * multiplier).round(decimal_places)
        df[result_col] = df[result_col].fillna(0)
        return df

    # =========================================================================
    # 전국 합계 계산
    # =========================================================================

    def add_national_total(
        self,
        df: pd.DataFrame,
        columns: List[str],
        name_col: str = 'name',
        total_name: str = '전국'
    ) -> pd.DataFrame:
        """
        전국 합계 행 추가

        Args:
            df: 데이터프레임
            columns: 합계할 컬럼 리스트
            name_col: 이름 컬럼명
            total_name: 합계 행 이름

        Returns:
            합계 행이 추가된 DataFrame
        """
        df = df.copy()

        # 년월별로 그룹화하여 합계 계산
        if 'base_ym' in df.columns:
            totals = []
            for ym in df['base_ym'].unique():
                ym_df = df[df['base_ym'] == ym]
                total_row = {name_col: total_name, 'base_ym': ym}
                for col in columns:
                    if col in ym_df.columns:
                        total_row[col] = ym_df[col].sum()
                totals.append(total_row)

            total_df = pd.DataFrame(totals)
            return pd.concat([total_df, df], ignore_index=True)
        else:
            total_row = {name_col: total_name}
            for col in columns:
                if col in df.columns:
                    total_row[col] = df[col].sum()
            return pd.concat([pd.DataFrame([total_row]), df], ignore_index=True)


# =============================================================================
# 편의 함수
# =============================================================================

def get_population_query() -> CacheDataQuery:
    """인구 데이터 조회용 인스턴스"""
    return CacheDataQuery('cache_sigungu_indicators')


def get_age_query() -> CacheDataQuery:
    """연령별/1인가구 데이터 조회용 인스턴스"""
    return CacheDataQuery('cache_sigungu_age')


# =============================================================================
# 초기 화면 요약 데이터 생성
# =============================================================================

def get_initial_summary(
    table_name: str,
    columns: List[str],
    column_labels: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    초기 화면용 시도별 요약 데이터 생성

    Args:
        table_name: 캐시 테이블명
        columns: 표시할 컬럼 리스트
        column_labels: 컬럼명 → 표시명 매핑

    Returns:
        dict: {
            'base_ym': '202512',
            'columns': [{'key': 'total_pop', 'label': '총인구'}, ...],
            'data': [{'name': '서울특별시', 'total_pop': 9000000, ...}, ...]
        }
    """
    query = CacheDataQuery(table_name)
    filters = query.get_filter_options()

    if not filters['latest_ym']:
        return {'base_ym': None, 'columns': [], 'data': []}

    # 최신 데이터 조회
    df = query.get_sido_summary(columns, latest_n=1)

    # 전국 합계 추가
    df = query.add_national_total(df, columns)

    # 컬럼 정보
    column_labels = column_labels or {}
    col_info = [
        {'key': col, 'label': column_labels.get(col, col)}
        for col in columns
    ]

    return {
        'base_ym': filters['latest_ym'],
        'columns': col_info,
        'data': df.to_dict('records')
    }


# =============================================================================
# 지표 계산 유틸리티 (code_indicator 테이블 기반)
# =============================================================================

def get_indicators_from_db(category: int = None) -> List[Dict[str, Any]]:
    """
    code_indicator 테이블에서 활성 지표 목록 조회

    Args:
        category: 지표 카테고리 (1=인구지표, 2=세대지표, None=전체)

    Returns:
        list: [{'column_name': ..., 'display_name': ..., 'numerator': ..., 'denominator': ..., ...}, ...]
    """
    engine = get_db_engine()

    where_clause = "WHERE is_active = TRUE"
    if category is not None:
        where_clause += f" AND category = {category}"

    df = pd.read_sql(f"""
        SELECT
            id, category, category_name, column_name, display_name, description,
            numerator, denominator, multiplier, decimal_places, data_type, sort_order
        FROM code_indicator
        {where_clause}
        ORDER BY category, sort_order
    """, engine)

    return df.to_dict('records')


def build_indicator_sql_expr(
    numerator: str,
    denominator: str,
    multiplier: float = 100,
    decimal_places: int = 2,
    prefix: str = 'c.'
) -> str:
    """
    지표 계산을 위한 SQL 표현식 생성

    Args:
        numerator: 분자 컬럼명 또는 표현식 (예: 'elderly_pop', 'youth_pop + elderly_pop')
        denominator: 분모 컬럼명 (예: 'total_pop', 'household_cnt')
        multiplier: 곱할 값 (기본 100)
        decimal_places: 소수점 자릿수
        prefix: 테이블 별칭 접두사 (기본 'c.')

    Returns:
        str: SQL 표현식 (예: "ROUND(SUM(c.elderly_pop)::numeric / NULLIF(SUM(c.total_pop), 0) * 100, 2)")
    """
    # 분자 처리: + 연산자가 있는 경우 각 항목에 prefix와 SUM 적용
    if '+' in numerator:
        parts = [p.strip() for p in numerator.split('+')]
        num_expr = ' + '.join([f"COALESCE(SUM({prefix}{p}), 0)" for p in parts])
        num_expr = f"({num_expr})"
    else:
        num_expr = f"COALESCE(SUM({prefix}{numerator}), 0)"

    # 분모 처리
    denom_expr = f"NULLIF(SUM({prefix}{denominator}), 0)"

    # 최종 표현식
    return f"ROUND({num_expr}::numeric / {denom_expr} * {multiplier}, {decimal_places})"


def calculate_indicator_df(
    df: pd.DataFrame,
    numerator: str,
    denominator: str,
    result_col: str,
    multiplier: float = 100,
    decimal_places: int = 2
) -> pd.DataFrame:
    """
    DataFrame에서 지표 계산 (code_indicator 정의 기반)

    Args:
        df: 데이터프레임
        numerator: 분자 컬럼명 또는 표현식 (예: 'elderly_pop', 'youth_pop + elderly_pop')
        denominator: 분모 컬럼명
        result_col: 결과 컬럼명
        multiplier: 곱할 값
        decimal_places: 소수점 자릿수

    Returns:
        지표 컬럼이 추가된 DataFrame
    """
    df = df.copy()

    # 분자 계산: + 연산자가 있는 경우 합산
    if '+' in numerator:
        parts = [p.strip() for p in numerator.split('+')]
        num_value = df[parts[0]].fillna(0)
        for part in parts[1:]:
            num_value = num_value + df[part].fillna(0)
    else:
        num_value = df[numerator].fillna(0)

    # 분모
    denom_value = df[denominator].replace(0, float('nan'))

    # 계산
    df[result_col] = (num_value / denom_value * multiplier).round(decimal_places).fillna(0)

    return df


def get_indicator_by_column_name(column_name: str) -> Optional[Dict[str, Any]]:
    """
    컬럼명으로 지표 정보 조회

    Args:
        column_name: 지표 컬럼명 (예: 'elderly_ratio', 'single_ratio')

    Returns:
        dict 또는 None: 지표 정보
    """
    engine = get_db_engine()

    df = pd.read_sql(f"""
        SELECT
            id, category, category_name, column_name, display_name, description,
            numerator, denominator, multiplier, decimal_places, data_type, sort_order
        FROM code_indicator
        WHERE column_name = '{column_name}' AND is_active = TRUE
        LIMIT 1
    """, engine)

    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_column_labels() -> Dict[str, str]:
    """
    code_age_group과 code_indicator에서 컬럼명 → 한글 라벨 매핑 조회

    Returns:
        dict: {'youth_pop': '유소년', 'elderly_ratio': '고령화율', ...}
    """
    engine = get_db_engine()
    labels = {}

    # code_age_group에서 column_name → code_name 매핑
    try:
        age_df = pd.read_sql("""
            SELECT column_name, code_name
            FROM code_age_group
            WHERE is_active = TRUE AND column_name IS NOT NULL AND column_name != ''
        """, engine)
        for _, row in age_df.iterrows():
            if row['column_name']:
                labels[row['column_name']] = row['code_name']
    except Exception:
        pass

    # code_indicator에서 column_name → display_name 매핑
    try:
        ind_df = pd.read_sql("""
            SELECT column_name, display_name
            FROM code_indicator
            WHERE is_active = TRUE AND column_name IS NOT NULL
        """, engine)
        for _, row in ind_df.iterrows():
            if row['column_name']:
                labels[row['column_name']] = row['display_name']
    except Exception:
        pass

    return labels
