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

### 2.3 fact_population_age_group (연령대별 인구 팩트 테이블)
월별 연령대별 인구 통계입니다.

| 컬럼명 | 데이터타입 | 설명 |
|--------|-----------|------|
| base_ym | VARCHAR | 기준년월 |
| admin_code | VARCHAR | 행정구역코드 (FK) |
| total_pop | INTEGER | 총인구수 |
| male_0_9 | INTEGER | 남자 0~9세 |
| female_0_9 | INTEGER | 여자 0~9세 |
| male_10_19 | INTEGER | 남자 10~19세 |
| female_10_19 | INTEGER | 여자 10~19세 |
| male_20_29 | INTEGER | 남자 20~29세 |
| ... | ... | (30대~90대까지 동일 패턴) |
| male_100_over | INTEGER | 남자 100세 이상 |
| female_100_over | INTEGER | 여자 100세 이상 |

### 2.4 fact_single_household (1인가구 팩트 테이블)
월별 1인가구 통계입니다.

| 컬럼명 | 데이터타입 | 설명 |
|--------|-----------|------|
| base_ym | VARCHAR | 기준년월 |
| admin_code | VARCHAR | 행정구역코드 (FK) |
| single_total | INTEGER | 1인가구 총수 |
| single_male | INTEGER | 남자 1인가구수 |
| single_female | INTEGER | 여자 1인가구수 |
| single_65_over | INTEGER | 65세 이상 1인가구수 |

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

## 3. 도메인 용어 사전

### 3.1 시도명 매핑
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

### 3.2 지표 용어 매핑

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

---

## 4. SQL 생성 규칙

### 4.1 기본 규칙
1. **최신 데이터**: 특정 시점이 언급되지 않으면 최신 base_ym 사용
   ```sql
   WHERE base_ym = (SELECT MAX(base_ym) FROM table_name)
   ```

2. **시군구 단위 조회**: `cache_sigungu_indicators` 테이블 우선 사용

3. **NULL 처리**: 정렬 시 NULL은 마지막으로
   ```sql
   ORDER BY column_name DESC NULLS LAST
   ```

### 4.2 JOIN 규칙
- 상세 데이터 필요 시: `fact_*` 테이블과 `dim_admin_area` JOIN
- 집계 데이터: `cache_sigungu_indicators` 직접 사용

---

## 5. 예시 질문과 SQL

### 예시 1: 고령화율 높은 지역
**질문**: "고령화율이 가장 높은 시군구 10개"

```sql
SELECT sido_nm, sigungu_nm, elderly_ratio, total_pop
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
ORDER BY elderly_ratio DESC NULLS LAST
LIMIT 10;
```

### 예시 2: 특정 시도 내 조회
**질문**: "경상북도에서 1인가구 비율이 높은 시군"

```sql
SELECT sigungu_nm, single_ratio, single_household_cnt, household_cnt
FROM cache_sigungu_indicators
WHERE base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND sido_nm = '경상북도'
ORDER BY single_ratio DESC NULLS LAST
LIMIT 10;
```

---

*이 문서는 Text-to-SQL LLM 시스템에서 참조됩니다.*
