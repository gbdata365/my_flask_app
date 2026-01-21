# -*- coding: utf-8 -*-
"""
공통 시각화 모듈 (Common Visualization Module)
==============================================

이 모듈은 데이터 분석에서 자주 사용되는 6가지 차트 함수를 제공합니다.
모든 함수는 매개변수화되어 있어 다양한 데이터에 재사용 가능합니다.

제공 함수:
    1. plot_horizontal_bar(): 수평 막대그래프
    2. plot_grouped_bar(): 그룹형 수직 막대그래프
    3. plot_dual_axis(): 이중축 차트 (막대 + 선)
    4. plot_heatmap(): 히트맵
    5. plot_pyramid(): 인구 피라미드
    6. plot_line(): 선 그래프

공통 매개변수:
    - data: pandas DataFrame
    - title: 그래프 제목
    - filename: 저장할 파일명
    - output_dir: 저장 디렉토리 (기본: ./output/images)
    - unit_divisor: 단위 변환 값 (기본: 10000 = 만)
    - figsize: 그래프 크기

사용 예시:
    >>> from module.visualizers import plot_horizontal_bar
    >>> plot_horizontal_bar(
    ...     data=df,
    ...     x_col='sido_nm',
    ...     y_col='total_pop',
    ...     title='시도별 인구 현황',
    ...     filename='sido_pop.png'
    ... )

Author: Claude AI Agent
Created: 2024-12-18
"""

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger
from .config import FIGSIZE_MEDIUM, FIGSIZE_WIDE, FIGSIZE_LARGE, COLORS, ensure_dir


# =============================================================================
# 헬퍼 함수 (Helper Functions)
# =============================================================================

def save_figure(fig, filename: str, output_dir: str = './output/images', dpi: int = 150):
    """
    matplotlib Figure를 이미지 파일로 저장합니다.

    저장 후 자동으로 Figure를 닫아 메모리를 해제합니다.
    출력 디렉토리가 없으면 자동 생성됩니다.

    Args:
        fig (matplotlib.figure.Figure): 저장할 Figure 객체

        filename (str): 저장할 파일명.
            확장자에 따라 포맷 결정 (png, jpg, pdf, svg 등)
            예: 'chart.png', 'report_fig1.pdf'

        output_dir (str, optional): 저장 디렉토리 경로.
            기본값: './output/images'
            절대/상대 경로 모두 지원

        dpi (int, optional): 해상도 (dots per inch).
            기본값: 150
            인쇄용: 300, 웹용: 72~150

    Returns:
        pathlib.Path: 저장된 파일의 전체 경로

    Examples:
        >>> fig, ax = plt.subplots()
        >>> ax.bar(['A', 'B', 'C'], [1, 2, 3])
        >>> filepath = save_figure(fig, 'test.png')
        >>> print(filepath)  # output/images/test.png

    Note:
        - 배경색은 흰색(white)으로 고정
        - bbox_inches='tight'로 여백 최소화
        - Figure는 저장 후 자동 close (메모리 해제)
    """
    # 출력 디렉토리 생성 (없으면)
    path = ensure_dir(output_dir)
    filepath = path / filename

    # Figure 저장 (흰색 배경, 여백 최소화)
    fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
    logger.info(f"이미지 저장: {filepath}")

    # 메모리 해제를 위해 Figure 닫기
    plt.close(fig)

    return filepath


# =============================================================================
# 1. 수평 막대그래프 (Horizontal Bar Chart)
# =============================================================================

def plot_horizontal_bar(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    filename: str,
    output_dir: str = './output/images',
    color: str = None,
    unit_divisor: float = 10000,
    unit_label: str = "만",
    figsize: tuple = None,
    show_values: bool = True,
    sort_by: str = None,
    sort_ascending: bool = False
):
    """
    수평 막대그래프를 생성합니다.

    카테고리별 값을 수평 막대로 시각화합니다.
    시도별 인구, 항목별 순위 등에 적합합니다.

    Args:
        data (pd.DataFrame): 시각화할 데이터프레임

        x_col (str): X축(카테고리) 컬럼명.
            예: 'sido_nm', 'category', 'product_name'

        y_col (str): Y축(값) 컬럼명.
            예: 'total_pop', 'sales', 'count'

        title (str): 그래프 제목.
            예: '시도별 인구 현황', '제품별 판매량'

        filename (str): 저장할 파일명.
            예: 'sido_population.png'

        output_dir (str, optional): 저장 디렉토리.
            기본값: './output/images'

        color (str, optional): 막대 색상.
            None이면 COLORS['total'] 사용
            예: '#4A90D9', 'blue', COLORS['male']

        unit_divisor (float, optional): 단위 변환 나눗수.
            기본값: 10000 (만 단위)
            예: 1000 (천 단위), 1 (원본)

        unit_label (str, optional): 단위 라벨.
            기본값: "만"
            예: "천", "억", "명"

        figsize (tuple, optional): 그래프 크기 (width, height).
            None이면 FIGSIZE_MEDIUM 사용

        show_values (bool, optional): 막대 끝에 값 표시 여부.
            기본값: True

        sort_by (str, optional): 정렬 기준 컬럼.
            None이면 정렬 안함
            예: 'total_pop' (값 기준), 'sido_nm' (이름 기준)

        sort_ascending (bool, optional): 오름차순 정렬 여부.
            기본값: False (내림차순)

    Returns:
        pathlib.Path: 저장된 파일 경로

    Examples:
        >>> # 기본 사용
        >>> plot_horizontal_bar(
        ...     df, 'sido_nm', 'total_pop',
        ...     '시도별 인구', 'sido_pop.png'
        ... )

        >>> # 정렬 및 색상 지정
        >>> plot_horizontal_bar(
        ...     df, 'product', 'sales',
        ...     '제품별 매출', 'product_sales.png',
        ...     color='#2196F3',
        ...     sort_by='sales',
        ...     sort_ascending=False
        ... )
    """
    # 데이터 복사 및 정렬
    df = data.copy()
    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=sort_ascending)

    # Figure 생성
    fig, ax = plt.subplots(figsize=figsize or FIGSIZE_MEDIUM)

    # 색상 설정 (없으면 기본 색상)
    color = color or COLORS.get('total')

    # 단위 변환된 값
    values = df[y_col] / unit_divisor

    # 수평 막대 그리기
    bars = ax.barh(df[x_col], values, color=color)

    # 막대 끝에 값 표시
    if show_values:
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + (values.max() * 0.02),  # 막대 끝에서 약간 오른쪽
                bar.get_y() + bar.get_height() / 2,       # 막대 중앙
                f'{val:,.1f}',                            # 천 단위 콤마, 소수점 1자리
                va='center',
                fontsize=9
            )

    # 축 라벨 및 제목
    ax.set_xlabel(f'{y_col} ({unit_label})')
    ax.set_title(title)

    plt.tight_layout()
    return save_figure(fig, filename, output_dir)


# =============================================================================
# 2. 그룹형 수직 막대그래프 (Grouped Vertical Bar Chart)
# =============================================================================

def plot_grouped_bar(
    data: pd.DataFrame,
    x_col: str,
    value_cols: list,
    labels: list,
    colors: list = None,
    title: str = '',
    filename: str = 'grouped_bar.png',
    output_dir: str = './output/images',
    unit_divisor: float = 10000,
    unit_label: str = "만",
    figsize: tuple = None,
    rotation: int = 45
):
    """
    그룹형 수직 막대그래프를 생성합니다.

    여러 값을 나란히 비교하는 그래프입니다.
    남/여 인구 비교, 연도별 비교 등에 적합합니다.

    Args:
        data (pd.DataFrame): 시각화할 데이터프레임

        x_col (str): X축(카테고리) 컬럼명.
            예: 'sido_nm', 'year', 'product'

        value_cols (list): 비교할 값 컬럼명 리스트.
            예: ['male_pop', 'female_pop']
            예: ['sales_2023', 'sales_2024']

        labels (list): 범례에 표시할 라벨 리스트.
            value_cols와 같은 순서.
            예: ['남자', '여자'], ['2023년', '2024년']

        colors (list, optional): 막대 색상 리스트.
            None이면 male/female 색상 사용
            예: ['#4A90D9', '#E57373']

        title (str, optional): 그래프 제목.
            기본값: '' (제목 없음)

        filename (str, optional): 저장할 파일명.
            기본값: 'grouped_bar.png'

        output_dir (str, optional): 저장 디렉토리.
            기본값: './output/images'

        unit_divisor (float, optional): 단위 변환 나눗수.
            기본값: 10000 (만 단위)

        unit_label (str, optional): Y축 단위 라벨.
            기본값: "만"

        figsize (tuple, optional): 그래프 크기.
            None이면 FIGSIZE_WIDE 사용

        rotation (int, optional): X축 라벨 회전 각도.
            기본값: 45도
            예: 0 (수평), 90 (수직)

    Returns:
        pathlib.Path: 저장된 파일 경로

    Examples:
        >>> # 남녀 인구 비교
        >>> plot_grouped_bar(
        ...     df, 'sido_nm',
        ...     ['male_pop', 'female_pop'],
        ...     ['남자', '여자'],
        ...     title='시도별 남녀 인구',
        ...     filename='gender_compare.png'
        ... )
    """
    fig, ax = plt.subplots(figsize=figsize or FIGSIZE_WIDE)

    # 색상 설정 (없으면 기본 남/여 색상)
    colors = colors or [COLORS.get('male'), COLORS.get('female')]

    # X축 위치 계산
    x = np.arange(len(data))
    width = 0.8 / len(value_cols)  # 막대 너비

    # 각 값 컬럼별로 막대 그리기
    for i, (col, label, color) in enumerate(zip(value_cols, labels, colors)):
        offset = (i - len(value_cols) / 2 + 0.5) * width  # 중앙 정렬을 위한 오프셋
        values = data[col] / unit_divisor
        ax.bar(x + offset, values, width, label=label, color=color)

    # 축 설정
    ax.set_ylabel(f'값 ({unit_label})')
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(data[x_col], rotation=rotation, ha='right')
    ax.legend()

    plt.tight_layout()
    return save_figure(fig, filename, output_dir)


# =============================================================================
# 3. 이중축 차트 (Dual Axis Chart)
# =============================================================================

def plot_dual_axis(
    data: pd.DataFrame,
    x_col: str,
    bar_col: str,
    line_col: str,
    title: str,
    filename: str,
    output_dir: str = './output/images',
    bar_label: str = "막대",
    line_label: str = "비율",
    bar_color: str = None,
    line_color: str = None,
    bar_divisor: float = 10000,
    bar_unit: str = "만",
    line_unit: str = "%",
    figsize: tuple = None
):
    """
    이중축 차트를 생성합니다 (막대 + 선).

    왼쪽 Y축: 막대그래프 (절대값)
    오른쪽 Y축: 선그래프 (비율 등)

    인구수와 비율, 매출액과 성장률 등을 동시에 표현할 때 사용합니다.

    Args:
        data (pd.DataFrame): 시각화할 데이터프레임

        x_col (str): X축(카테고리) 컬럼명.
            예: 'sido_nm', 'month'

        bar_col (str): 막대그래프용 값 컬럼명 (왼쪽 Y축).
            예: 'total_pop', 'sales'

        line_col (str): 선그래프용 값 컬럼명 (오른쪽 Y축).
            예: 'single_ratio', 'growth_rate'

        title (str): 그래프 제목

        filename (str): 저장할 파일명

        output_dir (str, optional): 저장 디렉토리.
            기본값: './output/images'

        bar_label (str, optional): 막대 범례 라벨.
            기본값: "막대"

        line_label (str, optional): 선 범례 라벨.
            기본값: "비율"

        bar_color (str, optional): 막대 색상.
            None이면 COLORS['single'] 사용

        line_color (str, optional): 선 색상.
            None이면 COLORS['highlight'] 사용

        bar_divisor (float, optional): 막대 값 단위 변환.
            기본값: 10000

        bar_unit (str, optional): 막대 Y축 단위.
            기본값: "만"

        line_unit (str, optional): 선 Y축 단위.
            기본값: "%"

        figsize (tuple, optional): 그래프 크기

    Returns:
        pathlib.Path: 저장된 파일 경로

    Examples:
        >>> # 인구수와 1인세대 비율
        >>> plot_dual_axis(
        ...     df, 'sido_nm',
        ...     bar_col='total_pop',
        ...     line_col='single_ratio',
        ...     title='시도별 인구 및 1인세대 비율',
        ...     filename='pop_single_ratio.png',
        ...     bar_label='인구',
        ...     line_label='1인세대비율'
        ... )
    """
    fig, ax1 = plt.subplots(figsize=figsize or FIGSIZE_WIDE)

    # 색상 설정
    bar_color = bar_color or COLORS.get('single')
    line_color = line_color or COLORS.get('highlight')

    x = np.arange(len(data))

    # 막대 그래프 (왼쪽 Y축)
    ax1.bar(x, data[bar_col] / bar_divisor, 0.6,
            label=bar_label, color=bar_color, alpha=0.7)
    ax1.set_ylabel(f'{bar_label} ({bar_unit})', color=bar_color)
    ax1.tick_params(axis='y', labelcolor=bar_color)

    # 선 그래프 (오른쪽 Y축)
    ax2 = ax1.twinx()  # 두 번째 Y축 생성
    ax2.plot(x, data[line_col], 'o-',
             color=line_color, linewidth=2, markersize=8, label=line_label)
    ax2.set_ylabel(f'{line_label} ({line_unit})', color=line_color)
    ax2.tick_params(axis='y', labelcolor=line_color)

    # X축 설정
    ax1.set_title(title)
    ax1.set_xticks(x)
    ax1.set_xticklabels(data[x_col], rotation=45, ha='right')

    # 범례 통합
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    plt.tight_layout()
    return save_figure(fig, filename, output_dir)


# =============================================================================
# 4. 히트맵 (Heatmap)
# =============================================================================

def plot_heatmap(
    data: pd.DataFrame,
    title: str,
    filename: str,
    output_dir: str = './output/images',
    cmap: str = 'YlOrRd',
    annot: bool = True,
    fmt: str = '.0f',
    cbar_label: str = "값",
    figsize: tuple = None
):
    """
    히트맵을 생성합니다.

    2차원 매트릭스 데이터를 색상으로 시각화합니다.
    시도×연령대, 월×카테고리 등의 교차 분석에 적합합니다.

    Args:
        data (pd.DataFrame): 피벗된 데이터프레임.
            행: 카테고리1, 열: 카테고리2, 값: 셀 값
            pivot_for_heatmap() 함수로 생성 권장

        title (str): 그래프 제목

        filename (str): 저장할 파일명

        output_dir (str, optional): 저장 디렉토리.
            기본값: './output/images'

        cmap (str, optional): 컬러맵.
            기본값: 'YlOrRd' (노랑→주황→빨강)
            다른 옵션: 'Blues', 'Greens', 'RdBu', 'coolwarm'

        annot (bool, optional): 셀에 값 표시 여부.
            기본값: True

        fmt (str, optional): 값 표시 포맷.
            기본값: '.0f' (정수)
            예: '.1f' (소수점 1자리), '.2%' (퍼센트)

        cbar_label (str, optional): 컬러바 라벨.
            기본값: "값"

        figsize (tuple, optional): 그래프 크기.
            None이면 FIGSIZE_LARGE 사용

    Returns:
        pathlib.Path: 저장된 파일 경로

    Examples:
        >>> # 시도×연령대 인구 히트맵
        >>> pivot_df = pivot_for_heatmap(df, 'sido_nm', 'age_group', 'population')
        >>> plot_heatmap(
        ...     pivot_df,
        ...     '시도별 연령대별 인구',
        ...     'sido_age_heatmap.png',
        ...     cmap='Blues'
        ... )
    """
    fig, ax = plt.subplots(figsize=figsize or FIGSIZE_LARGE)

    # seaborn 히트맵 생성
    sns.heatmap(
        data,
        cmap=cmap,
        annot=annot,
        fmt=fmt,
        cbar_kws={'label': cbar_label},
        ax=ax
    )

    ax.set_title(title)
    plt.tight_layout()

    return save_figure(fig, filename, output_dir)


# =============================================================================
# 5. 피라미드 그래프 (Population Pyramid)
# =============================================================================

def plot_pyramid(
    data: pd.DataFrame,
    left_col: str,
    right_col: str,
    y_col: str,
    title: str,
    filename: str,
    output_dir: str = './output/images',
    left_label: str = "남자",
    right_label: str = "여자",
    left_color: str = None,
    right_color: str = None,
    unit_divisor: float = 1000,
    figsize: tuple = None
):
    """
    인구 피라미드 그래프를 생성합니다.

    좌우 대칭 수평 막대그래프로, 성별-연령대 분포를 시각화합니다.
    왼쪽: 남자 (음수 방향), 오른쪽: 여자 (양수 방향)

    Args:
        data (pd.DataFrame): 시각화할 데이터프레임.
            연령대별 남/여 인구 데이터 필요

        left_col (str): 왼쪽(남자) 값 컬럼명.
            예: 'male_pop', 'male_count'

        right_col (str): 오른쪽(여자) 값 컬럼명.
            예: 'female_pop', 'female_count'

        y_col (str): Y축(연령대) 컬럼명.
            예: 'age_group', 'age_range'

        title (str): 그래프 제목

        filename (str): 저장할 파일명

        output_dir (str, optional): 저장 디렉토리.
            기본값: './output/images'

        left_label (str, optional): 왼쪽 범례 라벨.
            기본값: "남자"

        right_label (str, optional): 오른쪽 범례 라벨.
            기본값: "여자"

        left_color (str, optional): 왼쪽 막대 색상.
            None이면 COLORS['male'] 사용

        right_color (str, optional): 오른쪽 막대 색상.
            None이면 COLORS['female'] 사용

        unit_divisor (float, optional): 단위 변환.
            기본값: 1000 (천 명)

        figsize (tuple, optional): 그래프 크기.
            None이면 FIGSIZE_MEDIUM 사용

    Returns:
        pathlib.Path: 저장된 파일 경로

    Examples:
        >>> # 연령대별 인구 피라미드
        >>> plot_pyramid(
        ...     df, 'male_pop', 'female_pop', 'age_group',
        ...     '대한민국 인구 피라미드',
        ...     'population_pyramid.png'
        ... )
    """
    fig, ax = plt.subplots(figsize=figsize or FIGSIZE_MEDIUM)

    # 색상 설정
    left_color = left_color or COLORS.get('male')
    right_color = right_color or COLORS.get('female')

    y = data[y_col]
    left_vals = data[left_col] / unit_divisor
    right_vals = data[right_col] / unit_divisor

    # 왼쪽 막대 (음수 방향으로)
    ax.barh(y, -left_vals, height=0.8, color=left_color, label=left_label)

    # 오른쪽 막대 (양수 방향으로)
    ax.barh(y, right_vals, height=0.8, color=right_color, label=right_label)

    # X축 범위 대칭 설정
    max_val = max(left_vals.max(), right_vals.max())
    ax.set_xlim(-max_val * 1.1, max_val * 1.1)

    # 중앙선
    ax.axvline(0, color='black', linewidth=0.5)

    ax.set_title(title)
    ax.legend(loc='upper right')

    plt.tight_layout()
    return save_figure(fig, filename, output_dir)


# =============================================================================
# 6. 선 그래프 (Line Chart)
# =============================================================================

def plot_line(
    data: pd.DataFrame,
    x_col: str,
    y_cols: list,
    labels: list,
    colors: list = None,
    title: str = '',
    filename: str = 'line.png',
    output_dir: str = './output/images',
    unit_divisor: float = 10000,
    unit_label: str = "만",
    figsize: tuple = None,
    markers: list = None
):
    """
    선 그래프를 생성합니다.

    시계열 데이터나 연속적인 변화를 시각화합니다.
    여러 계열을 동시에 비교할 수 있습니다.

    Args:
        data (pd.DataFrame): 시각화할 데이터프레임

        x_col (str): X축 컬럼명.
            예: 'base_ym', 'year', 'month'

        y_cols (list): Y축 값 컬럼명 리스트.
            예: ['total_pop'], ['male_pop', 'female_pop']

        labels (list): 범례 라벨 리스트.
            y_cols와 같은 순서.
            예: ['총인구'], ['남자', '여자']

        colors (list, optional): 선 색상 리스트.
            None이면 기본 팔레트 사용

        title (str, optional): 그래프 제목.
            기본값: ''

        filename (str, optional): 저장할 파일명.
            기본값: 'line.png'

        output_dir (str, optional): 저장 디렉토리.
            기본값: './output/images'

        unit_divisor (float, optional): 단위 변환.
            기본값: 10000

        unit_label (str, optional): Y축 단위 라벨.
            기본값: "만"

        figsize (tuple, optional): 그래프 크기.
            None이면 FIGSIZE_WIDE 사용

        markers (list, optional): 마커 스타일 리스트.
            None이면 ['o', 's', '^', 'D'] 순환 사용
            예: ['o', 's'] (원, 사각형)

    Returns:
        pathlib.Path: 저장된 파일 경로

    Examples:
        >>> # 월별 인구 추이
        >>> plot_line(
        ...     df, 'base_ym',
        ...     ['total_pop'],
        ...     ['총인구'],
        ...     title='월별 인구 추이',
        ...     filename='monthly_trend.png'
        ... )

        >>> # 남녀 인구 추이 비교
        >>> plot_line(
        ...     df, 'year',
        ...     ['male_pop', 'female_pop'],
        ...     ['남자', '여자'],
        ...     colors=['#4A90D9', '#E57373'],
        ...     title='연도별 남녀 인구 추이'
        ... )
    """
    fig, ax = plt.subplots(figsize=figsize or FIGSIZE_WIDE)

    # 기본 색상 및 마커
    colors = colors or ['#2196F3', '#4CAF50', '#FFC107', '#E91E63']
    markers = markers or ['o', 's', '^', 'D']

    # 각 Y 컬럼별로 선 그리기
    for i, (col, label) in enumerate(zip(y_cols, labels)):
        ax.plot(
            data[x_col],
            data[col] / unit_divisor,
            marker=markers[i % len(markers)],
            color=colors[i % len(colors)],
            label=label,
            linewidth=2
        )

    ax.set_ylabel(f'값 ({unit_label})')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)

    # X축 라벨 자동 회전
    fig.autofmt_xdate()

    plt.tight_layout()
    return save_figure(fig, filename, output_dir)
