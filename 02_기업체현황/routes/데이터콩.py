# -*- coding: utf-8 -*-
"""
데이터콩 - 기업체현황 도메인
===========================

기업체현황 데이터와 인구통계를 연계하여 분석하는 AI 챗봇입니다.
지역의 인구 구조와 기업 현황을 종합적으로 분석하여 인사이트를 제공합니다.

공통 기능은 module.datacong_core에서 제공됩니다.

분석 가능한 데이터:
    - 기업통계등록부(SBR): 사업체수, 종사자수, 조직형태, 산업분류 등
    - 인구통계: 총인구, 고령화율, 1인가구 비율 등
    - 연계 분석: 인구 대비 사업체수, 고령화율과 산업구조 관계 등

사용법:
    Flask 앱에서 /02_기업체현황/routes/데이터콩 경로로 접속

Author: Claude AI Agent
Created: 2025-01-15
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
DOMAIN_NAME = "기업체현황"
DOMAIN_BASE = Path(__file__).parent.parent
CURRENT_FILE = __file__

# 예시 질문 목록 (기업+인구 연계 분석 특화)
EXAMPLE_QUESTIONS = [
    # 기업체 현황 기본
    "경상북도 시군구별 사업체수 현황",
    "제조업 사업체가 가장 많은 시군구 10개",
    "여성 대표 사업체 비율 높은 지역",
    "도소매업 사업체수 차트",

    # 인구 연계 분석
    "인구 천명당 사업체수 높은 시군구",
    "고령화율 대비 사업체수 관계",
    "경북에서 인구 대비 제조업 비율 높은 시군",

    # 시계열/추이 분석
    "경상북도 사업체수 분기별 추이",
    "포항시 산업별 사업체 변화 추이",

    # 심층 분석
    "폐업률 높은 시군구 분석",
    "개인사업체 vs 회사법인 비율 지역 비교",
]

# 챗봇 설정
CHAT_TITLE = "AI 기업체현황 분석 챗봇"
CHAT_SUBTITLE = "기업통계와 인구데이터를 연계하여 지역 산업구조를 분석합니다. 자연어로 질문하세요."


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

def render(
    request_args: Optional[Dict[str, str]] = None,
    request_form: Optional[Dict[str, str]] = None,
    method: str = 'GET'
) -> str:
    """
    데이터콩 기업체현황 페이지 렌더링

    Args:
        request_args: HTTP GET 요청 파라미터
            - 'q': 사용자 질문
            - 'llm': LLM 제공자 ('claude-haiku', 'openai', 'claude' 등)
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
