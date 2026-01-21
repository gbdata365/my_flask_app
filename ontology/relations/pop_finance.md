# 인구-재정 연계 분석 가이드

이 문서는 인구 데이터와 재정 데이터를 함께 분석할 때 참조하는 연계 규칙입니다.

## 1. 연계 키

| 인구 테이블 | 재정 테이블 | 연계 방법 |
|------------|------------|----------|
| cache_sigungu_indicators | cache_sigungu_finance | sido_nm + sigungu_nm |
| dim_admin_area | fact_local_finance | admin_code |

---

## 2. 시점 매핑 주의사항

- **인구 데이터**: 월별 (base_ym = 'YYYYMM')
- **재정 데이터**: 연도별 (base_year = 'YYYY')

```sql
-- 연계 시 시점 처리
SELECT ...
FROM cache_sigungu_finance f
JOIN cache_sigungu_indicators p
    ON f.sido_nm = p.sido_nm AND f.sigungu_nm = p.sigungu_nm
WHERE f.base_year = '2024'
  AND p.base_ym LIKE '2024%'  -- 또는 특정 월
  AND p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators WHERE base_ym LIKE '2024%')
```

---

## 3. 주요 연계 분석 패턴

### 3.1 고령화 vs 복지예산
고령화율이 높은 지역의 복지예산 투입 현황

```sql
SELECT
    p.sido_nm, p.sigungu_nm,
    p.elderly_ratio,
    p.elderly_pop,
    f.welfare_budget,
    f.welfare_ratio,
    ROUND(f.welfare_budget::numeric / NULLIF(p.elderly_pop, 0), 0) as welfare_per_elderly
FROM cache_sigungu_indicators p
JOIN cache_sigungu_finance f
    ON p.sido_nm = f.sido_nm AND p.sigungu_nm = f.sigungu_nm
WHERE p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND f.base_year = (SELECT MAX(base_year) FROM cache_sigungu_finance)
ORDER BY p.elderly_ratio DESC;
```

### 3.2 인구 규모 vs 재정자립도
인구가 많은 지역과 재정자립도의 관계

```sql
SELECT
    p.sido_nm, p.sigungu_nm,
    p.total_pop,
    f.fiscal_independence,
    f.expenditure_per_capita
FROM cache_sigungu_indicators p
JOIN cache_sigungu_finance f
    ON p.sido_nm = f.sido_nm AND p.sigungu_nm = f.sigungu_nm
WHERE p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND f.base_year = (SELECT MAX(base_year) FROM cache_sigungu_finance)
ORDER BY p.total_pop DESC;
```

### 3.3 1인당 예산 분석
1인당 세출액과 인구 특성의 관계

```sql
SELECT
    p.sido_nm, p.sigungu_nm,
    p.total_pop,
    p.elderly_ratio,
    p.single_ratio,
    f.expenditure_per_capita,
    f.welfare_budget / NULLIF(p.total_pop, 0) as welfare_per_capita
FROM cache_sigungu_indicators p
JOIN cache_sigungu_finance f
    ON p.sido_nm = f.sido_nm AND p.sigungu_nm = f.sigungu_nm
WHERE p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND f.base_year = (SELECT MAX(base_year) FROM cache_sigungu_finance)
ORDER BY f.expenditure_per_capita DESC;
```

---

## 4. 자연어 질문 → SQL 변환 예시

### 예시 1
**질문**: "고령화율이 높은데 복지예산이 적은 지역"

```sql
SELECT
    p.sido_nm, p.sigungu_nm,
    p.elderly_ratio,
    f.welfare_ratio
FROM cache_sigungu_indicators p
JOIN cache_sigungu_finance f
    ON p.sido_nm = f.sido_nm AND p.sigungu_nm = f.sigungu_nm
WHERE p.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND f.base_year = (SELECT MAX(base_year) FROM cache_sigungu_finance)
  AND p.elderly_ratio > 20  -- 고령화율 20% 이상
ORDER BY f.welfare_ratio ASC
LIMIT 10;
```

### 예시 2
**질문**: "인구 감소 지역 중 재정자립도 현황"

```sql
-- 전년 대비 인구 감소 지역의 재정자립도
WITH pop_change AS (
    SELECT
        c.sido_nm, c.sigungu_nm,
        c.total_pop as current_pop,
        p.total_pop as prev_pop,
        c.total_pop - p.total_pop as pop_diff
    FROM cache_sigungu_indicators c
    JOIN cache_sigungu_indicators p
        ON c.sido_nm = p.sido_nm
        AND c.sigungu_nm = p.sigungu_nm
        AND p.base_ym = '202310'  -- 1년 전
    WHERE c.base_ym = '202410'
)
SELECT
    pc.sido_nm, pc.sigungu_nm,
    pc.pop_diff,
    f.fiscal_independence
FROM pop_change pc
JOIN cache_sigungu_finance f
    ON pc.sido_nm = f.sido_nm AND pc.sigungu_nm = f.sigungu_nm
WHERE pc.pop_diff < 0  -- 인구 감소
  AND f.base_year = '2024'
ORDER BY pc.pop_diff ASC;
```

---

## 5. 분석 인사이트 키워드

연계 분석 시 활용할 수 있는 주요 인사이트:

| 키워드 | 분석 방향 |
|--------|----------|
| 고령화 재정부담 | elderly_ratio vs welfare_budget |
| 인구유출 재정악화 | pop_change vs fiscal_independence |
| 1인가구 복지수요 | single_ratio vs welfare_per_capita |
| 지방소멸위험 | elderly_ratio + pop_decrease + fiscal_independence |
| 복지사각지대 | elderly_ratio 높음 + welfare_ratio 낮음 |

---

*이 문서는 인구-재정 연계 분석 시 참조됩니다.*
