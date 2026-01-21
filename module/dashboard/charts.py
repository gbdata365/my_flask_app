"""
================================================================================
ChartGenerator - Matplotlib 기반 차트 생성 모듈
================================================================================
재사용 가능한 차트 생성 클래스

사용 예시:
    from module.dashboard.charts import ChartGenerator

    # 막대 차트
    chart_img = ChartGenerator.bar_chart(
        labels=['서울', '부산', '대구'],
        datasets=[
            {'label': '2023년', 'data': [100, 80, 60]},
            {'label': '2024년', 'data': [110, 85, 65]}
        ],
        title='시도별 인구'
    )

    # 이중축 차트
    chart_img = ChartGenerator.dual_axis_chart(
        labels=['서울', '부산'],
        bar_data=[100, 80],
        line_data=[15.2, 18.5],
        bar_label='인구(만)',
        line_label='고령화율(%)'
    )
================================================================================
"""
import io
import base64
import numpy as np
import koreanize_matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from typing import List, Dict, Optional, Tuple, Union


class ChartGenerator:
    """
    Matplotlib 기반 차트 생성 클래스

    클래스(Class)란?
    ----------------
    - 클래스는 '설계도'입니다. 붕어빵 틀처럼 같은 형태의 것을 여러 개 만들 수 있습니다.
    - self는 '나 자신'을 의미합니다. 클래스 안에서 자기 자신의 변수/메서드에 접근할 때 사용합니다.
    - @classmethod는 객체를 만들지 않고도 호출할 수 있는 메서드입니다.
      예: ChartGenerator.bar_chart(...) - 객체 생성 없이 바로 호출

    사용 예시:
        # 객체 생성 없이 바로 사용 (@classmethod)
        img = ChartGenerator.bar_chart(labels=['서울', '부산'], ...)

        # 또는 객체를 만들어서 사용
        chart_gen = ChartGenerator()
        chart_gen.highlight_region = '경상북도'  # 강조할 지역 설정
    """

    # 기본 색상 팔레트
    COLORS = [
        '#1D64F2',  # primary blue
        '#10b981',  # green
        '#f59e0b',  # amber
        '#8b5cf6',  # purple
        '#ec4899',  # pink
        '#06b6d4',  # cyan
        '#84cc16',  # lime
        '#64748b',  # slate
    ]

    # 강조 색상 (경상북도 등 특정 지역 강조용)
    HIGHLIGHT_COLOR = '#F24822'  # 빨간색
    HIGHLIGHT_EDGE_COLOR = '#dc2626'  # 진한 빨간 테두리
    HIGHLIGHT_EDGE_WIDTH = 3

    # 기본 강조 대상 (경상북도)
    DEFAULT_HIGHLIGHT = '경상북도'

    @classmethod
    def _fig_to_base64(cls, fig: plt.Figure, dpi: int = 100) -> str:
        """Figure를 Base64 문자열로 변환"""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_base64

    @classmethod
    def bar_chart(
        cls,
        labels: List[str],
        datasets: List[Dict],
        title: str = '',
        xlabel: str = '',
        ylabel: str = '',
        figsize: Tuple[int, int] = (12, 5),
        horizontal: bool = False,
        stacked: bool = False,
        show_values: bool = False,
        value_format: str = '{:.0f}',
        y_formatter: Optional[callable] = None,
        highlight: Optional[Union[str, List[str]]] = None  # 강조할 레이블 (예: '경상북도')
    ) -> str:
        """
        막대 차트 생성

        Args:
            labels: X축 레이블 리스트
            datasets: [{'label': '범례명', 'data': [값들], 'color': '#색상(선택)'}]
            title: 차트 제목
            xlabel: X축 레이블
            ylabel: Y축 레이블
            figsize: 그림 크기
            horizontal: 가로 막대 여부
            stacked: 누적 여부
            show_values: 값 표시 여부
            value_format: 값 포맷 문자열
            y_formatter: Y축 포맷터 함수
            highlight: 강조할 레이블 (예: '경상북도' 또는 ['경상북도', '서울특별시'])

        Returns:
            Base64 인코딩된 PNG 이미지 문자열
        """
        fig, ax = plt.subplots(figsize=figsize)

        x = np.arange(len(labels))
        n_datasets = len(datasets)
        width = 0.8 / n_datasets if not stacked else 0.8

        # 강조 대상을 리스트로 변환
        highlight_list = []
        if highlight:
            highlight_list = [highlight] if isinstance(highlight, str) else highlight

        for i, ds in enumerate(datasets):
            data = ds.get('data', [])
            label = ds.get('label', f'Dataset {i+1}')
            base_color = ds.get('color', cls.COLORS[i % len(cls.COLORS)])

            if stacked:
                offset = x
            else:
                offset = x + (i - (n_datasets - 1) / 2) * width

            # 각 막대별 색상 및 테두리 설정 (강조 대상 처리)
            colors = []
            edge_colors = []
            edge_widths = []

            for lbl in labels:
                if lbl in highlight_list:
                    colors.append(cls.HIGHLIGHT_COLOR)
                    edge_colors.append(cls.HIGHLIGHT_EDGE_COLOR)
                    edge_widths.append(cls.HIGHLIGHT_EDGE_WIDTH)
                else:
                    colors.append(base_color)
                    edge_colors.append('none')
                    edge_widths.append(0)

            if horizontal:
                bars = ax.barh(offset, data, width, label=label, color=colors,
                              edgecolor=edge_colors, linewidth=edge_widths, alpha=0.85)
            else:
                bars = ax.bar(offset, data, width, label=label, color=colors,
                             edgecolor=edge_colors, linewidth=edge_widths, alpha=0.85)

            if show_values:
                for bar, val in zip(bars, data):
                    if horizontal:
                        ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2,
                               value_format.format(val), ha='left', va='center', fontsize=8)
                    else:
                        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                               value_format.format(val), ha='center', va='bottom', fontsize=8)

        if horizontal:
            ax.set_yticks(x)
            ax.set_yticklabels(labels)
            if xlabel: ax.set_xlabel(xlabel)
            if ylabel: ax.set_ylabel(ylabel)
        else:
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            if xlabel: ax.set_xlabel(xlabel)
            if ylabel: ax.set_ylabel(ylabel)

        if title:
            ax.set_title(title, fontweight='bold', pad=10)

        if y_formatter:
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, p: y_formatter(v)))

        if n_datasets > 1:
            ax.legend(loc='upper right')

        ax.grid(axis='y' if not horizontal else 'x', alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()
        return cls._fig_to_base64(fig)

    @classmethod
    def line_chart(
        cls,
        labels: List[str],
        datasets: List[Dict],
        title: str = '',
        xlabel: str = '',
        ylabel: str = '',
        figsize: Tuple[int, int] = (12, 5),
        show_markers: bool = True,
        fill: bool = False,
        y_formatter: Optional[callable] = None
    ) -> str:
        """
        선 차트 생성

        Args:
            labels: X축 레이블 리스트
            datasets: [{'label': '범례명', 'data': [값들], 'color': '#색상(선택)'}]
            title: 차트 제목
            fill: 영역 채우기 여부

        Returns:
            Base64 인코딩된 PNG 이미지 문자열
        """
        fig, ax = plt.subplots(figsize=figsize)

        x = np.arange(len(labels))

        for i, ds in enumerate(datasets):
            data = ds.get('data', [])
            label = ds.get('label', f'Dataset {i+1}')
            color = ds.get('color', cls.COLORS[i % len(cls.COLORS)])

            line, = ax.plot(x, data, label=label, color=color, linewidth=2,
                           marker='o' if show_markers else None, markersize=6)

            if fill:
                ax.fill_between(x, data, alpha=0.2, color=color)

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')

        if title:
            ax.set_title(title, fontweight='bold', pad=10)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)

        if y_formatter:
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, p: y_formatter(v)))

        if len(datasets) > 1:
            ax.legend(loc='upper right')

        ax.grid(alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()
        return cls._fig_to_base64(fig)

    @classmethod
    def dual_axis_chart(
        cls,
        labels: List[str],
        bar_data: List[float],
        line_data: List[float],
        bar_label: str = '막대',
        line_label: str = '선',
        title: str = '',
        bar_color: str = '#1D64F2',
        line_color: str = '#F24822',
        figsize: Tuple[int, int] = (12, 5),
        bar_formatter: Optional[callable] = None,
        line_formatter: Optional[callable] = None
    ) -> str:
        """
        이중축 차트 (막대 + 선)

        Args:
            labels: X축 레이블
            bar_data: 막대 데이터 (왼쪽 Y축)
            line_data: 선 데이터 (오른쪽 Y축)
            bar_label: 막대 범례
            line_label: 선 범례

        Returns:
            Base64 인코딩된 PNG 이미지 문자열
        """
        fig, ax1 = plt.subplots(figsize=figsize)

        x = np.arange(len(labels))

        # 막대 그래프 (왼쪽 Y축)
        bars = ax1.bar(x, bar_data, color=bar_color, alpha=0.7, label=bar_label)
        ax1.set_ylabel(bar_label, color=bar_color, fontweight='bold')
        ax1.tick_params(axis='y', labelcolor=bar_color)
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45, ha='right')

        if bar_formatter:
            ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, p: bar_formatter(v)))

        # 선 그래프 (오른쪽 Y축)
        ax2 = ax1.twinx()
        line, = ax2.plot(x, line_data, color=line_color, marker='o',
                        linewidth=2, markersize=6, label=line_label)
        ax2.set_ylabel(line_label, color=line_color, fontweight='bold')
        ax2.tick_params(axis='y', labelcolor=line_color)

        if line_formatter:
            ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, p: line_formatter(v)))

        # Y축 범위 조정 (0부터 시작)
        ax1.set_ylim(bottom=0)
        if line_data:
            max_line = max(line_data)
            ax2.set_ylim(0, max_line * 1.2 if max_line > 0 else 10)

        if title:
            ax1.set_title(title, fontweight='bold', pad=10)

        # 범례 통합
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.spines['top'].set_visible(False)

        plt.tight_layout()
        return cls._fig_to_base64(fig)

    @classmethod
    def pie_chart(
        cls,
        labels: List[str],
        data: List[float],
        title: str = '',
        figsize: Tuple[int, int] = (8, 8),
        colors: Optional[List[str]] = None,
        show_percent: bool = True,
        donut: bool = False
    ) -> str:
        """
        파이/도넛 차트

        Args:
            labels: 항목 레이블
            data: 값 리스트
            donut: 도넛 차트 여부

        Returns:
            Base64 인코딩된 PNG 이미지 문자열
        """
        fig, ax = plt.subplots(figsize=figsize)

        colors = colors or cls.COLORS[:len(data)]

        wedges, texts, autotexts = ax.pie(
            data, labels=labels, colors=colors,
            autopct='%1.1f%%' if show_percent else None,
            startangle=90,
            wedgeprops={'linewidth': 2, 'edgecolor': 'white'}
        )

        if donut:
            centre_circle = plt.Circle((0, 0), 0.5, fc='white')
            ax.add_patch(centre_circle)

        if title:
            ax.set_title(title, fontweight='bold', pad=10)

        ax.axis('equal')
        plt.tight_layout()
        return cls._fig_to_base64(fig)

    @classmethod
    def grouped_bar_with_line(
        cls,
        labels: List[str],
        bar_datasets: List[Dict],
        line_dataset: Optional[Dict] = None,
        title: str = '',
        xlabel: str = '',
        bar_ylabel: str = '',
        line_ylabel: str = '',
        figsize: Tuple[int, int] = (12, 5)
    ) -> str:
        """
        묶음 막대 + 선 차트 (연도별 비교에 적합)

        Args:
            labels: X축 레이블
            bar_datasets: 막대 데이터셋들
            line_dataset: 선 데이터셋 (선택)

        Returns:
            Base64 인코딩된 PNG 이미지 문자열
        """
        fig, ax1 = plt.subplots(figsize=figsize)

        x = np.arange(len(labels))
        n_bars = len(bar_datasets)
        width = 0.8 / n_bars

        # 막대 그래프
        for i, ds in enumerate(bar_datasets):
            data = ds.get('data', [])
            label = ds.get('label', f'Dataset {i+1}')
            color = ds.get('color', cls.COLORS[i % len(cls.COLORS)])
            offset = x + (i - (n_bars - 1) / 2) * width
            ax1.bar(offset, data, width, label=label, color=color, alpha=0.85)

        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45, ha='right')
        if bar_ylabel:
            ax1.set_ylabel(bar_ylabel)

        # 선 그래프 (선택적)
        if line_dataset:
            ax2 = ax1.twinx()
            line_data = line_dataset.get('data', [])
            line_label = line_dataset.get('label', 'Line')
            line_color = line_dataset.get('color', '#F24822')
            ax2.plot(x, line_data, color=line_color, marker='o',
                    linewidth=2, markersize=6, label=line_label)
            ax2.set_ylabel(line_ylabel, color=line_color)
            ax2.tick_params(axis='y', labelcolor=line_color)

            # 범례 통합
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        else:
            ax1.legend(loc='upper right')

        if title:
            ax1.set_title(title, fontweight='bold', pad=10)

        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)

        plt.tight_layout()
        return cls._fig_to_base64(fig)
