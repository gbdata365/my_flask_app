# -*- coding: utf-8 -*-
"""
데이터콩 - 인구통계 도메인
=========================

인구통계 데이터에 대한 자연어 질의 챗봇입니다.
공통 기능은 module.datacong_core에서 제공됩니다.

사용법:
    Flask 앱에서 /01_인구및가구현황/routes/데이터콩 경로로 접속

Author: Claude AI Agent
Created: 2025-01-10
Updated: 2025-01-12 (공통 모듈 분리)
"""

import sys
from pathlib import Path
from typing import Optional, Dict

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 공통 모듈 임포트
from module.datacong_core import DataCongCore


# =============================================================================
# 도메인 설정 (Domain Configuration)
# =============================================================================

# 도메인 기본 정보
DOMAIN_NAME = "인구통계"
DOMAIN_BASE = Path(__file__).parent.parent
CURRENT_FILE = __file__

# 예시 질문 목록 (도메인 특화)
EXAMPLE_QUESTIONS = [
    "고령화율이 가장 높은 시군구 10개",
    "경상북도에서 1인가구 비율 높은 시군",
    "경북 시군구별 고령화율 차트",           # 막대 차트 예시
    "인구가 가장 많은 시군구 20개",
    "전라남도 노인인구 많은 시군",
    "경북 시군구별 6세이하 인구비율 그래프",  # 막대 차트 예시
    "유소년 인구 비율이 높은 곳",
    "80세 이상 비율 높은 읍면동 20개",
    # 시계열 분석 예시
    "경북 구미시 고령화율 월별 추이",        # 라인 차트 (단일 지역)
    "경북 주요 시군 인구 추이 비교",         # 라인 차트 (여러 지역)
    "서울 고령화율 전월 대비 변화",          # 전월 대비
    "경기도 인구 전년 동월 대비",            # 전년 동월 대비
]

# 챗봇 설정
CHAT_TITLE = "AI 인구통계 질의 챗봇"
CHAT_SUBTITLE = "인구, 고령화율, 1인가구 등 인구통계 데이터를 자연어로 질문하세요"
    

# =============================================================================
# 코어 인스턴스 생성
# =============================================================================

_core = DataCongCore(
    domain_name=DOMAIN_NAME,
    domain_base=DOMAIN_BASE,
    caller_file=CURRENT_FILE,
    example_questions=EXAMPLE_QUESTIONS,
    chat_title=CHAT_TITLE,
    chat_subtitle=CHAT_SUBTITLE
)


# =============================================================================
# 메인 렌더링 함수 (Flask 라우트용)
# =============================================================================

def render(request_args: Optional[Dict[str, str]] = None, request_form: Optional[Dict[str, str]] = None, method: str = 'GET') -> str:
    """
    데이터콩 인구통계 페이지 렌더링

    Args:
        request_args: HTTP GET 요청 파라미터
            - 'q': 사용자 질문
            - 'llm': LLM 제공자 ('claude', 'openai', 'solar')
        request_form: HTTP POST 요청 데이터 (MD/PPT 저장 시)
        method: 요청 메서드 ('GET' 또는 'POST')

    Returns:
        str: 완전한 HTML 페이지 또는 파일 다운로드 Response
    """
    # POST 요청 처리 (MD/PPT 저장)
    if method == 'POST' and request_form:
        action = request_form.get('action')
        if action in ('save_md', 'save_ppt'):
            return _core.handle_post(request_form)

    return _core.render(request_args)
