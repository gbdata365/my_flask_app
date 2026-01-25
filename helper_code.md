# 데이터 분석 대시보드 프로젝트 - 개발자 인수인계 문서

> **작성일**: 2026-01-23
> **프로젝트**: Flask 기반 데이터 분석 대시보드
> **목적**: 유지보수 및 기능 추가를 위한 기술 문서

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [디렉토리 구조](#2-디렉토리-구조)
3. [데이터베이스 구조](#3-데이터베이스-구조)
4. [핵심 모듈 설명](#4-핵심-모듈-설명)
5. [모듈 연계도](#5-모듈-연계도)
6. [라우트 시스템](#6-라우트-시스템)
7. [실전 예제 5가지](#7-실전-예제-5가지)
8. [환경 설정](#8-환경-설정)

---

## 1. 프로젝트 개요

### 1.1 시스템 구성

```
Flask 웹 서버 (main_app.py)
    ↓
카테고리 기반 라우팅 (01_인구및가구현황, 02_기업체현황, ...)
    ↓
PostgreSQL 데이터베이스 (캐시 테이블)
    ↓
대시보드 렌더링 (차트, 테이블, 내보내기)
```

### 1.2 주요 기술 스택

| 분야 | 기술 |
|------|------|
| 백엔드 | Flask, Python 3 |
| 데이터베이스 | PostgreSQL, SQLAlchemy |
| 프론트엔드 | Jinja2, Bootstrap 5 |
| 차트 | Matplotlib (Base64 인코딩) |
| 환경 관리 | python-dotenv, uv |

---

## 2. 디렉토리 구조

```
01_claude_project/
├── main_app.py              # Flask 메인 애플리케이션 (진입점)
├── .env                     # 환경 변수 (DB 접속 정보)
│
├── module/                  # 공통 모듈
│   ├── db.py               # DB 연결 (psycopg2, SQLAlchemy)
│   ├── data_query.py       # 캐시 테이블 조회 클래스
│   ├── menu_generator.py   # 동적 메뉴 생성
│   ├── markdown_renderer.py # 마크다운 렌더링
│   └── dashboard/          # 대시보드 컴포넌트
│       ├── __init__.py     # 모듈 export
│       ├── base.py         # DashboardBase 베이스 클래스
│       ├── charts.py       # ChartGenerator (Matplotlib)
│       ├── tables.py       # TableGenerator (HTML 테이블)
│       └── export.py       # ExportManager (Excel/MD/HTML)
│
├── common/                  # 공통 유틸리티
│   └── export_utils.py     # 내보내기 유틸리티
│
├── templates/               # 기본 템플릿
│   ├── index.html          # 메인 페이지
│   └── category_with_navbar.html  # 카테고리 레이아웃
│
├── 01_인구및가구현황/        # 인구/가구 분석 카테고리
│   ├── routes/             # Flask 라우트 (대시보드)
│   │   ├── 02_인구별현황.py
│   │   ├── 03_가구별 현황.py
│   │   ├── _edu_dash2_new.py   # _로 시작 = 메뉴 비표시
│   │   └── _population_api.py  # Blueprint API
│   ├── templates/          # Jinja2 템플릿
│   └── markdown_docs/      # 마크다운 문서
│
├── 02_기업체현황/           # 기업체 분석 카테고리
│   └── ...
│
└── 9_data/                  # 데이터베이스 뷰어
    ├── routes/
    └── markdown_docs/
```

### 2.1 폴더 명명 규칙

| 패턴 | 설명 | 예시 |
|------|------|------|
| `숫자_이름/` | 카테고리 폴더 (자동 등록) | `01_인구및가구현황`, `02_기업체현황` |
| `routes/파일명.py` | 대시보드 라우트 (메뉴 표시) | `02_인구별현황.py` |
| `routes/_파일명.py` | 내부 모듈 (메뉴 비표시) | `_population_api.py` |
| `markdown_docs/` | 마크다운 문서 폴더 | `index.md` (첫 화면) |

---

## 3. 데이터베이스 구조

### 3.1 주요 테이블 현황

#### 캐시 테이블 (주로 사용)

| 테이블명 | 설명 | 주요 컬럼 |
|----------|------|-----------|
| `cache_sigungu_indicators` | 시군구별 인구/세대 지표 | `base_ym`, `sigungu_code`, `sido_nm`, `total_pop`, `household_cnt`, `single_cnt`, `age_65_over` |
| `cache_sigungu_age` | 시군구별 연령별 1인가구 | `base_ym`, `sigungu_code`, `age_group`, `single_cnt` |

#### 코드 테이블 (참조용)

| 테이블명 | 설명 |
|----------|------|
| `dim_admin_area` | 행정구역 마스터 (권역/시도/시군구) |
| `code_indicator` | 지표 정의 코드 |
| `code_age_groups` | 연령 그룹 정의 코드 |

### 3.2 캐시 테이블 상세

```sql
-- cache_sigungu_indicators 테이블 구조
CREATE TABLE cache_sigungu_indicators (
    base_ym         DATE,           -- 기준년월 (2024-12-01)
    sigungu_code    VARCHAR(5),     -- 시군구코드 (11010)
    sido_nm         VARCHAR(20),    -- 시도명 (정규화됨: 강원특별자치도)
    sigungu_nm      VARCHAR(30),    -- 시군구명
    total_pop       INTEGER,        -- 총인구
    household_cnt   INTEGER,        -- 총세대수
    single_cnt      INTEGER,        -- 1인가구수
    age_65_over     INTEGER,        -- 65세이상인구
    ...
);
```

**중요**: `sido_nm`은 이미 정규화되어 있음 (강원도→강원특별자치도, 전라북도→전북특별자치도)
→ SQL에서 CASE문 변환 불필요

### 3.3 데이터 조회 패턴

```python
from module.data_query import CacheDataQuery

# 인스턴스 생성
query = CacheDataQuery('cache_sigungu_indicators')

# 필터 옵션 조회
filters = query.get_filter_options()
# 결과: {'base_ym_list': ['202512', '202411', ...], 'sido_list': [...]}

# 시도별 데이터 조회
df = query.get_sido_data(
    base_ym_list=['202412', '202512'],
    columns=['total_pop', 'household_cnt']
)

# 시군구별 데이터 조회
df = query.get_sigungu_data(
    base_ym_list=['202512'],
    columns=['total_pop', 'single_cnt'],
    sido='경상북도'  # 특정 시도만
)
```

---

## 4. 핵심 모듈 설명

### 4.1 module/db.py - 데이터베이스 연결

```python
from module.db import get_db_engine, get_db_connection

# SQLAlchemy 엔진 (pandas와 함께 사용, 권장)
engine = get_db_engine()
df = pd.read_sql("SELECT * FROM cache_sigungu_indicators", engine)

# psycopg2 연결 (직접 SQL 실행)
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM cache_sigungu_indicators")
```

**환경 변수** (`.env` 파일):
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=population
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

### 4.2 module/data_query.py - 데이터 조회

```python
from module.data_query import CacheDataQuery, get_initial_summary

# 기본 사용법
query = CacheDataQuery('cache_sigungu_indicators')

# 필터 옵션 (드롭다운용)
filters = query.get_filter_options()
# → {'base_ym_list': [...], 'sido_list': [...], 'latest_ym': '202512'}

# 시도별 집계
df = query.get_sido_data(['202512'], ['total_pop', 'single_cnt'])

# 권역별 집계
df = query.get_region_data(['202512'], ['total_pop'])

# 전국 합계 행 추가
df = query.add_national_total(df, ['total_pop', 'single_cnt'])

# 비율 계산
df = query.calculate_ratio(df, 'single_cnt', 'total_pop', 'single_rate')
```

### 4.3 module/dashboard/ - 대시보드 컴포넌트

#### DashboardBase (상속해서 사용)

```python
from module.dashboard import DashboardBase

class MyDashboard(DashboardBase):
    def __init__(self):
        super().__init__(
            title='내 대시보드',
            highlight_region='경상북도',  # 빨간 테두리 강조
            summary_row='합계'            # 합계 행 이름
        )

    def get_filter_options(self):
        """필터 옵션 반환 (필수 구현)"""
        return {'base_ym_list': [...], 'sido_list': [...]}

    def get_data(self, filters):
        """데이터 조회 (필수 구현)"""
        return {'sido_data': [...], 'chart_data': [...]}
```

#### ChartGenerator (차트 생성)

```python
from module.dashboard import ChartGenerator

# 막대 차트
chart_img = ChartGenerator.bar_chart(
    labels=['서울', '부산', '경상북도'],
    datasets=[{'label': '2024', 'data': [100, 80, 60]}],
    ylabel='인구 (만 명)',
    highlight='경상북도'  # 경상북도에 빨간 테두리
)

# 이중축 차트 (막대 + 선)
chart_img = ChartGenerator.dual_axis_chart(
    labels=['서울', '부산'],
    bar_data=[100, 80],
    line_data=[15.2, 18.5],
    bar_label='인구',
    line_label='증감률'
)
```

#### TableGenerator (테이블 생성)

```python
from module.dashboard import TableGenerator

# 2줄 헤더 테이블 (년월 × 지표)
table_html = TableGenerator.multi_header_table(
    data=data_list,
    row_key='name',          # 행 구분 키
    row_label='시도',        # 첫 열 제목
    ym_list=['202312', '202412'],
    metrics=[('pop', '인구'), ('rate', '증감률')],
    highlight='경상북도',    # 경상북도 강조
    summary_row='합계'       # 합계 행 맨 위
)
```

### 4.4 module/menu_generator.py - 메뉴 생성

```python
from module.menu_generator import MenuGenerator

# 카테고리 메뉴 항목 조회
menu_items = MenuGenerator.get_category_menu_items(
    category_base=Path('01_인구및가구현황'),
    category_name='01_인구및가구현황'
)
# 결과: [{'name': '인구별현황', 'url': '/01_.../routes/02_인구별현황', 'type': 'python'}, ...]
```

---

## 5. 모듈 연계도

```
┌─────────────────────────────────────────────────────────────────┐
│                        main_app.py                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  create_app() → register_all_categories()               │    │
│  │       ↓                                                 │    │
│  │  카테고리별 동적 라우트 등록                              │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                   카테고리 라우트 실행                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  /{category}/routes/{filename}                          │    │
│  │       ↓                                                 │    │
│  │  execute_route_module() → module.render(request_args)   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                    라우트 모듈 (예: 02_인구별현황.py)             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  def render(request_args):                              │    │
│  │       │                                                 │    │
│  │       ├── CacheDataQuery.get_filter_options()          │    │
│  │       ├── CacheDataQuery.get_sido_data()               │    │
│  │       ├── ChartGenerator.bar_chart()                   │    │
│  │       ├── TableGenerator.multi_header_table()          │    │
│  │       └── Jinja2 템플릿 렌더링                          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                     데이터베이스 조회                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  module/db.py → get_db_engine()                         │    │
│  │       ↓                                                 │    │
│  │  PostgreSQL (cache_sigungu_indicators 등)               │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 5.1 요청 처리 흐름

```
1. 사용자 접속: http://localhost:5000/01_인구및가구현황/routes/02_인구별현황
2. main_app.py → category_route_exec() 함수 호출
3. execute_route_module() → 02_인구별현황.py 동적 임포트
4. 02_인구별현황.render(request.args) 호출
5. CacheDataQuery로 DB 조회 → DataFrame
6. ChartGenerator/TableGenerator로 시각화 생성
7. Jinja2 템플릿으로 HTML 렌더링
8. 사용자에게 응답 반환
```

---

## 6. 라우트 시스템

### 6.1 라우트 파일 기본 구조

```python
# routes/파일명.py

from pathlib import Path
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from module.db import get_db_engine
from module.data_query import CacheDataQuery
from module.dashboard import ChartGenerator, TableGenerator
from module.menu_generator import MenuGenerator

# 경로 설정
BASE = Path(__file__).parent.parent
CATEGORY_NAME = BASE.name  # '01_인구및가구현황'
CURRENT_URL = f'/{CATEGORY_NAME}/routes/{Path(__file__).stem}'


def render(request_args):
    """
    메인 렌더 함수 (main_app.py에서 호출)

    Args:
        request_args: Flask request.args (GET 파라미터)

    Returns:
        HTML 문자열 또는 Flask Response
    """
    # 1. 필터 옵션 조회
    query = CacheDataQuery('cache_sigungu_indicators')
    filters = query.get_filter_options()

    # 2. 요청 파라미터 파싱
    base_ym = request_args.get('base_ym', filters['latest_ym'])
    sido = request_args.get('sido', '')

    # 3. 데이터 조회
    df = query.get_sido_data([base_ym], ['total_pop', 'single_cnt'])

    # 4. 차트/테이블 생성
    chart_img = ChartGenerator.bar_chart(...)
    table_html = TableGenerator.multi_header_table(...)

    # 5. 템플릿 렌더링
    jinja_env = Environment(loader=FileSystemLoader(str(BASE / 'templates')))
    template = jinja_env.get_template('my_template.html')

    return template.render(
        filters=filters,
        chart_img=chart_img,
        table_html=table_html,
        menu_items=MenuGenerator.get_category_menu_items(BASE, CATEGORY_NAME),
        current_url=CURRENT_URL
    )
```

### 6.2 URL 패턴

| URL 패턴 | 설명 |
|----------|------|
| `/` | 메인 페이지 (카테고리 목록) |
| `/{category}` | 카테고리 메인 (index.md 표시) |
| `/{category}/routes/{filename}` | 대시보드 라우트 실행 |
| `/{category}/markdown/{filename}` | 마크다운 문서 표시 |
| `/{category}/html/{filename}` | HTML 문서 표시 |

---

## 7. 실전 예제 5가지

### 예제 1: 새로운 대시보드 페이지 추가

**목표**: "04_연령별현황.py" 대시보드 추가

**단계**:

1. 라우트 파일 생성: `01_인구및가구현황/routes/04_연령별현황.py`

```python
from pathlib import Path
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from module.db import get_db_engine
from module.data_query import CacheDataQuery
from module.dashboard import ChartGenerator, TableGenerator
from module.menu_generator import MenuGenerator

BASE = Path(__file__).parent.parent
CATEGORY_NAME = BASE.name
CURRENT_URL = f'/{CATEGORY_NAME}/routes/{Path(__file__).stem}'


def render(request_args):
    """연령별 현황 대시보드"""

    # 데이터 조회
    query = CacheDataQuery('cache_sigungu_age')
    filters = query.get_filter_options()

    base_ym = request_args.get('base_ym', filters['latest_ym'])

    # 연령별 데이터 집계
    engine = get_db_engine()
    df = pd.read_sql(f"""
        SELECT age_group, SUM(single_cnt) as cnt
        FROM cache_sigungu_age
        WHERE TO_CHAR(base_ym, 'YYYYMM') = '{base_ym}'
        GROUP BY age_group
        ORDER BY age_group
    """, engine)

    # 차트 생성
    chart_img = ChartGenerator.bar_chart(
        labels=df['age_group'].tolist(),
        datasets=[{'label': '1인가구', 'data': df['cnt'].tolist()}],
        ylabel='가구수'
    )

    # 템플릿 렌더링
    jinja_env = Environment(loader=FileSystemLoader(str(BASE / 'templates')))
    template = jinja_env.get_template('age_dashboard.html')

    return template.render(
        filters=filters,
        selected_ym=base_ym,
        chart_img=chart_img,
        data=df.to_dict('records'),
        menu_items=MenuGenerator.get_category_menu_items(BASE, CATEGORY_NAME),
        current_url=CURRENT_URL
    )
```

2. 템플릿 파일 생성: `01_인구및가구현황/templates/age_dashboard.html`

3. **완료** - 자동으로 메뉴에 "04 연령별현황" 항목 추가됨

---

### 예제 2: 기존 대시보드에 새 지표 추가

**목표**: 인구별현황에 "고령화율" 컬럼 추가

**파일**: `01_인구및가구현황/routes/02_인구별현황.py`

**변경 사항**:

```python
# 1. 데이터 조회 시 컬럼 추가
df = query.get_sido_data(
    base_ym_list,
    ['total_pop', 'single_cnt', 'age_65_over']  # age_65_over 추가
)

# 2. 고령화율 계산
df = query.calculate_ratio(df, 'age_65_over', 'total_pop', 'aging_rate')

# 3. 테이블 생성 시 지표 추가
table_html = TableGenerator.multi_header_table(
    data=df.to_dict('records'),
    row_key='name',
    row_label='시도',
    ym_list=base_ym_list,
    metrics=[
        ('total_pop', '인구'),
        ('single_cnt', '1인가구'),
        ('aging_rate', '고령화율')  # 새 지표 추가
    ],
    highlight='경상북도'
)
```

---

### 예제 3: 새로운 카테고리 추가

**목표**: "03_보건현황" 카테고리 추가

**단계**:

1. 폴더 생성:
```
03_보건현황/
├── routes/
├── templates/
└── markdown_docs/
    └── index.md
```

2. `markdown_docs/index.md` 작성:
```markdown
# 보건 현황

보건 관련 데이터 분석 대시보드입니다.

## 주요 기능

1. 의료기관 현황
2. 건강지표 분석
```

3. 라우트 파일 생성: `03_보건현황/routes/01_의료기관현황.py`

4. **완료** - Flask 재시작 시 자동으로 카테고리 등록됨

---

### 예제 4: 차트 커스터마이징

**목표**: 특정 지역 색상 변경, 축 범위 조정

**파일**: `module/dashboard/charts.py` 참조하여 사용

```python
from module.dashboard import ChartGenerator

# 기본 막대 차트 (경상북도 강조)
chart_img = ChartGenerator.bar_chart(
    labels=['서울', '부산', '경상북도', '대구'],
    datasets=[{
        'label': '2024년',
        'data': [950, 340, 260, 240]
    }],
    ylabel='인구 (만 명)',
    highlight='경상북도',  # 빨간 테두리
    figsize=(12, 6)        # 차트 크기
)

# 이중축 차트 (막대 + 선)
chart_img = ChartGenerator.dual_axis_chart(
    labels=['서울', '부산', '경상북도'],
    bar_data=[950, 340, 260],     # 막대 데이터
    line_data=[15.2, 18.5, 22.1],  # 선 데이터
    bar_label='인구 (만 명)',
    line_label='고령화율 (%)',
    highlight='경상북도'
)
```

---

### 예제 5: 내보내기 기능 추가

**목표**: Excel/Markdown/HTML 내보내기 버튼 추가

**단계**:

1. 라우트에 내보내기 API 추가:

```python
from common.export_utils import export_to_excel, export_to_markdown

def render(request_args):
    export_type = request_args.get('export')

    if export_type:
        # 데이터 준비
        df = get_data_as_dataframe()

        if export_type == 'excel':
            output_path = export_to_excel(
                df,
                output_dir=BASE / 'output',
                filename='인구현황',
                highlight_regions=['경상북도']
            )
            return f"파일 저장됨: {output_path}"

        elif export_type == 'markdown':
            output_path = export_to_markdown(df, BASE / 'output', '인구현황')
            return f"파일 저장됨: {output_path}"

    # 일반 페이지 렌더링
    return template.render(...)
```

2. 템플릿에 버튼 추가:

```html
<div class="export-buttons">
    <a href="?export=excel" class="btn btn-success">Excel 다운로드</a>
    <a href="?export=markdown" class="btn btn-secondary">Markdown 다운로드</a>
</div>
```

---

## 8. 환경 설정

### 8.1 .env 파일

```env
# 데이터베이스 설정
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=population
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Flask 설정
PORT=5000
FLASK_DEBUG=1
```

### 8.2 의존성 설치 (uv 사용)

```bash
# uv 설치 (Windows)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 가상 환경 생성
uv venv

# 활성화
.venv\Scripts\activate

# 패키지 설치
uv pip install flask pandas numpy matplotlib psycopg2-binary sqlalchemy python-dotenv jinja2 openpyxl koreanize-matplotlib loguru
```

### 8.3 실행 방법

```bash
# 개발 서버 실행
python main_app.py

# 또는 Flask CLI
set FLASK_APP=main_app.py
flask run --debug

# 접속
http://localhost:5000
```

---

## 부록: 자주 사용하는 SQL 패턴

### A. 시도별 집계

```sql
SELECT
    sido_nm as name,
    MIN(LEFT(sigungu_code, 2)) as sido_code,
    SUM(total_pop) as pop,
    SUM(single_cnt) as single_cnt
FROM cache_sigungu_indicators
WHERE TO_CHAR(base_ym, 'YYYYMM') = '202512'
GROUP BY sido_nm
ORDER BY MIN(LEFT(sigungu_code, 2))
```

### B. 시군구별 조회 (특정 시도)

```sql
SELECT
    sigungu_code,
    sigungu_nm,
    total_pop,
    single_cnt
FROM cache_sigungu_indicators
WHERE TO_CHAR(base_ym, 'YYYYMM') = '202512'
  AND sido_nm = '경상북도'
ORDER BY sigungu_code
```

### C. 권역별 집계 (dim_admin_area 조인)

```sql
SELECT
    d.region_nm as name,
    SUM(c.total_pop) as pop
FROM cache_sigungu_indicators c
JOIN dim_admin_area d ON c.sigungu_code = d.sigungu_code
WHERE TO_CHAR(c.base_ym, 'YYYYMM') = '202512'
GROUP BY d.region_nm, d.region_code
ORDER BY d.region_code
```

---

## 문의 및 지원

- **프로젝트 위치**: `C:\Users\user\01_claude_project`
- **메인 진입점**: `main_app.py`
- **데이터베이스**: PostgreSQL (`population` 데이터베이스)
- **핵심 모듈**: `module/` 폴더

---

*이 문서는 Claude AI Agent에 의해 자동 생성되었습니다.*
