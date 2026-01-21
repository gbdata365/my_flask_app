"""
================================================================================
DashboardBase - 대시보드 베이스 클래스
================================================================================
모든 대시보드의 기본이 되는 베이스 클래스

상속(Inheritance) 설명:
----------------------
상속은 기존 클래스(부모)의 기능을 물려받아 새 클래스(자식)를 만드는 것입니다.
마치 부모의 재산을 자식이 물려받는 것과 같습니다.

예시:
    class Animal:           # 부모 클래스
        def eat(self):
            print("먹는다")

    class Dog(Animal):      # 자식 클래스 (Animal 상속)
        def bark(self):
            print("멍멍!")

    dog = Dog()
    dog.eat()   # 부모에게 물려받은 기능
    dog.bark()  # 자식만의 기능

사용 예시:
    from module.dashboard.base import DashboardBase

    class PopulationDashboard(DashboardBase):
        '''인구 대시보드 (DashboardBase를 상속)'''

        def __init__(self):
            super().__init__(
                title='인구 현황 대시보드',
                highlight_region='경상북도'
            )

        def get_data(self, filters):
            # 오버라이드: 인구 데이터 조회 로직
            return query_population(filters)

        def get_filter_options(self):
            # 오버라이드: 인구 관련 필터 옵션
            return {'base_ym_list': [...], 'sido_list': [...]}
================================================================================
"""
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from abc import ABC, abstractmethod
from jinja2 import Environment, FileSystemLoader
from flask import Response
import json

from .charts import ChartGenerator
from .tables import TableGenerator
from .export import ExportManager


class DashboardBase(ABC):
    """
    대시보드 베이스 클래스 (추상 클래스)

    ABC (Abstract Base Class):
    -------------------------
    ABC를 상속받으면 '추상 클래스'가 됩니다.
    @abstractmethod로 표시된 메서드는 반드시 자식 클래스에서 구현해야 합니다.
    (구현하지 않으면 오류 발생)

    주요 개념:
    ---------
    - __init__: 생성자. 객체가 만들어질 때 자동 실행됩니다.
    - self: 자기 자신. 클래스 내부에서 자신의 변수/메서드에 접근할 때 사용.
    - super(): 부모 클래스. 부모의 메서드를 호출할 때 사용.
    - @abstractmethod: 자식이 반드시 구현해야 하는 메서드 표시.
    - @classmethod: 객체 없이 클래스명으로 바로 호출 가능한 메서드.

    속성:
    -----
    - title: 대시보드 제목
    - highlight_region: 강조할 지역 (예: '경상북도')
    - summary_row: 합계 행 이름 (예: '합계', '전국')
    - template_name: Jinja2 템플릿 파일명
    """

    def __init__(
        self,
        title: str = '대시보드',
        highlight_region: str = '경상북도',
        summary_row: str = '합계',
        template_dir: Optional[Path] = None,
        template_name: str = 'dashboard/base.html'
    ):
        """
        생성자 (Constructor)

        __init__은 객체가 생성될 때 자동으로 호출됩니다.
        여기서 객체의 초기 상태를 설정합니다.

        Args:
            title: 대시보드 제목
            highlight_region: 강조할 지역 (빨간 테두리)
            summary_row: 합계 행 이름
            template_dir: 템플릿 디렉토리 경로
            template_name: 템플릿 파일명
        """
        self.title = title
        self.highlight_region = highlight_region
        self.summary_row = summary_row
        self.template_name = template_name

        # Jinja2 환경 설정
        if template_dir is None:
            # 기본 템플릿 디렉토리 (module/dashboard/templates)
            template_dir = Path(__file__).parent / 'templates'

        if template_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
        else:
            self.jinja_env = None

        # 차트/테이블/내보내기 유틸리티
        self.chart = ChartGenerator
        self.table = TableGenerator
        self.export = ExportManager

    # =========================================================================
    # 추상 메서드 (자식 클래스에서 반드시 구현해야 함)
    # =========================================================================

    @abstractmethod
    def get_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        데이터 조회 (반드시 구현 필요)

        이 메서드는 @abstractmethod이므로 자식 클래스에서 반드시 구현해야 합니다.
        구현하지 않으면 TypeError가 발생합니다.

        Args:
            filters: 필터 조건 딕셔너리

        Returns:
            조회된 데이터 딕셔너리
        """
        pass

    @abstractmethod
    def get_filter_options(self) -> Dict[str, Any]:
        """
        필터 옵션 조회 (반드시 구현 필요)

        Returns:
            필터 옵션 딕셔너리
            예: {'base_ym_list': [...], 'sido_list': [...]}
        """
        pass

    # =========================================================================
    # 오버라이드 가능한 메서드 (필요시 자식에서 재정의)
    # =========================================================================

    def get_tabs(self) -> List[Dict[str, str]]:
        """
        탭 목록 반환 (필요시 오버라이드)

        Returns:
            탭 정보 리스트
            예: [{'id': 'age', 'label': '연령별'}, {'id': 'region', 'label': '지역별'}]
        """
        return [{'id': 'main', 'label': '메인'}]

    def get_metrics(self, tab_id: str = 'main') -> List[Tuple[str, str]]:
        """
        지표 목록 반환 (필요시 오버라이드)

        Args:
            tab_id: 탭 ID

        Returns:
            지표 리스트 [(키, 라벨), ...]
            예: [('pop', '인구'), ('rate', '증감률')]
        """
        return [('value', '값')]

    def process_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        데이터 후처리 (필요시 오버라이드)

        정렬, 계산 필드 추가 등

        Args:
            raw_data: 원본 데이터

        Returns:
            처리된 데이터
        """
        return raw_data

    # =========================================================================
    # 공통 유틸리티 메서드
    # =========================================================================

    def create_chart(
        self,
        chart_type: str,
        data: Dict[str, Any],
        **kwargs
    ) -> Optional[str]:
        """
        차트 생성 유틸리티

        Args:
            chart_type: 'bar', 'line', 'dual_axis', 'pie'
            data: 차트 데이터
            **kwargs: 추가 옵션

        Returns:
            Base64 인코딩된 이미지 문자열
        """
        # 기본값으로 강조 지역 설정
        if 'highlight' not in kwargs and self.highlight_region:
            kwargs['highlight'] = self.highlight_region

        if chart_type == 'bar':
            return self.chart.bar_chart(**data, **kwargs)
        elif chart_type == 'line':
            return self.chart.line_chart(**data, **kwargs)
        elif chart_type == 'dual_axis':
            return self.chart.dual_axis_chart(**data, **kwargs)
        elif chart_type == 'pie':
            return self.chart.pie_chart(**data, **kwargs)
        else:
            return None

    def create_table(
        self,
        data: List[Dict],
        row_key: str,
        row_label: str,
        ym_list: List[str],
        metrics: List[Tuple[str, str]],
        **kwargs
    ) -> str:
        """
        테이블 생성 유틸리티

        Args:
            data: 데이터 리스트
            row_key: 행 이름 키
            row_label: 행 제목
            ym_list: 년월 리스트
            metrics: 지표 리스트
            **kwargs: 추가 옵션

        Returns:
            HTML 테이블 문자열
        """
        # 기본값 설정
        if 'highlight' not in kwargs and self.highlight_region:
            kwargs['highlight'] = self.highlight_region
        if 'summary_row' not in kwargs and self.summary_row:
            kwargs['summary_row'] = self.summary_row

        return self.table.multi_header_table(
            data=data,
            row_key=row_key,
            row_label=row_label,
            ym_list=ym_list,
            metrics=metrics,
            **kwargs
        )

    def export_data(
        self,
        data: Dict[str, Any],
        output_dir: Path,
        filename: str,
        charts: Optional[Dict[str, str]] = None,
        formats: List[str] = None
    ) -> Dict[str, Any]:
        """
        데이터 내보내기 유틸리티

        Args:
            data: 내보낼 데이터
            output_dir: 출력 디렉토리
            filename: 파일명
            charts: 차트 이미지 딕셔너리
            formats: 내보낼 형식 리스트

        Returns:
            내보내기 결과
        """
        return self.export.export_all(
            data=data,
            output_dir=output_dir,
            filename=filename,
            title=self.title,
            highlight_regions=[self.highlight_region] if self.highlight_region else None,
            charts=charts,
            formats=formats
        )

    # =========================================================================
    # 메인 렌더 함수
    # =========================================================================

    def render(self, request_args: Dict[str, Any]) -> Response:
        """
        메인 렌더 함수

        이 메서드가 HTTP 요청을 처리하고 응답을 반환합니다.

        Args:
            request_args: Flask request.args

        Returns:
            Flask Response 객체
        """
        api_type = request_args.get('api_type')

        # API 요청 처리
        if api_type:
            result = self.handle_api(api_type, request_args)
            return Response(
                json.dumps(result, ensure_ascii=False, default=str),
                mimetype='application/json'
            )

        # HTML 페이지 렌더링
        return Response(
            self.render_html(request_args),
            mimetype='text/html'
        )

    def handle_api(self, api_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        API 요청 처리

        Args:
            api_type: API 유형
            params: 요청 파라미터

        Returns:
            API 응답 딕셔너리
        """
        if api_type == 'filter_options':
            return self.get_filter_options()

        elif api_type == 'data':
            return self.get_data(params)

        elif api_type == 'export':
            # 내보내기 처리
            data = self.get_data(params)
            output_dir = Path(params.get('output_dir', 'output'))
            filename = params.get('filename', 'export')
            return self.export_data(data, output_dir, filename)

        else:
            return {'error': f'Unknown api_type: {api_type}'}

    def render_html(self, request_args: Dict[str, Any]) -> str:
        """
        HTML 렌더링

        Jinja2 템플릿을 사용하여 HTML을 생성합니다.

        Args:
            request_args: 요청 파라미터

        Returns:
            HTML 문자열
        """
        if self.jinja_env is None:
            return self._render_default_html(request_args)

        try:
            template = self.jinja_env.get_template(self.template_name)

            # 데이터 준비
            filters = self.get_filter_options()
            data = self.get_data(request_args)
            data = self.process_data(data)

            # 템플릿 컨텍스트
            context = {
                'title': self.title,
                'filters': filters,
                'data': data,
                'tabs': self.get_tabs(),
                'highlight_region': self.highlight_region,
                'request_args': request_args
            }

            return template.render(**context)

        except Exception as e:
            print(f"템플릿 렌더링 오류: {e}")
            return self._render_default_html(request_args)

    def _render_default_html(self, request_args: Dict[str, Any]) -> str:
        """템플릿 없을 때 기본 HTML 생성"""
        return f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>{self.title}</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; }}
        h1 {{ color: #1243A6; }}
    </style>
</head>
<body>
    <h1>{self.title}</h1>
    <p>템플릿을 찾을 수 없습니다. 템플릿 파일을 생성해주세요.</p>
    <p>템플릿 경로: {self.template_name}</p>
</body>
</html>'''


# =============================================================================
# 간단한 대시보드를 위한 SimpleDashboard 클래스
# =============================================================================

class SimpleDashboard(DashboardBase):
    """
    간단한 대시보드 클래스

    상속 없이 바로 사용할 수 있는 간단한 대시보드입니다.
    데이터 조회 함수와 필터 옵션을 생성자에서 전달받습니다.

    예시:
        def get_my_data(filters):
            return {'data': [...]}

        def get_my_filters():
            return {'year_list': [...]}

        dashboard = SimpleDashboard(
            title='내 대시보드',
            data_func=get_my_data,
            filter_func=get_my_filters
        )
    """

    def __init__(
        self,
        title: str,
        data_func: callable,
        filter_func: callable,
        **kwargs
    ):
        """
        Args:
            title: 대시보드 제목
            data_func: 데이터 조회 함수 (filters -> data)
            filter_func: 필터 옵션 함수 (() -> options)
            **kwargs: DashboardBase 추가 옵션
        """
        super().__init__(title=title, **kwargs)
        self._data_func = data_func
        self._filter_func = filter_func

    def get_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        return self._data_func(filters)

    def get_filter_options(self) -> Dict[str, Any]:
        return self._filter_func()
