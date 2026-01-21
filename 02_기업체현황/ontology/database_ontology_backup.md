# 기업체현황 데이터베이스 온톨로지
## Database Ontology for Business Status Statistics

---

## 1. 개요 (Overview)

| 항목 | 내용 |
|------|------|
| 테이블명 | `fact_business_status` |
| 데이터 출처 | 통계청 기업체현황 통계 |
| 갱신 주기 | 분기별 |
| 지역 단위 | 시군구 (251개) |
| 데이터 기준 | 2024년 1분기 기준 |

---

## 2. 테이블 스키마 (Table Schema)

### 2.1 기본 정보 컬럼 (Base Information)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 |
|------------|--------|-------------|------|
| `id` | 일련번호 | SERIAL | 기본키 |
| `base_ym` | 기준년월 | VARCHAR(6) | YYYYMM 형식 (예: 202403) |
| `year` | 연도 | VARCHAR(4) | YYYY 형식 (예: 2024) |
| `period_type` | 구분 | VARCHAR(100) | 분기/월간/연간 |
| `period_str` | 기준시기 | VARCHAR(100) | 원본 텍스트 (예: 2024년 1분기) |
| `sido_nm` | 시도명 | VARCHAR(100) | 광역시/도 명칭 |
| `sigungu_nm` | 시군구명 | VARCHAR(100) | 시/군/구 명칭 |

---

### 2.2 조직형태별 컬럼 (Organization Type)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 |
|------------|--------|-------------|------|
| `org_individual` | 개인사업체 | BIGINT | 개인이 운영하는 사업체 수 |
| `org_government` | 국가지방자치단체 | BIGINT | 정부 및 지자체 기관 수 |
| `org_unincorporated` | 비법인단체 | BIGINT | 법인격 없는 단체 수 |
| `org_corporation` | 회사법인 | BIGINT | 회사 형태의 법인 수 |
| `org_nonprofit_corp` | 회사이외법인 | BIGINT | 비영리법인 등 수 |
| `org_total` | 조직형태_합계 | BIGINT | 조직형태별 합계 |

**관계**: `org_total = org_individual + org_government + org_unincorporated + org_corporation + org_nonprofit_corp`

---

### 2.3 대표자성별별 컬럼 (CEO Gender)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 |
|------------|--------|-------------|------|
| `gender_unknown` | 성별미상 | BIGINT | 성별 미확인 대표자 수 |
| `gender_male` | 남성대표 | BIGINT | 남성 대표자 사업체 수 |
| `gender_female` | 여성대표 | BIGINT | 여성 대표자 사업체 수 |
| `gender_total` | 성별_합계 | BIGINT | 성별 합계 |

**관계**: `gender_total = gender_unknown + gender_male + gender_female`

---

### 2.4 폐업여부별 컬럼 (Business Status)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 |
|------------|--------|-------------|------|
| `status_active` | 영업중 | BIGINT | 현재 영업 중인 사업체 수 |
| `status_closed` | 폐업 | BIGINT | 폐업한 사업체 수 |
| `status_total` | 영업상태_합계 | BIGINT | 영업상태 합계 |

**관계**: `status_total = status_active + status_closed`

---

### 2.5 산업분류별 컬럼 (Industry Classification - KSIC)

한국표준산업분류(KSIC: Korean Standard Industrial Classification) 대분류 기준

| 영문 컬럼명 | 한글명 | KSIC 코드 | 설명 |
|------------|--------|-----------|------|
| `ind_unknown` | 산업미분류 | - | 분류 불가 사업체 (NULL 가능) |
| `ind_agriculture` | 농림어업 | A | 농업, 임업 및 어업 |
| `ind_mining` | 광업 | B | 광업 (NULL 가능) |
| `ind_manufacturing` | 제조업 | C | 제조업 |
| `ind_utilities` | 전기가스공급 | D | 전기, 가스, 증기 및 공기조절 공급업 (NULL 가능) |
| `ind_water_waste` | 수도하수폐기물 | E | 수도, 하수 및 폐기물 처리, 원료 재생업 |
| `ind_construction` | 건설업 | F | 건설업 |
| `ind_wholesale_retail` | 도소매업 | G | 도매 및 소매업 |
| `ind_transportation` | 운수창고업 | H | 운수 및 창고업 |
| `ind_accommodation_food` | 숙박음식점 | I | 숙박 및 음식점업 |
| `ind_ict` | 정보통신업 | J | 정보통신업 |
| `ind_finance` | 금융보험업 | K | 금융 및 보험업 |
| `ind_real_estate` | 부동산업 | L | 부동산업 |
| `ind_professional` | 전문과학기술 | M | 전문, 과학 및 기술 서비스업 |
| `ind_admin_support` | 사업시설관리 | N | 사업시설 관리, 사업 지원 및 임대 서비스업 |
| `ind_public_admin` | 공공행정 | O | 공공 행정, 국방 및 사회보장 행정 |
| `ind_education` | 교육서비스 | P | 교육 서비스업 |
| `ind_health_welfare` | 보건복지 | Q | 보건업 및 사회복지 서비스업 |
| `ind_arts_sports` | 예술스포츠여가 | R | 예술, 스포츠 및 여가관련 서비스업 |
| `ind_other_services` | 협회개인서비스 | S | 협회 및 단체, 수리 및 기타 개인 서비스업 |
| `ind_household` | 가구내고용 | T | 가구 내 고용활동 및 달리 분류되지 않은 자가소비 생산활동 (NULL 가능) |
| `ind_international` | 국제기관 | U | 국제 및 외국기관 (NULL 가능) |
| `ind_total` | 산업_합계 | - | 산업분류별 합계 |

**참고**: '*' 값(통계적 비밀보호)은 NULL로 처리됨

---

### 2.6 대표사업체별 컬럼 (Main Business)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 |
|------------|--------|-------------|------|
| `main_biz_unknown` | 대표사업체미상 | BIGINT | 대표사업체 미확인 |
| `main_biz_total` | 대표사업체_합계 | BIGINT | 대표사업체 합계 |

---

### 2.7 수치형통계 컬럼 (Numeric Statistics)

#### 2.7.1 종사자수 (Employee Count)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 |
|------------|--------|-------------|------|
| `emp_count` | 종사자수_건수 | BIGINT | 종사자수 정보가 있는 사업체 수 |
| `emp_total` | 종사자수_합계 | BIGINT | 총 종사자 수 |
| `emp_avg` | 종사자수_평균 | NUMERIC(20,2) | 사업체당 평균 종사자 수 |
| `emp_null_count` | 종사자수_공백 | BIGINT | 종사자수 정보 없는 사업체 수 |

#### 2.7.2 매출금액 (Revenue)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 | 단위 |
|------------|--------|-------------|------|------|
| `revenue_count` | 매출금액_건수 | BIGINT | 매출 정보가 있는 사업체 수 | 건 |
| `revenue_total` | 매출금액_합계 | BIGINT | 총 매출금액 | 백만원 |
| `revenue_avg` | 매출금액_평균 | NUMERIC(20,2) | 사업체당 평균 매출 | 백만원 |
| `revenue_null_count` | 매출금액_공백 | BIGINT | 매출 정보 없는 사업체 수 | 건 |

#### 2.7.3 상용근로자수 (Regular Employees)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 |
|------------|--------|-------------|------|
| `regular_emp_count` | 상용근로자_건수 | BIGINT | 상용근로자 정보가 있는 사업체 수 |
| `regular_emp_total` | 상용근로자_합계 | BIGINT | 총 상용근로자 수 |
| `regular_emp_avg` | 상용근로자_평균 | NUMERIC(20,2) | 사업체당 평균 상용근로자 수 |
| `regular_emp_null_count` | 상용근로자_공백 | BIGINT | 상용근로자 정보 없는 사업체 수 |

#### 2.7.4 임시일용근로자수 (Temporary Employees)

| 영문 컬럼명 | 한글명 | 데이터 타입 | 설명 |
|------------|--------|-------------|------|
| `temp_emp_count` | 임시일용_건수 | BIGINT | 임시일용 근로자 정보가 있는 사업체 수 |
| `temp_emp_total` | 임시일용_합계 | BIGINT | 총 임시일용 근로자 수 |
| `temp_emp_avg` | 임시일용_평균 | NUMERIC(20,2) | 사업체당 평균 임시일용 근로자 수 |
| `temp_emp_null_count` | 임시일용_공백 | BIGINT | 임시일용 정보 없는 사업체 수 |

---

## 3. 데이터 품질 규칙 (Data Quality Rules)

### 3.1 통계적 비밀보호 (Statistical Disclosure Control)

- 원본 데이터의 `*` 값은 통계적 비밀보호를 위해 비공개 처리된 값
- 데이터베이스에서는 `NULL`로 저장됨
- 주로 소수 사업체가 있는 산업 분류에서 발생

### 3.2 NULL 값이 발생하는 컬럼

| 컬럼명 | NULL 건수 (251건 중) | 사유 |
|--------|---------------------|------|
| `ind_unknown` | 96건 | 통계적 비밀보호 |
| `ind_household` | 87건 | 통계적 비밀보호 |
| `ind_mining` | 60건 | 통계적 비밀보호 |
| `ind_international` | 35건 | 통계적 비밀보호 |
| `ind_utilities` | 1건 | 통계적 비밀보호 |

---

## 4. 관계 및 제약조건 (Relationships & Constraints)

### 4.1 합계 검증 규칙

```sql
-- 조직형태 합계 검증
org_total = org_individual + org_government + org_unincorporated
          + org_corporation + org_nonprofit_corp

-- 성별 합계 검증
gender_total = gender_unknown + gender_male + gender_female

-- 영업상태 합계 검증
status_total = status_active + status_closed

-- 모든 분류의 전체 합계는 동일해야 함
org_total = gender_total = status_total = ind_total = main_biz_total
```

### 4.2 인덱스

| 인덱스명 | 컬럼 | 용도 |
|----------|------|------|
| `idx_fact_business_status_base_ym` | `base_ym` | 기준년월 조회 |
| `idx_fact_business_status_sido` | `sido_nm` | 시도별 조회 |
| `idx_fact_business_status_sigungu` | `sigungu_nm` | 시군구별 조회 |

---

## 5. 활용 예시 (Usage Examples)

### 5.1 시도별 사업체 현황 조회

```sql
SELECT sido_nm,
       SUM(org_total) as total_business,
       SUM(status_active) as active_business,
       ROUND(SUM(status_active)::numeric / SUM(org_total) * 100, 2) as active_rate
FROM fact_business_status
WHERE base_ym = '202403'
GROUP BY sido_nm
ORDER BY total_business DESC;
```

### 5.2 산업별 사업체 분포

```sql
SELECT sido_nm,
       ind_manufacturing as manufacturing,
       ind_wholesale_retail as retail,
       ind_accommodation_food as food_service,
       ind_construction as construction
FROM fact_business_status
WHERE base_ym = '202403' AND sido_nm = '서울특별시';
```

### 5.3 여성 대표 사업체 비율

```sql
SELECT sido_nm,
       gender_total,
       gender_female,
       ROUND(gender_female::numeric / NULLIF(gender_total, 0) * 100, 2) as female_ratio
FROM fact_business_status
WHERE base_ym = '202403'
ORDER BY female_ratio DESC;
```

---

## 6. 데이터 갱신 이력 (Update History)

| 날짜 | 기준시기 | 작업 내용 |
|------|----------|----------|
| 2026-01-13 | 2024년 1분기 | 최초 데이터 적재 (251건) |

---

## 7. 참고 자료 (References)

- [통계청 기업체현황](https://kosis.kr)
- [한국표준산업분류 (KSIC)](https://kssc.kostat.go.kr)
- 데이터 처리 스크립트: `02_기업체현황/read_xlsx.py`

---

## 8. 인구통계 연계 분석 (Cross-Domain Analysis)

### 8.1 연계 테이블

기업체 데이터와 인구 데이터를 연계하여 분석할 수 있습니다.

| 테이블명 | 설명 | 연계 키 |
|----------|------|---------|
| `fact_business_status` | 기업체 현황 (이 테이블) | sido_nm, sigungu_nm |
| `cache_sigungu_indicators` | 인구 지표 캐시 | sido_nm, sigungu_nm |

### 8.2 연계 분석 예시

#### 8.2.1 인구 천명당 사업체수

```sql
SELECT
    b.sido_nm AS 시도,
    b.sigungu_nm AS 시군구,
    b.org_total AS 사업체수,
    p.total_pop AS 총인구,
    ROUND(b.org_total * 1000.0 / NULLIF(p.total_pop, 0), 2) AS "인구천명당_사업체수"
FROM fact_business_status b
JOIN cache_sigungu_indicators p
    ON b.sido_nm = p.sido_nm AND b.sigungu_nm = p.sigungu_nm
WHERE b.base_ym = (SELECT MAX(base_ym) FROM fact_business_status)
  AND p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
ORDER BY "인구천명당_사업체수" DESC
LIMIT 10;
```

#### 8.2.2 고령화율 vs 제조업 비율 관계

```sql
SELECT
    b.sido_nm AS 시도,
    b.sigungu_nm AS 시군구,
    p.elderly_ratio AS 고령화율,
    ROUND(b.ind_manufacturing::numeric / NULLIF(b.ind_total, 0) * 100, 2) AS 제조업비율,
    ROUND(b.ind_accommodation_food::numeric / NULLIF(b.ind_total, 0) * 100, 2) AS 숙박음식업비율
FROM fact_business_status b
JOIN cache_sigungu_indicators p
    ON b.sido_nm = p.sido_nm AND b.sigungu_nm = p.sigungu_nm
WHERE b.base_ym = (SELECT MAX(base_ym) FROM fact_business_status)
  AND p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
ORDER BY p.elderly_ratio DESC
LIMIT 20;
```

#### 8.2.3 생산가능인구 대비 종사자수

```sql
SELECT
    b.sido_nm AS 시도,
    b.sigungu_nm AS 시군구,
    p.working_pop AS 생산가능인구,
    b.emp_total AS 종사자수,
    ROUND(b.emp_total::numeric / NULLIF(p.working_pop, 0) * 100, 2) AS "종사자비율(%)"
FROM fact_business_status b
JOIN cache_sigungu_indicators p
    ON b.sido_nm = p.sido_nm AND b.sigungu_nm = p.sigungu_nm
WHERE b.base_ym = (SELECT MAX(base_ym) FROM fact_business_status)
  AND p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
ORDER BY "종사자비율(%)" DESC
LIMIT 10;
```

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
| 데이터 기준 | [기준년월: YYYY년 N분기] |
| 분석 범위 | [전국/특정시도/특정시군구] |
| 데이터 출처 | 통계청 기업체현황, 행정안전부 인구통계 |

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

---
*본 보고서는 AI 기업체현황 분석 시스템에서 자동 생성되었습니다.*
```

### 9.2 인사이트 도출 가이드

**5개 인사이트는 다음 관점에서 도출합니다:**

| 순번 | 관점 | 도출 방향 | 예시 |
|------|------|----------|------|
| 1 | **1위/최고값** | 가장 높은 지역/항목 특성 분석 | "제조업 사업체 1위는 ○○시로 전체의 N%를 차지" |
| 2 | **평균 대비** | 전국/시도 평균과 비교 | "경북 평균(N개) 대비 2배 이상 높은 시군은 5개" |
| 3 | **특이값/이상치** | 눈에 띄는 패턴이나 예외 | "농림어업은 ○○군에 90% 이상 집중" |
| 4 | **비율/구조** | 구성비 또는 비율 분석 | "개인사업체 비율이 80% 이상인 시군은 N개" |
| 5 | **연계/상관** | 인구-기업 등 연계 분석 | "고령화율 상위 10개 시군의 제조업 비율은 평균 N%" |

### 9.3 보고서 형식 예시 (실제 샘플)

```markdown
# 📊 경상북도 제조업 사업체 현황 분석 보고서

## 1. 분석 개요
| 항목 | 내용 |
|------|------|
| 분석 목적 | 경상북도 시군구별 제조업 사업체 분포 및 특성 파악 |
| 데이터 기준 | 2024년 1분기 |
| 분석 범위 | 경상북도 23개 시군 |
| 데이터 출처 | 통계청 기업체현황, 행정안전부 인구통계 |

---

## 2. 주요 지표 요약

| 지표 | 값 | 비고 |
|------|-----|------|
| 경북 전체 사업체수 | 152,847개 | 전국 대비 4.2% |
| 제조업 사업체수 | 18,423개 | 경북 전체의 12.1% |
| 제조업 종사자수 | 245,621명 | 사업체당 평균 13.3명 |

---

## 3. 상세 분석 결과

| 순위 | 시군구 | 제조업 사업체수 | 비율 | 종사자수 |
|------|--------|---------------|------|----------|
| 1 | 구미시 | 4,521개 | 24.5% | 89,234명 |
| 2 | 포항시 | 3,892개 | 21.1% | 67,123명 |
| 3 | 경산시 | 2,134개 | 11.6% | 34,567명 |
| 4 | 김천시 | 1,567개 | 8.5% | 23,456명 |
| 5 | 경주시 | 1,234개 | 6.7% | 18,901명 |

---

## 4. 핵심 인사이트 (5개)

### 💡 인사이트 1: 구미-포항 양극화
경북 제조업의 45.6%(8,413개)가 구미시와 포항시에 집중되어 있습니다.
두 도시가 경북 제조업 허브 역할을 담당하고 있음을 보여줍니다.

### 💡 인사이트 2: 사업체당 종사자수 격차
구미시는 사업체당 평균 19.7명으로 경북 평균(13.3명)의 1.5배입니다.
이는 구미시에 중대형 제조업체가 집중되어 있음을 시사합니다.

### 💡 인사이트 3: 농촌 지역 제조업 취약
영양군(45개), 울릉군(12개), 봉화군(89개) 등 농촌 지역은
제조업 사업체가 100개 미만으로 산업 다각화가 필요합니다.

### 💡 인사이트 4: 고령화-제조업 역상관
고령화율 상위 5개 시군(영양, 의성, 청송, 봉화, 영덕)의 평균 제조업 비율은
5.2%로 경북 평균(12.1%)의 절반에도 미치지 못합니다.

### 💡 인사이트 5: 인구 대비 제조업 효율성
구미시는 인구 천명당 제조업 종사자수가 215명으로 경북 1위입니다.
이는 경북 평균(92명)의 2.3배에 달하는 수치입니다.

---

## 5. 시사점 및 제언

### 📌 정책적 시사점
- 구미-포항 외 지역의 제조업 육성을 위한 산업단지 확충 필요
- 고령화 지역은 제조업보다 6차산업(농업+가공+관광) 육성이 현실적

### 🔍 추가 분석 제안
- "경북 제조업 종사자 연령별 분포는?"
- "경북 제조업 폐업률 추이 분석"

---
*본 보고서는 AI 기업체현황 분석 시스템에서 자동 생성되었습니다.*
```

### 9.4 SQL 생성 불가능한 경우

```markdown
# ⚠️ 데이터 제한 안내

## 요청 내용
[사용자 질문]

## 제한 사유
요청하신 **[XXX]** 정보는 현재 데이터베이스에 포함되어 있지 않습니다.

## 현재 분석 가능한 데이터

### 기업체현황 (fact_business_status)
| 분류 | 포함 항목 |
|------|----------|
| 사업체수 | 조직형태별, 산업분류별, 대표자성별, 영업상태별 |
| 종사자수 | 총종사자, 상용근로자, 임시일용근로자 |
| 매출액 | 총매출, 평균매출 |
| 지역 | 시도, 시군구 단위 |

### 인구통계 (cache_sigungu_indicators)
| 분류 | 포함 항목 |
|------|----------|
| 인구 | 총인구, 남녀인구, 연령별 인구 |
| 지표 | 고령화율, 유소년율, 1인가구비율 |

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
| **순위/비교** | 가로막대 (barh) | "제조업 사업체 많은 시군구 10개" |
| **구성비** | 도넛/파이 (pie) | "경북 산업별 사업체 비율" |
| **시계열** | 라인 (line) | "분기별 사업체수 추이" |
| **분포** | 히스토그램 (hist) | "사업체수 분포" |
| **상관관계** | 산점도 (scatter) | "고령화율 vs 제조업 비율" |
| **지역비교** | 세로막대 (bar) | "시도별 사업체수 비교" |

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

# 단일 색상 그라데이션 (순위 표현)
BLUE_GRADIENT = ['#1243A6', '#1D64F2', '#4A90E2', '#7EB6FF', '#B8D4FF']

# 대비 색상 (비교 분석)
COMPARE_COLORS = {
    'positive': '#2ECC71',  # 증가/긍정
    'negative': '#E74C3C',  # 감소/부정
    'neutral': '#95A5A6',   # 중립
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
# 가로막대 - 순위/비교에 적합
fig, ax = plt.subplots(figsize=(10, 8))

# 색상: 1위는 강조색, 나머지는 그라데이션
colors = ['#F24822'] + ['#667EEA'] * (len(data) - 1)

bars = ax.barh(y_labels, values, color=colors, edgecolor='none')

# 값 표시 (막대 끝에)
for bar, val in zip(bars, values):
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
            f'{val:,}', va='center', fontsize=10)

ax.invert_yaxis()  # 1위가 위로
ax.set_title('제조업 사업체수 TOP 10', fontsize=16, fontweight='bold')
```

#### 10.4.2 도넛 차트 (구성비)

```python
# 도넛 차트 - 구성비에 적합
fig, ax = plt.subplots(figsize=(10, 10))

# 5% 미만은 '기타'로 통합
wedges, texts, autotexts = ax.pie(
    values,
    labels=labels,
    colors=COLORS[:len(values)],
    autopct=lambda pct: f'{pct:.1f}%' if pct >= 5 else '',
    startangle=90,
    pctdistance=0.75,
    wedgeprops={'width': 0.5, 'edgecolor': 'white'}
)

# 중앙에 총합 표시
ax.text(0, 0, f'총 {total:,}개', ha='center', va='center',
        fontsize=20, fontweight='bold')

ax.set_title('산업별 사업체 구성비', fontsize=16, fontweight='bold')
```

#### 10.4.3 라인 차트 (시계열)

```python
# 라인 차트 - 시계열/추이에 적합
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

ax.set_title('분기별 사업체수 추이', fontsize=16, fontweight='bold')
ax.set_xlabel('기준분기')
ax.set_ylabel('사업체수')
```

#### 10.4.4 산점도 (상관관계)

```python
# 산점도 - 상관관계 분석에 적합
fig, ax = plt.subplots(figsize=(10, 8))

scatter = ax.scatter(x_values, y_values,
                     c='#667EEA',
                     s=100,
                     alpha=0.7,
                     edgecolors='white')

# 추세선 추가
z = np.polyfit(x_values, y_values, 1)
p = np.poly1d(z)
ax.plot(x_values, p(x_values), '--', color='#F24822', linewidth=2, label='추세선')

# 주요 지점 레이블
for i, name in enumerate(top_5_names):
    ax.annotate(name, (x_values[i], y_values[i]),
                textcoords='offset points', xytext=(5, 5), fontsize=9)

ax.set_title('고령화율 vs 제조업 비율', fontsize=16, fontweight='bold')
ax.set_xlabel('고령화율 (%)')
ax.set_ylabel('제조업 비율 (%)')
```

### 10.5 범례 위치 가이드

| 차트 유형 | 범례 위치 | 설정 코드 |
|----------|----------|----------|
| 막대 (적은 항목) | 우측 상단 | `loc='upper right'` |
| 막대 (많은 항목) | 범례 생략, 직접 레이블 | - |
| 라인 (다중) | 차트 외부 우측 | `bbox_to_anchor=(1.02, 1)` |
| 도넛/파이 | 우측 | `bbox_to_anchor=(1.2, 0.5)` |
| 산점도 | 좌측 하단 | `loc='lower left'` |

### 10.6 데이터 값 표시 규칙

| 데이터 유형 | 표시 형식 | 예시 |
|------------|----------|------|
| 사업체수 | 천단위 쉼표 | `1,234개` |
| 비율 | 소수점 1자리 | `12.3%` |
| 금액(백만원) | 천단위 쉼표 | `1,234백만원` |
| 인구 | 천단위 쉼표 | `123,456명` |

```python
# 숫자 포맷팅 함수
def format_number(val, type='count'):
    if type == 'count':
        return f'{val:,.0f}개'
    elif type == 'ratio':
        return f'{val:.1f}%'
    elif type == 'money':
        return f'{val:,.0f}백만원'
    elif type == 'population':
        return f'{val:,.0f}명'
```

---

## 11. 자주 묻는 질문 유형별 처리

### 11.1 지역별 현황 질문
- "경상북도 사업체 현황" → 보고서 형식 + 시군구별 집계 + 5개 인사이트
- "제조업 많은 지역" → 산업분류별 필터 + 순위 + 평균 대비 분석

### 11.2 비율/순위 질문
- "여성 대표 비율 높은 곳" → 비율 계산 + 상위/하위 특성 비교
- "폐업률 높은 시군구" → 비율 순위 + 원인 추정 인사이트

### 11.3 연계 분석 질문
- "인구 대비 사업체" → 인구 테이블 JOIN + 효율성 지표 도출
- "고령화 지역의 산업구조" → 상관관계 분석 인사이트

### 11.4 추세/변화 질문
- "분기별 변화" → 시계열 데이터 확인 후 가능 여부 안내
- 현재는 단일 분기 데이터 → 향후 추세 분석 가능 안내

### 11.5 차트 요청 질문
- "차트로 보여줘" → 데이터 유형에 맞는 차트 자동 선택
- "그래프" → 가로막대(순위), 도넛(비율), 라인(추이) 중 선택

---

*이 온톨로지는 기업체현황 데이터콩 챗봇에서 참조됩니다. 데이터 구조나 분석 요구사항이 변경되면 함께 업데이트해주세요.*
