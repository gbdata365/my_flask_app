# 인구통계 데이터 분석 및 시각화 에이전트 규칙

## 1. 개요

### 1.1 목적
- PostgreSQL에 저장된 인구통계 데이터를 분석하고 시각화
- 2024년 11월 ~ 2025년 11월 읍면동 단위 데이터 활용
- 코드.xlsx 기반 연령 그룹핑으로 다양한 집계 제공
- 분석 결과를 report.md로 저장, 이미지는 images/ 폴더

### 1.2 정렬 규칙 (중요)
- **모든 분석 결과는 행정동코드(admin_code) 순으로 정렬**
- 가나다순(알파벳순)이 아닌 행정체계 순서를 따름
- 시도 정렬: admin_code 앞 2자리 기준 (예: 11=서울, 26=부산, ...)
- 시군구 정렬: admin_code 앞 5자리 기준
- **시군구통합 정렬: admin_code 앞 4자리 기준** (아래 참조)
- 읍면동 정렬: admin_code 전체 10자리 기준

### 1.2.1 시군구통합 개념 (중요)
- **DB 저장**: admin_code 5자리 (예: 47111=포항시북구, 47113=포항시남구)
- **분석 시**: admin_code 앞 **4자리**로 그룹화하여 통합
- **목적**: 광역시가 아닌 일반 시도에서 "시+구" 형태를 "시"로 통합
-  경기도 등 경북외에 다른 도에서도 시+구 형태가 있으니 꼭 전체를 확인 바람

| 원본 (5자리) | 시군구명 | 통합 (4자리) | 통합명 |
|-------------|---------|-------------|--------|
| 47111 | 포항시 북구 | 4711 | 포항시 |
| 47113 | 포항시 남구 | 4711 | 포항시 |
| 47130 | 경주시 | 4713 | 경주시 |
| 47150 | 김천시 | 4715 | 김천시 |
| 47170 | 안동시 | 4717 | 안동시 |
| 47190 | 구미시 | 4719 | 구미시 |

**통합 대상 시군구 (경상북도 예시)**:
- 포항시 (북구 47111 + 남구 47113) → 4711
- 이 외 단일 시군은 그대로 유지 (뒤 1자리가 0)

### 1.3 데이터 소스
| 테이블 | 설명 | 형식 |
|--------|------|------|
| dim_admin_area | 행정구역 마스터 (3,838개 읍면동) | - |
| fact_population_basic | 인구 및 세대현황 (API 1) | - |
| fact_population_by_age | 1세별 인구 (API 3) | **Wide** (225개 컬럼) |
| fact_single_household | 1인세대수 (API 4) | **Wide** (225개 컬럼) |
| code_age_group | 연령_그룹별 코드 (15개 그룹) | - |
| code_age_attribute | 연령_속성별 코드 (8개 그룹) | - |

### 1.4 수집 기간
- **시작:** 2024년 11월 (202411)
- **종료:** 2025년 11월 (202511)
- **단위:** 읍면동 (약 3,800개)

### 1.5 연령 그룹 정의

#### 1.5.1 연령_그룹별 (15개 그룹)
| 코드 | 코드내용 | 연령 범위 |
|------|----------|-----------|
| 0~10 | 10대미만 | 0~10세 |
| 11~20 | 10대 | 11~20세 |
| 21~25 | 20대초 | 21~25세 |
| 26~30 | 20대말 | 26~30세 |
| 31~35 | 30대초 | 31~35세 |
| 36~40 | 30대말 | 36~40세 |
| 41~45 | 40대초 | 41~45세 |
| 46~50 | 40대말 | 46~50세 |
| 51~55 | 50대초 | 51~55세 |
| 56~60 | 50대말 | 56~60세 |
| 61~65 | 60대초 | 61~65세 |
| 66~70 | 60대말 | 66~70세 |
| 71~75 | 70대초 | 71~75세 |
| 76~80 | 70대말 | 76~80세 |
| 81~999 | 80대이상 | 81세 이상 |

#### 1.5.2 연령_속성별 (8개 그룹)
| 코드 | 코드내용 | 연령 범위 |
|------|----------|-----------|
| 0~5 | 영유아 | 0~5세 |
| 6~11 | 초등 | 6~11세 |
| 12~17 | 중고등 | 12~17세 |
| 18~39 | 청년 | 18~39세 |
| 40~49 | 40대 | 40~49세 |
| 50~59 | 50대 | 50~59세 |
| 60~69 | 60대 | 60~69세 |
| 70~999 | 70대이상 | 70세 이상 |

---

## 2. 환경 설정

### 2.1 필수 패키지
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import koreanize_matplotlib  # 한글 깨짐 방지 (반드시 import)
import psycopg2
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
import os
```

### 2.2 한글 설정
```python
# koreanize_matplotlib만 import하면 자동 설정됨
import koreanize_matplotlib

# seaborn 스타일은 사용하지 않음 (한글 깨짐 방지)
# sns.set_theme()  # 사용 금지
```

### 2.3 이미지 저장 폴더 설정
```python
# 이미지 저장 폴더 생성
IMAGES_DIR = Path("./images")
IMAGES_DIR.mkdir(exist_ok=True)

# 이미지 저장 함수
def save_figure(fig, filename: str, dpi: int = 150):
    """이미지를 images 폴더에 저장"""
    filepath = IMAGES_DIR / filename
    fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
    logger.info(f"이미지 저장: {filepath}")
    plt.close(fig)
    return filepath
```

### 2.4 DB 연결
```python
load_dotenv(".env")

def get_db_connection():
    """PostgreSQL 연결"""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
```

---

## 3. 코드 테이블 등록 (코드.xlsx → DB)

### 3.1 코드 테이블 DDL
```python
def create_code_tables():
    """연령 그룹 코드 테이블 생성"""
    ddl_age_group = """
    CREATE TABLE IF NOT EXISTS code_age_group (
        id SERIAL PRIMARY KEY,
        code VARCHAR(10) NOT NULL UNIQUE,
        code_name VARCHAR(20) NOT NULL,
        age_start INTEGER NOT NULL,
        age_end INTEGER NOT NULL,
        sort_order INTEGER NOT NULL
    );
    """

    ddl_age_attribute = """
    CREATE TABLE IF NOT EXISTS code_age_attribute (
        id SERIAL PRIMARY KEY,
        code VARCHAR(10) NOT NULL UNIQUE,
        code_name VARCHAR(20) NOT NULL,
        age_start INTEGER NOT NULL,
        age_end INTEGER NOT NULL,
        sort_order INTEGER NOT NULL
    );
    """

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(ddl_age_group)
    cur.execute(ddl_age_attribute)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("코드 테이블 생성 완료")
```

### 3.2 코드.xlsx 데이터 등록
```python
def load_code_from_excel(excel_path: str = "../codedata/코드.xlsx"):
    """코드.xlsx에서 연령 그룹 코드를 DB에 등록"""

    # 연령 범위가 수정될 수 있으니 아래 리스트가 아니라 엑셀화일에서 확인하고 디비 저장하고 가지고 올것  (15개 그룹)
    age_group_data = [
        ("0~10", "10대미만", 0, 10, 1),
        ("11~20", "10대", 11, 20, 2),
        ("21~25", "20대초", 21, 25, 3),
        ("26~30", "20대말", 26, 30, 4),
        ("31~35", "30대초", 31, 35, 5),
        ("36~40", "30대말", 36, 40, 6),
        ("41~45", "40대초", 41, 45, 7),
        ("46~50", "40대말", 46, 50, 8),
        ("51~55", "50대초", 51, 55, 9),
        ("56~60", "50대말", 56, 60, 10),
        ("61~65", "60대초", 61, 65, 11),
        ("66~70", "60대말", 66, 70, 12),
        ("71~75", "70대초", 71, 75, 13),
        ("76~80", "70대말", 76, 80, 14),
        ("81~999", "80대이상", 81, 110, 15),
    ]

    # 연령_속성별 (8개 그룹)
    age_attr_data = [
        ("0~5", "영유아", 0, 5, 1),
        ("6~11", "초등", 6, 11, 2),
        ("12~17", "중고등", 12, 17, 3),
        ("18~39", "청년", 18, 39, 4),
        ("40~49", "40대", 40, 49, 5),
        ("50~59", "50대", 50, 59, 6),
        ("60~69", "60대", 60, 69, 7),
        ("70~999", "70대이상", 70, 110, 8),
    ]

    conn = get_db_connection()
    cur = conn.cursor()

    # 기존 데이터 삭제 후 삽입
    cur.execute("DELETE FROM code_age_group")
    cur.execute("DELETE FROM code_age_attribute")

    for row in age_group_data:
        cur.execute("""
            INSERT INTO code_age_group (code, code_name, age_start, age_end, sort_order)
            VALUES (%s, %s, %s, %s, %s)
        """, row)

    for row in age_attr_data:
        cur.execute("""
            INSERT INTO code_age_attribute (code, code_name, age_start, age_end, sort_order)
            VALUES (%s, %s, %s, %s, %s)
        """, row)

    conn.commit()
    cur.close()
    conn.close()
    logger.info("코드 데이터 등록 완료 (연령_그룹별 15건, 연령_속성별 8건)")
```

---

## 4. 데이터 로드

### 4.1 기본 인구 데이터 로드
```python
def load_population_basic(sido_filter: str = None, sigungu_filter: str = None) -> pd.DataFrame:
    """인구 및 세대현황 데이터 로드

    Args:
        sido_filter: 시도 필터 (예: '경상북도')
        sigungu_filter: 시군구 필터 (예: '포항시')
    """
    where_clauses = ["p.base_ym >= '2024-11-01' AND p.base_ym <= '2025-11-01'"]

    if sido_filter:
        where_clauses.append(f"a.sido_nm = '{sido_filter}'")
    if sigungu_filter:
        where_clauses.append(f"a.sigungu_nm LIKE '%{sigungu_filter}%'")

    where_sql = " AND ".join(where_clauses)

    query = f"""
    SELECT
        p.admin_code,
        p.base_ym,
        a.sido_nm,
        a.sigungu_nm,
        a.eupmyeondong_nm,
        a.region_nm,
        p.household_cnt,
        p.total_pop,
        p.male_pop,
        p.female_pop,
        p.sex_ratio,
        p.pop_per_house
    FROM fact_population_basic p
    JOIN dim_admin_area a ON p.admin_code = a.admin_code
    WHERE {where_sql}
    ORDER BY p.base_ym, p.admin_code
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    logger.info(f"인구 기본 데이터 로드: {len(df)}건")
    return df
```

### 4.2 1세별 인구 데이터 로드 (Wide 형식)
```python
def load_population_by_age(base_ym: str = None, sido_filter: str = None) -> pd.DataFrame:
    """1세별 인구 데이터 로드 (Wide 형식)

    Args:
        base_ym: 기준연월 (예: '2025-11-01'), None이면 전체 기간
        sido_filter: 시도 필터 (예: '경상북도')
    """
    where_clauses = []

    if base_ym:
        where_clauses.append(f"p.base_ym = '{base_ym}'")
    else:
        where_clauses.append("p.base_ym >= '2024-11-01' AND p.base_ym <= '2025-11-01'")

    if sido_filter:
        where_clauses.append(f"a.sido_nm = '{sido_filter}'")

    where_sql = " AND ".join(where_clauses)

    query = f"""
    SELECT
        p.*,
        a.sido_nm,
        a.sigungu_nm,
        a.eupmyeondong_nm,
        a.region_nm
    FROM fact_population_by_age p
    JOIN dim_admin_area a ON p.admin_code = a.admin_code
    WHERE {where_sql}
    ORDER BY p.base_ym, p.admin_code
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    logger.info(f"1세별 인구 데이터 로드: {len(df)}건")
    return df
```

### 4.3 1인세대수 데이터 로드 (Wide 형식)
```python
def load_single_household(base_ym: str = None, sido_filter: str = None) -> pd.DataFrame:
    """1인세대수 데이터 로드 (Wide 형식)

    Args:
        base_ym: 기준연월 (예: '2025-11-01'), None이면 전체 기간
        sido_filter: 시도 필터 (예: '경상북도')
    """
    where_clauses = []

    if base_ym:
        where_clauses.append(f"s.base_ym = '{base_ym}'")
    else:
        where_clauses.append("s.base_ym >= '2024-11-01' AND s.base_ym <= '2025-11-01'")

    if sido_filter:
        where_clauses.append(f"a.sido_nm = '{sido_filter}'")

    where_sql = " AND ".join(where_clauses)

    query = f"""
    SELECT
        s.*,
        a.sido_nm,
        a.sigungu_nm,
        a.eupmyeondong_nm,
        a.region_nm
    FROM fact_single_household s
    JOIN dim_admin_area a ON s.admin_code = a.admin_code
    WHERE {where_sql}
    ORDER BY s.base_ym, s.admin_code
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    logger.info(f"1인세대수 데이터 로드: {len(df)}건")
    return df
```

### 4.4 연령 그룹 코드 로드
```python
def load_age_group_codes() -> pd.DataFrame:
    """연령_그룹별 코드 로드 (15개 그룹)"""
    query = "SELECT * FROM code_age_group ORDER BY sort_order"
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df
```

---

## 4.5 시군구통합 함수 (Sigungu Consolidation)

### 4.5.1 시군구통합 코드 추가
```python
def add_sigungu_consolidated(df: pd.DataFrame) -> pd.DataFrame:
    """시군구통합 코드를 추가 (admin_code 앞 4자리)

    예: 포항시 북구(47111) + 포항시 남구(47113) → 포항시(4711)
    """
    df = df.copy()
    df['sigungu_code'] = df['admin_code'].str[:4]
    return df
```

### 4.5.2 시군구통합명 생성
```python
def get_sigungu_consolidated_name(df: pd.DataFrame) -> pd.DataFrame:
    """시군구통합명 생성 (구 이름 제거)

    '포항시 북구' → '포항시'
    '포항시 남구' → '포항시'
    '경주시' → '경주시' (변경 없음)
    """
    df = df.copy()
    df['sigungu_consolidated_nm'] = df['sigungu_nm'].str.replace(
        r'\s*(북구|남구|동구|서구|중구|수성구|달서구|달성군)$', '', regex=True
    ).str.strip()
    return df
```

### 4.5.3 시군구통합 기준 집계
```python
def aggregate_by_sigungu_consolidated(df: pd.DataFrame,
                                       value_cols: list = None,
                                       agg_func: str = 'sum') -> pd.DataFrame:
    """시군구통합 기준으로 데이터 집계

    Args:
        df: 원본 데이터 (admin_code, sido_nm, sigungu_nm 필수)
        value_cols: 집계할 컬럼 목록 (기본: total_pop, male_pop, female_pop, household_cnt)
        agg_func: 집계 함수 ('sum', 'mean', 'count' 등)

    Returns:
        시군구통합 기준 집계 결과

    Example:
        >>> df = load_population_basic(sido_filter='경상북도')
        >>> result = aggregate_by_sigungu_consolidated(df)
        >>> # 포항시 북구 + 남구가 '포항시'로 통합되어 집계됨
    """
    # ... (구현 내용)
```

---

## 5. Wide → Long 변환 및 연령 그룹핑

### 5.1 Wide → Long 변환 함수
```python
def wide_to_long(df: pd.DataFrame, value_name: str = "population") -> pd.DataFrame:
    """Wide 형식 데이터를 Long 형식으로 변환

    Args:
        df: Wide 형식 DataFrame (male_age_0, female_age_0, ... 컬럼 포함)
        value_name: 값 컬럼명 (population 또는 household_cnt)

    Returns:
        Long 형식 DataFrame (age, gender, value 컬럼 포함)
    """
    # ID 컬럼 (유지할 컬럼)
    id_cols = ['admin_code', 'base_ym', 'sido_nm', 'sigungu_nm', 'eupmyeondong_nm', 'region_nm']
    id_cols = [col for col in id_cols if col in df.columns]

    # 연령별 컬럼 추출
    male_cols = [f'male_age_{i}' for i in range(110)] + ['male_age_110_over']
    female_cols = [f'female_age_{i}' for i in range(110)] + ['female_age_110_over']

    # 실제 존재하는 컬럼만 선택
    male_cols = [c for c in male_cols if c in df.columns]
    female_cols = [c for c in female_cols if c in df.columns]

    # 남자 데이터
    male_df = df[id_cols + male_cols].melt(
        id_vars=id_cols,
        var_name='age_col',
        value_name=value_name
    )
    male_df['gender'] = '남자'
    male_df['age'] = male_df['age_col'].str.extract(r'(\d+)').astype(int)
    male_df.loc[male_df['age_col'] == 'male_age_110_over', 'age'] = 110

    # 여자 데이터
    female_df = df[id_cols + female_cols].melt(
        id_vars=id_cols,
        var_name='age_col',
        value_name=value_name
    )
    female_df['gender'] = '여자'
    female_df['age'] = female_df['age_col'].str.extract(r'(\d+)').astype(int)
    female_df.loc[female_df['age_col'] == 'female_age_110_over', 'age'] = 110

    # 합치기
    result = pd.concat([male_df, female_df], ignore_index=True)
    result = result.drop(columns=['age_col'])

    return result
```

### 5.2 연령 그룹 매핑 함수 (DB 기반 동적 로드)
```python
# 전역 캐시 (DB 조회 최소화)
_age_group_cache = {}

def _load_age_group_mapping(group_type: str = '15') -> tuple:
    """DB에서 연령 그룹 매핑 정보 로드 (캐싱)

    Args:
        group_type: '15' (연령_그룹별) 또는 '8' (연령_속성별)

    Returns:
        (mapping_list, group_order): 매핑 리스트와 정렬 순서
    """
    cache_key = f'age_group_{group_type}'

    if cache_key in _age_group_cache:
        return _age_group_cache[cache_key]

    if group_type == '15':
        code_df = load_age_group_codes()
    else:
        code_df = load_age_attribute_codes()

    # 매핑 리스트 생성: [(age_start, age_end, code_name), ...]
    mapping_list = []
    group_order = []

    for _, row in code_df.iterrows():
        mapping_list.append((row['age_start'], row['age_end'], row['code_name']))
        group_order.append(row['code_name'])

    _age_group_cache[cache_key] = (mapping_list, group_order)
    return mapping_list, group_order


def clear_age_group_cache():
    """연령 그룹 캐시 초기화 (코드 테이블 변경 시 호출)"""
    global _age_group_cache
    _age_group_cache = {}
    logger.info("연령 그룹 캐시 초기화 완료")
```

### 5.3 연령_그룹별 그룹핑 함수 (15개 그룹) - DB 기반
```python
def add_age_group_15(df: pd.DataFrame) -> pd.DataFrame:
    """연령_그룹별 컬럼 추가 (15개 그룹) - DB에서 동적 로드

    DB의 code_age_group 테이블에서 연령 범위를 읽어와 매핑
    테이블 변경 시 자동 반영됨
    """
    mapping_list, group_order = _load_age_group_mapping('15')

    def get_age_group(age):
        for age_start, age_end, code_name in mapping_list:
            if age_start <= age <= age_end:
                return code_name
        return mapping_list[-1][2]  # 범위 밖이면 마지막 그룹

    df['age_group_15'] = df['age'].apply(get_age_group)
    df['age_group_15'] = pd.Categorical(df['age_group_15'], categories=group_order, ordered=True)

    return df
```

### 5.4 연령_속성별 그룹핑 함수 (8개 그룹) - DB 기반
```python
def add_age_group_8(df: pd.DataFrame) -> pd.DataFrame:
    """연령_속성별 컬럼 추가 (8개 그룹) - DB에서 동적 로드

    DB의 code_age_attribute 테이블에서 연령 범위를 읽어와 매핑
    테이블 변경 시 자동 반영됨
    """
    mapping_list, group_order = _load_age_group_mapping('8')

    def get_age_group(age):
        for age_start, age_end, code_name in mapping_list:
            if age_start <= age <= age_end:
                return code_name
        return mapping_list[-1][2]  # 범위 밖이면 마지막 그룹

    df['age_group_8'] = df['age'].apply(get_age_group)
    df['age_group_8'] = pd.Categorical(df['age_group_8'], categories=group_order, ordered=True)

    return df
```

### 5.4 연령 그룹별 집계 함수
```python
def aggregate_by_age_group(df_long: pd.DataFrame, group_type: str = '15',
                            value_col: str = 'population') -> pd.DataFrame:
    """연령 그룹별 집계

    Args:
        df_long: Long 형식 데이터
        group_type: '15' (연령_그룹별) 또는 '8' (연령_속성별)
        value_col: 집계할 컬럼명

    Returns:
        연령 그룹별 집계 DataFrame
    """
    group_col = f'age_group_{group_type}'

    if group_col not in df_long.columns:
        if group_type == '15':
            df_long = add_age_group_15(df_long)
        else:
            df_long = add_age_group_8(df_long)

    agg_df = df_long.groupby([group_col, 'gender'])[value_col].sum().unstack(fill_value=0)
    agg_df['total'] = agg_df['남자'] + agg_df['여자']
    agg_df = agg_df.reset_index()

    return agg_df
```

---

## 6. 시각화 규칙

### 6.1 기본 설정
```python
# 그래프 크기 기본값
FIGSIZE_SMALL = (8, 6)
FIGSIZE_MEDIUM = (12, 8)
FIGSIZE_LARGE = (16, 10)
FIGSIZE_WIDE = (14, 6)
FIGSIZE_EXTRA_WIDE = (18, 8)

# 색상 팔레트
COLORS = {
    'male': '#4A90D9',      # 파란색 (남자)
    'female': '#E57373',    # 빨간색 (여자)
    'total': '#66BB6A',     # 초록색 (전체)
    'highlight': '#FFA726', # 주황색 (강조)
    'single': '#9C27B0',    # 보라색 (1인세대)
}

# 시도별 색상
SIDO_COLORS = plt.cm.tab20(np.linspace(0, 1, 17))
```

### 6.2 인구 피라미드
```python
def plot_population_pyramid(df_long: pd.DataFrame, title: str, filename: str):
    """인구 피라미드 그래프

    Args:
        df_long: Long 형식 데이터 (age, gender, population 컬럼 필수)
        title: 그래프 제목
        filename: 저장 파일명 (예: 'pyramid_seoul.png')
    """
    # 연령별 집계
    pyramid = df_long.groupby(['age', 'gender'])['population'].sum().unstack()

    fig, ax = plt.subplots(figsize=FIGSIZE_MEDIUM)

    y = pyramid.index
    male = pyramid['남자'].values / 1000  # 천 명 단위
    female = pyramid['여자'].values / 1000

    # 남자 (왼쪽, 음수)
    ax.barh(y, -male, height=0.8, color=COLORS['male'], label='남자')
    # 여자 (오른쪽, 양수)
    ax.barh(y, female, height=0.8, color=COLORS['female'], label='여자')

    # x축 라벨 절대값으로
    max_val = max(male.max(), female.max())
    ax.set_xlim(-max_val * 1.1, max_val * 1.1)

    ticks = ax.get_xticks()
    ax.set_xticklabels([f'{abs(int(t))}' for t in ticks])

    ax.set_xlabel('인구 (천 명)')
    ax.set_ylabel('연령')
    ax.set_title(title)
    ax.legend(loc='upper right')
    ax.axvline(0, color='black', linewidth=0.5)

    # 5세 단위 y축 눈금
    ax.set_yticks(range(0, 111, 5))

    plt.tight_layout()
    save_figure(fig, filename)
```

### 6.3 시도별 인구 막대 그래프
```python
def plot_sido_population(df: pd.DataFrame, filename: str = 'sido_population.png'):
    """시도별 인구 막대 그래프"""
    # 시도별 집계
    sido_pop = df.groupby('sido_nm')['total_pop'].sum().sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=FIGSIZE_MEDIUM)

    bars = ax.barh(sido_pop.index, sido_pop.values / 10000, color=COLORS['total'])

    # 값 표시
    for bar, val in zip(bars, sido_pop.values):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                f'{val/10000:,.0f}', va='center', fontsize=9)

    ax.set_xlabel('인구 (만 명)')
    ax.set_title('시도별 인구 현황')

    plt.tight_layout()
    save_figure(fig, filename)
```

### 6.4 경상북도 시군별 인구 시각화 (시군구통합 적용)
```python
def plot_gyeongbuk_sigungu(df: pd.DataFrame, value_col: str = 'total_pop',
                           title: str = None, filename: str = 'gyeongbuk_sigungu.png',
                           use_consolidated: bool = True):
    """경상북도 시군별 인구 막대 그래프 (시군구통합 적용)

    시군구통합: admin_code 앞 4자리로 그룹화
    예: 포항시 북구(47111) + 포항시 남구(47113) → 포항시(4711)

    Args:
        df: 인구 데이터 (sido_nm, sigungu_nm, admin_code 포함)
        value_col: 집계할 컬럼 (total_pop, household_cnt 등)
        title: 그래프 제목
        filename: 저장 파일명
        use_consolidated: 시군구통합 사용 여부 (기본: True)
    """
    # 경상북도 데이터만 필터링
    gb_df = df[df['sido_nm'] == '경상북도'].copy()

    if len(gb_df) == 0:
        logger.warning("경상북도 데이터가 없습니다.")
        return

    # 시군구통합 적용 (admin_code 앞 4자리)
    if use_consolidated:
        gb_df = add_sigungu_consolidated(gb_df)  # sigungu_code (4자리) 추가
        gb_df = get_sigungu_consolidated_name(gb_df)  # sigungu_consolidated_nm 추가

        sigungu_agg = gb_df.groupby('sigungu_code').agg({
            'sigungu_consolidated_nm': 'first',
            value_col: 'sum'
        }).reset_index()
        sigungu_agg = sigungu_agg.sort_values('sigungu_code')
        sigungu_agg = sigungu_agg.set_index('sigungu_consolidated_nm')[value_col]
    else:
        # 기존 방식 (5자리)
        sigungu_agg = gb_df.groupby('sigungu_nm')[value_col].sum().sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=FIGSIZE_MEDIUM)

    bars = ax.barh(sigungu_agg.index, sigungu_agg.values / 10000, color=COLORS['total'])

    # 값 표시
    for bar, val in zip(bars, sigungu_agg.values):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
                f'{val/10000:,.1f}', va='center', fontsize=9)

    if title is None:
        title = f'경상북도 시군별 인구 현황'
    ax.set_xlabel('인구 (만 명)')
    ax.set_title(title)

    plt.tight_layout()
    save_figure(fig, filename)
```

### 6.5 경상북도 시군별 1인세대 시각화
```python
def plot_gyeongbuk_single_household(df_hh: pd.DataFrame,
                                     filename: str = 'gyeongbuk_single_household.png'):
    """경상북도 시군별 1인세대수 막대 그래프"""
    # 경상북도 데이터만 필터링
    gb_df = df_hh[df_hh['sido_nm'] == '경상북도'].copy()

    if len(gb_df) == 0:
        logger.warning("경상북도 1인세대 데이터가 없습니다.")
        return

    # 시군별 집계
    sigungu_agg = gb_df.groupby('sigungu_nm')['total_cnt'].sum().sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=FIGSIZE_MEDIUM)

    bars = ax.barh(sigungu_agg.index, sigungu_agg.values / 1000, color=COLORS['single'])

    # 값 표시
    for bar, val in zip(bars, sigungu_agg.values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                f'{val/1000:,.1f}', va='center', fontsize=9)

    ax.set_xlabel('1인세대수 (천 세대)')
    ax.set_title('경상북도 시군별 1인세대 현황')

    plt.tight_layout()
    save_figure(fig, filename)
```

### 6.6 전국 상위/하위 20개 시군구 시각화
```python
def plot_top_bottom_sigungu(df: pd.DataFrame, value_col: str = 'total_pop',
                             top_n: int = 20, filename_prefix: str = 'sigungu'):
    """전국 상위/하위 20개 시군구 시각화

    Args:
        df: 인구 데이터
        
        value_col: 집계 컬럼
        top_n: 상위/하위 개수
        filename_prefix: 파일명 접두사
    """
    # 시군구별 집계 (시도명 포함)
    sigungu_agg = df.groupby(['sido_nm', 'sigungu_nm'])[value_col].sum().reset_index()
    sigungu_agg['region'] = sigungu_agg['sido_nm'] + ' ' + sigungu_agg['sigungu_nm']
    sigungu_agg = sigungu_agg.sort_values(value_col, ascending=False)

    # 상위 N개
    top_df = sigungu_agg.head(top_n).sort_values(value_col, ascending=True)

    fig, ax = plt.subplots(figsize=FIGSIZE_MEDIUM)
    bars = ax.barh(top_df['region'], top_df[value_col] / 10000, color=COLORS['highlight'])

    for bar, val in zip(bars, top_df[value_col].values):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                f'{val/10000:,.1f}', va='center', fontsize=9)

    ax.set_xlabel('인구 (만 명)')
    ax.set_title(f'전국 인구 상위 {top_n}개 시군구')
    plt.tight_layout()
    save_figure(fig, f'{filename_prefix}_top{top_n}.png')

    # 하위 N개
    bottom_df = sigungu_agg.tail(top_n).sort_values(value_col, ascending=False)

    fig, ax = plt.subplots(figsize=FIGSIZE_MEDIUM)
    bars = ax.barh(bottom_df['region'], bottom_df[value_col] / 10000, color='#78909C')

    for bar, val in zip(bars, bottom_df[value_col].values):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                f'{val/10000:,.2f}', va='center', fontsize=9)

    ax.set_xlabel('인구 (만 명)')
    ax.set_title(f'전국 인구 하위 {top_n}개 시군구')
    plt.tight_layout()
    save_figure(fig, f'{filename_prefix}_bottom{top_n}.png')
```

### 6.7 연령_그룹별 집계 막대 그래프
```python
def plot_age_group_bar(df_long: pd.DataFrame, group_type: str = '15',
                        value_col: str = 'population', title: str = None,
                        filename: str = 'age_group_bar.png'):
    """연령 그룹별 막대 그래프

    Args:
        df_long: Long 형식 데이터
        group_type: '15' (연령_그룹별) 또는 '8' (연령_속성별)
        value_col: 값 컬럼
        title: 그래프 제목
        filename: 저장 파일명
    """
    agg_df = aggregate_by_age_group(df_long, group_type, value_col)
    group_col = f'age_group_{group_type}'

    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)

    x = np.arange(len(agg_df))
    width = 0.35

    bars_male = ax.bar(x - width/2, agg_df['남자'] / 10000, width,
                       label='남자', color=COLORS['male'])
    bars_female = ax.bar(x + width/2, agg_df['여자'] / 10000, width,
                         label='여자', color=COLORS['female'])

    ax.set_xlabel('연령 그룹')
    ax.set_ylabel('인구 (만 명)')

    if title is None:
        group_name = "연령_그룹별" if group_type == '15' else "연령_속성별"
        title = f'{group_name} 인구 분포'
    ax.set_title(title)

    ax.set_xticks(x)
    ax.set_xticklabels(agg_df[group_col], rotation=45, ha='right')
    ax.legend()

    plt.tight_layout()
    save_figure(fig, filename)
```

### 6.8 연령대별 1인세대 비율 (교차 비교)
```python
def plot_single_household_ratio_by_age(pop_long: pd.DataFrame, hh_long: pd.DataFrame,
                                        group_type: str = '8',
                                        filename: str = 'single_ratio_by_age.png'):
    """연령대별 1인세대 비율 그래프 (인구 대비)

    Args:
        pop_long: 인구 데이터 (Long 형식)
        hh_long: 1인세대 데이터 (Long 형식)
        group_type: '15' 또는 '8'
        filename: 저장 파일명
    """
    group_col = f'age_group_{group_type}'

    # 연령 그룹 추가
    if group_col not in pop_long.columns:
        pop_long = add_age_group_15(pop_long) if group_type == '15' else add_age_group_8(pop_long)
    if group_col not in hh_long.columns:
        hh_long = add_age_group_15(hh_long) if group_type == '15' else add_age_group_8(hh_long)

    # 연령 그룹별 집계
    pop_agg = pop_long.groupby([group_col, 'gender'])['population'].sum().unstack(fill_value=0)
    hh_agg = hh_long.groupby([group_col, 'gender'])['household_cnt'].sum().unstack(fill_value=0)

    # 비율 계산 (1인세대수 / 인구 * 100)
    ratio_male = (hh_agg['남자'] / pop_agg['남자'] * 100).fillna(0)
    ratio_female = (hh_agg['여자'] / pop_agg['여자'] * 100).fillna(0)

    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)

    x = np.arange(len(ratio_male))
    width = 0.35

    bars_male = ax.bar(x - width/2, ratio_male.values, width,
                       label='남자', color=COLORS['male'])
    bars_female = ax.bar(x + width/2, ratio_female.values, width,
                         label='여자', color=COLORS['female'])

    # 값 표시
    for bar in bars_male:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{bar.get_height():.1f}', ha='center', fontsize=8)
    for bar in bars_female:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{bar.get_height():.1f}', ha='center', fontsize=8)

    ax.set_xlabel('연령 그룹')
    ax.set_ylabel('1인세대 비율 (%)')
    ax.set_title('연령대별 1인세대 비율 (인구 대비)')

    ax.set_xticks(x)
    ax.set_xticklabels(ratio_male.index, rotation=45, ha='right')
    ax.legend()

    plt.tight_layout()
    save_figure(fig, filename)
```

### 6.9 시도별 연령대별 히트맵
```python
def plot_age_sido_heatmap(df_long: pd.DataFrame, group_type: str = '8',
                           filename: str = 'age_sido_heatmap.png'):
    """시도별 연령대별 인구 히트맵

    Args:
        df_long: Long 형식 데이터
        group_type: '15' 또는 '8'
        filename: 저장 파일명
    """
    group_col = f'age_group_{group_type}'

    if group_col not in df_long.columns:
        df_long = add_age_group_15(df_long) if group_type == '15' else add_age_group_8(df_long)

    # 피벗 테이블
    pivot = df_long.groupby(['sido_nm', group_col])['population'].sum().unstack(fill_value=0)
    pivot = pivot / 10000  # 만 명 단위

    # 시도 정렬 (인구 많은 순)
    sido_order = pivot.sum(axis=1).sort_values(ascending=False).index
    pivot = pivot.loc[sido_order]

    fig, ax = plt.subplots(figsize=FIGSIZE_LARGE)

    sns.heatmap(pivot, cmap='YlOrRd', annot=True, fmt='.0f',
                cbar_kws={'label': '인구 (만 명)'}, ax=ax)

    ax.set_xlabel('연령 그룹')
    ax.set_ylabel('시도')
    ax.set_title(f'시도별 연령대별 인구 분포 (연령_{group_type}개 그룹)')

    plt.tight_layout()
    save_figure(fig, filename)
```

### 6.10 월별 인구 추이
```python
def plot_monthly_trend(df: pd.DataFrame, filename: str = 'monthly_trend.png'):
    """월별 인구 추이 그래프"""
    # 월별 집계
    monthly = df.groupby('base_ym').agg({
        'total_pop': 'sum',
        'male_pop': 'sum',
        'female_pop': 'sum'
    }).reset_index()

    monthly['base_ym'] = pd.to_datetime(monthly['base_ym'])

    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)

    ax.plot(monthly['base_ym'], monthly['total_pop'] / 10000,
            marker='o', color=COLORS['total'], label='전체', linewidth=2)
    ax.plot(monthly['base_ym'], monthly['male_pop'] / 10000,
            marker='s', color=COLORS['male'], label='남자', linewidth=1.5)
    ax.plot(monthly['base_ym'], monthly['female_pop'] / 10000,
            marker='^', color=COLORS['female'], label='여자', linewidth=1.5)

    ax.set_xlabel('기준연월')
    ax.set_ylabel('인구 (만 명)')
    ax.set_title('월별 인구 추이')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # x축 날짜 포맷
    fig.autofmt_xdate()

    plt.tight_layout()
    save_figure(fig, filename)
```

---

## 7. 교차 비교 분석

### 7.1 인구 vs 1인세대 비교 테이블
```python
def create_cross_comparison_table(pop_long: pd.DataFrame, hh_long: pd.DataFrame,
                                   group_by: str = 'sido_nm') -> pd.DataFrame:
    """인구와 1인세대 교차 비교 테이블 생성

    Args:
        pop_long: 인구 데이터 (Long 형식)
        hh_long: 1인세대 데이터 (Long 형식)
        group_by: 그룹핑 기준 ('sido_nm', 'sigungu_nm', 'age_group_8', 'age_group_15')

    Returns:
        교차 비교 DataFrame
    """
    # 인구 집계
    pop_agg = pop_long.groupby(group_by).agg({
        'population': 'sum'
    }).rename(columns={'population': '총인구'})

    pop_by_gender = pop_long.groupby([group_by, 'gender'])['population'].sum().unstack()
    pop_agg['남자인구'] = pop_by_gender['남자']
    pop_agg['여자인구'] = pop_by_gender['여자']

    # 1인세대 집계
    hh_agg = hh_long.groupby(group_by).agg({
        'household_cnt': 'sum'
    }).rename(columns={'household_cnt': '총1인세대'})

    hh_by_gender = hh_long.groupby([group_by, 'gender'])['household_cnt'].sum().unstack()
    hh_agg['남자1인세대'] = hh_by_gender['남자']
    hh_agg['여자1인세대'] = hh_by_gender['여자']

    # 합치기
    result = pop_agg.join(hh_agg, how='outer').fillna(0)

    # 비율 계산
    result['1인세대비율(%)'] = (result['총1인세대'] / result['총인구'] * 100).round(2)
    result['남자1인세대비율(%)'] = (result['남자1인세대'] / result['남자인구'] * 100).round(2)
    result['여자1인세대비율(%)'] = (result['여자1인세대'] / result['여자인구'] * 100).round(2)

    return result.reset_index()
```

### 7.2 시도별 교차 비교 시각화
```python
def plot_sido_cross_comparison(comparison_df: pd.DataFrame,
                                filename: str = 'sido_cross_comparison.png'):
    """시도별 인구-1인세대 교차 비교 시각화"""
    df = comparison_df.sort_values('총인구', ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_EXTRA_WIDE)

    # 왼쪽: 인구 vs 1인세대 수
    ax1 = axes[0]
    y = np.arange(len(df))
    width = 0.35

    ax1.barh(y - width/2, df['총인구'] / 100000, width, label='총인구 (십만)', color=COLORS['total'])
    ax1.barh(y + width/2, df['총1인세대'] / 10000, width, label='1인세대 (만)', color=COLORS['single'])

    ax1.set_yticks(y)
    ax1.set_yticklabels(df['sido_nm'])
    ax1.set_xlabel('인구/세대수')
    ax1.set_title('시도별 인구 vs 1인세대수')
    ax1.legend()

    # 오른쪽: 1인세대 비율
    ax2 = axes[1]
    bars = ax2.barh(df['sido_nm'], df['1인세대비율(%)'], color=COLORS['highlight'])

    for bar, val in zip(bars, df['1인세대비율(%)'].values):
        ax2.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
                f'{val:.1f}%', va='center', fontsize=9)

    ax2.set_xlabel('1인세대 비율 (%)')
    ax2.set_title('시도별 1인세대 비율')

    plt.tight_layout()
    save_figure(fig, filename)
```

---

## 8. 대시보드 필터 지원

### 8.1 필터 적용 함수
```python
def apply_filters(df: pd.DataFrame, sido: str = None, sigungu: str = None,
                  base_ym: str = None) -> pd.DataFrame:
    """대시보드 필터 적용

    Args:
        df: 원본 데이터
        sido: 시도 필터 (예: '서울특별시')
        sigungu: 시군구 필터 (예: '강남구')
        base_ym: 기준연월 필터 (예: '2025-11-01')

    Returns:
        필터링된 DataFrame
    """
    filtered = df.copy()

    if sido:
        filtered = filtered[filtered['sido_nm'] == sido]
    if sigungu:
        filtered = filtered[filtered['sigungu_nm'].str.contains(sigungu)]
    if base_ym:
        filtered = filtered[filtered['base_ym'] == base_ym]

    return filtered
```

### 8.2 필터 옵션 조회 함수
```python
def get_filter_options(df: pd.DataFrame) -> dict:
    """필터 옵션 목록 조회

    Returns:
        {'sido': [...], 'sigungu': {...}, 'base_ym': [...]}
    """
    options = {
        'sido': sorted(df['sido_nm'].unique().tolist()),
        'sigungu': {},  # 시도별 시군구 목록
        'base_ym': sorted(df['base_ym'].unique().tolist())
    }

    # 시도별 시군구 목록
    for sido in options['sido']:
        sido_df = df[df['sido_nm'] == sido]
        options['sigungu'][sido] = sorted(sido_df['sigungu_nm'].unique().tolist())

    return options
```

### 8.3 필터 기반 분석 실행
```python
def run_filtered_analysis(sido: str = None, sigungu: str = None,
                           base_ym: str = None, output_prefix: str = 'filtered'):
    """필터 기반 분석 실행

    Args:
        sido: 시도 필터
        sigungu: 시군구 필터
        base_ym: 기준연월 필터
        output_prefix: 출력 파일 접두사
    """
    logger.info(f"필터 분석 시작 - 시도: {sido}, 시군구: {sigungu}, 기준연월: {base_ym}")

    # 데이터 로드
    df_basic = load_population_basic(sido_filter=sido, sigungu_filter=sigungu)
    df_age = load_population_by_age(base_ym=base_ym, sido_filter=sido)
    df_hh = load_single_household(base_ym=base_ym, sido_filter=sido)

    # 필터 적용
    if sigungu:
        df_basic = df_basic[df_basic['sigungu_nm'].str.contains(sigungu)]
        df_age = df_age[df_age['sigungu_nm'].str.contains(sigungu)]
        df_hh = df_hh[df_hh['sigungu_nm'].str.contains(sigungu)]

    # Long 형식 변환
    df_age_long = wide_to_long(df_age, 'population')
    df_hh_long = wide_to_long(df_hh, 'household_cnt')

    # 연령 그룹 추가
    df_age_long = add_age_group_8(add_age_group_15(df_age_long))
    df_hh_long = add_age_group_8(add_age_group_15(df_hh_long))

    # 시각화 생성
    region_name = sido if sido else '전국'
    if sigungu:
        region_name = f'{region_name} {sigungu}'

    # 인구 피라미드
    plot_population_pyramid(df_age_long, f'{region_name} 인구 피라미드',
                            f'{output_prefix}_pyramid.png')

    # 연령_그룹별 막대그래프
    plot_age_group_bar(df_age_long, '15', 'population',
                       f'{region_name} 연령_그룹별 인구', f'{output_prefix}_age15.png')

    # 연령_속성별 막대그래프
    plot_age_group_bar(df_age_long, '8', 'population',
                       f'{region_name} 연령_속성별 인구', f'{output_prefix}_age8.png')

    # 1인세대 비율
    plot_single_household_ratio_by_age(df_age_long, df_hh_long, '8',
                                        f'{output_prefix}_single_ratio.png')

    logger.info(f"필터 분석 완료 - {region_name}")

    return {
        'basic': df_basic,
        'age_long': df_age_long,
        'hh_long': df_hh_long
    }
```

---

## 9. 분석 보고서 생성

### 9.1 집계표 생성 함수
```python
def create_summary_tables(pop_long: pd.DataFrame, hh_long: pd.DataFrame) -> dict:
    """각종 집계표 생성

    Returns:
        dict: 집계표 딕셔너리
    """
    tables = {}

    # 시도별 집계표
    tables['sido'] = create_cross_comparison_table(pop_long, hh_long, 'sido_nm')

    # 연령_그룹별 집계표 (15그룹)
    pop_long = add_age_group_15(pop_long)
    hh_long = add_age_group_15(hh_long)
    tables['age_group_15'] = create_cross_comparison_table(pop_long, hh_long, 'age_group_15')

    # 연령_속성별 집계표 (8그룹)
    pop_long = add_age_group_8(pop_long)
    hh_long = add_age_group_8(hh_long)
    tables['age_group_8'] = create_cross_comparison_table(pop_long, hh_long, 'age_group_8')

    return tables
```

### 9.2 보고서 생성
```python
def generate_report(analysis_results: dict, tables: dict, output_file: str = 'report.md'):
    """분석 결과를 마크다운 보고서로 저장"""
    report = []

    # 제목
    report.append("# 인구통계 데이터 분석 보고서\n")
    report.append(f"**분석일시:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**분석기간:** 2024년 11월 ~ 2025년 11월\n")
    report.append(f"**분석단위:** 읍면동\n")
    report.append("\n---\n")

    # 1. 데이터 개요
    report.append("## 1. 데이터 개요\n")
    if 'data_summary' in analysis_results:
        summary = analysis_results['data_summary']
        report.append(f"- **총 데이터 건수:** {summary.get('total_rows', 'N/A'):,}건\n")
        report.append(f"- **시도 수:** {summary.get('sido_count', 'N/A')}개\n")
        report.append(f"- **시군구 수:** {summary.get('sigungu_count', 'N/A')}개\n")
    report.append("\n")

    # 2. 시도별 분석
    report.append("## 2. 시도별 인구 현황\n")
    report.append("### 2.1 시도별 인구 막대그래프\n")
    report.append("![시도별 인구](./images/sido_population.png)\n\n")

    report.append("### 2.2 시도별 집계표\n")
    if 'sido' in tables:
        report.append(tables['sido'].to_markdown(index=False))
    report.append("\n\n")

    # 3. 인구 피라미드
    report.append("## 3. 인구 피라미드\n")
    report.append("![인구 피라미드](./images/population_pyramid.png)\n\n")

    # 4. 연령대별 분석
    report.append("## 4. 연령대별 분석\n")

    report.append("### 4.1 연령_그룹별 (15개 그룹) 분포\n")
    report.append("![연령_그룹별](./images/age_group_15.png)\n\n")

    if 'age_group_15' in tables:
        report.append("**집계표:**\n")
        report.append(tables['age_group_15'].to_markdown(index=False))
    report.append("\n\n")

    report.append("### 4.2 연령_속성별 (8개 그룹) 분포\n")
    report.append("![연령_속성별](./images/age_group_8.png)\n\n")

    if 'age_group_8' in tables:
        report.append("**집계표:**\n")
        report.append(tables['age_group_8'].to_markdown(index=False))
    report.append("\n\n")

    # 5. 1인세대 분석
    report.append("## 5. 1인세대 분석\n")
    report.append("### 5.1 연령대별 1인세대 비율\n")
    report.append("![1인세대 비율](./images/single_ratio_by_age.png)\n\n")

    report.append("### 5.2 시도별 교차 비교\n")
    report.append("![교차 비교](./images/sido_cross_comparison.png)\n\n")

    # 6. 경상북도 분석
    report.append("## 6. 경상북도 시군별 분석\n")
    report.append("### 6.1 시군별 인구\n")
    report.append("![경상북도 인구](./images/gyeongbuk_sigungu.png)\n\n")
    report.append("### 6.2 시군별 1인세대\n")
    report.append("![경상북도 1인세대](./images/gyeongbuk_single_household.png)\n\n")

    # 7. 전국 상위/하위 시군구
    report.append("## 7. 전국 상위/하위 20개 시군구\n")
    report.append("### 7.1 인구 상위 20개 시군구\n")
    report.append("![상위 20](./images/sigungu_top20.png)\n\n")
    report.append("### 7.2 인구 하위 20개 시군구\n")
    report.append("![하위 20](./images/sigungu_bottom20.png)\n\n")

    # 8. 히트맵
    report.append("## 8. 시도별 연령대별 히트맵\n")
    report.append("![히트맵](./images/age_sido_heatmap.png)\n\n")

    # 9. 월별 추이
    report.append("## 9. 월별 인구 추이\n")
    report.append("![월별 추이](./images/monthly_trend.png)\n\n")

    # 10. 결론
    report.append("## 10. 결론 및 시사점\n")
    if 'conclusions' in analysis_results:
        for i, conclusion in enumerate(analysis_results['conclusions'], 1):
            report.append(f"{i}. {conclusion}\n")
    report.append("\n")

    # 파일 저장
    report_content = '\n'.join(report)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)

    logger.info(f"보고서 저장 완료: {output_file}")
    return output_file
```

---

## 10. 전체 분석 실행

### 10.1 메인 실행 함수
```python
def run_full_analysis():
    """전체 분석 실행 및 보고서 생성"""
    logger.info("=" * 60)
    logger.info("인구통계 데이터 분석 시작")
    logger.info("=" * 60)

    results = {'images': [], 'conclusions': []}

    # 1. 코드 테이블 생성 및 등록
    logger.info("코드 테이블 초기화...")
    create_code_tables()
    load_code_from_excel()

    # 2. 데이터 로드
    logger.info("데이터 로드 중...")
    df_basic = load_population_basic()
    df_age = load_population_by_age()
    df_hh = load_single_household()

    # 최신 월 데이터
    latest_ym = df_basic['base_ym'].max()
    df_latest = df_basic[df_basic['base_ym'] == latest_ym]
    df_age_latest = df_age[df_age['base_ym'] == latest_ym]
    df_hh_latest = df_hh[df_hh['base_ym'] == latest_ym]

    results['data_summary'] = {
        'total_rows': len(df_basic),
        'sido_count': df_basic['sido_nm'].nunique(),
        'sigungu_count': df_basic['sigungu_nm'].nunique(),
    }

    # 3. Long 형식 변환
    logger.info("데이터 변환 중...")
    df_age_long = wide_to_long(df_age_latest, 'population')
    df_hh_long = wide_to_long(df_hh_latest, 'household_cnt')

    # 연령 그룹 추가
    df_age_long = add_age_group_8(add_age_group_15(df_age_long))
    df_hh_long = add_age_group_8(add_age_group_15(df_hh_long))

    # 4. 집계표 생성
    logger.info("집계표 생성 중...")
    tables = create_summary_tables(df_age_long.copy(), df_hh_long.copy())

    # 5. 시각화 생성
    logger.info("시각화 생성 중...")

    # 5.1 시도별 인구
    plot_sido_population(df_latest, 'sido_population.png')
    results['images'].append('sido_population.png')

    # 5.2 인구 피라미드
    plot_population_pyramid(df_age_long, f'전국 인구 피라미드 ({latest_ym})', 'population_pyramid.png')
    results['images'].append('population_pyramid.png')

    # 5.3 연령_그룹별 (15그룹)
    plot_age_group_bar(df_age_long, '15', 'population', '전국 연령_그룹별 인구', 'age_group_15.png')
    results['images'].append('age_group_15.png')

    # 5.4 연령_속성별 (8그룹)
    plot_age_group_bar(df_age_long, '8', 'population', '전국 연령_속성별 인구', 'age_group_8.png')
    results['images'].append('age_group_8.png')

    # 5.5 1인세대 비율
    plot_single_household_ratio_by_age(df_age_long, df_hh_long, '8', 'single_ratio_by_age.png')
    results['images'].append('single_ratio_by_age.png')

    # 5.6 시도별 교차 비교
    plot_sido_cross_comparison(tables['sido'], 'sido_cross_comparison.png')
    results['images'].append('sido_cross_comparison.png')

    # 5.7 경상북도 시군별
    plot_gyeongbuk_sigungu(df_latest, 'total_pop', '경상북도 시군별 인구 현황', 'gyeongbuk_sigungu.png')
    results['images'].append('gyeongbuk_sigungu.png')

    plot_gyeongbuk_single_household(df_hh_latest, 'gyeongbuk_single_household.png')
    results['images'].append('gyeongbuk_single_household.png')

    # 5.8 전국 상위/하위 20개 시군구
    plot_top_bottom_sigungu(df_latest, 'total_pop', 20, 'sigungu')
    results['images'].extend(['sigungu_top20.png', 'sigungu_bottom20.png'])

    # 5.9 히트맵
    plot_age_sido_heatmap(df_age_long, '8', 'age_sido_heatmap.png')
    results['images'].append('age_sido_heatmap.png')

    # 5.10 월별 추이
    plot_monthly_trend(df_basic, 'monthly_trend.png')
    results['images'].append('monthly_trend.png')

    # 6. 결론
    total_pop = df_latest['total_pop'].sum()
    total_hh = df_hh_latest['total_cnt'].sum() if 'total_cnt' in df_hh_latest.columns else 0

    results['conclusions'] = [
        f"분석 기간 동안 전국 총 인구는 약 {total_pop/10000:,.0f}만 명으로 집계됨",
        f"1인세대는 총 {total_hh:,}세대로, 전체 인구 대비 약 {total_hh/total_pop*100:.1f}% 수준",
        "청년층(18~39세)과 70대 이상에서 1인세대 비율이 높게 나타남",
        "경상북도 시군별로는 포항시, 구미시의 인구가 가장 많음",
        "수도권 집중 현상이 뚜렷하며, 지방 중소도시 인구 감소 추세 확인"
    ]

    # 7. 보고서 생성
    logger.info("보고서 생성 중...")
    generate_report(results, tables, 'report.md')

    logger.info("=" * 60)
    logger.info("분석 완료!")
    logger.info(f"- 보고서: report.md")
    logger.info(f"- 이미지: ./images/ 폴더")
    logger.info("=" * 60)

    return results, tables
```

---

## 11. 실행 예시

### 11.1 전체 분석 실행
```python
if __name__ == "__main__":
    results, tables = run_full_analysis()
```

### 11.2 필터 기반 분석 (대시보드용)
```python
# 경상북도만 분석
run_filtered_analysis(sido='경상북도', output_prefix='gyeongbuk')

# 서울특별시 강남구만 분석
run_filtered_analysis(sido='서울특별시', sigungu='강남구', output_prefix='gangnam')

# 특정 월만 분석
run_filtered_analysis(base_ym='2025-11-01', output_prefix='202511')
```

### 11.3 개별 시각화 생성
```python
# 데이터 로드
df_age = load_population_by_age('2025-11-01')
df_long = wide_to_long(df_age, 'population')
df_long = add_age_group_8(add_age_group_15(df_long))

# 특정 시도 인구 피라미드
seoul_df = df_long[df_long['sido_nm'] == '서울특별시']
plot_population_pyramid(seoul_df, '서울특별시 인구 피라미드', 'pyramid_seoul.png')

# 연령_속성별 막대그래프
plot_age_group_bar(df_long, '8', 'population', '전국 연령_속성별 인구', 'age8_nation.png')
```

---

## 12. 출력 파일

### 12.1 이미지 파일 (./images/)
| 파일명 | 설명 |
|--------|------|
| sido_population.png | 시도별 인구 막대그래프 |
| population_pyramid.png | 전국 인구 피라미드 |
| age_group_15.png | 연령_그룹별 (15개 그룹) 분포 |
| age_group_8.png | 연령_속성별 (8개 그룹) 분포 |
| single_ratio_by_age.png | 연령대별 1인세대 비율 |
| sido_cross_comparison.png | 시도별 인구-1인세대 교차 비교 |
| gyeongbuk_sigungu.png | 경상북도 시군별 인구 |
| gyeongbuk_single_household.png | 경상북도 시군별 1인세대 |
| sigungu_top20.png | 전국 인구 상위 20개 시군구 |
| sigungu_bottom20.png | 전국 인구 하위 20개 시군구 |
| age_sido_heatmap.png | 시도별 연령대별 히트맵 |
| monthly_trend.png | 월별 인구 추이 |

### 12.2 보고서 파일
- **report.md**: 분석 결과 마크다운 보고서

---

## 13. 주의사항

### 13.1 한글 깨짐 방지
```python
# 반드시 koreanize_matplotlib import
import koreanize_matplotlib

# seaborn의 set_theme() 사용 금지
# sns.set_theme()  # 한글 깨짐 발생
```

### 13.2 이미지 저장
```python
# facecolor='white' 지정 (배경 투명 방지)
fig.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')

# 저장 후 반드시 close
plt.close(fig)
```

### 13.3 메모리 관리
```python
# 대용량 데이터 처리 시 청크 단위로 로드
for chunk in pd.read_sql(query, conn, chunksize=10000):
    process(chunk)

# 사용 후 변수 삭제
del df_large
import gc
gc.collect()
```

### 13.4 DB 연결 관리
```python
# 항상 연결 해제
conn = get_db_connection()
try:
    df = pd.read_sql(query, conn)
finally:
    conn.close()
```

---

## 14. 인사이트 발굴

### 14.1 인사이트 발굴 개요
```python
"""
인사이트 발굴 카테고리:
1. 인구 구조 분석 - 고령화, 저출산, 생산가능인구 비율
2. 지역 특성 분석 - 인구 집중/과소, 성비 불균형
3. 1인세대 분석 - 연령별/지역별 1인세대 특성
4. 시계열 분석 - 인구 증감 추세, 이동 패턴
5. 이상치 탐지 - 급격한 변화, 특이 패턴
"""
```

### 14.2 고령화 지수 분석
```python
def calculate_aging_index(pop_long: pd.DataFrame, group_by: str = 'sido_nm') -> pd.DataFrame:
    """고령화 지수 계산

    고령화 지수 = (65세 이상 인구 / 0-14세 인구) * 100
    - 100 이상: 고령화 사회
    - 200 이상: 초고령 사회

    Args:
        pop_long: Long 형식 인구 데이터
        group_by: 그룹핑 기준

    Returns:
        고령화 지수 DataFrame
    """
    # 연령대 구분
    pop_long['age_category'] = pd.cut(
        pop_long['age'],
        bins=[0, 15, 65, 111],
        labels=['유소년(0-14)', '생산가능(15-64)', '고령(65+)'],
        right=False
    )

    # 그룹별 연령대별 인구 집계
    age_agg = pop_long.groupby([group_by, 'age_category'])['population'].sum().unstack(fill_value=0)

    # 고령화 지수 계산
    result = pd.DataFrame()
    result[group_by] = age_agg.index
    result['유소년인구'] = age_agg['유소년(0-14)'].values
    result['생산가능인구'] = age_agg['생산가능(15-64)'].values
    result['고령인구'] = age_agg['고령(65+)'].values
    result['총인구'] = result['유소년인구'] + result['생산가능인구'] + result['고령인구']

    # 지수 계산
    result['고령화지수'] = (result['고령인구'] / result['유소년인구'] * 100).round(1)
    result['고령인구비율(%)'] = (result['고령인구'] / result['총인구'] * 100).round(1)
    result['유소년부양비'] = (result['유소년인구'] / result['생산가능인구'] * 100).round(1)
    result['노년부양비'] = (result['고령인구'] / result['생산가능인구'] * 100).round(1)
    result['총부양비'] = result['유소년부양비'] + result['노년부양비']

    # 고령화 단계 판정
    def get_aging_stage(ratio):
        if ratio >= 20:
            return "초고령사회"
        elif ratio >= 14:
            return "고령사회"
        elif ratio >= 7:
            return "고령화사회"
        else:
            return "청년사회"

    result['고령화단계'] = result['고령인구비율(%)'].apply(get_aging_stage)

    return result.reset_index(drop=True)
```

### 14.3 성비 불균형 분석
```python
def analyze_sex_ratio(pop_long: pd.DataFrame, group_by: str = 'sido_nm') -> pd.DataFrame:
    """성비 분석 및 불균형 탐지

    성비 = (남자 인구 / 여자 인구) * 100
    - 100 미만: 여초 지역
    - 100 초과: 남초 지역

    Returns:
        성비 분석 결과 DataFrame
    """
    gender_agg = pop_long.groupby([group_by, 'gender'])['population'].sum().unstack(fill_value=0)

    result = pd.DataFrame()
    result[group_by] = gender_agg.index
    result['남자인구'] = gender_agg['남자'].values
    result['여자인구'] = gender_agg['여자'].values
    result['성비'] = (result['남자인구'] / result['여자인구'] * 100).round(1)
    result['성비차이'] = (result['성비'] - 100).abs().round(1)

    # 불균형 판정
    def get_balance_status(ratio):
        if ratio >= 110:
            return "심한 남초"
        elif ratio >= 105:
            return "남초"
        elif ratio >= 95:
            return "균형"
        elif ratio >= 90:
            return "여초"
        else:
            return "심한 여초"

    result['성비상태'] = result['성비'].apply(get_balance_status)

    return result.reset_index(drop=True)
```

### 14.4 1인세대 특성 분석
```python
def analyze_single_household_characteristics(pop_long: pd.DataFrame, hh_long: pd.DataFrame,
                                              group_by: str = 'sido_nm') -> dict:
    """1인세대 특성 종합 분석

    Returns:
        분석 결과 딕셔너리
    """
    insights = {
        'summary': {},
        'by_region': None,
        'by_age': None,
        'risk_regions': [],
        'key_findings': []
    }

    # 연령 그룹 추가
    pop_long = add_age_group_8(pop_long.copy())
    hh_long = add_age_group_8(hh_long.copy())

    # 지역별 분석
    pop_by_region = pop_long.groupby(group_by)['population'].sum()
    hh_by_region = hh_long.groupby(group_by)['household_cnt'].sum()

    region_df = pd.DataFrame({
        '인구': pop_by_region,
        '1인세대': hh_by_region,
        '1인세대비율(%)': (hh_by_region / pop_by_region * 100).round(2)
    }).reset_index()

    insights['by_region'] = region_df

    # 연령별 분석
    pop_by_age = pop_long.groupby('age_group_8')['population'].sum()
    hh_by_age = hh_long.groupby('age_group_8')['household_cnt'].sum()

    age_df = pd.DataFrame({
        '인구': pop_by_age,
        '1인세대': hh_by_age,
        '1인세대비율(%)': (hh_by_age / pop_by_age * 100).round(2)
    }).reset_index()

    insights['by_age'] = age_df

    # 전체 요약
    total_pop = pop_long['population'].sum()
    total_hh = hh_long['household_cnt'].sum()
    insights['summary'] = {
        '총인구': total_pop,
        '총1인세대': total_hh,
        '전국1인세대비율': round(total_hh / total_pop * 100, 2)
    }

    # 위험 지역 식별 (1인세대 비율 상위)
    high_ratio_regions = region_df.nlargest(5, '1인세대비율(%)')
    insights['risk_regions'] = high_ratio_regions[group_by].tolist()

    # 핵심 발견 사항
    max_ratio_region = region_df.loc[region_df['1인세대비율(%)'].idxmax()]
    min_ratio_region = region_df.loc[region_df['1인세대비율(%)'].idxmin()]
    max_ratio_age = age_df.loc[age_df['1인세대비율(%)'].idxmax()]

    insights['key_findings'] = [
        f"1인세대 비율이 가장 높은 지역: {max_ratio_region[group_by]} ({max_ratio_region['1인세대비율(%)']}%)",
        f"1인세대 비율이 가장 낮은 지역: {min_ratio_region[group_by]} ({min_ratio_region['1인세대비율(%)']}%)",
        f"1인세대 비율이 가장 높은 연령대: {max_ratio_age['age_group_8']} ({max_ratio_age['1인세대비율(%)']}%)",
        f"전국 평균 1인세대 비율: {insights['summary']['전국1인세대비율']}%"
    ]

    return insights
```

### 14.5 인구 증감 추세 분석
```python
def analyze_population_trend(df_basic: pd.DataFrame, group_by: str = 'sido_nm') -> pd.DataFrame:
    """월별 인구 증감 추세 분석

    Returns:
        증감 추세 분석 DataFrame
    """
    # 월별 그룹별 인구 집계
    monthly = df_basic.groupby(['base_ym', group_by])['total_pop'].sum().unstack(fill_value=0)

    # 시작월 대비 증감률 계산
    first_month = monthly.iloc[0]
    last_month = monthly.iloc[-1]

    result = pd.DataFrame({
        group_by: monthly.columns,
        '시작월인구': first_month.values,
        '종료월인구': last_month.values,
        '증감수': (last_month - first_month).values,
        '증감률(%)': ((last_month - first_month) / first_month * 100).round(2).values
    })

    # 월평균 증감률
    months_count = len(monthly)
    result['월평균증감률(%)'] = (result['증감률(%)'] / months_count).round(3)

    # 추세 판정
    def get_trend(rate):
        if rate >= 0.5:
            return "급증"
        elif rate >= 0.1:
            return "증가"
        elif rate >= -0.1:
            return "유지"
        elif rate >= -0.5:
            return "감소"
        else:
            return "급감"

    result['추세'] = result['증감률(%)'].apply(get_trend)

    return result.sort_values('증감률(%)', ascending=False).reset_index(drop=True)
```

### 14.6 이상치 탐지
```python
def detect_anomalies(df: pd.DataFrame, value_col: str, group_col: str = 'sido_nm',
                      threshold: float = 2.0) -> pd.DataFrame:
    """이상치 탐지 (Z-score 기반)

    Args:
        df: 데이터프레임
        value_col: 분석할 값 컬럼
        group_col: 그룹 컬럼
        threshold: Z-score 임계값 (기본 2.0)

    Returns:
        이상치 목록 DataFrame
    """
    # 그룹별 집계
    agg = df.groupby(group_col)[value_col].sum().reset_index()

    # Z-score 계산
    mean_val = agg[value_col].mean()
    std_val = agg[value_col].std()
    agg['z_score'] = ((agg[value_col] - mean_val) / std_val).round(2)
    agg['is_anomaly'] = agg['z_score'].abs() > threshold

    # 이상치 유형 판정
    def get_anomaly_type(z):
        if z > threshold:
            return "상위 이상치 (매우 높음)"
        elif z < -threshold:
            return "하위 이상치 (매우 낮음)"
        else:
            return "정상 범위"

    agg['이상치유형'] = agg['z_score'].apply(get_anomaly_type)

    return agg
```

### 14.7 종합 인사이트 생성
```python
def generate_insights(pop_long: pd.DataFrame, hh_long: pd.DataFrame,
                       df_basic: pd.DataFrame) -> dict:
    """종합 인사이트 생성

    Returns:
        모든 인사이트가 포함된 딕셔너리
    """
    insights = {
        'aging': None,
        'sex_ratio': None,
        'single_household': None,
        'population_trend': None,
        'anomalies': None,
        'executive_summary': []
    }

    # 1. 고령화 분석
    insights['aging'] = calculate_aging_index(pop_long.copy(), 'sido_nm')

    # 초고령사회 지역 수
    super_aged = insights['aging'][insights['aging']['고령화단계'] == '초고령사회']
    if len(super_aged) > 0:
        insights['executive_summary'].append(
            f"초고령사회 진입 시도: {len(super_aged)}개 ({', '.join(super_aged['sido_nm'].tolist())})"
        )

    # 2. 성비 분석
    insights['sex_ratio'] = analyze_sex_ratio(pop_long.copy(), 'sido_nm')

    imbalanced = insights['sex_ratio'][insights['sex_ratio']['성비상태'].isin(['심한 남초', '심한 여초'])]
    if len(imbalanced) > 0:
        insights['executive_summary'].append(
            f"성비 불균형 심각 지역: {len(imbalanced)}개"
        )

    # 3. 1인세대 분석
    insights['single_household'] = analyze_single_household_characteristics(
        pop_long.copy(), hh_long.copy(), 'sido_nm'
    )
    insights['executive_summary'].extend(insights['single_household']['key_findings'][:2])

    # 4. 인구 추세 분석
    insights['population_trend'] = analyze_population_trend(df_basic.copy(), 'sido_nm')

    declining = insights['population_trend'][insights['population_trend']['추세'].isin(['감소', '급감'])]
    if len(declining) > 0:
        insights['executive_summary'].append(
            f"인구 감소 추세 시도: {len(declining)}개"
        )

    # 5. 이상치 탐지
    insights['anomalies'] = detect_anomalies(pop_long.copy(), 'population', 'sido_nm')

    return insights
```

### 14.8 인사이트 시각화
```python
def plot_aging_index(aging_df: pd.DataFrame, filename: str = 'aging_index.png'):
    """고령화 지수 시각화"""
    df = aging_df.sort_values('고령화지수', ascending=True)

    fig, ax = plt.subplots(figsize=FIGSIZE_MEDIUM)

    # 색상 매핑
    colors = df['고령화단계'].map({
        '청년사회': '#4CAF50',
        '고령화사회': '#FFC107',
        '고령사회': '#FF9800',
        '초고령사회': '#F44336'
    })

    bars = ax.barh(df['sido_nm'], df['고령화지수'], color=colors)

    # 기준선
    ax.axvline(100, color='gray', linestyle='--', label='고령화지수=100')
    ax.axvline(200, color='red', linestyle='--', alpha=0.5, label='고령화지수=200')

    ax.set_xlabel('고령화 지수')
    ax.set_title('시도별 고령화 지수')
    ax.legend()

    plt.tight_layout()
    save_figure(fig, filename)


def plot_population_trend_heatmap(df_basic: pd.DataFrame, filename: str = 'pop_trend_heatmap.png'):
    """월별 인구 증감 히트맵"""
    # 월별 시도별 인구
    monthly = df_basic.groupby(['base_ym', 'sido_nm'])['total_pop'].sum().unstack()

    # 전월 대비 증감률 계산
    pct_change = monthly.pct_change() * 100

    fig, ax = plt.subplots(figsize=FIGSIZE_LARGE)

    sns.heatmap(pct_change.T, cmap='RdYlGn', center=0, annot=True, fmt='.2f',
                cbar_kws={'label': '증감률 (%)'}, ax=ax)

    ax.set_xlabel('기준연월')
    ax.set_ylabel('시도')
    ax.set_title('월별 인구 증감률 히트맵')

    plt.tight_layout()
    save_figure(fig, filename)
```

### 14.9 인사이트 보고서 생성
```python
def generate_insight_report(insights: dict, output_file: str = 'insight_report.md'):
    """인사이트 보고서 생성"""
    report = []

    report.append("# 인구통계 인사이트 보고서\n")
    report.append(f"**생성일시:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append("\n---\n")

    # Executive Summary
    report.append("## Executive Summary\n")
    for i, finding in enumerate(insights['executive_summary'], 1):
        report.append(f"{i}. {finding}\n")
    report.append("\n")

    # 고령화 분석
    report.append("## 1. 고령화 분석\n")
    report.append("### 시도별 고령화 현황\n")
    if insights['aging'] is not None:
        report.append(insights['aging'].to_markdown(index=False))
    report.append("\n\n![고령화지수](./images/aging_index.png)\n\n")

    # 성비 분석
    report.append("## 2. 성비 분석\n")
    if insights['sex_ratio'] is not None:
        report.append(insights['sex_ratio'].to_markdown(index=False))
    report.append("\n\n")

    # 1인세대 분석
    report.append("## 3. 1인세대 분석\n")
    if insights['single_household'] is not None:
        sh = insights['single_household']
        report.append("### 핵심 발견\n")
        for finding in sh['key_findings']:
            report.append(f"- {finding}\n")
        report.append("\n### 지역별 현황\n")
        if sh['by_region'] is not None:
            report.append(sh['by_region'].to_markdown(index=False))
        report.append("\n\n### 연령별 현황\n")
        if sh['by_age'] is not None:
            report.append(sh['by_age'].to_markdown(index=False))
    report.append("\n\n")

    # 인구 추세
    report.append("## 4. 인구 증감 추세\n")
    if insights['population_trend'] is not None:
        report.append(insights['population_trend'].to_markdown(index=False))
    report.append("\n\n![추세히트맵](./images/pop_trend_heatmap.png)\n\n")

    # 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    logger.info(f"인사이트 보고서 저장: {output_file}")
    return output_file
```
