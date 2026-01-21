# 대시보드 개발 가이드 (Dashboard Development Guide)

## 목차
1. [개요](#1-개요)
2. [아키텍처 흐름도](#2-아키텍처-흐름도)
3. [디렉토리 구조](#3-디렉토리-구조)
4. [공통 모듈](#4-공통-모듈)
5. [함수 상세 설명](#5-함수-상세-설명)
6. [데이터베이스 테이블 구조](#6-데이터베이스-테이블-구조)
7. [새 대시보드 생성 가이드](#7-새-대시보드-생성-가이드)
8. [템플릿 구조](#8-템플릿-구조)
9. [체크리스트](#9-체크리스트)

---

## 1. 개요

### 1.1 기술 스택
- **Backend**: Flask (Python 3.x)
- **Frontend**: Bootstrap 5 + JavaScript
- **Database**: PostgreSQL
- **차트**: Matplotlib (정적 PNG 이미지, Base64 인코딩)
- **템플릿**: Jinja2
- **내보내기**: Excel(openpyxl), Markdown, HTML

### 1.2 핵심 패턴
```
[사용자 요청] → [파라미터 파싱] → [DB 조회] → [데이터 가공] → [차트 생성] → [HTML 렌더링]
```

---

## 2. 아키텍처 흐름도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              사용자 브라우저                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Flask 라우터 (routes/)                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  render(request_args)  ──────►  generate_dashboard_html()           │   │
│  │                                         │                            │   │
│  │                                         ▼                            │   │
│  │                              ┌──────────────────────┐               │   │
│  │                              │   파라미터 파싱       │               │   │
│  │                              │   - base_ym_list     │               │   │
│  │                              │   - age_category     │               │   │
│  │                              │   - aggregate_type   │               │   │
│  │                              │   - sido             │               │   │
│  │                              └──────────────────────┘               │   │
│  │                                         │                            │   │
│  │                    ┌────────────────────┼────────────────────┐      │   │
│  │                    ▼                    ▼                    ▼      │   │
│  │          ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │   │
│  │          │ get_age_table() │  │ get_sido_table()│  │get_indicator│ │   │
│  │          │ 연령별 데이터    │  │ 지역별 데이터    │  │  _table()   │ │   │
│  │          └─────────────────┘  └─────────────────┘  └─────────────┘ │   │
│  │                    │                    │                    │      │   │
│  │                    └────────────────────┼────────────────────┘      │   │
│  │                                         ▼                            │   │
│  │                              ┌──────────────────────┐               │   │
│  │                              │     차트 생성        │               │   │
│  │                              │ create_*_chart()     │               │   │
│  │                              │ → Base64 PNG 이미지  │               │   │
│  │                              └──────────────────────┘               │   │
│  │                                         │                            │   │
│  │                                         ▼                            │   │
│  │                              ┌──────────────────────┐               │   │
│  │                              │    테이블 HTML 생성   │               │   │
│  │                              │ create_table_html()  │               │   │
│  │                              └──────────────────────┘               │   │
│  │                                         │                            │   │
│  │                                         ▼                            │   │
│  │                              ┌──────────────────────┐               │   │
│  │                              │  Jinja2 템플릿 렌더링 │               │   │
│  │                              │  template.render()   │               │   │
│  │                              └──────────────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
            │  module/    │   │   common/   │   │ templates/  │
            │   db.py     │   │export_utils │   │  *.html     │
            └─────────────┘   └─────────────┘   └─────────────┘
                    │
                    ▼
            ┌─────────────┐
            │ PostgreSQL  │
            │  Database   │
            └─────────────┘
```

### 2.1 데이터 처리 흐름

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          데이터 처리 파이프라인                               │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   1. 코드테이블 조회                                                        │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  get_age_groups_from_db(category)                               │     │
│   │  get_active_indicators(category)                                │     │
│   │  get_column_name_labels()                                       │     │
│   │                        │                                         │     │
│   │                        ▼                                         │     │
│   │         ┌──────────────────────────┐                            │     │
│   │         │ code_age_group 테이블    │                            │     │
│   │         │ code_indicator 테이블    │                            │     │
│   │         └──────────────────────────┘                            │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                                                                            │
│   2. 팩트/캐시 테이블 조회                                                  │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  각 년월(ym)별로 SQL 실행 → DataFrame 생성 → concat              │     │
│   │                        │                                         │     │
│   │                        ▼                                         │     │
│   │         ┌──────────────────────────┐                            │     │
│   │         │ cache_sigungu_indicators │                            │     │
│   │         │ (미리 집계된 캐시 테이블)  │                            │     │
│   │         └──────────────────────────┘                            │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                                                                            │
│   3. 피벗 및 증감률 계산                                                    │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  pivot_table(index=지역, columns=년월, values=인구)             │     │
│   │                        │                                         │     │
│   │                        ▼                                         │     │
│   │  증감률 = (현재값 - 이전값) / 이전값 * 100                        │     │
│   │  ※ 가장 오래된 시점에는 증감률 표시 안함                          │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                                                                            │
│   4. 결과 반환 형식                                                        │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  {                                                               │     │
│   │    'title': '테이블 제목',                                       │     │
│   │    'headers': ['지역', '202512 인구', '202512 증감률', ...],     │     │
│   │    'data': [                                                     │     │
│   │      {'name': '전국', 'pop_202512': 51000000, ...},             │     │
│   │      {'name': '서울특별시', 'pop_202512': 9500000, ...},        │     │
│   │      ...                                                         │     │
│   │    ]                                                             │     │
│   │  }                                                               │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 디렉토리 구조

```
01_claude_project/
├── .venv/                      # 가상환경
├── .env                        # 환경변수 (DB 접속 정보)
├── CLAUDE.md                   # 프로젝트 설명서
├── dash_guide.md               # 이 가이드 문서
│
├── module/                     # 공통 모듈
│   ├── db.py                   # DB 연결 (get_db_engine)
│   └── menu_generator.py       # 동적 메뉴 생성
│
├── common/                     # 공통 유틸리티
│   ├── __init__.py
│   └── export_utils.py         # DataExporter 클래스
│
├── 01_population/              # 인구 분야 (예시)
│   ├── routes/                 # 라우트 파일들
│   │   └── edu_dash2.py        # 대시보드 메인 파일
│   │
│   ├── templates/              # HTML 템플릿
│   │   └── edu_dash2.html      # 대시보드 템플릿
│   │
│   ├── output/                 # 내보내기 파일 저장
│   └── markdown_docs/          # 문서
│
└── 02_economy/                 # 경제 분야 (새로 만들 때)
    ├── routes/
    │   └── economy_dash.py
    ├── templates/
    │   └── economy_dash.html
    └── output/
```

---

## 4. 공통 모듈

### 4.1 DB 연결 (`module/db.py`)

```python
from module.db import get_db_engine

# SQLAlchemy 엔진 (pandas와 함께 사용)
engine = get_db_engine()
df = pd.read_sql("SELECT * FROM table_name", engine)
```

**필수 환경변수** (`.env` 파일):
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=database_name
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

### 4.2 내보내기 유틸리티 (`common/export_utils.py`)

```python
from common.export_utils import DataExporter

# 사용 예시
exporter = DataExporter(
    tables_data={
        '시도별_현황': region_data,
        '연령별_현황': age_data,
    },
    charts_data={
        '시도별_현황': region_chart_base64,
        '연령별_현황': age_chart_base64,
    },
    sort_config={'column': 'pop_202512', 'direction': 'desc'},
    report_title='인구 현황 보고서'
)

# 모든 형식으로 내보내기
result = exporter.export_all(output_dir, 'filename_base')
# result = {'xlsx': 'path/to/file.xlsx', 'md': '...', 'html': '...'}
```

### 4.3 메뉴 생성기 (`module/menu_generator.py`)

```python
from module.menu_generator import MenuGenerator

# 카테고리별 메뉴 항목 생성
menu_items = MenuGenerator.get_category_menu_items(POP_BASE, '01_population')
```

---

## 5. 함수 상세 설명

### 5.1 코드 테이블 조회 함수

| 함수명 | 설명 | 반환값 |
|--------|------|--------|
| `get_age_groups_from_db(category)` | 연령그룹 정의 조회 | DataFrame (column_name, code_name, ...) |
| `get_age_categories()` | 연령 카테고리 목록 | List[Dict] |
| `get_active_indicators(category)` | 활성 지표 목록 | List[Dict] |
| `get_column_name_labels()` | 컬럼명→한글명 매핑 | Dict |
| `get_filter_options()` | 필터 옵션 (년월, 시도, 권역 등) | Dict |

### 5.2 데이터 조회 함수

| 함수명 | 설명 | 주요 파라미터 |
|--------|------|---------------|
| `get_age_population_table()` | 연령별 인구 | base_ym_list, age_category |
| `get_sido_population_table()` | 시도별 인구 | base_ym_list, region |
| `get_region_population_table()` | 권역별 인구 | base_ym_list |
| `get_sigungu_population_table()` | 시군구별 인구 | base_ym_list, sido |
| `get_indicator_table()` | 동적 지표 데이터 | base_ym_list, indicator, aggregate_type |
| `get_age_population_by_region()` | 지역별 연령 인구 (subplot용) | base_ym_list, aggregate_type, priority_region |

### 5.3 차트 생성 함수

| 함수명 | 설명 | 반환값 |
|--------|------|--------|
| `create_age_chart()` | 연령별 막대 차트 | Base64 PNG |
| `create_region_chart()` | 지역별 막대 차트 (가로/세로 자동) | Base64 PNG |
| `create_age_chart_by_region()` | 지역별 연령 subplot 차트 | Base64 PNG |
| `create_indicator_chart()` | 지표 차트 (가로 막대) | Base64 PNG |
| `add_bar_labels()` | 막대에 레이블 추가 | None (in-place) |

**차트 생성 기본 패턴**:
```python
def create_xxx_chart(data, ym_list):
    """XXX 차트 생성"""
    if not data or not data.get('data'):
        return None

    try:
        import koreanize_matplotlib  # 한글 폰트
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(12, 6))

        # 차트 그리기
        # ...

        plt.tight_layout()

        # Base64 변환
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return img_base64

    except Exception as e:
        print(f"Chart error: {e}")
        return None
```

### 5.4 HTML 생성 함수

| 함수명 | 설명 |
|--------|------|
| `create_table_html()` | 2줄 헤더 테이블 (정렬 기능 포함) |
| `create_age_by_region_table_html()` | 아코디언 형식 테이블 |
| `create_indicator_table_html()` | 지표용 테이블 |

### 5.5 메인 함수

| 함수명 | 설명 |
|--------|------|
| `generate_dashboard_html()` | 전체 대시보드 HTML 생성 |
| `handle_api_request()` | API 요청 처리 (내보내기 등) |
| `render()` | Flask 라우트 진입점 |

---

## 6. 데이터베이스 테이블 구조

### 6.1 필수 테이블

#### 코드 테이블 (마스터)

**code_age_group** (연령그룹 정의)
```sql
CREATE TABLE code_age_group (
    id SERIAL PRIMARY KEY,
    category INTEGER,          -- 1: 5세별, 2: 10세별, 3: 정책연령
    code_name VARCHAR(50),     -- 한글명 (예: '0~4세')
    column_name VARCHAR(50),   -- 컬럼명 (예: 'age_0_4')
    age_start INTEGER,
    age_end INTEGER,
    sort_order INTEGER,
    is_active BOOLEAN DEFAULT TRUE
);
```

**code_indicator** (지표 정의)
```sql
CREATE TABLE code_indicator (
    id SERIAL PRIMARY KEY,
    category INTEGER,          -- 1: 인구지표
    column_name VARCHAR(50),   -- 컬럼명 (예: 'youth_rate')
    display_name VARCHAR(100), -- 표시명 (예: '유소년비율')
    description TEXT,          -- 산식 설명
    numerator VARCHAR(100),    -- 분자 컬럼명
    denominator VARCHAR(100),  -- 분모 컬럼명 (기본: total_pop)
    unit VARCHAR(20),          -- 단위 (%, 명, 등)
    sort_order INTEGER,
    is_active BOOLEAN DEFAULT TRUE
);
```

**dim_admin_area** (행정구역)
```sql
CREATE TABLE dim_admin_area (
    sigungu_code VARCHAR(10) PRIMARY KEY,
    sigungu_nm VARCHAR(50),
    sido_nm VARCHAR(50),
    region_nm VARCHAR(50),     -- 권역명 (수도권, 경상권 등)
    region_code VARCHAR(10)
);
```

#### 캐시 테이블 (집계 데이터)

**cache_sigungu_indicators** (시군구별 집계)
```sql
CREATE TABLE cache_sigungu_indicators (
    id SERIAL PRIMARY KEY,
    base_ym DATE,              -- 기준년월
    sigungu_code VARCHAR(10),
    sigungu_nm VARCHAR(50),
    sido_nm VARCHAR(50),

    -- 기본 인구
    total_pop INTEGER,
    male_pop INTEGER,
    female_pop INTEGER,

    -- 연령별 인구 (5세별, 10세별)
    age_0_4 INTEGER,
    age_5_9 INTEGER,
    age_10_14 INTEGER,
    ...
    age_85_over INTEGER,

    -- 특수 인구
    youth_pop INTEGER,         -- 유소년인구 (0~14세)
    working_pop INTEGER,       -- 생산가능인구 (15~64세)
    elderly_pop INTEGER,       -- 고령인구 (65세 이상)

    -- 가구
    household_cnt INTEGER,

    -- 계산 지표
    youth_rate NUMERIC(5,2),   -- 유소년비율
    aging_rate NUMERIC(5,2),   -- 고령화율
    old_age_index NUMERIC(5,2) -- 노령화지수
);

-- 인덱스
CREATE INDEX idx_cache_sigungu_base_ym ON cache_sigungu_indicators(base_ym);
CREATE INDEX idx_cache_sigungu_code ON cache_sigungu_indicators(sigungu_code);
```

### 6.2 특별자치도 처리

강원도→강원특별자치도, 전라북도→전북특별자치도 등 명칭 변경 대응:

```sql
-- SQL에서 CASE WHEN으로 합산
SELECT
    CASE
        WHEN sido_nm IN ('강원특별자치도', '강원도') THEN '강원특별자치도'
        WHEN sido_nm IN ('전북특별자치도', '전라북도') THEN '전북특별자치도'
        WHEN sido_nm IN ('제주특별자치도', '제주도') THEN '제주특별자치도'
        ELSE sido_nm
    END as sido_nm,
    SUM(total_pop) as total_pop
FROM cache_sigungu_indicators
WHERE TO_CHAR(base_ym, 'YYYYMM') = '202512'
GROUP BY CASE ... END
ORDER BY MIN(LEFT(sigungu_code, 2))
```

---

## 7. 새 대시보드 생성 가이드

### Step 1: 디렉토리 구조 생성

```bash
mkdir -p 02_economy/routes
mkdir -p 02_economy/templates
mkdir -p 02_economy/output
```

### Step 2: 코드 테이블 생성

```sql
-- 지표 정의
INSERT INTO code_indicator (category, column_name, display_name, description, numerator, unit, sort_order)
VALUES
(2, 'gdp_growth', 'GDP성장률', 'GDP 전년대비 성장률', 'gdp', '%', 1),
(2, 'unemployment_rate', '실업률', '실업자/경제활동인구*100', 'unemployed', '%', 2);
```

### Step 3: 캐시 테이블 생성

```sql
CREATE TABLE cache_economy_indicators (
    id SERIAL PRIMARY KEY,
    base_ym DATE,
    region_code VARCHAR(10),
    region_nm VARCHAR(50),

    -- 경제 지표
    gdp NUMERIC(15,2),
    gdp_growth NUMERIC(5,2),
    employed INTEGER,
    unemployed INTEGER,
    unemployment_rate NUMERIC(5,2)
);
```

### Step 4: 라우트 파일 생성 (`02_economy/routes/economy_dash.py`)

```python
# -*- coding: utf-8 -*-
"""경제 지표 대시보드"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import io
import base64
import koreanize_matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_engine
from module.menu_generator import MenuGenerator
from common.export_utils import DataExporter
from flask import jsonify, send_file

# 경로 설정
ECON_BASE = Path(__file__).parent.parent
TEMPLATE_DIR = ECON_BASE / 'templates'
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


# =============================================================================
# 코드 테이블 조회
# =============================================================================

def get_active_indicators(category=2):  # 2: 경제지표
    """활성 경제 지표 목록 조회"""
    engine = get_db_engine()
    df = pd.read_sql(f"""
        SELECT column_name, display_name, description, numerator, unit
        FROM code_indicator
        WHERE category = {category} AND is_active = TRUE
        ORDER BY sort_order
    """, engine)
    return df.to_dict('records')


def get_filter_options():
    """필터 옵션 조회"""
    engine = get_db_engine()

    # 기준년월 목록
    ym_df = pd.read_sql("""
        SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as ym
        FROM cache_economy_indicators
        ORDER BY ym DESC
    """, engine)

    # 지역 목록
    region_df = pd.read_sql("""
        SELECT DISTINCT region_nm FROM cache_economy_indicators
        WHERE region_nm IS NOT NULL
        ORDER BY region_nm
    """, engine)

    return {
        'base_ym_list': ym_df['ym'].tolist(),
        'region_list': region_df['region_nm'].tolist(),
        'active_indicators': get_active_indicators(2)
    }


# =============================================================================
# 데이터 조회 함수
# =============================================================================

def get_economy_table(base_ym_list, indicator_column):
    """경제 지표 테이블 조회"""
    engine = get_db_engine()

    results = []
    for ym in base_ym_list:
        df = pd.read_sql(f"""
            SELECT
                region_nm as name,
                {indicator_column} as value
            FROM cache_economy_indicators
            WHERE TO_CHAR(base_ym, 'YYYYMM') = '{ym}'
            ORDER BY region_nm
        """, engine)
        df['base_ym'] = ym
        results.append(df)

    if not results:
        return {'headers': [], 'data': []}

    combined_df = pd.concat(results, ignore_index=True)
    pivot = combined_df.pivot(index='name', columns='base_ym', values='value').fillna(0)

    data = []
    # 전국 합계
    total_row = {'name': '전국'}
    for ym in base_ym_list:
        if ym in pivot.columns:
            total_row[f'value_{ym}'] = round(pivot[ym].mean(), 2)  # 평균
    data.append(total_row)

    # 각 지역 행
    for region in pivot.index:
        row = {'name': region}
        for i, ym in enumerate(base_ym_list):
            if ym in pivot.columns:
                row[f'value_{ym}'] = round(pivot.loc[region, ym], 2)
                # 증감 계산 (이전 시점 대비)
                if i < len(base_ym_list) - 1 and base_ym_list[i+1] in pivot.columns:
                    prev_val = pivot.loc[region, base_ym_list[i+1]]
                    row[f'change_{ym}'] = round(row[f'value_{ym}'] - prev_val, 2)
        data.append(row)

    return {'data': data}


# =============================================================================
# 차트 생성
# =============================================================================

def create_economy_chart(data, ym_list, indicator_name):
    """경제 지표 차트 생성"""
    if not data or not data.get('data'):
        return None

    try:
        rows = data['data'][1:]  # 전국 제외
        labels = [r['name'] for r in rows]

        fig, ax = plt.subplots(figsize=(12, 6))
        colors = ['#1D64F2', '#F24822', '#10b981', '#f59e0b']

        x = np.arange(len(labels))
        width = 0.8 / len(ym_list)

        for i, ym in enumerate(ym_list):
            values = [r.get(f'value_{ym}', 0) for r in rows]
            ax.bar(x + i * width - (len(ym_list) - 1) * width / 2,
                   values, width, label=f'{ym[:4]}.{ym[4:]}',
                   color=colors[i % len(colors)])

        ax.set_xlabel('지역')
        ax.set_ylabel(indicator_name)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return img_base64

    except Exception as e:
        print(f"Chart error: {e}")
        return None


# =============================================================================
# 테이블 HTML 생성
# =============================================================================

def create_table_html(data, ym_list):
    """테이블 HTML 생성"""
    if not data or not data.get('data'):
        return '<p class="text-muted">데이터가 없습니다.</p>'

    rows = data['data']
    html = ['<table class="data-table">']

    # 헤더
    html.append('<thead><tr>')
    html.append('<th>지역</th>')
    for ym in ym_list:
        html.append(f'<th>{ym[:4]}년 {ym[4:]}월</th>')
    html.append('</tr></thead>')

    # 바디
    html.append('<tbody>')
    for row in rows:
        html.append('<tr>')
        html.append(f'<td>{row.get("name", "")}</td>')
        for ym in ym_list:
            val = row.get(f'value_{ym}', 0)
            html.append(f'<td>{val:,.2f}</td>')
        html.append('</tr>')
    html.append('</tbody>')

    html.append('</table>')
    return '\n'.join(html)


# =============================================================================
# 메인 렌더링
# =============================================================================

def generate_dashboard_html(request_args):
    """대시보드 HTML 생성"""
    # 파라미터 파싱
    base_ym_str = request_args.get('base_ym_list', '')
    base_ym_list = sorted([ym.strip() for ym in base_ym_str.split(',') if ym.strip()], reverse=True)
    indicator = request_args.get('indicator', 'gdp_growth')

    filters = get_filter_options()

    if not base_ym_list:
        # 초기 화면
        template = jinja_env.get_template('economy_dash.html')
        return template.render(
            filters=filters,
            chart_img=None,
            table_html='<p class="text-muted">조회 버튼을 클릭하세요.</p>'
        )

    # 데이터 조회
    data = get_economy_table(base_ym_list, indicator)
    chart_img = create_economy_chart(data, base_ym_list, indicator)
    table_html = create_table_html(data, base_ym_list)

    menu_items = MenuGenerator.get_category_menu_items(ECON_BASE, '02_economy')

    template = jinja_env.get_template('economy_dash.html')
    return template.render(
        filters=filters,
        selected_ym_list=base_ym_list,
        selected_indicator=indicator,
        chart_img=chart_img,
        table_html=table_html,
        menu_items=menu_items,
        current_url='/02_economy/economy_dash'
    )


def render(request_args):
    """Flask 라우트 진입점"""
    return generate_dashboard_html(request_args)
```

### Step 5: 템플릿 생성 (`02_economy/templates/economy_dash.html`)

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>경제 지표 대시보드</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        /* CSS 스타일 (edu_dash2.html 참고) */
        .data-table { width: 100%; border-collapse: collapse; }
        .data-table th, .data-table td { padding: 8px; border: 1px solid #ddd; }
        .data-table th { background: #1243A6; color: white; }
    </style>
</head>
<body>
    <div class="container-fluid p-4">
        <h4>경제 지표 대시보드</h4>

        <!-- 필터 -->
        <div class="card mb-3 p-3">
            <div class="row g-3">
                <div class="col-md-4">
                    <label>기준년월</label>
                    <select id="ymSelect" multiple class="form-select">
                        {% for ym in filters.base_ym_list %}
                        <option value="{{ ym }}">{{ ym[:4] }}년 {{ ym[4:] }}월</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-4">
                    <label>지표</label>
                    <select id="indicatorSelect" class="form-select">
                        {% for ind in filters.active_indicators %}
                        <option value="{{ ind.column_name }}">{{ ind.display_name }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-2">
                    <button onclick="loadData()" class="btn btn-primary">조회</button>
                </div>
            </div>
        </div>

        <!-- 차트 -->
        {% if chart_img %}
        <div class="card mb-3 p-3">
            <img src="data:image/png;base64,{{ chart_img }}" style="max-width: 100%;">
        </div>
        {% endif %}

        <!-- 테이블 -->
        <div class="card p-3">
            {{ table_html|safe }}
        </div>
    </div>

    <script>
        function loadData() {
            const yms = Array.from(document.getElementById('ymSelect').selectedOptions)
                           .map(o => o.value).join(',');
            const indicator = document.getElementById('indicatorSelect').value;
            window.location.href = `?base_ym_list=${yms}&indicator=${indicator}`;
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

### Step 6: Flask 라우트 등록 (`app.py`)

```python
from flask import Flask, request

app = Flask(__name__)

@app.route('/02_economy/economy_dash')
def economy_dash():
    from 02_economy.routes.economy_dash import render
    return render(request.args)
```

---

## 8. 템플릿 구조

### 8.1 기본 레이아웃

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <!-- 1. 메타 & CSS -->
    <meta charset="UTF-8">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        /* 커스텀 스타일 */
        .data-table { /* 테이블 스타일 */ }
        .chart-container { /* 차트 컨테이너 */ }
        .tab-btn { /* 탭 버튼 */ }
    </style>
</head>
<body>
    <div class="container-fluid p-4">
        <!-- 2. 헤더 & 메뉴 -->
        <div class="sidebar">
            {% for item in menu_items %}
            <a href="{{ item.url }}">{{ item.name }}</a>
            {% endfor %}
        </div>

        <!-- 3. 필터 영역 -->
        <div class="card filter-card">
            <div class="row g-3">
                <!-- 기준년월 선택 -->
                <!-- 집계단위 선택 -->
                <!-- 조회/내보내기 버튼 -->
            </div>
        </div>

        <!-- 4. 탭 네비게이션 -->
        <div class="tab-buttons">
            <button class="tab-btn active" onclick="showTab('region')">지역별</button>
            <button class="tab-btn" onclick="showTab('age')">연령별</button>
        </div>

        <!-- 5. 탭 콘텐츠 -->
        <div class="card">
            <div id="tab-region" class="tab-content active">
                <!-- 차트 -->
                {% if region_chart_img %}
                <img src="data:image/png;base64,{{ region_chart_img }}">
                {% endif %}
                <!-- 테이블 -->
                {{ region_table_html|safe }}
            </div>

            <div id="tab-age" class="tab-content">
                <!-- ... -->
            </div>
        </div>
    </div>

    <!-- 6. JavaScript -->
    <script>
        function showTab(tabId) { /* 탭 전환 */ }
        function loadAllData() { /* 데이터 조회 */ }
        function exportData() { /* 내보내기 */ }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

### 8.2 주요 UI 컴포넌트

#### 년월 선택 (뱃지 형식)
```html
<div id="selectedYmBadges" class="d-flex flex-wrap gap-1">
    <!-- JavaScript로 동적 생성 -->
</div>
<select id="ymSelect" onchange="addYm(this)">
    {% for ym in filters.base_ym_list %}
    <option value="{{ ym }}">{{ ym[:4] }}년 {{ ym[4:] }}월</option>
    {% endfor %}
</select>
```

#### 집계단위 드롭다운
```html
<select id="aggregateSelect" onchange="onAggregateChange()">
    <option value="region">권역별</option>
    <option value="sido">시도별</option>
    <option value="sigungu">시군구별</option>
</select>

<!-- 시도 선택 (시군구별일 때만 표시) -->
<div id="sidoSelectDiv" style="display: none;">
    <select id="sidoSelect">
        {% for sido in filters.sido_list %}
        <option value="{{ sido }}">{{ sido }}</option>
        {% endfor %}
    </select>
</div>
```

#### 아코디언 테이블
```html
<div class="accordion" id="dataAccordion">
    {% for item in items %}
    <div class="accordion-item">
        <h2 class="accordion-header">
            <button class="accordion-button {% if not loop.first %}collapsed{% endif %}"
                    data-bs-toggle="collapse" data-bs-target="#collapse{{ loop.index }}">
                {{ item.name }}
            </button>
        </h2>
        <div id="collapse{{ loop.index }}" class="accordion-collapse collapse {% if loop.first %}show{% endif %}"
             data-bs-parent="#dataAccordion">
            <div class="accordion-body">
                {{ item.table_html|safe }}
            </div>
        </div>
    </div>
    {% endfor %}
</div>
```

---

## 9. 체크리스트

### 새 대시보드 생성 시 확인 사항

- [ ] **디렉토리 구조**
  - [ ] `XX_분야/routes/` 폴더 생성
  - [ ] `XX_분야/templates/` 폴더 생성
  - [ ] `XX_분야/output/` 폴더 생성

- [ ] **데이터베이스**
  - [ ] 코드 테이블 생성 (code_indicator, code_xxx_group)
  - [ ] 캐시 테이블 생성 (cache_xxx_indicators)
  - [ ] 인덱스 생성 (base_ym, 주요 조회 컬럼)

- [ ] **라우트 파일**
  - [ ] 공통 모듈 import (db, menu_generator, export_utils)
  - [ ] get_filter_options() 구현
  - [ ] get_xxx_table() 데이터 조회 함수 구현
  - [ ] create_xxx_chart() 차트 생성 함수 구현
  - [ ] create_table_html() HTML 생성 함수 구현
  - [ ] generate_dashboard_html() 메인 함수 구현
  - [ ] render() 진입점 함수 구현

- [ ] **템플릿 파일**
  - [ ] Bootstrap CSS/JS 포함
  - [ ] 필터 영역 구현
  - [ ] 탭 네비게이션 구현 (필요시)
  - [ ] 차트 영역 구현
  - [ ] 테이블 영역 구현
  - [ ] JavaScript 함수 구현 (loadData, exportData 등)

- [ ] **Flask 라우트 등록**
  - [ ] app.py에 라우트 추가

- [ ] **테스트**
  - [ ] 초기 화면 로딩
  - [ ] 데이터 조회
  - [ ] 필터 변경
  - [ ] 내보내기 (Excel, MD, HTML)

### 공통 실수 방지

1. **특별자치도 처리**: 강원도/강원특별자치도, 전라북도/전북특별자치도 CASE WHEN 처리
2. **증감률 계산**: 가장 오래된 시점에는 증감률 표시 안함
3. **NULL 처리**: COALESCE 사용
4. **정렬**: 시도코드/지역코드 기준 정렬
5. **Bootstrap JS**: 아코디언 등 동적 컴포넌트 사용 시 필수 포함
6. **한글 차트**: `import koreanize_matplotlib` 필수

---

## 10. 참고 파일 경로

| 파일 | 경로 | 설명 |
|------|------|------|
| 인구 대시보드 라우트 | `01_population/routes/edu_dash2.py` | 전체 기능 참고 |
| 인구 대시보드 템플릿 | `01_population/templates/edu_dash2.html` | UI 참고 |
| DB 모듈 | `module/db.py` | DB 연결 |
| 메뉴 생성기 | `module/menu_generator.py` | 동적 메뉴 |
| 내보내기 유틸 | `common/export_utils.py` | DataExporter |

---

*이 가이드는 edu_dash2.py 대시보드를 기반으로 작성되었습니다.*
*작성일: 2026-01-21*
