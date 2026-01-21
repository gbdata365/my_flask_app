# -*- coding: utf-8 -*-
"""
공통 집계 모듈 (Common Aggregation Module)
==========================================

이 모듈은 데이터 분석에서 자주 사용되는 집계 함수들을 제공합니다.
pandas의 groupby, merge, pivot 등을 래핑하여 일관된 인터페이스를 제공합니다.

제공 함수:
    1. aggregate_by_group(): 그룹별 집계 (sum, mean, count 등)
    2. calculate_ratio(): 비율 계산 (분자/분모*100)
    3. convert_unit(): 단위 변환 (/10000 등)
    4. pivot_for_heatmap(): 히트맵용 피벗 테이블
    5. merge_dataframes(): 데이터프레임 병합

사용 예시:
    >>> from module.aggregators import aggregate_by_group, calculate_ratio

    >>> # 시도별 인구 합계
    >>> df_sido = aggregate_by_group(df, ['sido_nm'], ['total_pop', 'male_pop'])

    >>> # 1인세대 비율 계산
    >>> df = calculate_ratio(df, 'single_hh', 'total_hh', 'single_ratio')

Author: Claude AI Agent
Created: 2024-12-18
"""

import pandas as pd
from typing import List, Dict, Any


def aggregate_by_group(
    df: pd.DataFrame,
    group_cols: List[str],
    value_cols: List[str],
    agg_func: str = 'sum',
    sort_by: str = None,
    sort_ascending: bool = True
) -> pd.DataFrame:
    """
    그룹별 집계를 수행합니다.

    pandas의 groupby().agg() 패턴을 래핑한 함수입니다.
    여러 컬럼을 동시에 집계할 수 있습니다.

    Args:
        df (pd.DataFrame): 원본 데이터프레임

        group_cols (List[str]): 그룹핑할 컬럼 리스트.
            예: ['sido_nm'] - 시도별
            예: ['sido_nm', 'base_ym'] - 시도 및 연월별

        value_cols (List[str]): 집계할 값 컬럼 리스트.
            예: ['total_pop'] - 총인구만
            예: ['total_pop', 'male_pop', 'female_pop'] - 여러 컬럼

        agg_func (str, optional): 집계 함수.
            기본값: 'sum'
            지원: 'sum', 'mean', 'count', 'min', 'max', 'std'

        sort_by (str, optional): 정렬 기준 컬럼.
            None이면 정렬 안함
            예: 'total_pop' (값 기준 정렬)

        sort_ascending (bool, optional): 오름차순 정렬 여부.
            기본값: True

    Returns:
        pd.DataFrame: 집계된 데이터프레임.
            인덱스는 reset되어 일반 컬럼으로 변환됨

    Examples:
        >>> # 시도별 인구 합계
        >>> df_sido = aggregate_by_group(
        ...     df,
        ...     group_cols=['sido_nm'],
        ...     value_cols=['total_pop', 'male_pop', 'female_pop']
        ... )

        >>> # 시도×연월별 평균 인구
        >>> df_avg = aggregate_by_group(
        ...     df,
        ...     group_cols=['sido_nm', 'base_ym'],
        ...     value_cols=['total_pop'],
        ...     agg_func='mean'
        ... )

        >>> # 값 기준 내림차순 정렬
        >>> df_sorted = aggregate_by_group(
        ...     df,
        ...     ['category'],
        ...     ['sales'],
        ...     sort_by='sales',
        ...     sort_ascending=False
        ... )

    Note:
        - 존재하지 않는 컬럼은 자동으로 무시됨
        - NaN 값은 집계에서 제외됨
    """
    # 존재하는 컬럼만 필터링 (없는 컬럼은 무시)
    valid_cols = [col for col in value_cols if col in df.columns]
    agg_dict = {col: agg_func for col in valid_cols}

    # 그룹별 집계 수행
    result = df.groupby(group_cols).agg(agg_dict).reset_index()

    # 정렬 (옵션)
    if sort_by and sort_by in result.columns:
        result = result.sort_values(sort_by, ascending=sort_ascending)

    return result


def calculate_ratio(
    df: pd.DataFrame,
    numerator_col: str,
    denominator_col: str,
    result_col: str,
    multiply: float = 100,
    round_digits: int = 2
) -> pd.DataFrame:
    """
    비율을 계산하여 새 컬럼을 추가합니다.

    (분자 / 분모) * multiply 공식으로 비율을 계산합니다.
    퍼센트 계산 시 multiply=100 사용 (기본값)

    Args:
        df (pd.DataFrame): 원본 데이터프레임

        numerator_col (str): 분자 컬럼명.
            예: 'single_household', 'male_pop'

        denominator_col (str): 분모 컬럼명.
            예: 'total_household', 'total_pop'

        result_col (str): 결과를 저장할 새 컬럼명.
            예: 'single_ratio', 'male_ratio'

        multiply (float, optional): 곱할 값.
            기본값: 100 (퍼센트)
            예: 1 (비율 그대로), 1000 (천분율)

        round_digits (int, optional): 반올림 자릿수.
            기본값: 2
            예: 0 (정수), 1 (소수점 1자리)

    Returns:
        pd.DataFrame: 새 컬럼이 추가된 데이터프레임 (복사본)

    Examples:
        >>> # 1인세대 비율 (%)
        >>> df = calculate_ratio(
        ...     df,
        ...     numerator_col='single_hh',
        ...     denominator_col='total_hh',
        ...     result_col='single_ratio'
        ... )
        >>> print(df['single_ratio'])  # 42.15, 38.50, ...

        >>> # 성비 (여자 100명당 남자 수)
        >>> df = calculate_ratio(
        ...     df,
        ...     'male_pop', 'female_pop', 'sex_ratio',
        ...     multiply=100,
        ...     round_digits=1
        ... )

    Note:
        - 분모가 0인 경우 inf가 발생할 수 있음 (사전 필터링 권장)
        - 원본 데이터프레임은 변경되지 않음 (복사본 반환)
    """
    df = df.copy()
    df[result_col] = (df[numerator_col] / df[denominator_col] * multiply).round(round_digits)
    return df


def convert_unit(
    df: pd.DataFrame,
    cols: List[str],
    divisor: float = 10000,
    suffix: str = "_만",
    inplace: bool = False
) -> pd.DataFrame:
    """
    숫자 컬럼의 단위를 변환합니다.

    큰 숫자를 읽기 쉬운 단위로 변환합니다.
    예: 51,000,000 → 5,100 (만 단위)

    Args:
        df (pd.DataFrame): 원본 데이터프레임

        cols (List[str]): 변환할 컬럼 리스트.
            예: ['total_pop'], ['total_pop', 'male_pop']

        divisor (float, optional): 나눌 값.
            기본값: 10000 (만 단위)
            예: 1000 (천 단위), 100000000 (억 단위)

        suffix (str, optional): 새 컬럼명 접미사.
            기본값: "_만"
            예: "_천", "_억"
            None이면 원본 컬럼 덮어쓰기

        inplace (bool, optional): 원본 컬럼 덮어쓰기 여부.
            기본값: False (새 컬럼 생성)
            True이면 suffix 무시하고 원본 덮어쓰기

    Returns:
        pd.DataFrame: 변환된 데이터프레임 (복사본)

    Examples:
        >>> # 새 컬럼 생성 (기본)
        >>> df = convert_unit(df, ['total_pop', 'male_pop'])
        >>> print(df.columns)  # [..., 'total_pop_만', 'male_pop_만']

        >>> # 원본 컬럼 덮어쓰기
        >>> df = convert_unit(df, ['total_pop'], inplace=True)

        >>> # 천 단위 변환
        >>> df = convert_unit(df, ['small_value'], divisor=1000, suffix='_천')

    Note:
        - 존재하지 않는 컬럼은 자동으로 무시됨
        - 원본 데이터프레임은 변경되지 않음
    """
    df = df.copy()
    for col in cols:
        if col in df.columns:
            if inplace or suffix is None:
                # 원본 컬럼 덮어쓰기
                df[col] = df[col] / divisor
            else:
                # 새 컬럼 생성
                df[col + suffix] = df[col] / divisor
    return df


def pivot_for_heatmap(
    df: pd.DataFrame,
    index_col: str,
    columns_col: str,
    values_col: str,
    aggfunc: str = 'sum',
    fill_value: Any = 0
) -> pd.DataFrame:
    """
    히트맵용 피벗 테이블을 생성합니다.

    Long 형식 데이터를 Wide 형식(매트릭스)으로 변환합니다.
    plot_heatmap() 함수와 함께 사용합니다.

    Args:
        df (pd.DataFrame): Long 형식 데이터프레임

        index_col (str): 행(Y축)이 될 컬럼명.
            예: 'sido_nm' (시도가 행)

        columns_col (str): 열(X축)이 될 컬럼명.
            예: 'age_group' (연령대가 열)

        values_col (str): 셀 값이 될 컬럼명.
            예: 'population', 'ratio'

        aggfunc (str, optional): 중복 값 처리 함수.
            기본값: 'sum'
            예: 'mean', 'count', 'first'

        fill_value (Any, optional): 빈 셀 채울 값.
            기본값: 0
            예: None (NaN 유지), '' (빈 문자열)

    Returns:
        pd.DataFrame: 피벗된 데이터프레임 (매트릭스 형태)

    Examples:
        >>> # 시도 × 연령대 인구 매트릭스
        >>> pivot_df = pivot_for_heatmap(
        ...     df,
        ...     index_col='sido_nm',
        ...     columns_col='age_group',
        ...     values_col='population'
        ... )
        >>> print(pivot_df)
        #           10대  20대  30대  ...
        # 서울특별시  100   200   300
        # 부산광역시   80   150   200

        >>> # 히트맵으로 시각화
        >>> from module.visualizers import plot_heatmap
        >>> plot_heatmap(pivot_df, '시도별 연령대별 인구', 'heatmap.png')

    Note:
        - 인덱스는 그대로 유지됨 (reset_index 안함)
        - 컬럼 순서는 원본 데이터의 순서를 따름
    """
    return df.pivot_table(
        index=index_col,
        columns=columns_col,
        values=values_col,
        aggfunc=aggfunc,
        fill_value=fill_value
    )


def merge_dataframes(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    on: List[str],
    how: str = 'outer'
) -> pd.DataFrame:
    """
    두 데이터프레임을 병합합니다.

    pandas의 merge() 함수를 래핑하여 NaN을 0으로 채웁니다.
    여러 테이블의 데이터를 결합할 때 사용합니다.

    Args:
        df1 (pd.DataFrame): 첫 번째 데이터프레임 (왼쪽)

        df2 (pd.DataFrame): 두 번째 데이터프레임 (오른쪽)

        on (List[str]): 병합 키 컬럼 리스트.
            예: ['sido_nm'], ['sido_nm', 'base_ym']

        how (str, optional): 병합 방식.
            기본값: 'outer' (합집합)
            - 'inner': 교집합 (양쪽 모두 있는 것만)
            - 'left': 왼쪽 기준 (df1의 모든 행 유지)
            - 'right': 오른쪽 기준 (df2의 모든 행 유지)
            - 'outer': 합집합 (모든 행 유지)

    Returns:
        pd.DataFrame: 병합된 데이터프레임.
            NaN 값은 0으로 채워짐

    Examples:
        >>> # 인구 데이터와 세대 데이터 병합
        >>> df_merged = merge_dataframes(
        ...     pop_df, household_df,
        ...     on=['sido_nm', 'base_ym'],
        ...     how='left'
        ... )

        >>> # 여러 데이터프레임 연속 병합
        >>> result = merge_dataframes(df1, df2, ['key'])
        >>> result = merge_dataframes(result, df3, ['key'])

    Note:
        - 숫자형 NaN만 0으로 변환 (문자열 NaN은 유지)
        - 컬럼명 충돌 시 자동으로 _x, _y 접미사 추가됨
    """
    return df1.merge(df2, on=on, how=how).fillna(0)
