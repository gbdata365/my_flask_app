# 공통 온톨로지 (Common Ontology)

이 문서는 모든 도메인에서 공통으로 참조하는 기본 정보입니다.
다른 도메인 온톨로지와 함께 로드되어 LLM이 SQL을 생성할 때 참조합니다.

---

## 1. 공통 테이블

### 1.1 dim_admin_area (행정구역 마스터)

모든 도메인에서 공통으로 사용하는 행정구역 정보 테이블입니다.

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|-----------|------|------|
| admin_code | VARCHAR(10) | 행정구역코드 (PK) | '4711000000' |
| sido_nm | VARCHAR | 시도명 | '경상북도' |
| sigungu_nm | VARCHAR | 시군구명 | '안동시' |
| sigungu_code | VARCHAR(5) | 시군구코드 | '47110' |
| eupmyeondong_nm | VARCHAR | 읍면동명 | '풍천면' |
| region_nm | VARCHAR | 권역명 | '영남권' |

**행정구역 계층 구조:**
```
시도(17개) → 시군구(약 250개) → 읍면동(약 3,500개)
```

### 1.2 시군구 코드 규칙 (매우 중요!)

| 코드 형태 | 설명 | 예시 |
|----------|------|------|
| `____0` (5번째=0) | 대표 시군구 | '47110' = 안동시 |
| `____X` (5번째≠0) | 하위 행정구 | '41111' = 수원시 장안구 |

**시군구 단위 조회 기본 규칙:**
- 기본값: 하위시군구 합산 (`LEFT(sigungu_code, 4)` 기준 그룹핑)
- "하위구 구분", "자치구별" 언급 시: 5자리 개별 조회

---

## 2. 시도명 매핑 (자연어 → 정규화)

| 자연어 표현 | 정규화된 시도명 | 권역 |
|------------|----------------|------|
| 서울, 서울시 | 서울특별시 | 수도권 |
| 부산, 부산시 | 부산광역시 | 영남권 |
| 대구, 대구시 | 대구광역시 | 영남권 |
| 인천, 인천시 | 인천광역시 | 수도권 |
| 광주, 광주시 | 광주광역시 | 호남권 |
| 대전, 대전시 | 대전광역시 | 충청권 |
| 울산, 울산시 | 울산광역시 | 영남권 |
| 세종, 세종시 | 세종특별자치시 | 충청권 |
| 경기, 경기도 | 경기도 | 수도권 |
| 강원, 강원도 | 강원특별자치도 | 강원권 |
| 충북, 충청북도 | 충청북도 | 충청권 |
| 충남, 충청남도 | 충청남도 | 충청권 |
| 전북, 전라북도 | 전북특별자치도 | 호남권 |
| 전남, 전라남도 | 전라남도 | 호남권 |
| 경북, 경상북도 | 경상북도 | 영남권 |
| 경남, 경상남도 | 경상남도 | 영남권 |
| 제주, 제주도 | 제주특별자치도 | 제주권 |

---

## 3. 기본 인구 정보 (모든 도메인 공통)

### 3.1 인구 기본 테이블: fact_population_basic

| 컬럼명 | 설명 | 비고 |
|--------|------|------|
| base_ym | 기준년월 (YYYYMM) | 매월 갱신 |
| admin_code | 행정구역코드 (FK) | dim_admin_area 참조 |
| total_pop | 총인구수 | |
| male_pop | 남자인구수 | |
| female_pop | 여자인구수 | |
| household_cnt | 세대수 | |

### 3.2 시군구 지표 캐시: cache_sigungu_indicators

빠른 조회를 위해 미리 계산된 시군구별 지표입니다.

| 컬럼명 | 설명 | 계산식 |
|--------|------|--------|
| total_pop | 총인구 | - |
| male_pop | 남자인구 | - |
| female_pop | 여자인구 | - |
| household_cnt | 총세대수 | - |
| elderly_pop | 고령인구 | 65세 이상 |
| elderly_ratio | 고령화율 (%) | 고령인구 / 총인구 × 100 |
| youth_pop | 유소년인구 | 0~14세 |
| youth_ratio | 유소년율 (%) | 유소년 / 총인구 × 100 |
| working_pop | 생산연령인구 | 15~64세 |
| sex_ratio | 성비 | 남자 / 여자 × 100 |
| aging_index | 노령화지수 | 고령 / 유소년 × 100 |
| single_household_cnt | 1인가구수 | - |
| single_ratio | 1인가구비율 (%) | 1인가구 / 총세대 × 100 |

---

## 4. 공통 용어 사전

### 4.1 인구 관련 기본 용어

| 자연어 표현 | 컬럼/의미 | 설명 |
|------------|----------|------|
| 인구, 총인구, 인구수 | total_pop | 주민등록인구 |
| 남자, 남성 | male_pop | 남자인구 |
| 여자, 여성 | female_pop | 여자인구 |
| 가구, 세대, 가구수 | household_cnt | 총세대수 |
| 고령, 노인, 65세 이상 | elderly_pop | 65세+ 인구 |
| 유소년, 아동, 어린이 | youth_pop | 0~14세 인구 |
| 청년 | - | 15~34세 (정책에 따라 다름) |
| 생산인구, 경제활동인구 | working_pop | 15~64세 |

### 4.2 정렬/순위 표현

| 자연어 표현 | SQL 표현 |
|------------|----------|
| 높은, 많은, 큰, 최고, 상위, TOP | ORDER BY ... DESC |
| 낮은, 적은, 작은, 최저, 하위 | ORDER BY ... ASC |
| N개, N위, TOP N | LIMIT N |

### 4.3 시간 표현

| 자연어 표현 | SQL 처리 |
|------------|----------|
| 최신, 현재, 가장 최근 | WHERE base_ym = (SELECT MAX(base_ym) FROM ...) |
| 작년, 전년 | 현재년도 - 1 |
| N년 전 | 현재년도 - N |
| YYYY년 MM월 | WHERE base_ym = 'YYYYMM' |

---

## 5. 공통 SQL 규칙

### 5.1 기본 규칙

```sql
-- 1. 최신 데이터 조회 (기본값)
WHERE base_ym = (SELECT MAX(base_ym) FROM 테이블명)

-- 2. NULL 처리
ORDER BY 컬럼명 DESC NULLS LAST

-- 3. 비율 계산 (0 나누기 방지)
ROUND(분자::numeric / NULLIF(분모, 0) * 100, 2)
```

### 5.2 결과 컬럼명 한글화 (필수!)

| 영문 컬럼명 | 한글 별칭 |
|------------|----------|
| sido_nm | 시도 |
| sigungu_nm | 시군구 |
| eupmyeondong_nm | 읍면동 |
| total_pop | 총인구 |
| male_pop | 남자인구 |
| female_pop | 여자인구 |
| household_cnt | 세대수 |
| base_ym | 기준년월 |

```sql
-- 올바른 예시
SELECT sido_nm AS 시도, sigungu_nm AS 시군구, total_pop AS 총인구
FROM ...
```

### 5.3 시군구 단위 조회 패턴

```sql
-- 기본: 대표 시군구만 (하위구 합산된 값)
WHERE sigungu_code LIKE '____0'

-- 또는: 4자리 기준 그룹핑
GROUP BY LEFT(sigungu_code, 4)
```

### 5.4 팩트 테이블 조인 규칙 (매우 중요!)

**⚠️ 여러 팩트 테이블 조인 시 반드시 base_ym도 조인 조건에 포함해야 함!**

base_ym 없이 조인하면 모든 월별 데이터가 곱해져서 잘못된 결과가 나옴 (Cartesian Product).

```sql
-- ❌ 잘못된 예: base_ym 없이 조인 → 데이터 뻥튀기!
SELECT d.sigungu_nm, SUM(p.total_pop), SUM(s.total_cnt)
FROM fact_population_basic p
JOIN fact_single_household s ON p.admin_code = s.admin_code  -- base_ym 없음!
JOIN dim_admin_area d ON p.admin_code = d.admin_code
GROUP BY d.sigungu_nm;
-- 결과: 12개월 × 12개월 = 144배로 뻥튀기됨

-- ✅ 올바른 예 1: base_ym을 조인 조건에 포함
SELECT d.sigungu_nm, SUM(p.total_pop), SUM(s.total_cnt)
FROM fact_population_basic p
JOIN fact_single_household s ON p.admin_code = s.admin_code
                             AND p.base_ym = s.base_ym  -- base_ym 조인!
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_basic)
GROUP BY d.sigungu_nm;

-- ✅ 올바른 예 2: 서브쿼리로 최신 데이터만 먼저 필터링
WITH latest_pop AS (
    SELECT * FROM fact_population_basic
    WHERE base_ym = (SELECT MAX(base_ym) FROM fact_population_basic)
),
latest_single AS (
    SELECT * FROM fact_single_household
    WHERE base_ym = (SELECT MAX(base_ym) FROM fact_single_household)
)
SELECT d.sigungu_nm, p.total_pop, s.total_cnt
FROM latest_pop p
JOIN latest_single s ON p.admin_code = s.admin_code
JOIN dim_admin_area d ON p.admin_code = d.admin_code;

-- ✅ 올바른 예 3: 단일 팩트 테이블만 사용 (가장 안전)
SELECT d.sigungu_nm, p.total_pop
FROM fact_population_basic p
JOIN dim_admin_area d ON p.admin_code = d.admin_code
WHERE p.base_ym = (SELECT MAX(base_ym) FROM fact_population_basic);
```

**핵심 규칙:**
1. 여러 팩트 테이블 조인 시 → `AND t1.base_ym = t2.base_ym` 필수
2. 또는 CTE/서브쿼리로 각 테이블의 최신 데이터만 먼저 필터링
3. CASE WHEN으로 base_ym 필터는 조인 문제를 해결하지 못함!

### 5.5 캐시 테이블과 팩트 테이블 조인 규칙 (매우 중요!)

**⚠️ 시군구 레벨 캐시 테이블과 읍면동 레벨 팩트 테이블을 직접 조인하면 안됨!**

cache_sigungu_indicators는 이미 시군구 단위로 집계된 1행이지만,
fact_single_household 등 팩트 테이블은 읍면동별로 N행이 있음.
직접 조인하면 캐시 테이블의 값이 N배로 뻥튀기됨!

```sql
-- ❌ 잘못된 예: 시군구 캐시(1행) + 읍면동 팩트(N행) 직접 조인
SELECT c.sigungu_nm, SUM(c.total_pop), SUM(s.age_columns...)
FROM cache_sigungu_indicators c
JOIN fact_single_household s ON LEFT(c.sigungu_code,4)||'0' = LEFT(s.admin_code,5)
GROUP BY c.sigungu_nm;
-- 결과: total_pop이 읍면동 수만큼 곱해짐! (울릉군 4개 읍면동 → 4배)

-- ✅ 올바른 예 1: 팩트 테이블 먼저 시군구 단위로 집계 후 조인
WITH sigungu_single AS (
    SELECT
        LEFT(admin_code, 5) as sigungu_code,
        SUM(age_0_14) as youth_single,
        SUM(age_65_over) as elderly_single
    FROM fact_single_household
    WHERE base_ym = (SELECT MAX(base_ym) FROM fact_single_household)
    GROUP BY LEFT(admin_code, 5)
)
SELECT
    c.sigungu_nm,
    c.total_pop,  -- SUM 불필요, 이미 시군구 1행
    c.single_household_cnt,
    ss.youth_single,
    ss.elderly_single
FROM cache_sigungu_indicators c
JOIN sigungu_single ss ON LEFT(c.sigungu_code,4)||'0' = ss.sigungu_code
WHERE c.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND c.sido_nm = '경상북도';

-- ✅ 올바른 예 2: 팩트 테이블만 사용하여 직접 집계
SELECT
    d.sigungu_nm,
    SUM(p.total_pop) as 총인구,
    SUM(s.total_cnt) as 총1인가구수
FROM fact_single_household s
JOIN fact_population_basic p ON s.admin_code = p.admin_code AND s.base_ym = p.base_ym
JOIN dim_admin_area d ON s.admin_code = d.admin_code
WHERE s.base_ym = (SELECT MAX(base_ym) FROM fact_single_household)
  AND d.sido_nm = '경상북도'
GROUP BY LEFT(d.sigungu_code, 4), d.sigungu_nm;
```

**핵심:**
- cache_sigungu_indicators 조인 시 → SUM() 쓰지 말 것 (이미 집계된 값)
- 또는 CTE로 팩트 테이블을 먼저 시군구 단위로 집계 후 조인
- 또는 팩트 테이블만 사용하여 직접 GROUP BY

---

## 6. 시계열 분석 (Time Series Analysis)

### 6.1 시계열 분석 유형

| 분석 유형 | 키워드 | 설명 |
|----------|--------|------|
| 전월 대비 | 전월 대비, 지난달 대비, 월별 변화, MoM | 직전 월과 비교 |
| 전년 동월 | 전년 동월, 작년 같은 달, 전년대비, YoY | 1년 전 같은 월과 비교 |
| 기간 추이 | 추이, 트렌드, 변화, 기간별, 월별 추이 | 여러 시점 데이터 |

### 6.2 시계열 SQL 패턴

#### 6.2.1 전월 대비 변화율 (Month-over-Month)

```sql
WITH current_data AS (
    SELECT sigungu_nm, 지표컬럼, base_ym
    FROM cache_sigungu_indicators
    WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
      AND sido_nm = '시도명'
      AND sigungu_code LIKE '____0'
),
prev_data AS (
    SELECT sigungu_nm, 지표컬럼, base_ym
    FROM cache_sigungu_indicators
    WHERE base_ym = (
        SELECT MAX(base_ym) FROM cache_sigungu_indicators
        WHERE base_ym < (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
    )
      AND sido_nm = '시도명'
      AND sigungu_code LIKE '____0'
)
SELECT
    c.sigungu_nm AS 시군구,
    p.지표컬럼 AS 전월값,
    c.지표컬럼 AS 당월값,
    ROUND(c.지표컬럼 - p.지표컬럼, 2) AS 변화량,
    ROUND((c.지표컬럼 - p.지표컬럼) / NULLIF(p.지표컬럼, 0) * 100, 2) AS 변화율
FROM current_data c
JOIN prev_data p ON c.sigungu_nm = p.sigungu_nm
ORDER BY 변화율 DESC;
```

#### 6.2.2 전년 동월 대비 (Year-over-Year)

```sql
WITH current_data AS (
    SELECT sigungu_nm, 지표컬럼, base_ym
    FROM cache_sigungu_indicators
    WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
      AND sido_nm = '시도명'
      AND sigungu_code LIKE '____0'
),
prev_year_data AS (
    SELECT sigungu_nm, 지표컬럼, base_ym
    FROM cache_sigungu_indicators
    WHERE base_ym = (
        SELECT TO_CHAR(TO_DATE(MAX(base_ym), 'YYYYMM') - INTERVAL '1 year', 'YYYYMM')
        FROM cache_sigungu_indicators
    )
      AND sido_nm = '시도명'
      AND sigungu_code LIKE '____0'
)
SELECT
    c.sigungu_nm AS 시군구,
    p.지표컬럼 AS 전년동월값,
    c.지표컬럼 AS 당월값,
    c.지표컬럼 - p.지표컬럼 AS 변화량,
    ROUND((c.지표컬럼 - p.지표컬럼)::numeric / NULLIF(p.지표컬럼, 0) * 100, 2) AS 변화율
FROM current_data c
JOIN prev_year_data p ON c.sigungu_nm = p.sigungu_nm
ORDER BY 변화율 DESC;
```

#### 6.2.3 기간별 추이 (Trend)

```sql
-- 최근 12개월 추이 (단일 지역)
SELECT
    base_ym AS 기준년월,
    sigungu_nm AS 시군구,
    지표컬럼 AS 지표값
FROM cache_sigungu_indicators
WHERE sido_nm = '시도명'
  AND sigungu_nm = '시군구명'
  AND sigungu_code LIKE '____0'
  AND base_ym >= (
      SELECT TO_CHAR(TO_DATE(MAX(base_ym), 'YYYYMM') - INTERVAL '11 months', 'YYYYMM')
      FROM cache_sigungu_indicators
  )
ORDER BY base_ym ASC;

-- 여러 지역 비교 추이
SELECT
    base_ym AS 기준년월,
    sigungu_nm AS 시군구,
    지표컬럼 AS 지표값
FROM cache_sigungu_indicators
WHERE sido_nm = '시도명'
  AND sigungu_nm IN ('지역1', '지역2', '지역3')
  AND sigungu_code LIKE '____0'
  AND base_ym >= (
      SELECT TO_CHAR(TO_DATE(MAX(base_ym), 'YYYYMM') - INTERVAL '11 months', 'YYYYMM')
      FROM cache_sigungu_indicators
  )
ORDER BY base_ym ASC, sigungu_nm;
```

### 6.3 시계열 분석 규칙

1. **기간 미지정 시**: 최근 12개월 기본 적용
2. **추이/트렌드 요청 시**: 시간순 정렬 (`ORDER BY base_ym ASC`)
3. **변화율 계산**: `(현재값 - 이전값) / 이전값 * 100`
4. **NULL 방지**: `NULLIF(이전값, 0)` 사용
5. **날짜 연산**: PostgreSQL `INTERVAL` 사용
   - 전월: `- INTERVAL '1 month'`
   - 전년 동월: `- INTERVAL '1 year'`

### 6.4 시계열 키워드 매핑

| 자연어 표현 | 분석 유형 | 기간 |
|------------|----------|------|
| 전월 대비, 지난달 비교 | MoM | 2개월 |
| 전년 동월, 작년 대비, YoY | YoY | 2개 시점 |
| 추이, 트렌드, 변화 추이 | Trend | 최근 12개월 |
| 최근 6개월, 6개월간 | Trend | 최근 6개월 |
| 최근 1년, 연간 | Trend | 최근 12개월 |
| 최근 2년 | Trend | 최근 24개월 |

### 6.5 시계열 차트 표시 규칙

- **추이/트렌드 데이터**: 꺾은선 그래프 (Line Chart) 사용
- **X축**: 기준년월 (base_ym)
- **Y축**: 지표값
- **여러 지역 비교 시**: 지역별 다른 색상 라인

---

## 7. 크로스 도메인 분석 가이드

### 7.1 도메인 간 JOIN 규칙

여러 도메인 데이터를 연결할 때는 **행정구역코드(admin_code)** 또는 **시군구코드(sigungu_code)**를 기준으로 JOIN합니다.

```sql
-- 인구 + 다른 도메인 JOIN 예시
SELECT
    p.시도, p.시군구, p.총인구,
    other.지표값
FROM cache_sigungu_indicators p
JOIN 다른도메인테이블 other
  ON p.sigungu_code = other.sigungu_code
  AND p.base_ym = other.base_ym
```

### 7.2 시점 일치 주의

도메인 간 데이터 시점이 다를 수 있으므로, 가능하면 동일 base_ym 조건을 명시합니다.

```sql
-- 시점 맞추기
WHERE p.base_ym = '202411'
  AND other.base_ym = '202411'
```

### 7.3 단위 인구당 지표 계산

다른 도메인 지표를 인구 대비로 분석할 때:

```sql
-- 인구 1만명당 시설 수
ROUND(시설수::numeric / (총인구 / 10000), 2) AS "인구만명당시설수"

-- 인구 1천명당 비율
ROUND(대상수::numeric / (총인구 / 1000), 2) AS "인구천명당비율"
```

---

## 8. 참조 도메인 온톨로지

이 공통 온톨로지와 함께 사용되는 도메인별 온톨로지:

| 도메인 | 온톨로지 경로 | 설명 |
|--------|-------------|------|
| 인구통계 | `01_population/ontology/database_ontology.md` | 인구 상세 지표 |
| (향후 추가) | `02_xxx/ontology/database_ontology.md` | - |

---

## 9. 업데이트 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-01-12 | 초기 문서 작성 |
| 2026-01-12 | 시계열 분석 섹션 추가 (섹션 6) |

---

*이 문서는 모든 도메인의 Text-to-SQL 시스템에서 공통으로 참조됩니다.*
*도메인별 상세 내용은 각 도메인의 ontology 폴더를 참조하세요.*
