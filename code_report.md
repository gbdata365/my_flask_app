# 인구통계 대시보드 프로젝트 기술 문서

**작성일**: 2026-01-10
**프로젝트명**: 01_population (인구통계 분석 시스템)
**목적**: 담당자 인수인계 및 신규 개발자 온보딩용 기술 문서

---

## 1. 프로젝트 개요

### 1.1 시스템 소개

이 프로젝트는 **행정안전부 주민등록인구통계 API**를 활용한 인구통계 분석 시스템입니다.

**핵심 기능:**
- 공공데이터 API에서 인구 데이터 수집 및 PostgreSQL 저장
- 시군구/읍면동별 인구 지표 대시보드
- **Text-to-SQL 챗봇**: 자연어 질문 → SQL 변환 → LLM 분석 응답

### 1.2 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python 3, Flask |
| Database | PostgreSQL (파티셔닝 적용) |
| LLM | Claude API, OpenAI GPT-4o, Solar2 |
| 라이브러리 | pandas, psycopg2, anthropic, requests |

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 (웹 브라우저)                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Flask 웹 서버 (main_app.py)                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              동적 라우트 시스템                               │   │
│  │   01_population/routes/*.py → 자동 등록                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│  Text-to-SQL      │ │   LLM Client    │ │   데이터콩 라우트    │
│  (text_to_sql.py) │ │ (llm_client.py) │ │  (데이터콩.py)      │
└─────────┬─────────┘ └────────┬────────┘ └──────────┬──────────┘
          │                    │                     │
          └────────────────────┼─────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PostgreSQL 데이터베이스                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ dim_admin    │  │ fact_pop_*   │  │ cache_sigungu_*         │   │
│  │ _area        │  │ (파티션)      │  │ (캐시 테이블)            │   │
│  └──────────────┘  └──────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               ▲
                               │
┌─────────────────────────────────────────────────────────────────────┐
│                     API 데이터 수집 (api_to_db.py)                   │
│                                                                     │
│    공공데이터 API (4개 엔드포인트) → DB 저장                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 디렉토리 구조

```
01_claude_project/
├── main_app.py              # Flask 메인 애플리케이션
├── module/                  # 공통 모듈
│   ├── db.py                # DB 연결 관리
│   ├── llm_client.py        # LLM API 클라이언트 (Claude/OpenAI/Solar)
│   ├── text_to_sql.py       # Text-to-SQL 변환 엔진
│   ├── ontology_loader.py   # 온톨로지 로더
│   └── .env                 # 환경변수 (DB_URL, API_KEY 등)
│
├── 01_population/           # 인구통계 프로젝트
│   ├── api_to_db.py         # 공공API → DB 수집 스크립트
│   ├── transfer.py          # 캐시 테이블 갱신 스크립트
│   ├── routes/              # Flask 라우트 (자동 등록)
│   │   └── 데이터콩.py       # LLM 챗봇 인터페이스
│   ├── ontology/            # 도메인 지식
│   │   └── database_ontology.md  # Text-to-SQL용 온톨로지
│   └── templates/           # Jinja2 HTML 템플릿
│
└── .venv/                   # Python 가상환경
```

---

## 4. 핵심 모듈 상세 설명

### 4.1 main_app.py - Flask 메인 애플리케이션

**역할**: 웹 서버 진입점, 동적 라우트 등록

**위치**: `C:\Users\user\01_claude_project\main_app.py`

**핵심 기능:**
- Flask 앱 생성 및 구성
- 프로젝트 폴더의 `routes/*.py` 자동 스캔 및 등록
- URL 패턴: `/{프로젝트명}/routes/{라우트명}`

**주요 함수:**

| 함수명 | 역할 |
|--------|------|
| `register_project_routes(app)` | 프로젝트별 라우트 자동 등록 |
| `create_route_handler(module)` | 각 라우트 모듈의 `render()` 호출 핸들러 생성 |

**동작 방식:**
```python
# 01_population/routes/데이터콩.py가 있으면
# → /01_population/routes/데이터콩 URL로 자동 등록
```

---

### 4.2 module/db.py - 데이터베이스 연결 모듈

**역할**: PostgreSQL 연결 관리

**위치**: `C:\Users\user\01_claude_project\module\db.py`

**주요 함수:**

| 함수명 | 반환 타입 | 설명 |
|--------|----------|------|
| `get_db_connection()` | `psycopg2.connection` | psycopg2 커넥션 객체 반환 |
| `get_db_engine()` | `sqlalchemy.Engine` | SQLAlchemy 엔진 반환 (pandas용) |

**환경변수:**
```env
DATABASE_URL=postgresql://user:password@host:port/dbname
```

**사용 예시:**
```python
from module.db import get_db_connection

conn = get_db_connection()
try:
    df = pd.read_sql("SELECT * FROM ...", conn)
finally:
    conn.close()
```

---

### 4.3 module/llm_client.py - LLM API 클라이언트

**역할**: 다중 LLM 제공자 통합 API

**위치**: `C:\Users\user\01_claude_project\module\llm_client.py`

**지원 LLM:**
| 제공자 | 모델 | 클래스명 |
|--------|------|---------|
| Claude | claude-sonnet-4-20250514 | `ClaudeClient` |
| OpenAI | gpt-4o | `OpenAIClient` |
| Solar | solar-pro2-preview | `SolarClient` |

**클래스 구조:**

```
BaseLLMClient (추상 클래스)
    ├── ClaudeClient
    ├── OpenAIClient
    └── SolarClient

LLMClient (통합 인터페이스)
    → provider 파라미터로 구현체 선택
```

**주요 클래스/함수:**

| 클래스/함수 | 역할 |
|------------|------|
| `LLMClient(provider)` | 통합 LLM 클라이언트 (기본: claude) |
| `LLMClient.chat(message, system)` | 채팅 요청 및 응답 |
| `LLMClient.get_rate_limit_info()` | Rate Limit 정보 조회 |
| `LLMClientWithFallback` | 자동 폴백 기능 LLM 클라이언트 |
| `UsageInfo` | 토큰 사용량 데이터 클래스 |
| `RateLimitInfo` | Rate Limit 정보 데이터 클래스 |
| `ModelInfo` | 모델 정보 데이터 클래스 |

**사용 예시:**
```python
from module.llm_client import LLMClient, LLMClientWithFallback

# 기본 사용
llm = LLMClient(provider='claude')
response = llm.chat("질문 내용", system_prompt="시스템 프롬프트")
print(response)

# Rate Limit 정보 확인
rate_info = llm.get_rate_limit_info()
print(rate_info)  # [claude] 요청: 900/1,000 (90.0%) | 토큰: 45,000/50,000 (90.0%)

# 자동 폴백 사용 (한도 초과 시 자동으로 다음 LLM으로 전환)
fallback_llm = LLMClientWithFallback()
response = fallback_llm.chat("질문 내용")
print(f"현재 제공자: {fallback_llm.get_current_provider()}")
```

#### Rate Limit 관리 기능

API 호출 시 응답 헤더에서 Rate Limit 정보를 자동 추출하여 모니터링합니다.

**Rate Limit 환경 변수:**
| 환경변수 | 기본값 | 설명 |
|---------|-------|------|
| `LLM_RATE_LIMIT_WARN_PERCENT` | 20 | 경고 임계값 (남은 한도가 이 % 이하면 경고) |
| `LLM_AUTO_FALLBACK` | true | 자동 폴백 활성화 여부 |
| `LLM_FALLBACK_ORDER` | claude,openai,solar | 폴백 순서 |

**Rate Limit 헤더 (제공자별):**
| 제공자 | 요청 한도 헤더 | 토큰 한도 헤더 |
|--------|---------------|---------------|
| Claude | `anthropic-ratelimit-requests-*` | `anthropic-ratelimit-tokens-*` |
| OpenAI | `x-ratelimit-*-requests` | `x-ratelimit-*-tokens` |
| Solar | (제공하지 않음) | (제공하지 않음) |

**자동 폴백 동작:**
1. API 호출 시 Rate Limit 헤더 자동 추출
2. 남은 한도가 임계값(기본 20%) 이하이면 경고 로그 출력
3. `LLMClientWithFallback` 사용 시 자동으로 다음 LLM으로 전환
4. API 오류 발생 시에도 자동 폴백 시도

```python
# .env 설정 예시
LLM_RATE_LIMIT_WARN_PERCENT=20
LLM_AUTO_FALLBACK=true
LLM_FALLBACK_ORDER=claude,openai,solar
```

#### LLM별 API 호출 방식 차이

| 구분 | Claude | OpenAI | Solar |
|------|--------|--------|-------|
| **라이브러리** | `anthropic` | `openai` | `requests` (REST) |
| **시스템 프롬프트** | `system` 파라미터 별도 | `messages[0]`에 role="system" | `messages[0]`에 role="system" |
| **응답 추출** | `response.content[0].text` | `response.choices[0].message.content` | `json['choices'][0]['message']['content']` |

```python
# Claude - system 파라미터 별도 전달
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    system=system_prompt,  # 별도 파라미터
    messages=[{"role": "user", "content": message}]
)

# OpenAI / Solar - messages 배열에 포함
messages=[
    {"role": "system", "content": system_prompt},  # 메시지에 포함
    {"role": "user", "content": message}
]
```

#### LLM별 장단점 비교

| 항목 | Claude | OpenAI GPT-4o | Solar |
|------|--------|---------------|-------|
| **SQL 생성 정확도** | 높음 | 높음 | 보통 |
| **한국어 이해** | 우수 | 우수 | 매우 우수 (한국어 특화) |
| **응답 속도** | 보통 | 빠름 | 빠름 |
| **비용** | 중간 | 높음 | 저렴 |
| **분석 품질** | 우수 (인사이트 도출) | 우수 | 보통 |
| **최대 컨텍스트** | 200K 토큰 | 128K 토큰 | 32K 토큰 |

#### 용도별 권장 모델

| 용도 | 권장 모델 | 이유 |
|------|----------|------|
| **복잡한 분석 질의** | Claude | 근거 기반 인사이트 도출 우수, 긴 컨텍스트 |
| **단순 SQL 생성** | Solar | 빠르고 저렴, 한국어 처리 우수 |
| **빠른 응답 필요** | GPT-4o | 응답 속도 빠름 |
| **비용 절감** | Solar | API 비용 가장 저렴 |

> **현재 기본값**: `claude` (웹에서 `llm` 파라미터로 변경 가능)

#### API 사용량 확인 방법

**Claude (Anthropic)**

| 항목 | 내용 |
|------|------|
| **과금 방식** | 월정액 플랜 (조직 계정) |
| **확인 방법 1** | [console.anthropic.com](https://console.anthropic.com) → Usage 메뉴 |
| **확인 방법 2** | Admin API Key로 프로그래밍 방식 조회 (아래 코드) |
| **한도 리셋** | 매월 결제일 기준 |

```python
# Claude 사용량 조회 (Admin API Key 필요)
import requests
from datetime import datetime, timedelta

ADMIN_API_KEY = "your-admin-api-key"  # 일반 API Key 아님!

headers = {
    'x-api-key': ADMIN_API_KEY,
    'anthropic-version': '2023-06-01'
}

end_date = datetime.now().strftime('%Y-%m-%dT00:00:00Z')
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT00:00:00Z')

url = f'https://api.anthropic.com/v1/organizations/usage_report/messages?starting_at={start_date}&ending_at={end_date}&bucket_width=1d'

resp = requests.get(url, headers=headers)
print(resp.json())
```

> **주의**: Usage API는 **Admin API Key**가 필요합니다.
> Console → Settings → Admin API Keys에서 발급 (조직 관리자 권한 필요)

**Solar (Upstage)**

| 항목 | 내용 |
|------|------|
| **과금 방식** | 비영리법인 무료 (2026.03까지) |
| **확인 방법** | [console.upstage.ai](https://console.upstage.ai) → Billing → Credit |
| **API 조회** | 불가 (콘솔에서만 확인) |
| **크레딧 부족 시** | 403 Forbidden 에러 발생 |

**OpenAI**

| 항목 | 내용 |
|------|------|
| **확인 방법** | [platform.openai.com](https://platform.openai.com) → Usage |
| **API 조회** | 불가 (콘솔에서만 확인) |

---

### 4.4 module/text_to_sql.py - Text-to-SQL 엔진

**역할**: 자연어 질문을 SQL로 변환하고 실행

**위치**: `C:\Users\user\01_claude_project\module\text_to_sql.py`

**핵심 클래스:**

#### `SchemaExtractor` - DB 스키마 자동 추출

| 메서드 | 설명 |
|--------|------|
| `get_tables()` | 모든 테이블/뷰 목록 조회 |
| `get_columns(table_name)` | 테이블 컬럼 정보 조회 |
| `get_schema_summary()` | LLM 프롬프트용 스키마 요약 생성 |
| `get_sample_data(table_name)` | 샘플 데이터 조회 |

#### `TextToSQL` - 메인 변환 클래스

| 메서드 | 설명 |
|--------|------|
| `__init__(llm_provider, ontology_path, domains)` | 초기화 |
| `generate_sql(question)` | 자연어 → SQL 변환 |
| `execute_sql(sql)` | SQL 실행 및 결과 반환 |
| `ask(question)` | 전체 처리 (SQL 생성→실행→결과) |
| `_build_system_prompt()` | LLM 시스템 프롬프트 생성 |
| `_analyze_with_llm(question)` | SQL 실패 시 LLM 직접 분석 |

**프롬프트 구조:**
1. PostgreSQL 전문가 역할 설정
2. SQL 생성 규칙 (최신 데이터, NULL 처리 등)
3. 시군구 코드 규칙 (4자리/5자리 구분)
4. 온톨로지 (도메인 지식)
5. 동적 DB 스키마

**"근거 기반 인사이트" 가이드라인** (최근 추가):
- 수치 + 맥락 = 인사이트
- 비교 기준 명확화
- 정책적 시사점 도출
- 판단의 근거 명시

#### `generate_natural_response()` - 자연어 응답 생성 함수

SQL 결과를 LLM에게 전달하여 자연어 분석 응답 생성

---

### 4.5 module/ontology_loader.py - 온톨로지 로더

**역할**: 도메인별 온톨로지 파일 모듈러 로딩

**위치**: `C:\Users\user\01_claude_project\module\ontology_loader.py`

**지원 도메인:**
| 도메인 | 파일명 | 설명 |
|--------|--------|------|
| population (기본) | database_ontology.md | 인구통계 |
| finance | finance_ontology.md | 재정/예산 |
| health | health_ontology.md | 보건의료 |
| transport | transport_ontology.md | 교통 |
| education | education_ontology.md | 교육 |
| environment | environment_ontology.md | 환경 |

**사용 예시:**
```python
from module.ontology_loader import OntologyLoader

# 인구 + 재정 도메인 로드
loader = OntologyLoader(domains=['finance'])
ontology_text = loader.load()
```

---

### 4.6 01_population/api_to_db.py - API 데이터 수집

**역할**: 공공데이터 API에서 인구 데이터 수집 → DB 저장

**위치**: `C:\Users\user\01_claude_project\01_population\api_to_db.py`

**데이터 출처:**
- **행정안전부 주민등록인구통계 API** (공공데이터포털)

**수집 대상 (4개 API 엔드포인트):**

| 엔드포인트 | 테이블명 | 설명 |
|-----------|----------|------|
| 인구및세대현황 | fact_population_basic | 총인구, 세대수 등 기본 통계 |
| 연령대별인구 | fact_population_age_group | 연령대별 인구 |
| 1세별인구 (OAS) | fact_population_by_age | **1세 단위** 인구 (Wide 형식) |
| 1인세대수 (OAS) | fact_single_household | 1인가구 1세별 통계 |

**핵심 함수:**

| 함수명 | 역할 |
|--------|------|
| `fetch_endpoints_from_oas(spec_url)` | OAS 명세에서 엔드포인트 추출 |
| `fetch_month_data(ym, endpoint, region)` | 특정 월/지역 데이터 요청 |
| `insert_population_by_age_wide(df, table)` | Wide 형식으로 1세별 데이터 삽입 |
| `create_tables(conn, table_type)` | 테이블 생성 (파티셔닝 포함) |
| `main_collect()` | 전체 수집 프로세스 실행 |

**테이블 파티셔닝:**
- 3년 단위 Range 파티션 (예: 2024~2026)
- `base_ym` 컬럼 기준

**실행 방법:**
```bash
# 초기화 (테이블 생성)
python api_to_db.py --init

# 데이터 수집 (월별)
python api_to_db.py --collect

# 전체 (초기화 + 수집)
python api_to_db.py --init --collect
```

**Wide 테이블 구조 (fact_population_by_age):**
```
admin_code, base_ym, total_pop, male_total, female_total,
male_age_0, male_age_1, ..., male_age_109, male_age_110_over,
female_age_0, female_age_1, ..., female_age_109, female_age_110_over
```
→ 컬럼 수: 약 230개 (1세 단위 × 남녀)

---

### 4.7 01_population/transfer.py - 캐시 테이블 갱신

**역할**: 원본 팩트 테이블에서 집계하여 캐시 테이블 생성

**위치**: `C:\Users\user\01_claude_project\01_population\transfer.py`

**생성되는 캐시 테이블:**

| 테이블명 | 용도 |
|----------|------|
| cache_sigungu_indicators | 시군구별 주요 지표 (고령화율, 유소년율 등) |
| cache_sigungu_age_summary | 시군구별 연령대 요약 |

**핵심 함수:**

| 함수명 | 역할 |
|--------|------|
| `refresh_indicators()` | 시군구 지표 캐시 갱신 |
| `refresh_age_summary()` | 연령대 요약 캐시 갱신 |
| `get_policy_age_ranges()` | code_age_group에서 정책 연령대 조회 |
| `build_age_sum_expression(start, end)` | 연령 합산 SQL 표현식 생성 |

**연령대 정의 (code_age_group 테이블 연동):**
```
category=3 (정책지표):
- 0~14: 유소년
- 15~64: 생산가능인구
- 65~999: 고령인구
```

**실행 방법:**
```bash
python transfer.py
```

---

### 4.8 01_population/routes/데이터콩.py - LLM 챗봇 라우트

**역할**: 웹 기반 자연어 질의 인터페이스

**위치**: `C:\Users\user\01_claude_project\01_population\routes\데이터콩.py`

**URL**: `/01_population/routes/데이터콩`

**핵심 함수:**

| 함수명 | 역할 |
|--------|------|
| `render(request_args)` | 메인 진입점, 요청 처리 및 HTML 반환 |
| `process_question(question, llm_provider)` | 질문 처리 (Text-to-SQL 실행) |
| `format_dataframe_to_table(df)` | DataFrame → HTML 테이블 변환 |
| `format_llm_answer(text)` | LLM 응답 마크다운 → HTML 변환 |

**요청 파라미터:**
| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `q` | 질문 내용 | "고령화율 높은 시군구 10개" |
| `llm` | LLM 선택 | "claude", "gpt4o", "solar" |

**처리 흐름:**
```
1. 사용자 질문 입력 (q 파라미터)
2. TextToSQL.ask() 호출
   → SQL 생성 → 실행 → 결과 DataFrame
3. SQL 실패 시: _analyze_with_llm() 호출
   → LLM이 직접 분석 응답 생성
4. 결과를 HTML로 렌더링
```

---

### 4.9 01_population/routes/대시보드1.py - 연령별/1인가구 대시보드

**역할**: 연령별 인구 및 1인가구 분석 시각화 대시보드

**위치**: `C:\Users\user\01_claude_project\01_population\routes\대시보드1.py`

**URL**: `/01_population/routes/대시보드1`

**주요 기능:**
- 고령화율, 유소년율, 생산가능인구율 등 주요 지표 카드
- 연령 그룹별 인구 분석 (라디오버튼으로 카테고리 선택)
- 1인가구 연령별 분석
- matplotlib 기반 시각화 (막대, 도넛, 피라미드 차트)

**핵심 함수:**

| 함수명 | 역할 |
|--------|------|
| `render(request_args)` | 메인 진입점, 대시보드 HTML 렌더링 |
| `get_filter_options()` | 필터 옵션 조회 (기준년월, 시도, 연령카테고리) |
| `get_summary_indicators(...)` | 주요 지표 계산 (고령화율, 유소년율 등) |
| `get_age_population(...)` | 연령 그룹별 인구 조회 |
| `get_single_household_by_age(...)` | 연령 그룹별 1인가구 조회 |
| `get_combined_age_data(...)` | 인구 + 1인가구 통합 데이터 |
| `get_pivot_data_by_region(...)` | 지역별 피벗 테이블 데이터 |
| `create_bar_chart(...)` | 막대 차트 생성 (Base64 이미지) |
| `create_pyramid_chart(...)` | 인구 피라미드 차트 생성 |
| `create_donut_chart(...)` | 도넛 차트 생성 |
| `create_combined_chart(...)` | 인구 vs 1인가구 이중축 차트 |

**요청 파라미터:**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `base_ym` | 기준년월 | 최신월 |
| `view_type` | 조회 단위 (region/sido/sigungu) | sigungu |
| `sido` | 시도 선택 | 경상북도 |
| `age_cat` | 연령 그룹 카테고리 (1:10년단위, 2:5년단위, 3:정책지표) | 1 |
| `show_pop` | 인구수 표시 | on |
| `show_single` | 1인가구 표시 | on |
| `show_ratio` | 비율 표시 | on |

**차트 생성 방식:**
- matplotlib으로 차트 생성 → BytesIO → Base64 인코딩 → HTML img 태그로 삽입
- 서버사이드 렌더링 (별도 JS 차트 라이브러리 불필요)

---

### 4.10 01_population/ontology/database_ontology.md

**역할**: Text-to-SQL LLM을 위한 도메인 지식

**위치**: `C:\Users\user\01_claude_project\01_population\ontology\database_ontology.md`

**주요 내용:**

1. **테이블 스키마 설명**
   - dim_admin_area (행정구역)
   - fact_population_basic (인구 기본)
   - fact_population_by_age (1세별 인구)
   - fact_single_household (1인가구)
   - cache_sigungu_indicators (캐시)

2. **도메인 용어 매핑**
   - 시도명 정규화 (서울 → 서울특별시)
   - 지표명 매핑 (고령화율 → elderly_ratio)

3. **SQL 생성 규칙**
   - 최신 데이터 조회 패턴
   - 시군구 코드 4자리/5자리 구분
   - 연령별 집계 방법

4. **예시 SQL**
   - 고령화율 조회
   - 1세별 연령 집계
   - 읍면동 단위 조회

---

## 5. 데이터베이스 구조

### 5.1 핵심 테이블

```
┌─────────────────────────────────────────────────────────────────┐
│                        Dimension Tables                          │
├─────────────────────────────────────────────────────────────────┤
│ dim_admin_area                                                   │
│   - admin_code (PK): 행정구역코드 10자리                          │
│   - sido_nm: 시도명                                              │
│   - sigungu_nm: 시군구명                                         │
│   - sigungu_code: 시군구코드 5자리                                │
│   - eupmyeondong_nm: 읍면동명                                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Fact Tables (Partitioned)                │
├─────────────────────────────────────────────────────────────────┤
│ fact_population_basic          │ 기본 인구통계                    │
│   - base_ym, admin_code, total_pop, male_pop, female_pop, ...  │
├─────────────────────────────────────────────────────────────────┤
│ fact_population_by_age         │ 1세별 인구 (Wide)               │
│   - base_ym, admin_code, male_age_0~110_over, female_age_0~... │
├─────────────────────────────────────────────────────────────────┤
│ fact_single_household          │ 1세별 1인가구                   │
│   - base_ym, admin_code, male_age_0~110_over, female_age_0~... │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Cache Tables                             │
├─────────────────────────────────────────────────────────────────┤
│ cache_sigungu_indicators       │ 시군구별 지표                   │
│   - base_ym, sido_nm, sigungu_nm, sigungu_code                  │
│   - total_pop, elderly_pop, elderly_ratio, youth_ratio, ...    │
├─────────────────────────────────────────────────────────────────┤
│ cache_sigungu_age_summary      │ 시군구별 연령대 요약            │
│   - 유소년, 생산가능인구, 고령인구 등                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Code Tables                              │
├─────────────────────────────────────────────────────────────────┤
│ code_age_group                 │ 연령대 정의                     │
│   - category: 1(10년단위), 2(5년단위), 3(정책지표)               │
│   - code: 연령 범위 (예: "65~999")                              │
│   - code_name: 그룹명 (예: "고령인구")                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 테이블 파티셔닝

```sql
-- 3년 단위 Range 파티션
CREATE TABLE fact_population_by_age (
    ...
) PARTITION BY RANGE (base_ym);

CREATE TABLE fact_population_by_age_2024_2026
PARTITION OF fact_population_by_age
FOR VALUES FROM ('2024-01-01') TO ('2027-01-01');
```

### 5.3 시군구 코드 체계

```
시군구코드 (5자리): 예) 41115
  - 앞 4자리 (4111): 기본 시군구 (수원시)
  - 5번째 자리 (5): 하위구 식별
    - 0: 대표 시군구
    - 0이 아님: 하위 자치구

예) 수원시
  - 41110: 수원시 (대표)
  - 41111: 장안구
  - 41113: 권선구
  - 41115: 팔달구
  - 41117: 영통구
```

---

## 6. 데이터 흐름

### 6.1 데이터 수집 흐름

```
┌──────────────────┐     ┌────────────────┐     ┌─────────────────┐
│   공공데이터 API   │────▶│  api_to_db.py  │────▶│   Fact Tables   │
│   (행정안전부)     │     │  (수집 스크립트) │     │  (원본 데이터)   │
└──────────────────┘     └────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                         ┌────────────────┐     ┌─────────────────┐
                         │  transfer.py   │────▶│  Cache Tables   │
                         │  (캐시 갱신)    │     │  (집계 데이터)   │
                         └────────────────┘     └─────────────────┘
```

### 6.2 사용자 질의 흐름

```
┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│   사용자      │────▶│  Flask Route │────▶│   TextToSQL       │
│   (웹 브라우저)│     │  (데이터콩.py)│     │   (text_to_sql.py)│
└──────────────┘     └──────────────┘     └─────────┬─────────┘
                                                    │
                     ┌──────────────────────────────┼──────────────────────────────┐
                     │                              │                              │
                     ▼                              ▼                              │
            ┌─────────────────┐           ┌─────────────────┐                      │
            │   SQL 생성       │           │   온톨로지 로드   │                      │
            │   (LLM 호출)     │◀──────────│   + 스키마 추출   │                      │
            └────────┬────────┘           └─────────────────┘                      │
                     │                                                             │
                     ▼                                                             │
            ┌─────────────────┐                                                    │
            │   SQL 실행       │                                                    │
            │   (PostgreSQL)   │                                                    │
            └────────┬────────┘                                                    │
                     │                                                             │
         ┌───────────┴───────────┐                                                 │
         │ 성공                  │ 실패                                            │
         ▼                       ▼                                                 │
┌─────────────────┐    ┌─────────────────────┐                                    │
│  결과 DataFrame  │    │  _analyze_with_llm()│◀───────────────────────────────────┘
│  + 자연어 응답   │    │  (LLM 직접 분석)     │
└────────┬────────┘    └──────────┬──────────┘
         │                        │
         └────────────┬───────────┘
                      ▼
             ┌─────────────────┐
             │   HTML 응답      │
             │   (결과 표시)     │
             └─────────────────┘
```

---

## 7. 최근 수정 내역

### 7.1 "근거 기반 인사이트" 프롬프트 업데이트 (2026-01-10)

**배경:**
- 기존 LLM 응답이 "너무 객관적"이라는 피드백
- 단순 수치 나열이 아닌 정책적 인사이트 필요

**수정 파일:**
- `module/text_to_sql.py`: `_analyze_with_llm()` 함수

**추가된 가이드라인:**

```
### 핵심 원칙: 데이터가 말하게 하되, 의미를 부여하라

1. 수치 + 맥락 = 인사이트
   - ❌ "경북 1.22%, 전국 0.77%입니다"
   - ✅ "경북은 전국 평균 대비 1.6배 높은 1.22%로, 초고령 인구 비중이 큼"

2. 비교 기준 명확화
   - 전국, 시도 내, 유사 지역 대비 명시
   - 순위뿐 아니라 분포에서의 위치 설명

3. 정책적 시사점 도출
   - 단순 현황 나열이 아닌 실행 가능한 인사이트

4. 판단의 근거 명시
   - 데이터 확인된 사실 → 단정적 표현 OK
   - 추론 필요 → "~일 수 있다" 표현

5. 출력 형식
   - 핵심 인사이트 → 상세 분석 → 시사점/제언
```

### 7.2 온톨로지 업데이트 (2026-01-10)

**수정 파일:**
- `01_population/ontology/database_ontology.md`

**추가된 내용:**
- 80세+, 90세+ 초고령 연령 집계 SQL 예시
- 청년(20~34세) 인구비율 쿼리 예시
- 읍면동 단위 조회 방법

---

## 8. 향후 개발 계획 (TODO)

### 8.1 추가 도메인 확장

| 도메인 | 상태 | 설명 |
|--------|------|------|
| finance | 계획 | 재정/예산 데이터 연동 |
| health | 계획 | 보건의료 데이터 연동 |
| transport | 계획 | 교통 데이터 연동 |

### 8.2 기능 개선

- [ ] 대화 기록 저장 (세션/DB)
- [ ] 차트 시각화 자동 생성
- [ ] 다중 테이블 조인 질의 개선
- [ ] 캐시 테이블 자동 갱신 스케줄러

### 8.3 성능 최적화

- [ ] LLM 응답 캐싱
- [ ] DB 인덱스 최적화
- [ ] 비동기 API 호출

---

## 9. 환경 설정

### 9.1 필수 환경변수 (.env)

```env
# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/population_db

# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-api...
OPENAI_API_KEY=sk-...
SOLAR_API_KEY=up_...

# 공공데이터 API
PUBLIC_DATA_API_KEY=...
```

### 9.2 uv 설치 및 환경 구성

**uv 설치 (최초 1회):**
```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**가상환경 생성:**
```bash
uv venv
```

**패키지 설치:**
```bash
uv pip install flask pandas psycopg2-binary sqlalchemy \
               anthropic openai requests python-dotenv loguru \
               matplotlib koreanize-matplotlib numpy
```

### 9.3 서버 실행

```bash
# 방법 1: uv run 사용 (권장 - 가상환경 자동 활성화)
uv run python main_app.py

# 방법 2: 가상환경 직접 활성화 후 실행
# Windows
.venv\Scripts\activate
python main_app.py

# macOS/Linux
source .venv/bin/activate
python main_app.py

# 브라우저 접속
# http://localhost:5000/01_population/routes/데이터콩
# http://localhost:5000/01_population/routes/대시보드1
```

### 9.4 uv 주요 명령어

| 명령어 | 설명 |
|--------|------|
| `uv venv` | 가상환경 생성 (.venv) |
| `uv pip install 패키지` | 패키지 설치 |
| `uv pip list` | 설치된 패키지 목록 |
| `uv run python 스크립트.py` | 가상환경에서 스크립트 실행 |
| `uv pip freeze > requirements.txt` | 의존성 파일 생성 |

---

## 10. 문제 해결 가이드

### 10.1 자주 발생하는 오류

| 오류 | 원인 | 해결 방법 |
|------|------|----------|
| `relation does not exist` | 테이블 미생성 | `api_to_db.py --init` 실행 |
| `ANTHROPIC_API_KEY not set` | 환경변수 누락 | `.env` 파일 확인 |
| `Connection refused` | DB 미실행 | PostgreSQL 서버 시작 |
| `SQL 생성 실패` | 온톨로지 누락 | `database_ontology.md` 확인 |

### 10.2 디버깅 방법

```python
# 로그 레벨 설정 (loguru)
from loguru import logger
logger.add("debug.log", level="DEBUG")

# SQL 확인
result = t2s.ask("질문")
print(f"생성된 SQL: {result['sql']}")
```

---

## 11. 교육자료 PDF 생성

### 11.1 교육 가이드 문서

프로젝트 인수인계 및 신규 개발자 온보딩을 위한 교육 가이드 PDF를 생성할 수 있습니다.

**생성되는 파일:**
- `study_guide.md`: 교육 가이드 마크다운 원본
- `study.pdf`: 최종 PDF 교육자료
- `create_pdf.py`: PDF 변환 스크립트

### 11.2 교육자료 내용 구성

| 섹션 | 내용 |
|------|------|
| 1. 프로젝트 개요 | 시스템 소개, 기술 스택 |
| 2. 데이터 설명 | 데이터 출처, DB 구조, 지표 설명 |
| 3. 시스템 아키텍처 | 전체 구조도, 데이터 흐름도, Text-to-SQL 플로우 |
| 4. 핵심 코드 설명 | 디렉토리 구조, 주요 파일 역할 |
| 5. 구축 완료 현황 | 완료된 기능 체크리스트 |
| 6. 정기 운영 작업 | 월별 데이터 수집, LLM 사용량 확인 |
| 7. Git/Cloudtype 배포 | 배포 플로우, 환경변수 설정 |
| 8. 문제 해결 가이드 | 자주 발생하는 오류, 디버깅 방법 |

### 11.3 PDF 생성 방법

```bash
# fpdf2 라이브러리 설치 (최초 1회)
pip install fpdf2

# PDF 생성
python create_pdf.py
# → study.pdf 생성됨
```

### 11.4 create_pdf.py 스크립트

**위치**: `C:\Users\user\01_claude_project\create_pdf.py`

**핵심 기능:**
- 맑은 고딕 폰트 자동 적용 (한글 지원)
- 마크다운 → PDF 자동 변환
- 표지, 헤더/푸터, 코드 블록, 테이블 등 렌더링
- 시스템 다이어그램(ASCII 아트) 포함

**주요 클래스/함수:**

| 클래스/함수 | 역할 |
|------------|------|
| `StudyPDF` | fpdf2 기반 한글 PDF 클래스 |
| `parse_markdown()` | 마크다운 파싱하여 요소 추출 |
| `create_pdf()` | PDF 생성 메인 함수 |

**사용 예시:**
```python
from create_pdf import create_pdf
from pathlib import Path

md_file = Path("study_guide.md")
pdf_file = Path("study.pdf")
create_pdf(md_file, pdf_file)
```

---

## 12. 참고 자료

- [행정안전부 주민등록인구통계](https://www.data.go.kr/)
- [Claude API 문서](https://docs.anthropic.com/)
- [PostgreSQL 파티셔닝](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [fpdf2 문서](https://py-pdf.github.io/fpdf2/)

---

*이 문서는 프로젝트 인수인계 및 신규 개발자 온보딩을 위해 작성되었습니다.*
*최종 업데이트: 2026-01-11*
