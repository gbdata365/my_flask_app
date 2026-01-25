# -*- coding: utf-8 -*-
"""
================================================================================
차트 설정 파일 (chart_config.py)
================================================================================

차트에 표시되는 단위, 포맷 등을 설정합니다.
.env 파일에서 단위를 변경할 수 있습니다.

[.env 설정 예시]
    CHART_POPULATION_UNIT=10000
    CHART_POPULATION_LABEL=만 명
    CHART_HOUSEHOLD_UNIT=100
    CHART_HOUSEHOLD_LABEL=백 가구

[단위 옵션]
- 'unit': 1 (원본), 100 (백), 1000 (천), 10000 (만)
- 'label': 단위 라벨 (예: '백 가구', '만 명')
- 'format': 숫자 포맷 (예: '{:,.0f}', '{:,.1f}')

================================================================================
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
_config_dir = Path(__file__).parent
_env_paths = [
    _config_dir / '.env',                    # config/.env
    _config_dir.parent / '.env',             # 01_인구및가구현황/.env
    _config_dir.parent.parent / 'module' / '.env',  # module/.env
]

for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

# =============================================================================
# 환경변수에서 단위 설정 읽기 (기본값: 1)
# =============================================================================
def _get_unit_label(unit_value):
    """단위 값에 따른 기본 라벨 반환"""
    labels = {1: '명', 100: '백 명', 1000: '천 명', 10000: '만 명'}
    return labels.get(unit_value, '명')

def _get_household_label(unit_value):
    """가구 단위 값에 따른 기본 라벨 반환"""
    labels = {1: '가구', 100: '백 가구', 1000: '천 가구', 10000: '만 가구'}
    return labels.get(unit_value, '가구')

# =============================================================================
# 인구 차트 단위 설정
# =============================================================================
_pop_unit = int(os.environ.get('CHART_POPULATION_UNIT', '1'))
POPULATION_UNIT = {
    'unit': _pop_unit,
    'label': os.environ.get('CHART_POPULATION_LABEL', _get_unit_label(_pop_unit)),
    'format': '{:,.0f}',
}

# =============================================================================
# 가구 차트 단위 설정
# =============================================================================
_hh_unit = int(os.environ.get('CHART_HOUSEHOLD_UNIT', '1'))
HOUSEHOLD_UNIT = {
    'unit': _hh_unit,
    'label': os.environ.get('CHART_HOUSEHOLD_LABEL', _get_household_label(_hh_unit)),
    'format': '{:,.0f}',
}

# =============================================================================
# 1인가구 차트 단위 설정
# =============================================================================
_single_unit = int(os.environ.get('CHART_SINGLE_HOUSEHOLD_UNIT', '1'))
SINGLE_HOUSEHOLD_UNIT = {
    'unit': _single_unit,
    'label': os.environ.get('CHART_SINGLE_HOUSEHOLD_LABEL', _get_household_label(_single_unit)),
    'format': '{:,.0f}',
}

# =============================================================================
# 연령별 1인가구 차트 단위 설정
# =============================================================================
_single_age_unit = int(os.environ.get('CHART_SINGLE_AGE_UNIT', '1'))
SINGLE_AGE_UNIT = {
    'unit': _single_age_unit,
    'label': os.environ.get('CHART_SINGLE_AGE_LABEL', _get_household_label(_single_age_unit)),
    'format': '{:,.0f}',
}

# =============================================================================
# 지역별 서브플롯 설정
# =============================================================================
REGIONAL_SUBPLOT = {
    'max_regions': None,  # None이면 전체 표시, 숫자면 해당 개수만 표시
    'cols': 3,            # 열 개수 (한 행에 3개)
    'fig_width_per_col': 5,   # 열당 너비
    'fig_height_per_row': 4,  # 행당 높이
}

# =============================================================================
# 아코디언 테이블 설정
# =============================================================================
ACCORDION_TABLE = {
    'expand_all': True,   # True면 전체 펼침, False면 첫 번째만 펼침
}


# =============================================================================
# 단위 변경 헬퍼 함수
# =============================================================================
def get_unit_config(chart_type='population'):
    """
    차트 타입에 따른 단위 설정 반환

    Args:
        chart_type: 'population', 'household', 'single', 'single_age'

    Returns:
        dict: unit, label, format
    """
    configs = {
        'population': POPULATION_UNIT,
        'household': HOUSEHOLD_UNIT,
        'single': SINGLE_HOUSEHOLD_UNIT,
        'single_age': SINGLE_AGE_UNIT,
    }
    return configs.get(chart_type, POPULATION_UNIT)


def format_value(value, chart_type='population'):
    """
    값을 단위에 맞게 변환하고 포맷팅

    Args:
        value: 원본 값
        chart_type: 차트 타입

    Returns:
        str: 포맷팅된 문자열
    """
    config = get_unit_config(chart_type)
    converted = value / config['unit']
    return config['format'].format(converted)


def convert_value(value, chart_type='population'):
    """
    값을 단위에 맞게 변환 (포맷팅 없이)

    Args:
        value: 원본 값
        chart_type: 차트 타입

    Returns:
        float: 변환된 값
    """
    config = get_unit_config(chart_type)
    return value / config['unit']
