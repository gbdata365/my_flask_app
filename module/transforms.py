# -*- coding: utf-8 -*-
"""
데이터 변환 모듈 (Data Transformation Module)
=============================================

이 모듈은 데이터 분석에서 자주 사용되는 데이터 변환 함수들을 제공합니다.
pandas의 melt, pivot, cut 등을 래핑하여 일관된 인터페이스를 제공합니다.

제공 함수:
    1. add_region(): 시도별 권역 매핑 추가
    2. add_category(): 범용 카테고리 매핑
    3. add_age_group(): 연령대 구간 분류
    4. wide_to_long(): Wide → Long 형식 변환
    5. long_to_wide(): Long → Wide 형식 변환
    6. filter_rows(): 조건별 행 필터링
    7. rename_columns(): 컬럼명 변경
    8. reorder_by_list(): 지정 순서로 정렬
    9. extract_year(): 날짜에서 년도 추출

사용 예시:
    >>> from module.transforms import add_region, wide_to_long

    >>> # 권역 추가
    >>> df = add_region(df, 'sido_nm', REGION_MAPPING)

    >>> # Wide → Long 변환
    >>> df_long = wide_to_long(df, ['sido_nm'], ['male_pop', 'female_pop'])

Author: Claude AI Agent
Created: 2024-12-18
"""

import pandas as pd
from typing import Dict, List, Any


def add_region(
    df: pd.DataFrame,
    sido_col: str,
    region_mapping: Dict[str, str],
    result_col: str = '권역'
) -> pd.DataFrame:
    """
    시도명을 기준으로 권역 컬럼을 추가합니다.

    17개 시도를 수도권, 충청권, 호남권, 영남권, 강원/제주 등
    권역으로 그룹화할 때 사용합니다.

    Args:
        df (pd.DataFrame): 원본 데이터프레임.
            시도명 컬럼을 포함해야 함

        sido_col (str): 시도명이 담긴 컬럼명.
            예: 'sido_nm', '시도명'

        region_mapping (Dict[str, str]): 시도 → 권역 매핑 딕셔너리.
            예: {'서울특별시': '수도권', '부산광역시': '영남권', ...}

        result_col (str, optional): 결과 컬럼명.
            기본값: '권역'

    Returns:
        pd.DataFrame: 권역 컬럼이 추가된 데이터프레임 (복사본)

    Examples:
        >>> REGION_MAPPING = {
        ...     '서울특별시': '수도권', '경기도': '수도권', '인천광역시': '수도권',
        ...     '부산광역시': '영남권', '대구광역시': '영남권', '울산광역시': '영남권',
        ...     '광주광역시': '호남권', '전라남도': '호남권', '전라북도': '호남권',
        ... }
        >>> df = add_region(df, 'sido_nm', REGION_MAPPING)
        >>> print(df[['sido_nm', '권역']].head())
        #      sido_nm   권역
        # 0  서울특별시  수도권
        # 1  부산광역시  영남권

        >>> # 다른 컬럼명으로 저장
        >>> df = add_region(df, 'sido_nm', REGION_MAPPING, result_col='region')

    Note:
        - 매핑에 없는 시도는 NaN으로 표시됨
        - 원본 데이터프레임은 변경되지 않음 (복사본 반환)
    """
    df = df.copy()
    df[result_col] = df[sido_col].map(region_mapping)
    return df


def add_category(
    df: pd.DataFrame,
    source_col: str,
    category_mapping: Dict[str, str],
    result_col: str = 'category'
) -> pd.DataFrame:
    """
    소스 컬럼 값을 카테고리로 매핑하여 새 컬럼을 추가합니다.

    범용 매핑 함수로, 다양한 분류 작업에 활용할 수 있습니다.
    예: 연령별 세대 분류, 업종별 산업 분류 등

    Args:
        df (pd.DataFrame): 원본 데이터프레임

        source_col (str): 매핑할 소스 컬럼명.
            예: 'age', 'industry_code'

        category_mapping (Dict[str, str]): 값 → 카테고리 매핑 딕셔너리.
            예: {0: '영유아', 10: '청소년', 20: '청년', ...}

        result_col (str, optional): 결과 컬럼명.
            기본값: 'category'

    Returns:
        pd.DataFrame: 카테고리 컬럼이 추가된 데이터프레임 (복사본)

    Examples:
        >>> # 연령을 세대로 매핑
        >>> GENERATION_MAP = {
        ...     '10대': 'Z세대', '20대': 'Z세대',
        ...     '30대': '밀레니얼', '40대': 'X세대',
        ...     '50대': '베이비붐', '60대': '베이비붐'
        ... }
        >>> df = add_category(df, 'age_group', GENERATION_MAP, 'generation')

        >>> # 산업 대분류 추가
        >>> INDUSTRY_MAP = {'01': '농업', '02': '임업', '03': '어업'}
        >>> df = add_category(df, 'industry_code', INDUSTRY_MAP, '산업분류')

    Note:
        - add_region()과 동일한 동작이지만 더 범용적인 이름
        - 매핑에 없는 값은 NaN으로 표시됨
    """
    df = df.copy()
    df[result_col] = df[source_col].map(category_mapping)
    return df


def add_age_group(
    df: pd.DataFrame,
    age_col: str,
    bins: List[int],
    labels: List[str],
    result_col: str = '연령대'
) -> pd.DataFrame:
    """
    연속형 나이 데이터를 구간별 연령대로 분류합니다.

    pandas의 pd.cut() 함수를 래핑하여 연령 그룹을 생성합니다.
    인구 피라미드, 연령대별 분석 등에 활용됩니다.

    Args:
        df (pd.DataFrame): 원본 데이터프레임.
            숫자형 나이 컬럼을 포함해야 함

        age_col (str): 나이가 담긴 컬럼명.
            예: 'age', '나이'

        bins (List[int]): 구간 경계값 리스트.
            예: [0, 10, 20, 30, 40, 50, 60, 70, 80, 100]
            구간은 [시작, 끝) 형태 (right=False)

        labels (List[str]): 각 구간의 라벨 리스트.
            bins보다 1개 적어야 함
            예: ['0~9세', '10~19세', '20~29세', ...]

        result_col (str, optional): 결과 컬럼명.
            기본값: '연령대'

    Returns:
        pd.DataFrame: 연령대 컬럼이 추가된 데이터프레임 (복사본)

    Examples:
        >>> # 10세 단위 연령대
        >>> bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 100]
        >>> labels = ['0~9세', '10대', '20대', '30대', '40대',
        ...           '50대', '60대', '70대', '80세+']
        >>> df = add_age_group(df, 'age', bins, labels)
        >>> print(df[['age', '연령대']].head())
        #    age   연령대
        # 0   25    20대
        # 1   34    30대

        >>> # 생애주기별 분류
        >>> bins = [0, 20, 40, 65, 100]
        >>> labels = ['미성년', '청년', '중장년', '노년']
        >>> df = add_age_group(df, 'age', bins, labels, '생애주기')

    Note:
        - bins=[0, 10, 20]이면 구간은 [0,10), [10,20)
        - NaN 값은 연령대도 NaN
        - right=False이므로 경계값은 다음 구간에 포함
    """
    df = df.copy()
    df[result_col] = pd.cut(df[age_col], bins=bins, labels=labels, right=False)
    return df


def wide_to_long(
    df: pd.DataFrame,
    id_vars: List[str],
    value_vars: List[str],
    var_name: str = 'variable',
    value_name: str = 'value'
) -> pd.DataFrame:
    """
    Wide 형식 데이터를 Long 형식으로 변환합니다.

    여러 컬럼에 분산된 값을 하나의 컬럼으로 모읍니다.
    pandas의 melt() 함수를 래핑합니다.

    변환 전 (Wide):
        | sido | male_pop | female_pop |
        |------|----------|------------|
        | 서울 | 100      | 110        |

    변환 후 (Long):
        | sido | variable   | value |
        |------|------------|-------|
        | 서울 | male_pop   | 100   |
        | 서울 | female_pop | 110   |

    Args:
        df (pd.DataFrame): Wide 형식 데이터프레임

        id_vars (List[str]): 고정할 컬럼 리스트 (식별자).
            이 컬럼들은 그대로 유지됨
            예: ['sido_nm', 'base_ym']

        value_vars (List[str]): Long으로 변환할 컬럼 리스트.
            이 컬럼들이 녹아서 하나의 컬럼이 됨
            예: ['male_pop', 'female_pop']

        var_name (str, optional): 변수명 컬럼명.
            기본값: 'variable'
            예: 'gender', '성별'

        value_name (str, optional): 값 컬럼명.
            기본값: 'value'
            예: 'population', '인구수'

    Returns:
        pd.DataFrame: Long 형식으로 변환된 데이터프레임

    Examples:
        >>> # 성별 인구를 Long 형식으로
        >>> df_long = wide_to_long(
        ...     df,
        ...     id_vars=['sido_nm', 'base_ym'],
        ...     value_vars=['male_pop', 'female_pop'],
        ...     var_name='성별',
        ...     value_name='인구수'
        ... )

        >>> # 연도별 데이터를 Long 형식으로
        >>> df_long = wide_to_long(
        ...     df,
        ...     id_vars=['region'],
        ...     value_vars=['2020', '2021', '2022', '2023'],
        ...     var_name='년도',
        ...     value_name='값'
        ... )

    Note:
        - 시각화 라이브러리(seaborn 등)는 Long 형식을 선호
        - 반대 변환은 long_to_wide() 사용
    """
    return pd.melt(
        df,
        id_vars=id_vars,
        value_vars=value_vars,
        var_name=var_name,
        value_name=value_name
    )


def long_to_wide(
    df: pd.DataFrame,
    index_col: str,
    columns_col: str,
    values_col: str,
    fill_value: Any = 0
) -> pd.DataFrame:
    """
    Long 형식 데이터를 Wide 형식으로 변환합니다.

    하나의 컬럼에 있는 값을 여러 컬럼으로 펼칩니다.
    pandas의 pivot() 함수를 래핑합니다.

    변환 전 (Long):
        | sido | gender | pop |
        |------|--------|-----|
        | 서울 | 남     | 100 |
        | 서울 | 여     | 110 |

    변환 후 (Wide):
        | sido | 남  | 여  |
        |------|-----|-----|
        | 서울 | 100 | 110 |

    Args:
        df (pd.DataFrame): Long 형식 데이터프레임

        index_col (str): 행이 될 컬럼명.
            예: 'sido_nm'

        columns_col (str): 열로 펼칠 컬럼명.
            예: 'gender', 'year'

        values_col (str): 셀 값이 될 컬럼명.
            예: 'population'

        fill_value (Any, optional): 빈 셀 채울 값.
            기본값: 0
            예: None (NaN 유지), '' (빈 문자열)

    Returns:
        pd.DataFrame: Wide 형식으로 변환된 데이터프레임.
            인덱스는 reset됨 (일반 컬럼으로 변환)

    Examples:
        >>> # 성별을 컬럼으로 펼치기
        >>> df_wide = long_to_wide(
        ...     df,
        ...     index_col='sido_nm',
        ...     columns_col='gender',
        ...     values_col='population'
        ... )
        >>> print(df_wide.columns)  # ['sido_nm', '남', '여']

        >>> # 연도를 컬럼으로 펼치기
        >>> df_wide = long_to_wide(
        ...     df,
        ...     index_col='region',
        ...     columns_col='year',
        ...     values_col='value',
        ...     fill_value=None  # 빈 값은 NaN
        ... )

    Note:
        - pivot_table()과 달리 aggfunc 없음 (중복 시 에러)
        - 중복 값이 있으면 pivot_for_heatmap() 사용
        - 반대 변환은 wide_to_long() 사용
    """
    return df.pivot(
        index=index_col,
        columns=columns_col,
        values=values_col
    ).fillna(fill_value).reset_index()


def filter_rows(
    df: pd.DataFrame,
    conditions: Dict[str, Any]
) -> pd.DataFrame:
    """
    조건에 맞는 행만 필터링합니다.

    딕셔너리로 필터 조건을 지정하여 데이터를 추출합니다.
    단일 값 또는 값 리스트로 필터링할 수 있습니다.

    Args:
        df (pd.DataFrame): 원본 데이터프레임

        conditions (Dict[str, Any]): 필터 조건 딕셔너리.
            - 단일 값: {컬럼명: 값} → 해당 값과 일치하는 행
            - 리스트: {컬럼명: [값1, 값2]} → 값들 중 하나와 일치하는 행
            - 여러 조건: AND 조건으로 모두 적용

    Returns:
        pd.DataFrame: 필터링된 데이터프레임 (복사본)

    Examples:
        >>> # 단일 조건 필터
        >>> df_seoul = filter_rows(df, {'sido_nm': '서울특별시'})

        >>> # 복수 값 필터 (OR 조건)
        >>> df_metro = filter_rows(df, {
        ...     'sido_nm': ['서울특별시', '부산광역시', '대구광역시']
        ... })

        >>> # 복수 조건 필터 (AND 조건)
        >>> df_filtered = filter_rows(df, {
        ...     'sido_nm': '서울특별시',
        ...     'base_ym': '202411'
        ... })

        >>> # 연도와 지역 동시 필터
        >>> df_filtered = filter_rows(df, {
        ...     'year': [2022, 2023],
        ...     'region': '수도권'
        ... })

    Note:
        - 조건이 비어있으면 전체 데이터 반환
        - 존재하지 않는 값으로 필터링하면 빈 데이터프레임 반환
        - 부등호 조건(>, <)은 지원하지 않음 (직접 df[df['col'] > 값] 사용)
    """
    result = df.copy()
    for col, val in conditions.items():
        if isinstance(val, list):
            result = result[result[col].isin(val)]
        else:
            result = result[result[col] == val]
    return result


def rename_columns(
    df: pd.DataFrame,
    rename_map: Dict[str, str]
) -> pd.DataFrame:
    """
    컬럼명을 변경합니다.

    pandas의 rename() 함수를 래핑합니다.
    영문 컬럼명을 한글로 바꾸거나 약어를 풀어쓸 때 사용합니다.

    Args:
        df (pd.DataFrame): 원본 데이터프레임

        rename_map (Dict[str, str]): {원래이름: 새이름} 매핑 딕셔너리.
            예: {'sido_nm': '시도명', 'pop': '인구수'}

    Returns:
        pd.DataFrame: 컬럼명이 변경된 데이터프레임

    Examples:
        >>> # 영문 → 한글 변경
        >>> df = rename_columns(df, {
        ...     'sido_nm': '시도명',
        ...     'total_pop': '총인구',
        ...     'male_pop': '남자인구',
        ...     'female_pop': '여자인구'
        ... })

        >>> # 약어 풀어쓰기
        >>> df = rename_columns(df, {
        ...     'pop': 'population',
        ...     'hh': 'household'
        ... })

    Note:
        - 존재하지 않는 컬럼명은 무시됨 (에러 발생 안함)
        - 원본 데이터프레임은 변경되지 않음
    """
    return df.rename(columns=rename_map)


def reorder_by_list(
    df: pd.DataFrame,
    col: str,
    order_list: List[str]
) -> pd.DataFrame:
    """
    지정된 순서대로 데이터프레임을 정렬합니다.

    알파벳순이나 숫자순이 아닌 특정 순서로 정렬할 때 사용합니다.
    예: 시도를 북→남 순서로, 요일을 월→일 순서로 정렬

    Args:
        df (pd.DataFrame): 원본 데이터프레임

        col (str): 정렬 기준 컬럼명.
            예: 'sido_nm', 'weekday'

        order_list (List[str]): 원하는 순서의 값 리스트.
            예: ['서울특별시', '경기도', '인천광역시', ...]
            예: ['월', '화', '수', '목', '금', '토', '일']

    Returns:
        pd.DataFrame: 지정 순서로 정렬된 데이터프레임 (복사본)

    Examples:
        >>> # 시도 순서 지정
        >>> SIDO_ORDER = [
        ...     '서울특별시', '부산광역시', '대구광역시', '인천광역시',
        ...     '광주광역시', '대전광역시', '울산광역시', '세종특별자치시',
        ...     '경기도', '강원특별자치도', '충청북도', '충청남도',
        ...     '전라북도', '전라남도', '경상북도', '경상남도', '제주특별자치도'
        ... ]
        >>> df = reorder_by_list(df, 'sido_nm', SIDO_ORDER)

        >>> # 요일 순서 지정
        >>> WEEKDAY_ORDER = ['월', '화', '수', '목', '금', '토', '일']
        >>> df = reorder_by_list(df, 'weekday', WEEKDAY_ORDER)

        >>> # 권역 순서 지정
        >>> REGION_ORDER = ['수도권', '충청권', '호남권', '영남권', '강원/제주']
        >>> df = reorder_by_list(df, '권역', REGION_ORDER)

    Note:
        - order_list에 없는 값은 맨 뒤에 배치됨
        - 정렬용 임시 컬럼은 자동 삭제됨
        - 원본 데이터프레임은 변경되지 않음
    """
    df = df.copy()
    df['_sort_order'] = df[col].apply(
        lambda x: order_list.index(x) if x in order_list else len(order_list)
    )
    df = df.sort_values('_sort_order').drop('_sort_order', axis=1)
    return df


def extract_year(
    df: pd.DataFrame,
    date_col: str,
    result_col: str = '년도'
) -> pd.DataFrame:
    """
    날짜 컬럼에서 년도를 추출하여 새 컬럼을 추가합니다.

    다양한 날짜 형식('2024-01-15', '20240115', '2024/01/15')을
    자동으로 인식하여 년도만 추출합니다.

    Args:
        df (pd.DataFrame): 원본 데이터프레임.
            날짜 또는 날짜 형식 문자열 컬럼 포함

        date_col (str): 날짜가 담긴 컬럼명.
            예: 'date', 'base_ym', '기준일자'

        result_col (str, optional): 결과 컬럼명.
            기본값: '년도'

    Returns:
        pd.DataFrame: 년도 컬럼이 추가된 데이터프레임 (복사본)

    Examples:
        >>> # 날짜에서 년도 추출
        >>> df = extract_year(df, 'date')
        >>> print(df[['date', '년도']].head())
        #         date  년도
        # 0 2024-01-15  2024
        # 1 2023-12-01  2023

        >>> # YYYYMM 형식에서 추출
        >>> df = extract_year(df, 'base_ym', 'year')
        >>> print(df[['base_ym', 'year']].head())
        #   base_ym  year
        # 0  202411  2024
        # 1  202311  2023

    Note:
        - pandas의 to_datetime()이 인식하는 형식은 모두 지원
        - 변환 불가능한 값은 NaT(Not a Time)로 처리
        - 추가로 월(.month), 일(.day) 추출도 비슷하게 가능
    """
    df = df.copy()
    df[result_col] = pd.to_datetime(df[date_col]).dt.year
    return df
