# -*- coding: utf-8 -*-
"""
공통 분석 모듈 패키지 (Common Analysis Module Package)
======================================================

이 패키지는 다양한 데이터 분석 프로젝트에서 공통으로 사용되는
시각화, 집계, 변환 함수들을 제공합니다.

패키지 구조:
    - config.py: 그래프 크기, 색상, 단위 등 상수 정의
    - db.py: PostgreSQL 데이터베이스 연결 함수
    - visualizers.py: 6가지 시각화 함수 (막대, 선, 히트맵, 피라미드 등)
    - aggregators.py: 5가지 집계 함수 (그룹별 집계, 비율 계산 등)
    - transforms.py: 9가지 데이터 변환 함수 (권역 추가, 피벗 등)

사용 예시:
    >>> from module import plot_horizontal_bar, aggregate_by_group
    >>> from module import COLORS, FIGSIZE_MEDIUM
    >>> from module import get_db_connection

    >>> # 데이터 집계 후 시각화
    >>> df_agg = aggregate_by_group(df, ['sido_nm'], ['total_pop'])
    >>> plot_horizontal_bar(df_agg, 'sido_nm', 'total_pop', '시도별 인구')

지원 분야:
    - 01_population: 인구통계
    - 02_economy: 경제/산업 (예정)
    - 03_environment: 환경/기상 (예정)
    - 04_traffic: 교통/물류 (예정)
    - 05_welfare: 복지/의료 (예정)

Author: Claude AI Agent
Version: 1.0.0
Created: 2024-12-18
"""

# =============================================================================
# 모듈 임포트 (Module Imports)
# =============================================================================

# config.py에서 상수들을 가져옴 (* 사용으로 모든 public 변수 임포트)
from .config import *

# db.py에서 데이터베이스 연결 함수 가져옴
from .db import get_db_connection

# visualizers.py에서 시각화 함수들을 가져옴
from .visualizers import *

# aggregators.py에서 집계 함수들을 가져옴
from .aggregators import *

# transforms.py에서 변환 함수들을 가져옴
from .transforms import *

# llm_client.py에서 LLM 클라이언트 가져옴
from .llm_client import LLMClient

# text_to_sql.py에서 Text-to-SQL 기능 가져옴
from .text_to_sql import TextToSQL, SchemaExtractor

# ontology_loader.py에서 온톨로지 로더 가져옴
from .ontology_loader import OntologyLoader

# =============================================================================
# 패키지 메타데이터 (Package Metadata)
# =============================================================================

__version__ = '1.0.0'
__author__ = 'Claude AI Agent'
__all__ = [
    # config
    'FIGSIZE_SMALL', 'FIGSIZE_MEDIUM', 'FIGSIZE_LARGE', 'FIGSIZE_WIDE',
    'COLORS', 'COLOR_PALETTE', 'UNIT_MAN', 'UNIT_CHEON', 'UNIT_EUK',
    'ensure_dir',
    # db
    'get_db_connection',
    # visualizers
    'save_figure', 'plot_horizontal_bar', 'plot_grouped_bar',
    'plot_dual_axis', 'plot_heatmap', 'plot_pyramid', 'plot_line',
    # aggregators
    'aggregate_by_group', 'calculate_ratio', 'convert_unit',
    'pivot_for_heatmap', 'merge_dataframes',
    # transforms
    'add_region', 'add_category', 'add_age_group', 'wide_to_long',
    'long_to_wide', 'filter_rows', 'rename_columns', 'reorder_by_list',
    'extract_year',
    # llm
    'LLMClient',
    # text_to_sql
    'TextToSQL', 'SchemaExtractor',
    # ontology
    'OntologyLoader',
]
