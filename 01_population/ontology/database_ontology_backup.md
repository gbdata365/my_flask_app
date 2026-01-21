# 인구통계 데이터베이스 온톨로지

이 문서는 LLM이 자연어 질문을 SQL로 변환할 때 참조하는 데이터베이스 스키마 및 도메인 지식입니다.

## 1. 데이터베이스 개요

- **데이터베이스**: PostgreSQL
- **스키마**: public
- **도메인**: 대한민국 인구통계 데이터
- **데이터 기준**: 행정안전부 주민등록인구통계

---

## 2. 핵심 테이블

### 2.1 dim_admin_area (행정구역 차원 테이블)
행정구역 정보를 담고 있는 마스터 테이블입니다.

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|-----------|------|------|
| admin_code | VARCHAR | 행정구역코드 (PK, 10자리) | '1100000000' |
| sido_nm | VARCHAR | 시도명 | '서울특별시' |
| sigungu_nm | VARCHAR | 시군구명 | '강남구' |
| sigungu_code | VARCHAR | 시군구코드 (5자리) | '11680' |
| region_nm | VARCHAR | 권역명 | '수도권' |

**참고사항**:
- `sigungu_code`의 5번째 자리가 '0'이면 일반 시군구, '0'이 아니면 하위행정구(자치구)
- 예: '11680' = 강남구, '11215' = 광진구 내 하위구역

### 2.2 fact_population_basic (인구 기본 팩트 테이블)
월별 인구 기본 통계입니다.

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|-----------|------|------|
| base_ym | VARCHAR | 기준년월 (YYYYMM) | '202411' |
| admin_code | VARCHAR | 행정구역코드 (FK) | '1100000000' |
| total_pop | INTEGER | 총인구수 | 9,550,227 |
| male_pop | INTEGER | 남자인구수 | 4,648,512 |
| female_pop | INTEGER | 여자인구수 | 4,901,715 |
| household_cnt | INTEGER | 세대수 (가구수) | 4,527,283 |

### 2.3 fact_population_by_age (1세별 인구 팩트 테이블) ⭐중요
월별 **1세 단위** 인구 통계입니다. 연령별 집계 시 반드시 이 테이블 사용!

| 컬럼명 | 데이터타입 | 설명 |
|--------|-----------|------|
| base_ym | DATE | 기준년월 (YYYY-MM-01 형식) |
| admin_code | VARCHAR | 행정구역코드 (FK) |
| total_pop | INTEGER | 총인구수 |
| male_total | INTEGER | 남자 총인구 |
| female_total | INTEGER | 여자 총인구 |
| male_age_0 | INTEGER | 남자 0세 |
| female_age_0 | INTEGER | 여자 0세 |
| male_age_1 | INTEGER | 남자 1세 |
| female_age_1 | INTEGER | 여자 1세 |
| ... | ... | (2세~109세까지 동일 패턴) |
| male_age_110_over | INTEGER | 남자 110세 이상 |
| female_age_110_over | INTEGER | 여자 110세 이상 |

**컬럼 명명 규칙:**
- 남자: `male_age_N` (N = 0~109) + `male_age_110_over`
- 여자: `female_age_N` (N = 0~109) + `female_age_110_over`

### 2.4 fact_single_household (1인가구 1세별 팩트 테이블)
월별 **1세 단위** 1인가구 통계입니다.

| 컬럼명 | 데이터타입 | 설명 |
|--------|-----------|------|
| base_ym | DATE | 기준년월 |
| admin_code | VARCHAR | 행정구역코드 (FK) |
| total_cnt | INTEGER | 1인가구 총수 |
| male_total | INTEGER | 남자 1인가구 총수 |
| female_total | INTEGER | 여자 1인가구 총수 |
| male_age_0 | INTEGER | 남자 0세 1인가구 |
| female_age_0 | INTEGER | 여자 0세 1인가구 |
| ... | ... | (1세~109세까지 동일 패턴) |
| male_age_110_over | INTEGER | 남자 110세 이상 1인가구 |
| female_age_110_over | INTEGER | 여자 110세 이상 1인가구 |

### 2.5 cache_sigungu_indicators (시군구 지표 캐시 테이블)
시군구별 주요 지표를 미리 계산해둔 캐시 테이블입니다. **조회 성능이 중요할 때 이 테이블 사용을 권장합니다.**

| 컬럼명 | 데이터타입 | 설명 |
|--------|-----------|------|
| base_ym | VARCHAR | 기준년월 |
| sido_nm | VARCHAR | 시도명 |
| sigungu_nm | VARCHAR | 시군구명 |
| total_pop | INTEGER | 총인구 |
| male_pop | INTEGER | 남자인구 |
| female_pop | INTEGER | 여자인구 |
| household_cnt | INTEGER | 총가구수 |
| elderly_pop | INTEGER | 65세 이상 인구 |
| elderly_ratio | DECIMAL | 고령화율 (%) |
| youth_pop | INTEGER | 유소년인구 (0-14세) |
| youth_ratio | DECIMAL | 유소년율 (%) |
| working_pop | INTEGER | 생산연령인구 (15-64세) |
| sex_ratio | DECIMAL | 성비 (남/여 * 100) |
| aging_index | DECIMAL | 노령화지수 (노인/유소년 * 100) |
| single_household_cnt | INTEGER | 1인가구수 |
| single_ratio | DECIMAL | 1인가구비율 (%) |

---

## 3. 주요 View

### 3.1 v_sigungu_population
시군구별 인구 (하위행정구 합산 적용)

### 3.2 v_sigungu_age_group
시군구별 연령대 인구 (하위행정구 합산 적용)

### 3.3 v_sigungu_population_rank
시군구별 인구 순위 (최신월 기준)

---

## 4. 도메인 용어 사전

### 4.1 시도명 매핑
자연어에서 사용되는 다양한 표현을 정규화합니다.

| 자연어 표현 | 정규화된 시도명 |
|------------|----------------|
| 서울, 서울시 | 서울특별시 |
| 부산, 부산시 | 부산광역시 |
| 대구, 대구시 | 대구광역시 |
| 인천, 인천시 | 인천광역시 |
| 광주, 광주시 | 광주광역시 |
| 대전, 대전시 | 대전광역시 |
| 울산, 울산시 | 울산광역시 |
| 세종, 세종시 | 세종특별자치시 |
| 경기, 경기도 | 경기도 |
| 강원, 강원도 | 강원특별자치도 |
| 충북, 충청북도 | 충청북도 |
| 충남, 충청남도 | 충청남도 |
| 전북, 전라북도 | 전북특별자치도 |
| 전남, 전라남도 | 전라남도 |
| 경북, 경상북도 | 경상북도 |
| 경남, 경상남도 | 경상남도 |
| 제주, 제주도 | 제주특별자치도 |

### 4.2 지표 용어 매핑

| 자연어 표현 | 컬럼명 | 설명 |
|------------|--------|------|
| 인구, 총인구, 인구수 | total_pop | 총인구수 |
| 남자, 남성, 남자인구 | male_pop | 남자인구수 |
| 여자, 여성, 여자인구 | female_pop | 여자인구수 |
| 가구, 세대, 가구수 | household_cnt | 총세대수 |
| 고령화율, 노인비율, 65세이상비율 | elderly_ratio | 65세 이상 인구 비율 |
| 노인인구, 고령인구, 65세이상 | elderly_pop | 65세 이상 인구수 |
| 유소년, 어린이, 아이 | youth_pop | 0-14세 인구수 |
| 유소년율, 유소년비율 | youth_ratio | 0-14세 인구 비율 |
| 생산인구, 경제활동인구 | working_pop | 15-64세 인구수 |
| 성비 | sex_ratio | 여자 100명당 남자 수 |
| 노령화지수 | aging_index | 유소년 100명당 노인 수 |
| 1인가구, 단독가구, 독거 | single_household_cnt | 1인가구수 |
| 1인가구비율, 1인가구율 | single_ratio | 1인가구 비율 |

### 4.3 정렬/순위 표현

| 자연어 표현 | SQL 표현 |
|------------|----------|
| 높은, 많은, 큰, 최고, 상위, TOP | ORDER BY ... DESC |
| 낮은, 적은, 작은, 최저, 하위 | ORDER BY ... ASC |

### 4.4 개수 표현

| 자연어 표현 | 추출 방법 |
|------------|----------|
| "10개", "10위", "TOP 10", "상위 10" | LIMIT 10 |

---

## 5. SQL 생성 규칙

### 5.1 기본 규칙
1. **최신 데이터**: 특정 시점이 언급되지 않으면 최신 base_ym 사용
   ```sql
   WHERE base_ym = (SELECT MAX(base_ym) FROM table_name)
   ```

2. **시군구 단위 조회**: `cache_sigungu_indicators` 테이블 우선 사용

3. **NULL 처리**: 정렬 시 NULL은 마지막으로
   ```sql
   ORDER BY column_name DESC NULLS LAST
   ```

### 5.2 JOIN 규칙
- 상세 데이터 필요 시: `fact_*` 테이블과 `dim_admin_area` JOIN
- 집계 데이터: `cache_sigungu_indicators` 직접 사용

### 5.3 시군구 코드 구분 규칙 (매우 중요!) ⭐

**sigungu_code 구조:**
- 5자리 코드: 예) '11680', '41111'
- 앞 4자리: 기본 시군구 코드 (예: '4111' = 수원시)
- 5번째 자리: '0'이면 대표 시군구, '0'이 아니면 하위행정구(자치구)
- 예: 수원시 → 41110(대표), 41111(장안구), 41113(권선구), 41115(팔달구), 41117(영통구)

**질의 시 기본 규칙 (기본값: 하위시군구 합산):**
| 사용자 표현 | 처리 방식 | 설명 |
|------------|----------|------|
| "시군구", "시군구별" (기본) | 4자리 기준 합산 | 수원시 전체 = 장안구+권선구+팔달구+영통구 합산 |
| "하위시군구 구분", "세부 시군구", "자치구별" | 5자리 기준 개별 | 수원시 장안구, 수원시 권선구 각각 표시 |

**핵심 SQL 패턴 (기본: 하위시군구 합산):**
```sql
-- ⭐ 기본 패턴: 4자리 그룹핑 + dim_admin_area에서 대표 시군구명 조회
-- 주의: dim_admin_area는 읍면동 단위이므로 DISTINCT 서브쿼리 필수!
SELECT
    d.sigungu_nm as 시군구,
    SUM(c.total_pop) as 총인구,
    SUM(c.elderly_pop) as 고령인구,
    ROUND(SUM(c.elderly_pop)::numeric / NULLIF(SUM(c.total_pop), 0) * 100, 2) as 고령화율,
    ROUND(SUM(c.elderly_pop)::numeric / NULLIF(SUM(c.youth_pop), 0) * 100, 2) as 노령화지수
FROM cache_sigungu_indicators c
JOIN (SELECT DISTINCT sigungu_code, sigungu_nm FROM dim_admin_area WHERE sigungu_nm IS NOT NULL) d
  ON LEFT(c.sigungu_code, 4) || '0' = d.sigungu_code
WHERE c.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
GROUP BY LEFT(c.sigungu_code, 4), d.sigungu_nm
ORDER BY 고령화율 DESC;

-- 특정 시도 조건 추가 시
SELECT
    d.sigungu_nm as 시군구,
    SUM(c.total_pop) as 총인구,
    ROUND(SUM(c.elderly_pop)::numeric / NULLIF(SUM(c.total_pop), 0) * 100, 2) as 고령화율
FROM cache_sigungu_indicators c
JOIN (SELECT DISTINCT sigungu_code, sigungu_nm, sido_nm FROM dim_admin_area WHERE sigungu_nm IS NOT NULL) d
  ON LEFT(c.sigungu_code, 4) || '0' = d.sigungu_code
WHERE c.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND d.sido_nm = '경기도'
GROUP BY LEFT(c.sigungu_code, 4), d.sigungu_nm
ORDER BY 고령화율 ASC
LIMIT 5;
```

**하위시군구 구분 시 (개별 표시):**
```sql
-- 하위시군구 구분: cache 테이블 그대로 사용
SELECT
    sigungu_nm as 시군구,
    total_pop as 총인구,
    elderly_ratio as 고령화율
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sido_nm = '경기도'
ORDER BY elderly_ratio ASC;
```

**주의사항:**
- `LEFT(sigungu_code, 4) || '0'`으로 dim_admin_area 조인해야 대표 시군구명(예: "수원시") 조회 가능
- 비율(고령화율, 노령화지수 등)은 합산 후 재계산 필요 (SUM 후 나눗셈)

### 5.4 결과 컬럼명 한글화 규칙 (필수!)

**SQL SELECT 절에서 반드시 한글 별칭(alias) 사용:**

| 영문 컬럼명 | 한글 별칭 |
|------------|----------|
| sido_nm | 시도 |
| sigungu_nm | 시군구 |
| sigungu_code | 시군구코드 |
| region_nm | 권역 |
| total_pop | 총인구 |
| male_pop | 남자인구 |
| female_pop | 여자인구 |
| household_cnt | 세대수 |
| elderly_pop | 고령인구 |
| elderly_ratio | 고령화율 |
| youth_pop | 유소년인구 |
| youth_ratio | 유소년율 |
| working_pop | 생산연령인구 |
| sex_ratio | 성비 |
| aging_index | 노령화지수 |
| single_household_cnt | 1인가구수 |
| single_ratio | 1인가구비율 |
| base_ym | 기준년월 |

**예시:**
```sql
-- 올바른 예시 (한글 별칭 사용)
SELECT sido_nm AS 시도,
       sigungu_nm AS 시군구,
       total_pop AS 총인구,
       elderly_ratio AS 고령화율
FROM cache_sigungu_indicators

-- 잘못된 예시 (영문 컬럼명 그대로)
SELECT sido_nm, sigungu_nm, total_pop, elderly_ratio  -- X
```

### 5.5 연령별 집계 규칙 (매우 중요!) ⭐

**테이블 선택 기준:**

| 질문 유형 | 사용 테이블 | 이유 |
|----------|------------|------|
| 고령화율, 유소년율, 생산가능인구 | `cache_sigungu_indicators` | 정책지표(category=3) 미리 계산됨 |
| 20대, 30대, 80세 이상 등 | `fact_population_by_age` | 사용자 정의 연령 → 직접 집계 |
| 1인가구 연령별 | `fact_single_household` | 1세별 1인가구 데이터 |

**cache_sigungu_indicators의 연령 컬럼 (code_age_group category=3 기준):**

| 컬럼명 | 연령 그룹 | code_age_group 매핑 |
|--------|----------|---------------------|
| youth_pop | 유소년 (0~14세) | code='0~14', code_name='유소년' |
| youth_ratio | 유소년율 (%) | 유소년/총인구*100 |
| working_pop | 생산가능인구 (15~64세) | code='15~64', code_name='생산가능인구' |
| elderly_pop | 고령인구 (65세+) | code='65~999', code_name='고령인구' |
| elderly_ratio | 고령화율 (%) | 고령/총인구*100 |
| aging_index | 노령화지수 | 고령/유소년*100 |

> **참고**: code_age_group 테이블의 category=3 (정책지표)와 동일한 분류입니다.
> 연령 그룹 정의를 변경하려면 code_age_group 테이블을 수정하세요.

**fact_population_by_age 사용이 필요한 경우:**
- 10대, 20대, 30대 등 10년 단위 집계
- 청년(15~34세), 중장년(35~64세) 등 사용자 정의 그룹
- 초고령(80세+, 85세+) 등 세부 연령
- code_age_group의 다른 카테고리(category=1, 2) 기준 집계

**연령 그룹 집계 방법:**
```sql
-- 0~14세 (유소년) 인구 집계
SUM(male_age_0 + male_age_1 + ... + male_age_14 +
    female_age_0 + female_age_1 + ... + female_age_14) AS 유소년인구

-- 15~64세 (생산가능인구) 집계
SUM(male_age_15 + male_age_16 + ... + male_age_64 +
    female_age_15 + female_age_16 + ... + female_age_64) AS 생산가능인구

-- 65세 이상 (고령인구) 집계
SUM(male_age_65 + male_age_66 + ... + male_age_109 + male_age_110_over +
    female_age_65 + female_age_66 + ... + female_age_109 + female_age_110_over) AS 고령인구
```

**주요 연령 그룹 정의:**

| 그룹명 | 연령 범위 | 컬럼 범위 |
|--------|----------|----------|
| 유소년 | 0~14세 | male_age_0 ~ male_age_14, female_age_0 ~ female_age_14 |
| 청년 | 15~34세 | male_age_15 ~ male_age_34, female_age_15 ~ female_age_34 |
| 중장년 | 35~64세 | male_age_35 ~ male_age_64, female_age_35 ~ female_age_64 |
| 고령 | 65세 이상 | male_age_65 ~ male_age_110_over, female_age_65 ~ female_age_110_over |
| 초고령 | 80세 이상 | male_age_80 ~ male_age_110_over, female_age_80 ~ female_age_110_over |

**10대 단위 집계 예시:**
| 그룹명 | 연령 범위 | 컬럼 범위 |
|--------|----------|----------|
| 10대 | 10~19세 | male_age_10 ~ male_age_19, female_age_10 ~ female_age_19 |
| 20대 | 20~29세 | male_age_20 ~ male_age_29, female_age_20 ~ female_age_29 |
| 30대 | 30~39세 | male_age_30 ~ male_age_39, female_age_30 ~ female_age_39 |
| ... | ... | ... |

**예시 SQL - 시군구별 고령인구:**
```sql
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
        p.female_age_70 + p.female_age_71 + p.female_age_72 + p.female_age_73 + p.female_age_74 +
        p.female_age_75 + p.female_age_76 + p.female_age_77 + p.female_age_78 + p.female_age_79 +
        p.female_age_80 + p.female_age_81 + p.female_age_82 + p.female_age_83 + p.female_age_84 +
        p.female_age_85 + p.female_age_86 + p.female_age_87 + p.female_age_88 + p.female_age_89 +
        p.female_age_90 + p.female_age_91 + p.female_age_92 + p.female_age_93 + p.female_age_94 +
        p.female_age_95 + p.female_age_96 + p.female_age_97 + p.female_age_98 + p.female_age_99 +
        p.female_age_100 + p.female_age_101 + p.female_age_102 + p.female_age_103 + p.female_age_104 +
        p.female_age_105 + p.female_age_106 + p.female_age_107 + p.female_age_108 + p.female_age_109 +
        p.female_age_110_over
    ) AS 고령인구
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
  AND d.sigungu_code LIKE '____0'
GROUP BY d.sido_nm, d.sigungu_nm
ORDER BY 고령인구 DESC
LIMIT 10;
```

**예시 SQL - 20대 인구 비율:**
```sql
SELECT
    d.sido_nm AS 시도,
    d.sigungu_nm AS 시군구,
    SUM(p.male_age_20 + p.male_age_21 + p.male_age_22 + p.male_age_23 + p.male_age_24 +
        p.male_age_25 + p.male_age_26 + p.male_age_27 + p.male_age_28 + p.male_age_29 +
        p.female_age_20 + p.female_age_21 + p.female_age_22 + p.female_age_23 + p.female_age_24 +
        p.female_age_25 + p.female_age_26 + p.female_age_27 + p.female_age_28 + p.female_age_29
    ) AS "20대인구",
    SUM(p.total_pop) AS 총인구,
    ROUND(
        SUM(p.male_age_20 + p.male_age_21 + p.male_age_22 + p.male_age_23 + p.male_age_24 +
            p.male_age_25 + p.male_age_26 + p.male_age_27 + p.male_age_28 + p.male_age_29 +
            p.female_age_20 + p.female_age_21 + p.female_age_22 + p.female_age_23 + p.female_age_24 +
            p.female_age_25 + p.female_age_26 + p.female_age_27 + p.female_age_28 + p.female_age_29
        )::NUMERIC / NULLIF(SUM(p.total_pop), 0) * 100, 2
    ) AS "20대비율"
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
  AND d.sigungu_code LIKE '____0'
GROUP BY d.sido_nm, d.sigungu_nm
ORDER BY "20대비율" DESC
LIMIT 10;
```

**주의사항:**
1. **정책지표(고령화율, 유소년율 등)** → `cache_sigungu_indicators` 사용 ✅
2. **사용자 정의 연령(20대, 30대, 80세+ 등)** → `fact_population_by_age` 사용 ✅
3. `fact_population_by_age` 사용 시 `dim_admin_area` JOIN 필요
4. 시군구 단위 집계 시 `GROUP BY` 필수
5. 110세 이상은 `male_age_110_over`, `female_age_110_over` 사용
6. 읍면동 단위 조회 시 `d.eupmyeondong_nm IS NOT NULL` 조건 사용

**⚠️ 존재하지 않는 테이블/컬럼 주의:**
- ❌ `fact_population_age_group` - 존재하지 않음
- ❌ `male_80_89`, `female_80_89` 등 연령대별 컬럼 - 존재하지 않음
- ✅ 반드시 1세별 컬럼 사용: `male_age_80`, `male_age_81`, ..., `male_age_110_over`

---

## 6. 예시 질문과 SQL

### 예시 1: 고령화율 높은 지역 (기본 - 하위시군구 합산)
**질문**: "고령화율이 가장 높은 시군구 10개"

```sql
SELECT sido_nm AS 시도,
       sigungu_nm AS 시군구,
       elderly_ratio AS 고령화율,
       total_pop AS 총인구
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sigungu_code LIKE '____0'  -- 대표 시군구만 (하위구 제외)
ORDER BY elderly_ratio DESC NULLS LAST
LIMIT 10;
```

### 예시 2: 특정 시도 내 조회
**질문**: "경상북도에서 1인가구 비율이 높은 시군"

```sql
SELECT sigungu_nm AS 시군구,
       single_ratio AS "1인가구비율",
       single_household_cnt AS "1인가구수",
       household_cnt AS 세대수
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sido_nm = '경상북도'
  AND sigungu_code LIKE '____0'
ORDER BY single_ratio DESC NULLS LAST
LIMIT 10;
```

### 예시 3: 인구 순위 (기본)
**질문**: "인구가 많은 시군구 20개"

```sql
SELECT sido_nm AS 시도,
       sigungu_nm AS 시군구,
       total_pop AS 총인구,
       household_cnt AS 세대수
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sigungu_code LIKE '____0'  -- 대표 시군구만
ORDER BY total_pop DESC
LIMIT 20;
```

### 예시 4: 하위시군구 구분 조회
**질문**: "인구가 많은 시군구 20개, 하위시군구 구분해서"

```sql
SELECT sido_nm AS 시도,
       sigungu_nm AS 시군구,
       sigungu_code AS 시군구코드,
       total_pop AS 총인구,
       household_cnt AS 세대수
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
ORDER BY total_pop DESC
LIMIT 20;
```

### 예시 5: 연령별 인구 조회 (1세별 테이블 사용)
**질문**: "30대 인구가 많은 시군구 10개"

```sql
SELECT
    d.sido_nm AS 시도,
    d.sigungu_nm AS 시군구,
    SUM(
        p.male_age_30 + p.male_age_31 + p.male_age_32 + p.male_age_33 + p.male_age_34 +
        p.male_age_35 + p.male_age_36 + p.male_age_37 + p.male_age_38 + p.male_age_39 +
        p.female_age_30 + p.female_age_31 + p.female_age_32 + p.female_age_33 + p.female_age_34 +
        p.female_age_35 + p.female_age_36 + p.female_age_37 + p.female_age_38 + p.female_age_39
    ) AS "30대인구"
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
  AND d.sigungu_code LIKE '____0'
GROUP BY d.sido_nm, d.sigungu_nm
ORDER BY "30대인구" DESC
LIMIT 10;
```

### 예시 6: 유소년 인구 비율
**질문**: "유소년(0~14세) 비율이 높은 시군구"

```sql
SELECT
    d.sido_nm AS 시도,
    d.sigungu_nm AS 시군구,
    SUM(
        p.male_age_0 + p.male_age_1 + p.male_age_2 + p.male_age_3 + p.male_age_4 +
        p.male_age_5 + p.male_age_6 + p.male_age_7 + p.male_age_8 + p.male_age_9 +
        p.male_age_10 + p.male_age_11 + p.male_age_12 + p.male_age_13 + p.male_age_14 +
        p.female_age_0 + p.female_age_1 + p.female_age_2 + p.female_age_3 + p.female_age_4 +
        p.female_age_5 + p.female_age_6 + p.female_age_7 + p.female_age_8 + p.female_age_9 +
        p.female_age_10 + p.female_age_11 + p.female_age_12 + p.female_age_13 + p.female_age_14
    ) AS 유소년인구,
    SUM(p.total_pop) AS 총인구,
    ROUND(
        SUM(
            p.male_age_0 + p.male_age_1 + p.male_age_2 + p.male_age_3 + p.male_age_4 +
            p.male_age_5 + p.male_age_6 + p.male_age_7 + p.male_age_8 + p.male_age_9 +
            p.male_age_10 + p.male_age_11 + p.male_age_12 + p.male_age_13 + p.male_age_14 +
            p.female_age_0 + p.female_age_1 + p.female_age_2 + p.female_age_3 + p.female_age_4 +
            p.female_age_5 + p.female_age_6 + p.female_age_7 + p.female_age_8 + p.female_age_9 +
            p.female_age_10 + p.female_age_11 + p.female_age_12 + p.female_age_13 + p.female_age_14
        )::NUMERIC / NULLIF(SUM(p.total_pop), 0) * 100, 2
    ) AS 유소년비율
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
  AND d.sigungu_code LIKE '____0'
GROUP BY d.sido_nm, d.sigungu_nm
ORDER BY 유소년비율 DESC
LIMIT 10;
```

### 예시 7: 1인가구 연령별 조회
**질문**: "65세 이상 1인가구가 많은 시군구"

```sql
SELECT
    d.sido_nm AS 시도,
    d.sigungu_nm AS 시군구,
    SUM(
        s.male_age_65 + s.male_age_66 + s.male_age_67 + s.male_age_68 + s.male_age_69 +
        s.male_age_70 + s.male_age_71 + s.male_age_72 + s.male_age_73 + s.male_age_74 +
        s.male_age_75 + s.male_age_76 + s.male_age_77 + s.male_age_78 + s.male_age_79 +
        s.male_age_80 + s.male_age_81 + s.male_age_82 + s.male_age_83 + s.male_age_84 +
        s.male_age_85 + s.male_age_86 + s.male_age_87 + s.male_age_88 + s.male_age_89 +
        s.male_age_90 + s.male_age_91 + s.male_age_92 + s.male_age_93 + s.male_age_94 +
        s.male_age_95 + s.male_age_96 + s.male_age_97 + s.male_age_98 + s.male_age_99 +
        s.male_age_100 + s.male_age_101 + s.male_age_102 + s.male_age_103 + s.male_age_104 +
        s.male_age_105 + s.male_age_106 + s.male_age_107 + s.male_age_108 + s.male_age_109 +
        s.male_age_110_over +
        s.female_age_65 + s.female_age_66 + s.female_age_67 + s.female_age_68 + s.female_age_69 +
        s.female_age_70 + s.female_age_71 + s.female_age_72 + s.female_age_73 + s.female_age_74 +
        s.female_age_75 + s.female_age_76 + s.female_age_77 + s.female_age_78 + s.female_age_79 +
        s.female_age_80 + s.female_age_81 + s.female_age_82 + s.female_age_83 + s.female_age_84 +
        s.female_age_85 + s.female_age_86 + s.female_age_87 + s.female_age_88 + s.female_age_89 +
        s.female_age_90 + s.female_age_91 + s.female_age_92 + s.female_age_93 + s.female_age_94 +
        s.female_age_95 + s.female_age_96 + s.female_age_97 + s.female_age_98 + s.female_age_99 +
        s.female_age_100 + s.female_age_101 + s.female_age_102 + s.female_age_103 + s.female_age_104 +
        s.female_age_105 + s.female_age_106 + s.female_age_107 + s.female_age_108 + s.female_age_109 +
        s.female_age_110_over
    ) AS "65세이상_1인가구"
FROM fact_single_household s
JOIN dim_admin_area d ON s.admin_code = d.admin_code
WHERE s.base_ym = (SELECT MAX(base_ym) FROM fact_single_household)
  AND d.sigungu_code LIKE '____0'
GROUP BY d.sido_nm, d.sigungu_nm
ORDER BY "65세이상_1인가구" DESC
LIMIT 10;
```

### 예시 8: 읍면동 단위 80세 이상 인구비율 ⭐
**질문**: "80세 이상 인구비율이 높은 읍면동 20개"

```sql
SELECT
    d.sido_nm AS 시도,
    d.sigungu_nm AS 시군구,
    d.eupmyeondong_nm AS 읍면동,
    (p.male_total + p.female_total) AS 총인구,
    (
        p.male_age_80 + p.male_age_81 + p.male_age_82 + p.male_age_83 + p.male_age_84 +
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
        p.female_age_110_over
    ) AS "80세이상",
    ROUND(
        (
            p.male_age_80 + p.male_age_81 + p.male_age_82 + p.male_age_83 + p.male_age_84 +
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
            p.female_age_110_over
        )::NUMERIC / NULLIF(p.male_total + p.female_total, 0) * 100, 2
    ) AS "80세이상비율"
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
  AND d.eupmyeondong_nm IS NOT NULL
  AND (p.male_total + p.female_total) > 0
ORDER BY "80세이상비율" DESC NULLS LAST
LIMIT 20;
```

**핵심 포인트:**
- 읍면동 단위: `d.eupmyeondong_nm IS NOT NULL` 조건 사용
- 80세 이상: male_age_80 ~ male_age_110_over + female_age_80 ~ female_age_110_over
- GROUP BY 없음 (읍면동별로 1행씩 존재)

### 예시 9: 읍면동 단위 청년(20~34세) 인구비율
**질문**: "청년 인구비율이 높은 읍면동 20개"

```sql
SELECT
    d.sido_nm AS 시도,
    d.sigungu_nm AS 시군구,
    d.eupmyeondong_nm AS 읍면동,
    (p.male_total + p.female_total) AS 총인구,
    (
        p.male_age_20 + p.male_age_21 + p.male_age_22 + p.male_age_23 + p.male_age_24 +
        p.male_age_25 + p.male_age_26 + p.male_age_27 + p.male_age_28 + p.male_age_29 +
        p.male_age_30 + p.male_age_31 + p.male_age_32 + p.male_age_33 + p.male_age_34 +
        p.female_age_20 + p.female_age_21 + p.female_age_22 + p.female_age_23 + p.female_age_24 +
        p.female_age_25 + p.female_age_26 + p.female_age_27 + p.female_age_28 + p.female_age_29 +
        p.female_age_30 + p.female_age_31 + p.female_age_32 + p.female_age_33 + p.female_age_34
    ) AS 청년인구,
    ROUND(
        (
            p.male_age_20 + p.male_age_21 + p.male_age_22 + p.male_age_23 + p.male_age_24 +
            p.male_age_25 + p.male_age_26 + p.male_age_27 + p.male_age_28 + p.male_age_29 +
            p.male_age_30 + p.male_age_31 + p.male_age_32 + p.male_age_33 + p.male_age_34 +
            p.female_age_20 + p.female_age_21 + p.female_age_22 + p.female_age_23 + p.female_age_24 +
            p.female_age_25 + p.female_age_26 + p.female_age_27 + p.female_age_28 + p.female_age_29 +
            p.female_age_30 + p.female_age_31 + p.female_age_32 + p.female_age_33 + p.female_age_34
        )::NUMERIC / NULLIF(p.male_total + p.female_total, 0) * 100, 2
    ) AS 청년비율
FROM fact_population_by_age p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_by_age)
  AND d.eupmyeondong_nm IS NOT NULL
  AND (p.male_total + p.female_total) > 0
ORDER BY 청년비율 DESC NULLS LAST
LIMIT 20;
```

---

## 7. 데이터 품질 참고사항

1. **데이터 갱신 주기**: 매월 (행정안전부 주민등록인구통계 기준)
2. **결측값**: 일부 소규모 행정구역에서 세부 데이터 누락 가능
3. **65세 이상 인구**: 연령대별 데이터에서 추정값 (60대 절반 + 70대 이상)

> **참고**: 시계열 분석(전월 대비, 전년 동월, 추이 등)은 공통 온톨로지(`module/ontology/common_ontology.md`)를 참조하세요.

---

## 8. 업데이트 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2025-01-10 | 초기 문서 작성 |
| 2025-01-10 | 시군구 코드 구분 규칙 추가 (4자리/5자리), 한글 컬럼명 규칙 추가 |
| 2025-01-10 | 1세별 연령 집계 규칙 추가 (5.5절), 연령별 SQL 예시 추가 (예시5~7) |
| 2026-01-12 | 시계열 분석 섹션을 공통 온톨로지로 이동 |
| 2026-01-15 | LLM 답변 가이드라인, 차트 시각화 가이드라인 추가 |

---

## 9. LLM 답변 가이드라인 (Response Guidelines)

**중요**: 모든 분석 결과는 아래 보고서 형식으로 작성하고, 반드시 **5개의 인사이트**를 도출해야 합니다.

### 9.1 표준 보고서 형식 (SQL 성공 시)

```markdown
# 📊 [분석 주제] 분석 보고서

## 1. 분석 개요
| 항목 | 내용 |
|------|------|
| 분석 목적 | [사용자 질문 요약] |
| 데이터 기준 | [기준년월: YYYY년 MM월] |
| 분석 범위 | [전국/특정시도/특정시군구] |
| 데이터 출처 | 행정안전부 주민등록인구통계 |

---

## 2. 주요 지표 요약

| 지표 | 값 | 비고 |
|------|-----|------|
| [지표1] | [값] | [전국평균 대비 등] |
| [지표2] | [값] | [순위 등] |
| [지표3] | [값] | [특이사항] |

---

## 3. 상세 분석 결과

[데이터 테이블 표시]

---

## 4. 핵심 인사이트 (5개)

### 💡 인사이트 1: [제목]
[구체적인 발견 내용과 수치 근거]

### 💡 인사이트 2: [제목]
[구체적인 발견 내용과 수치 근거]

### 💡 인사이트 3: [제목]
[구체적인 발견 내용과 수치 근거]

### 💡 인사이트 4: [제목]
[구체적인 발견 내용과 수치 근거]

### 💡 인사이트 5: [제목]
[구체적인 발견 내용과 수치 근거]

---

## 5. 시사점 및 제언

### 📌 정책적 시사점
- [시사점 1]
- [시사점 2]

### 🔍 추가 분석 제안
- [관련 심화 질문 1]
- [관련 심화 질문 2]


### 9.2 인사이트 도출 가이드

**5개 인사이트는 다음 관점에서 도출합니다:**

| 순번 | 관점 | 도출 방향 | 예시 |
|------|------|----------|------|
| 1 | **1위/최고값** | 가장 높은 지역/항목 특성 분석 | "고령화율 1위는 ○○군으로 전국 평균의 2.1배" |
| 2 | **평균 대비** | 전국/시도 평균과 비교 | "경북 평균(N%)보다 10%p 이상 높은 시군은 8개" |
| 3 | **특이값/이상치** | 눈에 띄는 패턴이나 예외 | "유일하게 유소년율이 증가한 시군구는 ○○시" |
| 4 | **비율/구조** | 구성비 또는 비율 분석 | "초고령사회(20%+) 진입 시군구는 전국 N개" |
| 5 | **추세/변화** | 전월/전년 대비 변화 | "전년 동월 대비 고령화율 상승폭 1위는 ○○군(+1.2%p)" |

### 9.3 보고서 형식 예시 (실제 샘플)

```markdown
# 📊 경상북도 고령화 현황 분석 보고서

## 1. 분석 개요
| 항목 | 내용 |
|------|------|
| 분석 목적 | 경상북도 시군구별 고령화율 분포 및 특성 파악 |
| 데이터 기준 | 2025년 11월 |
| 분석 범위 | 경상북도 23개 시군 |
| 데이터 출처 | 행정안전부 주민등록인구통계 |

---

## 2. 주요 지표 요약

| 지표 | 값 | 비고 |
|------|-----|------|
| 경북 총인구 | 2,567,890명 | 전국 대비 4.9% |
| 경북 평균 고령화율 | 24.8% | 전국 평균(19.2%) 대비 +5.6%p |
| 초고령사회(20%+) 시군 | 18개 | 경북 23개 중 78% |

---

## 3. 상세 분석 결과

| 순위 | 시군구 | 총인구 | 고령인구 | 고령화율 | 노령화지수 |
|------|--------|--------|----------|----------|-----------|
| 1 | 의성군 | 48,234명 | 21,567명 | 44.7% | 589.2 |
| 2 | 청송군 | 23,891명 | 10,234명 | 42.8% | 534.1 |
| 3 | 영양군 | 15,678명 | 6,543명 | 41.7% | 512.3 |
| 4 | 봉화군 | 29,012명 | 11,234명 | 38.7% | 423.5 |
| 5 | 영덕군 | 34,567명 | 12,890명 | 37.3% | 398.2 |

---

## 4. 핵심 인사이트 (5개)

### 💡 인사이트 1: 의성군 고령화율 전국 최고 수준
의성군의 고령화율 44.7%는 전국 평균(19.2%)의 2.3배로,
전국 226개 시군구 중 최상위권에 해당합니다.

### 💡 인사이트 2: 경북 농촌지역 초고령사회 진입
고령화율 30% 이상인 시군이 12개로 경북 전체의 52%를 차지합니다.
특히 북부 산간지역(의성, 청송, 영양, 봉화)이 40% 이상입니다.

### 💡 인사이트 3: 도시-농촌 격차 심화
구미시(14.2%), 포항시(17.8%) 등 도시 지역은 전국 평균 수준인 반면,
농촌 지역과의 격차가 최대 30.5%p에 달합니다.

### 💡 인사이트 4: 노령화지수 500 초과 지역 3개
의성, 청송, 영양군의 노령화지수가 500을 초과하여
유소년 1명당 노인 5명 이상인 극심한 고령화 상태입니다.

### 💡 인사이트 5: 전년 대비 고령화 가속화
경북 평균 고령화율이 전년(23.9%) 대비 0.9%p 상승했으며,
상승폭 1위는 영양군(+1.4%p)입니다.

---

## 5. 시사점 및 제언

### 📌 정책적 시사점
- 농촌 고령화 대응을 위한 의료·복지 인프라 확충 필요
- 청년 유입을 위한 일자리·주거 정책과 연계 필요

### 🔍 추가 분석 제안
- "경북 1인가구 중 65세 이상 비율은?"
- "경북 생산가능인구 감소 추이 분석"


### 9.4 SQL 생성 불가능한 경우

```markdown
# ⚠️ 데이터 제한 안내

## 요청 내용
[사용자 질문]

## 제한 사유
요청하신 **[XXX]** 정보는 현재 데이터베이스에 포함되어 있지 않습니다.

## 현재 분석 가능한 데이터

### 인구통계 (cache_sigungu_indicators)
| 분류 | 포함 항목 |
|------|----------|
| 인구수 | 총인구, 남녀인구, 세대수 |
| 연령 | 1세별 인구, 유소년/생산가능/고령 인구 |
| 지표 | 고령화율, 유소년율, 성비, 노령화지수 |
| 1인가구 | 1인가구수, 1인가구비율, 연령별 1인가구 |

### 지역 단위
| 단위 | 설명 |
|------|------|
| 시도 | 17개 광역시/도 |
| 시군구 | 226개 기초자치단체 |
| 읍면동 | 약 3,500개 행정동 |

## 💡 대안 분석 제안
- [분석 가능한 유사 질문 1]
- [분석 가능한 유사 질문 2]
- [분석 가능한 유사 질문 3]
```

---

## 10. 차트 시각화 가이드라인 (Chart Guidelines)

### 10.1 차트 종류 선택 기준

| 데이터 유형 | 권장 차트 | 예시 질문 |
|------------|----------|----------|
| **순위/비교** | 가로막대 (barh) | "고령화율 높은 시군구 10개" |
| **구성비** | 도넛/파이 (pie) | "연령대별 인구 비율" |
| **시계열** | 라인 (line) | "월별 인구 추이" |
| **분포** | 히스토그램 (hist) | "고령화율 분포" |
| **비교(다항목)** | 묶음막대 (grouped bar) | "시도별 남녀 인구 비교" |
| **인구피라미드** | 양방향 막대 | "연령별 남녀 인구 구조" |

### 10.2 색상 팔레트 (표준)

```python
# 메인 색상 팔레트 (8색)
COLORS = [
    '#667EEA',  # 파랑 (주력)
    '#764BA2',  # 보라
    '#F24822',  # 빨강 (강조)
    '#2ECC71',  # 초록
    '#3498DB',  # 하늘
    '#F39C12',  # 주황
    '#9B59B6',  # 자주
    '#1ABC9C',  # 청록
]

# 성별 색상
GENDER_COLORS = {
    'male': '#3498DB',    # 남성 - 파랑
    'female': '#E74C3C',  # 여성 - 빨강
}

# 연령대 색상 (그라데이션)
AGE_COLORS = {
    'youth': '#2ECC71',     # 유소년 - 초록
    'working': '#3498DB',   # 생산가능 - 파랑
    'elderly': '#E74C3C',   # 고령 - 빨강
}

# 단일 색상 그라데이션 (순위 표현)
BLUE_GRADIENT = ['#1243A6', '#1D64F2', '#4A90E2', '#7EB6FF', '#B8D4FF']

# 대비 색상 (비교 분석)
COMPARE_COLORS = {
    'increase': '#2ECC71',  # 증가
    'decrease': '#E74C3C',  # 감소
    'neutral': '#95A5A6',   # 변동없음
}
```

### 10.3 차트 스타일 표준

```python
import matplotlib.pyplot as plt
import koreanize_matplotlib

# 기본 스타일 설정
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 11

# 차트 생성 표준 템플릿
fig, ax = plt.subplots(figsize=(12, 6))

# 제목 스타일
ax.set_title('차트 제목', fontsize=16, fontweight='bold', pad=20)

# 축 레이블
ax.set_xlabel('X축 레이블', fontsize=12)
ax.set_ylabel('Y축 레이블', fontsize=12)

# 그리드 (가로선만)
ax.yaxis.grid(True, linestyle='--', alpha=0.7)
ax.set_axisbelow(True)

# 테두리 제거
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# 범례 (우측 상단)
ax.legend(loc='upper right', frameon=False)

plt.tight_layout()
```

### 10.4 차트 유형별 상세 가이드

#### 10.4.1 가로막대 차트 (순위 표현)

```python
# 가로막대 - 고령화율 순위 등에 적합
fig, ax = plt.subplots(figsize=(10, 8))

# 색상: 1위는 강조색, 나머지는 그라데이션
colors = ['#F24822'] + ['#667EEA'] * (len(data) - 1)

bars = ax.barh(y_labels, values, color=colors, edgecolor='none')

# 값 표시 (막대 끝에)
for bar, val in zip(bars, values):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
            f'{val:.1f}%', va='center', fontsize=10)

ax.invert_yaxis()  # 1위가 위로
ax.set_title('고령화율 TOP 10 시군구', fontsize=16, fontweight='bold')
ax.set_xlabel('고령화율 (%)')
```

#### 10.4.2 도넛 차트 (연령 구성비)

```python
# 도넛 차트 - 연령대별 구성비에 적합
fig, ax = plt.subplots(figsize=(10, 10))

labels = ['유소년(0~14세)', '생산가능(15~64세)', '고령(65세+)']
colors = ['#2ECC71', '#3498DB', '#E74C3C']

wedges, texts, autotexts = ax.pie(
    values,
    labels=labels,
    colors=colors,
    autopct='%1.1f%%',
    startangle=90,
    pctdistance=0.75,
    wedgeprops={'width': 0.5, 'edgecolor': 'white'}
)

# 중앙에 총인구 표시
ax.text(0, 0, f'총인구\n{total:,}명', ha='center', va='center',
        fontsize=18, fontweight='bold')

ax.set_title('연령대별 인구 구성비', fontsize=16, fontweight='bold')
```

#### 10.4.3 라인 차트 (시계열)

```python
# 라인 차트 - 월별 추이에 적합
fig, ax = plt.subplots(figsize=(12, 6))

# 여러 지역 비교 시
for i, region in enumerate(regions):
    ax.plot(dates, values[region],
            color=COLORS[i],
            marker='o',
            linewidth=2,
            markersize=6,
            label=region)

# 범례 (차트 외부 우측)
ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=False)

ax.set_title('월별 고령화율 추이', fontsize=16, fontweight='bold')
ax.set_xlabel('기준년월')
ax.set_ylabel('고령화율 (%)')
```

#### 10.4.4 인구피라미드

```python
# 인구피라미드 - 연령별 남녀 분포에 적합
fig, ax = plt.subplots(figsize=(10, 12))

# 연령 구간 (5세 단위)
age_groups = ['0-4', '5-9', '10-14', ..., '80-84', '85+']
y_pos = range(len(age_groups))

# 남성은 왼쪽(음수), 여성은 오른쪽(양수)
ax.barh(y_pos, [-v for v in male_values], color='#3498DB', label='남성')
ax.barh(y_pos, female_values, color='#E74C3C', label='여성')

ax.set_yticks(y_pos)
ax.set_yticklabels(age_groups)
ax.set_xlabel('인구수')
ax.set_title('연령별 인구 피라미드', fontsize=16, fontweight='bold')
ax.legend(loc='upper right')

# X축 레이블 절대값으로 표시
ax.set_xticklabels([f'{abs(int(x)):,}' for x in ax.get_xticks()])
```

### 10.5 범례 위치 가이드

| 차트 유형 | 범례 위치 | 설정 코드 |
|----------|----------|----------|
| 막대 (적은 항목) | 우측 상단 | `loc='upper right'` |
| 막대 (많은 항목) | 범례 생략, 직접 레이블 | - |
| 라인 (다중) | 차트 외부 우측 | `bbox_to_anchor=(1.02, 1)` |
| 도넛/파이 | 우측 | `bbox_to_anchor=(1.2, 0.5)` |
| 인구피라미드 | 우측 상단 | `loc='upper right'` |

### 10.6 데이터 값 표시 규칙

| 데이터 유형 | 표시 형식 | 예시 |
|------------|----------|------|
| 인구수 | 천단위 쉼표 | `1,234,567명` |
| 비율 | 소수점 1자리 | `24.8%` |
| 지수 | 소수점 1자리 | `423.5` |
| 증감 | 부호 + 소수점 1자리 | `+1.2%p`, `-0.5%p` |

```python
# 숫자 포맷팅 함수
def format_number(val, data_type='population'):
    if data_type == 'population':
        return f'{val:,.0f}명'
    elif data_type == 'ratio':
        return f'{val:.1f}%'
    elif data_type == 'index':
        return f'{val:.1f}'
    elif data_type == 'change':
        sign = '+' if val > 0 else ''
        return f'{sign}{val:.1f}%p'
```

---

## 11. 자주 묻는 질문 유형별 처리

### 11.1 지역별 현황 질문
- "경상북도 고령화율 현황" → 보고서 형식 + 시군구별 집계 + 5개 인사이트
- "인구 많은 시군구" → 순위 + 전국 대비 비중 분석

### 11.2 비율/순위 질문
- "고령화율 높은 곳" → 비율 순위 + 초고령사회 기준(20%) 비교
- "1인가구 비율 높은 읍면동" → 세부 지역 단위 분석

### 11.3 연령별 분석 질문
- "20대 인구 많은 시군구" → fact_population_by_age 사용 + 1세별 합산
- "80세 이상 비율 높은 곳" → 초고령 인구 집계

### 11.4 추세/변화 질문
- "월별 인구 추이" → 라인 차트 + 증감 분석
- "전년 대비 변화" → 전년 동월 비교 + 변화율 인사이트

### 11.5 차트 요청 질문
- "차트로 보여줘" → 데이터 유형에 맞는 차트 자동 선택
- "그래프" → 가로막대(순위), 도넛(비율), 라인(추이), 피라미드(연령별)

---

*이 온톨로지는 인구통계 데이터콩 챗봇에서 참조됩니다. 데이터 구조나 분석 요구사항이 변경되면 함께 업데이트해주세요.*
