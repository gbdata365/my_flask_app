# 인구통계 대시보드 프로젝트 교육 가이드

**작성일**: 2026-01-11 (최종 수정: 2026-01-15)
**프로젝트명**: 01_population (인구통계 분석 시스템)
**대상**: 신규 담당자 및 개발자

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [데이터 설명](#2-데이터-설명)
3. [시스템 아키텍처 플로우](#3-시스템-아키텍처-플로우)
4. [핵심 코드 설명](#4-핵심-코드-설명)
5. [지금까지 구축한 내용](#5-지금까지-구축한-내용)
   - [5.2 최근 업데이트 내역](#52-최근-업데이트-내역)
   - [5.3 2026-01-12 작업 상세 내역](#53-2026-01-12-작업-상세-내역)
   - [5.4 2026-01-13 작업 상세 내역](#54-2026-01-13-작업-상세-내역)
   - [5.5 2026-01-15 작업 상세 내역](#55-2026-01-15-작업-상세-내역)
6. [정기 운영 작업](#6-정기-운영-작업)
7. [Git 및 Cloudtype 배포](#7-git-및-cloudtype-배포)
8. [문제 해결 가이드](#8-문제-해결-가이드)
9. [MD/PPT 보고서 저장 기능](#9-mdppt-보고서-저장-기능)
10. [대시보드 모듈 사용법](#10-대시보드-모듈-사용법)

---

## 1. 프로젝트 개요

### 1.1 시스템 소개

**행정안전부 주민등록인구통계 API**를 활용한 **인구통계 분석 시스템**입니다.

### 1.2 핵심 기능 3가지

```
┌─────────────────────────────────────────────────────────────────┐
│                      인구통계 분석 시스템                         │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  1. 데이터 수집   │  2. 대시보드     │  3. Text-to-SQL 챗봇         │
│  ─────────────  │  ─────────────  │  ─────────────────────────  │
│  공공API → DB   │  시각화 차트     │  자연어 질문 → SQL → 분석   │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

### 1.3 기술 스택

| 분류 | 기술 |
|------|------|
| **Backend** | Python 3, Flask |
| **Database** | PostgreSQL (파티셔닝) |
| **LLM** | Claude, OpenAI GPT-4o, Solar |
| **시각화** | matplotlib, koreanize-matplotlib |
| **패키지관리** | uv |

---

## 2. 데이터 설명

### 2.1 데이터 출처

- **행정안전부 주민등록인구통계** (공공데이터포털)
- 매월 말 기준 인구 데이터 제공
- 읍면동 단위까지 상세 데이터

### 2.2 수집 데이터 종류

```
┌─────────────────────────────────────────────────────────────────┐
│                        수집 데이터 (4종)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────┐        │
│  │ 1. 인구 및 세대현황   │    │ 2. 연령대별 인구         │        │
│  │   (기본 통계)        │    │   (10세/5세 단위)        │        │
│  │   총인구, 세대수     │    │   연령그룹별 남녀인구     │        │
│  └─────────────────────┘    └─────────────────────────┘        │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────┐        │
│  │ 3. 1세별 인구        │    │ 4. 1세별 1인가구        │        │
│  │   (0~110세+)        │    │   (0~110세+)            │        │
│  │   ★ 가장 상세       │    │   1인가구 상세분석       │        │
│  └─────────────────────┘    └─────────────────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 데이터베이스 테이블 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Dimension Table - 행정구역]                                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ dim_admin_area                                       │       │
│  │   - admin_code (PK): 10자리 행정구역코드             │       │
│  │   - sido_nm: 시도명 (예: 경상북도)                   │       │
│  │   - sigungu_nm: 시군구명 (예: 안동시)               │       │
│  │   - eupmyeondong_nm: 읍면동명                       │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  [Fact Tables - 인구 데이터] (파티셔닝 적용)                     │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ fact_population_basic    : 기본 인구통계             │       │
│  │ fact_population_by_age   : 1세별 인구 (컬럼 230개)   │       │
│  │ fact_single_household    : 1세별 1인가구            │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  [Cache Tables - 집계 캐시]                                     │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ cache_sigungu_indicators : 고령화율, 유소년율 등     │       │
│  │ cache_sigungu_age_summary: 연령대별 요약            │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.4 주요 지표 설명

| 지표명 | 계산식 | 설명 |
|--------|--------|------|
| **고령화율** | 65세+ / 전체인구 × 100 | 14% 이상이면 고령사회 |
| **유소년율** | 0~14세 / 전체인구 × 100 | 낮을수록 저출산 |
| **생산가능인구율** | 15~64세 / 전체인구 × 100 | 경제활동인구 비율 |
| **노령화지수** | 65세+ / 0~14세 × 100 | 100 이상이면 고령인구 > 유소년 |
| **1인가구비율** | 1인가구 / 전체세대 × 100 | 독거 가구 비율 |

---

## 3. 시스템 아키텍처 플로우

### 3.1 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                      [ 전체 시스템 구조도 ]                           │
└─────────────────────────────────────────────────────────────────────┘

                         ┌──────────────────┐
                         │   사용자 (브라우저) │
                         └────────┬─────────┘
                                  │ HTTP 요청
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Flask 웹 서버 (main_app.py)                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                   동적 라우트 시스템                          │    │
│  │         01_population/routes/*.py → 자동 URL 등록           │    │
│  └────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│   데이터콩.py    │  │   대시보드1.py   │  │   기타 라우트        │
│  (LLM 챗봇)     │  │  (시각화 차트)   │  │                     │
└────────┬────────┘  └────────┬────────┘  └─────────────────────┘
         │                    │
         │  ┌─────────────────┘
         ▼  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         공통 모듈 (module/)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │ llm_client  │  │ text_to_sql │  │    db.py    │  │ ontology  │ │
│  │ (LLM 호출)  │  │ (NL→SQL)   │  │ (DB연결)    │  │ (도메인)  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       PostgreSQL Database                            │
│    dim_admin_area │ fact_population_* │ cache_sigungu_*             │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 데이터 수집 플로우

```
┌─────────────────────────────────────────────────────────────────────┐
│                      [ 데이터 수집 플로우 ]                           │
└─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐
  │  공공데이터 API  │ ─────┐
  │  (행정안전부)    │      │
  └─────────────────┘      │
                           │ REST API 호출
                           ▼
                    ┌──────────────────┐
                    │   api_to_db.py   │
                    │  (수집 스크립트)  │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
     │ fact_pop_   │ │ fact_pop_   │ │ fact_single │
     │ basic       │ │ by_age      │ │ _household  │
     └─────────────┘ └─────────────┘ └─────────────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   transfer.py    │
                    │   (캐시 갱신)     │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  cache_sigungu_  │
                    │  indicators      │
                    └──────────────────┘
```

### 3.3 Text-to-SQL 질의 플로우

```
┌─────────────────────────────────────────────────────────────────────┐
│                    [ Text-to-SQL 질의 플로우 ]                       │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ 사용자 질문   │  "경상북도 고령화율 상위 10개 시군구 알려줘"
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                     TextToSQL 엔진                            │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 1. 시스템 프롬프트 구성                                  │  │
│  │    - PostgreSQL 전문가 역할                             │  │
│  │    - 온톨로지 (도메인 지식)                              │  │
│  │    - DB 스키마 (자동 추출)                              │  │
│  └────────────────────────────────────────────────────────┘  │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 2. LLM 호출 (Claude/OpenAI/Solar)                      │  │
│  │    → SQL 쿼리 생성                                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                         │                                    │
│              ┌──────────┴──────────┐                        │
│              ▼                     ▼                        │
│        [ 성공 ]              [ 실패 ]                        │
│              │                     │                        │
│              ▼                     ▼                        │
│  ┌─────────────────┐   ┌─────────────────────┐             │
│  │ 3. SQL 실행     │   │ 3. LLM 직접 분석     │             │
│  │    (PostgreSQL) │   │    (온톨로지 기반)   │             │
│  └────────┬────────┘   └──────────┬──────────┘             │
│           │                       │                        │
│           └───────────┬───────────┘                        │
│                       ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 4. 결과 + 자연어 분석 응답 생성                          │  │
│  │    "경북은 전국 평균 대비 1.6배 높은 고령화율..."        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│  HTML 응답    │  데이터 테이블 + LLM 분석 인사이트
└──────────────┘
```

---

## 4. 핵심 코드 설명

### 4.1 디렉토리 구조

```
01_claude_project/
├── main_app.py              # Flask 메인 (진입점)
│
├── module/                  # 공통 모듈
│   ├── db.py                # DB 연결 관리
│   ├── llm_client.py        # LLM API 클라이언트
│   ├── text_to_sql.py       # Text-to-SQL 엔진
│   ├── ontology_loader.py   # 온톨로지 로더
│   └── .env                 # 환경변수 (비밀정보)
│
├── 01_population/           # 인구통계 프로젝트
│   ├── api_to_db.py         # API → DB 수집
│   ├── transfer.py          # 캐시 테이블 갱신
│   ├── routes/              # Flask 라우트
│   │   ├── 데이터콩.py       # LLM 챗봇 UI
│   │   └── 대시보드1.py      # 시각화 대시보드
│   ├── ontology/            # 도메인 지식
│   │   └── database_ontology.md
│   └── templates/           # HTML 템플릿
│
└── .venv/                   # Python 가상환경
```

### 4.2 주요 파일별 역할

| 파일 (전체 경로) | 역할 | 핵심 함수 |
|------|------|----------|
| `01_claude_project/main_app.py` | Flask 서버 시작, 라우트 등록 | `register_project_routes()` |
| `01_claude_project/module/db.py` | PostgreSQL 연결 | `get_db_connection()` |
| `01_claude_project/module/llm_client.py` | Claude/OpenAI/Solar API | `LLMClient.chat()` |
| `01_claude_project/module/text_to_sql.py` | 자연어 → SQL 변환 | `TextToSQL.ask()` |
| `01_claude_project/module/ontology_loader.py` | 온톨로지 파일 로드 | `load_ontology()` |
| `01_claude_project/module/datacong_core.py` | 데이터콩 챗봇 공통 기능 | `DataCongCore.render()` |
| `01_claude_project/module/report_generator.py` | MD/PPT 보고서 생성 | `DashboardReport` 클래스 |
| `01_claude_project/module/create_ppt_template.py` | PPT 템플릿 생성 스크립트 | `create_template()` |
| `01_claude_project/module/.env` | 환경변수 (API키, DB접속정보) | - |
| `01_claude_project/01_population/api_to_db.py` | 공공API 데이터 수집 | `main_collect()` |
| `01_claude_project/01_population/transfer.py` | 캐시 테이블 갱신 | `refresh_indicators()` |
| `01_claude_project/01_population/routes/데이터콩.py` | LLM 챗봇 UI (인구통계) | `render()` |
| `01_claude_project/01_population/routes/대시보드1.py` | 시각화 대시보드 | - |
| `01_claude_project/02_기업체현황/routes/데이터콩.py` | LLM 챗봇 UI (기업체현황) | `render()` |
| `01_claude_project/01_population/ontology/database_ontology.md` | 인구통계 도메인 지식 | - |
| `01_claude_project/module/ontology/common_ontology.md` | 공통 온톨로지 (모든 도메인 공유) | - |
| `01_claude_project/templates/report_template.pptx` | PPT 보고서 기본 템플릿 | - |

### 4.3 LLM 클라이언트 사용법

```python
from module.llm_client import LLMClient, LLMClientWithFallback

# 기본 사용
llm = LLMClient(provider='claude')  # claude, openai, solar 중 선택
response = llm.chat("질문 내용", system_prompt="시스템 프롬프트")

# Rate Limit 확인
rate_info = llm.get_rate_limit_info()
print(rate_info)  # [claude] 요청: 900/1,000 (90.0%)

# 자동 폴백 (한도 초과 시 자동 전환)
fallback_llm = LLMClientWithFallback()
response = fallback_llm.chat("질문 내용")
```

### 4.4 Text-to-SQL 사용법

```python
from module.text_to_sql import TextToSQL

t2s = TextToSQL(llm_provider='claude')
result = t2s.ask("경상북도 고령화율 상위 10개 시군구")

print(result['sql'])      # 생성된 SQL
print(result['data'])     # 결과 DataFrame
print(result['answer'])   # LLM 분석 응답
```

### 4.5 온톨로지 로더 사용법

온톨로지 로더는 **파일 위치**와 **질문 내용**을 분석하여 필요한 도메인의 온톨로지를 자동으로 로드합니다.

#### 4.5.1 온톨로지 구조

```
01_claude_project/
├── module/
│   └── ontology/
│       └── common_ontology.md      ← 공통 온톨로지 (항상 로드)
│
├── 01_population/
│   └── ontology/
│       └── database_ontology.md    ← 인구통계 도메인 (기본 포함)
│
├── 02_welfare/
│   └── ontology/
│       └── database_ontology.md    ← 복지 도메인 (키워드 감지 시)
│
└── ... (추가 도메인)
```

#### 4.5.2 자동 도메인 감지 원리

```
┌─────────────────────────────────────────────────────────────────┐
│                    자동 도메인 감지 흐름                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  데이터콩.py 위치: 01_population/routes/데이터콩.py              │
│  사용자 질문: "고령화율과 복지시설 현황 비교해줘"                │
│                                                                 │
│  1. 파일 경로 분석 → 01_population 감지                         │
│  2. 질문 키워드 분석 → "고령화" → 인구, "복지" → 복지           │
│  3. 최종 로드: 공통 + 인구 + 복지 온톨로지                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.5.3 도메인별 키워드 설정

| 도메인 | 폴더명 | 감지 키워드 예시 |
|--------|--------|-----------------|
| 인구통계 | 01_population | 인구, 고령화, 유소년, 세대, 1인가구, 노인, 청년 |
| 복지 | 02_welfare | 복지, 기초생활, 수급자, 장애인, 돌봄, 요양 |
| 경제 | 03_economy | 경제, 고용, 실업, 취업, 소득, 임금 |
| 보건의료 | 04_health | 보건, 의료, 병원, 건강, 질병, 진료 |
| 교육 | 05_education | 교육, 학교, 학생, 유치원, 대학 |

> **참고**: 인구통계(01_population)는 `always_include: True`로 설정되어 항상 포함됩니다.

#### 4.5.4 사용 방법

**방법 1: 자동 감지 (권장)**
```python
from module.ontology_loader import OntologyLoader, load_ontology

# 파일 위치 + 질문으로 자동 감지
ontology = load_ontology(
    caller_file=__file__,      # 현재 파일 위치
    question=user_question      # 사용자 질문
)

# TextToSQL에 전달
t2s = TextToSQL(llm_provider='claude', ontology_content=ontology)
```

**방법 2: OntologyLoader 클래스 직접 사용**
```python
from module.ontology_loader import OntologyLoader

# 자동 감지
loader = OntologyLoader.auto_detect(
    caller_file=__file__,
    question="인구와 복지 현황 비교해줘"
)

# 로드된 도메인 확인
print(loader.get_domain_names())  # ['인구통계', '복지']

# 온톨로지 로드
ontology = loader.load()
```

**방법 3: 도메인 명시적 지정**
```python
from module.ontology_loader import OntologyLoader

# 특정 도메인 직접 지정
loader = OntologyLoader(domains=['01_population', '02_welfare', '03_economy'])
ontology = loader.load()
```

#### 4.5.5 데이터콩.py에서의 실제 사용

```python
# 01_population/routes/데이터콩.py

from module.ontology_loader import OntologyLoader

def process_question(question: str, llm_provider: str = 'claude'):
    # 파일 위치 + 질문 키워드로 자동 감지
    loader = OntologyLoader.auto_detect(
        caller_file=__file__,     # → 01_population 감지
        question=question          # → 추가 도메인 키워드 감지
    )
    ontology_content = loader.load()

    # Text-to-SQL에 전달
    t2s = TextToSQL(
        llm_provider=llm_provider,
        ontology_content=ontology_content
    )

    result = t2s.ask(question)
    return result
```

#### 4.5.6 온톨로지 현황 확인

```python
from module.ontology_loader import get_ontology_status

print(get_ontology_status())
```

출력 예시:
```
==================================================
온톨로지 현황
==================================================

공통 온톨로지: 있음

도메인별 현황:
----------------------------------------
  [O] 01_population (인구통계): 1개 파일, 25.3KB
  [X] 02_welfare (복지): 폴더 없음
  [X] 03_economy (경제): 폴더 없음
==================================================
```

#### 4.5.7 새 도메인 추가 방법

1. **폴더 생성**: `02_welfare/ontology/` 폴더 생성
2. **온톨로지 파일 작성**: `database_ontology.md` 작성
3. **키워드 등록**: `ontology_loader.py`의 `DOMAIN_CONFIG`에 추가

```python
# module/ontology_loader.py

DOMAIN_CONFIG = {
    # ... 기존 도메인 ...

    '02_welfare': {
        'name': '복지',
        'keywords': ['복지', '기초생활', '수급자', '장애인', '돌봄'],
        'always_include': False,
    },
}
```

### 4.6 Report Generator 사용법

`report_generator.py` 모듈은 대시보드 분석 결과를 마크다운(MD) 파일이나 파워포인트(PPT) 파일로 저장하는 기능을 제공합니다.

#### 4.6.1 핵심 클래스 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                    Report Generator 구조                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Data Classes - 데이터 구조체]                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ ChartData   : 차트 데이터 (제목, 이미지경로, 설명)    │       │
│  │ TableData   : 테이블 데이터 (제목, DataFrame)        │       │
│  │ MetricData  : 지표 데이터 (라벨, 값, 변화량)         │       │
│  │ InsightData : 인사이트 데이터 (제목, 설명, 타입)      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  [Main Class - 보고서 생성기]                                   │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ DashboardReport                                      │       │
│  │   - __init__: 보고서 초기화 (제목, 부제목 등)         │       │
│  │   - add_metrics: 지표 카드 추가                      │       │
│  │   - add_table: 데이터 테이블 추가                    │       │
│  │   - add_chart: 차트 이미지 추가                      │       │
│  │   - add_insights: 인사이트 추가                      │       │
│  │   - to_markdown: MD 문자열 생성                      │       │
│  │   - save_markdown: MD 파일 저장                      │       │
│  │   - save_ppt: PPT 파일 저장                          │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.6.2 기본 사용법

```python
from module.report_generator import DashboardReport

# 1. 보고서 객체 생성
report = DashboardReport(
    title="인구통계 분석 보고서",
    subtitle="2025년 11월 기준",
    source_file=__file__,  # 현재 파일 경로 (출력 파일명 결정용)
    output_dir="./output"   # 출력 디렉토리
)

# 2. 지표 카드 추가
report.add_metrics([
    {"label": "총인구", "value": "51,234,567명", "change": "+0.3%"},
    {"label": "고령화율", "value": "18.5%", "change": "+0.8%"},
])

# 3. 테이블 추가
import pandas as pd
df = pd.DataFrame({"시군구": ["서울", "부산"], "인구": [9500000, 3400000]})
report.add_table("주요 도시 인구", df)

# 4. 차트 추가
report.add_chart("고령화율 추이", "/path/to/chart.png", "2020-2025년 추이")

# 5. 인사이트 추가
report.add_insights([
    {"title": "핵심 발견", "description": "고령화가 가속화되고 있습니다", "type": "warning"}
])

# 6. 파일 저장
md_path = report.save_markdown()    # ./output/데이터콩_report.md
ppt_path = report.save_ppt()        # ./output/데이터콩_report.pptx
```

#### 4.6.3 source_file 패턴

`source_file` 파라미터는 출력 파일명을 자동 결정하는 데 사용됩니다:

```python
# 예시: 01_population/routes/데이터콩.py에서 호출

report = DashboardReport(
    title="보고서",
    source_file=__file__  # → "데이터콩.py"
)

# 출력 파일명:
# - MD: 데이터콩_report.md
# - PPT: 데이터콩_report.pptx
```

**파일명 생성 로직:**
1. `__file__` → 경로에서 파일명만 추출 → `데이터콩.py`
2. `.py` 확장자 제거 → `데이터콩`
3. `_report` 접미사 추가 → `데이터콩_report`
4. 확장자 추가 → `데이터콩_report.md` 또는 `.pptx`

---

## 5. 지금까지 구축한 내용

### 5.1 완료된 기능

```
┌─────────────────────────────────────────────────────────────────────┐
│                      [ 구축 완료 현황 ]                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ✅ 데이터 수집 파이프라인                                           │
│     - 공공API 4종 연동 완료                                         │
│     - 월별 데이터 자동 수집 스크립트                                 │
│     - 테이블 파티셔닝 (3년 단위)                                     │
│                                                                     │
│  ✅ Text-to-SQL 챗봇                                                │
│     - 자연어 질문 → SQL 변환                                        │
│     - 근거 기반 인사이트 분석 응답                                   │
│     - 다중 LLM 지원 (Claude, OpenAI, Solar)                         │
│     - Rate Limit 자동 모니터링 및 폴백                               │
│                                                                     │
│  ✅ 대시보드 시각화                                                  │
│     - 고령화율, 유소년율 등 주요 지표 카드                           │
│     - 연령대별 인구 막대/도넛/피라미드 차트                          │
│     - 1인가구 분석 차트                                             │
│                                                                     │
│  ✅ 운영 인프라                                                     │
│     - PostgreSQL 캐시 테이블 자동 갱신                              │
│     - 온톨로지 기반 도메인 지식 관리                                 │
│     - 환경변수 기반 설정 관리                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 최근 업데이트 내역

| 날짜 | 내용 |
|------|------|
| 2026-01-15 | **[기능추가]** MD/PPT 보고서 저장 기능 - 대시보드 분석 결과 문서화 |
| 2026-01-15 | **[기능추가]** PPT 템플릿 생성기 - 8종 슬라이드 레이아웃 자동 생성 |
| 2026-01-15 | **[기능추가]** 기업체현황 도메인 추가 - SBR 데이터 + 인구 연계 분석 |
| 2026-01-15 | **[문서화]** report_generator.py, create_ppt_template.py 상세 독스트링 추가 |
| 2026-01-13 | **[기능추가]** LLM 다중 모델 지원 - Claude 3종, OpenAI 3종, Upstage 2종 |
| 2026-01-13 | **[개선]** 기본 LLM을 Claude Haiku로 변경 (가성비 최적화) |
| 2026-01-13 | **[개선]** LLM 드롭다운에 토큰 비용 표시 추가 |
| 2026-01-13 | **[개선]** 네비게이션 바 스타일 통일 및 로딩 오버레이 추가 |
| 2026-01-13 | **[버그수정]** ClaudeClient 추상 메서드 오류 수정 |
| 2026-01-13 | **[버그수정]** Claude3HaikuClient 중복 메서드 제거 |
| 2026-01-12 | **[버그수정]** Solar2 datetime.date 오류 수정 - 문자열 변환 처리 |
| 2026-01-12 | **[버그수정]** base_ym 날짜 형식 오류 수정 - YYYY-MM-DD 형식 적용 |
| 2026-01-12 | **[버그수정]** 메뉴 중복 문제 수정 - inject_navbar_to_html 조건 추가 |
| 2026-01-12 | **[개선]** 메뉴 스타일 통일 - datacong_core.py 컨텐츠 전용 렌더링 |
| 2026-01-12 | **[문서]** 인구통계 시스템 가이드 문서 작성 (index.md) |
| 2026-01-12 | 온톨로지 로더 개선 - 파일 위치/질문 키워드 기반 자동 도메인 감지 |
| 2026-01-12 | 공통 온톨로지(common_ontology.md) 추가 |
| 2026-01-12 | 데이터콩.py에 새 온톨로지 로더 적용 |
| 2026-01-10 | "근거 기반 인사이트" 프롬프트 개선 |
| 2026-01-10 | Rate Limit 모니터링 및 자동 폴백 기능 |
| 2026-01-10 | 온톨로지에 초고령(80세+, 90세+) 쿼리 예시 추가 |

### 5.3 2026-01-12 작업 상세 내역

#### 5.3.1 Solar2 datetime.date 오류 수정

**문제 상황:**
```
오류: "sequence item 0: expected str instance, datetime.date found"
발생 위치: module/text_to_sql.py (_analyze_with_llm 함수)
```

**원인 분석:**
- PostgreSQL에서 `base_ym` 컬럼 조회 시 `datetime.date` 객체로 반환
- `', '.join()` 함수에서 문자열이 아닌 datetime.date 객체를 연결하려 할 때 오류 발생

**수정 내용 (text_to_sql.py):**
```python
# 수정 전
available_months = df_months['base_ym'].tolist()
# → datetime.date 객체 리스트

# 수정 후
available_months_sql = []      # SQL WHERE절용 (YYYY-MM-DD)
available_months_display = []  # 표시용 (YYYYMM)
for m in df_months['base_ym'].tolist():
    if hasattr(m, 'strftime'):
        available_months_sql.append(m.strftime('%Y-%m-%d'))
        available_months_display.append(m.strftime('%Y%m'))
    else:
        available_months_sql.append(str(m))
        available_months_display.append(str(m).replace('-', '')[:6])
```

**핵심 포인트:**
- `hasattr(m, 'strftime')`으로 datetime 객체 여부 확인
- SQL용(YYYY-MM-DD)과 표시용(YYYYMM) 두 가지 형식 분리

---

#### 5.3.2 base_ym 날짜 형식 오류 수정

**문제 상황:**
```
오류: "date/time field value out of range: 202511"
잘못된 SQL: WHERE base_ym = '202511'
```

**원인 분석:**
- `base_ym` 컬럼은 PostgreSQL DATE 타입
- DATE 타입은 'YYYY-MM-DD' 형식만 허용
- LLM이 'YYYYMM' 형식으로 SQL 생성하여 오류 발생

**수정 내용 1 - 시스템 프롬프트 추가 (text_to_sql.py):**
```markdown
## ⚠️ base_ym (기준년월) 날짜 형식 (필수!)
- base_ym은 DATE 타입입니다 (문자열이 아님!)
- ❌ 잘못된 형식: WHERE base_ym = '202511' (에러 발생!)
- ✅ 올바른 형식: WHERE base_ym = '2025-11-01' (YYYY-MM-DD)
- 최신 데이터 조회 시: WHERE base_ym = (SELECT MAX(base_ym) FROM 테이블명)
- 특정 월 조회 시: WHERE base_ym = '2025-11-01' (해당 월의 1일)
```

**수정 내용 2 - SQL 쿼리 수정 (text_to_sql.py):**
```python
# 수정 전
current_sql = f"""
    SELECT ... FROM cache_sigungu_indicators
    WHERE base_ym = '{latest_month}'  -- '202511' 형식
"""

# 수정 후
current_sql = f"""
    SELECT ... FROM cache_sigungu_indicators
    WHERE base_ym = '{latest_month_sql}'  -- '2025-11-01' 형식
"""
```

**핵심 포인트:**
- PostgreSQL DATE 타입은 ISO 8601 형식(YYYY-MM-DD) 필수
- LLM 프롬프트에 명확한 형식 가이드 추가로 오류 예방

---

#### 5.3.3 메뉴 중복 문제 수정

**문제 상황:**
- PY 파일(데이터콩.py 등) 선택 시 메뉴가 두 번 표시됨
- 상단에 datacong_core.py의 메뉴 + 하단에 main_app.py의 메뉴

**원인 분석:**
```
┌─────────────────────────────────────────────────────────────────┐
│  문제 구조                                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  datacong_core.py (render)                                     │
│  └─ 전체 HTML 반환 (자체 네비게이션 포함)                        │
│                                                                 │
│  main_app.py                                                    │
│  └─ inject_navbar_to_html() 호출                                │
│     └─ 또 다른 네비게이션 추가 → 중복 발생!                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**수정 내용 (menu_generator.py):**
```python
@staticmethod
def inject_navbar_to_html(html_content, menu_items, current_filename=None):
    try:
        # 이미 네비게이션이 있는 HTML인지 확인
        if 'class="main-nav"' in html_content or 'name="navbar-included"' in html_content:
            return html_content  # 중복 삽입 방지

        # 네비게이션이 없는 경우에만 추가
        nav_html = MenuGenerator.generate_navbar_html(menu_items, current_filename)
        ...
```

**핵심 포인트:**
- `class="main-nav"` 또는 `name="navbar-included"` 메타 태그로 기존 네비게이션 감지
- 이미 네비게이션이 있으면 추가 삽입 건너뜀

---

#### 5.3.4 메뉴 스타일 통일

**문제 상황:**
- MD 파일: 주황색 하이라이트 + 흰색 배경 (표준 스타일)
- PY 파일(데이터콩): 보라색 그라데이션 헤더 (다른 스타일)
- 사용자가 일관된 스타일 요청

**원인 분석:**
```
┌─────────────────────────────────────────────────────────────────┐
│  스타일 불일치 원인                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MD 파일 렌더링:                                                │
│  └─ main_app.py → category_with_navbar.html 템플릿 사용         │
│     └─ 표준 CSS 적용 (주황색 하이라이트)                         │
│                                                                 │
│  PY 파일 (데이터콩) 렌더링:                                      │
│  └─ datacong_core.py → 자체 전체 HTML 반환                      │
│     └─ 독자적 CSS 적용 (보라색 그라데이션)                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**수정 내용 (datacong_core.py):**
```python
def render(self, request_args: Optional[Dict[str, str]] = None) -> str:
    """페이지 렌더링 (컨텐츠만 반환)"""

    # 컨텐츠만 반환 (메뉴는 main_app.py의 템플릿에서 추가)
    styles = get_content_styles()

    html = f'''
<style>
{styles}
</style>

<div class="datacong-container">
    <div class="chat-container">
        <!-- 컨텐츠만, 헤더/네비게이션 없음 -->
    </div>
</div>
'''
    return html
```

**추가된 함수 - get_content_styles():**
```python
def get_content_styles() -> str:
    """컨텐츠 영역 스타일 (표준 템플릿 색상과 일치)"""
    return """
        .datacong-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        /* 표준 색상 적용 */
        --primary-dark: #1243A6;
        --primary: #1D64F2;
        --accent: #F24822;
        ...
    """
```

**결과:**
- 모든 페이지가 `category_with_navbar.html` 템플릿 사용
- 일관된 메뉴 스타일 (주황색 하이라이트, 흰색 배경)

---

#### 5.3.5 인구통계 시스템 가이드 문서 작성

**생성 파일:** `01_population/markdown_docs/index.md`

**포함 내용:**
| 섹션 | 내용 |
|------|------|
| 1. 시스템 개요 | 프로젝트 목적, 주요 기능 소개 |
| 2. 보유 데이터 | 데이터 출처, 테이블 구조, 주요 지표 설명 |
| 3. 메뉴 구성 | 웹 애플리케이션 메뉴 안내 |
| 4. 대시보드1 사용법 | 필터 옵션, 연령그룹, 차트 종류, 피벗 테이블 |
| 5. 데이터콩 사용법 | AI 챗봇 질문 유형, LLM 선택, 결과 출력 형식 |
| 6. 시작하기 | 환경 설정, 실행 방법 |
| 7. 폴더 구조 | 프로젝트 디렉토리 설명 |

**파일명 `index.md` 선택 이유:**
- 메뉴에서 가장 먼저 표시됨 (알파벳 순 정렬)
- 새 사용자가 처음 접하는 문서로 적합

---

### 5.4 2026-01-13 작업 상세 내역

#### 5.4.1 LLM 다중 모델 지원 추가

**배경:**
- 기존에는 각 공급자별 1개 모델만 지원 (Claude Sonnet 4, GPT-4o-mini, Solar Pro)
- 사용자가 비용/성능 트레이드오프에 따라 모델 선택을 원함

**추가된 모델 목록:**

| 공급자 | 모델명 | 클래스명 | 비용 (입력 토큰 1M당) | 특징 |
|--------|--------|----------|---------------------|------|
| **Claude** | claude-sonnet-4-20250514 | `ClaudeClient` | $3 | 고성능 |
| **Claude** | claude-3-5-haiku-20241022 | `ClaudeHaikuClient` | $0.8 | 빠르고 저렴 (추천) |
| **Claude** | claude-3-haiku-20240307 | `Claude3HaikuClient` | $0.25 | 가장 저렴 |
| **OpenAI** | gpt-4o | `GPT4oClient` | $2.5 | 고성능 |
| **OpenAI** | gpt-4o-mini | `OpenAIClient` | $0.15 | 가성비 우수 |
| **OpenAI** | gpt-3.5-turbo | `GPT35TurboClient` | $0.5 | 저렴 |
| **Upstage** | solar-pro | `SolarClient` | - | 고성능 |
| **Upstage** | solar-mini | `SolarMiniClient` | - | 저렴 |

**수정된 파일 (llm_client.py):**
```python
# 가성비 순서로 정렬된 PROVIDERS 딕셔너리
PROVIDERS = {
    'claude-haiku': ClaudeHaikuClient,       # Claude 3.5 Haiku (추천)
    'openai': OpenAIClient,                  # GPT-4o-mini
    'claude-3-haiku': Claude3HaikuClient,    # Claude 3 Haiku (가장 저렴)
    'gpt-3.5-turbo': GPT35TurboClient,
    'solar-mini': SolarMiniClient,
    'claude': ClaudeClient,                  # Claude Sonnet 4 (고성능)
    'gpt-4o': GPT4oClient,
    'solar': SolarClient,
}
```

**핵심 포인트:**
- 모든 클라이언트 클래스는 `BaseLLMClient` 추상 클래스 상속
- 필수 구현 메서드: `chat()`, `is_available()`
- 딕셔너리 순서가 드롭다운 표시 순서를 결정

---

#### 5.4.2 기본 LLM을 Claude Haiku로 변경

**변경 이유:**
- 기존 기본값: `claude` (Sonnet 4) - 고성능이지만 비용 높음
- 새 기본값: `claude-haiku` (3.5 Haiku) - 빠르고 가성비 우수

**수정된 파일 및 위치:**

1. **datacong_core.py (2102행):**
```python
# 수정 전
llm_provider = request_args.get('llm', 'claude')

# 수정 후
llm_provider = request_args.get('llm', 'claude-haiku')
```

2. **datacong_core.py (1899행):**
```python
# 수정 전
def process_question(self, question: str, llm_provider: str = 'claude') -> Dict[str, Any]:

# 수정 후
def process_question(self, question: str, llm_provider: str = 'claude-haiku') -> Dict[str, Any]:
```

3. **.env 파일:**
```env
LLM_PROVIDER=claude-haiku
```

---

#### 5.4.3 LLM 드롭다운에 토큰 비용 표시

**변경 내용:**
- LLM 선택 드롭다운에서 각 모델의 토큰 비용을 함께 표시
- 사용자가 비용을 고려하여 모델 선택 가능

**수정된 파일 (datacong_core.py):**
```python
LLM_DISPLAY_NAMES: Dict[str, str] = {
    # 가성비 모델 (상위 추천)
    'claude-haiku': 'Claude 3.5 Haiku ($0.8/1M)',
    'openai': 'GPT-4o-mini ($0.15/1M)',
    'claude-3-haiku': 'Claude 3 Haiku ($0.25/1M)',
    'gpt-3.5-turbo': 'GPT-3.5 Turbo ($0.5/1M)',
    'solar-mini': 'Solar Mini',
    # 고성능 모델
    'claude': 'Claude Sonnet 4 ($3/1M)',
    'gpt-4o': 'GPT-4o ($2.5/1M)',
    'solar': 'Solar Pro',
}
```

**화면 예시:**
```
┌─────────────────────────────────────┐
│ Claude 3.5 Haiku ($0.8/1M)     ▼   │  ← 기본 선택
├─────────────────────────────────────┤
│ GPT-4o-mini ($0.15/1M)              │
│ Claude 3 Haiku ($0.25/1M)           │
│ GPT-3.5 Turbo ($0.5/1M)             │
│ Solar Mini                          │
│ Claude Sonnet 4 ($3/1M)             │
│ GPT-4o ($2.5/1M)                    │
│ Solar Pro                           │
└─────────────────────────────────────┘
```

---

#### 5.4.4 네비게이션 바 스타일 통일 및 로딩 오버레이

**문제 상황:**
- 데이터콩 선택 시 네비게이션 바와 대시보드1 선택 시 네비게이션 바 스타일이 다름
- 현재 선택된 메뉴에 빨간 배경이 표시되지 않음
- 페이지 전환 시 로딩 피드백 없음

**수정 내용:**

1. **네비게이션 바 스타일 통일:**
   - 모든 페이지에서 동일한 파란색 그라데이션 헤더 사용
   - 현재 선택된 메뉴 항목에 빨간 배경(`#F24822`) 적용

2. **로딩 오버레이 추가:**
   - 페이지 전환 시 "페이지 로딩 중..." 메시지 표시
   - 사용자에게 진행 상태 피드백 제공

**수정된 파일:**

1. **templates/category_with_navbar.html:**
```html
<!-- 로딩 오버레이 -->
<div class="loading-overlay" id="loadingOverlay">
    <div class="loading-content">
        <div class="spinner"></div>
        <p>페이지 로딩 중...</p>
    </div>
</div>

<script>
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', function(e) {
        document.getElementById('loadingOverlay').classList.add('show');
    });
});
</script>
```

2. **menu_generator.py - generate_navbar_html():**
```python
# URL 기반 현재 메뉴 활성화
nav_html += """
<script>
    document.addEventListener('DOMContentLoaded', function() {
        const currentPath = window.location.pathname;
        document.querySelectorAll('.injected-nav a').forEach(link => {
            const linkUrl = link.getAttribute('data-url');
            if (currentPath === linkUrl) {
                link.classList.add('active');
            }
        });
    });
</script>
"""
```

3. **CSS 스타일:**
```css
.nav-link.active {
    background: #F24822;  /* 빨간 배경 */
    color: white;
    font-weight: 500;
}

.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(255, 255, 255, 0.9);
    display: none;
    justify-content: center;
    align-items: center;
    z-index: 9999;
}

.loading-overlay.show {
    display: flex;
}
```

---

#### 5.4.5 ClaudeClient 추상 메서드 오류 수정

**오류 메시지:**
```
Can't instantiate abstract class ClaudeClient without an implementation
for abstract methods 'chat', 'is_available'
```

**원인:**
- 새로운 Claude 모델 클라이언트 추가 과정에서 `ClaudeClient` 클래스의 필수 메서드 구현이 누락됨
- `BaseLLMClient` 추상 클래스의 `@abstractmethod`로 정의된 `chat()`, `is_available()` 미구현

**수정 내용 (llm_client.py):**
```python
class ClaudeClient(BaseLLMClient):
    """Anthropic Claude API 클라이언트 (Sonnet 4 - 고성능)"""

    def __init__(self):
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.model = "claude-sonnet-4-20250514"
        # ... 초기화

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != 'your_anthropic_api_key_here')

    def chat(self, message: str, system_prompt: str = None) -> str:
        # ... 구현
```

---

#### 5.4.6 Claude3HaikuClient 중복 메서드 제거

**문제:**
- `Claude3HaikuClient` 클래스에서 동일한 메서드가 두 번 정의됨
- `_get_client()`, `_parse_rate_limit_headers()`, `is_available()`, `chat()` 중복

**수정 전 (llm_client.py 376-515행):**
```python
class Claude3HaikuClient(BaseLLMClient):
    # ... __init__ ...

    def _get_client(self):  # 첫 번째 정의 (376행)
        ...
    def chat(self, ...):    # 첫 번째 정의
        ...

    def _get_client(self):  # 두 번째 정의 (434행) - 중복!
        ...
    def chat(self, ...):    # 두 번째 정의 - 중복!
        ...
```

**수정 후:**
- 중복된 두 번째 정의 블록 전체 삭제
- 첫 번째 정의만 유지

**핵심 포인트:**
- Python에서 중복 메서드는 마지막 정의로 덮어씀
- 동작에는 문제없으나 코드 가독성과 유지보수성 저해
- 불필요한 코드 제거로 깔끔하게 정리

---

### 5.5 2026-01-15 작업 상세 내역

#### 5.5.1 MD/PPT 보고서 저장 기능 추가

**배경:**
- 대시보드에서 분석한 결과를 문서로 저장하고 싶다는 요구사항
- 마크다운(MD)은 버전 관리 및 웹 게시용, PPT는 발표용으로 활용

**구현 구조:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                  [ MD/PPT 저장 기능 구조 ]                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [사용자] ──(클릭)──▶ [저장 버튼 (MD/PPT)]                           │
│                           │                                         │
│                           ▼                                         │
│               ┌──────────────────────┐                             │
│               │  datacong_core.py    │                             │
│               │  handle_post()       │                             │
│               └──────────┬───────────┘                             │
│                          │                                         │
│                          ▼                                         │
│               ┌──────────────────────┐                             │
│               │ report_generator.py  │                             │
│               │ DashboardReport      │                             │
│               └──────────┬───────────┘                             │
│                          │                                         │
│            ┌─────────────┼─────────────┐                           │
│            ▼             ▼             ▼                           │
│     ┌──────────┐  ┌──────────┐  ┌──────────────┐                   │
│     │ MD 저장   │  │PPT 저장  │  │ PPT 템플릿    │                   │
│     │ (텍스트)  │  │(python-  │  │ (pptx 파일)  │                   │
│     │          │  │ pptx)    │  │              │                   │
│     └──────────┘  └──────────┘  └──────────────┘                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**생성 파일:**

| 파일 | 역할 | 주요 내용 |
|------|------|----------|
| `module/report_generator.py` | 보고서 생성 모듈 | DashboardReport 클래스, 데이터 클래스 4종 |
| `module/create_ppt_template.py` | PPT 템플릿 생성 스크립트 | 8종 슬라이드 레이아웃 정의 |
| `templates/report_template.pptx` | 기본 PPT 템플릿 | 생성된 템플릿 파일 |

---

#### 5.5.2 PPT 템플릿 생성기 구현

**PPT 템플릿 구조 (8종 슬라이드):**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    [ PPT 템플릿 슬라이드 구성 ]                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  슬라이드 1: 제목                    슬라이드 2: 목차                 │
│  ┌─────────────────────────┐       ┌─────────────────────────┐     │
│  │ ═══════════════════════ │       │ ═══════════════════════ │     │
│  │                         │       │ 1. 개요                 │     │
│  │    보고서 제목           │       │ 2. 주요 지표            │     │
│  │    부제목               │       │ 3. 상세 분석            │     │
│  │                         │       │ 4. 결론                 │     │
│  └─────────────────────────┘       └─────────────────────────┘     │
│                                                                     │
│  슬라이드 3: 내용                    슬라이드 4: 지표 카드 (2x2)     │
│  ┌─────────────────────────┐       ┌─────────────────────────┐     │
│  │ ═══════════════════════ │       │ ═══════════════════════ │     │
│  │ ● 항목 1                │       │ ┌─────┐  ┌─────┐       │     │
│  │ ● 항목 2                │       │ │지표1│  │지표2│       │     │
│  │ ● 항목 3                │       │ └─────┘  └─────┘       │     │
│  │                         │       │ ┌─────┐  ┌─────┐       │     │
│  │                         │       │ │지표3│  │지표4│       │     │
│  └─────────────────────────┘       └─────────────────────────┘     │
│                                                                     │
│  슬라이드 5: 차트                    슬라이드 6: 표                   │
│  ┌─────────────────────────┐       ┌─────────────────────────┐     │
│  │ ═══════════════════════ │       │ ═══════════════════════ │     │
│  │ ┌───────────────────┐   │       │ ┌───────────────────┐   │     │
│  │ │                   │   │       │ │ A │ B │ C │ D │   │   │     │
│  │ │    차트 영역       │   │       │ │───│───│───│───│   │   │     │
│  │ │                   │   │       │ │ 1 │ 2 │ 3 │ 4 │   │   │     │
│  │ └───────────────────┘   │       │ └───────────────────┘   │     │
│  └─────────────────────────┘       └─────────────────────────┘     │
│                                                                     │
│  슬라이드 7: 인사이트                슬라이드 8: 마무리               │
│  ┌─────────────────────────┐       ┌─────────────────────────┐     │
│  │ ═══════════════════════ │       │ ═══════════════════════ │     │
│  │ 💡 핵심 발견            │       │                         │     │
│  │    설명 텍스트...       │       │     감사합니다          │     │
│  │ ⚠️ 주의 사항            │       │     Q&A                 │     │
│  │    설명 텍스트...       │       │                         │     │
│  └─────────────────────────┘       └─────────────────────────┘     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**색상 체계:**

| 색상명 | HEX 코드 | 용도 |
|--------|----------|------|
| PRIMARY_DARK | #1243A6 | 헤더 배경, 주요 텍스트 |
| PRIMARY | #1D64F2 | 강조 요소 |
| ACCENT | #F24822 | 주의/경고 하이라이트 |
| TEXT_DARK | #1E1E1E | 본문 텍스트 |
| CARD_BLUE | #667EEA | 지표 카드 배경 1 |
| CARD_PURPLE | #764BA2 | 지표 카드 배경 2 |
| CARD_GREEN | #2ECC71 | 지표 카드 배경 3 |
| CARD_SKY | #3498DB | 지표 카드 배경 4 |

**템플릿 생성 명령어:**
```bash
cd C:\Users\user\01_claude_project
uv run python module/create_ppt_template.py
# → templates/report_template.pptx 생성
```

---

#### 5.5.3 기업체현황 도메인 추가

**새 도메인 구조:**

```
02_기업체현황/
├── ontology/
│   └── database_ontology.md    # 기업통계 도메인 지식
└── routes/
    └── 데이터콩.py              # 기업체현황 챗봇 UI
```

**데이터콩.py 핵심 설정:**
```python
# 도메인 설정
DOMAIN_NAME = "기업체현황"
DOMAIN_BASE = Path(__file__).parent.parent
CURRENT_FILE = __file__

# 예시 질문 (기업+인구 연계)
EXAMPLE_QUESTIONS = [
    "경상북도 시군구별 사업체수 현황",
    "제조업 사업체가 가장 많은 시군구 10개",
    "인구 천명당 사업체수 높은 시군구",
    "고령화율 대비 사업체수 관계",
]

# 챗봇 설정
CHAT_TITLE = "AI 기업체현황 분석 챗봇"
CHAT_SUBTITLE = "기업통계와 인구데이터를 연계하여 지역 산업구조를 분석합니다."
```

**온톨로지 로더 설정 추가 (ontology_loader.py):**
```python
DOMAIN_CONFIG = {
    # ... 기존 ...
    '02_기업체현황': {
        'name': '기업체현황',
        'keywords': ['기업', '사업체', '종사자', '산업', '제조업', '도소매업', 'SBR'],
        'always_include': False,
    },
}
```

---

#### 5.5.4 코드 문서화 작업

**문서화 완료 파일:**

1. **module/report_generator.py** (약 1,350줄)
   - 모듈 독스트링: 전체 구조, 사용법, 예시 포함
   - 데이터 클래스 4종 독스트링
   - DashboardReport 클래스 및 모든 메서드 독스트링
   - 인라인 주석: 각 처리 단계 설명

2. **module/create_ppt_template.py** (약 1,000줄)
   - 모듈 독스트링: 템플릿 구조, 슬라이드 설명
   - 색상 상수 문서화
   - 각 슬라이드 생성 함수에 ASCII 아트 레이아웃 포함
   - main() 함수 사용 예시

**독스트링 형식 예시:**
```python
def add_chart(self, title: str, image_path: str, description: str = "") -> None:
    """
    차트 이미지를 보고서에 추가합니다.

    차트 이미지는 matplotlib 등으로 생성한 PNG/JPG 파일을 참조합니다.
    PPT 저장 시 이미지가 슬라이드에 삽입되며, MD 저장 시에는
    상대 경로로 링크됩니다.

    Args:
        title (str): 차트 제목 (예: "고령화율 추이")
        image_path (str): 차트 이미지 파일 경로 (절대 또는 상대)
        description (str, optional): 차트 설명. Defaults to "".

    Returns:
        None

    Examples:
        >>> report = DashboardReport("보고서", source_file=__file__)
        >>> report.add_chart(
        ...     "월별 인구 변화",
        ...     "./charts/population_trend.png",
        ...     "2025년 1월~12월 인구 변화 추이"
        ... )

    Notes:
        - 이미지 파일이 존재하지 않으면 PPT 저장 시 오류 발생
        - pathlib.Path 사용으로 Windows/Linux 호환성 보장
    """
```

---

## 6. 정기 운영 작업

### 6.1 월별 필수 작업

```
┌─────────────────────────────────────────────────────────────────────┐
│                    [ 월별 운영 체크리스트 ]                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📅 매월 10일 이후 (전월 데이터 공개 후)                             │
│                                                                     │
│  □ 1. 데이터 수집                                                   │
│     $ cd 01_population                                              │
│     $ uv run python api_to_db.py --collect                         │
│                                                                     │
│  □ 2. 캐시 테이블 갱신                                              │
│     $ uv run python transfer.py                                    │
│                                                                     │
│  □ 3. 데이터 검증 (챗봇에서 확인)                                    │
│     질문: "최신 데이터 기준년월이 언제야?"                           │
│     → 전월(YYYYMM) 이 나오면 정상                                   │
│                                                                     │
│  □ 4. 서버 배포 (변경사항 있을 경우)                                 │
│     $ git add . && git commit -m "월별 데이터 갱신"                 │
│     $ git push origin main                                         │
│     → Cloudtype 자동 배포                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 데이터 수집 명령어

```bash
# 위치: 01_population 폴더

# 초기화 (테이블 생성) - 최초 1회만
uv run python api_to_db.py --init

# 데이터 수집 - 매월 실행
uv run python api_to_db.py --collect

# 캐시 테이블 갱신 - 데이터 수집 후 실행
uv run python transfer.py
```

### 6.3 LLM API 사용량 확인

| 제공자 | 확인 방법 |
|--------|----------|
| **Claude** | [console.anthropic.com](https://console.anthropic.com) → Usage |
| **OpenAI** | [platform.openai.com](https://platform.openai.com) → Usage |
| **Solar** | [console.upstage.ai](https://console.upstage.ai) → Billing |

---

## 7. Git 및 Cloudtype 배포

### 7.1 Git 저장소 설정

```bash
# 1. Git 초기화 (최초 1회)
cd C:\Users\user\01_claude_project
git init
git remote add origin https://github.com/YOUR_USERNAME/01_claude_project.git

# 2. .gitignore 설정 (중요!)
# .env 파일은 절대 커밋하지 않음
echo ".env" >> .gitignore
echo ".venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
```

### 7.2 Git 배포 플로우

```
┌─────────────────────────────────────────────────────────────────────┐
│                      [ Git 배포 플로우 ]                             │
└─────────────────────────────────────────────────────────────────────┘

  ┌────────────────┐
  │ 로컬 개발 환경   │
  │ (코드 수정)     │
  └───────┬────────┘
          │
          ▼
  ┌────────────────────────────────────────┐
  │ $ git add .                            │
  │ $ git commit -m "변경 내용 설명"        │
  │ $ git push origin main                 │
  └───────┬────────────────────────────────┘
          │
          ▼
  ┌────────────────┐
  │  GitHub 저장소  │
  │  (main 브랜치)  │
  └───────┬────────┘
          │ Webhook 트리거
          ▼
  ┌────────────────────────────────────────┐
  │           Cloudtype                     │
  │  ┌────────────────────────────────┐    │
  │  │ 1. 코드 Pull                   │    │
  │  │ 2. 의존성 설치                  │    │
  │  │ 3. 서버 재시작                  │    │
  │  └────────────────────────────────┘    │
  └───────┬────────────────────────────────┘
          │
          ▼
  ┌────────────────┐
  │ 배포 완료!      │
  │ https://xxx.   │
  │ cloudtype.app  │
  └────────────────┘
```

### 7.3 Cloudtype 설정

#### 7.3.1 프로젝트 생성

1. [cloudtype.io](https://cloudtype.io) 접속 → 로그인
2. "새 프로젝트" → GitHub 저장소 연결
3. 프레임워크: **Python (Flask)** 선택

#### 7.3.2 환경변수 설정

Cloudtype 대시보드 → 프로젝트 → 설정 → 환경변수

```
DATABASE_URL=postgresql://user:password@host:port/dbname
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
UPSTAGE_API_KEY=up_...
```

> **중요**: .env 파일은 Git에 올리지 않고, Cloudtype 환경변수로 설정

#### 7.3.3 빌드 설정

**빌드 명령어:**
```bash
pip install -r requirements.txt
```

**실행 명령어:**
```bash
python main_app.py
```

**포트:** `5000`

#### 7.3.4 requirements.txt 생성

```bash
uv pip freeze > requirements.txt
```

```
# requirements.txt 예시
flask==3.0.0
pandas==2.1.4
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
anthropic==0.18.0
openai==1.12.0
requests==2.31.0
python-dotenv==1.0.0
loguru==0.7.2
matplotlib==3.8.2
koreanize-matplotlib==0.1.1
numpy==1.26.3
```

### 7.4 배포 확인

```bash
# 배포 후 접속 URL
https://YOUR_PROJECT.cloudtype.app/01_population/routes/데이터콩
https://YOUR_PROJECT.cloudtype.app/01_population/routes/대시보드1
```

---

## 8. 문제 해결 가이드

### 8.1 자주 발생하는 오류

| 오류 메시지 | 원인 | 해결 방법 |
|------------|------|----------|
| `relation does not exist` | 테이블 미생성 | `api_to_db.py --init` 실행 |
| `ANTHROPIC_API_KEY not set` | 환경변수 누락 | `.env` 파일 또는 Cloudtype 환경변수 확인 |
| `Connection refused` | DB 미실행 | PostgreSQL 서버 시작 |
| `Rate limit exceeded` | API 한도 초과 | 다른 LLM으로 전환 또는 대기 |
| `SQL 생성 실패` | 온톨로지 부족 | `database_ontology.md`에 예시 추가 |
| `sequence item 0: expected str instance, datetime.date found` | datetime 객체 문자열 변환 누락 | `strftime()`으로 문자열 변환 |
| `date/time field value out of range: YYYYMM` | DATE 타입에 잘못된 형식 | 'YYYY-MM-DD' 형식 사용 |
| 메뉴 두 번 표시 | inject_navbar 중복 호출 | `class="main-nav"` 확인 조건 추가 |

### 8.2 로그 확인 방법

```python
# loguru 로그 설정
from loguru import logger

# 콘솔에서 실시간 확인
logger.info("정보 메시지")
logger.error("에러 메시지")

# 파일로 저장
logger.add("debug.log", level="DEBUG")
```

### 8.3 디버깅 체크리스트

```
□ 1. 환경변수 확인
   $ echo $DATABASE_URL
   $ echo $ANTHROPIC_API_KEY

□ 2. DB 연결 테스트
   $ uv run python -c "from module.db import get_db_connection; print(get_db_connection())"

□ 3. LLM API 테스트
   $ uv run python -c "from module.llm_client import LLMClient; print(LLMClient().chat('안녕'))"

□ 4. 서버 실행 확인
   $ uv run python main_app.py
   → http://localhost:5000 접속
```

---

## 부록: 빠른 참조

### A. 주요 URL

| 용도 | URL |
|------|-----|
| 인구통계 챗봇 | `/01_population/routes/데이터콩` |
| 인구통계 대시보드 | `/01_population/routes/대시보드1` |
| 기업체현황 챗봇 | `/02_기업체현황/routes/데이터콩` |

### B. 주요 명령어

```bash
# 서버 실행
uv run python main_app.py

# 데이터 수집
uv run python 01_population/api_to_db.py --collect

# 캐시 갱신
uv run python 01_population/transfer.py

# PPT 템플릿 생성
uv run python module/create_ppt_template.py

# Git 배포
git add . && git commit -m "message" && git push origin main
```

### C. 환경변수 목록

```env
# 필수
DATABASE_URL=postgresql://...
ANTHROPIC_API_KEY=sk-ant-...

# 선택
OPENAI_API_KEY=sk-...
UPSTAGE_API_KEY=up_...
LLM_PROVIDER=claude
LLM_AUTO_FALLBACK=true
LLM_FALLBACK_ORDER=claude,openai,solar
```

---

## 9. MD/PPT 보고서 저장 기능

### 9.1 기능 개요

대시보드에서 분석한 결과를 문서화하여 보관하거나 공유할 수 있는 기능입니다.

```
┌─────────────────────────────────────────────────────────────────────┐
│                   [ 보고서 저장 기능 개요 ]                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  데이터콩/대시보드 질의 결과                                          │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────────────────────────────┐                       │
│  │              저장 옵션 선택               │                       │
│  │  ┌─────────────┐    ┌─────────────┐    │                       │
│  │  │ MD 저장     │    │ PPT 저장    │    │                       │
│  │  │ (마크다운)   │    │ (파워포인트) │    │                       │
│  │  └──────┬──────┘    └──────┬──────┘    │                       │
│  └─────────┼─────────────────┼────────────┘                       │
│            │                 │                                     │
│            ▼                 ▼                                     │
│  ┌─────────────────┐ ┌─────────────────────┐                       │
│  │ .md 파일 다운로드│ │ .pptx 파일 다운로드  │                       │
│  │ - 텍스트 기반    │ │ - 발표용 슬라이드    │                       │
│  │ - Git 버전관리  │ │ - 시각적 정리        │                       │
│  │ - 웹 게시 용이  │ │ - 오프라인 공유      │                       │
│  └─────────────────┘ └─────────────────────┘                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 사용 방법

#### 9.2.1 데이터콩에서 사용

1. 데이터콩 챗봇에서 질문 입력
2. 분석 결과 확인
3. 하단의 **"MD 저장"** 또는 **"PPT 저장"** 버튼 클릭
4. 파일 자동 다운로드

#### 9.2.2 프로그래밍 방식 사용

```python
from module.report_generator import DashboardReport, ChartData, TableData

# 보고서 생성
report = DashboardReport(
    title="월간 인구통계 분석",
    subtitle="2025년 11월 기준",
    source_file=__file__
)

# 데이터 추가
report.add_metrics([
    {"label": "총인구", "value": "51,234,567", "change": "+0.3%"},
    {"label": "고령화율", "value": "18.5%", "change": "+0.8%"},
])

report.add_table("시군구별 고령화율", df_aging_rate, max_rows=10)
report.add_chart("고령화율 추이", "./charts/aging_trend.png")
report.add_insights([
    {"title": "핵심 발견", "description": "고령화 가속화", "type": "warning"}
])

# 저장
report.save_markdown()  # → 데이터콩_report.md
report.save_ppt()       # → 데이터콩_report.pptx
```

### 9.3 출력 파일 위치

| 상황 | 기본 출력 위치 | 파일명 패턴 |
|------|--------------|-------------|
| 인구통계 도메인 | `01_population/output/` | `데이터콩_report.md/.pptx` |
| 기업체현황 도메인 | `02_기업체현황/output/` | `데이터콩_report.md/.pptx` |
| 사용자 지정 | `output_dir` 파라미터 | 사용자 지정 |

### 9.4 PPT 템플릿 커스터마이징

#### 9.4.1 기존 템플릿 위치

```
templates/report_template.pptx
```

#### 9.4.2 템플릿 재생성

```bash
# 템플릿 생성 스크립트 실행
cd C:\Users\user\01_claude_project
uv run python module/create_ppt_template.py

# 결과
# → templates/report_template.pptx 생성 (8개 슬라이드)
```

#### 9.4.3 색상 변경 방법

`module/create_ppt_template.py` 파일의 상단 색상 상수 수정:

```python
# 색상 상수 정의
PRIMARY_DARK = RGBColor(18, 67, 166)    # #1243A6 → 변경
PRIMARY = RGBColor(29, 100, 242)         # #1D64F2 → 변경
ACCENT = RGBColor(242, 72, 34)           # #F24822 → 변경

# 지표 카드 배경색
CARD_COLORS = [
    RGBColor(102, 126, 234),  # 파랑
    RGBColor(118, 75, 162),   # 보라  → 변경 가능
    RGBColor(46, 204, 113),   # 초록
    RGBColor(52, 152, 219),   # 하늘
]
```

### 9.5 의존성 패키지

| 패키지 | 용도 | 설치 명령 |
|--------|------|----------|
| python-pptx | PPT 파일 생성/편집 | `uv pip install python-pptx` |
| pandas | 데이터프레임 처리 | `uv pip install pandas` |
| pathlib | 경로 처리 (내장) | - |

**requirements.txt 추가:**
```
python-pptx>=0.6.21
```

### 9.6 주의사항

1. **이미지 경로**: 차트 이미지 경로는 절대 경로 또는 실행 위치 기준 상대 경로 사용
2. **한글 파일명**: Windows/Linux 호환을 위해 pathlib.Path 사용
3. **PPT 템플릿**: 템플릿 파일이 없으면 PPT 저장 시 오류 발생
4. **출력 디렉토리**: output 폴더가 없으면 자동 생성됨

### 9.7 문제 해결

| 문제 | 원인 | 해결 방법 |
|------|------|----------|
| PPT 저장 실패 | 템플릿 파일 없음 | `create_ppt_template.py` 실행 |
| 이미지 누락 | 경로 오류 | 절대 경로 사용 또는 경로 확인 |
| 한글 깨짐 | 인코딩 문제 | UTF-8 인코딩 확인 |
| 파일 다운로드 안됨 | Flask 응답 오류 | `handle_post()` 함수 확인 |

---

## 10. 대시보드 모듈 사용법

**작성일**: 2026-01-20

### 10.1 모듈 구조

재사용 가능한 대시보드 컴포넌트가 `module/dashboard/` 폴더에 모듈화되어 있습니다.

```
module/dashboard/
├── __init__.py      # 모듈 진입점
├── base.py          # DashboardBase 클래스 (상속용)
├── charts.py        # ChartGenerator (차트 생성)
├── tables.py        # TableGenerator (테이블 생성)
└── export.py        # ExportManager (내보내기)
```

### 10.2 ChartGenerator - 차트 생성

Matplotlib 기반의 차트를 Base64 이미지로 생성합니다.

```python
from module.dashboard import ChartGenerator

# 막대 차트
chart_img = ChartGenerator.bar_chart(
    labels=['서울', '부산', '대구', '경상북도'],
    datasets=[
        {'label': '2024년', 'data': [100, 80, 60, 50]},
        {'label': '2025년', 'data': [110, 85, 65, 55]}
    ],
    title='시도별 인구',
    highlight='경상북도'  # 빨간 테두리로 강조
)

# 이중축 차트 (막대 + 선)
chart_img = ChartGenerator.dual_axis_chart(
    labels=['서울', '부산', '대구'],
    bar_data=[9500, 3300, 2300],       # 막대 (인구, 왼쪽 Y축)
    line_data=[17.2, 21.5, 23.1],      # 선 (고령화율, 오른쪽 Y축)
    bar_label='인구(천명)',
    line_label='고령화율(%)'
)

# 선 차트
chart_img = ChartGenerator.line_chart(
    labels=['2020', '2021', '2022', '2023', '2024'],
    datasets=[
        {'label': '서울', 'data': [9700, 9600, 9500, 9400, 9300]},
        {'label': '경상북도', 'data': [2700, 2650, 2600, 2550, 2500]}
    ],
    title='연도별 인구 추이'
)

# 파이/도넛 차트
chart_img = ChartGenerator.pie_chart(
    labels=['0-14세', '15-64세', '65세 이상'],
    data=[12, 72, 16],
    title='연령대별 인구 비율',
    donut=True  # 도넛 차트로
)
```

**주요 메서드:**

| 메서드 | 용도 | 주요 파라미터 |
|--------|------|--------------|
| `bar_chart()` | 막대 차트 | labels, datasets, highlight, stacked |
| `line_chart()` | 선 차트 | labels, datasets, fill |
| `dual_axis_chart()` | 이중축 차트 | bar_data, line_data |
| `pie_chart()` | 파이/도넛 | data, donut |
| `grouped_bar_with_line()` | 묶음 막대+선 | bar_datasets, line_dataset |

### 10.3 TableGenerator - 테이블 생성

HTML 테이블을 생성합니다. 2줄 헤더, 자동 정렬, 강조 기능을 지원합니다.

```python
from module.dashboard import TableGenerator

# 데이터 예시
data = [
    {'sido_nm': '합계', 'pop_202312': 51000000, 'rate_202312': 0.0,
     'pop_202412': 50800000, 'rate_202412': -0.39},
    {'sido_nm': '경상북도', 'pop_202312': 2600000, 'rate_202312': -1.2,
     'pop_202412': 2550000, 'rate_202412': -1.92},
    {'sido_nm': '서울특별시', 'pop_202312': 9500000, 'rate_202312': -0.8,
     'pop_202412': 9400000, 'rate_202412': -1.05},
]

# 2줄 헤더 테이블 (년월 + 지표)
html = TableGenerator.multi_header_table(
    data=data,
    row_key='sido_nm',           # 행 이름 키
    row_label='시도',             # 첫 컬럼 제목
    ym_list=['202312', '202412'], # 기준년월
    metrics=[                     # 지표 정의 (키, 표시명)
        ('pop', '인구'),
        ('rate', '증감률')
    ],
    highlight='경상북도',          # 강조할 행 (빨간 배경)
    summary_row='합계'            # 합계 행 (노란 배경)
)
```

**결과 테이블 특징:**
- 자동 정렬: 합계 → 강조지역(경상북도) → 나머지 (코드순)
- 합계 행: 노란 배경
- 강조 행: 빨간 배경
- 증감률: 양수는 파란색, 음수는 빨간색
- 숫자: 천단위 콤마 자동 적용

**주요 메서드:**

| 메서드 | 용도 | 주요 파라미터 |
|--------|------|--------------|
| `multi_header_table()` | 2줄 헤더 테이블 | ym_list, metrics, highlight |
| `simple_table()` | 단순 테이블 | columns, highlight_values |
| `dataframe_to_html()` | DataFrame 변환 | df, highlight_col |

### 10.4 DashboardBase - 상속 방식 (권장)

새 대시보드를 만들 때 `DashboardBase`를 상속하면 공통 기능을 재사용할 수 있습니다.

```python
from module.dashboard import DashboardBase
from module.db import get_db_engine
import pandas as pd

class PopulationDashboard(DashboardBase):
    """인구 대시보드"""

    def __init__(self):
        super().__init__(
            title='인구 현황 대시보드',
            highlight_region='경상북도'
        )
        self.engine = get_db_engine()

    def get_data(self, filters):
        """데이터 조회 (필수 구현)"""
        base_ym = filters.get('base_ym', '202412')

        df = pd.read_sql(f"""
            SELECT sido_nm, SUM(total_pop) as pop
            FROM cache_sigungu_indicators
            WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}'
            GROUP BY sido_nm
        """, self.engine)

        return {'sido_data': df.to_dict('records')}

    def get_filter_options(self):
        """필터 옵션 (필수 구현)"""
        return {
            'base_ym_list': ['202312', '202412', '202512'],
            'sido_list': ['서울특별시', '부산광역시', '경상북도']
        }

# Flask 라우트에서 사용
dashboard = PopulationDashboard()

@app.route('/population')
def population_page():
    return dashboard.render(request.args)
```

**필수 구현 메서드:**
- `get_data(filters)`: 데이터 조회 로직
- `get_filter_options()`: 필터 드롭다운 옵션

### 10.5 ExportManager - 내보내기

Excel, Markdown, HTML 파일로 내보내기 기능을 제공합니다.

```python
from module.dashboard import ExportManager
import pandas as pd

df = pd.DataFrame({
    'sido_nm': ['서울', '부산', '경상북도'],
    'pop': [9500000, 3300000, 2600000]
})

# Excel 내보내기
ExportManager.to_excel(
    df_dict={'시도별인구': df},
    output_path='output/population.xlsx',
    highlight_rows=['경상북도']  # 강조 행
)

# 전체 내보내기 (Excel + Markdown + HTML)
ExportManager.export_all(
    data={'시도별': df, '연령별': df_age},
    output_dir='output',
    filename='report',
    highlight_regions=['경상북도']
)
```

### 10.6 컴포넌트 요약

| 컴포넌트 | 용도 | import 방법 |
|---------|------|------------|
| **ChartGenerator** | 차트 생성 (Base64) | `from module.dashboard import ChartGenerator` |
| **TableGenerator** | HTML 테이블 | `from module.dashboard import TableGenerator` |
| **ExportManager** | 파일 내보내기 | `from module.dashboard import ExportManager` |
| **DashboardBase** | 상속용 베이스 | `from module.dashboard import DashboardBase` |

### 10.7 강조(Highlight) 기능

모든 컴포넌트에서 `highlight` 파라미터로 특정 지역을 강조할 수 있습니다:

```python
# 차트에서 강조 (빨간 테두리)
ChartGenerator.bar_chart(..., highlight='경상북도')

# 테이블에서 강조 (빨간 배경)
TableGenerator.multi_header_table(..., highlight='경상북도')

# 내보내기에서 강조
ExportManager.to_excel(..., highlight_rows=['경상북도'])
```

기본 강조 색상:
- **HIGHLIGHT_COLOR**: `#F24822` (빨간색)
- **HIGHLIGHT_EDGE_COLOR**: `#dc2626` (진한 빨간 테두리)

---

*이 문서는 인구통계 대시보드 프로젝트 교육 및 인수인계를 위해 작성되었습니다.*
*최종 업데이트: 2026-01-20*
