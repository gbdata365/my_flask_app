# -*- coding: utf-8 -*-
"""
================================================================================
공통 차트 모듈 (charts.py)
================================================================================

모든 프로젝트에서 공통으로 사용하는 차트 함수들입니다.
스타일과 색상은 .env 파일에서 변경할 수 있습니다.

[.env 설정 예시]
    # 차트 색상 (쉼표로 구분)
    CHART_COLORS=#1D64F2,#F24822,#10b981,#f59e0b,#8b5cf6

    # 차트 기본 설정
    CHART_DPI=100
    CHART_FONT_SIZE=10
    CHART_TITLE_SIZE=12
    CHART_GRID_ALPHA=0.3

[사용 예시]
    from module.charts import BarChart, LineChart, PieChart

    # 막대 차트
    chart = BarChart(title='시도별 인구')
    chart.add_series('2024.12', regions, values1)
    chart.add_series('2023.12', regions, values2)
    img_base64 = chart.to_base64()

    # 선 차트
    chart = LineChart(title='월별 추이')
    chart.add_series('인구', months, values)
    img_base64 = chart.to_base64()

================================================================================
"""

import os
import io
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
import numpy as np

# matplotlib 임포트
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정
try:
    import koreanize_matplotlib
except ImportError:
    # koreanize_matplotlib 없으면 수동 설정
    if os.name == 'nt':  # Windows
        plt.rcParams['font.family'] = 'Malgun Gothic'
    else:  # Mac/Linux
        plt.rcParams['font.family'] = 'AppleGothic'
    plt.rcParams['axes.unicode_minus'] = False

# .env 로드
from dotenv import load_dotenv
_module_dir = Path(__file__).parent
_env_paths = [
    _module_dir / '.env',
    _module_dir.parent / '.env',
]
for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        break


# =============================================================================
# 차트 스타일 설정 (환경변수에서 로드)
# =============================================================================
class ChartStyle:
    """차트 스타일 설정 클래스"""

    # 기본 색상 팔레트
    DEFAULT_COLORS = ['#1D64F2', '#F24822', '#10b981', '#f59e0b', '#8b5cf6',
                      '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1']

    # 환경변수에서 설정 로드
    COLORS = os.environ.get('CHART_COLORS', ','.join(DEFAULT_COLORS)).split(',')
    DPI = int(os.environ.get('CHART_DPI', '100'))
    FONT_SIZE = int(os.environ.get('CHART_FONT_SIZE', '10'))
    TITLE_SIZE = int(os.environ.get('CHART_TITLE_SIZE', '12'))
    LABEL_SIZE = int(os.environ.get('CHART_LABEL_SIZE', '9'))
    GRID_ALPHA = float(os.environ.get('CHART_GRID_ALPHA', '0.3'))
    FIGURE_WIDTH = int(os.environ.get('CHART_FIGURE_WIDTH', '12'))
    FIGURE_HEIGHT = int(os.environ.get('CHART_FIGURE_HEIGHT', '6'))

    # 막대 차트 설정
    BAR_WIDTH = float(os.environ.get('CHART_BAR_WIDTH', '0.8'))
    BAR_LABEL_FORMAT = os.environ.get('CHART_BAR_LABEL_FORMAT', '{:,.0f}')

    # 선 차트 설정
    LINE_WIDTH = float(os.environ.get('CHART_LINE_WIDTH', '2'))
    MARKER_SIZE = int(os.environ.get('CHART_MARKER_SIZE', '6'))

    @classmethod
    def get_color(cls, index: int) -> str:
        """인덱스에 해당하는 색상 반환"""
        return cls.COLORS[index % len(cls.COLORS)]

    @classmethod
    def get_colors(cls, count: int) -> List[str]:
        """지정된 개수만큼 색상 리스트 반환"""
        return [cls.get_color(i) for i in range(count)]


# =============================================================================
# 기본 차트 클래스
# =============================================================================
class BaseChart:
    """모든 차트의 기본 클래스"""

    def __init__(self, title: str = '', xlabel: str = '', ylabel: str = '',
                 figsize: Tuple[int, int] = None):
        self.title = title
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.figsize = figsize or (ChartStyle.FIGURE_WIDTH, ChartStyle.FIGURE_HEIGHT)
        self.fig = None
        self.ax = None
        self.series_data = []

    def _create_figure(self):
        """Figure 생성"""
        self.fig, self.ax = plt.subplots(figsize=self.figsize)
        if self.title:
            self.ax.set_title(self.title, fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
        if self.xlabel:
            self.ax.set_xlabel(self.xlabel, fontsize=ChartStyle.FONT_SIZE)
        if self.ylabel:
            self.ax.set_ylabel(self.ylabel, fontsize=ChartStyle.FONT_SIZE)

    def _finalize(self):
        """차트 마무리"""
        if self.series_data and len(self.series_data) > 1:
            self.ax.legend(fontsize=ChartStyle.LABEL_SIZE)
        plt.tight_layout()

    def to_base64(self) -> str:
        """차트를 base64 문자열로 변환"""
        if self.fig is None:
            self._render()

        buf = io.BytesIO()
        self.fig.savefig(buf, format='png', dpi=ChartStyle.DPI, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(self.fig)
        return img_base64

    def save(self, filepath: str, dpi: int = None):
        """차트를 파일로 저장"""
        if self.fig is None:
            self._render()

        self.fig.savefig(filepath, dpi=dpi or ChartStyle.DPI, bbox_inches='tight')
        plt.close(self.fig)

    def _render(self):
        """차트 렌더링 (서브클래스에서 구현)"""
        raise NotImplementedError


# =============================================================================
# 막대 차트
# =============================================================================
class BarChart(BaseChart):
    """막대 차트 클래스"""

    def __init__(self, title: str = '', xlabel: str = '', ylabel: str = '',
                 figsize: Tuple[int, int] = None, horizontal: bool = False,
                 show_labels: bool = True, label_format: str = None):
        super().__init__(title, xlabel, ylabel, figsize)
        self.horizontal = horizontal
        self.show_labels = show_labels
        self.label_format = label_format or ChartStyle.BAR_LABEL_FORMAT

    def add_series(self, name: str, categories: List[str], values: List[float],
                   color: str = None):
        """데이터 시리즈 추가"""
        self.series_data.append({
            'name': name,
            'categories': categories,
            'values': values,
            'color': color or ChartStyle.get_color(len(self.series_data))
        })

    def _add_bar_labels(self, bars, values, is_horizontal: bool = False):
        """막대에 레이블 추가"""
        for bar, val in zip(bars, values):
            if is_horizontal:
                x = bar.get_width()
                y = bar.get_y() + bar.get_height() / 2
                ha, va = 'left', 'center'
                offset = (3, 0)
            else:
                x = bar.get_x() + bar.get_width() / 2
                y = bar.get_height()
                ha, va = 'center', 'bottom'
                offset = (0, 3)

            label = self.label_format.format(val)
            self.ax.annotate(label, (x, y), textcoords='offset points',
                           xytext=offset, ha=ha, va=va,
                           fontsize=ChartStyle.LABEL_SIZE)

    def _render(self):
        """막대 차트 렌더링"""
        if not self.series_data:
            return

        categories = self.series_data[0]['categories']
        n_series = len(self.series_data)
        n_categories = len(categories)

        # 항목이 많으면 가로 막대, figsize 조정
        if n_categories >= 10 and not self.horizontal:
            self.horizontal = True
            self.figsize = (self.figsize[0], max(6, n_categories * 0.35))

        self._create_figure()

        positions = np.arange(n_categories)
        width = ChartStyle.BAR_WIDTH / n_series

        for i, series in enumerate(self.series_data):
            offset = (i - (n_series - 1) / 2) * width

            if self.horizontal:
                bars = self.ax.barh(positions + offset, series['values'],
                                   width, label=series['name'], color=series['color'])
                if self.show_labels and i == 0:
                    self._add_bar_labels(bars, series['values'], is_horizontal=True)
            else:
                bars = self.ax.bar(positions + offset, series['values'],
                                  width, label=series['name'], color=series['color'])
                if self.show_labels and i == 0:
                    self._add_bar_labels(bars, series['values'], is_horizontal=False)

        if self.horizontal:
            self.ax.set_yticks(positions)
            self.ax.set_yticklabels(categories, fontsize=ChartStyle.FONT_SIZE)
            self.ax.grid(axis='x', alpha=ChartStyle.GRID_ALPHA)
            self.ax.invert_yaxis()
        else:
            self.ax.set_xticks(positions)
            self.ax.set_xticklabels(categories, rotation=45, ha='right',
                                    fontsize=ChartStyle.FONT_SIZE)
            self.ax.grid(axis='y', alpha=ChartStyle.GRID_ALPHA)

        self._finalize()


# =============================================================================
# 선 차트
# =============================================================================
class LineChart(BaseChart):
    """선 차트 클래스"""

    def __init__(self, title: str = '', xlabel: str = '', ylabel: str = '',
                 figsize: Tuple[int, int] = None, show_markers: bool = True,
                 show_labels: bool = False, label_format: str = None):
        super().__init__(title, xlabel, ylabel, figsize)
        self.show_markers = show_markers
        self.show_labels = show_labels
        self.label_format = label_format or '{:,.0f}'

    def add_series(self, name: str, x_values: List, y_values: List[float],
                   color: str = None, linestyle: str = '-'):
        """데이터 시리즈 추가"""
        self.series_data.append({
            'name': name,
            'x_values': x_values,
            'y_values': y_values,
            'color': color or ChartStyle.get_color(len(self.series_data)),
            'linestyle': linestyle
        })

    def _render(self):
        """선 차트 렌더링"""
        if not self.series_data:
            return

        self._create_figure()

        for series in self.series_data:
            marker = 'o' if self.show_markers else None
            self.ax.plot(series['x_values'], series['y_values'],
                        label=series['name'], color=series['color'],
                        linestyle=series['linestyle'],
                        linewidth=ChartStyle.LINE_WIDTH,
                        marker=marker, markersize=ChartStyle.MARKER_SIZE)

            if self.show_labels:
                for x, y in zip(series['x_values'], series['y_values']):
                    self.ax.annotate(self.label_format.format(y), (x, y),
                                   textcoords='offset points', xytext=(0, 5),
                                   ha='center', fontsize=ChartStyle.LABEL_SIZE)

        self.ax.grid(alpha=ChartStyle.GRID_ALPHA)

        # X축 레이블 회전
        plt.xticks(rotation=45, ha='right', fontsize=ChartStyle.FONT_SIZE)

        self._finalize()


# =============================================================================
# 파이/도넛 차트
# =============================================================================
class PieChart(BaseChart):
    """파이/도넛 차트 클래스"""

    def __init__(self, title: str = '', figsize: Tuple[int, int] = None,
                 donut: bool = False, center_text: str = '', sub_text: str = '',
                 show_percent: bool = True, show_value: bool = False):
        super().__init__(title, figsize=figsize or (8, 8))
        self.donut = donut
        self.center_text = center_text
        self.sub_text = sub_text
        self.show_percent = show_percent
        self.show_value = show_value
        self.labels = []
        self.values = []
        self.colors = []

    def set_data(self, labels: List[str], values: List[float],
                 colors: List[str] = None):
        """데이터 설정"""
        self.labels = labels
        self.values = values
        self.colors = colors or ChartStyle.get_colors(len(labels))

    def _render(self):
        """파이/도넛 차트 렌더링"""
        if not self.values:
            return

        self._create_figure()

        # autopct 함수
        def make_autopct(values):
            def autopct(pct):
                total = sum(values)
                val = int(round(pct * total / 100.0))
                if self.show_percent and self.show_value:
                    return f'{pct:.1f}%\n({val:,})'
                elif self.show_percent:
                    return f'{pct:.1f}%'
                elif self.show_value:
                    return f'{val:,}'
                return ''
            return autopct

        wedgeprops = {'width': 0.5} if self.donut else {}

        wedges, texts, autotexts = self.ax.pie(
            self.values, labels=self.labels, colors=self.colors,
            autopct=make_autopct(self.values), startangle=90,
            wedgeprops=wedgeprops
        )

        # 텍스트 스타일
        for text in texts:
            text.set_fontsize(ChartStyle.FONT_SIZE)
        for autotext in autotexts:
            autotext.set_fontsize(ChartStyle.LABEL_SIZE)

        # 도넛 중앙 텍스트
        if self.donut and self.center_text:
            self.ax.text(0, 0.05, self.center_text, ha='center', va='center',
                        fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
            if self.sub_text:
                self.ax.text(0, -0.1, self.sub_text, ha='center', va='center',
                            fontsize=ChartStyle.FONT_SIZE, color='gray')

        self.ax.axis('equal')
        self._finalize()


# =============================================================================
# 스택 막대 차트
# =============================================================================
class StackedBarChart(BaseChart):
    """스택 막대 차트 클래스"""

    def __init__(self, title: str = '', xlabel: str = '', ylabel: str = '',
                 figsize: Tuple[int, int] = None, horizontal: bool = False,
                 show_labels: bool = True, label_format: str = None):
        super().__init__(title, xlabel, ylabel, figsize)
        self.horizontal = horizontal
        self.show_labels = show_labels
        self.label_format = label_format or '{:,.0f}'

    def add_series(self, name: str, categories: List[str], values: List[float],
                   color: str = None):
        """데이터 시리즈 추가"""
        self.series_data.append({
            'name': name,
            'categories': categories,
            'values': values,
            'color': color or ChartStyle.get_color(len(self.series_data))
        })

    def _render(self):
        """스택 막대 차트 렌더링"""
        if not self.series_data:
            return

        categories = self.series_data[0]['categories']
        n_categories = len(categories)

        self._create_figure()

        positions = np.arange(n_categories)
        bottom = np.zeros(n_categories)

        for series in self.series_data:
            values = np.array(series['values'])

            if self.horizontal:
                self.ax.barh(positions, values, left=bottom,
                           label=series['name'], color=series['color'])
            else:
                self.ax.bar(positions, values, bottom=bottom,
                          label=series['name'], color=series['color'])

            bottom += values

        if self.horizontal:
            self.ax.set_yticks(positions)
            self.ax.set_yticklabels(categories, fontsize=ChartStyle.FONT_SIZE)
            self.ax.grid(axis='x', alpha=ChartStyle.GRID_ALPHA)
        else:
            self.ax.set_xticks(positions)
            self.ax.set_xticklabels(categories, rotation=45, ha='right',
                                    fontsize=ChartStyle.FONT_SIZE)
            self.ax.grid(axis='y', alpha=ChartStyle.GRID_ALPHA)

        self._finalize()


# =============================================================================
# 히트맵
# =============================================================================
class HeatmapChart(BaseChart):
    """히트맵 차트 클래스"""

    def __init__(self, title: str = '', xlabel: str = '', ylabel: str = '',
                 figsize: Tuple[int, int] = None, cmap: str = 'YlOrRd',
                 show_values: bool = True, value_format: str = '{:.1f}'):
        super().__init__(title, xlabel, ylabel, figsize)
        self.cmap = cmap
        self.show_values = show_values
        self.value_format = value_format
        self.data = None
        self.row_labels = []
        self.col_labels = []

    def set_data(self, data: np.ndarray, row_labels: List[str], col_labels: List[str]):
        """데이터 설정"""
        self.data = data
        self.row_labels = row_labels
        self.col_labels = col_labels

    def _render(self):
        """히트맵 렌더링"""
        if self.data is None:
            return

        # figsize 자동 조정
        n_rows, n_cols = self.data.shape
        self.figsize = (max(8, n_cols * 0.8), max(6, n_rows * 0.5))

        self._create_figure()

        im = self.ax.imshow(self.data, cmap=self.cmap, aspect='auto')

        # 축 레이블
        self.ax.set_xticks(np.arange(len(self.col_labels)))
        self.ax.set_yticks(np.arange(len(self.row_labels)))
        self.ax.set_xticklabels(self.col_labels, rotation=45, ha='right',
                                fontsize=ChartStyle.FONT_SIZE)
        self.ax.set_yticklabels(self.row_labels, fontsize=ChartStyle.FONT_SIZE)

        # 값 표시
        if self.show_values:
            for i in range(len(self.row_labels)):
                for j in range(len(self.col_labels)):
                    val = self.data[i, j]
                    # 배경색에 따라 텍스트 색상 결정
                    text_color = 'white' if val > self.data.mean() else 'black'
                    self.ax.text(j, i, self.value_format.format(val),
                               ha='center', va='center', color=text_color,
                               fontsize=ChartStyle.LABEL_SIZE)

        # 컬러바
        plt.colorbar(im, ax=self.ax)

        self._finalize()


# =============================================================================
# 복합 차트 (막대 + 선)
# =============================================================================
class ComboChart(BaseChart):
    """
    복합 차트 클래스 - 막대와 선을 함께 표시

    사용 예시:
        chart = ComboChart(title='인구 및 증가율', ylabel='인구', ylabel2='증가율(%)')
        chart.add_bar('인구', regions, pop_values)
        chart.add_line('증가율', regions, rate_values)
        chart.add_average_line(average_value, label='전국평균', color='red', linestyle='--')
        chart.highlight_categories(['경북'], edgecolor='red', linewidth=2)
        img = chart.to_base64()
    """

    def __init__(self, title: str = '', xlabel: str = '', ylabel: str = '',
                 ylabel2: str = '', figsize: Tuple[int, int] = None,
                 show_labels: bool = True, label_format: str = None):
        super().__init__(title, xlabel, ylabel, figsize)
        self.ylabel2 = ylabel2  # 오른쪽 Y축 라벨
        self.show_labels = show_labels
        self.label_format = label_format or '{:,.0f}'
        self.bar_data = []
        self.line_data = []
        self.average_lines = []
        self.highlights = {}  # {category: {edgecolor, linewidth, ...}}

    def add_bar(self, name: str, categories: List[str], values: List[float],
                color: str = None, axis: str = 'left'):
        """막대 시리즈 추가 (axis: 'left' 또는 'right')"""
        self.bar_data.append({
            'name': name,
            'categories': categories,
            'values': values,
            'color': color or ChartStyle.get_color(len(self.bar_data)),
            'axis': axis
        })

    def add_line(self, name: str, categories: List[str], values: List[float],
                 color: str = None, linestyle: str = '-', marker: str = 'o',
                 axis: str = 'right'):
        """선 시리즈 추가 (axis: 'left' 또는 'right')"""
        self.line_data.append({
            'name': name,
            'categories': categories,
            'values': values,
            'color': color or ChartStyle.get_color(len(self.bar_data) + len(self.line_data)),
            'linestyle': linestyle,
            'marker': marker,
            'axis': axis
        })

    def add_average_line(self, value: float, label: str = '평균',
                         color: str = 'red', linestyle: str = '--',
                         linewidth: float = 1.5, axis: str = 'left'):
        """평균선 추가 (수평선)"""
        self.average_lines.append({
            'value': value,
            'label': label,
            'color': color,
            'linestyle': linestyle,
            'linewidth': linewidth,
            'axis': axis
        })

    def highlight_categories(self, categories: List[str], edgecolor: str = 'red',
                            linewidth: float = 2, hatch: str = None):
        """특정 카테고리 강조 (빨간 테두리 등)"""
        for cat in categories:
            self.highlights[cat] = {
                'edgecolor': edgecolor,
                'linewidth': linewidth,
                'hatch': hatch
            }

    def _render(self):
        """복합 차트 렌더링"""
        if not self.bar_data and not self.line_data:
            return

        categories = (self.bar_data[0]['categories'] if self.bar_data
                     else self.line_data[0]['categories'])
        n_categories = len(categories)

        self._create_figure()

        # 오른쪽 Y축 생성 (선 그래프용)
        ax2 = None
        if self.line_data or any(avg['axis'] == 'right' for avg in self.average_lines):
            ax2 = self.ax.twinx()
            if self.ylabel2:
                ax2.set_ylabel(self.ylabel2, fontsize=ChartStyle.FONT_SIZE)

        positions = np.arange(n_categories)
        n_bars = len(self.bar_data)
        width = ChartStyle.BAR_WIDTH / max(n_bars, 1)

        # 막대 그래프
        for i, bar in enumerate(self.bar_data):
            offset = (i - (n_bars - 1) / 2) * width if n_bars > 1 else 0
            target_ax = ax2 if bar['axis'] == 'right' and ax2 else self.ax

            bars = target_ax.bar(positions + offset, bar['values'], width,
                                label=bar['name'], color=bar['color'], zorder=2)

            # 강조 처리
            for j, cat in enumerate(categories):
                if cat in self.highlights:
                    hl = self.highlights[cat]
                    bars[j].set_edgecolor(hl['edgecolor'])
                    bars[j].set_linewidth(hl['linewidth'])
                    if hl['hatch']:
                        bars[j].set_hatch(hl['hatch'])

            # 레이블 표시 (첫 번째 시리즈만)
            if self.show_labels and i == 0:
                for bar_rect, val in zip(bars, bar['values']):
                    height = bar_rect.get_height()
                    target_ax.annotate(self.label_format.format(val),
                                      (bar_rect.get_x() + bar_rect.get_width() / 2, height),
                                      textcoords='offset points', xytext=(0, 3),
                                      ha='center', va='bottom',
                                      fontsize=ChartStyle.LABEL_SIZE)

        # 선 그래프
        for line in self.line_data:
            target_ax = ax2 if line['axis'] == 'right' and ax2 else self.ax
            target_ax.plot(positions, line['values'], label=line['name'],
                          color=line['color'], linestyle=line['linestyle'],
                          marker=line['marker'], linewidth=ChartStyle.LINE_WIDTH,
                          markersize=ChartStyle.MARKER_SIZE, zorder=3)

        # 평균선 (수평선)
        for avg in self.average_lines:
            target_ax = ax2 if avg['axis'] == 'right' and ax2 else self.ax
            target_ax.axhline(y=avg['value'], color=avg['color'],
                             linestyle=avg['linestyle'], linewidth=avg['linewidth'],
                             label=avg['label'], zorder=1)

        # X축 설정
        self.ax.set_xticks(positions)
        self.ax.set_xticklabels(categories, rotation=45, ha='right',
                                fontsize=ChartStyle.FONT_SIZE)
        self.ax.grid(axis='y', alpha=ChartStyle.GRID_ALPHA, zorder=0)

        # 범례 (양쪽 축 통합)
        lines1, labels1 = self.ax.get_legend_handles_labels()
        if ax2:
            lines2, labels2 = ax2.get_legend_handles_labels()
            self.ax.legend(lines1 + lines2, labels1 + labels2,
                          loc='upper right', fontsize=ChartStyle.LABEL_SIZE)
        elif labels1:
            self.ax.legend(fontsize=ChartStyle.LABEL_SIZE)

        plt.tight_layout()


# =============================================================================
# 유틸리티 함수
# =============================================================================
def quick_bar(categories: List[str], values: List[float], title: str = '',
              **kwargs) -> str:
    """간편 막대 차트 생성"""
    chart = BarChart(title=title, **kwargs)
    chart.add_series('', categories, values)
    return chart.to_base64()


def quick_line(x_values: List, y_values: List[float], title: str = '',
               **kwargs) -> str:
    """간편 선 차트 생성"""
    chart = LineChart(title=title, **kwargs)
    chart.add_series('', x_values, y_values)
    return chart.to_base64()


def quick_pie(labels: List[str], values: List[float], title: str = '',
              donut: bool = False, **kwargs) -> str:
    """간편 파이/도넛 차트 생성"""
    chart = PieChart(title=title, donut=donut, **kwargs)
    chart.set_data(labels, values)
    return chart.to_base64()


# =============================================================================
# 차트 타입 매핑 (문자열로 차트 생성용)
# =============================================================================
CHART_TYPES = {
    'bar': BarChart,
    'line': LineChart,
    'pie': PieChart,
    'donut': lambda **kw: PieChart(donut=True, **kw),
    'stacked_bar': StackedBarChart,
    'heatmap': HeatmapChart,
    'combo': ComboChart,
}


def create_chart(chart_type: str, **kwargs) -> BaseChart:
    """차트 타입 문자열로 차트 객체 생성"""
    if chart_type not in CHART_TYPES:
        raise ValueError(f"Unknown chart type: {chart_type}. "
                        f"Available: {list(CHART_TYPES.keys())}")
    return CHART_TYPES[chart_type](**kwargs)
