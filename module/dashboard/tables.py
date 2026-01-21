"""
================================================================================
TableGenerator - HTML 테이블 생성 모듈
================================================================================
재사용 가능한 테이블 생성 클래스

주요 기능:
    - 2줄 헤더 테이블 (년월 + 지표)
    - 특정 행 강조 (경상북도 등)
    - 자동 정렬 (합계 → 강조지역 → 나머지)
    - 숫자 포맷팅 (천단위 콤마, 퍼센트 등)

사용 예시:
    from module.dashboard.tables import TableGenerator

    # 2줄 헤더 테이블 생성
    html = TableGenerator.multi_header_table(
        data=data_list,
        row_key='sido_nm',
        row_label='시도',
        ym_list=['202212', '202312', '202412'],
        metrics=[('pop', '인구'), ('rate', '증감률')],
        highlight='경상북도',
        summary_row='합계'
    )
================================================================================
"""
from typing import List, Dict, Optional, Tuple, Union, Any
import pandas as pd


class TableGenerator:
    """
    HTML 테이블 생성 클래스

    클래스(Class) 설명:
    ------------------
    이 클래스는 데이터를 HTML 테이블로 변환합니다.
    @classmethod 데코레이터를 사용하면 객체를 만들지 않고 바로 호출할 수 있습니다.

    예시:
        # 바로 호출 (권장)
        html = TableGenerator.multi_header_table(data, ...)

        # 또는 객체 생성 후 호출
        tg = TableGenerator()
        html = tg.multi_header_table(data, ...)
    """

    # CSS 스타일 정의
    STYLES = {
        'table': 'width:100%; border-collapse:collapse; font-size:0.875rem;',
        'th': 'background:#1243A6; color:white; padding:8px; text-align:center; border:1px solid #1a4fa3;',
        'th_year': 'background:#1D64F2; border-bottom:2px solid #1243A6;',
        'th_metric': 'background:#1243A6;',
        'th_divider': 'border-left:3px solid #0d3a8a;',
        'td': 'border:1px solid #e5e7eb; padding:8px; text-align:right;',
        'td_name': 'text-align:left; font-weight:500; background:#f9fafb;',
        'td_divider': 'border-left:3px solid #ccc;',
        'tr_even': 'background:#f9fafb;',
        'tr_hover': 'background:#e0f2fe;',
        'tr_summary': 'background:#fef3c7; font-weight:bold;',
        'tr_highlight': 'background:#fee2e2;',  # 강조 행 (연한 빨강)
        'positive': 'color:#2563eb;',
        'negative': 'color:#dc2626;',
    }

    # 기본 강조 대상
    DEFAULT_HIGHLIGHT = '경상북도'

    # 정렬 우선순위 (낮을수록 먼저)
    SORT_PRIORITY = {
        '합계': 0, '전국': 0, '계': 0, 'Total': 0,
        '경상북도': 1,
    }

    @classmethod
    def _format_value(cls, value: Any, key: str = '') -> Tuple[str, str]:
        """
        값을 포맷팅하고 CSS 클래스 반환

        Args:
            value: 원본 값
            key: 컬럼 키 (rate가 포함되면 퍼센트 처리)

        Returns:
            (포맷팅된 문자열, CSS 스타일)
        """
        if value is None:
            return '-', ''

        if isinstance(value, (int, float)):
            if 'rate' in key.lower():
                # 비율/증감률
                css = cls.STYLES['positive'] if value > 0 else (cls.STYLES['negative'] if value < 0 else '')
                return f'{value:.2f}%', css
            else:
                # 일반 숫자
                return f'{value:,.0f}', ''

        return str(value), ''

    @classmethod
    def _sort_data(
        cls,
        data: List[Dict],
        row_key: str,
        highlight: Optional[Union[str, List[str]]] = None,
        summary_row: Optional[str] = None
    ) -> List[Dict]:
        """
        데이터 정렬: 합계 → 강조지역 → 나머지 (코드순 또는 가나다순)

        Args:
            data: 데이터 리스트
            row_key: 행 이름 키
            highlight: 강조할 행 (예: '경상북도')
            summary_row: 합계 행 이름

        Returns:
            정렬된 데이터 리스트
        """
        if not data:
            return data

        # 강조 대상을 리스트로 변환
        highlight_list = []
        if highlight:
            highlight_list = [highlight] if isinstance(highlight, str) else highlight

        # 정렬 우선순위 계산
        def get_priority(row):
            name = row.get(row_key, '')

            # 합계/전국 행
            if summary_row and name == summary_row:
                return (0, '', name)

            # 강조 행 (경상북도 등)
            if name in highlight_list:
                return (1, '', name)

            # 시도코드가 있으면 코드순, 없으면 이름순
            code = row.get('sido_code', row.get('sigungu_code', ''))
            if code:
                return (2, code, name)

            return (2, name, name)

        return sorted(data, key=get_priority)

    @classmethod
    def multi_header_table(
        cls,
        data: List[Dict],
        row_key: str,
        row_label: str,
        ym_list: List[str],
        metrics: List[Tuple[str, str]],
        highlight: Optional[Union[str, List[str]]] = None,
        summary_row: Optional[str] = None,
        auto_sort: bool = True
    ) -> str:
        """
        2줄 헤더 테이블 생성

        Args:
            data: 데이터 리스트 [{'sido_nm': '서울', 'pop_202312': 1000, ...}, ...]
            row_key: 행 이름 키 (예: 'sido_nm', 'age_group')
            row_label: 첫 번째 컬럼 제목 (예: '시도', '연령대')
            ym_list: 기준년월 리스트 ['202212', '202312', '202412']
            metrics: 지표 리스트 [('pop', '인구'), ('rate', '증감률')]
            highlight: 강조할 행 (예: '경상북도')
            summary_row: 합계 행 이름 (예: '합계', '전국')
            auto_sort: 자동 정렬 여부 (합계→강조→나머지)

        Returns:
            HTML 테이블 문자열

        예시:
            # 시도별 인구 테이블
            html = TableGenerator.multi_header_table(
                data=sido_data,
                row_key='sido_nm',
                row_label='시도',
                ym_list=['202212', '202312'],
                metrics=[('pop', '인구'), ('aging_rate', '고령화율')],
                highlight='경상북도',
                summary_row='합계'
            )
        """
        if not data:
            return '<p style="color:#6b7280;">데이터가 없습니다.</p>'

        # 강조 대상을 리스트로 변환
        highlight_list = []
        if highlight:
            highlight_list = [highlight] if isinstance(highlight, str) else highlight

        # 데이터 정렬
        if auto_sort:
            data = cls._sort_data(data, row_key, highlight, summary_row)

        # HTML 생성 시작
        html = [f'<table style="{cls.STYLES["table"]}">']

        # ===== 헤더 1행: 년월 =====
        html.append('<thead>')
        html.append('<tr>')
        html.append(f'<th rowspan="2" style="{cls.STYLES["th"]}">{row_label}</th>')

        for i, ym in enumerate(ym_list):
            ym_display = f'{ym[:4]}년 {ym[4:]}월'
            divider = cls.STYLES['th_divider'] if i > 0 else ''
            # 해당 년월에 존재하는 지표 수 계산
            colspan = sum(1 for m_key, _ in metrics if any(f'{m_key}_{ym}' in row for row in data))
            if colspan == 0:
                colspan = len(metrics)
            html.append(f'<th colspan="{colspan}" style="{cls.STYLES["th"]} {cls.STYLES["th_year"]} {divider}">{ym_display}</th>')

        html.append('</tr>')

        # ===== 헤더 2행: 지표 =====
        html.append('<tr>')
        for i, ym in enumerate(ym_list):
            for j, (m_key, m_label) in enumerate(metrics):
                key = f'{m_key}_{ym}'
                # 데이터에 해당 키가 있는지 확인
                if any(key in row for row in data):
                    divider = cls.STYLES['th_divider'] if i > 0 and j == 0 else ''
                    html.append(f'<th style="{cls.STYLES["th"]} {cls.STYLES["th_metric"]} {divider}">{m_label}</th>')

        html.append('</tr>')
        html.append('</thead>')

        # ===== 데이터 행 =====
        html.append('<tbody>')
        for row_idx, row in enumerate(data):
            row_name = row.get(row_key, '')

            # 행 스타일 결정
            row_style = ''
            if summary_row and row_name == summary_row:
                row_style = cls.STYLES['tr_summary']
            elif row_name in highlight_list:
                row_style = cls.STYLES['tr_highlight']
            elif row_idx % 2 == 0:
                row_style = cls.STYLES['tr_even']

            html.append(f'<tr style="{row_style}">')

            # 첫 번째 컬럼 (행 이름)
            html.append(f'<td style="{cls.STYLES["td"]} {cls.STYLES["td_name"]}">{row_name}</td>')

            # 데이터 컬럼
            for i, ym in enumerate(ym_list):
                for j, (m_key, m_label) in enumerate(metrics):
                    key = f'{m_key}_{ym}'
                    if key in row:
                        val = row[key]
                        formatted_val, val_style = cls._format_value(val, key)
                        divider = cls.STYLES['td_divider'] if i > 0 and j == 0 else ''
                        html.append(f'<td style="{cls.STYLES["td"]} {divider} {val_style}">{formatted_val}</td>')

            html.append('</tr>')

        html.append('</tbody>')
        html.append('</table>')

        return '\n'.join(html)

    @classmethod
    def simple_table(
        cls,
        data: List[Dict],
        columns: List[Tuple[str, str]],
        highlight_key: Optional[str] = None,
        highlight_values: Optional[List[str]] = None
    ) -> str:
        """
        단순 테이블 생성 (1줄 헤더)

        Args:
            data: 데이터 리스트
            columns: 컬럼 정의 [(key, label), ...]
            highlight_key: 강조 기준 키
            highlight_values: 강조할 값 리스트

        Returns:
            HTML 테이블 문자열
        """
        if not data:
            return '<p style="color:#6b7280;">데이터가 없습니다.</p>'

        highlight_values = highlight_values or []

        html = [f'<table style="{cls.STYLES["table"]}">']

        # 헤더
        html.append('<thead><tr>')
        for key, label in columns:
            html.append(f'<th style="{cls.STYLES["th"]}">{label}</th>')
        html.append('</tr></thead>')

        # 데이터
        html.append('<tbody>')
        for row_idx, row in enumerate(data):
            # 강조 여부 확인
            is_highlight = (highlight_key and row.get(highlight_key) in highlight_values)
            row_style = cls.STYLES['tr_highlight'] if is_highlight else (
                cls.STYLES['tr_even'] if row_idx % 2 == 0 else ''
            )

            html.append(f'<tr style="{row_style}">')
            for col_idx, (key, label) in enumerate(columns):
                val = row.get(key, '')
                formatted_val, val_style = cls._format_value(val, key)
                td_style = cls.STYLES['td_name'] if col_idx == 0 else ''
                html.append(f'<td style="{cls.STYLES["td"]} {td_style} {val_style}">{formatted_val}</td>')
            html.append('</tr>')

        html.append('</tbody></table>')

        return '\n'.join(html)

    @classmethod
    def dataframe_to_html(
        cls,
        df: pd.DataFrame,
        highlight_col: Optional[str] = None,
        highlight_values: Optional[List[str]] = None
    ) -> str:
        """
        Pandas DataFrame을 HTML 테이블로 변환

        Args:
            df: DataFrame
            highlight_col: 강조 기준 컬럼
            highlight_values: 강조할 값 리스트

        Returns:
            HTML 테이블 문자열
        """
        if df is None or df.empty:
            return '<p style="color:#6b7280;">데이터가 없습니다.</p>'

        # DataFrame을 딕셔너리 리스트로 변환
        data = df.to_dict('records')
        columns = [(col, col) for col in df.columns]

        return cls.simple_table(data, columns, highlight_col, highlight_values)
