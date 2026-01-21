# Flask 기반 데이터 분석 대시보드 구축 가이드

## 개요

인구통계 데이터를 웹에서 분석할 수 있는 Flask 기반 대시보드 시스템 구축 문서입니다.
공통 모듈을 활용하여 다양한 분야(인구, 경제, 환경, 교통, 복지)에 재사용 가능한 구조로 설계되었습니다.

---

## 1. 프로젝트 구조

```
C:\Users\user\01_claude_project\
├── main_app.py                      # Flask 메인 앱 (신규)
├── templates/
│   └── index.html                   # 메인 페이지 템플릿
├── static/                          # 정적 파일
│
├── module/                          # 공통 모듈 (모든 카테고리 공유)
│   ├── __init__.py
│   ├── config.py                    # 상수, 색상, 크기 설정
│   ├── db.py                        # PostgreSQL DB 연결
│   ├── visualizers.py               # 시각화 함수 6종
│   ├── aggregators.py               # 집계 함수 5종
│   └── transforms.py                # 데이터 변환 함수 9종
│
└── 01_population/                   # 인구통계 카테고리
    ├── routes/
    │   ├── __init__.py
    │   └── population_routes.py     # Flask 라우트 및 API
    ├── templates/
    │   └── population_dashboard.html # 대시보드 HTML (Chart.js)
    ├── images/                      # 생성된 이미지
    ├── agent_eda.py                 # 기존 분석 코드
    └── report.md                    # 분석 보고서
```

---

## 2. 공통 모듈 (module/)

### 2.1 config.py - 설정 상수

```python
# 그래프 크기
FIGSIZE_SMALL = (8, 6)
FIGSIZE_MEDIUM = (12, 8)
FIGSIZE_LARGE = (16, 10)
FIGSIZE_WIDE = (14, 6)

# 색상
COLORS = {
    'male': '#4A90D9',      # 파란색
    'female': '#E57373',    # 빨간색
    'total': '#66BB6A',     # 초록색
    'highlight': '#FFA726', # 주황색
    'single': '#9C27B0',    # 보라색
}

# 단위
UNIT_MAN = 10000      # 만
UNIT_CHEON = 1000     # 천
```

### 2.2 db.py - 데이터베이스 연결

```python
from module.db import get_db_connection

conn = get_db_connection()
df = pd.read_sql("SELECT * FROM table", conn)
conn.close()
```

### 2.3 visualizers.py - 시각화 함수 (6종)

| 함수 | 용도 |
|------|------|
| `plot_horizontal_bar()` | 수평 막대그래프 |
| `plot_grouped_bar()` | 그룹형 수직 막대그래프 |
| `plot_dual_axis()` | 이중축 차트 (막대+선) |
| `plot_heatmap()` | 히트맵 |
| `plot_pyramid()` | 인구 피라미드 |
| `plot_line()` | 선 그래프 |

### 2.4 aggregators.py - 집계 함수 (5종)

| 함수 | 용도 |
|------|------|
| `aggregate_by_group()` | 그룹별 집계 (groupby + agg) |
| `calculate_ratio()` | 비율 계산 (분자/분모*100) |
| `convert_unit()` | 단위 변환 (/10000 등) |
| `pivot_for_heatmap()` | 히트맵용 피벗 테이블 |
| `merge_dataframes()` | 데이터프레임 병합 |

### 2.5 transforms.py - 데이터 변환 함수 (9종)

| 함수 | 용도 |
|------|------|
| `add_region()` | 시도별 권역 추가 |
| `add_category()` | 범용 카테고리 매핑 |
| `add_age_group()` | 연령 그룹 추가 |
| `wide_to_long()` | Wide → Long 변환 |
| `long_to_wide()` | Long → Wide 변환 |
| `filter_rows()` | 조건별 필터링 |
| `rename_columns()` | 컬럼명 변경 |
| `reorder_by_list()` | 지정 순서로 정렬 |
| `extract_year()` | 날짜에서 년도 추출 |

---

## 3. Flask 메인 앱 (main_app.py)

### 3.1 핵심 코드

```python
from flask import Flask, render_template
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

def create_app():
    app = Flask(__name__,
                template_folder=str(BASE_DIR / 'templates'),
                static_folder=str(BASE_DIR / 'static'))

    app.config['SECRET_KEY'] = 'data_analysis_dashboard_2024'

    @app.route("/")
    def index():
        categories = get_category_list()
        return render_template("index.html", categories=categories)

    # 카테고리 라우트 등록
    register_population_routes(app)

    return app

def register_population_routes(app):
    """01_population 인구통계 라우트 등록"""
    pop_base = BASE_DIR / "01_population"
    sys.path.insert(0, str(pop_base))
    sys.path.insert(0, str(pop_base / "routes"))

    from routes.population_routes import population_bp
    app.register_blueprint(population_bp, url_prefix="/01_population")
```

### 3.2 실행 방법

```bash
cd C:\Users\user\01_claude_project
python main_app.py
```

- 메인 페이지: http://localhost:5000
- 인구통계: http://localhost:5000/01_population

---

## 4. 인구통계 라우트 (population_routes.py)

### 4.1 Blueprint 구조

```python
from flask import Blueprint, render_template, request, jsonify

population_bp = Blueprint('population', __name__,
                          template_folder='../templates',
                          static_folder='../images')
```

### 4.2 API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/` | GET | 메인 대시보드 페이지 |
| `/api/sigungu` | GET | 시군구 목록 조회 |
| `/api/summary` | GET | 요약 통계 |
| `/api/sido_data` | GET | 시도별 데이터 |
| `/api/sigungu_data` | GET | 시군구별 데이터 |
| `/api/emd_data` | GET | 읍면동별 데이터 |
| `/api/chart/sido_pop` | GET | 시도별 인구 차트 |
| `/api/chart/single_ratio` | GET | 1인세대 비율 차트 |
| `/api/chart/gender_pie` | GET | 성별 파이 차트 |
| `/api/chart/household_pie` | GET | 세대 구성 파이 차트 |
| `/api/chart/sigungu_top10` | GET | Top 10 시군구 차트 |

### 4.3 필터 파라미터

모든 API는 다음 필터 파라미터를 지원합니다:

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| `base_ym` | 기준 연월 | `202411` |
| `sido` | 시도명 | `경상북도` |
| `sigungu` | 시군구명 | `포항시` |

---

## 5. 대시보드 HTML (population_dashboard.html)

### 5.1 주요 기능

- **필터**: 기준시기, 시도, 시군구 선택
- **요약카드**: 총인구, 남/여, 세대수, 1인세대 비율, 성비
- **차트 5종**: Chart.js 기반 인터랙티브 차트
- **테이블 3종**: 시도별, 시군구별, 읍면동별 (스크롤)

### 5.2 차트 목록

| 차트명 | 유형 | 설명 |
|--------|------|------|
| 시도별 남녀 인구 | 스택 바 | 17개 시도 남/여 비교 |
| 시도별 1인세대 비율 | 수평 바 | 비율 높은 순 |
| 인구 Top 10 시군구 | 수평 바 | 인구 상위 10개 |
| 성별 인구 구성 | 도넛 | 남/여 비율 |
| 세대 구성 | 도넛 | 1인/다인 세대 |

### 5.3 사용된 라이브러리

```html
<!-- Bootstrap 5 -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">

<!-- Chart.js 4 -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
```

### 5.4 차트 생성 함수

```javascript
function createOrUpdateChart(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    if (charts[canvasId]) {
        charts[canvasId].destroy();
    }

    charts[canvasId] = new Chart(ctx, {
        type: type,
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            ...options
        }
    });
}
```

---

## 6. 새 카테고리 추가 방법

### 6.1 폴더 구조 생성

```
02_economy/
├── routes/
│   ├── __init__.py
│   └── economy_routes.py
├── templates/
│   └── economy_dashboard.html
└── images/
```

### 6.2 main_app.py에 라우트 등록

```python
def register_economy_routes(app):
    eco_base = BASE_DIR / "02_economy"
    sys.path.insert(0, str(eco_base))
    sys.path.insert(0, str(eco_base / "routes"))

    from routes.economy_routes import economy_bp
    app.register_blueprint(economy_bp, url_prefix="/02_economy")
```

### 6.3 create_app()에 추가

```python
def create_app():
    # ... 기존 코드 ...
    register_population_routes(app)
    register_economy_routes(app)  # 추가
    return app
```

---

## 7. 데이터베이스 테이블 구조

### 7.1 인구 기본 (fact_population_basic)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| base_ym | VARCHAR | 기준연월 (202411) |
| admin_code | VARCHAR | 행정동코드 |
| total_pop | INTEGER | 총인구 |
| male_pop | INTEGER | 남자인구 |
| female_pop | INTEGER | 여자인구 |
| household_cnt | INTEGER | 세대수 |

### 7.2 1인세대 (fact_single_household)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| base_ym | VARCHAR | 기준연월 |
| admin_code | VARCHAR | 행정동코드 |
| household_cnt | INTEGER | 1인세대수 |

### 7.3 행정구역 (dim_admin_area)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| admin_code | VARCHAR | 행정동코드 (PK) |
| sido_nm | VARCHAR | 시도명 |
| sigungu_nm | VARCHAR | 시군구명 |
| admin_nm | VARCHAR | 읍면동명 |

---

## 8. 환경 설정

### 8.1 .env 파일

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=population
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

### 8.2 필요 패키지

```bash
uv pip install flask pandas psycopg2-binary python-dotenv loguru
uv pip install matplotlib seaborn koreanize-matplotlib
```

---

## 9. 파일 위치 요약

| 파일 | 경로 |
|------|------|
| Flask 메인 앱 | `C:\Users\user\01_claude_project\main_app.py` |
| 공통 모듈 | `C:\Users\user\01_claude_project\module\` |
| 인구통계 라우트 | `C:\Users\user\01_claude_project\01_population\routes\population_routes.py` |
| 대시보드 HTML | `C:\Users\user\01_claude_project\01_population\templates\population_dashboard.html` |
| 기존 분석 코드 | `C:\Users\user\01_claude_project\01_population\agent_eda.py` |

---

## 10. 실행 및 접속

```bash
# 실행
cd C:\Users\user\01_claude_project
python main_app.py

# 접속
# 메인: http://localhost:5000
# 인구통계: http://localhost:5000/01_population
```

---

## 11. 화면 구성

```
┌─────────────────────────────────────────────────────────────┐
│  인구통계 분석 대시보드                           [홈으로]  │
├─────────────────────────────────────────────────────────────┤
│  기준시기 [▼]   시도 [▼]   시군구 [▼]   [조회]              │
├─────────────────────────────────────────────────────────────┤
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐   │
│  │총인구│ │남자│ │여자│ │세대│ │1인 │ │비율│ │성비│ │구역│   │
│  │5148│ │2567│ │2581│ │2340│ │987 │ │42.2│ │99.5│ │3838│   │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘   │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │ 시도별 남녀 인구     │  │ 시도별 1인세대 비율  │        │
│  │ [스택 바 차트]       │  │ [수평 바 차트]       │        │
│  └──────────────────────┘  └──────────────────────┘        │
│  ┌──────────────────────┐  ┌──────────┬──────────┐        │
│  │ Top 10 시군구        │  │ 성별구성 │ 세대구성 │        │
│  │ [수평 바 차트]       │  │ [도넛]   │ [도넛]   │        │
│  └──────────────────────┘  └──────────┴──────────┘        │
├─────────────────────────────────────────────────────────────┤
│  [시도별] [시군구별] [읍면동별]                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 시도    │총인구(만)│ 남자  │ 여자  │세대수│1인세대│비율│   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ 경기도  │ 1,390   │ ...   │ ...   │ ...  │ ...  │... │   │
│  │ 서울시  │  941    │ ...   │ ...   │ ...  │ ...  │... │   │
│  │ ...     │ ...     │ ...   │ ...   │ ...  │ ...  │... │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

*작성일: 2024-12-18*
*작성자: Claude AI Agent*
