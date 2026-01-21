# 인구통계 데이터베이스 상세 온톨로지

> **목적**: 토큰 제약 없이 데이터베이스 구조, 관계, 규칙을 완전하게 문서화
> **최종 수정**: 2026-01-16

---

## 목차

1. [개요](#1-개요)
2. [테이블 상세 명세](#2-테이블-상세-명세)
3. [테이블 관계 및 조인](#3-테이블-관계-및-조인)
4. [지표 계산식](#4-지표-계산식)
5. [연령 그룹 정의](#5-연령-그룹-정의)
6. [용어 정규화 사전](#6-용어-정규화-사전)
7. [SQL 생성 규칙](#7-sql-생성-규칙)
8. [테이블 선택 가이드](#8-테이블-선택-가이드)
9. [차트 및 시각화 규칙](#9-차트-및-시각화-규칙)
10. [보고서 생성 규칙](#10-보고서-생성-규칙)
11. [예시 SQL 패턴](#11-예시-sql-패턴)
12. [ERD 다이어그램](#12-erd-다이어그램)
13. [데이터 흐름](#13-데이터-흐름)

---

## 1. 개요

### 1.1 데이터 출처
- **원천**: 행정안전부 주민등록인구통계 (공공데이터포털 API)
- **수집 주기**: 월별
- **수집 단위**: 읍면동 (최소 행정단위)
- **보관 기간**: 3년 이상 (파티션 테이블로 관리)

### 1.2 데이터베이스 구조 개요

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PostgreSQL Database                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐                                                         │
│  │  Dimension      │  마스터/참조 테이블                                      │
│  │  Tables         │  - dim_admin_area (행정구역)                            │
│  └────────┬────────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐                                                         │
│  │  Fact Tables    │  원본 데이터 (읍면동 단위)                               │
│  │  (Partitioned)  │  - fact_population_basic                                │
│  │                 │  - fact_population_by_age                               │
│  │                 │  - fact_single_household                                │
│  └────────┬────────┘                                                         │
│           │                                                                  │
│           ▼ GROUP BY sigungu_code                                            │
│  ┌─────────────────┐                                                         │
│  │  Cache Tables   │  시군구 단위 집계 (빠른 조회용)                          │
│  │                 │  - cache_sigungu_indicators                             │
│  │                 │  - cache_sigungu_age_summary                            │
│  └─────────────────┘                                                         │
│                                                                              │
│  ┌─────────────────┐                                                         │
│  │  Materialized   │  시군구 단위 1세별 집계                                  │
│  │  Views          │  - mv_sigungu_population_by_age                         │
│  │                 │  - mv_sigungu_single_household                          │
│  └─────────────────┘                                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 테이블 상세 명세

### 2.1 dim_admin_area (행정구역 마스터)

**목적**: 전국 행정구역 정보를 관리하는 마스터 테이블

| 컬럼명 | 데이터타입 | PK | NULL | 설명 | 예시 |
|--------|-----------|:--:|:----:|------|------|
| admin_code | VARCHAR(10) | ✓ | N | 행정구역코드 (10자리) | '4111000000' |
| sido_code | VARCHAR(2) | | N | 시도코드 (2자리) | '41' |
| sido_nm | VARCHAR(20) | | N | 시도명 | '경기도' |
| sigungu_code | VARCHAR(5) | | N | 시군구코드 (5자리) | '41110' |
| sigungu_nm | VARCHAR(30) | | Y | 시군구명 | '수원시' |
| eupmyeondong_code | VARCHAR(10) | | Y | 읍면동코드 | '4111000000' |
| eupmyeondong_nm | VARCHAR(30) | | Y | 읍면동명 | '장안동' |
| region_code | VARCHAR(2) | | Y | 권역코드 | '01' |
| region_nm | VARCHAR(20) | | Y | 권역명 | '수도권' |
| is_active | BOOLEAN | | N | 활성화 여부 | true |
| created_at | TIMESTAMP | | N | 생성일시 | |
| updated_at | TIMESTAMP | | N | 수정일시 | |

**sigungu_code 규칙 (매우 중요)**:
```
5자리 시군구코드 해석 방법:
- 앞 4자리: 기본 시군구 식별자
- 5번째 자리:
  - '0' → 대표 시군구 (예: 41110 = 수원시 전체)
  - '0' 외 → 하위 행정구 (예: 41111=장안구, 41113=권선구, 41115=팔달구, 41117=영통구)

┌─────────────────────────────────────────────────────────┐
│ 수원시 예시                                              │
├─────────────────────────────────────────────────────────┤
│ 41110 (수원시 대표) ←── sigungu_code LIKE '____0'       │
│   ├── 41111 (장안구)                                    │
│   ├── 41113 (권선구)                                    │
│   ├── 41115 (팔달구)                                    │
│   └── 41117 (영통구)                                    │
└─────────────────────────────────────────────────────────┘

시군구 단위 조회 시:
- 기본(하위 합산): WHERE sigungu_code LIKE '____0'
- 하위구분 필요시: 조건 없이 sigungu_code 그대로 사용
```

**권역 정보**:
| 권역코드 | 권역명 | 포함 시도 |
|---------|--------|----------|
| 01 | 수도권 | 서울특별시, 인천광역시, 경기도 |
| 02 | 강원권 | 강원특별자치도 |
| 03 | 충청권 | 대전광역시, 세종특별자치시, 충청북도, 충청남도 |
| 04 | 전라권 | 광주광역시, 전북특별자치도, 전라남도 |
| 05 | 경상권 | 부산광역시, 대구광역시, 울산광역시, 경상북도, 경상남도 |
| 06 | 제주권 | 제주특별자치도 |

---

### 2.2 fact_population_basic (인구 기본 현황)

**목적**: 월별 읍면동 단위 기본 인구 정보 저장

| 컬럼명 | 데이터타입 | PK | NULL | 설명 | 예시 |
|--------|-----------|:--:|:----:|------|------|
| base_ym | DATE | ✓ | N | 기준연월 (매월 1일) | '2024-11-01' |
| admin_code | VARCHAR(10) | ✓ | N | 행정구역코드 | '4111053000' |
| total_pop | INTEGER | | N | 총인구 | 45230 |
| male_pop | INTEGER | | N | 남자인구 | 22150 |
| female_pop | INTEGER | | N | 여자인구 | 23080 |
| household_cnt | INTEGER | | N | 세대수 | 18500 |
| created_at | TIMESTAMP | | N | 생성일시 | |

**파티션 전략**:
```sql
-- 3년 단위 파티션
CREATE TABLE fact_population_basic_2022_2024 PARTITION OF fact_population_basic
    FOR VALUES FROM ('2022-01-01') TO ('2025-01-01');

CREATE TABLE fact_population_basic_2025_2027 PARTITION OF fact_population_basic
    FOR VALUES FROM ('2025-01-01') TO ('2028-01-01');
```

---

### 2.3 fact_population_by_age (1세별 인구현황)

**목적**: 월별 읍면동 단위 1세별 인구 데이터 저장 (Wide Format)

| 컬럼명 | 데이터타입 | PK | NULL | 설명 |
|--------|-----------|:--:|:----:|------|
| base_ym | DATE | ✓ | N | 기준연월 |
| admin_code | VARCHAR(10) | ✓ | N | 행정구역코드 |
| total_pop | INTEGER | | N | 총인구 |
| male_total | INTEGER | | N | 남자 총인구 |
| female_total | INTEGER | | N | 여자 총인구 |
| male_age_0 | INTEGER | | N | 남자 0세 |
| male_age_1 | INTEGER | | N | 남자 1세 |
| ... | ... | | | ... |
| male_age_109 | INTEGER | | N | 남자 109세 |
| male_age_110_over | INTEGER | | N | 남자 110세 이상 |
| female_age_0 | INTEGER | | N | 여자 0세 |
| female_age_1 | INTEGER | | N | 여자 1세 |
| ... | ... | | | ... |
| female_age_109 | INTEGER | | N | 여자 109세 |
| female_age_110_over | INTEGER | | N | 여자 110세 이상 |
| created_at | TIMESTAMP | | N | 생성일시 |

**컬럼 수**: 약 226개
- 기본 컬럼: 5개 (base_ym, admin_code, total_pop, male_total, female_total)
- 1세별 컬럼: 220개 (남녀 각 110개: age_0 ~ age_109, age_110_over)
- 메타 컬럼: 1개 (created_at)

**Wide Format 선택 이유**:
1. 조회 성능: 특정 연령대 조회 시 별도 집계 불필요
2. 저장 효율: 행 수 최소화 (읍면동×월 = 약 3,500행/월)
3. 분석 편의: 연령대별 합산이 SQL로 직관적

---

### 2.4 fact_single_household (1세별 1인가구 현황)

**목적**: 월별 읍면동 단위 1세별 1인가구 데이터 저장

| 컬럼명 | 데이터타입 | PK | NULL | 설명 |
|--------|-----------|:--:|:----:|------|
| base_ym | DATE | ✓ | N | 기준연월 |
| admin_code | VARCHAR(10) | ✓ | N | 행정구역코드 |
| total_cnt | INTEGER | | N | 총 1인가구수 |
| male_total | INTEGER | | N | 남자 1인가구 총계 |
| female_total | INTEGER | | N | 여자 1인가구 총계 |
| male_age_0 | INTEGER | | N | 남자 0세 1인가구 |
| ... | ... | | | (fact_population_by_age와 동일 구조) |
| female_age_110_over | INTEGER | | N | 여자 110세 이상 1인가구 |
| created_at | TIMESTAMP | | N | 생성일시 |

---

### 2.5 cache_sigungu_indicators (시군구별 인구지표 캐시)

**목적**: 대시보드/챗봇에서 빠른 조회를 위해 미리 계산된 시군구 단위 지표 저장

| 컬럼명 | 데이터타입 | PK | NULL | 설명 | 계산식 |
|--------|-----------|:--:|:----:|------|--------|
| base_ym | DATE | ✓ | N | 기준연월 | |
| sigungu_code | VARCHAR(5) | ✓ | N | 시군구코드 | |
| sido_nm | VARCHAR(20) | | N | 시도명 | |
| sigungu_nm | VARCHAR(30) | | N | 시군구명 | |
| total_pop | INTEGER | | N | 총인구 | SUM(total_pop) |
| male_pop | INTEGER | | N | 남자인구 | SUM(male_pop) |
| female_pop | INTEGER | | N | 여자인구 | SUM(female_pop) |
| household_cnt | INTEGER | | N | 세대수 | SUM(household_cnt) |
| single_household_cnt | INTEGER | | N | 1인가구수 | SUM(total_cnt) from fact_single_household |
| youth_pop | INTEGER | | N | 유소년인구 (0~14세) | SUM(age_0~14) |
| working_pop | INTEGER | | N | 생산가능인구 (15~64세) | SUM(age_15~64) |
| elderly_pop | INTEGER | | N | 고령인구 (65세+) | SUM(age_65~110_over) |
| elderly_ratio | NUMERIC(8,2) | | N | 고령인구 비율 (%) | elderly_pop / total_pop × 100 |
| youth_ratio | NUMERIC(8,2) | | N | 유소년 비율 (%) | youth_pop / total_pop × 100 |
| working_ratio | NUMERIC(8,2) | | N | 생산가능인구 비율 (%) | working_pop / total_pop × 100 |
| single_ratio | NUMERIC(8,2) | | N | 1인가구 비율 (%) | single_household_cnt / household_cnt × 100 |
| aging_index | NUMERIC(8,2) | | N | 고령화지수 | elderly_pop / youth_pop × 100 |
| youth_dependency_ratio | NUMERIC(8,2) | | N | 유소년부양비 | youth_pop / working_pop × 100 |
| elderly_dependency_ratio | NUMERIC(8,2) | | N | 노년부양비 | elderly_pop / working_pop × 100 |
| pop_per_house | NUMERIC(8,2) | | N | 세대당 인구 | total_pop / household_cnt |
| sex_ratio | NUMERIC(8,2) | | N | 성비 | male_pop / female_pop × 100 |
| created_at | TIMESTAMP | | N | 생성일시 | |

**인덱스**:
```sql
CREATE INDEX idx_cache_sigungu_indicators_base_ym ON cache_sigungu_indicators(base_ym);
CREATE INDEX idx_cache_sigungu_indicators_sido ON cache_sigungu_indicators(sido_nm);
CREATE INDEX idx_cache_sigungu_indicators_code ON cache_sigungu_indicators(sigungu_code);
```

---

### 2.6 cache_sigungu_age_summary (시군구별 연령그룹 요약)

**목적**: 연령 카테고리별 인구와 1인가구 통계 저장

| 컬럼명 | 데이터타입 | PK | NULL | 설명 |
|--------|-----------|:--:|:----:|------|
| base_ym | DATE | ✓ | N | 기준연월 |
| sigungu_code | VARCHAR(5) | ✓ | N | 시군구코드 |
| age_category | SMALLINT | ✓ | N | 카테고리 (1:연대별, 2:정책연령, 3:생애주기) |
| age_group_name | VARCHAR(20) | ✓ | N | 연령그룹명 |
| male_pop | INTEGER | | N | 남자인구 |
| female_pop | INTEGER | | N | 여자인구 |
| total_pop | INTEGER | | N | 총인구 |
| male_single | INTEGER | | N | 남자 1인가구 |
| female_single | INTEGER | | N | 여자 1인가구 |
| total_single | INTEGER | | N | 총 1인가구 |
| single_ratio | NUMERIC(8,2) | | N | 1인가구 비율 |

**age_category 값**:
| 카테고리 | 설명 | 연령그룹 예시 |
|---------|------|--------------|
| 1 | 연대별 | 0대, 10대, 20대, 30대, 40대, 50대, 60대, 70대, 80대, 90대, 100세이상 |
| 2 | 정책연령 | 유소년(0~14), 생산가능(15~64), 고령(65+), 초고령(80+) |
| 3 | 생애주기 | 영유아(0~6), 학령기(7~18), 청년(19~34), 중년(35~49), 장년(50~64), 노년(65+) |

---

### 2.7 mv_sigungu_population_by_age (시군구별 1세별 인구 MV)

**목적**: 시군구 단위로 집계된 1세별 인구 데이터 (빠른 조회용)

| 컬럼명 | 데이터타입 | 설명 |
|--------|-----------|------|
| base_ym | DATE | 기준연월 |
| sido_nm | VARCHAR(20) | 시도명 |
| sigungu_code | VARCHAR(5) | 시군구코드 |
| sigungu_nm | VARCHAR(30) | 시군구명 |
| total_pop | INTEGER | 총인구 |
| male_total | INTEGER | 남자 총인구 |
| female_total | INTEGER | 여자 총인구 |
| male_age_0 ~ male_age_109 | INTEGER | 남자 0~109세 |
| male_age_110_over | INTEGER | 남자 110세 이상 |
| female_age_0 ~ female_age_109 | INTEGER | 여자 0~109세 |
| female_age_110_over | INTEGER | 여자 110세 이상 |

**생성 SQL 패턴**:
```sql
CREATE MATERIALIZED VIEW mv_sigungu_population_by_age AS
SELECT
    a.base_ym,
    d.sido_nm,
    d.sigungu_code,
    d.sigungu_nm,
    SUM(a.total_pop) as total_pop,
    SUM(a.male_total) as male_total,
    SUM(a.female_total) as female_total,
    SUM(a.male_age_0) as male_age_0,
    SUM(a.female_age_0) as female_age_0,
    -- ... 모든 연령 컬럼
    SUM(a.male_age_110_over) as male_age_110_over,
    SUM(a.female_age_110_over) as female_age_110_over
FROM fact_population_by_age a
JOIN dim_admin_area d ON a.admin_code = d.admin_code
WHERE d.sigungu_code IS NOT NULL
GROUP BY a.base_ym, d.sido_nm, d.sigungu_code, d.sigungu_nm;
```

---

### 2.8 mv_sigungu_single_household (시군구별 1세별 1인가구 MV)

**목적**: 시군구 단위로 집계된 1세별 1인가구 데이터

구조는 `mv_sigungu_population_by_age`와 동일 (total_pop → total_cnt)

---

## 3. 테이블 관계 및 조인

### 3.1 관계 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JOIN 관계도                                     │
└─────────────────────────────────────────────────────────────────────────────┘

                           dim_admin_area
                          ┌─────────────┐
                          │ admin_code  │ (PK, 10자리)
                          │ sigungu_code│ (5자리)
                          │ sido_nm     │
                          │ sigungu_nm  │
                          │ region_code │ ← 권역 정보는 여기만 있음!
                          │ region_nm   │
                          └──────┬──────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
            ▼                    ▼                    ▼
   fact_population_basic  fact_population_by_age  fact_single_household
   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
   │ base_ym    (PK) │    │ base_ym    (PK) │    │ base_ym    (PK) │
   │ admin_code (PK) │    │ admin_code (PK) │    │ admin_code (PK) │
   │ total_pop       │    │ male_age_0~110  │    │ male_age_0~110  │
   │ male_pop        │    │ female_age_0~110│    │ female_age_0~110│
   │ female_pop      │    └─────────────────┘    └─────────────────┘
   │ household_cnt   │
   └─────────────────┘

   ※ 조인 키: admin_code (10자리)
```

### 3.2 조인 패턴

**패턴 1: 읍면동 단위 조회**
```sql
SELECT
    d.sido_nm, d.sigungu_nm, d.eupmyeondong_nm,
    p.total_pop, p.male_pop, p.female_pop
FROM fact_population_basic p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE d.eupmyeondong_nm IS NOT NULL;
```

**패턴 2: 시군구 단위 집계**
```sql
SELECT
    d.sido_nm, d.sigungu_nm,
    SUM(p.total_pop) AS total_pop
FROM fact_population_basic p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE d.sigungu_code LIKE '____0'  -- 대표 시군구만
GROUP BY d.sido_nm, d.sigungu_nm;
```

**패턴 3: 권역별 조회 (dim_admin_area 필수)**
```sql
SELECT
    d.region_nm,
    SUM(c.total_pop) AS total_pop,
    AVG(c.elderly_ratio) AS avg_elderly_ratio
FROM cache_sigungu_indicators c
JOIN dim_admin_area d ON c.sigungu_code = d.sigungu_code
WHERE d.region_nm = '수도권'
GROUP BY d.region_nm;
```

---

## 4. 지표 계산식

### 4.1 인구 구조 지표

| 지표명 | 영문 컬럼명 | 계산식 | 단위 | 해석 |
|--------|------------|--------|------|------|
| 고령화율 | elderly_ratio | (65세+ 인구 / 총인구) × 100 | % | 전체 인구 중 고령인구 비율 |
| 유소년율 | youth_ratio | (0~14세 인구 / 총인구) × 100 | % | 전체 인구 중 유소년 비율 |
| 생산가능인구율 | working_ratio | (15~64세 인구 / 총인구) × 100 | % | 전체 인구 중 생산가능인구 비율 |

### 4.2 부양 관련 지표

| 지표명 | 영문 컬럼명 | 계산식 | 단위 | 해석 |
|--------|------------|--------|------|------|
| 고령화지수 | aging_index | (65세+ 인구 / 0~14세 인구) × 100 | - | 유소년 100명당 고령인구 수 |
| 유소년부양비 | youth_dependency_ratio | (0~14세 인구 / 15~64세 인구) × 100 | - | 생산가능인구 100명당 부양해야 할 유소년 수 |
| 노년부양비 | elderly_dependency_ratio | (65세+ 인구 / 15~64세 인구) × 100 | - | 생산가능인구 100명당 부양해야 할 고령인구 수 |
| 총부양비 | (계산) | 유소년부양비 + 노년부양비 | - | 생산가능인구가 부양해야 할 총 인구 비율 |

**부양비 해석 예시**:
```
노년부양비 = 40 의미:
"생산가능인구(15~64세) 100명이 고령인구(65세+) 40명을 부양해야 함"
= 2.5명의 생산가능인구가 1명의 고령인구를 부양

유소년부양비 = 20 + 노년부양비 = 40 → 총부양비 = 60
"생산가능인구 100명이 유소년+고령 60명을 부양해야 함"
```

### 4.3 가구 관련 지표

| 지표명 | 영문 컬럼명 | 계산식 | 단위 | 해석 |
|--------|------------|--------|------|------|
| 1인가구비율 | single_ratio | (1인가구수 / 총세대수) × 100 | % | 전체 세대 중 1인가구 비율 |
| 세대당인구 | pop_per_house | 총인구 / 총세대수 | 명 | 한 세대당 평균 가구원 수 |

### 4.4 성비 지표

| 지표명 | 영문 컬럼명 | 계산식 | 단위 | 해석 |
|--------|------------|--------|------|------|
| 성비 | sex_ratio | (남자인구 / 여자인구) × 100 | - | 여자 100명당 남자 수 |

**성비 해석**:
- 성비 = 100: 남녀 동수
- 성비 > 100: 남초 (예: 105 = 여자 100명당 남자 105명)
- 성비 < 100: 여초 (예: 95 = 여자 100명당 남자 95명)

### 4.5 고령화 사회 기준

| 구분 | 고령인구 비율 | 고령화지수 기준 |
|------|--------------|----------------|
| 고령화사회 | 7% 이상 | 약 50 이상 |
| 고령사회 | 14% 이상 | 약 100 이상 |
| 초고령사회 | 20% 이상 | 약 150 이상 |

---

## 5. 연령 그룹 정의

### 5.1 정책 연령 그룹 (가장 많이 사용)

| 그룹명 | 연령 범위 | 컬럼 패턴 | 용도 |
|--------|----------|----------|------|
| 유소년 | 0 ~ 14세 | male_age_0 ~ male_age_14, female_age_0 ~ female_age_14 | 부양비 계산, 교육 정책 |
| 생산가능인구 | 15 ~ 64세 | male_age_15 ~ male_age_64, female_age_15 ~ female_age_64 | 부양비 계산, 경제활동 |
| 고령인구 | 65세 이상 | male_age_65 ~ male_age_110_over, female_age_65 ~ female_age_110_over | 고령화 지표, 복지 정책 |
| 초고령인구 | 80세 이상 | male_age_80 ~ male_age_110_over, female_age_80 ~ female_age_110_over | 돌봄 정책, 의료 서비스 |

### 5.2 연대별 그룹

| 그룹명 | 연령 범위 | SQL 패턴 |
|--------|----------|----------|
| 0대 | 0 ~ 9세 | male_age_0 + ... + male_age_9 + female_age_0 + ... + female_age_9 |
| 10대 | 10 ~ 19세 | male_age_10 + ... + male_age_19 + female_age_10 + ... + female_age_19 |
| 20대 | 20 ~ 29세 | male_age_20 + ... + male_age_29 + female_age_20 + ... + female_age_29 |
| 30대 | 30 ~ 39세 | (동일 패턴) |
| 40대 | 40 ~ 49세 | (동일 패턴) |
| 50대 | 50 ~ 59세 | (동일 패턴) |
| 60대 | 60 ~ 69세 | (동일 패턴) |
| 70대 | 70 ~ 79세 | (동일 패턴) |
| 80대 | 80 ~ 89세 | (동일 패턴) |
| 90대 | 90 ~ 99세 | (동일 패턴) |
| 100세 이상 | 100세+ | male_age_100 + ... + male_age_110_over + female_age_100 + ... + female_age_110_over |

### 5.3 연령 그룹 집계 SQL 예시

```sql
-- 65세 이상 고령인구 집계
SELECT
    d.sido_nm AS 시도,
    d.sigungu_nm AS 시군구,
    SUM(
        p.male_age_65 + p.male_age_66 + p.male_age_67 + p.male_age_68 + p.male_age_69 +
        p.male_age_70 + p.male_age_71 + p.male_age_72 + p.male_age_73 + p.male_age_74 +
        p.male_age_75 + p.male_age_76 + p.male_age_77 + p.male_age_78 + p.male_age_79 +
        p.male_age_80 + p.male_age_81 + p.male_age_82 + p.male_age_83 + p.male_age_84 +
        p.male_age_85 + p.male_age_86 + p.male_age_87 + p.male_age_88 + p.male_age_89 +
        p.male_age_90 + p.male_age_91 + p.male_age_92 + p.male_age_93 + p.male_age_94 +
        p.male_age_95 + p.male_age_96 + p.male_age_97 + p.male_age_98 + p.male_age_99 +
        p.male_age_100 + p.male_age_101 + p.male_age_102 + p.male_age_103 + p.male_age_104 +
        p.male_age_105 + p.male_age_106 + p.male_age_107 + p.male_age_108 + p.male_age_109 +
        p.male_age_110_over +
        p.female_age_65 + p.female_age_66 + p.female_age_67 + p.female_age_68 + p.female_age_69 +
        -- ... (여자도 동일 패턴)
        p.female_age_110_over
    ) AS 고령인구
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
GROUP BY d.sido_nm, d.sigungu_nm;
```

---

## 6. 용어 정규화 사전

### 6.1 시도명 정규화

| 사용자 입력 (가능한 변형) | 정규화된 값 |
|-------------------------|------------|
| 서울, 서울시, 서울특별시 | '서울특별시' |
| 부산, 부산시, 부산광역시 | '부산광역시' |
| 대구, 대구시, 대구광역시 | '대구광역시' |
| 인천, 인천시, 인천광역시 | '인천광역시' |
| 광주, 광주시, 광주광역시 | '광주광역시' |
| 대전, 대전시, 대전광역시 | '대전광역시' |
| 울산, 울산시, 울산광역시 | '울산광역시' |
| 세종, 세종시, 세종특별자치시 | '세종특별자치시' |
| 경기, 경기도 | '경기도' |
| 강원, 강원도, 강원특별자치도 | '강원특별자치도' |
| 충북, 충청북도 | '충청북도' |
| 충남, 충청남도 | '충청남도' |
| 전북, 전라북도, 전북특별자치도 | '전북특별자치도' |
| 전남, 전라남도 | '전라남도' |
| 경북, 경상북도 | '경상북도' |
| 경남, 경상남도 | '경상남도' |
| 제주, 제주도, 제주특별자치도 | '제주특별자치도' |

### 6.2 지표명 정규화

| 사용자 입력 (가능한 변형) | 정규화된 컬럼명 |
|-------------------------|----------------|
| 고령화율, 노인비율, 65세이상비율, 고령인구비율 | elderly_ratio |
| 유소년율, 유소년비율, 0-14세비율 | youth_ratio |
| 고령화지수, 노령화지수 | aging_index |
| 유소년부양비, 유년부양비 | youth_dependency_ratio |
| 노년부양비, 노인부양비, 고령부양비 | elderly_dependency_ratio |
| 1인가구, 단독가구, 독거, 1인세대 | single_household_cnt |
| 1인가구비율, 1인가구율, 단독가구비율 | single_ratio |
| 성비, 남녀성비 | sex_ratio |
| 세대수, 가구수 | household_cnt |
| 세대당인구, 가구당인구 | pop_per_house |

### 6.3 연령 표현 정규화

| 사용자 입력 | 해석 | 연령 범위 |
|------------|------|----------|
| 청년, 청년층 | 19~34세 | age_19 ~ age_34 |
| 중년, 중년층 | 35~49세 | age_35 ~ age_49 |
| 장년, 장년층 | 50~64세 | age_50 ~ age_64 |
| 노년, 노년층, 고령, 노인 | 65세 이상 | age_65 ~ age_110_over |
| 초고령, 후기고령자 | 80세 이상 | age_80 ~ age_110_over |
| MZ세대 | 대략 1980~2000년생 | 현재 기준 age_24 ~ age_44 (유동적) |
| 베이비붐 | 1955~1963년생 | 현재 기준 age_61 ~ age_69 (유동적) |

---

## 7. SQL 생성 규칙

### 7.1 기본 규칙

| 상황 | 규칙 | 예시 |
|------|------|------|
| 시점 미지정 | 최신 데이터 사용 | `WHERE base_ym = (SELECT MAX(base_ym) FROM 테이블)` |
| 순위/TOP N/상위 | 내림차순 정렬 | `ORDER BY 컬럼 DESC LIMIT N` |
| 낮은/하위/적은 | 오름차순 정렬 | `ORDER BY 컬럼 ASC LIMIT N` |
| NULL 처리 | NULL은 마지막 | `ORDER BY 컬럼 DESC NULLS LAST` |
| 비율 계산 | 소수점 2자리, 0 나눗셈 방지 | `ROUND(분자::NUMERIC / NULLIF(분모, 0) * 100, 2)` |
| 시군구 단위 (기본) | 대표 시군구만 | `WHERE sigungu_code LIKE '____0'` |
| 하위 시군구 구분 | 조건 없이 | sigungu_code 그대로 사용 |

### 7.2 컬럼 별칭 규칙 (필수)

```sql
-- 지역 관련
sido_nm AS 시도
sigungu_nm AS 시군구
eupmyeondong_nm AS 읍면동
region_nm AS 권역

-- 인구 관련
total_pop AS 총인구
male_pop AS 남자인구
female_pop AS 여자인구
youth_pop AS 유소년인구
working_pop AS 생산연령인구
elderly_pop AS 고령인구

-- 비율/지수
elderly_ratio AS 고령화율
youth_ratio AS 유소년율
working_ratio AS 생산연령인구율
aging_index AS 노령화지수
youth_dependency_ratio AS 유소년부양비
elderly_dependency_ratio AS 노년부양비
sex_ratio AS 성비

-- 가구 관련
household_cnt AS 세대수
single_household_cnt AS "1인가구수"
single_ratio AS "1인가구비율"
pop_per_house AS 세대당인구
```

### 7.3 안전한 SQL 패턴

```sql
-- 0으로 나누기 방지
ROUND(elderly_pop::NUMERIC / NULLIF(youth_pop, 0) * 100, 2) AS 고령화지수

-- NULL 처리
COALESCE(single_household_cnt, 0) AS "1인가구수"

-- 문자열 비교 (LIKE)
WHERE sido_nm LIKE '%경기%'  -- 부분 일치
WHERE sido_nm = '경기도'     -- 완전 일치 (권장)

-- 날짜 비교
WHERE base_ym >= '2024-01-01' AND base_ym < '2025-01-01'  -- 2024년 전체
WHERE base_ym = '2024-11-01'  -- 특정 월
```

---

## 8. 테이블 선택 가이드

### 8.1 의사결정 플로우차트

```
                          ┌─────────────────────────┐
                          │    어떤 지표가 필요?     │
                          └───────────┬─────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
     ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
     │ 정책지표       │     │ 사용자정의연령  │     │ 1인가구 연령별  │
     │ (고령화율,     │     │ (20대, 80세+   │     │                │
     │  부양비 등)    │     │  등 직접 합산)  │     │                │
     └───────┬────────┘     └───────┬────────┘     └───────┬────────┘
             │                       │                       │
             ▼                       ▼                       ▼
     ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
     │ cache_sigungu_ │     │ fact_population│     │ fact_single_   │
     │ indicators     │     │ _by_age        │     │ household      │
     │ (빠름, 추천)   │     │ 또는           │     │                │
     └────────────────┘     │ mv_sigungu_    │     └────────────────┘
                            │ population_    │
                            │ by_age         │
                            └────────────────┘
```

### 8.2 테이블별 용도

| 테이블 | 용도 | 단위 | 장점 | 단점 |
|--------|------|------|------|------|
| cache_sigungu_indicators | 정책지표 조회 | 시군구 | 빠름, 지표 계산 완료 | 연령 세부 불가 |
| cache_sigungu_age_summary | 연령그룹별 통계 | 시군구 | 그룹화 완료 | 커스텀 연령 불가 |
| mv_sigungu_population_by_age | 시군구 1세별 인구 | 시군구 | 유연한 연령 집계 | 조인 불필요 |
| mv_sigungu_single_household | 시군구 1세별 1인가구 | 시군구 | 유연한 연령 집계 | 조인 불필요 |
| fact_population_by_age | 읍면동 1세별 인구 | 읍면동 | 최소 단위 | 집계 필요 |
| fact_single_household | 읍면동 1세별 1인가구 | 읍면동 | 최소 단위 | 집계 필요 |
| fact_population_basic | 읍면동 기본 인구 | 읍면동 | 가벼움 | 연령 없음 |

### 8.3 선택 규칙 요약

```
IF 고령화율/유소년율/부양비/1인가구비율 등 정책지표
   → cache_sigungu_indicators (가장 빠름)

IF 20대/30대/80세+ 등 사용자정의 연령 (시군구 단위)
   → mv_sigungu_population_by_age (조인 불필요)

IF 20대/30대/80세+ 등 사용자정의 연령 (읍면동 단위)
   → fact_population_by_age + dim_admin_area (조인 필요)

IF 1인가구 연령별 (시군구 단위)
   → mv_sigungu_single_household

IF 1인가구 연령별 (읍면동 단위)
   → fact_single_household + dim_admin_area

IF 권역별 조회
   → 어떤 테이블이든 dim_admin_area와 조인 필요 (권역 정보는 dim에만 있음)
```

---

## 9. 차트 및 시각화 규칙

### 9.1 차트 유형 선택

| 질문 유형 | 차트 유형 | 예시 |
|----------|----------|------|
| 순위/비교 | 가로막대 (barh) | "고령화율 높은 지역 Top 10" |
| 구성비 | 도넛 (donut) | "연령대별 인구 구성" |
| 시계열/추이 | 선 (line) | "최근 3년 고령화율 변화" |
| 남녀 비교/피라미드 | 양방향 가로막대 | "연령별 인구 피라미드" |
| 분포 | 히스토그램 | "고령화율 분포" |
| 지역 비교 | 막대/그룹막대 | "시도별 1인가구비율" |

### 9.2 색상 팔레트

```python
# 메인 색상 (순서대로 사용)
MAIN = ['#667EEA', '#764BA2', '#F24822', '#2ECC71', '#3498DB', '#F39C12', '#9B59B6', '#1ABC9C']

# 강조/1위 표시
HIGHLIGHT = '#F24822'  # 빨간색

# 성별 구분
GENDER = {
    'male': '#3498DB',    # 파란색 (남자)
    'female': '#E74C3C'   # 빨간색 (여자)
}

# 연령 그룹 구분
AGE = {
    'youth': '#2ECC71',     # 초록색 (유소년)
    'working': '#3498DB',   # 파란색 (생산가능)
    'elderly': '#E74C3C'    # 빨간색 (고령)
}

# 그라데이션 (순위/단계 표현)
GRADIENT = ['#1243A6', '#1D64F2', '#4A90E2', '#7EB6FF', '#B8D4FF']

# 증감 표현
COMPARE = {
    'increase': '#2ECC71',  # 초록색 (증가)
    'decrease': '#E74C3C',  # 빨간색 (감소)
    'neutral': '#95A5A6'    # 회색 (변동없음)
}
```

### 9.3 차트 스타일 가이드

- **제목**: 명확하고 구체적 (예: "2024년 11월 기준 고령화율 상위 10개 시군구")
- **축 레이블**: 한글 사용, 단위 명시 (예: "고령화율 (%)")
- **범례**: 필요시만 표시, 차트 외부 배치
- **데이터 레이블**: 막대/파이 차트에 값 표시
- **그리드**: 가로 그리드만 연하게 표시

---

## 10. 보고서 생성 규칙

### 10.1 SQL 성공 시 보고서 구조

```markdown
## 1. 개요
- **분석 목적**: [사용자 질문 요약]
- **기준 시점**: [YYYY년 MM월]
- **분석 범위**: [전국/특정 시도/특정 시군구]
- **데이터 출처**: 행정안전부 주민등록인구통계

## 2. 주요 지표 요약
| 지표 | 값 | 비고 |
|------|-----|------|
| [지표1] | [값] | [전국 평균 대비 등] |
| [지표2] | [값] | |
| [지표3] | [값] | |

## 3. 상세 결과
[테이블 또는 차트]

## 4. 인사이트 (5개)
1. **1위/최고값 특성**: [1위 지역의 특성 분석]
2. **평균 대비 비교**: [전국/시도 평균과 비교]
3. **특이값/이상치**: [유일하게 증가/감소하는 지역 등]
4. **비율/구조 분석**: [초고령사회 20%+ 해당 여부 등]
5. **추세/변화**: [전월/전년 대비 변화 - 데이터 있을 경우]

## 5. 시사점 및 추가 질문 제안
- [정책적 시사점]
- **추가 질문 제안**:
  1. [관련 심화 질문 1]
  2. [관련 심화 질문 2]
  3. [관련 심화 질문 3]
```

### 10.2 SQL 실패 시 응답 구조

```markdown
## 분석 불가 안내

### 1. 제한 사유
- [데이터가 없는 이유 또는 요청이 처리 불가한 이유]

### 2. 분석 가능한 데이터
- **인구 데이터**: 총인구, 남녀인구, 연령별 인구 (0~110세+)
- **가구 데이터**: 세대수, 1인가구수, 연령별 1인가구
- **지역 단위**: 시도, 시군구, 읍면동
- **시간 범위**: [사용 가능한 시간 범위]

### 3. 대안 질문 제안
1. [대안 질문 1]
2. [대안 질문 2]
3. [대안 질문 3]
```

---

## 11. 예시 SQL 패턴

### 11.1 고령화율 순위 (cache 사용 - 권장)

```sql
-- 전국 고령화율 상위 10개 시군구
SELECT
    sido_nm AS 시도,
    sigungu_nm AS 시군구,
    elderly_ratio AS 고령화율,
    total_pop AS 총인구,
    elderly_pop AS 고령인구
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sigungu_code LIKE '____0'
ORDER BY elderly_ratio DESC NULLS LAST
LIMIT 10;
```

### 11.2 특정 시도 내 시군구 비교

```sql
-- 경기도 시군구별 1인가구 현황
SELECT
    sigungu_nm AS 시군구,
    single_ratio AS "1인가구비율",
    single_household_cnt AS "1인가구수",
    household_cnt AS 총세대수
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sido_nm = '경기도'
  AND sigungu_code LIKE '____0'
ORDER BY single_ratio DESC NULLS LAST;
```

### 11.3 부양비 분석

```sql
-- 노년부양비 상위 지역 (생산가능인구 부담이 큰 지역)
SELECT
    sido_nm AS 시도,
    sigungu_nm AS 시군구,
    elderly_dependency_ratio AS 노년부양비,
    youth_dependency_ratio AS 유소년부양비,
    (elderly_dependency_ratio + youth_dependency_ratio) AS 총부양비,
    working_pop AS 생산연령인구,
    elderly_pop AS 고령인구
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sigungu_code LIKE '____0'
ORDER BY elderly_dependency_ratio DESC NULLS LAST
LIMIT 20;
```

### 11.4 20대 인구 비율 (MV 사용)

```sql
-- 시군구별 20대 인구 비율 (청년 유출/유입 분석)
SELECT
    sido_nm AS 시도,
    sigungu_nm AS 시군구,
    (male_age_20 + male_age_21 + male_age_22 + male_age_23 + male_age_24 +
     male_age_25 + male_age_26 + male_age_27 + male_age_28 + male_age_29 +
     female_age_20 + female_age_21 + female_age_22 + female_age_23 + female_age_24 +
     female_age_25 + female_age_26 + female_age_27 + female_age_28 + female_age_29) AS "20대인구",
    total_pop AS 총인구,
    ROUND(
        (male_age_20 + male_age_21 + male_age_22 + male_age_23 + male_age_24 +
         male_age_25 + male_age_26 + male_age_27 + male_age_28 + male_age_29 +
         female_age_20 + female_age_21 + female_age_22 + female_age_23 + female_age_24 +
         female_age_25 + female_age_26 + female_age_27 + female_age_28 + female_age_29)::NUMERIC
        / NULLIF(total_pop, 0) * 100, 2
    ) AS "20대비율"
FROM mv_sigungu_population_by_age
WHERE base_ym = (SELECT MAX(base_ym) FROM mv_sigungu_population_by_age)
  AND sigungu_code LIKE '____0'
ORDER BY "20대비율" DESC
LIMIT 10;
```

### 11.5 읍면동 단위 80세+ 비율

```sql
-- 읍면동별 초고령인구(80세+) 비율
SELECT
    d.sido_nm AS 시도,
    d.sigungu_nm AS 시군구,
    d.eupmyeondong_nm AS 읍면동,
    (p.male_total + p.female_total) AS 총인구,
    (p.male_age_80 + p.male_age_81 + p.male_age_82 + p.male_age_83 + p.male_age_84 +
     p.male_age_85 + p.male_age_86 + p.male_age_87 + p.male_age_88 + p.male_age_89 +
     p.male_age_90 + p.male_age_91 + p.male_age_92 + p.male_age_93 + p.male_age_94 +
     p.male_age_95 + p.male_age_96 + p.male_age_97 + p.male_age_98 + p.male_age_99 +
     p.male_age_100 + p.male_age_101 + p.male_age_102 + p.male_age_103 + p.male_age_104 +
     p.male_age_105 + p.male_age_106 + p.male_age_107 + p.male_age_108 + p.male_age_109 +
     p.male_age_110_over +
     p.female_age_80 + p.female_age_81 + p.female_age_82 + p.female_age_83 + p.female_age_84 +
     p.female_age_85 + p.female_age_86 + p.female_age_87 + p.female_age_88 + p.female_age_89 +
     p.female_age_90 + p.female_age_91 + p.female_age_92 + p.female_age_93 + p.female_age_94 +
     p.female_age_95 + p.female_age_96 + p.female_age_97 + p.female_age_98 + p.female_age_99 +
     p.female_age_100 + p.female_age_101 + p.female_age_102 + p.female_age_103 + p.female_age_104 +
     p.female_age_105 + p.female_age_106 + p.female_age_107 + p.female_age_108 + p.female_age_109 +
     p.female_age_110_over) AS "80세이상",
    ROUND(
        (위의 80세이상 합계)::NUMERIC / NULLIF(p.male_total + p.female_total, 0) * 100, 2
    ) AS "80세이상비율"
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
  AND d.eupmyeondong_nm IS NOT NULL
  AND (p.male_total + p.female_total) > 0
ORDER BY "80세이상비율" DESC NULLS LAST
LIMIT 20;
```

### 11.6 권역별 집계

```sql
-- 권역별 평균 고령화율 및 인구
SELECT
    d.region_nm AS 권역,
    COUNT(DISTINCT c.sigungu_code) AS 시군구수,
    SUM(c.total_pop) AS 총인구,
    ROUND(AVG(c.elderly_ratio), 2) AS 평균고령화율,
    ROUND(AVG(c.aging_index), 2) AS 평균고령화지수,
    ROUND(AVG(c.elderly_dependency_ratio), 2) AS 평균노년부양비
FROM cache_sigungu_indicators c
JOIN dim_admin_area d ON c.sigungu_code = d.sigungu_code
WHERE c.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND c.sigungu_code LIKE '____0'
  AND d.region_nm IS NOT NULL
GROUP BY d.region_nm
ORDER BY 평균고령화율 DESC;
```

### 11.7 시계열 분석

```sql
-- 특정 시군구의 고령화율 추이 (최근 12개월)
SELECT
    base_ym AS 기준월,
    elderly_ratio AS 고령화율,
    elderly_pop AS 고령인구,
    total_pop AS 총인구
FROM cache_sigungu_indicators
WHERE sido_nm = '경상북도'
  AND sigungu_nm = '군위군'
  AND base_ym >= (SELECT MAX(base_ym) - INTERVAL '11 months' FROM cache_sigungu_indicators)
ORDER BY base_ym;
```

---

## 12. ERD 다이어그램

### 12.1 전체 ERD

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    전체 ERD                                              │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                 ┌───────────────────────────┐
                                 │      dim_admin_area       │
                                 ├───────────────────────────┤
                                 │ PK: admin_code (10자리)   │
                                 │     sido_code             │
                                 │     sido_nm               │
                                 │     sigungu_code (5자리)  │◄─────────────────────────┐
                                 │     sigungu_nm            │                          │
                                 │     eupmyeondong_code     │                          │
                                 │     eupmyeondong_nm       │                          │
                                 │     region_code           │ ← 권역 정보              │
                                 │     region_nm             │                          │
                                 └─────────────┬─────────────┘                          │
                                               │                                         │
                    ┌──────────────────────────┼──────────────────────────┐              │
                    │                          │                          │              │
                    ▼                          ▼                          ▼              │
         ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐     │
         │ fact_population_ │       │ fact_population_ │       │ fact_single_     │     │
         │ basic            │       │ by_age           │       │ household        │     │
         ├──────────────────┤       ├──────────────────┤       ├──────────────────┤     │
         │ PK: base_ym      │       │ PK: base_ym      │       │ PK: base_ym      │     │
         │ PK: admin_code ──┼───────┤ PK: admin_code ──┼───────┤ PK: admin_code   │     │
         │     total_pop    │  FK   │     total_pop    │  FK   │     total_cnt    │     │
         │     male_pop     │       │     male_total   │       │     male_total   │     │
         │     female_pop   │       │     female_total │       │     female_total │     │
         │     household_cnt│       │     male_age_0~  │       │     male_age_0~  │     │
         │                  │       │       110_over   │       │       110_over   │     │
         │                  │       │     female_age_0~│       │     female_age_0~│     │
         │                  │       │       110_over   │       │       110_over   │     │
         └──────────────────┘       └──────────────────┘       └──────────────────┘     │
                    │                          │                          │              │
                    └──────────────────────────┼──────────────────────────┘              │
                                               │                                         │
                                               ▼ GROUP BY sigungu_code                   │
                                               │                                         │
         ┌─────────────────────────────────────┼─────────────────────────────────────┐   │
         │                                     │                                     │   │
         ▼                                     ▼                                     ▼   │
┌─────────────────────┐             ┌─────────────────────┐             ┌─────────────────────┐
│ cache_sigungu_      │             │ mv_sigungu_         │             │ mv_sigungu_         │
│ indicators          │             │ population_by_age   │             │ single_household    │
├─────────────────────┤             ├─────────────────────┤             ├─────────────────────┤
│ PK: base_ym         │             │ base_ym             │             │ base_ym             │
│ PK: sigungu_code ───┼─────────────┤ sigungu_code ───────┼─────────────┤ sigungu_code ───────┼──┘
│     sido_nm         │     JOIN    │ sido_nm             │     JOIN    │ sido_nm             │
│     sigungu_nm      │             │ sigungu_nm          │             │ sigungu_nm          │
│     total_pop       │             │ total_pop           │             │ total_cnt           │
│     male_pop        │             │ male_total          │             │ male_total          │
│     female_pop      │             │ female_total        │             │ female_total        │
│     elderly_ratio   │             │ male_age_0~110_over │             │ male_age_0~110_over │
│     youth_ratio     │             │ female_age_0~110_over             │ female_age_0~110_over
│     aging_index     │             └─────────────────────┘             └─────────────────────┘
│     youth_dependency│
│     _ratio          │
│     elderly_        │
│     dependency_ratio│
│     single_ratio    │
│     pop_per_house   │
│     sex_ratio       │
└─────────────────────┘
```

### 12.2 조인 관계 요약

| From | To | 조인 키 | 관계 |
|------|----|--------|------|
| fact_population_basic | dim_admin_area | admin_code | N:1 |
| fact_population_by_age | dim_admin_area | admin_code | N:1 |
| fact_single_household | dim_admin_area | admin_code | N:1 |
| cache_sigungu_indicators | dim_admin_area | sigungu_code | N:1 (권역 조회시) |
| mv_sigungu_* | dim_admin_area | sigungu_code | N:1 (권역 조회시) |

---

## 13. 데이터 흐름

### 13.1 수집 → 저장 → 캐시 흐름

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              데이터 수집 및 처리 흐름                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  공공데이터포털   │     │   api_to_db.py  │     │   PostgreSQL    │     │  transfer.py   │
│  (data.go.kr)   │     │   (수집 스크립트) │     │   (원본 저장)    │     │  (캐시 생성)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │                       │
         │   4개 API 호출         │                       │                       │
         │ ─────────────────────▶│                       │                       │
         │                       │                       │                       │
         │   - 인구기본           │   Wide Format 변환    │                       │
         │   - 1세별 인구         │ ─────────────────────▶│                       │
         │   - 1세별 1인가구      │                       │                       │
         │   - 행정구역           │   Fact 테이블 저장    │                       │
         │                       │   (읍면동 단위)        │                       │
         │                       │                       │                       │
         │                       │                       │   시군구 단위 집계     │
         │                       │                       │ ─────────────────────▶│
         │                       │                       │                       │
         │                       │                       │   Cache 테이블 생성   │
         │                       │                       │ ◀─────────────────────│
         │                       │                       │                       │
         │                       │                       │   MV 생성/갱신        │
         │                       │                       │ ◀─────────────────────│
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    조회 흐름                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  대시보드/챗봇   │     │   PostgreSQL    │     │   응답 생성     │
│  (사용자 질문)   │     │   (데이터 조회)  │     │   (시각화/보고서)│
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │   "고령화율 높은 지역?"│                       │
         │ ─────────────────────▶│                       │
         │                       │                       │
         │                       │   cache_sigungu_      │
         │                       │   indicators 조회     │
         │                       │   (빠름!)             │
         │                       │                       │
         │   결과 반환            │                       │
         │ ◀─────────────────────│                       │
         │                       │                       │
         │   차트/보고서 생성     │                       │
         │ ─────────────────────────────────────────────▶│
         │                       │                       │
         ▼                       ▼                       ▼
```

### 13.2 월별 데이터 갱신 프로세스

```bash
# 1. API에서 새 데이터 수집
python api_to_db.py --month 202412

# 2. 캐시 테이블 및 MV 갱신
python transfer.py --refresh

# 또는 특정 월만 갱신
python transfer.py --month 202412
```

---

## 부록: 존재하지 않는 것들 (주의!)

### ❌ 존재하지 않는 테이블

| 잘못된 테이블명 | 올바른 대안 |
|---------------|------------|
| fact_population_age_group | fact_population_by_age (1세별 컬럼 사용) |
| cache_population_summary | cache_sigungu_indicators |
| dim_age_group | (없음 - 연령그룹은 SQL로 직접 계산) |

### ❌ 존재하지 않는 컬럼

| 잘못된 컬럼명 | 올바른 대안 |
|-------------|------------|
| male_80_89 | male_age_80 + male_age_81 + ... + male_age_89 |
| female_0_14 | female_age_0 + female_age_1 + ... + female_age_14 |
| age_group | (없음 - 1세별 컬럼만 존재) |
| total_dependency_ratio | youth_dependency_ratio + elderly_dependency_ratio |

### ✅ 올바른 컬럼 패턴

```sql
-- 1세별 컬럼 패턴
male_age_0, male_age_1, ..., male_age_109, male_age_110_over
female_age_0, female_age_1, ..., female_age_109, female_age_110_over

-- 연령 그룹 집계는 항상 1세별 컬럼의 합으로 계산
SUM(male_age_0 + male_age_1 + ... + male_age_14) AS 유소년_남자
```

---

*최종 수정: 2026-01-16 | 상세 온톨로지 (토큰 제약 없음)*
