# 기업체현황 온톨로지 (3단계 구조)

> **목표**: 자연어 질문 → SQL 생성 → 표(테이블) 결과 → 차트 → 인사이트 도출

---

## 1단계: 개념 스켈레톤 (Concept Skeleton)

### 메인 테이블 ⭐
```
fact_business_status  # 기업체현황 통계 (핵심 테이블)
  - 출처: 통계청 기업통계등록부(SBR)
  - 갱신: 분기별
  - 지역단위: 시군구 (251개)
```

### 연계 테이블 (선택적)
```
cache_sigungu_indicators  # 인구 지표 (인구연계 분석 시에만 사용)
```

### 차원 (Dimensions)
```
지역: sido_nm(시도), sigungu_nm(시군구)
시간: base_ym(YYYYMM), year, period_type(분기/월/연), period_str
```

### 측정값 - 조직형태별 사업체수
```
org_individual    개인사업체
org_government    국가지방자치단체
org_unincorporated 비법인단체
org_corporation   회사법인
org_nonprofit_corp 회사이외법인
org_total         조직형태_합계
```

### 측정값 - 대표자성별
```
gender_male    남성대표
gender_female  여성대표
gender_unknown 성별미상
gender_total   성별_합계
```

### 측정값 - 영업상태
```
status_active  영업중
status_closed  폐업
status_total   영업상태_합계
```

### 측정값 - 산업분류 (KSIC 대분류 21개)
```
ind_agriculture(농림어업/A), ind_mining(광업/B), ind_manufacturing(제조업/C),
ind_utilities(전기가스/D), ind_water_waste(수도하수/E), ind_construction(건설업/F),
ind_wholesale_retail(도소매/G), ind_transportation(운수창고/H), ind_accommodation_food(숙박음식/I),
ind_ict(정보통신/J), ind_finance(금융보험/K), ind_real_estate(부동산/L),
ind_professional(전문과학/M), ind_admin_support(사업시설/N), ind_public_admin(공공행정/O),
ind_education(교육/P), ind_health_welfare(보건복지/Q), ind_arts_sports(예술스포츠/R),
ind_other_services(협회개인/S), ind_household(가구내고용/T), ind_international(국제기관/U),
ind_unknown(미분류), ind_total(산업_합계)
```

### 측정값 - 수치통계
```
emp_total(종사자수_합계), emp_avg(종사자_평균), emp_count(종사자_건수)
revenue_total(매출_합계_백만원), revenue_avg(매출_평균), revenue_count(매출_건수)
regular_emp_total(상용근로자_합계), temp_emp_total(임시일용_합계)
```

### 인구연계용 컬럼 (cache_sigungu_indicators - 필요시만)
```
total_pop(총인구), elderly_ratio(고령화율), working_pop(생산가능인구)
```

---

## 2단계: 의미 연결 (Semantic Relations)

### 합계 검증 (모두 동일)
```
org_total = gender_total = status_total = ind_total
```

### 구성 관계
```
org_total = org_individual + org_government + org_unincorporated + org_corporation + org_nonprofit_corp
gender_total = gender_male + gender_female + gender_unknown
status_total = status_active + status_closed
ind_total = SUM(모든 ind_* 산업)
```

### 파생 지표 계산식
```
폐업률(%) = status_closed / status_total * 100
여성대표비율(%) = gender_female / gender_total * 100
개인사업체비율(%) = org_individual / org_total * 100
제조업비율(%) = ind_manufacturing / ind_total * 100
사업체당종사자(명) = emp_total / org_total
인구천명당사업체(개) = org_total * 1000 / total_pop  # 인구연계 시
```

### 인구테이블 연계 (선택적)
```
fact_business_status b JOIN cache_sigungu_indicators p
  ON b.sido_nm = p.sido_nm AND b.sigungu_nm = p.sigungu_nm
  WHERE b.base_ym = MAX(b.base_ym) AND p.base_ym = MAX(p.base_ym)
```

### 용어 정규화
```
서울/서울시 → '서울특별시'
경북/경상북도 → '경상북도'
사업체/기업체/업체/회사 → org_total
제조업/제조/공장 → ind_manufacturing
도소매/유통/상업 → ind_wholesale_retail
숙박음식/요식업/음식점 → ind_accommodation_food
```

---

## 3단계: 규칙/추론 (Inference & Constraints)

### SQL 생성 규칙 ⭐⭐⭐
```
1. 시점 미지정 → WHERE base_ym = (SELECT MAX(base_ym) FROM fact_business_status)
2. 순위/TOP N/많은 → ORDER BY ... DESC LIMIT N
3. 낮은/적은/하위 → ORDER BY ... ASC LIMIT N
4. 비율 계산 → ROUND(분자::numeric / NULLIF(분모, 0) * 100, 2)
5. NULL 정렬 → NULLS LAST
6. 인구연계 키워드(인구대비, 천명당 등) 있을 때만 → JOIN cache_sigungu_indicators
```

### 컬럼 한글 별칭 (필수)
```
sido_nm → 시도
sigungu_nm → 시군구
org_total → 사업체수
org_individual → 개인사업체
org_corporation → 회사법인
gender_female → 여성대표
gender_male → 남성대표
status_active → 영업중
status_closed → 폐업
ind_manufacturing → 제조업
ind_wholesale_retail → 도소매업
ind_accommodation_food → 숙박음식업
ind_construction → 건설업
emp_total → 종사자수
revenue_total → 매출액
```

### 데이터 품질
```
'*' 값 → NULL (통계적 비밀보호)
NULL 다발 컬럼: ind_unknown, ind_household, ind_mining, ind_international, ind_utilities
```

### 출력 흐름 ⭐⭐⭐
```
1단계: SQL 실행 → 표(테이블) 결과 출력
2단계: 표 데이터 기반 → 차트 생성 (필요시)
3단계: 표 데이터 분석 → 인사이트 5개 도출
```

### 차트 선택 규칙
```
IF 순위/TOP N 질문 → barh(가로막대), 1위=#F24822(빨강), 나머지=#667EEA(파랑)
IF 구성비/비율 질문 → donut, 5%미만='기타'
IF 시계열/추이 질문 → line + marker
IF 비교 질문 → bar(세로막대)
IF 상관관계 질문 → scatter + 추세선
```

### 보고서 형식
```
## 분석 결과

### 📋 데이터 테이블
[SQL 결과 표]

### 📊 시각화 (차트 요청 시)
[차트 이미지]

### 💡 핵심 인사이트 (5개)
1. **1위/최고값**: {지역}이(가) {값}으로 1위, 전체의 {비율}% 차지
2. **평균 대비**: {시도} 평균({평균값}) 대비 {배수}배 높은 지역 {N}개
3. **특이값**: {지역}은 {특이사항}으로 눈에 띔
4. **구조/비율**: {분류} 비율이 {기준}% 이상인 지역 {N}개
5. **연계분석**: {지표A}와 {지표B} 간 {관계}
```

---

## 4단계: 에러 처리 가이드라인 ⭐

### 에러 발생 시 한글 메시지 형식
```markdown
## ⚠️ 분석 오류 안내

**오류 유형**: [오류 유형 한글명]

**원인**: [원인 설명]

**해결 방법**: [해결 방법 안내]

**대안 질문**:
- [분석 가능한 질문 1]
- [분석 가능한 질문 2]
```

### 주요 에러 유형별 한글 메시지

#### API 요청 한도 초과 (429)
```
## ⚠️ 분석 오류 안내

**오류 유형**: API 요청 한도 초과

**원인**: 짧은 시간에 너무 많은 분석 요청이 발생했습니다.

**해결 방법**:
- 잠시 후(1~2분) 다시 시도해주세요
- 복잡한 질문은 단순하게 나누어 질문해주세요

**대안 질문**:
- 질문을 더 간단하게 바꿔서 시도해보세요
```

#### SQL 오류
```
## ⚠️ 분석 오류 안내

**오류 유형**: SQL 실행 오류

**원인**: 요청하신 데이터 조회 중 문제가 발생했습니다.

**해결 방법**:
- 지역명이나 용어를 정확히 입력해주세요
- 예: "경북" → "경상북도"

**분석 가능한 데이터**:
- 사업체수 (조직형태별, 산업별, 성별, 영업상태별)
- 종사자수, 매출액
- 시도/시군구 단위
```

#### 데이터 없음
```
## ⚠️ 분석 오류 안내

**오류 유형**: 데이터 없음

**원인**: 요청하신 조건에 해당하는 데이터가 없습니다.

**해결 방법**:
- 지역명 또는 조건을 확인해주세요
- 현재 데이터: 2024년 1분기 기준

**대안 질문**:
- "경상북도 제조업 사업체수"
- "전국 시군구별 사업체 순위"
```

#### 네트워크/서버 오류
```
## ⚠️ 분석 오류 안내

**오류 유형**: 서버 연결 오류

**원인**: 일시적인 네트워크 문제가 발생했습니다.

**해결 방법**:
- 잠시 후 다시 시도해주세요
- 문제가 지속되면 관리자에게 문의해주세요
```

---

## 예시 SQL 패턴

### 기본: 시군구별 사업체수 순위
```sql
SELECT sido_nm AS 시도, sigungu_nm AS 시군구, org_total AS 사업체수
FROM fact_business_status
WHERE base_ym = (SELECT MAX(base_ym) FROM fact_business_status)
ORDER BY org_total DESC
LIMIT 10;
```

### 특정 시도 내 산업별 현황
```sql
SELECT sigungu_nm AS 시군구,
       ind_manufacturing AS 제조업,
       ind_wholesale_retail AS 도소매업,
       ind_accommodation_food AS 숙박음식업,
       ind_construction AS 건설업
FROM fact_business_status
WHERE base_ym = (SELECT MAX(base_ym) FROM fact_business_status)
  AND sido_nm = '경상북도'
ORDER BY ind_manufacturing DESC;
```

### 비율 계산: 여성대표 비율
```sql
SELECT sido_nm AS 시도, sigungu_nm AS 시군구,
       gender_female AS 여성대표,
       gender_total AS 전체,
       ROUND(gender_female::numeric / NULLIF(gender_total, 0) * 100, 2) AS 여성대표비율
FROM fact_business_status
WHERE base_ym = (SELECT MAX(base_ym) FROM fact_business_status)
ORDER BY 여성대표비율 DESC
LIMIT 10;
```

### 인구 연계: 인구 천명당 사업체수
```sql
SELECT b.sido_nm AS 시도, b.sigungu_nm AS 시군구,
       b.org_total AS 사업체수,
       p.total_pop AS 총인구,
       ROUND(b.org_total * 1000.0 / NULLIF(p.total_pop, 0), 2) AS 인구천명당사업체
FROM fact_business_status b
JOIN cache_sigungu_indicators p
  ON b.sido_nm = p.sido_nm AND b.sigungu_nm = p.sigungu_nm
WHERE b.base_ym = (SELECT MAX(base_ym) FROM fact_business_status)
  AND p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
ORDER BY 인구천명당사업체 DESC
LIMIT 10;
```

---

## 색상 팔레트
```python
MAIN = ['#667EEA', '#764BA2', '#F24822', '#2ECC71', '#3498DB', '#F39C12', '#9B59B6', '#1ABC9C']
HIGHLIGHT = '#F24822'  # 1위/강조
GRADIENT = ['#1243A6', '#1D64F2', '#4A90E2', '#7EB6FF', '#B8D4FF']
```

---

*최종 수정: 2026-01-15 | 기업 데이터 중심 + 에러 한글화*
