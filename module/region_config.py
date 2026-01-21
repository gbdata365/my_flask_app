# -*- coding: utf-8 -*-
"""
권역 설정 모듈
==========================================

권역별 시도 매핑 정보를 데이터베이스에서 동적으로 조회합니다.
하드코딩을 방지하고 유지보수성을 높이기 위한 공통 모듈입니다.
"""

from module.db import get_db_connection
import pandas as pd


def get_region_sido_mapping():
    """권역별 시도 매핑 조회 (DB에서 동적 조회)"""
    conn = get_db_connection()

    query = """
        SELECT DISTINCT region_nm, sido_nm
        FROM dim_admin_area
        WHERE region_nm IS NOT NULL AND sido_nm IS NOT NULL
        ORDER BY region_nm, sido_nm
    """

    df = pd.read_sql(query, conn)
    conn.close()

    # 권역별로 시도 리스트 생성
    region_mapping = {}
    for region in df['region_nm'].unique():
        sidos = df[df['region_nm'] == region]['sido_nm'].tolist()
        region_mapping[region] = sidos

    return region_mapping


def get_regions_list():
    """권역 목록 조회 (DB에서 동적 조회)"""
    conn = get_db_connection()

    query = """
        SELECT DISTINCT region_nm
        FROM dim_admin_area
        WHERE region_nm IS NOT NULL
        ORDER BY region_nm
    """

    df = pd.read_sql(query, conn)
    conn.close()

    # 전국 옵션 추가
    regions = [{'code': '전국', 'name': '전국'}]

    # DB에서 가져온 권역 추가
    for region in df['region_nm'].tolist():
        regions.append({'code': region, 'name': region})

    return regions


def get_sidos_by_region(region_code):
    """특정 권역의 시도 목록 조회"""
    if region_code == '전국':
        return []

    region_mapping = get_region_sido_mapping()
    return region_mapping.get(region_code, [])


def get_region_filter_sql(view_type, sido=None):
    """view_type에 따른 필터 SQL 생성"""
    if view_type == '전체':
        return ""
    elif view_type == '권역별':
        return ""
    elif view_type == '시도별' and sido:
        return f" AND \"CTPV_NM\" = '{sido}'"
    else:
        return ""
