# -*- coding: utf-8 -*-
"""
Cache 테이블 생성/갱신 모듈 (Cache Table Transfer Module)
=========================================================

이 모듈은 Fact 테이블에서 집계하여 Cache 테이블을 생성/갱신합니다.
code_age_group 테이블에서 연령 그룹 정의를 동적으로 읽어와 DDL 및 쿼리를 생성합니다.

주요 기능:
    - cache_sigungu_indicators: 시군구별 인구지표 캐시 테이블
    - code_age_group 테이블 기반 동적 컬럼 생성

시도명/시도코드 정규화:
    - 강원도 / 강원특별자치도 → 강원특별자치도 (42)
    - 전라북도 / 전북특별자치도 → 전북특별자치도 (45)
    - 제주도 / 제주특별자치도 → 제주특별자치도 (50)

사용법:
    python transfer.py --refresh          # 전체 갱신
    python transfer.py --month 202512     # 특정 월만 갱신
    python transfer.py --init             # 테이블 재생성

Author: Claude AI Agent
Created: 2026-01-23
"""

import os
import sys
import argparse
from pathlib import Path

# 프로젝트 루트 경로를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from loguru import logger
from module.db import get_db_engine, get_db_connection

# ============================================================
# 시도명/시도코드 정규화 매핑
# ============================================================

# 시도명 정규화 SQL CASE문
SIDO_NAME_NORMALIZE_SQL = """
    CASE
        WHEN sido_nm IN ('강원특별자치도', '강원도') THEN '강원특별자치도'
        WHEN sido_nm IN ('전북특별자치도', '전라북도') THEN '전북특별자치도'
        WHEN sido_nm IN ('제주특별자치도', '제주도') THEN '제주특별자치도'
        ELSE sido_nm
    END
"""

# 시도코드 정규화 SQL CASE문 (시도명 기준)
SIDO_CODE_NORMALIZE_SQL = """
    CASE
        WHEN sido_nm IN ('강원특별자치도', '강원도') THEN '42'
        WHEN sido_nm IN ('전북특별자치도', '전라북도') THEN '45'
        WHEN sido_nm IN ('제주특별자치도', '제주도') THEN '50'
        ELSE LEFT(sigungu_code, 2)
    END
"""

# 시도 별칭 SQL CASE문
SIDO_ALIAS_SQL = """
    CASE
        WHEN sido_nm IN ('서울특별시') THEN '서울'
        WHEN sido_nm IN ('부산광역시') THEN '부산'
        WHEN sido_nm IN ('대구광역시') THEN '대구'
        WHEN sido_nm IN ('인천광역시') THEN '인천'
        WHEN sido_nm IN ('광주광역시') THEN '광주'
        WHEN sido_nm IN ('대전광역시') THEN '대전'
        WHEN sido_nm IN ('울산광역시') THEN '울산'
        WHEN sido_nm IN ('세종특별자치시') THEN '세종'
        WHEN sido_nm IN ('경기도') THEN '경기'
        WHEN sido_nm IN ('강원특별자치도', '강원도') THEN '강원'
        WHEN sido_nm IN ('충청북도') THEN '충북'
        WHEN sido_nm IN ('충청남도') THEN '충남'
        WHEN sido_nm IN ('전북특별자치도', '전라북도') THEN '전북'
        WHEN sido_nm IN ('전라남도') THEN '전남'
        WHEN sido_nm IN ('경상북도') THEN '경북'
        WHEN sido_nm IN ('경상남도') THEN '경남'
        WHEN sido_nm IN ('제주특별자치도', '제주도') THEN '제주'
        ELSE LEFT(sido_nm, 2)
    END
"""


def get_age_group_definitions():
    """code_age_group 테이블에서 연령 그룹 정의를 읽어옵니다."""
    engine = get_db_engine()
    df = pd.read_sql("""
        SELECT id, category, category_name, code, code_name, column_name, age_start, age_end, sort_order
        FROM code_age_group
        WHERE is_active = true
        ORDER BY category, sort_order
    """, engine)
    return df


def generate_age_sum_sql(age_start: int, age_end: int, prefix: str = 'p') -> str:
    """
    주어진 연령 범위에 대한 SUM SQL을 생성합니다.

    Args:
        age_start: 시작 연령
        age_end: 종료 연령 (999이면 110세 이상 포함)
        prefix: 테이블 alias (기본값 'p')

    Returns:
        SUM SQL 문자열
    """
    # 실제 종료 연령 계산 (110세 이상은 별도 처리)
    actual_end = min(age_end, 109)

    male_cols = [f"COALESCE({prefix}.male_age_{i}, 0)" for i in range(age_start, actual_end + 1)]
    female_cols = [f"COALESCE({prefix}.female_age_{i}, 0)" for i in range(age_start, actual_end + 1)]

    # 110세 이상 포함 여부
    if age_end >= 110:
        male_cols.append(f"COALESCE({prefix}.male_age_110_over, 0)")
        female_cols.append(f"COALESCE({prefix}.female_age_110_over, 0)")

    all_cols = male_cols + female_cols
    return f"SUM({' + '.join(all_cols)})"


def generate_ddl(age_groups_df: pd.DataFrame) -> str:
    """code_age_group 정의를 기반으로 DDL을 생성합니다."""

    # 기본 컬럼들
    base_columns = """
    base_ym DATE NOT NULL,
    sido_cd VARCHAR(2),
    sido_nm VARCHAR(50),
    sido_alias VARCHAR(4),
    sigungu_code VARCHAR(10),
    sigungu_nm VARCHAR(50),

    -- 기본 인구
    total_pop BIGINT,
    male_pop BIGINT,
    female_pop BIGINT,

    -- 세대
    household_cnt BIGINT,
    single_cnt BIGINT,
    male_single BIGINT,
    female_single BIGINT,
    elderly_single BIGINT,
    super_elderly_single BIGINT,
    young_adult_single BIGINT,
    youth_single BIGINT,

    -- 5세별 인구 (21개)
    pop_0_4 BIGINT,
    pop_5_9 BIGINT,
    pop_10_14 BIGINT,
    pop_15_19 BIGINT,
    pop_20_24 BIGINT,
    pop_25_29 BIGINT,
    pop_30_34 BIGINT,
    pop_35_39 BIGINT,
    pop_40_44 BIGINT,
    pop_45_49 BIGINT,
    pop_50_54 BIGINT,
    pop_55_59 BIGINT,
    pop_60_64 BIGINT,
    pop_65_69 BIGINT,
    pop_70_74 BIGINT,
    pop_75_79 BIGINT,
    pop_80_84 BIGINT,
    pop_85_89 BIGINT,
    pop_90_94 BIGINT,
    pop_95_99 BIGINT,
    pop_100_over BIGINT"""

    # code_age_group 기반 동적 컬럼 생성
    age_columns = []
    for _, row in age_groups_df.iterrows():
        col_name = row['column_name']
        code_name = row['code_name']
        age_start = row['age_start']
        age_end = row['age_end']

        # 5세별은 이미 기본 컬럼에 포함되어 있으므로 스킵
        if row['category'] == 1:  # 5세별
            continue

        age_range = f"{age_start}-{age_end}" if age_end < 999 else f"{age_start}+"
        age_columns.append(f"    {col_name} BIGINT,  -- {code_name} ({age_range})")

    dynamic_columns = "\n".join(age_columns)

    # 인구 지표 컬럼들
    indicator_columns = """
    -- 인구 지표
    elderly_ratio NUMERIC(10,2),
    aging_index NUMERIC(10,2),
    extinction_index NUMERIC(10,4),
    youth_dependency NUMERIC(10,2),
    elderly_dependency NUMERIC(10,2),
    total_dependency NUMERIC(10,2),
    sex_ratio NUMERIC(10,2),

    -- 세대 지표
    single_ratio NUMERIC(10,2),
    pop_per_house NUMERIC(10,2),

    PRIMARY KEY (base_ym, sigungu_code)"""

    ddl = f"""
DROP TABLE IF EXISTS cache_sigungu_indicators CASCADE;

CREATE TABLE cache_sigungu_indicators (
{base_columns},

    -- code_age_group 기반 동적 컬럼 (10세별, 정책연령 등)
{dynamic_columns}

{indicator_columns}
);

CREATE INDEX idx_cache_sigungu_indicators_sido ON cache_sigungu_indicators(sido_nm);
CREATE INDEX idx_cache_sigungu_indicators_ym ON cache_sigungu_indicators(base_ym);

COMMENT ON TABLE cache_sigungu_indicators IS '시군구별 인구지표 캐시 테이블 (code_age_group 기반 동적 생성)';
"""
    return ddl


def generate_insert_columns(age_groups_df: pd.DataFrame) -> str:
    """INSERT 문의 컬럼 목록을 생성합니다."""
    base_cols = [
        "base_ym", "sido_cd", "sido_nm", "sido_alias", "sigungu_code", "sigungu_nm",
        "total_pop", "male_pop", "female_pop", "household_cnt", "single_cnt",
        "male_single", "female_single", "elderly_single", "super_elderly_single",
        "young_adult_single", "youth_single",
        "pop_0_4", "pop_5_9", "pop_10_14", "pop_15_19", "pop_20_24",
        "pop_25_29", "pop_30_34", "pop_35_39", "pop_40_44", "pop_45_49",
        "pop_50_54", "pop_55_59", "pop_60_64", "pop_65_69", "pop_70_74",
        "pop_75_79", "pop_80_84", "pop_85_89", "pop_90_94", "pop_95_99", "pop_100_over"
    ]

    # code_age_group 기반 동적 컬럼 (5세별 제외)
    for _, row in age_groups_df.iterrows():
        if row['category'] != 1:  # 5세별이 아닌 경우만
            base_cols.append(row['column_name'])

    # 지표 컬럼들
    indicator_cols = [
        "elderly_ratio", "aging_index", "extinction_index",
        "youth_dependency", "elderly_dependency", "total_dependency", "sex_ratio",
        "single_ratio", "pop_per_house"
    ]

    all_cols = base_cols + indicator_cols
    return ", ".join(all_cols)


def generate_select_columns(age_groups_df: pd.DataFrame) -> str:
    """SELECT 문의 컬럼 목록을 생성합니다."""

    # 5세별 인구 SQL 생성
    age_5_sqls = []
    for start in range(0, 100, 5):
        end = start + 4
        sql = generate_age_sum_sql(start, end)
        age_5_sqls.append(f"{sql} as pop_{start}_{end}")

    # 100세 이상
    sql_100_over = generate_age_sum_sql(100, 999)
    age_5_sqls.append(f"{sql_100_over} as pop_100_over")

    age_5_sql = ",\n                ".join(age_5_sqls)

    # code_age_group 기반 동적 컬럼 SQL (5세별 제외)
    dynamic_sqls = []
    for _, row in age_groups_df.iterrows():
        if row['category'] != 1:  # 5세별이 아닌 경우만
            col_name = row['column_name']
            age_start = int(row['age_start'])
            age_end = int(row['age_end'])
            sql = generate_age_sum_sql(age_start, age_end)
            dynamic_sqls.append(f"{sql} as {col_name}")

    dynamic_sql = ",\n                ".join(dynamic_sqls)

    # 지표 계산용 서브쿼리 생성
    # 유소년 (0-14), 생산가능 (15-64), 고령 (65+), 20-39여성
    youth_sql = generate_age_sum_sql(0, 14)
    working_sql = generate_age_sum_sql(15, 64)
    elderly_sql = generate_age_sum_sql(65, 999)
    female_20_39_cols = [f"COALESCE(p.female_age_{i}, 0)" for i in range(20, 40)]
    female_20_39_sql = f"SUM({' + '.join(female_20_39_cols)})"

    # 1인가구 합계
    single_male_cols = [f"COALESCE(s.male_age_{i}, 0)" for i in range(0, 110)] + ["COALESCE(s.male_age_110_over, 0)"]
    single_female_cols = [f"COALESCE(s.female_age_{i}, 0)" for i in range(0, 110)] + ["COALESCE(s.female_age_110_over, 0)"]
    single_sql = f"SUM({' + '.join(single_male_cols)} + {' + '.join(single_female_cols)})"

    # 1인가구 세부 (남성/여성)
    male_single_sql = f"SUM({' + '.join(single_male_cols)})"
    female_single_sql = f"SUM({' + '.join(single_female_cols)})"

    # 1인가구 세부 (연령별)
    # 고령 1인가구 (65세 이상)
    elderly_single_male = [f"COALESCE(s.male_age_{i}, 0)" for i in range(65, 110)] + ["COALESCE(s.male_age_110_over, 0)"]
    elderly_single_female = [f"COALESCE(s.female_age_{i}, 0)" for i in range(65, 110)] + ["COALESCE(s.female_age_110_over, 0)"]
    elderly_single_sql = f"SUM({' + '.join(elderly_single_male)} + {' + '.join(elderly_single_female)})"

    # 초고령 1인가구 (85세 이상)
    super_elderly_single_male = [f"COALESCE(s.male_age_{i}, 0)" for i in range(85, 110)] + ["COALESCE(s.male_age_110_over, 0)"]
    super_elderly_single_female = [f"COALESCE(s.female_age_{i}, 0)" for i in range(85, 110)] + ["COALESCE(s.female_age_110_over, 0)"]
    super_elderly_single_sql = f"SUM({' + '.join(super_elderly_single_male)} + {' + '.join(super_elderly_single_female)})"

    # 청년 1인가구 - 청년기본법 (19-34세)
    young_adult_single_male = [f"COALESCE(s.male_age_{i}, 0)" for i in range(19, 35)]
    young_adult_single_female = [f"COALESCE(s.female_age_{i}, 0)" for i in range(19, 35)]
    young_adult_single_sql = f"SUM({' + '.join(young_adult_single_male)} + {' + '.join(young_adult_single_female)})"

    # 청년 1인가구 - 경북청년 (19-39세)
    youth_single_male = [f"COALESCE(s.male_age_{i}, 0)" for i in range(19, 40)]
    youth_single_female = [f"COALESCE(s.female_age_{i}, 0)" for i in range(19, 40)]
    youth_single_sql = f"SUM({' + '.join(youth_single_male)} + {' + '.join(youth_single_female)})"

    select_sql = f"""
            SELECT
                p.base_ym,
                {SIDO_CODE_NORMALIZE_SQL} as sido_cd,
                {SIDO_NAME_NORMALIZE_SQL} as sido_nm,
                {SIDO_ALIAS_SQL} as sido_alias,
                d.sigungu_code,
                d.sigungu_nm,

                -- 기본 인구
                SUM(p.total_pop) as total_pop,
                SUM(p.male_total) as male_pop,
                SUM(p.female_total) as female_pop,
                SUM(COALESCE(b.household_cnt, 0)) as household_cnt,
                {single_sql} as single_cnt,
                {male_single_sql} as male_single,
                {female_single_sql} as female_single,
                {elderly_single_sql} as elderly_single,
                {super_elderly_single_sql} as super_elderly_single,
                {young_adult_single_sql} as young_adult_single,
                {youth_single_sql} as youth_single,

                -- 5세별 인구
                {age_5_sql},

                -- code_age_group 기반 동적 컬럼
                {dynamic_sql},

                -- 인구 지표
                ROUND({elderly_sql}::numeric / NULLIF(SUM(p.total_pop), 0) * 100, 2) as elderly_ratio,
                ROUND({elderly_sql}::numeric / NULLIF({youth_sql}, 0) * 100, 2) as aging_index,
                ROUND({female_20_39_sql}::numeric / NULLIF({elderly_sql}, 0), 4) as extinction_index,
                ROUND({youth_sql}::numeric / NULLIF({working_sql}, 0) * 100, 2) as youth_dependency,
                ROUND({elderly_sql}::numeric / NULLIF({working_sql}, 0) * 100, 2) as elderly_dependency,
                ROUND(({youth_sql} + {elderly_sql})::numeric / NULLIF({working_sql}, 0) * 100, 2) as total_dependency,
                ROUND(SUM(p.male_total)::numeric / NULLIF(SUM(p.female_total), 0) * 100, 2) as sex_ratio,
                ROUND({single_sql}::numeric / NULLIF(SUM(COALESCE(b.household_cnt, 0)), 0) * 100, 2) as single_ratio,
                ROUND(SUM(p.total_pop)::numeric / NULLIF(SUM(COALESCE(b.household_cnt, 0)), 0), 2) as pop_per_house

            FROM fact_population_by_age p
            JOIN dim_admin_area d ON p.admin_code = d.admin_code
            LEFT JOIN fact_single_household s ON p.admin_code = s.admin_code AND p.base_ym = s.base_ym
            LEFT JOIN fact_population_basic b ON p.admin_code = b.admin_code AND p.base_ym = b.base_ym
            WHERE TO_CHAR(p.base_ym, 'YYYYMM') = '{{ym}}'
            GROUP BY p.base_ym, d.sigungu_code, d.sigungu_nm,
                {SIDO_CODE_NORMALIZE_SQL},
                {SIDO_NAME_NORMALIZE_SQL},
                {SIDO_ALIAS_SQL}
    """

    return select_sql


def init_cache_tables():
    """Cache 테이블을 초기화(재생성)합니다."""
    logger.info("code_age_group 테이블에서 연령 그룹 정의 로딩...")
    age_groups_df = get_age_group_definitions()
    logger.info(f"  총 {len(age_groups_df)}개 연령 그룹 정의 로딩 완료")

    # 동적 DDL 생성
    ddl = generate_ddl(age_groups_df)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            logger.info("cache_sigungu_indicators 테이블 재생성 중...")
            cur.execute(ddl)
            conn.commit()
            logger.info("cache_sigungu_indicators 테이블 재생성 완료")
    except Exception as e:
        conn.rollback()
        logger.error(f"테이블 초기화 실패: {e}")
        raise
    finally:
        conn.close()


def refresh_cache_sigungu_indicators(target_month: str = None):
    """
    cache_sigungu_indicators 테이블을 갱신합니다.

    Args:
        target_month: 특정 월만 갱신 (YYYYMM 형식). None이면 전체 갱신.
    """
    logger.info("code_age_group 테이블에서 연령 그룹 정의 로딩...")
    age_groups_df = get_age_group_definitions()
    logger.info(f"  총 {len(age_groups_df)}개 연령 그룹 정의 로딩 완료")

    engine = get_db_engine()
    conn = get_db_connection()

    try:
        # 대상 월 목록 조회
        if target_month:
            months_df = pd.DataFrame({'base_ym': [target_month]})
            logger.info(f"대상 월: {target_month}")
        else:
            months_df = pd.read_sql("""
                SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as base_ym
                FROM fact_population_by_age
                ORDER BY base_ym
            """, engine)
            logger.info(f"전체 갱신 대상: {len(months_df)}개월")

        # INSERT 컬럼 목록 생성
        insert_columns = generate_insert_columns(age_groups_df)

        # SELECT 쿼리 템플릿 생성
        select_template = generate_select_columns(age_groups_df)

        for idx, row in months_df.iterrows():
            ym = row['base_ym']
            logger.info(f"[{idx+1}/{len(months_df)}] {ym} 처리 중...")

            # 기존 데이터 삭제
            with conn.cursor() as cur:
                cur.execute(f"""
                    DELETE FROM cache_sigungu_indicators
                    WHERE TO_CHAR(base_ym, 'YYYYMM') = '{ym}'
                """)

            # SELECT 쿼리에서 {ym} 치환
            select_sql = select_template.replace('{ym}', ym)

            # INSERT 쿼리 실행
            insert_sql = f"""
            INSERT INTO cache_sigungu_indicators ({insert_columns})
            {select_sql}
            """

            with conn.cursor() as cur:
                cur.execute(insert_sql)

            conn.commit()
            logger.info(f"  {ym} 완료")

        logger.info("cache_sigungu_indicators 갱신 완료")

    except Exception as e:
        conn.rollback()
        logger.error(f"Cache 갱신 실패: {e}")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Cache 테이블 갱신 (code_age_group 기반 동적 생성)')
    parser.add_argument('--refresh', action='store_true', help='전체 갱신')
    parser.add_argument('--month', type=str, help='특정 월만 갱신 (YYYYMM)')
    parser.add_argument('--init', action='store_true', help='테이블 재생성')
    parser.add_argument('--show-ddl', action='store_true', help='생성될 DDL 확인')
    parser.add_argument('--show-select', action='store_true', help='생성될 SELECT 쿼리 확인')

    args = parser.parse_args()

    if args.show_ddl:
        age_groups_df = get_age_group_definitions()
        ddl = generate_ddl(age_groups_df)
        print(ddl)
    elif args.show_select:
        age_groups_df = get_age_group_definitions()
        select_sql = generate_select_columns(age_groups_df)
        print(select_sql)
    elif args.init:
        init_cache_tables()
        logger.info("테이블 초기화 후 전체 갱신을 시작합니다...")
        refresh_cache_sigungu_indicators()
    elif args.month:
        refresh_cache_sigungu_indicators(args.month)
    elif args.refresh:
        refresh_cache_sigungu_indicators()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
