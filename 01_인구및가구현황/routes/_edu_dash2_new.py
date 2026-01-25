"""
================================================================================
인구 집계표 대시보드 (새 모듈 사용 버전)
================================================================================
module.dashboard 모듈을 사용하여 리팩토링한 버전

기존 edu_dash2.py (1200줄) → edu_dash2_new.py (약 300줄)

클래스 상속 구조:
    DashboardBase (베이스 클래스)
         ↓ 상속
    PopulationDashboard (인구 대시보드)

주요 개념:
    - 상속(Inheritance): 부모 클래스의 기능을 물려받아 확장
    - 오버라이드(Override): 부모의 메서드를 자식이 재정의
    - super(): 부모 클래스의 메서드 호출
================================================================================
"""
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pandas as pd

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from module.dashboard import DashboardBase, ChartGenerator, TableGenerator, ExportManager
from module.db import get_db_engine
from module.menu_generator import MenuGenerator

POP_BASE = Path(__file__).parent.parent

# 동적 URL 생성 (하드코딩 제거)
CATEGORY_NAME = POP_BASE.name  # '01_인구및가구현황'
FILE_STEM = Path(__file__).stem  # '_edu_dash2_new'
CURRENT_URL = f'/{CATEGORY_NAME}/routes/{FILE_STEM}'


class PopulationDashboard(DashboardBase):
    """
    인구 집계표 대시보드

    DashboardBase를 상속받아 인구 관련 기능을 구현합니다.

    상속 예시:
        class 자식클래스(부모클래스):
            def __init__(self):
                super().__init__(...)  # 부모의 __init__ 호출

            def 부모메서드(self):
                # 오버라이드: 부모의 메서드를 재정의
                return 새로운_결과
    """

    def __init__(self):
        """
        생성자: 대시보드 초기 설정

        super().__init__()은 부모 클래스(DashboardBase)의 __init__을 호출합니다.
        부모에게 필요한 설정값들을 전달합니다.
        """
        super().__init__(
            title='인구 집계표 대시보드',
            highlight_region='경상북도',      # 차트/테이블에서 경상북도 강조
            summary_row='합계',               # 합계 행 이름
            template_dir=POP_BASE / 'templates',
            template_name='edu_dash2.html'
        )

        # 인구 대시보드 전용 설정
        self.db_engine = get_db_engine()
        self.pop_base = POP_BASE  # 메뉴 생성용

    # =========================================================================
    # 추상 메서드 구현 (반드시 구현해야 함)
    # =========================================================================

    def get_filter_options(self) -> Dict[str, Any]:
        """
        필터 옵션 조회

        @abstractmethod로 지정된 메서드는 반드시 구현해야 합니다.
        구현하지 않으면 오류가 발생합니다.
        """
        try:
            # 기준년월 목록
            base_ym_df = pd.read_sql("""
                SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as ym
                FROM cache_sigungu_indicators
                ORDER BY ym DESC
            """, self.db_engine)

            # 시도 목록 (캐시 테이블은 이미 정규화된 시도명 사용)
            sido_df = pd.read_sql("""
                SELECT DISTINCT sido_nm, MIN(LEFT(sigungu_code, 2)) as sido_code
                FROM cache_sigungu_indicators
                GROUP BY sido_nm
                ORDER BY sido_code
            """, self.db_engine)

            # 연령 카테고리
            age_cat_df = pd.read_sql("""
                SELECT DISTINCT category, category_name
                FROM code_age_groups
                ORDER BY category
            """, self.db_engine)

            return {
                'base_ym_list': base_ym_df['ym'].tolist(),
                'sido_list': sido_df['sido_nm'].tolist(),
                'age_categories': age_cat_df.to_dict('records'),
                'region_list': ['수도권', '충청권', '호남권', '영남권', '강원/제주']
            }
        except Exception as e:
            print(f"필터 옵션 조회 오류: {e}")
            return {'base_ym_list': [], 'sido_list': [], 'age_categories': [], 'region_list': []}

    def get_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        데이터 조회

        filters 딕셔너리에서 조건을 받아 데이터를 조회합니다.
        """
        base_ym_str = filters.get('base_ym_list', '')
        base_ym_list = [ym.strip() for ym in base_ym_str.split(',') if ym.strip()]

        if not base_ym_list:
            # 기본값: 최근 12월 데이터 4개
            opts = self.get_filter_options()
            dec_list = [ym for ym in opts['base_ym_list'] if ym.endswith('12')]
            base_ym_list = dec_list[:4][::-1]

        sido = filters.get('sido', '')
        age_category = int(filters.get('age_category', 1))

        return {
            'sido_data': self._get_sido_data(base_ym_list, sido),
            'elderly_data': self._get_elderly_data(base_ym_list, sido),
            'base_ym_list': base_ym_list,
            'sido': sido
        }

    # =========================================================================
    # 오버라이드 메서드
    # =========================================================================

    def get_tabs(self) -> List[Dict[str, str]]:
        """탭 목록 (부모 메서드 오버라이드)"""
        return [
            {'id': 'region', 'label': '지역별 인구'},
            {'id': 'elderly', 'label': '노령인구'},
        ]

    def get_metrics(self, tab_id: str = 'region') -> List[Tuple[str, str]]:
        """지표 목록 (부모 메서드 오버라이드)"""
        if tab_id == 'elderly':
            return [('pop', '인구'), ('aging_rate', '고령화율'), ('change_rate', '증감률')]
        return [('pop', '인구'), ('single', '1인가구'), ('pop_rate', '증감률')]

    # =========================================================================
    # 내부 헬퍼 메서드
    # =========================================================================

    def _get_sido_data(self, base_ym_list: List[str], sido: str = None) -> Dict[str, Any]:
        """시도별 인구 데이터 조회"""
        all_data = []
        summary_row = {}

        for ym in base_ym_list:
            where = f"AND sido_nm = '{sido}'" if sido else ""

            # 캐시 테이블은 이미 정규화된 시도명 사용
            df = pd.read_sql(f"""
                SELECT
                    sido_nm as name,
                    MIN(LEFT(sigungu_code, 2)) as sido_code,
                    SUM(total_pop) as pop,
                    SUM(COALESCE(single_cnt, 0)) as single_cnt
                FROM cache_sigungu_indicators
                WHERE TO_CHAR(base_ym, 'YYYYMM') = '{ym}'
                {where}
                GROUP BY sido_nm
                ORDER BY MIN(LEFT(sigungu_code, 2))
            """, self.db_engine)

            # 합계 계산
            total_pop = df['pop'].sum()
            total_single = df['single_cnt'].sum()
            summary_row[f'pop_{ym}'] = total_pop
            summary_row[f'single_{ym}'] = total_single

            for _, row in df.iterrows():
                name = row['name']
                existing = next((d for d in all_data if d['name'] == name), None)
                if not existing:
                    existing = {'name': name, 'sido_code': row['sido_code']}
                    all_data.append(existing)

                existing[f'pop_{ym}'] = int(row['pop'])
                existing[f'single_{ym}'] = int(row['single_cnt'])

        # 증감률 계산
        if len(base_ym_list) >= 2:
            prev_ym, curr_ym = base_ym_list[-2], base_ym_list[-1]
            for row in all_data:
                prev_pop = row.get(f'pop_{prev_ym}', 0)
                curr_pop = row.get(f'pop_{curr_ym}', 0)
                if prev_pop > 0:
                    row[f'pop_rate_{curr_ym}'] = round((curr_pop - prev_pop) / prev_pop * 100, 2)

        # 합계 행 추가
        summary_row['name'] = '합계'
        summary_row['sido_code'] = '00'

        return {'data': [summary_row] + all_data, 'ym_list': base_ym_list}

    def _get_elderly_data(self, base_ym_list: List[str], sido: str = None) -> Dict[str, Any]:
        """노령인구 데이터 조회"""
        all_data = []
        summary_row = {}

        for ym in base_ym_list:
            where = f"AND sido_nm = '{sido}'" if sido else ""

            # 캐시 테이블은 이미 정규화된 시도명 사용
            df = pd.read_sql(f"""
                SELECT
                    sido_nm as name,
                    MIN(LEFT(sigungu_code, 2)) as sido_code,
                    SUM(total_pop) as total_pop,
                    SUM(COALESCE(age_65_over, 0)) as elderly_pop
                FROM cache_sigungu_indicators
                WHERE TO_CHAR(base_ym, 'YYYYMM') = '{ym}'
                {where}
                GROUP BY sido_nm
                ORDER BY MIN(LEFT(sigungu_code, 2))
            """, self.db_engine)

            total_pop_sum = df['total_pop'].sum()
            elderly_sum = df['elderly_pop'].sum()
            summary_row[f'pop_{ym}'] = elderly_sum
            summary_row[f'aging_rate_{ym}'] = round(elderly_sum / total_pop_sum * 100, 2) if total_pop_sum > 0 else 0

            for _, row in df.iterrows():
                name = row['name']
                existing = next((d for d in all_data if d['name'] == name), None)
                if not existing:
                    existing = {'name': name, 'sido_code': row['sido_code']}
                    all_data.append(existing)

                elderly = int(row['elderly_pop'])
                total = int(row['total_pop'])
                existing[f'pop_{ym}'] = elderly
                existing[f'aging_rate_{ym}'] = round(elderly / total * 100, 2) if total > 0 else 0

        summary_row['name'] = '합계'
        summary_row['sido_code'] = '00'

        return {'data': [summary_row] + all_data, 'ym_list': base_ym_list}

    # =========================================================================
    # 렌더링 메서드 (커스터마이징)
    # =========================================================================

    def render_html(self, request_args: Dict[str, Any]) -> str:
        """HTML 렌더링 (커스터마이징)"""
        from jinja2 import Environment, FileSystemLoader

        # 데이터 준비
        filters = self.get_filter_options()
        data = self.get_data(request_args)

        base_ym_list = data['base_ym_list']

        # 차트 생성 (경상북도 강조)
        sido_data = data['sido_data']['data']
        elderly_data = data['elderly_data']['data']

        # 시도별 인구 차트
        region_chart = self.chart.bar_chart(
            labels=[d['name'] for d in sido_data[1:]],  # 합계 제외
            datasets=[{
                'label': f'{ym[:4]}.{ym[4:]}',
                'data': [d.get(f'pop_{ym}', 0) / 10000 for d in sido_data[1:]]
            } for ym in base_ym_list],
            ylabel='인구 (만 명)',
            highlight=self.highlight_region
        )

        # 노령인구 이중축 차트
        latest_ym = base_ym_list[-1] if base_ym_list else ''
        elderly_chart = self.chart.dual_axis_chart(
            labels=[d['name'] for d in elderly_data[1:]],
            bar_data=[d.get(f'pop_{latest_ym}', 0) / 10000 for d in elderly_data[1:]],
            line_data=[d.get(f'aging_rate_{latest_ym}', 0) for d in elderly_data[1:]],
            bar_label='노령인구 (만 명)',
            line_label='고령화율 (%)'
        ) if latest_ym else None

        # 테이블 생성
        region_table = self.table.multi_header_table(
            data=sido_data,
            row_key='name',
            row_label='시도',
            ym_list=base_ym_list,
            metrics=[('pop', '인구'), ('single', '1인가구')],
            highlight=self.highlight_region,
            summary_row=self.summary_row
        )

        elderly_table = self.table.multi_header_table(
            data=elderly_data,
            row_key='name',
            row_label='시도',
            ym_list=base_ym_list,
            metrics=[('pop', '노령인구'), ('aging_rate', '고령화율')],
            highlight=self.highlight_region,
            summary_row=self.summary_row
        )

        # 템플릿 렌더링
        jinja_env = Environment(loader=FileSystemLoader(str(POP_BASE / 'templates')))
        template = jinja_env.get_template('edu_dash2.html')

        return template.render(
            filters=filters,
            selected_ym_list=base_ym_list,
            aggregate_type='sido',
            selected_sido=data.get('sido', ''),
            active_tab='region',
            menu_items=MenuGenerator.get_category_menu_items(self.pop_base, '01_인구및가구현황'),
            current_url=CURRENT_URL,
            region_chart_img=region_chart,
            elderly_chart_img=elderly_chart,
            region_table_html=region_table,
            elderly_table_html=elderly_table
        )


# =============================================================================
# 메인 렌더 함수 (Flask 라우트에서 호출)
# =============================================================================

# 대시보드 인스턴스 (싱글톤)
_dashboard = None

def get_dashboard():
    """대시보드 인스턴스 반환 (싱글톤 패턴)"""
    global _dashboard
    if _dashboard is None:
        _dashboard = PopulationDashboard()
    return _dashboard


def render(request_args):
    """
    메인 렌더 함수

    Flask 라우트에서 이 함수를 호출합니다:
        @app.route('/edu_dash2')
        def edu_dash2():
            return edu_dash2_new.render(request.args)
    """
    dashboard = get_dashboard()
    return dashboard.render(request_args)
