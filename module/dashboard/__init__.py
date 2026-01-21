"""
================================================================================
Dashboard Module - 재사용 가능한 대시보드 컴포넌트
================================================================================

이 모듈은 다양한 도메인(인구, 기업, 보건 등)에서 재사용 가능한
대시보드 컴포넌트를 제공합니다.

주요 클래스:
-----------
- DashboardBase: 대시보드 베이스 클래스 (상속해서 사용)
- SimpleDashboard: 간단한 대시보드 (함수만 전달해서 사용)
- ChartGenerator: Matplotlib 기반 차트 생성
- TableGenerator: HTML 테이블 생성 (2줄 헤더 지원)
- ExportManager: Excel/Markdown/HTML 내보내기

기본 사용법:
-----------
1. 상속 방식 (권장):

    from module.dashboard import DashboardBase, ChartGenerator

    class MyDashboard(DashboardBase):
        def __init__(self):
            super().__init__(
                title='내 대시보드',
                highlight_region='경상북도'  # 강조할 지역
            )

        def get_data(self, filters):
            # 데이터 조회 로직 구현
            return {'data': [...]}

        def get_filter_options(self):
            # 필터 옵션 반환
            return {'year_list': [...]}

    # 사용
    dashboard = MyDashboard()
    response = dashboard.render(request.args)

2. 간단한 방식:

    from module.dashboard import SimpleDashboard

    def get_data(filters):
        return {'data': [...]}

    def get_filters():
        return {'year_list': [...]}

    dashboard = SimpleDashboard(
        title='간단한 대시보드',
        data_func=get_data,
        filter_func=get_filters
    )

3. 개별 컴포넌트 사용:

    from module.dashboard import ChartGenerator, TableGenerator, ExportManager

    # 차트 생성
    chart_img = ChartGenerator.bar_chart(
        labels=['서울', '부산', '경상북도'],
        datasets=[{'label': '2024', 'data': [100, 80, 60]}],
        highlight='경상북도'  # 경상북도 빨간 테두리
    )

    # 테이블 생성 (합계 → 경상북도 → 나머지 순서)
    table_html = TableGenerator.multi_header_table(
        data=data_list,
        row_key='sido_nm',
        row_label='시도',
        ym_list=['202312', '202412'],
        metrics=[('pop', '인구'), ('rate', '증감률')],
        highlight='경상북도',
        summary_row='합계'
    )

    # 내보내기
    ExportManager.export_all(
        data={'시도별': df},
        output_dir='output',
        filename='report',
        highlight_regions=['경상북도']
    )

================================================================================
"""

# 베이스 클래스
from .base import DashboardBase, SimpleDashboard

# 차트 생성기
from .charts import ChartGenerator

# 테이블 생성기
from .tables import TableGenerator

# 내보내기 관리자
from .export import ExportManager

# 버전 정보
__version__ = '1.0.0'
__author__ = 'Claude AI Assistant'

# 외부에서 import 가능한 항목
__all__ = [
    'DashboardBase',
    'SimpleDashboard',
    'ChartGenerator',
    'TableGenerator',
    'ExportManager',
]
