# Flask 데이터 분석 대시보드 프로젝트 설명서

## 1. 프로젝트 구조 개요

```
01_claude_project/
├── main_app.py              # Flask 메인 애플리케이션 (진입점)
├── module/                  # 공통 모듈
│   ├── db.py               # DB 연결
│   ├── config.py           # 설정 상수
│   ├── markdown_renderer.py # 마크다운 렌더링
│   ├── menu_generator.py   # 동적 메뉴 생성
│   ├── visualizers.py      # 차트 시각화 (6종)
│   ├── aggregators.py      # 데이터 집계 (5종)
│   └── transforms.py       # 데이터 변환 (9종)
├── templates/              # 기본 템플릿
└── 01_population/          # 인구통계 카테고리
    ├── routes/             # Flask Blueprint
    │   ├── population_routes.py  # 대시보드 라우트
    │   └── age.py               # 연령별 통계 라우트
    ├── templates/          # 인구통계 템플릿
    └── markdown_docs/      # 마크다운 문서
```

---

## 2. main_app.py - 메인 애플리케이션

### 역할
Flask 웹 애플리케이션의 진입점으로, 모든 라우트를 등록하고 서버를 실행합니다.

### 사용 모듈
| 모듈 | 용도 |
|------|------|
| `flask` | 웹 프레임워크 (Flask, render_template, redirect) |
| `pathlib.Path` | 파일 경로 처리 |
| `importlib.util` | 동적 모듈 임포트 |
| `dotenv` | 환경변수 로드 |
| `module.menu_generator` | 동적 메뉴 생성 |
| `module.markdown_renderer` | 마크다운 렌더링 |

### 주요 함수

| 함수 | 설명 |
|------|------|
| `create_app()` | Flask 앱 인스턴스 생성 및 설정 |
| `get_category_list()` | 숫자_이름 형식 폴더 목록 조회 |
| `register_population_routes()` | 01_population 라우트 등록 |
| `get_first_markdown_content()` | index.md 또는 첫 번째 마크다운 렌더링 |
| `execute_route_module()` | routes/*.py 파일의 render() 함수 실행 |
| `is_complete_html()` | HTML 문서 완전성 체크 |
| `ensure_templates()` | 기본 템플릿 자동 생성 |

### 처리 흐름

```
1. 앱 시작 (python main_app.py)
   │
2. create_app() 호출
   │
   ├─ Flask 앱 생성
   ├─ 메인 페이지 라우트 등록 (@app.route("/"))
   └─ register_population_routes() 호출
      │
      ├─ Blueprint 등록 (population_bp, age_bp)
      ├─ /01_population 라우트 등록
      ├─ /01_population/routes/<filename> 라우트 등록
      ├─ /01_population/html/<filename> 라우트 등록
      └─ /01_population/markdown/<filename> 라우트 등록
   │
3. app.run() - 서버 시작 (port 5000)
```

---

## 3. module/ - 공통 모듈

### 3.1 db.py - 데이터베이스 연결

#### 역할
PostgreSQL 데이터베이스 연결을 관리합니다.

#### 사용 모듈
| 모듈 | 용도 |
|------|------|
| `psycopg2` | PostgreSQL 연결 |
| `dotenv` | .env 파일 로드 |
| `loguru` | 로깅 |

#### 주요 함수

| 함수 | 매개변수 | 반환값 | 설명 |
|------|----------|--------|------|
| `get_db_connection()` | database (str, optional) | psycopg2 connection | DB 연결 객체 생성 |
| `execute_query()` | query, params, database | list | SQL 실행 후 결과 반환 |

#### 환경변수
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=population
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

---

### 3.2 config.py - 설정 상수

#### 역할
차트 크기, 색상, 단위 등 공통 상수를 정의합니다.

#### 상수 목록

| 상수 | 값 | 용도 |
|------|-----|------|
| `FIGSIZE_SMALL` | (8, 6) | 소형 차트 |
| `FIGSIZE_MEDIUM` | (12, 8) | 중형 차트 (기본) |
| `FIGSIZE_LARGE` | (16, 10) | 대형 차트 (히트맵) |
| `FIGSIZE_WIDE` | (14, 6) | 가로형 차트 (시계열) |
| `COLORS` | dict | 용도별 색상 (male, female, total 등) |
| `COLOR_PALETTE` | list | 다중 계열용 8색 팔레트 |
| `UNIT_MAN` | 10000 | 만 단위 |
| `UNIT_CHEON` | 1000 | 천 단위 |
| `UNIT_EUK` | 100000000 | 억 단위 |

#### 유틸리티 함수
| 함수 | 설명 |
|------|------|
| `ensure_dir(path)` | 디렉토리 생성 (없으면) |

---

### 3.3 markdown_renderer.py - 마크다운 렌더링

#### 역할
마크다운 파일을 스타일이 적용된 HTML로 변환합니다.

#### 사용 모듈
| 모듈 | 용도 |
|------|------|
| `markdown` | 마크다운 → HTML 변환 |

#### 클래스: MarkdownRenderer

| 메서드 | 설명 |
|--------|------|
| `__init__()` | 마크다운 파서 초기화 (tables, fenced_code, toc, codehilite 확장) |
| `get_markdown_styles()` | CSS 스타일 문자열 반환 |
| `render_file(file_path)` | 마크다운 파일을 HTML로 변환 |
| `render_text(markdown_text)` | 마크다운 문자열을 HTML로 변환 |

---

### 3.4 menu_generator.py - 동적 메뉴 생성

#### 역할
카테고리 폴더를 검색하고 메뉴 항목을 자동 생성합니다.

#### 클래스: MenuGenerator

| 메서드 | 설명 |
|--------|------|
| `get_category_folders()` | 숫자로 시작하는 폴더 목록 반환 |
| `get_category_menu_items(category_base)` | 카테고리별 메뉴 항목 생성 |
| `get_main_menu_items()` | 메인 페이지용 메뉴 생성 |
| `generate_navbar_html(menu_items)` | 네비게이션 HTML 생성 |
| `inject_navbar_to_html(html_content, menu_items)` | HTML에 네비게이션 삽입 |

#### 메뉴 항목 생성 규칙

| 폴더 | 파일 | 메뉴 타입 | URL 패턴 |
|------|------|-----------|----------|
| markdown_docs/ | *.md | markdown | /{category}/markdown/{stem} |
| html_docs/ | *.html | html | /{category}/html/{stem} |
| routes/ | *.py | python | Blueprint 또는 동적 라우트 |

#### Blueprint vs render() 함수

| 파일 | 유형 | URL |
|------|------|-----|
| `population_routes.py` | Blueprint | /01_population/ |
| `age.py` | Blueprint | /01_population/age |
| 일반 *.py | render() 함수 | /01_population/routes/{stem} |

---

### 3.5 visualizers.py - 차트 시각화

#### 역할
6가지 공통 차트 생성 함수를 제공합니다.

#### 사용 모듈
| 모듈 | 용도 |
|------|------|
| `matplotlib.pyplot` | 차트 생성 |
| `seaborn` | 히트맵 |
| `numpy` | 수치 계산 |
| `pandas` | 데이터 처리 |
| `loguru` | 로깅 |

#### 함수 목록

| 함수 | 용도 | 주요 매개변수 |
|------|------|---------------|
| `plot_horizontal_bar()` | 수평 막대그래프 | x_col, y_col, title, filename |
| `plot_grouped_bar()` | 그룹형 막대그래프 | x_col, value_cols, labels |
| `plot_dual_axis()` | 이중축 차트 | bar_col, line_col |
| `plot_heatmap()` | 히트맵 | cmap, annot, fmt |
| `plot_pyramid()` | 인구 피라미드 | left_col, right_col, y_col |
| `plot_line()` | 선 그래프 | y_cols, labels, markers |

#### 공통 매개변수
- `data`: pandas DataFrame
- `title`: 그래프 제목
- `filename`: 저장할 파일명
- `output_dir`: 저장 디렉토리 (기본: ./output/images)
- `unit_divisor`: 단위 변환 (기본: 10000 = 만)
- `figsize`: 그래프 크기

#### 헬퍼 함수
| 함수 | 설명 |
|------|------|
| `save_figure(fig, filename)` | Figure를 이미지로 저장 후 메모리 해제 |

---

### 3.6 aggregators.py - 데이터 집계

#### 역할
groupby, merge, pivot 등 집계 함수를 제공합니다.

#### 사용 모듈
| 모듈 | 용도 |
|------|------|
| `pandas` | 데이터 집계 |

#### 함수 목록

| 함수 | 용도 | 예시 |
|------|------|------|
| `aggregate_by_group()` | 그룹별 집계 | 시도별 인구 합계 |
| `calculate_ratio()` | 비율 계산 | 1인세대 비율 |
| `convert_unit()` | 단위 변환 | 만 단위 변환 |
| `pivot_for_heatmap()` | 히트맵용 피벗 | 시도×연령대 매트릭스 |
| `merge_dataframes()` | 데이터 병합 | 인구+세대 데이터 병합 |

---

### 3.7 transforms.py - 데이터 변환

#### 역할
melt, pivot, cut 등 데이터 변환 함수를 제공합니다.

#### 함수 목록

| 함수 | 용도 | 예시 |
|------|------|------|
| `add_region()` | 권역 매핑 추가 | 시도→수도권/영남권 |
| `add_category()` | 범용 카테고리 매핑 | 연령→세대 |
| `add_age_group()` | 연령대 구간 분류 | 나이→10대/20대 |
| `wide_to_long()` | Wide→Long 변환 | male_pop/female_pop → gender+pop |
| `long_to_wide()` | Long→Wide 변환 | gender+pop → male_pop/female_pop |
| `filter_rows()` | 조건별 필터링 | 서울만 추출 |
| `rename_columns()` | 컬럼명 변경 | sido_nm→시도명 |
| `reorder_by_list()` | 지정 순서 정렬 | 시도 행정코드 순 |
| `extract_year()` | 년도 추출 | 20241115→2024 |

---

## 4. 01_population/routes/ - 인구통계 라우트

### 4.1 population_routes.py - 대시보드 Blueprint

#### 역할
인구통계 대시보드 페이지와 API를 제공합니다.

#### Blueprint 정보
```python
population_bp = Blueprint('population', __name__)
# URL prefix: /01_population
```

#### 사용 모듈
| 모듈 | 용도 |
|------|------|
| `flask` | Blueprint, render_template, request, jsonify |
| `pandas` | 데이터 처리 |
| `module.db` | DB 연결 |
| `module.menu_generator` | 메뉴 생성 |

#### 헬퍼 함수

| 함수 | 설명 |
|------|------|
| `get_filter_options()` | 기준시기, 시도 목록 조회 |
| `get_sigungu_list(sido_nm)` | 특정 시도의 시군구 목록 |
| `load_population_data()` | 기본 인구 데이터 조회 |
| `load_single_household_data()` | 1인세대 데이터 조회 |
| `aggregate_sido(df)` | 시도별 집계 |
| `aggregate_sigungu(df)` | 시군구별 집계 |
| `add_sigungu_consolidated(df)` | 시군구 통합 코드 추가 |

#### 라우트 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/` | GET | 대시보드 메인 페이지 |
| `/api/sigungu` | GET | 시군구 목록 |
| `/api/summary` | GET | 요약 통계 |
| `/api/sido_data` | GET | 시도별 데이터 |
| `/api/sigungu_data` | GET | 시군구별 데이터 |
| `/api/emd_data` | GET | 읍면동별 데이터 |
| `/api/chart/sido_pop` | GET | 시도별 인구 차트 |
| `/api/chart/single_ratio` | GET | 1인세대 비율 차트 |
| `/api/chart/gender_pie` | GET | 성별 파이차트 |
| `/api/chart/household_pie` | GET | 세대 파이차트 |
| `/api/chart/sigungu_top10` | GET | 시군구 Top10 차트 |
| `/api/save_report` | POST | 보고서 저장 |

#### 데이터베이스 테이블

| 테이블 | 설명 |
|--------|------|
| `fact_population_basic` | 기본 인구통계 (인구, 세대, 내외국인) |
| `fact_single_household` | 1인세대 데이터 |
| `dim_admin_area` | 행정구역 (시도, 시군구, 읍면동) |

---

### 4.2 age.py - 연령별 통계 Blueprint

#### 역할
연령별 인구 데이터를 조회하고 피라미드 차트를 제공합니다.

#### Blueprint 정보
```python
age_bp = Blueprint('age', __name__)
# URL prefix: /01_population
```

#### 헬퍼 함수

| 함수 | 설명 |
|------|------|
| `get_filter_options()` | 기준시기, 시도 목록 조회 |
| `load_age_population_data()` | 10세 단위 연령별 인구 조회 |

#### 라우트 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/age` | GET | 연령별 통계 페이지 |
| `/api/age_pyramid` | GET | 피라미드 차트 데이터 |
| `/api/age_table` | GET | 연령대별 테이블 |
| `/api/sigungu` | GET | 시군구 목록 (연령 페이지용) |

#### 데이터베이스 테이블

| 테이블 | 설명 |
|--------|------|
| `fact_population_by_age` | 1세별 인구 (Wide 형식, 컬럼 225개) |

---

## 5. 전체 처리 흐름도

### 5.1 페이지 요청 흐름

```
브라우저 요청
    │
    ▼
main_app.py (Flask 앱)
    │
    ├─ / (메인 페이지)
    │   └─ get_category_list() → index.html 렌더링
    │
    ├─ /01_population (카테고리 메인)
    │   ├─ MenuGenerator.get_category_menu_items()
    │   └─ category_with_navbar.html 렌더링
    │
    ├─ /01_population/ (대시보드)
    │   ├─ population_routes.py → population_bp
    │   ├─ get_filter_options()
    │   └─ population_dashboard.html 렌더링
    │
    ├─ /01_population/age (연령별 통계)
    │   ├─ age.py → age_bp
    │   ├─ get_filter_options()
    │   └─ population_age.html 렌더링
    │
    ├─ /01_population/markdown/{filename}
    │   ├─ MarkdownRenderer.render_file()
    │   └─ category_with_navbar.html 렌더링
    │
    └─ /01_population/routes/{filename}
        ├─ execute_route_module() → render() 호출
        └─ category_with_navbar.html 렌더링
```

### 5.2 API 요청 흐름

```
JavaScript (Chart.js)
    │
    ▼
API 요청 (/api/*)
    │
    ▼
population_routes.py 또는 age.py
    │
    ├─ get_db_connection() (db.py)
    │
    ├─ pd.read_sql() (SQL 실행)
    │
    ├─ 데이터 집계/변환
    │   ├─ aggregate_sido()
    │   ├─ aggregate_sigungu()
    │   └─ load_age_population_data()
    │
    └─ jsonify() → JSON 응답
```

### 5.3 차트 생성 흐름 (분석용)

```
데이터 조회
    │
    ▼
module/aggregators.py (집계)
    ├─ aggregate_by_group()
    ├─ calculate_ratio()
    └─ pivot_for_heatmap()
    │
    ▼
module/transforms.py (변환)
    ├─ add_region()
    ├─ wide_to_long()
    └─ filter_rows()
    │
    ▼
module/visualizers.py (시각화)
    ├─ plot_horizontal_bar()
    ├─ plot_grouped_bar()
    ├─ plot_heatmap()
    └─ plot_pyramid()
    │
    ▼
./output/images/*.png (이미지 저장)
```

---

## 6. render() 함수 vs Blueprint 비교

### render() 함수 방식
- **용도**: 단순한 단일 페이지
- **파일 위치**: routes/*.py
- **필수 구현**: `def render(): return "HTML 문자열"`
- **URL**: /01_population/routes/{파일명}
- **예시**: 간단한 통계 페이지, 테스트 페이지

### Blueprint 방식
- **용도**: 복잡한 다중 라우트 + API
- **파일 위치**: routes/*.py
- **필수 구현**: `Blueprint` 객체 + `@bp.route()` 데코레이터
- **URL**: main_app.py에서 등록한 prefix + 라우트
- **예시**: 대시보드, CRUD 기능, REST API

---

## 7. 사용 예시

### 7.1 DB에서 데이터 조회
```python
from module.db import get_db_connection
import pandas as pd

conn = get_db_connection()
df = pd.read_sql("SELECT * FROM fact_population_basic LIMIT 10", conn)
conn.close()
```

### 7.2 시도별 인구 집계
```python
from module.aggregators import aggregate_by_group

df_sido = aggregate_by_group(
    df,
    group_cols=['sido_nm'],
    value_cols=['total_pop', 'male_pop', 'female_pop'],
    sort_by='total_pop',
    sort_ascending=False
)
```

### 7.3 차트 생성
```python
from module.visualizers import plot_horizontal_bar

plot_horizontal_bar(
    data=df_sido,
    x_col='sido_nm',
    y_col='total_pop',
    title='시도별 인구 현황',
    filename='sido_population.png'
)
```

### 7.4 데이터 변환
```python
from module.transforms import add_region, wide_to_long

REGION_MAP = {
    '서울특별시': '수도권', '경기도': '수도권',
    '부산광역시': '영남권', '대구광역시': '영남권'
}

df = add_region(df, 'sido_nm', REGION_MAP)
df_long = wide_to_long(df, ['sido_nm'], ['male_pop', 'female_pop'], '성별', '인구')
```

---

## 8. 문서 정보

- **작성일**: 2024-12-18
- **작성자**: ljs
- **버전**: 1.0
