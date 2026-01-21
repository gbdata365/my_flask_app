# -*- coding: utf-8 -*-
"""
데이터콩 공통 모듈 (DataCong Core Module)
=========================================

여러 도메인에서 공통으로 사용하는 데이터콩 챗봇 기능을 제공합니다.

주요 기능:
    1. 차트 생성 (generate_chart)
    2. CSV 다운로드 데이터 생성
    3. HTML 포맷팅 (테이블, LLM 답변)
    4. CSS 스타일
    5. 결과 렌더링

사용법:
    각 도메인의 데이터콩.py에서 이 모듈을 import하여 사용합니다.

    >>> from module.datacong_core import DataCongCore
    >>> core = DataCongCore(
    ...     domain_name="인구통계",
    ...     domain_base=Path(__file__).parent.parent,
    ...     example_questions=["고령화율 높은 지역", ...]
    ... )
    >>> html = core.render(request_args)

Author: Claude AI Agent
Created: 2025-01-12
"""

import io
import re
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

import pandas as pd

# GUI 백엔드 문제 방지 (Flask 스레드 환경용)
import matplotlib
matplotlib.use('Agg')  # 비-GUI 백엔드 사용

import matplotlib.pyplot as plt
import koreanize_matplotlib
from loguru import logger


# =============================================================================
# 차트 관련 상수
# =============================================================================

CHART_KEYWORDS: List[str] = ['차트', '그래프', '시각화', '비교 차트', '막대', '바차트', '파이']

# 그룹 막대 차트 키워드 (여러 카테고리를 색상으로 구분, 나란히 배치)
GROUPED_CHART_KEYWORDS: List[str] = [
    '그룹별', '항목별', '카테고리별',
    '색상으로 구분', '색별로', '그룹 차트',
    '비교 막대', '다중 막대', '나란히'
]

# 100% 누적 막대 차트 키워드 (비율로 구분, 전체 100%)
STACKED_CHART_KEYWORDS: List[str] = [
    '누적', '스택', '100%', '백분율', '비율 차트', '비율로',
    '구성비', '점유율', '비중', '연령별', '연령그룹별',
    '구성 차트', '비율 비교'
]

# 동적 차트 키워드 (LLM이 직접 코드 생성)
DYNAMIC_CHART_KEYWORDS: List[str] = [
    '꺾은선', '선 그래프', '선그래프', '라인', 'line',
    '파이', '원형', '도넛', 'pie',
    '산점도', '스캐터', 'scatter', '분포도',
    '히스토그램', 'histogram', '분포',
    '박스플롯', 'boxplot', '상자그림',
    '히트맵', 'heatmap', '열지도',
    '영역', 'area', '면적',
    '버블', 'bubble',
    '레이더', 'radar', '방사형',
    '커스텀', '직접', '자유형'
]

# 시계열 분석 키워드
TIMESERIES_KEYWORDS: List[str] = [
    '추이', '트렌드', '변화 추이', '월별 추이', '연도별',
    '전월 대비', '지난달 대비', '전월대비',
    '전년 동월', '전년동월', '작년 대비', '전년대비', 'YoY', 'MoM',
    '최근 6개월', '최근 12개월', '최근 1년', '최근 2년',
    '기간별', '시계열'
]

LLM_DISPLAY_NAMES: Dict[str, str] = {
    # 가성비 모델 (상위 추천)
    'solar': 'Solar Pro',    
    'claude-haiku': 'Claude 3.5 Haiku ($0.8/1M)',
    'openai': 'GPT-4o-mini ($0.15/1M)',
    #'claude-3-haiku': 'Claude 3 Haiku ($0.25/1M)',
    'gpt-3.5-turbo': 'GPT-3.5 Turbo ($0.5/1M)',
    #'solar-mini': 'Solar Mini',
    # 고성능 모델
    'claude': 'Claude Sonnet 4 ($3/1M)',
    'gpt-4o': 'GPT-4o ($2.5/1M)',
}

# LLM 자동 전환 순서 (rate limit 시 다음 LLM으로 전환)
LLM_FALLBACK_ORDER: Dict[str, List[str]] = {
    'claude-haiku': ['openai', 'claude-3-haiku', 'claude'],
    'openai': ['claude-haiku', 'gpt-3.5-turbo', 'claude'],
    'claude-3-haiku': ['claude-haiku', 'openai', 'claude'],
    'gpt-3.5-turbo': ['openai', 'claude-haiku', 'claude'],
    'solar-mini': ['solar', 'claude-haiku', 'openai'],
    'claude': ['claude-haiku', 'openai', 'gpt-4o'],
    'gpt-4o': ['openai', 'claude', 'claude-haiku'],
    'solar': ['solar-mini', 'claude-haiku', 'openai'],
}


# =============================================================================
# 에러 메시지 변환 함수
# =============================================================================

def is_rate_limit_error(error_msg: str) -> bool:
    """Rate limit 또는 크레딧 부족 에러인지 확인"""
    error_lower = str(error_msg).lower()
    return any(keyword in error_lower for keyword in [
        'rate_limit', 'rate limit', '429', 'too many requests',
        'quota exceeded', 'rate-limit',
        'credit balance', 'insufficient', 'billing', 'purchase credits'
    ])


def convert_error_to_korean(error_msg: str) -> str:
    """
    영문 에러 메시지를 사용자 친화적 한글 메시지로 변환

    Args:
        error_msg: 원본 에러 메시지

    Returns:
        str: 한글 에러 메시지
    """
    error_lower = str(error_msg).lower()

    # Rate Limit 에러
    if 'rate_limit' in error_lower or '429' in error_lower or 'rate limit' in error_lower:
        return (
            "⚠️ API 호출 한도 초과\n\n"
            "현재 사용 중인 AI 서비스의 분당 요청 한도에 도달했습니다.\n\n"
            "해결 방법:\n"
            "• 1~2분 후에 다시 시도해 주세요\n"
            "• 또는 다른 AI 모델(OpenAI, Solar)을 선택해 보세요"
        )

    # 크레딧 부족 에러
    if 'credit balance' in error_lower or 'purchase credits' in error_lower or 'billing' in error_lower:
        return (
            "⚠️ API 크레딧 부족\n\n"
            "현재 사용 중인 AI 서비스의 크레딧이 부족합니다.\n\n"
            "해결 방법:\n"
            "• Anthropic Console에서 크레딧을 충전해 주세요\n"
            "• 또는 다른 AI 모델(OpenAI, Solar)을 선택해 보세요"
        )

    # API 키 에러
    if 'api_key' in error_lower or 'authentication' in error_lower or 'unauthorized' in error_lower:
        return (
            "⚠️ API 인증 오류\n\n"
            "AI 서비스 API 키가 유효하지 않거나 설정되지 않았습니다.\n"
            "관리자에게 문의해 주세요."
        )

    # 연결 에러
    if 'connection' in error_lower or 'timeout' in error_lower or 'network' in error_lower:
        return (
            "⚠️ 네트워크 연결 오류\n\n"
            "AI 서비스에 연결할 수 없습니다.\n"
            "인터넷 연결을 확인하고 다시 시도해 주세요."
        )

    # SQL 에러
    if 'sql' in error_lower or 'syntax' in error_lower or 'column' in error_lower:
        return (
            "⚠️ 데이터 조회 오류\n\n"
            "질문을 처리하는 중 오류가 발생했습니다.\n"
            "질문을 다르게 표현해서 다시 시도해 주세요."
        )

    # 기타 에러는 원본 메시지 반환
    return f"⚠️ 오류가 발생했습니다\n\n{error_msg}"


# =============================================================================
# 차트 생성 함수
# =============================================================================

def is_chart_request(question: str) -> bool:
    """질문이 차트 생성 요청인지 판단"""
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in CHART_KEYWORDS)


def is_timeseries_request(question: str) -> bool:
    """질문이 시계열 분석 요청인지 판단"""
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in TIMESERIES_KEYWORDS)


def is_grouped_chart_request(question: str) -> bool:
    """질문이 그룹 막대 차트 요청인지 판단"""
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in GROUPED_CHART_KEYWORDS)


def is_stacked_chart_request(question: str) -> bool:
    """질문이 100% 누적 막대 차트 요청인지 판단"""
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in STACKED_CHART_KEYWORDS)


def is_dynamic_chart_request(question: str) -> bool:
    """질문이 동적 차트 요청인지 판단 (LLM이 직접 코드 생성)"""
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in DYNAMIC_CHART_KEYWORDS)


def is_timeseries_data(df: pd.DataFrame) -> bool:
    """DataFrame이 시계열 데이터인지 판단 (기준년월 컬럼 존재 + 여러 시점)"""
    if df is None or df.empty:
        return False
    # 기준년월 컬럼이 있고, 여러 시점 데이터가 있는지 확인
    time_cols = [col for col in df.columns if '기준년월' in col or 'base_ym' in col.lower()]
    if time_cols:
        return df[time_cols[0]].nunique() > 1
    return False


def _format_time_value(val) -> str:
    """시간 값을 차트용 문자열로 변환"""
    if hasattr(val, 'strftime'):
        # datetime.date 또는 datetime 객체
        return val.strftime('%Y-%m')
    return str(val)


def generate_line_chart(df: pd.DataFrame, question: str, title: str = None) -> Optional[str]:
    """
    시계열 데이터를 꺾은선 그래프로 생성

    Args:
        df: 시계열 DataFrame (기준년월 컬럼 포함)
        question: 사용자 질문
        title: 차트 제목

    Returns:
        str: base64 인코딩된 이미지 또는 None
    """
    if df is None or df.empty:
        return None

    try:
        # 기준년월 컬럼 찾기
        time_col = None
        for col in df.columns:
            if '기준년월' in col or 'base_ym' in col.lower():
                time_col = col
                break

        if not time_col:
            return None

        # 숫자형 컬럼 찾기
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric_cols:
            return None

        # 그룹 컬럼 찾기 (시군구 등)
        group_col = None
        for col in df.columns:
            if col != time_col and col not in numeric_cols:
                if '시군구' in col or '지역' in col or 'sigungu' in col.lower():
                    group_col = col
                    break

        value_col = numeric_cols[-1]  # 마지막 숫자 컬럼 사용

        # 차트 크기 설정
        fig, ax = plt.subplots(figsize=(14, 7))

        # 색상 팔레트
        colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
                  '#00BCD4', '#8BC34A', '#FF5722', '#673AB7', '#3F51B5']

        if group_col and df[group_col].nunique() > 1:
            # 여러 지역 비교 (멀티라인)
            groups = df[group_col].unique()
            for i, group in enumerate(groups):
                group_data = df[df[group_col] == group].sort_values(time_col)
                time_labels = [_format_time_value(v) for v in group_data[time_col]]
                ax.plot(
                    time_labels,
                    group_data[value_col],
                    marker='o',
                    linewidth=2,
                    markersize=6,
                    label=str(group),
                    color=colors[i % len(colors)]
                )
            ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=10)
        else:
            # 단일 지역 추이
            df_sorted = df.sort_values(time_col)
            time_labels = [_format_time_value(v) for v in df_sorted[time_col]]
            ax.plot(
                time_labels,
                df_sorted[value_col],
                marker='o',
                linewidth=2.5,
                markersize=8,
                color='#2196F3'
            )
            # 데이터 라벨 추가
            for x, y in zip(time_labels, df_sorted[value_col]):
                ax.annotate(
                    f'{y:,.1f}' if isinstance(y, float) else f'{y:,}',
                    (x, y),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha='center',
                    fontsize=9
                )

        # 제목 설정
        if title:
            chart_title = title
        else:
            chart_title = f"{value_col} 추이"
            if group_col and df[group_col].nunique() == 1:
                chart_title = f"{df[group_col].iloc[0]} {chart_title}"

        ax.set_title(chart_title, fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('기준년월', fontsize=11)
        ax.set_ylabel(value_col, fontsize=11)

        # X축 라벨 회전
        plt.xticks(rotation=45, ha='right')

        # 그리드 추가
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)

        plt.tight_layout()

        # base64 인코딩
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close(fig)

        return image_base64

    except Exception as e:
        logger.error(f"라인 차트 생성 오류: {e}")
        return None


def generate_grouped_bar_chart(df: pd.DataFrame, question: str, title: str = None) -> Optional[str]:
    """
    여러 카테고리를 색상으로 구분하는 그룹 막대 차트 생성

    Args:
        df: DataFrame (첫 컬럼=라벨, 나머지=숫자형 그룹 컬럼들)
        question: 사용자 질문
        title: 차트 제목

    Returns:
        str: base64 인코딩된 이미지 또는 None
    """
    import numpy as np

    if df is None or df.empty or len(df.columns) < 3:
        return None

    try:
        label_col = df.columns[0]
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

        # 그룹 차트에 적합한 컬럼만 필터링 (비율 컬럼 제외)
        group_cols = [col for col in numeric_cols
                     if '비율' not in col and '율' not in col.replace('가구', '')]

        if len(group_cols) < 2:
            return None

        # 데이터 준비
        labels = df[label_col].astype(str).tolist()
        n_labels = len(labels)
        n_groups = len(group_cols)

        # 차트 크기 설정
        fig, ax = plt.subplots(figsize=(14, max(8, n_labels * 0.5)))

        # 막대 위치 계산
        bar_height = 0.8 / n_groups
        y_positions = np.arange(n_labels)

        # 색상 팔레트 (연령대별 구분)
        colors = ['#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0',
                  '#00BCD4', '#8BC34A', '#FF5722', '#673AB7', '#3F51B5']

        # 각 그룹별 막대 그리기
        for i, col in enumerate(group_cols):
            values = df[col].tolist()
            offset = (i - n_groups/2 + 0.5) * bar_height
            bars = ax.barh(y_positions + offset, values,
                          height=bar_height * 0.9,
                          label=col,
                          color=colors[i % len(colors)],
                          edgecolor='white',
                          linewidth=0.5)

        # Y축 라벨 설정
        ax.set_yticks(y_positions)
        ax.set_yticklabels(labels, fontsize=10)

        # 제목 및 라벨
        chart_title = title or f'{label_col}별 그룹 비교'
        ax.set_title(chart_title, fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('인원 수', fontsize=11)

        # 범례 (차트 외부 오른쪽)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1),
                 fontsize=9, title='구분')

        # 그리드
        ax.grid(axis='x', linestyle='--', alpha=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout()

        # base64 인코딩
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close(fig)

        return image_base64

    except Exception as e:
        logger.error(f"그룹 막대 차트 생성 오류: {e}")
        plt.close('all')
        return None


def generate_stacked_bar_chart(df: pd.DataFrame, question: str, title: str = None) -> Optional[str]:
    """
    100% 누적 막대 차트 생성 (각 행의 합계가 100%가 되도록)

    Args:
        df: DataFrame (첫 컬럼=라벨, 나머지=숫자형 그룹 컬럼들)
        question: 사용자 질문
        title: 차트 제목

    Returns:
        str: base64 인코딩된 이미지 또는 None
    """
    import numpy as np

    if df is None or df.empty or len(df.columns) < 3:
        return None

    try:
        label_col = df.columns[0]
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

        # 비율/율 컬럼 제외, 실제 수치 컬럼만 사용
        group_cols = [col for col in numeric_cols
                     if '비율' not in col and '율' not in col.replace('가구', '')]

        if len(group_cols) < 2:
            return None

        # 데이터 준비
        labels = df[label_col].astype(str).tolist()
        n_labels = len(labels)

        # 각 행별 합계 계산 후 비율로 변환
        data_matrix = df[group_cols].values
        row_totals = data_matrix.sum(axis=1, keepdims=True)
        # 0으로 나누기 방지
        row_totals = np.where(row_totals == 0, 1, row_totals)
        percentages = (data_matrix / row_totals) * 100

        # 차트 크기 설정
        fig, ax = plt.subplots(figsize=(14, max(8, n_labels * 0.45)))

        # 색상 팔레트
        colors = ['#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0',
                  '#00BCD4', '#8BC34A', '#FF5722', '#673AB7', '#3F51B5']

        # 누적 막대 그리기
        y_positions = np.arange(n_labels)
        left = np.zeros(n_labels)

        for i, col in enumerate(group_cols):
            values = percentages[:, i]
            bars = ax.barh(y_positions, values, left=left,
                          height=0.7,
                          label=col,
                          color=colors[i % len(colors)],
                          edgecolor='white',
                          linewidth=0.5)

            # 막대 안에 비율 텍스트 표시 (5% 이상일 때만)
            for j, (bar, val) in enumerate(zip(bars, values)):
                if val >= 5:  # 5% 이상일 때만 텍스트 표시
                    text_x = left[j] + val / 2
                    ax.text(text_x, y_positions[j], f'{val:.1f}%',
                           ha='center', va='center', fontsize=8,
                           color='white', fontweight='bold')

            left += values

        # Y축 라벨 설정
        ax.set_yticks(y_positions)
        ax.set_yticklabels(labels, fontsize=10)

        # X축 설정 (0~100%)
        ax.set_xlim(0, 100)
        ax.set_xlabel('비율 (%)', fontsize=11)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xticklabels(['0%', '25%', '50%', '75%', '100%'])

        # 제목
        chart_title = title or f'{label_col}별 구성비 비교'
        ax.set_title(chart_title, fontsize=14, fontweight='bold', pad=15)

        # 범례 (차트 외부 오른쪽)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1),
                 fontsize=9, title='구분')

        # 그리드
        ax.grid(axis='x', linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

        plt.tight_layout()

        # base64 인코딩
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close(fig)

        return image_base64

    except Exception as e:
        logger.error(f"100% 누적 차트 생성 오류: {e}")
        plt.close('all')
        return None


def generate_dynamic_chart(df: pd.DataFrame, question: str, llm_client=None) -> Optional[str]:
    """
    LLM이 생성한 matplotlib 코드를 실행하여 동적 차트 생성

    Args:
        df: 차트로 표시할 DataFrame
        question: 사용자 질문
        llm_client: LLM 클라이언트 인스턴스

    Returns:
        str: base64 인코딩된 이미지 또는 None
    """
    import numpy as np

    if df is None or df.empty or llm_client is None:
        return None

    try:
        # DataFrame 정보 요약
        df_info = f"""
DataFrame 컬럼: {list(df.columns)}
DataFrame 크기: {len(df)}행 x {len(df.columns)}열
데이터 타입: {df.dtypes.to_dict()}
샘플 데이터 (상위 3행):
{df.head(3).to_string()}
"""

        # LLM에게 matplotlib 코드 생성 요청
        prompt = f"""다음 데이터와 질문을 바탕으로 matplotlib 차트를 그리는 Python 코드를 생성해주세요.

질문: {question}

{df_info}

규칙:
1. 변수 'df'에 이미 DataFrame이 로드되어 있음
2. 'fig'와 'ax' 변수를 사용하여 차트 생성 (이미 생성됨: fig, ax = plt.subplots())
3. plt.show() 호출하지 말 것
4. 한글 폰트는 이미 설정되어 있음 (koreanize_matplotlib)
5. 코드만 반환하고 설명은 제외
6. ```python 마커 없이 순수 Python 코드만 반환
7. figsize 설정하지 말 것 (이미 설정됨)
8. import 문 포함하지 말 것

예시 형식:
ax.bar(df['컬럼1'], df['컬럼2'])
ax.set_xlabel('X축 라벨')
ax.set_ylabel('Y축 라벨')
ax.set_title('차트 제목')
"""

        # LLM 호출
        response = llm_client.generate(prompt)
        generated_code = response.strip()

        # 코드 블록 마커 제거
        if generated_code.startswith('```'):
            lines = generated_code.split('\n')
            generated_code = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        logger.info(f"LLM 생성 차트 코드:\n{generated_code[:500]}...")

        # 안전한 실행 환경 구성
        fig, ax = plt.subplots(figsize=(12, max(6, len(df) * 0.4)))

        # 허용된 모듈/함수만 포함
        safe_globals = {
            '__builtins__': {
                'range': range,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'zip': zip,
                'enumerate': enumerate,
                'sorted': sorted,
                'reversed': reversed,
                'min': min,
                'max': max,
                'sum': sum,
                'abs': abs,
                'round': round,
                'True': True,
                'False': False,
                'None': None,
            },
            'plt': plt,
            'np': np,
            'pd': pd,
            'df': df.copy(),  # 원본 보호를 위해 복사본 사용
            'fig': fig,
            'ax': ax,
        }

        # 위험한 키워드 체크
        dangerous_keywords = [
            'import ', 'exec', 'eval', 'open(', 'file', 'os.', 'sys.',
            'subprocess', 'shell', 'system(', '__', 'globals', 'locals',
            'compile', 'input(', 'raw_input', 'execfile', 'reload',
            'rm ', 'del ', 'shutil', 'pathlib', 'requests', 'urllib',
            'socket', 'http', 'ftp'
        ]

        code_lower = generated_code.lower()
        for keyword in dangerous_keywords:
            if keyword.lower() in code_lower:
                logger.warning(f"위험한 키워드 감지: {keyword}")
                plt.close(fig)
                return None

        # 코드 실행
        exec(generated_code, safe_globals)

        plt.tight_layout()

        # base64 인코딩
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close(fig)

        logger.info("동적 차트 생성 성공")
        return image_base64

    except Exception as e:
        logger.error(f"동적 차트 생성 오류: {e}")
        plt.close('all')
        return None


def generate_chart(df: pd.DataFrame, question: str, title: str = None) -> Optional[str]:
    """
    DataFrame을 기반으로 차트를 생성하고 base64 이미지로 반환

    Args:
        df: 차트로 표시할 DataFrame
        question: 사용자 질문
        title: 차트 제목 (None이면 자동 생성)

    Returns:
        str: base64 인코딩된 이미지 또는 None
    """
    if df is None or df.empty or len(df.columns) < 2:
        return None

    try:
        fig, ax = plt.subplots(figsize=(12, max(6, len(df) * 0.4)))

        label_col = df.columns[0]
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric_cols:
            return None
        value_col = numeric_cols[-1]

        df_sorted = df.sort_values(value_col, ascending=True)
        labels = df_sorted[label_col].astype(str).tolist()
        values = df_sorted[value_col].tolist()

        # 색상 그라데이션
        min_val, max_val = min(values), max(values)
        if max_val > min_val:
            colors = []
            for v in values:
                ratio = (v - min_val) / (max_val - min_val)
                if ratio < 0.33:
                    colors.append('#d73027')
                elif ratio < 0.66:
                    colors.append('#fee090')
                else:
                    colors.append('#4575b4')
        else:
            colors = ['#667eea'] * len(values)

        bars = ax.barh(labels, values, color=colors, edgecolor='gray', linewidth=0.5)

        for bar, val in zip(bars, values):
            if isinstance(val, float) and val != int(val):
                val_text = f'{val:.2f}'
            else:
                val_text = f'{int(val):,}'
            ax.text(val + (max_val * 0.01), bar.get_y() + bar.get_height()/2,
                   val_text, va='center', fontsize=9)

        avg = sum(values) / len(values)
        ax.axvline(x=avg, color='red', linestyle='--', linewidth=1.5,
                  label=f'평균: {avg:.2f}')

        ax.set_xlabel(value_col, fontsize=11)
        chart_title = title or f'{label_col}별 {value_col} 비교'
        ax.set_title(chart_title, fontsize=13, fontweight='bold')
        ax.legend(loc='lower right')
        ax.set_xlim(0, max(values) * 1.15)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)

        return image_base64

    except Exception as e:
        logger.error(f"차트 생성 오류: {e}")
        plt.close('all')
        return None


def save_chart_to_file(df: pd.DataFrame, output_dir: Path, filename: str,
                       question: str, title: str = None,
                       use_line_chart: bool = False) -> Optional[Path]:
    """차트를 파일로 저장 (막대 차트 또는 라인 차트)"""
    if df is None or df.empty:
        return None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        # 시계열 라인 차트
        if use_line_chart:
            # 기준년월 컬럼 찾기
            time_col = None
            for col in df.columns:
                if '기준년월' in col or 'base_ym' in col.lower():
                    time_col = col
                    break

            if not time_col:
                return None

            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if not numeric_cols:
                return None

            # 그룹 컬럼 찾기
            group_col = None
            for col in df.columns:
                if col != time_col and col not in numeric_cols:
                    if '시군구' in col or '지역' in col or 'sigungu' in col.lower():
                        group_col = col
                        break

            value_col = numeric_cols[-1]
            fig, ax = plt.subplots(figsize=(14, 7))

            colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
                      '#00BCD4', '#8BC34A', '#FF5722', '#673AB7', '#3F51B5']

            if group_col and df[group_col].nunique() > 1:
                groups = df[group_col].unique()
                for i, group in enumerate(groups):
                    group_data = df[df[group_col] == group].sort_values(time_col)
                    time_labels = [_format_time_value(v) for v in group_data[time_col]]
                    ax.plot(
                        time_labels,
                        group_data[value_col],
                        marker='o', linewidth=2, markersize=6,
                        label=str(group), color=colors[i % len(colors)]
                    )
                ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=10)
            else:
                df_sorted = df.sort_values(time_col)
                time_labels = [_format_time_value(v) for v in df_sorted[time_col]]
                ax.plot(
                    time_labels,
                    df_sorted[value_col],
                    marker='o', linewidth=2.5, markersize=8, color='#2196F3'
                )

            chart_title = title or f"{value_col} 추이"
            ax.set_title(chart_title, fontsize=14, fontweight='bold', pad=15)
            ax.set_xlabel('기준년월', fontsize=11)
            ax.set_ylabel(value_col, fontsize=11)
            plt.xticks(rotation=45, ha='right')
            ax.grid(True, linestyle='--', alpha=0.7)
            ax.set_axisbelow(True)

        # 일반 막대 차트
        else:
            fig, ax = plt.subplots(figsize=(12, max(6, len(df) * 0.4)))

            label_col = df.columns[0]
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if not numeric_cols:
                return None
            value_col = numeric_cols[-1]

            df_sorted = df.sort_values(value_col, ascending=True)
            labels = df_sorted[label_col].astype(str).tolist()
            values = df_sorted[value_col].tolist()

            min_val, max_val = min(values), max(values)
            if max_val > min_val:
                colors = []
                for v in values:
                    ratio = (v - min_val) / (max_val - min_val)
                    if ratio < 0.33:
                        colors.append('#d73027')
                    elif ratio < 0.66:
                        colors.append('#fee090')
                    else:
                        colors.append('#4575b4')
            else:
                colors = ['#667eea'] * len(values)

            bars = ax.barh(labels, values, color=colors, edgecolor='gray', linewidth=0.5)

            for bar, val in zip(bars, values):
                if isinstance(val, float) and val != int(val):
                    val_text = f'{val:.2f}'
                else:
                    val_text = f'{int(val):,}'
                ax.text(val + (max_val * 0.01), bar.get_y() + bar.get_height()/2,
                       val_text, va='center', fontsize=9)

            avg = sum(values) / len(values)
            ax.axvline(x=avg, color='red', linestyle='--', linewidth=1.5,
                      label=f'평균: {avg:.2f}')

            ax.set_xlabel(value_col, fontsize=11)
            chart_title = title or f'{label_col}별 {value_col} 비교'
            ax.set_title(chart_title, fontsize=13, fontweight='bold')
            ax.legend(loc='lower right')
            ax.set_xlim(0, max(values) * 1.15)

        plt.tight_layout()

        output_path = output_dir / filename
        plt.savefig(output_path, dpi=150, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)

        logger.info(f"차트 저장: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"차트 파일 저장 오류: {e}")
        plt.close('all')
        return None


def generate_csv_download(df: pd.DataFrame) -> str:
    """DataFrame을 CSV base64 문자열로 변환"""
    if df is None or df.empty:
        return ""
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    csv_data = csv_buffer.getvalue().encode('utf-8-sig')
    return base64.b64encode(csv_data).decode('utf-8')


def save_csv_to_file(df: pd.DataFrame, output_dir: Path, filename: str) -> Optional[Path]:
    """DataFrame을 CSV 파일로 저장"""
    if df is None or df.empty:
        return None
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"CSV 저장: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"CSV 파일 저장 오류: {e}")
        return None


# =============================================================================
# HTML 포맷팅 함수
# =============================================================================

def format_dataframe_to_table(df: pd.DataFrame) -> str:
    """DataFrame을 HTML 테이블로 변환"""
    if df is None or df.empty:
        return "<p>조회 결과가 없습니다.</p>"

    rows = []
    for idx, row in df.iterrows():
        cells = [f"<td>{idx + 1}</td>"]
        for col in df.columns:
            val = row[col]
            formatted = _format_cell_value(val, col)
            cells.append(f"<td>{formatted}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    headers = ['#'] + list(df.columns)
    header_html = ''.join([f"<th>{h}</th>" for h in headers])

    return f"""
<table class="result-table">
    <thead><tr>{header_html}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
</table>
"""


def _format_cell_value(val: Any, col_name: str) -> str:
    """셀 값 포맷팅"""
    if pd.isna(val):
        return '-'

    # datetime 객체 처리
    if hasattr(val, 'strftime'):
        # 기준년월 컬럼은 YYYY년 MM월 형식으로
        if '기준년월' in col_name or 'base_ym' in col_name.lower():
            return val.strftime('%Y년 %m월')
        # 일반 날짜는 YYYY-MM-DD
        return val.strftime('%Y-%m-%d')

    if isinstance(val, float):
        ratio_keywords = ['ratio', 'rate', '%', '율', '비율', 'index', '지수']
        is_ratio_column = any(kw in col_name.lower() for kw in ratio_keywords)

        if is_ratio_column:
            return f"{val:.2f}"
        elif val == int(val):
            return f"{int(val):,}"
        else:
            return f"{val:.2f}"

    if isinstance(val, int):
        return f"{val:,}"

    return str(val)


def format_llm_answer(answer: str) -> str:
    """LLM 답변을 HTML로 변환"""
    answer = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', answer)
    answer = answer.replace('\n', '<br>')

    return f'''
    <div class="llm-answer">
        <div class="answer-badge">AI 분석 결과</div>
        <div class="answer-content">{answer}</div>
    </div>
    '''


def build_llm_select_html(available_providers: Dict[str, bool], selected_provider: str) -> str:
    """LLM 선택 드롭다운 HTML 생성"""
    options = []
    for provider, is_available in available_providers.items():
        selected = 'selected' if provider == selected_provider else ''
        disabled = '' if is_available else 'disabled'
        display_name = LLM_DISPLAY_NAMES.get(provider, provider)
        status = '' if is_available else ' (API키 없음)'
        options.append(
            f'<option value="{provider}" {selected} {disabled}>'
            f'{display_name}{status}</option>'
        )
    return '\n'.join(options)


def build_example_buttons_html(questions: List[str]) -> str:
    """예시 질문 버튼 HTML 생성"""
    buttons = []
    for q in questions:
        escaped_q = q.replace("'", "\\'")
        buttons.append(
            f'<button type="button" class="example-btn" '
            f'onclick="setQuestion(\'{escaped_q}\')">{q}</button>'
        )
    return ''.join(buttons)


def build_result_section_html(
    question: str,
    result_html: Optional[str],
    sql: Optional[str],
    error: Optional[str],
    provider: Optional[str],
    model_name: Optional[str] = None,
    model_display_name: Optional[str] = None,
    usage: Optional[Dict[str, int]] = None,
    chart_base64: Optional[str] = None,
    csv_base64: Optional[str] = None,
    base_ym: Optional[str] = None,
    saved_files: Optional[List[str]] = None,
    fallback_message: Optional[str] = None
) -> str:
    """결과 영역 HTML 생성"""
    if not question:
        return '''
        <div class="empty-state">
            <div class="icon">&#129302;</div>
            <p>AI에게 데이터에 대해 자유롭게 질문하세요!</p>
        </div>
        '''

    if error:
        # 에러 메시지를 한글로 변환하고 줄바꿈을 HTML로 처리
        korean_error = convert_error_to_korean(error)
        error_html = korean_error.replace('\n', '<br>')
        return f'<div class="error-msg">{error_html}</div>'

    if result_html:
        # 기준년월 표시
        base_ym_html = ""
        if base_ym:
            year = base_ym[:4]
            month = base_ym[4:6] if len(base_ym) >= 6 else ""
            base_ym_html = f'<span class="base-ym-badge">기준: {year}년 {month}월</span>'

        # SQL 표시
        sql_html = ""
        if sql:
            sql_html = f'''
            <details class="sql-details" open>
                <summary>생성된 SQL</summary>
                <pre>{sql.strip()}</pre>
            </details>
            '''

        # 모델 정보
        model_info_html = ""
        if model_display_name:
            model_badge = f'<span class="model-badge">{model_display_name}</span>'
            model_id_html = f'<span class="model-id">{model_name}</span>' if model_name else ""
            usage_html = ""
            if usage:
                usage_html = f'''
                <span class="usage-info">
                    입력: {usage.get("input_tokens", 0):,}토큰 |
                    출력: {usage.get("output_tokens", 0):,}토큰
                </span>
                '''
            model_info_html = f'''
            <div class="model-info-bar">
                {model_badge}
                {model_id_html}
                {base_ym_html}
                {usage_html}
            </div>
            '''
        elif provider:
            display_name = LLM_DISPLAY_NAMES.get(provider, provider)
            model_info_html = f'''
            <div class="model-info-bar">
                <span class="model-badge">{display_name}</span>
                {base_ym_html}
            </div>
            '''

        # 차트 HTML
        chart_html = ""
        if chart_base64:
            chart_html = f'''
            <div class="chart-container">
                <img src="data:image/png;base64,{chart_base64}" alt="차트" class="result-chart">
            </div>
            '''

        # CSV 다운로드 버튼
        csv_download_html = ""
        if csv_base64:
            csv_download_html = f'''
            <div class="download-section">
                <a href="data:text/csv;base64,{csv_base64}"
                   download="result_data.csv"
                   class="download-btn">
                   CSV 다운로드
                </a>
            </div>
            '''

        # 저장된 파일 목록
        saved_files_html = ""
        if saved_files:
            files_list = ''.join([f'<li>{f}</li>' for f in saved_files])
            saved_files_html = f'''
            <div class="saved-files-info">
                <strong>저장된 파일:</strong>
                <ul>{files_list}</ul>
            </div>
            '''

        # LLM 전환 메시지
        fallback_html = ""
        if fallback_message:
            fallback_html = f'''
            <div class="fallback-message">
                {fallback_message}
            </div>
            '''

        return f'''
        <div class="result-section">
            {fallback_html}
            {model_info_html}
            <div class="result-header">
                <span class="query-text">"{question}"</span>
                {csv_download_html}
            </div>
            {chart_html}
            {result_html}
            {saved_files_html}
            {sql_html}
        </div>
        '''

    return '<div class="empty-state"><p>결과를 표시할 수 없습니다.</p></div>'


def build_menu_html(menu_items: List[Dict[str, str]]) -> str:
    """메뉴 HTML 생성"""
    links = [f'<a href="{item["url"]}">{item["name"]}</a>' for item in menu_items]
    return ' | '.join(links)


# =============================================================================
# CSS 스타일
# =============================================================================

def get_page_styles() -> str:
    """페이지 CSS 스타일 반환"""
    return '''
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Malgun Gothic', sans-serif;
            background: #f5f7fa;
            min-height: 100vh;
        }

        .header {
            background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
            color: white;
            padding: 0.75rem 1rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        .header-content {
            max-width: 1800px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 1.25rem; font-weight: 600; }

        .main-nav { display: flex; gap: 0.5rem; margin-left: 2rem; }
        .main-nav a {
            color: rgba(255,255,255,0.8);
            text-decoration: none;
            font-size: 0.9rem;
            padding: 0.4rem 0.8rem;
            border-radius: 4px;
            transition: all 0.3s;
        }
        .main-nav a:hover { background: rgba(255,255,255,0.2); color: white; }
        .main-nav a.active { background: #F24822; color: white; font-weight: 500; }

        .btn-home {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 0.4rem 0.8rem;
            border-radius: 4px;
            text-decoration: none;
            font-size: 0.85rem;
        }
        .btn-home:hover { background: rgba(255,255,255,0.3); }

        /* 로딩 오버레이 */
        .loading-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 9999;
            justify-content: center;
            align-items: center;
        }
        .loading-overlay.show { display: flex; }
        .loading-box {
            background: white;
            padding: 2rem 3rem;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }
        .loading-spinner {
            width: 50px;
            height: 50px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #1D64F2;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .loading-text { font-size: 1.1rem; color: #011C40; font-weight: 500; }

        .main-content {
            max-width: 1000px;
            margin: 2rem auto;
            padding: 0 1rem;
        }

        .chat-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            overflow: hidden;
        }

        .chat-header {
            background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
            color: #ffffff;
            padding: 0.6rem 1rem;
            text-align: center;
        }
        .chat-header h2 { font-size: 1.2rem; margin-bottom: 0.2rem; color: #ffffff !important; }
        .chat-header p { opacity: 1; font-size: 0.85rem; color: #ffffff !important; }

        .search-section {
            padding: 1.5rem;
            border-bottom: 1px solid #eee;
        }
        .search-form { display: flex; gap: 0.5rem; flex-wrap: wrap; }

        .search-input {
            flex: 1;
            min-width: 300px;
            padding: 0.9rem 1rem;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.2s;
        }
        .search-input:focus { outline: none; border-color: #667eea; }

        .llm-select {
            padding: 0.9rem 1rem;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 0.95rem;
            background: white;
            cursor: pointer;
            min-width: 120px;
        }
        .llm-select:focus { outline: none; border-color: #667eea; }

        .search-btn {
            padding: 0 1.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .search-btn:hover { transform: scale(1.02); }

        .examples {
            padding: 1rem 1.5rem;
            background: #f8f9fc;
            border-bottom: 1px solid #eee;
        }
        .examples-label { font-size: 0.85rem; color: #666; margin-bottom: 0.8rem; }
        .example-btn {
            background: white;
            border: 1px solid #ddd;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.85rem;
            margin: 0.2rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .example-btn:hover { border-color: #667eea; color: #667eea; }

        .result-section { padding: 1.5rem; }

        .result-header {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            margin-bottom: 1rem;
            padding-bottom: 0.8rem;
            border-bottom: 1px solid #eee;
            flex-wrap: wrap;
        }

        .provider-badge, .model-badge {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0.3rem 0.8rem;
            border-radius: 16px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .query-text { color: #555; font-style: italic; }

        .model-info-bar {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            padding: 0.6rem 1rem;
            background: linear-gradient(135deg, #f8f9fc 0%, #e8ebf3 100%);
            border-radius: 8px;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .model-id {
            color: #666;
            font-size: 0.75rem;
            font-family: 'Consolas', 'Monaco', monospace;
            background: #fff;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            border: 1px solid #ddd;
        }
        .usage-info { margin-left: auto; color: #888; font-size: 0.75rem; }

        .base-ym-badge {
            background: #28a745;
            color: white;
            padding: 0.2rem 0.6rem;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 500;
        }

        .result-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .result-table th {
            background: #f8f9fc;
            padding: 0.8rem;
            text-align: left;
            border-bottom: 2px solid #e1e5eb;
            font-weight: 600;
            color: #333;
        }
        .result-table td {
            padding: 0.7rem 0.8rem;
            border-bottom: 1px solid #eee;
        }
        .result-table tr:hover { background: #f8f9fc; }
        .result-table td:first-child {
            font-weight: 600;
            color: #667eea;
            width: 50px;
            text-align: center;
        }

        .sql-details {
            margin-top: 1rem;
            padding: 0.8rem;
            background: #f8f9fc;
            border-radius: 8px;
        }
        .sql-details summary { cursor: pointer; color: #666; font-size: 0.85rem; font-weight: 600; }
        .sql-details pre {
            margin-top: 0.8rem;
            padding: 1rem;
            background: #1e1e1e;
            color: #d4d4d4;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 0.8rem;
            line-height: 1.5;
        }

        .error-msg {
            padding: 1.5rem;
            background: linear-gradient(135deg, #fff5f5 0%, #ffe8e8 100%);
            color: #c62828;
            border-radius: 12px;
            margin: 1rem 1.5rem;
            border-left: 4px solid #ef5350;
            font-size: 0.95rem;
            line-height: 1.8;
            box-shadow: 0 2px 8px rgba(239, 83, 80, 0.15);
        }

        .fallback-message {
            padding: 0.8rem 1.2rem;
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            color: #1565c0;
            border-radius: 8px;
            margin: 0.5rem 0 1rem 0;
            border-left: 4px solid #2196f3;
            font-size: 0.9rem;
            box-shadow: 0 2px 6px rgba(33, 150, 243, 0.15);
        }

        .llm-answer {
            padding: 1.5rem;
            background: #f8f9fc;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .answer-badge {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }
        .answer-content { line-height: 1.8; color: #333; font-size: 0.95rem; }
        .answer-content strong { color: #667eea; }

        .empty-state { padding: 3rem; text-align: center; color: #888; }
        .empty-state .icon { font-size: 3rem; margin-bottom: 1rem; }

        .info-box {
            margin: 1rem 1.5rem;
            padding: 0.8rem 1rem;
            background: #e8f4fd;
            border-radius: 8px;
            font-size: 0.85rem;
            color: #1565c0;
        }

        .chart-container {
            margin: 1rem 0;
            padding: 1rem;
            background: #fafbfc;
            border-radius: 8px;
            text-align: center;
        }
        .result-chart {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .download-section { margin-left: auto; }
        .download-btn {
            display: inline-block;
            padding: 0.4rem 0.8rem;
            background: #28a745;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-size: 0.85rem;
            transition: background 0.2s;
        }
        .download-btn:hover { background: #218838; }

        .saved-files-info {
            margin-top: 1rem;
            padding: 0.8rem;
            background: #e8f5e9;
            border-radius: 6px;
            font-size: 0.85rem;
            color: #2e7d32;
        }
        .saved-files-info ul {
            margin: 0.5rem 0 0 1.5rem;
        }

        @media (max-width: 768px) {
            .search-form { flex-direction: column; }
            .search-input { min-width: 100%; }
            .example-btn { display: block; width: 100%; margin: 0.3rem 0; }
            .main-nav { display: none; }
            .chart-container { padding: 0.5rem; }
        }
    '''


def get_content_styles() -> str:
    """컨텐츠 전용 CSS 스타일 반환 (템플릿 내장용)"""
    return '''
        .datacong-container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 0 1rem;
        }

        .chat-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            overflow: hidden;
        }

        .chat-header {
            background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
            color: #ffffff;
            padding: 0.6rem 1rem;
            text-align: center;
        }
        .chat-header h2 { font-size: 1.2rem; margin-bottom: 0.2rem; color: #ffffff !important; }
        .chat-header p { opacity: 1; font-size: 0.85rem; color: #ffffff !important; }

        .search-section {
            padding: 1.5rem;
            border-bottom: 1px solid #eee;
        }
        .search-form { display: flex; gap: 0.5rem; flex-wrap: wrap; }

        .search-input {
            flex: 1;
            min-width: 300px;
            padding: 0.9rem 1rem;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.2s;
        }
        .search-input:focus { outline: none; border-color: #1D64F2; }

        .llm-select {
            padding: 0.9rem 1rem;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 0.95rem;
            background: white;
            cursor: pointer;
            min-width: 120px;
        }
        .llm-select:focus { outline: none; border-color: #1D64F2; }

        .search-btn {
            padding: 0 1.5rem;
            background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .search-btn:hover { transform: scale(1.02); }

        .examples {
            padding: 1rem 1.5rem;
            background: #f8f9fc;
            border-bottom: 1px solid #eee;
        }
        .examples-label { font-size: 0.85rem; color: #666; margin-bottom: 0.8rem; }
        .example-btn {
            background: white;
            border: 1px solid #ddd;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.85rem;
            margin: 0.2rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .example-btn:hover { border-color: #1D64F2; color: #1D64F2; }

        .result-section { padding: 1.5rem; }

        .result-header {
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
            gap: 1rem;
        }
        .query-text { font-weight: 600; color: #333; font-size: 1.1rem; }
        .provider-badge {
            font-size: 0.75rem;
            padding: 0.3rem 0.8rem;
            background: #e8f4fd;
            color: #1565c0;
            border-radius: 15px;
        }
        .base-ym-badge {
            font-size: 0.75rem;
            padding: 0.3rem 0.8rem;
            background: #e8f5e9;
            color: #2e7d32;
            border-radius: 15px;
        }
        .usage-info {
            font-size: 0.75rem;
            color: #888;
        }

        .result-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.9rem;
        }
        .result-table th, .result-table td {
            padding: 0.8rem 1rem;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        .result-table th { background: #f5f7fa; font-weight: 600; color: #333; }
        .result-table tr:hover { background: #fafbfc; }

        .sql-details {
            margin-top: 1rem;
            padding: 1rem;
            background: #f5f7fa;
            border-radius: 8px;
        }
        .sql-details summary { cursor: pointer; color: #666; font-size: 0.85rem; font-weight: 600; }
        .sql-details pre {
            margin-top: 0.8rem;
            padding: 1rem;
            background: #1e1e1e;
            color: #d4d4d4;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 0.8rem;
            line-height: 1.5;
        }

        .error-msg {
            padding: 1.5rem;
            background: linear-gradient(135deg, #fff5f5 0%, #ffe8e8 100%);
            color: #c62828;
            border-radius: 12px;
            margin: 1rem 1.5rem;
            border-left: 4px solid #ef5350;
            font-size: 0.95rem;
            line-height: 1.8;
            box-shadow: 0 2px 8px rgba(239, 83, 80, 0.15);
        }

        .fallback-message {
            padding: 0.8rem 1.2rem;
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            color: #1565c0;
            border-radius: 8px;
            margin: 0.5rem 0 1rem 0;
            border-left: 4px solid #2196f3;
            font-size: 0.9rem;
        }

        .llm-answer {
            padding: 1.5rem;
            background: #f8f9fc;
            border-radius: 8px;
            border-left: 4px solid #1D64F2;
        }
        .answer-badge {
            display: inline-block;
            background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
            color: white;
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }
        .answer-content { line-height: 1.8; color: #333; font-size: 0.95rem; }
        .answer-content strong { color: #1D64F2; }

        .empty-state { padding: 3rem; text-align: center; color: #888; }
        .empty-state .icon { font-size: 3rem; margin-bottom: 1rem; }

        .info-box {
            margin: 1rem 0;
            padding: 0.8rem 1rem;
            background: #e8f4fd;
            border-radius: 8px;
            font-size: 0.85rem;
            color: #1565c0;
        }

        .chart-container {
            margin: 1rem 0;
            padding: 1rem;
            background: #fafbfc;
            border-radius: 8px;
            text-align: center;
        }
        .result-chart {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .download-section { margin-left: auto; }
        .download-btn {
            display: inline-block;
            padding: 0.4rem 0.8rem;
            background: #28a745;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-size: 0.85rem;
        }
        .download-btn:hover { background: #218838; }

        .saved-files-info {
            margin-top: 1rem;
            padding: 0.8rem;
            background: #e8f5e9;
            border-radius: 6px;
            font-size: 0.85rem;
            color: #2e7d32;
        }

        #loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.9);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        .loading-content { text-align: center; }
        .loading-spinner {
            width: 60px;
            height: 60px;
            border: 4px solid #e0e0e0;
            border-top: 4px solid #1D64F2;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .loading-text { font-size: 1.2rem; font-weight: 600; color: #333; margin-bottom: 0.5rem; }
        .loading-subtext { font-size: 0.9rem; color: #666; }

        @media (max-width: 768px) {
            .search-form { flex-direction: column; }
            .search-input { min-width: 100%; }
            .example-btn { display: block; width: 100%; margin: 0.3rem 0; }
            .chart-container { padding: 0.5rem; }
        }
    '''


# =============================================================================
# 메인 클래스
# =============================================================================

class DataCongCore:
    """
    데이터콩 공통 기능 클래스

    각 도메인의 데이터콩.py에서 이 클래스를 사용하여
    도메인 특화 설정만 지정하면 됩니다.
    """

    def __init__(
        self,
        domain_name: str,
        domain_base: Path,
        caller_file: str,
        example_questions: List[str],
        chat_title: str = None,
        chat_subtitle: str = None
    ):
        """
        Args:
            domain_name: 도메인 이름 (예: "인구통계", "복지")
            domain_base: 도메인 폴더 경로 (예: Path(__file__).parent.parent)
            caller_file: 호출자 파일 경로 (__file__)
            example_questions: 예시 질문 목록
            chat_title: 챗봇 제목 (기본: "AI {domain_name} 질의 챗봇")
            chat_subtitle: 챗봇 부제목
        """
        self.domain_name = domain_name
        self.domain_base = domain_base
        self.caller_file = caller_file
        self.example_questions = example_questions
        self.chat_title = chat_title or f"AI {domain_name} 질의 챗봇"
        self.chat_subtitle = chat_subtitle or "자연어로 질문하면 AI가 SQL을 생성하여 답변합니다"

        # output 폴더 경로
        self.output_dir = domain_base / "output"

        # 모듈 임포트 (지연 로딩)
        self._db = None
        self._t2s = None
        self._llm_client = None
        self._menu_gen = None
        self._ontology_loader = None

    def _lazy_import(self):
        """필요한 모듈 지연 임포트"""
        if self._db is None:
            from module.db import get_db_connection
            from module.text_to_sql import TextToSQL
            from module.llm_client import LLMClient
            from module.menu_generator import MenuGenerator
            from module.ontology_loader import OntologyLoader

            self._db = get_db_connection
            self._t2s = TextToSQL
            self._llm_client = LLMClient
            self._menu_gen = MenuGenerator
            self._ontology_loader = OntologyLoader

    def _generate_data_interpretation(self, question: str, df: pd.DataFrame, llm) -> Optional[str]:
        """
        데이터 결과에 대한 AI 해석 생성

        Args:
            question: 사용자 질문
            df: 결과 데이터프레임
            llm: LLM 클라이언트 객체

        Returns:
            AI 해석 텍스트 또는 None
        """
        if llm is None or df is None or df.empty:
            return None

        try:
            # 데이터 요약 생성
            data_summary = df.head(20).to_string(index=False)
            if len(df) > 20:
                data_summary += f"\n\n... (총 {len(df)}행 중 20행만 표시)"

            # 기본 통계
            stats_info = ""
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                stats_info = f"\n\n수치형 컬럼 통계:\n{df[numeric_cols].describe().to_string()}"

            # LLM에게 해석 요청
            interpretation_prompt = f"""다음 데이터 분석 결과를 해석해주세요.

사용자 질문: {question}

데이터 결과:
{data_summary}
{stats_info}

위 데이터를 바탕으로 다음 내용을 포함한 분석 해석을 제공해주세요:
1. 핵심 발견사항 (주요 패턴, 특이점)
2. 데이터가 의미하는 바 (인사이트)
3. 주의할 점이나 추가 분석 제안

간결하고 명확하게 한국어로 작성해주세요. 마크다운 형식을 사용해도 됩니다."""

            system_prompt = "당신은 데이터 분석 전문가입니다. 주어진 데이터를 분석하고 인사이트를 제공합니다."

            interpretation = llm.chat(interpretation_prompt, system_prompt)
            return interpretation

        except Exception as e:
            logger.warning(f"AI 해석 생성 중 오류: {e}")
            return None

    def _parse_markdown_sections(self, markdown_text: str) -> list:
        """
        마크다운 텍스트를 ## 섹션별로 파싱

        Args:
            markdown_text: 마크다운 형식의 텍스트

        Returns:
            [{'title': '섹션 제목', 'content': '섹션 내용'}, ...] 형태의 리스트
        """
        sections = []
        current_title = "분석 결과"
        current_content = []

        lines = markdown_text.split('\n')

        for line in lines:
            # ## 헤더 감지 (##로 시작하는 라인)
            if line.startswith('## '):
                # 이전 섹션 저장
                if current_content:
                    content_text = '\n'.join(current_content).strip()
                    if content_text:
                        sections.append({
                            'title': current_title,
                            'content': content_text
                        })

                # 새 섹션 시작
                current_title = line[3:].strip()
                current_content = []
            elif line.startswith('# ') and not line.startswith('## '):
                # # 대제목은 섹션 제목으로 사용하지만 새 섹션으로 분리하지 않음
                if not current_content:  # 첫 번째 # 헤더만 제목으로 사용
                    current_title = line[2:].strip()
            else:
                current_content.append(line)

        # 마지막 섹션 저장
        if current_content:
            content_text = '\n'.join(current_content).strip()
            if content_text:
                sections.append({
                    'title': current_title,
                    'content': content_text
                })

        # 섹션이 없으면 전체 텍스트를 하나의 섹션으로
        if not sections and markdown_text.strip():
            sections.append({
                'title': '분석 결과',
                'content': markdown_text.strip()
            })

        return sections

    def get_latest_base_ym(self) -> Optional[str]:
        """최신 기준년월 조회"""
        self._lazy_import()
        conn = self._db()
        try:
            df = pd.read_sql("""
                SELECT MAX(base_ym) as base_ym
                FROM cache_sigungu_indicators
            """, conn)
            if df.empty or df['base_ym'].iloc[0] is None:
                return None
            base_ym = df['base_ym'].iloc[0]
            # datetime.date 또는 datetime 객체인 경우 문자열로 변환
            if hasattr(base_ym, 'strftime'):
                return base_ym.strftime('%Y%m')
            return str(base_ym)
        finally:
            conn.close()

    def process_question(self, question: str, llm_provider: str = 'claude-haiku') -> Dict[str, Any]:
        """질문 처리 (Rate limit 시 자동으로 다른 LLM으로 전환)"""
        self._lazy_import()

        response = {
            'sql': None,
            'result_html': None,
            'response': None,  # LLM 응답 텍스트 (PPT/MD 저장용)
            'error': None,
            'provider': llm_provider,
            'model_name': None,
            'model_display_name': None,
            'usage': None,
            'chart_base64': None,
            'csv_base64': None,
            'dataframe': None,  # DataFrame (PPT/HWP 저장용)
            'is_chart_request': False,
            'is_timeseries_request': False,
            'is_grouped_chart_request': False,
            'is_stacked_chart_request': False,
            'is_dynamic_chart_request': False,
            'base_ym': None,
            'saved_files': [],
            'fallback_message': None  # LLM 전환 메시지
        }

        response['is_chart_request'] = is_chart_request(question)
        response['is_timeseries_request'] = is_timeseries_request(question)
        response['is_grouped_chart_request'] = is_grouped_chart_request(question)
        response['is_stacked_chart_request'] = is_stacked_chart_request(question)
        response['is_dynamic_chart_request'] = is_dynamic_chart_request(question)

        if not question or not question.strip():
            response['error'] = "질문을 입력해주세요."
            return response

        try:
            # 온톨로지 로드
            loader = self._ontology_loader.auto_detect(
                caller_file=self.caller_file,
                question=question
            )
            ontology_content = loader.load()
            logger.info(f"로드된 도메인: {loader.get_domain_names()}")

            # LLM 호출 시도 (rate limit 시 자동 전환)
            providers_to_try = [llm_provider] + LLM_FALLBACK_ORDER.get(llm_provider, [])
            result = None
            t2s = None
            used_provider = llm_provider

            for i, provider in enumerate(providers_to_try):
                try:
                    logger.info(f"LLM 호출 시도: {provider}")
                    t2s = self._t2s(
                        llm_provider=provider,
                        ontology_content=ontology_content
                    )
                    result = t2s.ask(question)
                    used_provider = provider

                    # 전환된 경우 메시지 추가
                    if i > 0:
                        original_name = LLM_DISPLAY_NAMES.get(llm_provider, llm_provider)
                        new_name = LLM_DISPLAY_NAMES.get(provider, provider)
                        response['fallback_message'] = (
                            f"ℹ️ {original_name} API 한도 초과로 {new_name}(으)로 자동 전환되었습니다."
                        )
                        logger.info(f"LLM 전환: {llm_provider} → {provider}")
                    break

                except Exception as e:
                    error_str = str(e)
                    if is_rate_limit_error(error_str):
                        logger.warning(f"{provider} rate limit 발생, 다음 LLM으로 전환 시도")
                        if i == len(providers_to_try) - 1:
                            # 모든 LLM 실패
                            response['error'] = (
                                "⚠️ 모든 AI 서비스의 API 한도가 초과되었습니다.\n\n"
                                "잠시 후 다시 시도해 주세요."
                            )
                            return response
                        continue
                    else:
                        # rate limit 외 다른 에러는 바로 반환
                        raise

            response['provider'] = result['provider']
            response['model_name'] = t2s.llm.get_model_name()
            response['model_display_name'] = t2s.llm.get_display_name()

            last_usage = t2s.llm.get_last_usage()
            if last_usage:
                response['usage'] = {
                    'input_tokens': last_usage.input_tokens,
                    'output_tokens': last_usage.output_tokens,
                    'total_tokens': last_usage.total_tokens
                }

            if result['error']:
                response['sql'] = result['sql']
                response['error'] = result['error']
                return response

            if result.get('answer'):
                response['response'] = result['answer']  # LLM 응답 텍스트 저장 (PPT용)
                response['result_html'] = format_llm_answer(result['answer'])
                return response

            response['sql'] = result['sql']
            response['result_html'] = format_dataframe_to_table(result['data'])

            # 기준년월 조회
            response['base_ym'] = self.get_latest_base_ym()

            # 차트 생성 (동적 vs 누적 vs 그룹 vs 시계열 vs 일반 차트 구분)
            should_chart = (response['is_chart_request'] or
                           response['is_timeseries_request'] or
                           response['is_grouped_chart_request'] or
                           response['is_stacked_chart_request'] or
                           response['is_dynamic_chart_request'])
            if should_chart and result['data'] is not None:
                # 동적 차트 판단 (LLM이 직접 코드 생성)
                use_dynamic_chart = response['is_dynamic_chart_request']
                # 100% 누적 막대 차트 판단
                use_stacked_chart = response['is_stacked_chart_request']
                # 그룹 막대 차트 판단 (나란히 배치)
                use_grouped_chart = response['is_grouped_chart_request']
                # 시계열 데이터 판단: 키워드 요청 또는 데이터에 기준년월 + 여러 시점
                use_line_chart = (
                    response['is_timeseries_request'] or
                    is_timeseries_data(result['data'])
                )

                if use_dynamic_chart and t2s is not None:
                    chart_base64 = generate_dynamic_chart(result['data'], question, t2s.llm)
                    logger.info("동적 차트 생성 (LLM 코드)")
                elif use_stacked_chart:
                    chart_base64 = generate_stacked_bar_chart(result['data'], question)
                    logger.info("100% 누적 막대 차트 생성")
                elif use_grouped_chart:
                    chart_base64 = generate_grouped_bar_chart(result['data'], question)
                    logger.info("그룹 막대 차트 생성")
                elif use_line_chart:
                    chart_base64 = generate_line_chart(result['data'], question)
                    logger.info("시계열 라인 차트 생성")
                else:
                    chart_base64 = generate_chart(result['data'], question)
                    logger.info("일반 막대 차트 생성")

                if chart_base64:
                    response['chart_base64'] = chart_base64

                    # 파일로도 저장
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    if use_dynamic_chart:
                        chart_type = "dynamic"
                    elif use_stacked_chart:
                        chart_type = "stacked"
                    elif use_grouped_chart:
                        chart_type = "grouped"
                    elif use_line_chart:
                        chart_type = "trend"
                    else:
                        chart_type = "chart"
                    # 차트를 image 폴더에 저장 (MD에서 참조용)
                    image_dir = self.domain_base / "image"
                    image_dir.mkdir(parents=True, exist_ok=True)

                    chart_filename = f"{chart_type}_{timestamp}.png"
                    chart_path = save_chart_to_file(
                        result['data'],
                        image_dir,
                        chart_filename,
                        question,
                        use_line_chart=use_line_chart
                    )
                    if chart_path:
                        response['saved_files'].append(str(chart_path))
                        # MD에서 사용할 상대 경로 저장
                        response['chart_relative_path'] = f"../image/{chart_filename}"

                    # CSV도 저장
                    csv_path = save_csv_to_file(
                        result['data'],
                        self.output_dir,
                        f"data_{timestamp}.csv"
                    )
                    if csv_path:
                        response['saved_files'].append(str(csv_path))

            # CSV 다운로드 데이터
            if result['data'] is not None and not result['data'].empty:
                response['csv_base64'] = generate_csv_download(result['data'])
                # DataFrame도 저장 (PPT/HWP 저장 시 사용)
                response['dataframe'] = result['data']

                # AI 해석 추가 - 데이터가 있으면 LLM에게 해석 요청
                try:
                    interpretation = self._generate_data_interpretation(
                        question, result['data'], t2s.llm if t2s else None
                    )
                    if interpretation:
                        response['response'] = interpretation
                        logger.info("AI 데이터 해석 생성 완료")
                except Exception as e:
                    logger.warning(f"AI 해석 생성 실패 (무시): {e}")

            return response

        except Exception as e:
            logger.error(f"질문 처리 오류: {e}")
            response['error'] = str(e)
            return response

    def render(self, request_args: Optional[Dict[str, str]] = None) -> str:
        """
        페이지 렌더링 (컨텐츠만 반환)

        main_app.py의 category_with_navbar.html 템플릿이 메뉴를 추가하므로,
        여기서는 본문 컨텐츠만 반환합니다.
        """
        self._lazy_import()

        request_args = request_args or {}
        question = request_args.get('q', '')
        llm_provider = request_args.get('llm', 'claude-haiku')

        available_providers = self._llm_client.list_providers()

        process_result = {
            'sql': None,
            'result_html': None,
            'error': None,
            'provider': None,
            'model_name': None,
            'model_display_name': None,
            'usage': None,
            'chart_base64': None,
            'csv_base64': None,
            'base_ym': None,
            'saved_files': [],
            'fallback_message': None
        }

        if question:
            process_result = self.process_question(question, llm_provider)

        llm_select_html = build_llm_select_html(available_providers, llm_provider)
        example_html = build_example_buttons_html(self.example_questions)

        result_section = build_result_section_html(
            question=question,
            result_html=process_result['result_html'],
            sql=process_result['sql'],
            error=process_result['error'],
            provider=process_result['provider'],
            model_name=process_result['model_name'],
            model_display_name=process_result['model_display_name'],
            usage=process_result['usage'],
            chart_base64=process_result['chart_base64'],
            csv_base64=process_result['csv_base64'],
            base_ym=process_result['base_ym'],
            saved_files=process_result['saved_files'],
            fallback_message=process_result['fallback_message']
        )

        # 컨텐츠만 반환 (메뉴는 main_app.py의 템플릿에서 추가)
        styles = get_content_styles()

        html = f'''
<style>
{styles}
</style>

<div class="datacong-container">
    <div class="chat-container">
        <div class="chat-header">
            <h2>{self.chat_title}</h2>
            <p>{self.chat_subtitle}</p>
        </div>

        <div class="search-section">
            <form class="search-form" method="get">
                <input type="text" name="q" class="search-input"
                       placeholder="예: {self.example_questions[0] if self.example_questions else '질문을 입력하세요'}"
                       value="{question}">
                <select name="llm" class="llm-select">
                    {llm_select_html}
                </select>
                <button type="submit" class="search-btn">질문하기</button>
            </form>
        </div>

        <div class="examples">
            <div class="examples-label">예시 질문:</div>
            {example_html}
        </div>

        <div id="result-area">
            {result_section}
        </div>

        <!-- 결과가 있을 때만 저장 버튼 표시 -->
        {self._get_save_buttons_html(question, llm_provider) if question and process_result.get('result_html') else ''}
    </div>

    <div class="info-box">
        <strong>TIP:</strong> "차트", "그래프", "시각화" 키워드를 포함하면 차트가 생성됩니다.
        결과는 CSV로 다운로드하거나 output 폴더에 자동 저장됩니다.
    </div>
</div>

<!-- 로딩 오버레이 -->
<div id="loading-overlay" style="display:none;">
    <div class="loading-content">
        <div class="loading-spinner"></div>
        <p class="loading-text">AI가 분석 중입니다...</p>
        <p class="loading-subtext">잠시만 기다려주세요</p>
    </div>
</div>

<script>
    function setQuestion(q) {{
        var input = document.querySelector('.search-input');
        input.value = q;
        input.focus();
    }}

    function showLoading() {{
        document.getElementById('loading-overlay').style.display = 'flex';
        var resultArea = document.getElementById('result-area');
        if (resultArea) {{
            resultArea.innerHTML = '<div class="loading-placeholder" style="padding:2rem;text-align:center;color:#666;">질문을 처리하고 있습니다...</div>';
        }}
    }}

    document.addEventListener('DOMContentLoaded', function() {{
        var form = document.querySelector('.search-form');
        if (form) {{
            form.addEventListener('submit', function(e) {{
                var input = document.querySelector('.search-input');
                if (input && input.value.trim()) {{
                    showLoading();
                }}
            }});
        }}
    }});
</script>
'''

        return html

    def _get_save_buttons_html(self, question: str, llm_provider: str) -> str:
        """저장 버튼 HTML 생성"""
        import html as html_lib
        escaped_q = html_lib.escape(question)

        return f'''
<div class="save-buttons-container" style="margin-top: 1rem; padding: 1rem; background: #f0f4f8; border-radius: 10px; text-align: center; border-top: 1px solid #e0e0e0;">
    <span style="font-weight: 600; color: #333; margin-right: 1rem;">결과 저장:</span>

    <form method="post" style="display: inline-block; margin: 0 0.3rem;">
        <input type="hidden" name="action" value="save_md">
        <input type="hidden" name="q" value="{escaped_q}">
        <input type="hidden" name="llm" value="{llm_provider}">
        <button type="submit" class="save-btn" style="
            padding: 0.5rem 1rem;
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
        ">📝 MD 저장</button>
    </form>

    <form method="post" style="display: inline-block; margin: 0 0.3rem;">
        <input type="hidden" name="action" value="save_ppt">
        <input type="hidden" name="q" value="{escaped_q}">
        <input type="hidden" name="llm" value="{llm_provider}">
        <button type="submit" class="save-btn" style="
            padding: 0.5rem 1rem;
            background: linear-gradient(135deg, #e67e22, #d35400);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
        ">📊 PPT 저장</button>
    </form>
</div>
'''

    def handle_post(self, form_data: Dict[str, str], template_path: Optional[str] = None):
        """
        POST 요청 처리 (MD/PPT 저장)

        main_app.py에서 POST 요청을 받았을 때 호출합니다.

        사용 예 (main_app.py):
            if request.method == 'POST':
                return _core.handle_post(request.form)

        Args:
            form_data: request.form 딕셔너리
            template_path: PPT 템플릿 경로

        Returns:
            Flask Response (파일 다운로드 또는 에러)
        """
        from flask import Response, make_response
        from urllib.parse import quote

        action = form_data.get('action')
        question = form_data.get('q', '')
        llm_provider = form_data.get('llm', 'claude-haiku')

        if not question:
            return Response(
                "<script>alert('질문이 없습니다.'); history.back();</script>",
                mimetype='text/html'
            )

        try:
            # 질문 처리
            result = self.process_question(question, llm_provider)

            if result.get('error'):
                return Response(
                    f"<script>alert('오류: {result['error'][:100]}'); history.back();</script>",
                    mimetype='text/html'
                )

            if action == 'save_md':
                md_path = self.save_result_to_md(question, result)
                if md_path and md_path.exists():
                    # 한글 파일명 인코딩 처리
                    with open(md_path, 'rb') as f:
                        file_data = f.read()

                    response = make_response(file_data)
                    response.headers['Content-Type'] = 'text/markdown; charset=utf-8'
                    encoded_filename = quote(md_path.name)
                    response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
                    response.headers['Content-Length'] = len(file_data)
                    return response
                return Response(
                    "<script>alert('MD 저장에 실패했습니다.'); history.back();</script>",
                    mimetype='text/html'
                )

            elif action == 'save_ppt':
                # PPT 저장 시 MD 파일도 함께 생성
                md_path = self.save_result_to_md(question, result)
                if md_path:
                    logger.info(f"MD 파일 자동 생성 완료: {md_path}")

                ppt_path = self.save_result_to_ppt(question, result, template_path=template_path)
                if ppt_path and ppt_path.exists():
                    # 한글 파일명 인코딩 처리 (RFC 5987)
                    with open(ppt_path, 'rb') as f:
                        file_data = f.read()

                    response = make_response(file_data)
                    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    encoded_filename = quote(ppt_path.name)
                    response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
                    response.headers['Content-Length'] = len(file_data)
                    return response
                return Response(
                    "<script>alert('PPT 저장에 실패했습니다. python-pptx가 설치되어 있는지 확인하세요.'); history.back();</script>",
                    mimetype='text/html'
                )

            return Response(
                "<script>alert('잘못된 요청입니다.'); history.back();</script>",
                mimetype='text/html'
            )

        except Exception as e:
            logger.error(f"POST 처리 오류: {e}")
            return Response(
                f"<script>alert('저장 중 오류: {str(e)[:100]}'); history.back();</script>",
                mimetype='text/html'
            )

    def save_result_to_md(
        self,
        question: str,
        process_result: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> Optional[Path]:
        """
        LLM 질의 결과를 마크다운 파일로 저장

        Args:
            question: 사용자 질문
            process_result: process_question() 결과 딕셔너리
            output_path: 저장 경로 (None이면 caller_file과 같은 이름으로)

        Returns:
            Path: 저장된 MD 파일 경로
        """
        try:
            from module.report_generator import DashboardReport

            # 제목 생성
            title = f"{self.domain_name} 질의 결과"
            subtitle = f"질문: {question}"

            # 보고서 객체 생성
            report = DashboardReport(
                title=title,
                subtitle=subtitle,
                source_file=self.caller_file,
                output_dir=str(self.output_dir) if output_path is None else None
            )

            # 1. AI 인사이트를 가장 먼저 표시 (사용자 요청)
            if process_result.get('response'):
                report.add_section("AI 분석 인사이트", process_result['response'])

            # 2. 기준년월 정보
            if process_result.get('base_ym'):
                base_ym = process_result['base_ym']
                year = base_ym[:4]
                month = base_ym[4:6] if len(base_ym) >= 6 else ""
                subtitle += f" | 기준: {year}년 {month}월"

            # 3. 데이터 테이블 추가 (MD에서 표로 표시)
            if process_result.get('dataframe') is not None:
                df = process_result['dataframe']
                if not df.empty:
                    report.add_table("분석 결과 데이터", df, max_rows=30)

            # 4. 차트 이미지 추가 (MD에서 상대 경로로 참조)
            if process_result.get('chart_relative_path'):
                report.add_chart("분석 차트", process_result['chart_relative_path'])
            elif process_result.get('saved_files'):
                for file_path in process_result['saved_files']:
                    if file_path.endswith('.png'):
                        report.add_chart("분석 차트", file_path)

            # 5. SQL 정보
            if process_result.get('sql'):
                report.add_section("생성된 SQL", f"```sql\n{process_result['sql']}\n```")

            # 6. 모델 정보
            if process_result.get('model_display_name'):
                model_info = f"AI 모델: {process_result['model_display_name']}"
                if process_result.get('usage'):
                    usage = process_result['usage']
                    model_info += f"\n토큰 사용량: 입력 {usage.get('input_tokens', 0):,} / 출력 {usage.get('output_tokens', 0):,}"
                report.add_section("AI 모델 정보", model_info)

            # 저장
            if output_path:
                md_path = report.save_markdown(output_path)
            else:
                # caller_file과 같은 이름으로 저장
                caller_path = Path(self.caller_file)
                md_path = caller_path.parent / f"{caller_path.stem}.md"
                md_path.write_text(report.to_markdown(), encoding='utf-8')

            logger.info(f"MD 저장 완료: {md_path}")
            return md_path

        except Exception as e:
            logger.error(f"MD 저장 오류: {e}")
            return None

    def save_result_to_ppt(
        self,
        question: str,
        process_result: Dict[str, Any],
        output_path: Optional[str] = None,
        template_path: Optional[str] = None
    ) -> Optional[Path]:
        """
        LLM 질의 결과를 PPT 파일로 저장

        Args:
            question: 사용자 질문
            process_result: process_question() 결과 딕셔너리
            output_path: 저장 경로 (None이면 caller_file과 같은 이름으로)
            template_path: PPT 템플릿 경로

        Returns:
            Path: 저장된 PPT 파일 경로
        """
        try:
            from module.report_generator import DashboardReport, PPT_AVAILABLE

            if not PPT_AVAILABLE:
                logger.warning("python-pptx가 설치되지 않았습니다.")
                return None

            # 제목 생성
            title = f"{self.domain_name} 분석 결과"
            subtitle = f"질문: {question}"

            # 기준년월 추가
            if process_result.get('base_ym'):
                base_ym = process_result['base_ym']
                year = base_ym[:4]
                month = base_ym[4:6] if len(base_ym) >= 6 else ""
                subtitle += f" | 기준: {year}년 {month}월"

            # 보고서 객체 생성
            report = DashboardReport(
                title=title,
                subtitle=subtitle,
                source_file=self.caller_file,
                output_dir=str(self.output_dir) if output_path is None else None
            )

            # 모델 정보 지표로 추가
            if process_result.get('model_display_name'):
                report.add_metric(
                    label="AI 모델",
                    value=process_result['model_display_name'],
                    unit=""
                )

            if process_result.get('usage'):
                usage = process_result['usage']
                report.add_metric(
                    label="토큰 사용량",
                    value=f"{usage.get('total_tokens', 0):,}",
                    unit="토큰"
                )

            # 데이터 테이블 추가
            if process_result.get('dataframe') is not None:
                df = process_result['dataframe']
                if not df.empty:
                    report.add_table("분석 결과 데이터", df, max_rows=20)

            # AI 분석 결과 텍스트 추가 (가장 중요!)
            # ## 섹션별로 분할하여 각각 슬라이드로 생성
            if process_result.get('response'):
                response_text = process_result['response']

                # 마크다운의 ## 섹션별로 분할하여 각각 add_section 호출
                # 이렇게 하면 PPT에서 각 섹션이 별도 슬라이드로 생성됨
                sections = self._parse_markdown_sections(response_text)

                for section in sections:
                    report.add_section(section['title'], section['content'])

                # 짧은 인사이트도 추가 (주요 인사이트 슬라이드용)
                # 처음 4개 섹션만 인사이트로 추가
                icons = ["🤖", "📊", "📈", "💡"]
                for i, section in enumerate(sections[:4]):
                    content = section['content']
                    # 마크다운 형식 정리
                    clean_content = re.sub(r'^#{1,6}\s*', '', content, flags=re.MULTILINE)
                    clean_content = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean_content)
                    clean_content = re.sub(r'```[\s\S]*?```', '', clean_content)  # 코드블록 제거

                    # 첫 단락만 추출 (인사이트용)
                    first_para = clean_content.split('\n\n')[0] if '\n\n' in clean_content else clean_content
                    if len(first_para) > 300:
                        first_para = first_para[:300] + "..."

                    if first_para.strip():
                        report.add_insight(
                            icon=icons[i % len(icons)],
                            title=section['title'],
                            content=first_para.strip()
                        )

            # 차트 이미지 추가
            if process_result.get('saved_files'):
                for file_path in process_result['saved_files']:
                    if file_path.endswith('.png'):
                        report.add_chart("분석 결과 차트", file_path)

            # SQL 정보 섹션으로 추가 (간략히)
            if process_result.get('sql'):
                sql_text = process_result['sql']
                if len(sql_text) > 300:
                    sql_text = sql_text[:300] + "..."
                # report.add_section("실행된 SQL 쿼리", sql_text)  # SQL은 생략 (PPT에서 불필요)

            # 에러가 있는 경우 에러 메시지 추가
            if process_result.get('error'):
                report.add_section("오류 정보", process_result['error'])

            # 저장 경로 결정 (타임스탬프 추가로 파일 충돌 방지)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if output_path:
                ppt_save_path = Path(output_path)
            else:
                # caller_file과 같은 이름 + 타임스탬프로 저장
                caller_path = Path(self.caller_file)
                ppt_save_path = caller_path.parent / f"{caller_path.stem}_{timestamp}.pptx"

            # MD 파일 먼저 저장 (PPT 생성 전에 내부적으로 생성)
            md_save_path = ppt_save_path.with_suffix('.md')
            md_path = report.save_markdown(str(md_save_path))
            logger.info(f"MD 저장 완료: {md_path}")

            # PPT 저장 (파일이 열려있으면 새 파일명으로 시도)
            try:
                ppt_path = report.save_ppt(str(ppt_save_path), template_path)
            except PermissionError:
                # 파일이 열려있으면 새 타임스탬프로 재시도
                new_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
                caller_path = Path(self.caller_file)
                ppt_save_path = caller_path.parent / f"{caller_path.stem}_{new_timestamp}.pptx"
                ppt_path = report.save_ppt(str(ppt_save_path), template_path)

            logger.info(f"PPT 저장 완료: {ppt_path}")

            return ppt_path

        except Exception as e:
            logger.error(f"PPT 저장 오류: {e}")
            return None
