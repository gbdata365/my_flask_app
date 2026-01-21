# -*- coding: utf-8 -*-
"""
공통 설정 모듈 (Common Configuration Module)
============================================

이 모듈은 데이터 분석 및 시각화에서 사용되는 공통 상수들을 정의합니다.
그래프 크기, 색상 팔레트, 단위 변환 상수 등을 포함합니다.

상수 카테고리:
    1. 그래프 크기 (Figure Size)
       - FIGSIZE_SMALL: 소형 (8, 6)
       - FIGSIZE_MEDIUM: 중형 (12, 8) - 기본값
       - FIGSIZE_LARGE: 대형 (16, 10) - 히트맵 등
       - FIGSIZE_WIDE: 가로형 (14, 6) - 시계열 등

    2. 색상 (Colors)
       - COLORS: 용도별 색상 딕셔너리
       - COLOR_PALETTE: 다중 계열용 색상 리스트

    3. 단위 (Units)
       - UNIT_MAN: 만 (10,000)
       - UNIT_CHEON: 천 (1,000)
       - UNIT_EUK: 억 (100,000,000)

사용 예시:
    >>> from module.config import FIGSIZE_MEDIUM, COLORS
    >>> import matplotlib.pyplot as plt

    >>> fig, ax = plt.subplots(figsize=FIGSIZE_MEDIUM)
    >>> ax.bar(x, y, color=COLORS['male'])

Author: Claude AI Agent
Created: 2024-12-18
"""

from pathlib import Path

# =============================================================================
# 1. 그래프 크기 상수 (Figure Size Constants)
# =============================================================================

FIGSIZE_SMALL = (8, 6)
"""tuple: 소형 그래프 크기 (width=8, height=6 인치)
- 용도: 단순 차트, 파이 차트, 작은 막대그래프
- 예시: 성별 비율 파이차트, 간단한 비교 차트
"""

FIGSIZE_MEDIUM = (12, 8)
"""tuple: 중형 그래프 크기 (width=12, height=8 인치) - 기본값
- 용도: 일반적인 막대그래프, 선그래프
- 예시: 시도별 인구 현황, 연도별 추이
"""

FIGSIZE_LARGE = (16, 10)
"""tuple: 대형 그래프 크기 (width=16, height=10 인치)
- 용도: 히트맵, 복잡한 다중 그래프
- 예시: 시도×연령대 히트맵, 권역별 비교
"""

FIGSIZE_WIDE = (14, 6)
"""tuple: 가로로 긴 그래프 크기 (width=14, height=6 인치)
- 용도: 시계열 차트, 많은 카테고리의 막대그래프
- 예시: 월별 추이, 17개 시도 비교
"""

# =============================================================================
# 2. 색상 상수 (Color Constants)
# =============================================================================

COLORS = {
    'male': '#4A90D9',      # 파란색 - 남자
    'female': '#E57373',    # 빨간색 - 여자
    'total': '#66BB6A',     # 초록색 - 전체/합계
    'highlight': '#FFA726', # 주황색 - 강조/하이라이트
    'primary': '#2196F3',   # 파란색 - 주요 항목
    'secondary': '#9C27B0', # 보라색 - 보조 항목
    'single': '#9C27B0',    # 보라색 - 1인세대
    'gray': '#78909C',      # 회색 - 비활성/참고
}
"""dict: 용도별 색상 딕셔너리

키 설명:
    - male: 남자 관련 데이터 (파란색 계열)
    - female: 여자 관련 데이터 (빨간색 계열)
    - total: 전체/합계 데이터 (초록색 계열)
    - highlight: 강조가 필요한 데이터 (주황색)
    - primary: 주요 데이터 (파란색)
    - secondary: 보조 데이터 (보라색)
    - single: 1인세대 데이터 (보라색)
    - gray: 비활성 또는 참고 데이터 (회색)

사용 예시:
    >>> ax.bar(x, male_data, color=COLORS['male'], label='남자')
    >>> ax.bar(x, female_data, color=COLORS['female'], label='여자')
"""

COLOR_PALETTE = [
    '#2196F3',  # 파란색
    '#4CAF50',  # 초록색
    '#FFC107',  # 노란색
    '#E91E63',  # 분홍색
    '#9C27B0',  # 보라색
    '#00BCD4',  # 청록색
    '#FF5722',  # 주황색
    '#795548',  # 갈색
]
"""list: 다중 계열용 색상 팔레트 (8색)

여러 카테고리를 구분해야 할 때 순서대로 사용합니다.
예: 8개 권역 비교, 연령대별 비교

사용 예시:
    >>> for i, category in enumerate(categories):
    ...     ax.plot(x, data[category], color=COLOR_PALETTE[i % len(COLOR_PALETTE)])
"""

# =============================================================================
# 3. 단위 상수 (Unit Constants)
# =============================================================================

UNIT_MAN = 10000
"""int: 만 단위 (10,000)
- 용도: 인구수를 만 명 단위로 변환
- 예시: 51,000,000명 → 5,100만 명
"""

UNIT_CHEON = 1000
"""int: 천 단위 (1,000)
- 용도: 소규모 데이터를 천 단위로 변환
- 예시: 50,000명 → 50천 명
"""

UNIT_EUK = 100000000
"""int: 억 단위 (100,000,000)
- 용도: 금액 데이터를 억 원 단위로 변환
- 예시: 1,000,000,000원 → 10억 원
"""

# =============================================================================
# 4. 한글 폰트 설정 (Korean Font Setup)
# =============================================================================

try:
    import koreanize_matplotlib
    # koreanize_matplotlib 임포트 시 자동으로 한글 폰트가 설정됨
    # matplotlib에서 한글이 깨지지 않고 정상 출력됨
except ImportError:
    # koreanize_matplotlib이 설치되지 않은 경우 경고 없이 통과
    # 이 경우 한글이 깨질 수 있으므로 별도 폰트 설정 필요
    pass

# =============================================================================
# 5. 유틸리티 함수 (Utility Functions)
# =============================================================================

def ensure_dir(path):
    """
    디렉토리가 존재하지 않으면 생성합니다.

    이미 존재하는 디렉토리도 에러 없이 처리됩니다 (exist_ok=True).
    중첩된 디렉토리도 한 번에 생성됩니다 (parents=True).

    Args:
        path (str or Path): 생성할 디렉토리 경로
            예: './output/images', 'C:/data/results'

    Returns:
        Path: 생성된 (또는 이미 존재하는) 디렉토리의 Path 객체

    Examples:
        >>> output_dir = ensure_dir('./output/images')
        >>> print(output_dir)
        output/images

        >>> # 파일 저장 시 활용
        >>> filepath = ensure_dir('./results') / 'chart.png'
        >>> fig.savefig(filepath)

    Note:
        - 상대 경로, 절대 경로 모두 지원
        - Windows, Linux, Mac 모두 호환
    """
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)
