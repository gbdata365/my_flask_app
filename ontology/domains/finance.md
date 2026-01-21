# 재정 데이터베이스 온톨로지

이 문서는 LLM이 재정 관련 자연어 질문을 SQL로 변환할 때 참조하는 도메인 지식입니다.

## 1. 도메인 개요

- **도메인**: 지방자치단체 재정 데이터
- **데이터 기준**: 행정안전부 지방재정365, 지방재정연감
- **연계 키**: admin_code, sido_nm, sigungu_nm (인구 데이터와 연계)

---

## 2. 핵심 테이블

### 2.1 fact_local_finance (지방재정 팩트 테이블)
연도별 지자체 재정 현황입니다.

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|-----------|------|------|
| base_year | VARCHAR | 기준연도 (YYYY) | '2024' |
| admin_code | VARCHAR | 행정구역코드 (FK) | '1100000000' |
| budget_total | BIGINT | 총 예산액 (천원) | 45,000,000,000 |
| revenue_total | BIGINT | 총 세입액 (천원) | 44,500,000,000 |
| expenditure_total | BIGINT | 총 세출액 (천원) | 43,800,000,000 |
| local_tax | BIGINT | 지방세 수입 (천원) | 12,000,000,000 |
| grant_in_aid | BIGINT | 보조금 (천원) | 8,000,000,000 |
| local_debt | BIGINT | 지방채 잔액 (천원) | 5,000,000,000 |

### 2.2 fact_fiscal_index (재정지표 팩트 테이블)
연도별 지자체 재정 지표입니다.

| 컬럼명 | 데이터타입 | 설명 |
|--------|-----------|------|
| base_year | VARCHAR | 기준연도 |
| admin_code | VARCHAR | 행정구역코드 (FK) |
| fiscal_independence | DECIMAL | 재정자립도 (%) |
| fiscal_autonomy | DECIMAL | 재정자주도 (%) |
| debt_ratio | DECIMAL | 채무비율 (%) |
| expenditure_per_capita | BIGINT | 1인당 세출액 (원) |

### 2.3 cache_sigungu_finance (시군구 재정 캐시 테이블)
시군구별 재정 지표 캐시입니다. **인구 데이터와 연계 분석 시 이 테이블 사용 권장**

| 컬럼명 | 데이터타입 | 설명 |
|--------|-----------|------|
| base_year | VARCHAR | 기준연도 |
| sido_nm | VARCHAR | 시도명 |
| sigungu_nm | VARCHAR | 시군구명 |
| budget_total | BIGINT | 총 예산액 |
| fiscal_independence | DECIMAL | 재정자립도 (%) |
| fiscal_autonomy | DECIMAL | 재정자주도 (%) |
| expenditure_per_capita | BIGINT | 1인당 세출액 |
| welfare_budget | BIGINT | 복지예산 |
| welfare_ratio | DECIMAL | 복지예산 비율 (%) |

---

## 3. 도메인 용어 사전

### 3.1 재정 지표 용어

| 자연어 표현 | 컬럼명 | 설명 |
|------------|--------|------|
| 예산, 총예산 | budget_total | 총 예산액 |
| 세입 | revenue_total | 총 세입액 |
| 세출 | expenditure_total | 총 세출액 |
| 지방세, 세금 | local_tax | 지방세 수입 |
| 보조금, 국비 | grant_in_aid | 정부 보조금 |
| 채무, 부채, 빚 | local_debt | 지방채 잔액 |
| 재정자립도 | fiscal_independence | 자체수입/일반회계*100 |
| 재정자주도 | fiscal_autonomy | 자주재원/일반회계*100 |
| 1인당 세출, 1인당 예산 | expenditure_per_capita | 세출액/인구 |
| 복지예산, 사회복지비 | welfare_budget | 사회복지 분야 예산 |

### 3.2 재정 관련 표현

| 자연어 표현 | 의미 |
|------------|------|
| 부자 지역, 재정 여유 | fiscal_independence 높은 지역 |
| 가난한 지역, 재정 열악 | fiscal_independence 낮은 지역 |
| 복지 투자 높은 | welfare_ratio 높은 지역 |

---

## 4. SQL 생성 규칙

### 4.1 기준 시점
- 재정 데이터는 **연도(YYYY)** 기준 (인구는 월별 YYYYMM)
- 최신 연도: `WHERE base_year = (SELECT MAX(base_year) FROM 테이블명)`

### 4.2 인구 데이터 연계
```sql
-- 재정자립도와 고령화율 비교
SELECT
    f.sido_nm, f.sigungu_nm,
    f.fiscal_independence,
    p.elderly_ratio
FROM cache_sigungu_finance f
JOIN cache_sigungu_indicators p
    ON f.sido_nm = p.sido_nm AND f.sigungu_nm = p.sigungu_nm
WHERE f.base_year = (SELECT MAX(base_year) FROM cache_sigungu_finance)
  AND p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
ORDER BY f.fiscal_independence DESC;
```

---

## 5. 예시 질문과 SQL

### 예시 1: 재정자립도 순위
**질문**: "재정자립도가 낮은 시군구 10개"

```sql
SELECT sido_nm, sigungu_nm, fiscal_independence, budget_total
FROM cache_sigungu_finance
WHERE base_year = (SELECT MAX(base_year) FROM cache_sigungu_finance)
ORDER BY fiscal_independence ASC NULLS LAST
LIMIT 10;
```

### 예시 2: 복지예산 비율
**질문**: "복지예산 비율이 높은 지역"

```sql
SELECT sido_nm, sigungu_nm, welfare_ratio, welfare_budget
FROM cache_sigungu_finance
WHERE base_year = (SELECT MAX(base_year) FROM cache_sigungu_finance)
ORDER BY welfare_ratio DESC NULLS LAST
LIMIT 10;
```

---

*TODO: 실제 테이블 구축 후 이 문서를 업데이트하세요.*
