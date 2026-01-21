# -*- coding: utf-8 -*-
"""
LLM API 클라이언트 모듈
======================

Claude, OpenAI GPT, Upstage Solar API를 통합하여 사용할 수 있는 클라이언트입니다.
환경변수에서 API 키를 읽어오며, 사용자가 원하는 LLM을 선택할 수 있습니다.

환경 변수:
    - ANTHROPIC_API_KEY: Claude API 키
    - OPENAI_API_KEY: OpenAI API 키
    - UPSTAGE_API_KEY: Upstage Solar API 키
    - LLM_PROVIDER: 기본 LLM 제공자 (claude, openai 또는 solar)

Rate Limit 환경 변수 (선택):
    - LLM_RATE_LIMIT_WARN_PERCENT: 경고 임계값 (기본: 20, 남은 한도가 20% 이하면 경고)
    - LLM_AUTO_FALLBACK: 자동 폴백 활성화 (기본: true)
    - LLM_FALLBACK_ORDER: 폴백 순서 (기본: claude,openai,solar)

사용 예시:
    >>> from module.llm_client import LLMClient, LLMClientWithFallback
    >>> client = LLMClient()
    >>> response = client.chat("안녕하세요")
    >>> print(response)
    >>> print(client.get_model_info())  # 모델 정보 확인
    >>> print(client.get_rate_limit_info())  # 한도 정보 확인

    # 자동 폴백 사용
    >>> client = LLMClientWithFallback()
    >>> response = client.chat("안녕하세요")  # 한도 초과 시 자동으로 다음 LLM으로 전환
"""

import os
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

# .env 파일 로드 (여러 위치에서 검색)
_module_dir = Path(__file__).parent
_env_paths = [
    _module_dir.parent / '01_population' / '.env',  # 01_population/.env 우선
    _module_dir / '.env',
    _module_dir.parent / '.env',
    _module_dir.parent / 'project' / '.env',
]

for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        break


@dataclass
class UsageInfo:
    """API 사용량 정보를 담는 데이터 클래스"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class RateLimitInfo:
    """Rate Limit 정보를 담는 데이터 클래스"""
    # 요청 한도
    limit_requests: Optional[int] = None      # 전체 요청 한도
    remaining_requests: Optional[int] = None  # 남은 요청 수
    reset_requests: Optional[str] = None      # 요청 한도 리셋 시간

    # 토큰 한도
    limit_tokens: Optional[int] = None        # 전체 토큰 한도
    remaining_tokens: Optional[int] = None    # 남은 토큰 수
    reset_tokens: Optional[str] = None        # 토큰 한도 리셋 시간

    # 메타 정보
    provider: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def requests_percent_remaining(self) -> Optional[float]:
        """남은 요청 비율 (%)"""
        if self.limit_requests and self.remaining_requests is not None:
            return round(self.remaining_requests / self.limit_requests * 100, 1)
        return None

    @property
    def tokens_percent_remaining(self) -> Optional[float]:
        """남은 토큰 비율 (%)"""
        if self.limit_tokens and self.remaining_tokens is not None:
            return round(self.remaining_tokens / self.limit_tokens * 100, 1)
        return None

    def is_low(self, threshold_percent: float = 20.0) -> bool:
        """한도가 임계값 이하인지 확인"""
        req_pct = self.requests_percent_remaining
        tok_pct = self.tokens_percent_remaining

        if req_pct is not None and req_pct <= threshold_percent:
            return True
        if tok_pct is not None and tok_pct <= threshold_percent:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider,
            'limit_requests': self.limit_requests,
            'remaining_requests': self.remaining_requests,
            'requests_percent_remaining': self.requests_percent_remaining,
            'reset_requests': self.reset_requests,
            'limit_tokens': self.limit_tokens,
            'remaining_tokens': self.remaining_tokens,
            'tokens_percent_remaining': self.tokens_percent_remaining,
            'reset_tokens': self.reset_tokens,
            'timestamp': self.timestamp.isoformat(),
        }

    def __str__(self) -> str:
        parts = [f"[{self.provider}]"]
        if self.remaining_requests is not None:
            parts.append(f"요청: {self.remaining_requests:,}/{self.limit_requests:,} ({self.requests_percent_remaining}%)")
        if self.remaining_tokens is not None:
            parts.append(f"토큰: {self.remaining_tokens:,}/{self.limit_tokens:,} ({self.tokens_percent_remaining}%)")
        return " | ".join(parts)


@dataclass
class ModelInfo:
    """모델 정보를 담는 데이터 클래스"""
    provider: str           # 'claude' 또는 'solar'
    model_id: str          # 실제 모델 ID
    display_name: str      # 표시용 이름
    last_usage: Optional[UsageInfo] = None
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider,
            'model_id': self.model_id,
            'display_name': self.display_name,
            'total_calls': self.total_calls,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'last_usage': self.last_usage.to_dict() if self.last_usage else None,
        }


class BaseLLMClient(ABC):
    """LLM 클라이언트 기본 클래스"""

    model: str = ""
    display_name: str = ""
    provider_id: str = ""  # claude, openai, solar
    _last_usage: Optional[UsageInfo] = None
    _rate_limit_info: Optional[RateLimitInfo] = None
    _total_calls: int = 0
    _total_input_tokens: int = 0
    _total_output_tokens: int = 0

    @abstractmethod
    def chat(self, message: str, system_prompt: str = None) -> str:
        """메시지를 보내고 응답을 받습니다."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """API가 사용 가능한지 확인합니다."""
        pass

    def get_model_name(self) -> str:
        """모델 ID 반환"""
        return self.model

    def get_display_name(self) -> str:
        """표시용 이름 반환"""
        return self.display_name

    def get_last_usage(self) -> Optional[UsageInfo]:
        """마지막 API 호출의 사용량 정보 반환"""
        return self._last_usage

    def get_rate_limit_info(self) -> Optional[RateLimitInfo]:
        """마지막 API 호출의 Rate Limit 정보 반환"""
        return self._rate_limit_info

    def get_usage_stats(self) -> Dict[str, int]:
        """누적 사용량 통계 반환"""
        return {
            'total_calls': self._total_calls,
            'total_input_tokens': self._total_input_tokens,
            'total_output_tokens': self._total_output_tokens,
        }


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude API 클라이언트 (Sonnet 4 - 고성능)"""

    def __init__(self):
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.model = "claude-sonnet-4-20250514"
        self.display_name = "Claude Sonnet 4"
        self.provider_id = "claude"
        self._client = None
        self._last_usage = None
        self._rate_limit_info = None
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic 패키지가 설치되지 않았습니다. pip install anthropic")
                raise
        return self._client

    def _parse_rate_limit_headers(self, headers) -> RateLimitInfo:
        def safe_int(val):
            try:
                return int(val) if val else None
            except (ValueError, TypeError):
                return None
        return RateLimitInfo(
            limit_requests=safe_int(headers.get('anthropic-ratelimit-requests-limit')),
            remaining_requests=safe_int(headers.get('anthropic-ratelimit-requests-remaining')),
            reset_requests=headers.get('anthropic-ratelimit-requests-reset'),
            limit_tokens=safe_int(headers.get('anthropic-ratelimit-tokens-limit')),
            remaining_tokens=safe_int(headers.get('anthropic-ratelimit-tokens-remaining')),
            reset_tokens=headers.get('anthropic-ratelimit-tokens-reset'),
            provider=self.provider_id,
        )

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_anthropic_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        if not self.is_available():
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        try:
            client = self._get_client()
            kwargs = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": message}]
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            raw_response = client.messages.with_raw_response.create(**kwargs)
            response = raw_response.parse()
            self._rate_limit_info = self._parse_rate_limit_headers(raw_response.headers)
            warn_threshold = float(os.environ.get('LLM_RATE_LIMIT_WARN_PERCENT', '20'))
            if self._rate_limit_info.is_low(warn_threshold):
                logger.warning(f"⚠️ Rate Limit 경고: {self._rate_limit_info}")
            usage = response.usage
            self._last_usage = UsageInfo(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.input_tokens + usage.output_tokens,
            )
            self._total_calls += 1
            self._total_input_tokens += usage.input_tokens
            self._total_output_tokens += usage.output_tokens
            logger.debug(f"Claude 사용량 - 입력: {usage.input_tokens}, 출력: {usage.output_tokens}")
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API 호출 실패: {e}")
            raise


class ClaudeHaikuClient(BaseLLMClient):
    """Anthropic Claude 3.5 Haiku API 클라이언트 (빠르고 저렴)"""

    def __init__(self):
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.model = "claude-3-5-haiku-20241022"
        self.display_name = "Claude 3.5 Haiku"
        self.provider_id = "claude-haiku"
        self._client = None
        self._last_usage = None
        self._rate_limit_info = None
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic 패키지가 설치되지 않았습니다. pip install anthropic")
                raise
        return self._client

    def _parse_rate_limit_headers(self, headers) -> RateLimitInfo:
        def safe_int(val):
            try:
                return int(val) if val else None
            except (ValueError, TypeError):
                return None
        return RateLimitInfo(
            limit_requests=safe_int(headers.get('anthropic-ratelimit-requests-limit')),
            remaining_requests=safe_int(headers.get('anthropic-ratelimit-requests-remaining')),
            reset_requests=headers.get('anthropic-ratelimit-requests-reset'),
            limit_tokens=safe_int(headers.get('anthropic-ratelimit-tokens-limit')),
            remaining_tokens=safe_int(headers.get('anthropic-ratelimit-tokens-remaining')),
            reset_tokens=headers.get('anthropic-ratelimit-tokens-reset'),
            provider=self.provider_id,
        )

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_anthropic_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        if not self.is_available():
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        try:
            client = self._get_client()
            kwargs = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": message}]
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            raw_response = client.messages.with_raw_response.create(**kwargs)
            response = raw_response.parse()
            self._rate_limit_info = self._parse_rate_limit_headers(raw_response.headers)
            usage = response.usage
            self._last_usage = UsageInfo(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.input_tokens + usage.output_tokens,
            )
            self._total_calls += 1
            self._total_input_tokens += usage.input_tokens
            self._total_output_tokens += usage.output_tokens
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude Haiku API 호출 실패: {e}")
            raise


class Claude3HaikuClient(BaseLLMClient):
    """Anthropic Claude 3 Haiku API 클라이언트 (가장 저렴)"""

    def __init__(self):
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.model = "claude-3-haiku-20240307"
        self.display_name = "Claude 3 Haiku"
        self.provider_id = "claude-3-haiku"
        self._client = None
        self._last_usage = None
        self._rate_limit_info = None
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic 패키지가 설치되지 않았습니다. pip install anthropic")
                raise
        return self._client

    def _parse_rate_limit_headers(self, headers) -> RateLimitInfo:
        def safe_int(val):
            try:
                return int(val) if val else None
            except (ValueError, TypeError):
                return None
        return RateLimitInfo(
            limit_requests=safe_int(headers.get('anthropic-ratelimit-requests-limit')),
            remaining_requests=safe_int(headers.get('anthropic-ratelimit-requests-remaining')),
            reset_requests=headers.get('anthropic-ratelimit-requests-reset'),
            limit_tokens=safe_int(headers.get('anthropic-ratelimit-tokens-limit')),
            remaining_tokens=safe_int(headers.get('anthropic-ratelimit-tokens-remaining')),
            reset_tokens=headers.get('anthropic-ratelimit-tokens-reset'),
            provider=self.provider_id,
        )

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_anthropic_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        if not self.is_available():
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        try:
            client = self._get_client()
            kwargs = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": message}]
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            raw_response = client.messages.with_raw_response.create(**kwargs)
            response = raw_response.parse()
            self._rate_limit_info = self._parse_rate_limit_headers(raw_response.headers)
            usage = response.usage
            self._last_usage = UsageInfo(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.input_tokens + usage.output_tokens,
            )
            self._total_calls += 1
            self._total_input_tokens += usage.input_tokens
            self._total_output_tokens += usage.output_tokens
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude 3 Haiku API 호출 실패: {e}")
            raise


class SolarClient(BaseLLMClient):
    """Upstage Solar API 클라이언트"""

    def __init__(self):
        self.api_key = os.environ.get('UPSTAGE_API_KEY', '')
        self.model = "solar-pro"
        self.display_name = "Solar Pro"
        self.provider_id = "solar"
        self.base_url = "https://api.upstage.ai/v1/solar"
        self._client = None
        self._last_usage = None
        self._rate_limit_info = None  # Solar는 Rate Limit 헤더를 제공하지 않을 수 있음
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                logger.error("openai 패키지가 설치되지 않았습니다. pip install openai")
                raise
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_upstage_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        if not self.is_available():
            raise ValueError("UPSTAGE_API_KEY가 설정되지 않았습니다.")

        try:
            client = self._get_client()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=4096
            )

            # Solar는 Rate Limit 헤더를 제공하지 않으므로 기본값 사용
            self._rate_limit_info = RateLimitInfo(provider=self.provider_id)

            # 사용량 정보 추출 및 저장 (OpenAI 호환 형식)
            usage = response.usage
            if usage:
                self._last_usage = UsageInfo(
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                )

                # 누적 통계 업데이트
                self._total_calls += 1
                self._total_input_tokens += usage.prompt_tokens
                self._total_output_tokens += usage.completion_tokens

                logger.debug(f"Solar 사용량 - 입력: {usage.prompt_tokens}, 출력: {usage.completion_tokens}")

            return response.choices[0].message.content

        except ImportError:
            logger.error("openai 패키지가 설치되지 않았습니다. pip install openai")
            raise
        except Exception as e:
            logger.error(f"Solar API 호출 실패: {e}")
            raise


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT API 클라이언트"""

    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        self.model = "gpt-4o-mini"  # 비용 효율적인 기본 모델
        self.display_name = "GPT-4o Mini"
        self.provider_id = "openai"
        self._client = None
        self._last_usage = None
        self._rate_limit_info = None
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("openai 패키지가 설치되지 않았습니다. pip install openai")
                raise
        return self._client

    def _parse_rate_limit_headers(self, headers) -> RateLimitInfo:
        """HTTP 응답 헤더에서 Rate Limit 정보 추출"""
        def safe_int(val):
            try:
                return int(val) if val else None
            except (ValueError, TypeError):
                return None

        return RateLimitInfo(
            # 요청 한도
            limit_requests=safe_int(headers.get('x-ratelimit-limit-requests')),
            remaining_requests=safe_int(headers.get('x-ratelimit-remaining-requests')),
            reset_requests=headers.get('x-ratelimit-reset-requests'),
            # 토큰 한도
            limit_tokens=safe_int(headers.get('x-ratelimit-limit-tokens')),
            remaining_tokens=safe_int(headers.get('x-ratelimit-remaining-tokens')),
            reset_tokens=headers.get('x-ratelimit-reset-tokens'),
            provider=self.provider_id,
        )

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_openai_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        if not self.is_available():
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

        try:
            client = self._get_client()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

            # with_raw_response를 사용하여 HTTP 헤더에 접근
            raw_response = client.chat.completions.with_raw_response.create(
                model=self.model,
                messages=messages,
                max_tokens=4096
            )
            response = raw_response.parse()

            # Rate Limit 정보 추출 및 저장
            self._rate_limit_info = self._parse_rate_limit_headers(raw_response.headers)

            # 경고 임계값 체크
            warn_threshold = float(os.environ.get('LLM_RATE_LIMIT_WARN_PERCENT', '20'))
            if self._rate_limit_info.is_low(warn_threshold):
                logger.warning(f"⚠️ Rate Limit 경고: {self._rate_limit_info}")

            # 사용량 정보 추출 및 저장
            usage = response.usage
            if usage:
                self._last_usage = UsageInfo(
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                )

                # 누적 통계 업데이트
                self._total_calls += 1
                self._total_input_tokens += usage.prompt_tokens
                self._total_output_tokens += usage.completion_tokens

                logger.debug(f"OpenAI 사용량 - 입력: {usage.prompt_tokens}, 출력: {usage.completion_tokens}")
                logger.debug(f"OpenAI Rate Limit - {self._rate_limit_info}")

            return response.choices[0].message.content

        except ImportError:
            logger.error("openai 패키지가 설치되지 않았습니다. pip install openai")
            raise
        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {e}")
            raise


class GPT4oClient(BaseLLMClient):
    """OpenAI GPT-4o API 클라이언트 (고성능)"""

    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        self.model = "gpt-4o"
        self.display_name = "GPT-4o"
        self.provider_id = "gpt-4o"
        self._client = None
        self._last_usage = None
        self._rate_limit_info = None
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_openai_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        if not self.is_available():
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        response = client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=4096
        )
        usage = response.usage
        if usage:
            self._last_usage = UsageInfo(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
            self._total_calls += 1
            self._total_input_tokens += usage.prompt_tokens
            self._total_output_tokens += usage.completion_tokens
        return response.choices[0].message.content


class GPT35TurboClient(BaseLLMClient):
    """OpenAI GPT-3.5 Turbo API 클라이언트 (가장 저렴)"""

    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        self.model = "gpt-3.5-turbo"
        self.display_name = "GPT-3.5 Turbo"
        self.provider_id = "gpt-3.5-turbo"
        self._client = None
        self._last_usage = None
        self._rate_limit_info = None
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_openai_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        if not self.is_available():
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        response = client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=4096
        )
        usage = response.usage
        if usage:
            self._last_usage = UsageInfo(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
            self._total_calls += 1
            self._total_input_tokens += usage.prompt_tokens
            self._total_output_tokens += usage.completion_tokens
        return response.choices[0].message.content


class SolarMiniClient(BaseLLMClient):
    """Upstage Solar Mini API 클라이언트 (저렴)"""

    def __init__(self):
        self.api_key = os.environ.get('UPSTAGE_API_KEY', '')
        self.model = "solar-mini"
        self.display_name = "Solar Mini"
        self.provider_id = "solar-mini"
        self.base_url = "https://api.upstage.ai/v1/solar"
        self._client = None
        self._last_usage = None
        self._rate_limit_info = None
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_upstage_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        if not self.is_available():
            raise ValueError("UPSTAGE_API_KEY가 설정되지 않았습니다.")
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        response = client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=4096
        )
        usage = response.usage
        if usage:
            self._last_usage = UsageInfo(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
            self._total_calls += 1
            self._total_input_tokens += usage.prompt_tokens
            self._total_output_tokens += usage.completion_tokens
        return response.choices[0].message.content


class LLMClient:
    """
    통합 LLM 클라이언트

    Claude, OpenAI GPT, Solar 중 선택하여 사용할 수 있습니다.

    Args:
        provider: 사용할 LLM 제공자 ('claude', 'openai' 또는 'solar')
                 None이면 환경변수 LLM_PROVIDER 또는 기본값 'claude' 사용

    Examples:
        >>> client = LLMClient()  # 기본값 claude
        >>> client = LLMClient(provider='openai')  # OpenAI GPT 사용
        >>> client = LLMClient(provider='solar')  # Solar 사용
        >>> response = client.chat("안녕하세요")
        >>> print(client.get_model_info())  # 모델 정보 확인
    """

    # 가성비 순서로 정렬 (저렴한 것이 위로)
    PROVIDERS = {
        'claude-haiku': ClaudeHaikuClient,       # Claude 3.5 Haiku (추천)
        'openai': OpenAIClient,                  # GPT-4o-mini
        'claude-3-haiku': Claude3HaikuClient,    # Claude 3 Haiku (가장 저렴)
        'gpt-3.5-turbo': GPT35TurboClient,       # GPT-3.5 Turbo
        'solar-mini': SolarMiniClient,           # Solar Mini
        'claude': ClaudeClient,                  # Claude Sonnet 4 (고성능)
        'gpt-4o': GPT4oClient,                   # GPT-4o (고성능)
        'solar': SolarClient,                    # Solar Pro
    }

    def __init__(self, provider: str = None):
        self.provider_name = provider or os.environ.get('LLM_PROVIDER', 'claude-haiku')
        self.provider_name = self.provider_name.lower()

        if self.provider_name not in self.PROVIDERS:
            raise ValueError(f"지원하지 않는 LLM 제공자: {self.provider_name}. 사용 가능: {list(self.PROVIDERS.keys())}")

        self._client = self.PROVIDERS[self.provider_name]()
        logger.info(f"LLM 클라이언트 초기화: {self.provider_name} ({self._client.model})")

    def is_available(self) -> bool:
        """현재 선택된 LLM이 사용 가능한지 확인"""
        return self._client.is_available()

    def chat(self, message: str, system_prompt: str = None) -> str:
        """
        LLM에 메시지를 보내고 응답을 받습니다.

        Args:
            message: 사용자 메시지
            system_prompt: 시스템 프롬프트 (선택사항)

        Returns:
            LLM 응답 텍스트
        """
        return self._client.chat(message, system_prompt)

    def get_provider_name(self) -> str:
        """현재 사용 중인 LLM 제공자 이름 반환"""
        return self.provider_name

    def get_model_name(self) -> str:
        """현재 사용 중인 모델 ID 반환"""
        return self._client.get_model_name()

    def get_display_name(self) -> str:
        """현재 사용 중인 모델의 표시용 이름 반환"""
        return self._client.get_display_name()

    def get_last_usage(self) -> Optional[UsageInfo]:
        """마지막 API 호출의 사용량 정보 반환"""
        return self._client.get_last_usage()

    def get_usage_stats(self) -> Dict[str, int]:
        """누적 사용량 통계 반환"""
        return self._client.get_usage_stats()

    def get_rate_limit_info(self) -> Optional[RateLimitInfo]:
        """마지막 API 호출의 Rate Limit 정보 반환"""
        return self._client.get_rate_limit_info()

    def get_rate_limit_str(self) -> str:
        """
        Rate Limit 정보를 문자열로 반환 (UI 표시용)

        Returns:
            str: "[claude] 요청: 900/1,000 (90.0%) | 토큰: 45,000/50,000 (90.0%)" 형태
        """
        info = self._client.get_rate_limit_info()
        if info:
            return str(info)
        return "Rate Limit 정보 없음"

    def get_model_info(self) -> ModelInfo:
        """
        현재 모델의 전체 정보 반환

        Returns:
            ModelInfo: 모델 정보 객체
        """
        stats = self._client.get_usage_stats()
        return ModelInfo(
            provider=self.provider_name,
            model_id=self._client.get_model_name(),
            display_name=self._client.get_display_name(),
            last_usage=self._client.get_last_usage(),
            total_calls=stats['total_calls'],
            total_input_tokens=stats['total_input_tokens'],
            total_output_tokens=stats['total_output_tokens'],
        )

    def get_model_info_str(self) -> str:
        """
        모델 정보를 문자열로 반환 (UI 표시용)

        Returns:
            str: "Claude Sonnet 4 (claude-sonnet-4-20250514)" 형태
        """
        return f"{self._client.get_display_name()} ({self._client.get_model_name()})"

    def get_usage_summary_str(self) -> str:
        """
        사용량 요약을 문자열로 반환 (UI 표시용)

        Returns:
            str: "총 3회 호출, 입력 1,234토큰, 출력 567토큰" 형태
        """
        stats = self._client.get_usage_stats()
        return (f"총 {stats['total_calls']:,}회 호출, "
                f"입력 {stats['total_input_tokens']:,}토큰, "
                f"출력 {stats['total_output_tokens']:,}토큰")

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """사용 가능한 LLM 제공자 목록 반환"""
        available = []
        for name, client_class in cls.PROVIDERS.items():
            client = client_class()
            if client.is_available():
                available.append(name)
        return available

    @classmethod
    def list_providers(cls) -> Dict[str, bool]:
        """모든 LLM 제공자와 사용 가능 여부 반환"""
        result = {}
        for name, client_class in cls.PROVIDERS.items():
            client = client_class()
            result[name] = client.is_available()
        return result


class LLMClientWithFallback:
    """
    자동 폴백 기능을 가진 LLM 클라이언트

    Rate Limit에 근접하거나 API 호출 실패 시 자동으로 다음 LLM으로 전환합니다.

    Args:
        fallback_order: 폴백 순서 리스트. None이면 환경변수 또는 기본값 사용
        auto_fallback: 자동 폴백 활성화 여부. None이면 환경변수 또는 기본값 사용
        warn_threshold: Rate Limit 경고 임계값 (%). None이면 환경변수 또는 기본값 사용

    Examples:
        >>> client = LLMClientWithFallback()
        >>> response = client.chat("안녕하세요")  # 한도 초과 시 자동 폴백
        >>> print(client.get_current_provider())  # 현재 사용 중인 LLM 확인

        >>> # 커스텀 폴백 순서
        >>> client = LLMClientWithFallback(fallback_order=['openai', 'claude', 'solar'])
    """

    # 가성비 순서로 정렬
    PROVIDERS = {
        'claude-haiku': ClaudeHaikuClient,
        'openai': OpenAIClient,
        'claude-3-haiku': Claude3HaikuClient,
        'gpt-3.5-turbo': GPT35TurboClient,
        'solar-mini': SolarMiniClient,
        'claude': ClaudeClient,
        'gpt-4o': GPT4oClient,
        'solar': SolarClient,
    }

    def __init__(
        self,
        fallback_order: List[str] = None,
        auto_fallback: bool = None,
        warn_threshold: float = None
    ):
        # 환경변수에서 기본값 로드
        default_order = os.environ.get('LLM_FALLBACK_ORDER', 'claude-haiku,openai,claude-3-haiku,claude')
        default_auto = os.environ.get('LLM_AUTO_FALLBACK', 'true').lower() == 'true'
        default_threshold = float(os.environ.get('LLM_RATE_LIMIT_WARN_PERCENT', '20'))

        self.fallback_order = fallback_order or [p.strip() for p in default_order.split(',')]
        self.auto_fallback = auto_fallback if auto_fallback is not None else default_auto
        self.warn_threshold = warn_threshold if warn_threshold is not None else default_threshold

        # 유효한 프로바이더만 필터링
        self.fallback_order = [p for p in self.fallback_order if p in self.PROVIDERS]
        if not self.fallback_order:
            raise ValueError("유효한 LLM 제공자가 없습니다.")

        # 각 프로바이더별 클라이언트 초기화
        self._clients: Dict[str, BaseLLMClient] = {}
        for provider in self.fallback_order:
            client = self.PROVIDERS[provider]()
            if client.is_available():
                self._clients[provider] = client

        if not self._clients:
            raise ValueError("사용 가능한 LLM API 키가 설정되지 않았습니다.")

        # 현재 사용 중인 프로바이더 (첫 번째로 사용 가능한 것)
        self._current_provider = list(self._clients.keys())[0]
        self._fallback_history: List[Tuple[str, str, datetime]] = []  # (from, to, timestamp)

        logger.info(f"LLMClientWithFallback 초기화: 사용 가능 {list(self._clients.keys())}, 현재: {self._current_provider}")

    @property
    def current_client(self) -> BaseLLMClient:
        """현재 사용 중인 클라이언트"""
        return self._clients[self._current_provider]

    def get_current_provider(self) -> str:
        """현재 사용 중인 LLM 제공자 이름"""
        return self._current_provider

    def get_available_providers(self) -> List[str]:
        """사용 가능한 LLM 제공자 목록"""
        return list(self._clients.keys())

    def get_fallback_history(self) -> List[Dict[str, Any]]:
        """폴백 이력 반환"""
        return [
            {'from': f, 'to': t, 'timestamp': ts.isoformat()}
            for f, t, ts in self._fallback_history
        ]

    def _should_fallback(self) -> bool:
        """폴백이 필요한지 확인"""
        if not self.auto_fallback:
            return False

        rate_info = self.current_client.get_rate_limit_info()
        if rate_info and rate_info.is_low(self.warn_threshold):
            return True
        return False

    def _do_fallback(self) -> bool:
        """
        다음 LLM으로 폴백 수행

        Returns:
            bool: 폴백 성공 여부
        """
        current_idx = self.fallback_order.index(self._current_provider)
        available_keys = list(self._clients.keys())

        # 현재 이후의 프로바이더 중 사용 가능한 것 찾기
        for provider in self.fallback_order[current_idx + 1:]:
            if provider in available_keys:
                old_provider = self._current_provider
                self._current_provider = provider
                self._fallback_history.append((old_provider, provider, datetime.now()))
                logger.warning(f"🔄 LLM 폴백: {old_provider} → {provider}")
                return True

        logger.warning(f"⚠️ 더 이상 폴백할 LLM이 없습니다. 현재: {self._current_provider}")
        return False

    def chat(self, message: str, system_prompt: str = None) -> str:
        """
        LLM에 메시지를 보내고 응답을 받습니다.
        Rate Limit 초과 또는 오류 시 자동으로 다음 LLM으로 폴백합니다.

        Args:
            message: 사용자 메시지
            system_prompt: 시스템 프롬프트 (선택사항)

        Returns:
            LLM 응답 텍스트
        """
        # 호출 전 Rate Limit 체크 (이전 호출 기준)
        if self._should_fallback():
            self._do_fallback()

        last_error = None
        tried_providers = []

        while True:
            try:
                tried_providers.append(self._current_provider)
                result = self.current_client.chat(message, system_prompt)

                # 호출 후 Rate Limit 체크 (다음 호출을 위해)
                if self._should_fallback():
                    logger.info(f"다음 호출부터 폴백 예정: {self._current_provider}")

                return result

            except Exception as e:
                last_error = e
                logger.warning(f"{self._current_provider} API 오류: {e}")

                # 자동 폴백 시도
                if self.auto_fallback and self._do_fallback():
                    # 이미 시도한 프로바이더는 건너뛰기
                    if self._current_provider in tried_providers:
                        break
                    continue
                else:
                    break

        # 모든 시도 실패
        raise RuntimeError(f"모든 LLM 호출 실패. 시도: {tried_providers}. 마지막 오류: {last_error}")

    def get_rate_limit_info(self) -> Optional[RateLimitInfo]:
        """현재 LLM의 Rate Limit 정보 반환"""
        return self.current_client.get_rate_limit_info()

    def get_all_rate_limits(self) -> Dict[str, Optional[RateLimitInfo]]:
        """모든 LLM의 Rate Limit 정보 반환"""
        return {
            provider: client.get_rate_limit_info()
            for provider, client in self._clients.items()
        }

    def get_rate_limit_str(self) -> str:
        """현재 LLM의 Rate Limit 정보를 문자열로 반환"""
        info = self.get_rate_limit_info()
        if info:
            return str(info)
        return "Rate Limit 정보 없음"

    def get_model_name(self) -> str:
        """현재 사용 중인 모델 ID 반환"""
        return self.current_client.get_model_name()

    def get_display_name(self) -> str:
        """현재 사용 중인 모델의 표시용 이름 반환"""
        return self.current_client.get_display_name()

    def get_last_usage(self) -> Optional[UsageInfo]:
        """현재 LLM의 마지막 사용량 정보 반환"""
        return self.current_client.get_last_usage()

    def get_model_info_str(self) -> str:
        """모델 정보를 문자열로 반환 (UI 표시용)"""
        return f"{self.current_client.get_display_name()} ({self.current_client.get_model_name()})"

    def switch_provider(self, provider: str) -> bool:
        """
        수동으로 LLM 제공자 전환

        Args:
            provider: 전환할 LLM 제공자 이름

        Returns:
            bool: 전환 성공 여부
        """
        if provider not in self._clients:
            logger.error(f"사용할 수 없는 LLM 제공자: {provider}")
            return False

        old_provider = self._current_provider
        self._current_provider = provider
        logger.info(f"LLM 제공자 수동 전환: {old_provider} → {provider}")
        return True
