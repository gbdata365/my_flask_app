# -*- coding: utf-8 -*-
"""
기업체현황 분석 스크립트
- 권역별, 시도별, 시군구별 기업체 현황 분석
- 한글 별칭 사용
"""

import sys
from pathlib import Path
import pandas as pd
from tabulate import tabulate

# 상위 디렉토리의 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent))
from module.db import get_db_connection


def get_dataframe(query: str) -> pd.DataFrame:
    """쿼리 실행 후 DataFrame 반환"""
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def print_df(df: pd.DataFrame, title: str = None):
    """DataFrame을 보기 좋게 출력"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    print(tabulate(df, headers='keys', tablefmt='pretty', showindex=False,
                   numalign='right', stralign='left'))
    print(f"(총 {len(df)}건)")


# ============================================================
# 1. 권역별 기업체 현황
# ============================================================
def analysis_by_region(base_ym: str = None, data_type: str = None):
    """권역별 기업체 현황 분석"""

    where_clause = "WHERE 1=1"
    if base_ym:
        where_clause += f" AND g.base_ym = '{base_ym}'"
    if data_type:
        where_clause += f" AND g.data_type = '{data_type}'"

    query = f"""
    SELECT
        COALESCE(a.권역, '미분류') AS 권역,
        g.base_ym AS 기준년월,
        g.data_type AS 자료유형,
        COUNT(DISTINCT g.sigun_cd) AS 시군구수,
        SUM(o.indiv_biz) AS 개인사업체,
        SUM(o.corp) AS 회사법인,
        SUM(o.corp_other) AS 회사이외법인,
        SUM(o.non_corp) AS 비법인단체,
        SUM(o.gov_local) AS 국가지방자치단체,
        SUM(o.total) AS 총기업체수,
        ROUND(SUM(o.total)::numeric / COUNT(DISTINCT g.sigun_cd), 0) AS 시군구당평균
    FROM giup_summary g
    JOIN giup_detail_org_type o ON g.id = o.summary_id
    LEFT JOIN (
        SELECT DISTINCT sigun_cd, 권역
        FROM gb_address
        WHERE sigun_cd IS NOT NULL
    ) a ON g.sigun_cd = a.sigun_cd
    {where_clause}
    GROUP BY COALESCE(a.권역, '미분류'), g.base_ym, g.data_type
    ORDER BY g.base_ym, SUM(o.total) DESC
    """

    df = get_dataframe(query)
    print_df(df, "권역별 기업체 현황")
    return df


# ============================================================
# 2. 시도별 기업체 현황
# ============================================================
def analysis_by_sido(base_ym: str = None, data_type: str = None):
    """시도별 기업체 현황 분석"""

    where_clause = "WHERE 1=1"
    if base_ym:
        where_clause += f" AND g.base_ym = '{base_ym}'"
    if data_type:
        where_clause += f" AND g.data_type = '{data_type}'"

    query = f"""
    SELECT
        g.sido_nm AS 시도명,
        g.base_ym AS 기준년월,
        g.data_type AS 자료유형,
        COUNT(DISTINCT g.sigun_nm) AS 시군구수,
        SUM(o.indiv_biz) AS 개인사업체,
        SUM(o.corp) AS 회사법인,
        SUM(o.corp_other) AS 회사이외법인,
        SUM(o.non_corp) AS 비법인단체,
        SUM(o.gov_local) AS 국가지방자치단체,
        SUM(o.total) AS 총기업체수,
        ROUND(SUM(o.indiv_biz)::numeric / NULLIF(SUM(o.total), 0) * 100, 1) AS 개인사업체비율
    FROM giup_summary g
    JOIN giup_detail_org_type o ON g.id = o.summary_id
    {where_clause}
    GROUP BY g.sido_nm, g.base_ym, g.data_type
    ORDER BY g.base_ym, SUM(o.total) DESC
    """

    df = get_dataframe(query)
    print_df(df, "시도별 기업체 현황")
    return df


# ============================================================
# 3. 시군구별 기업체 현황 (TOP N)
# ============================================================
def analysis_by_sigungu(base_ym: str = None, data_type: str = None,
                        sido_nm: str = None, top_n: int = 20):
    """시군구별 기업체 현황 분석"""

    where_clause = "WHERE 1=1"
    if base_ym:
        where_clause += f" AND g.base_ym = '{base_ym}'"
    if data_type:
        where_clause += f" AND g.data_type = '{data_type}'"
    if sido_nm:
        where_clause += f" AND g.sido_nm = '{sido_nm}'"

    query = f"""
    SELECT
        g.sido_nm AS 시도명,
        g.sigun_nm AS 시군구명,
        g.sigun_cd AS 시군구코드,
        g.base_ym AS 기준년월,
        o.indiv_biz AS 개인사업체,
        o.corp AS 회사법인,
        o.corp_other AS 회사이외법인,
        o.non_corp AS 비법인단체,
        o.gov_local AS 국가지방자치단체,
        o.total AS 총기업체수,
        ROUND(o.indiv_biz::numeric / NULLIF(o.total, 0) * 100, 1) AS 개인사업체비율
    FROM giup_summary g
    JOIN giup_detail_org_type o ON g.id = o.summary_id
    {where_clause}
    ORDER BY o.total DESC
    LIMIT {top_n}
    """

    df = get_dataframe(query)
    title = f"시군구별 기업체 현황 (TOP {top_n})"
    if sido_nm:
        title += f" - {sido_nm}"
    print_df(df, title)
    return df


# ============================================================
# 4. 산업분류별 기업체 현황
# ============================================================
def analysis_by_industry(base_ym: str = None, data_type: str = None):
    """산업분류별 기업체 현황 분석"""

    where_clause = "WHERE 1=1"
    if base_ym:
        where_clause += f" AND g.base_ym = '{base_ym}'"
    if data_type:
        where_clause += f" AND g.data_type = '{data_type}'"

    query = f"""
    SELECT
        g.base_ym AS 기준년월,
        g.data_type AS 자료유형,
        SUM(i.ind_a) AS "A.농림어업",
        SUM(i.ind_b) AS "B.광업",
        SUM(i.ind_c) AS "C.제조업",
        SUM(i.ind_d) AS "D.전기가스",
        SUM(i.ind_e) AS "E.수도하수",
        SUM(i.ind_f) AS "F.건설업",
        SUM(i.ind_g) AS "G.도소매업",
        SUM(i.ind_h) AS "H.운수창고",
        SUM(i.ind_i) AS "I.숙박음식",
        SUM(i.ind_j) AS "J.정보통신",
        SUM(i.ind_k) AS "K.금융보험",
        SUM(i.ind_l) AS "L.부동산",
        SUM(i.ind_m) AS "M.전문과학",
        SUM(i.ind_n) AS "N.사업시설",
        SUM(i.ind_o) AS "O.공공행정",
        SUM(i.ind_p) AS "P.교육서비스",
        SUM(i.ind_q) AS "Q.보건복지",
        SUM(i.ind_r) AS "R.예술스포츠",
        SUM(i.ind_s) AS "S.협회개인",
        SUM(i.total) AS 총합계
    FROM giup_summary g
    JOIN giup_detail_industry i ON g.id = i.summary_id
    {where_clause}
    GROUP BY g.base_ym, g.data_type
    ORDER BY g.base_ym
    """

    df = get_dataframe(query)
    print_df(df, "산업분류별 기업체 현황 (전국 합계)")
    return df


# ============================================================
# 5. 대표자 성별 현황
# ============================================================
def analysis_by_gender(base_ym: str = None, data_type: str = None):
    """대표자 성별 현황 분석"""

    where_clause = "WHERE 1=1"
    if base_ym:
        where_clause += f" AND g.base_ym = '{base_ym}'"
    if data_type:
        where_clause += f" AND g.data_type = '{data_type}'"

    query = f"""
    SELECT
        g.sido_nm AS 시도명,
        g.base_ym AS 기준년월,
        SUM(gd.male) AS 남자,
        SUM(gd.female) AS 여자,
        SUM(gd.blank) AS 미상,
        SUM(gd.total) AS 합계,
        ROUND(SUM(gd.male)::numeric / NULLIF(SUM(gd.total), 0) * 100, 1) AS 남자비율,
        ROUND(SUM(gd.female)::numeric / NULLIF(SUM(gd.total), 0) * 100, 1) AS 여자비율
    FROM giup_summary g
    JOIN giup_detail_gender gd ON g.id = gd.summary_id
    {where_clause}
    GROUP BY g.sido_nm, g.base_ym
    ORDER BY g.base_ym, SUM(gd.total) DESC
    """

    df = get_dataframe(query)
    print_df(df, "시도별 대표자 성별 현황")
    return df


# ============================================================
# 6. 폐업 현황
# ============================================================
def analysis_by_status(base_ym: str = None, data_type: str = None):
    """폐업 현황 분석"""

    where_clause = "WHERE 1=1"
    if base_ym:
        where_clause += f" AND g.base_ym = '{base_ym}'"
    if data_type:
        where_clause += f" AND g.data_type = '{data_type}'"

    query = f"""
    SELECT
        g.sido_nm AS 시도명,
        g.base_ym AS 기준년월,
        SUM(s.active) AS 영업중,
        SUM(s.closed) AS 폐업,
        SUM(s.total) AS 합계,
        ROUND(SUM(s.closed)::numeric / NULLIF(SUM(s.total), 0) * 100, 1) AS 폐업률
    FROM giup_summary g
    JOIN giup_detail_status s ON g.id = s.summary_id
    {where_clause}
    GROUP BY g.sido_nm, g.base_ym
    ORDER BY g.base_ym, ROUND(SUM(s.closed)::numeric / NULLIF(SUM(s.total), 0) * 100, 1) DESC
    """

    df = get_dataframe(query)
    print_df(df, "시도별 폐업 현황")
    return df


# ============================================================
# 7. 기간별 추이 분석
# ============================================================
def analysis_trend(sido_nm: str = None):
    """기간별 기업체 추이 분석"""

    where_clause = ""
    if sido_nm:
        where_clause = f"WHERE g.sido_nm = '{sido_nm}'"

    query = f"""
    SELECT
        g.base_ym AS 기준년월,
        g.data_type AS 자료유형,
        SUM(o.total) AS 총기업체수,
        SUM(o.indiv_biz) AS 개인사업체,
        SUM(o.corp) AS 회사법인,
        SUM(s.active) AS 영업중,
        SUM(s.closed) AS 폐업,
        ROUND(SUM(s.closed)::numeric / NULLIF(SUM(s.total), 0) * 100, 1) AS 폐업률
    FROM giup_summary g
    JOIN giup_detail_org_type o ON g.id = o.summary_id
    JOIN giup_detail_status s ON g.id = s.summary_id
    {where_clause}
    GROUP BY g.base_ym, g.data_type
    ORDER BY g.base_ym
    """

    df = get_dataframe(query)
    title = "기간별 기업체 추이"
    if sido_nm:
        title += f" - {sido_nm}"
    print_df(df, title)
    return df


# ============================================================
# 8. 기준년월 목록 조회
# ============================================================
def get_base_ym_list():
    """사용 가능한 기준년월 목록 조회"""
    query = """
    SELECT DISTINCT
        base_ym AS 기준년월,
        base_ym1 AS 원본기준시기,
        data_type AS 자료유형,
        COUNT(*) AS 시군구수
    FROM giup_summary
    GROUP BY base_ym, base_ym1, data_type
    ORDER BY base_ym, data_type
    """
    df = get_dataframe(query)
    print_df(df, "사용 가능한 기준년월 목록")
    return df


# ============================================================
# 메인 메뉴
# ============================================================
def show_menu():
    """메뉴 출력"""
    print("\n" + "="*60)
    print("  기업체현황 분석 메뉴")
    print("="*60)
    print("  0. 기준년월 목록 조회")
    print("  1. 권역별 기업체 현황")
    print("  2. 시도별 기업체 현황")
    print("  3. 시군구별 기업체 현황 (TOP N)")
    print("  4. 산업분류별 기업체 현황")
    print("  5. 대표자 성별 현황")
    print("  6. 폐업 현황")
    print("  7. 기간별 추이 분석")
    print("  q. 종료")
    print("="*60)


def main():
    """메인 실행"""
    print("\n기업체현황 분석 프로그램")
    print("(한글 별칭 사용)")

    # 기본값 설정
    default_base_ym = '202312'  # 2023년 연간
    default_data_type = 'annual'

    while True:
        show_menu()
        choice = input("\n선택 (0-7, q): ").strip()

        if choice == 'q':
            print("종료합니다.")
            break
        elif choice == '0':
            get_base_ym_list()
        elif choice == '1':
            base_ym = input(f"기준년월 (기본값: {default_base_ym}, Enter=전체): ").strip() or None
            data_type = input(f"자료유형 (annual/quarterly/monthly, Enter=전체): ").strip() or None
            analysis_by_region(base_ym, data_type)
        elif choice == '2':
            base_ym = input(f"기준년월 (기본값: {default_base_ym}, Enter=전체): ").strip() or None
            data_type = input(f"자료유형 (annual/quarterly/monthly, Enter=전체): ").strip() or None
            analysis_by_sido(base_ym, data_type)
        elif choice == '3':
            base_ym = input(f"기준년월 (Enter=전체): ").strip() or None
            data_type = input(f"자료유형 (Enter=전체): ").strip() or None
            sido_nm = input(f"시도명 (Enter=전체): ").strip() or None
            top_n = input(f"상위 몇 개? (기본값: 20): ").strip()
            top_n = int(top_n) if top_n else 20
            analysis_by_sigungu(base_ym, data_type, sido_nm, top_n)
        elif choice == '4':
            base_ym = input(f"기준년월 (Enter=전체): ").strip() or None
            data_type = input(f"자료유형 (Enter=전체): ").strip() or None
            analysis_by_industry(base_ym, data_type)
        elif choice == '5':
            base_ym = input(f"기준년월 (Enter=전체): ").strip() or None
            data_type = input(f"자료유형 (Enter=전체): ").strip() or None
            analysis_by_gender(base_ym, data_type)
        elif choice == '6':
            base_ym = input(f"기준년월 (Enter=전체): ").strip() or None
            data_type = input(f"자료유형 (Enter=전체): ").strip() or None
            analysis_by_status(base_ym, data_type)
        elif choice == '7':
            sido_nm = input(f"시도명 (Enter=전국): ").strip() or None
            analysis_trend(sido_nm)
        else:
            print("잘못된 선택입니다.")


# ============================================================
# 빠른 실행 함수들 (스크립트에서 직접 호출용)
# ============================================================
def quick_analysis():
    """빠른 분석 - 2023년 연간 데이터 기준"""
    print("\n" + "="*70)
    print("  2023년 연간 기업체 현황 분석 (base_ym='202312', data_type='annual')")
    print("="*70)

    analysis_by_region('202312', 'annual')
    analysis_by_sido('202312', 'annual')
    analysis_by_sigungu('202312', 'annual', top_n=15)
    analysis_trend()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        # 빠른 분석 실행
        quick_analysis()
    else:
        # 대화형 메뉴 실행
        main()
