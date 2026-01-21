# 인구통계 데이터베이스 온톨로지

> **최종 수정**: 2026-01-19
> **목적**: DB 구조, 테이블 관계, 데이터 흐름 정의

---

## 1. 시스템 아키텍처

### 데이터 흐름
```
┌─────────────────────────────────────────────────────────────┐
│                    공공데이터 API                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ basic    │ │age_group │ │population│ │household │       │
│  │(3개월만) │ │(불필요)  │ │(전체)    │ │(전체)    │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────┬───────────────────────────────────────┘
                      │ api_to_db.py
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Fact Tables (원본)                        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │fact_population_ │ │fact_population_ │ │fact_single_   │ │
│  │    basic        │ │   by_age ⭐     │ │  household    │ │
│  │ (세대수 포함)   │ │ (1세별 인구)    │ │(1세별 1인가구)│ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │ transfer.py --refresh
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Cache Tables (시군구 집계)                │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │  cache_sigungu_age  │  │ cache_sigungu_indicators ⭐ │  │
│  │ (1세별 Wide format) │  │  (연령그룹 + 24개 지표)     │  │
│  │     455개 컬럼      │  │       92개 컬럼             │  │
│  └─────────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                      ▲
                      │ load_code_master.py
┌─────────────────────┴───────────────────────────────────────┐
│                    Code Tables (정의)                        │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │   code_age_group    │  │      code_indicator         │  │
│  │  (51개 연령그룹)    │  │     (24개 지표 계산식)      │  │
│  └─────────────────────┘  └─────────────────────────────┘  │
│                      ▲                                      │
│                      │                                      │
│              code_master.xlsx (엑셀 관리)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 테이블 구조

### 2.1 Dimension Tables (차원)

#### dim_admin_area (행정구역 마스터)
```
PK: admin_code (10자리)
├── sido_cd (2자리)         # 시도코드
├── sido_nm                  # 시도명 (서울특별시, 경상북도 등)
├── sigungu_code (5자리)    # 시군구코드 ⭐
├── sigungu_nm              # 시군구명
├── eupmyeondong_cd         # 읍면동코드
├── eupmyeondong_nm         # 읍면동명 (NULL이면 시군구 레벨)
└── region_nm               # 권역명
```

**sigungu_code 규칙** ⭐
```
5자리: 앞4자리=기본시군구, 5번째='0'이면 대표, '0'이 아니면 하위행정구
예: 41110=수원시(대표), 41111=장안구, 41113=권선구, 41115=팔달구

시군구 단위 조회: sigungu_code LIKE '____0'
```

### 2.2 Fact Tables (원본 데이터)

#### fact_population_basic
```
PK: (admin_code, base_ym)
├── total_pop               # 총인구
├── male_pop                # 남자인구
├── female_pop              # 여자인구
└── household_cnt ⭐        # 전체세대수 (basic API에서만 제공)
```
> **제약**: basic API는 최근 3개월만 제공

#### fact_population_by_age ⭐ (메인)
```
PK: (admin_code, base_ym)
├── total_pop, male_total, female_total
├── male_age_0 ~ male_age_109, male_age_110_over    (111개)
└── female_age_0 ~ female_age_109, female_age_110_over (111개)
```
> 총 225개 컬럼, 읍면동 단위

#### fact_single_household
```
PK: (admin_code, base_ym)
├── total_cnt, male_total, female_total
├── male_age_0 ~ male_age_109, male_age_110_over
└── female_age_0 ~ female_age_109, female_age_110_over
```

### 2.3 Code Tables (정의 테이블)

#### code_age_group (51개 연령그룹)
```
├── category (1=5세별, 2=10세별, 3=정책연령)
├── code, code_name          # youth, 유소년
├── column_name              # youth_pop
├── age_start, age_end       # 0, 14
└── is_active
```

**주요 연령그룹**:
| category | code | code_name | 범위 | column_name |
|----------|------|-----------|------|-------------|
| 3 | youth | 유소년 | 0-14 | youth_pop |
| 3 | working | 생산가능인구 | 15-64 | working_pop |
| 3 | elderly | 고령인구 | 65-999 | elderly_pop |
| 3 | young_adult | 청년(기본법) | 19-34 | young_adult_pop |
| 3 | female_20_39 | 20-39세여성 | 20-39 | female_20_39_pop |

#### code_indicator (24개 지표)
```
├── category (1=인구지표, 2=세대지표)
├── column_name, display_name
├── numerator, denominator   # 계산식: 분자 / 분모
├── multiplier               # 곱할 값 (100=백분율)
└── decimal_places           # 소수점 자리수
```

**주요 지표**:
| column_name | display_name | 계산식 |
|-------------|--------------|--------|
| elderly_ratio | 고령화율 | elderly_pop / total_pop × 100 |
| aging_index | 고령화지수 | elderly_pop / youth_pop × 100 |
| extinction_index | 소멸위험지수 | female_20_39_pop / elderly_pop |
| youth_dependency | 유소년부양비 | youth_pop / working_pop × 100 |
| elderly_dependency | 노년부양비 | elderly_pop / working_pop × 100 |
| single_ratio | 1인가구비율 | single_cnt / **household_cnt** × 100 |
| pop_per_house | 세대당인구 | total_pop / **household_cnt** |

### 2.4 Cache Tables (집계 테이블)

#### cache_sigungu_age (1세별 Wide format)
```
PK: (base_ym, sigungu_code)
├── sido_nm, sigungu_nm
├── total_pop, male_total, female_total
├── male_age_0 ~ male_age_110_over (인구)
├── female_age_0 ~ female_age_110_over (인구)
├── male_single_0 ~ male_single_110_over (1인가구)
├── female_single_0 ~ female_single_110_over (1인가구)
└── single_total, male_single_total, female_single_total
```
> 455개 컬럼

#### cache_sigungu_indicators ⭐ (조회 우선)
```
PK: (base_ym, sigungu_code)
├── 기본: sido_nm, sigungu_nm, total_pop, male_pop, female_pop
├── 세대: household_cnt, single_cnt
├── 5세별 인구 (21개): pop_0_4, pop_5_9, ..., pop_100_over
├── 10세별 인구 (16개): pop_under10, pop_10s, ..., pop_80s_over
├── 정책연령 (15개): youth_pop, working_pop, elderly_pop, ...
├── 인구지표 (14개): elderly_ratio, aging_index, extinction_index, ...
└── 세대지표 (9개): single_ratio, pop_per_house, ...
```
> 92개 컬럼

---

## 3. 테이블 연결 관계

### ERD
```
                         ┌─────────────────────┐
                         │   dim_admin_area    │
                         │  (PK: admin_code)   │
                         └──────────┬──────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
           ▼                        ▼                        ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│fact_population_basic│  │fact_population_by_age│  │fact_single_household│
│(admin_code, base_ym)│  │(admin_code, base_ym) │  │(admin_code, base_ym)│
│                     │  │                      │  │                     │
│ household_cnt ⭐    │  │ 1세별 인구 (메인)    │  │ 1세별 1인가구       │
│ (최근 3개월만)      │  │ (2022-12~)          │  │ (2022-12~)          │
└──────────┬──────────┘  └──────────┬───────────┘  └──────────┬──────────┘
           │                        │                         │
           │                        │ 시군구 집계 (메인)      │
           │                        ▼                         │
           │             ┌─────────────────────┐              │
           │             │ cache_sigungu_age   │◄─────────────┘
           │             │ (시군구 1세별 집계) │
           │             └─────────────────────┘
           │                        │
           │  LEFT JOIN             │ 연령그룹 집계
           │  (household_cnt)       ▼
           │             ┌─────────────────────────┐
           └────────────►│cache_sigungu_indicators │
                         │  (지표 계산 결과)       │
                         │                         │
                         │ ※ household_cnt 없는 월:│
                         │   single_ratio = NULL   │
                         │   pop_per_house = NULL  │
                         └─────────────────────────┘
```

### JOIN 관계
```sql
-- Fact → Dimension
fact_population_by_age.admin_code = dim_admin_area.admin_code
fact_single_household.admin_code = dim_admin_area.admin_code
fact_population_basic.admin_code = dim_admin_area.admin_code

-- Cache는 독립 (시군구 단위로 직접 조회)
cache_sigungu_indicators: sido_nm, sigungu_code, sigungu_nm으로 조회
```

---

## 4. 데이터 제약사항

### 4.1 API 제공 범위
| API | 테이블 | 제공 범위 | 필드명 형식 |
|-----|--------|----------|------------|
| basic | fact_population_basic | **최근 3개월만** | - |
| population | fact_population_by_age | 2022-12~ | 시기별 상이 |
| household | fact_single_household | 2022-12~ | 시기별 상이 |

### 4.2 API 필드명 형식 (1세별)
| 시기 | 형식 | 예시 |
|------|------|------|
| 2024년~ | `{age}세남자` | `0세남자`, `0세여자` |
| 2022-12~2023 | `만{age}세남자` | `만0세남자`, `만0세여자` |

### 4.3 household_cnt 관련 제약 ⭐
```
fact_population_basic (최근 3개월만)
         │
         └─ household_cnt 제공
                  │
                  ▼
         영향받는 지표 (2개):
         ├── single_ratio = single_cnt / household_cnt × 100
         └── pop_per_house = total_pop / household_cnt

         household_cnt 없는 월 → 위 지표 NULL
         나머지 22개 지표 → 정상 계산
```

---

## 5. 쿼리 규칙

### 5.1 테이블 선택 규칙
```
IF 고령화율/부양비 등 정책지표 → cache_sigungu_indicators (빠름)
IF 20대/30대 등 사용자정의 연령 → cache_sigungu_age 또는 fact_population_by_age
IF 읍면동 단위 → fact_population_by_age + dim_admin_area
IF 1인가구 연령별 → cache_sigungu_age 또는 fact_single_household
```

### 5.2 SQL 생성 규칙
```sql
-- 시점 미지정 시 최신 데이터
WHERE base_ym = (SELECT MAX(base_ym) FROM 테이블)

-- 시군구 단위 (기본)
WHERE sigungu_code LIKE '____0'

-- 비율 계산 (0 나누기 방지)
ROUND(분자::numeric / NULLIF(분모, 0) * 100, 2)

-- NULL 정렬
ORDER BY ... DESC NULLS LAST
```

### 5.3 컬럼 별칭
```
sido_nm → 시도
sigungu_nm → 시군구
total_pop → 총인구
elderly_pop → 고령인구
elderly_ratio → 고령화율
aging_index → 고령화지수
single_ratio → 1인가구비율
```

---

## 6. 예시 SQL

### 고령화율 순위 (cache 사용)
```sql
SELECT sido_nm AS 시도, sigungu_nm AS 시군구,
       elderly_ratio AS 고령화율, total_pop AS 총인구
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sigungu_code LIKE '____0'
ORDER BY elderly_ratio DESC NULLS LAST
LIMIT 10;
```

### 20대 인구 (cache_sigungu_age 사용)
```sql
SELECT sido_nm AS 시도, sigungu_nm AS 시군구,
       (male_age_20 + male_age_21 + ... + male_age_29 +
        female_age_20 + female_age_21 + ... + female_age_29) AS "20대인구"
FROM cache_sigungu_age
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_age)
ORDER BY "20대인구" DESC
LIMIT 10;
```

### 읍면동 단위 조회 (fact 사용)
```sql
SELECT d.sido_nm AS 시도, d.sigungu_nm AS 시군구,
       d.eupmyeondong_nm AS 읍면동, p.total_pop AS 총인구
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
  AND d.eupmyeondong_nm IS NOT NULL
ORDER BY p.total_pop DESC
LIMIT 20;
```

---

## 7. 용어 정규화

### 시도명
```
서울/서울시 → 서울특별시
경북/경상북도 → 경상북도
강원/강원도 → 강원특별자치도
전북/전라북도 → 전북특별자치도
세종/세종시 → 세종특별자치시
제주/제주도 → 제주특별자치도
```

### 지표명
```
고령화율/노인비율/65세이상비율 → elderly_ratio
1인가구/단독가구/독거 → single_cnt
노령화지수/고령화지수 → aging_index
소멸위험지수 → extinction_index
```

---

## 8. 운영 명령어

### 데이터 수집
```bash
# 전체 수집 (대화형)
python api_to_db.py

# 특정 월 수집
python api_to_db.py --collect --api population --start 202212 --end 202212

# 강제 재수집
python api_to_db.py --collect --force
```

### Cache 갱신
```bash
# 전체 갱신
python transfer.py --refresh

# 특정 월만
python transfer.py --month 202512

# 테이블 재생성 (DDL 변경 시)
python transfer.py --init
```

### 코드 테이블 갱신
```bash
# 엑셀 → DB
python load_code_master.py
```
