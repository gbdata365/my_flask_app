import pandas as pd
import plotly.graph_objs as go
import plotly.utils
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os
from datetime import datetime
import re


class CSVAnalyzer:
    """CSV 파일 자동 분석 및 차트 생성 클래스"""
    
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        self.df = None
        self.analysis_results = {}
        self.detected_columns = {
            'time_columns': [],
            'location_columns': [],
            'numeric_columns': [],
            'categorical_columns': []
        }
    
    def load_and_analyze_csv(self) -> Dict[str, Any]:
        """CSV 파일 로드 및 기본 분석 수행"""
        try:
            # CSV 파일 로드 (다양한 인코딩 시도)
            encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
            for encoding in encodings:
                try:
                    self.df = pd.read_csv(self.csv_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if self.df is None:
                raise ValueError("파일 인코딩을 인식할 수 없습니다.")
            
            # 컬럼 타입 자동 감지
            self._detect_column_types()
            
            # 기본 통계 정보
            self.analysis_results = {
                'file_info': {
                    'filename': self.csv_path.name,
                    'rows': len(self.df),
                    'columns': len(self.df.columns),
                    'upload_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                'columns': dict(self.detected_columns),
                'sample_data': self.df.head(5).to_dict('records'),
                'summary_stats': self._generate_summary_stats()
            }
            
            return self.analysis_results
            
        except Exception as e:
            return {'error': f"파일 분석 중 오류 발생: {str(e)}"}
    
    def _detect_column_types(self):
        """컬럼 타입 자동 감지"""
        # 시간/날짜 컬럼 패턴
        time_patterns = [
            r'(\d{4})[년\-/]?(\d{1,2})[월\-/]?(\d{1,2})?일?',  # 년월일
            r'(\d{4})(\d{2})(\d{2})?',  # YYYYMMDD
            r'(\d{1,2})[월\-/](\d{1,2})[일\-/](\d{4})',  # MM/DD/YYYY
        ]
        
        # 지역 관련 키워드
        location_keywords = ['시도', '시군구', '시', '도', '군', '구', '지역', 'region', 'area', 'location', 'city', 'province']
        
        for col in self.df.columns:
            col_lower = str(col).lower()
            col_str = str(col)
            
            # 시간 컬럼 감지
            if any(keyword in col_lower for keyword in ['년', 'year', '월', 'month', '일', 'day', 'date', 'time']):
                self.detected_columns['time_columns'].append(col)
            elif self._is_time_column(self.df[col]):
                self.detected_columns['time_columns'].append(col)
            
            # 지역 컬럼 감지
            elif any(keyword in col_lower for keyword in location_keywords):
                self.detected_columns['location_columns'].append(col)
            
            # 숫자 컬럼 감지 (숫자로 변환 가능한 컬럼)
            elif self._is_numeric_column(self.df[col]):
                self.detected_columns['numeric_columns'].append(col)
            
            # 범주형 컬럼
            else:
                unique_ratio = len(self.df[col].unique()) / len(self.df)
                if unique_ratio < 0.5:  # 고유값 비율이 50% 미만인 경우 범주형으로 간주
                    self.detected_columns['categorical_columns'].append(col)
    
    def _is_time_column(self, series: pd.Series) -> bool:
        """시계열 컬럼인지 판단"""
        sample = series.dropna().astype(str).head(10)
        time_patterns = [
            r'\d{4}',  # 년도
            r'\d{4}\d{2}',  # 년월
            r'\d{4}-\d{2}',  # 년-월
            r'\d{4}/\d{2}',  # 년/월
        ]
        
        for pattern in time_patterns:
            matches = sum(1 for val in sample if re.match(pattern, str(val)))
            if matches / len(sample) > 0.8:  # 80% 이상 매칭되면 시간 컬럼으로 간주
                return True
        return False
    
    def _is_numeric_column(self, series: pd.Series) -> bool:
        """숫자 컬럼인지 판단"""
        try:
            # 문자열을 숫자로 변환 시도 (쉼표, 특수문자 제거)
            cleaned = series.astype(str).str.replace(',', '').str.replace('*', '1').str.strip()
            numeric_converted = pd.to_numeric(cleaned, errors='coerce')
            # 90% 이상이 숫자로 변환 가능하면 숫자 컬럼으로 간주
            return (numeric_converted.notna().sum() / len(series)) > 0.9
        except:
            return False
    
    def _generate_summary_stats(self) -> Dict[str, Any]:
        """요약 통계 생성"""
        stats = {}
        
        for col in self.detected_columns['numeric_columns']:
            try:
                # 숫자 컬럼 정리
                cleaned = self.df[col].astype(str).str.replace(',', '').str.replace('*', '1').str.strip()
                numeric_data = pd.to_numeric(cleaned, errors='coerce').fillna(0)
                
                stats[col] = {
                    'sum': int(numeric_data.sum()),
                    'mean': round(numeric_data.mean(), 2),
                    'max': int(numeric_data.max()),
                    'min': int(numeric_data.min()),
                    'count': int(numeric_data.count())
                }
            except:
                continue
        
        return stats
    
    def generate_charts(self) -> Dict[str, Any]:
        """자동 차트 생성"""
        charts = {}
        
        if not self.detected_columns['numeric_columns']:
            return {'error': '차트 생성을 위한 숫자 데이터를 찾을 수 없습니다.'}
        
        # 시계열 차트 생성
        if self.detected_columns['time_columns']:
            charts['timeseries'] = self._create_timeseries_charts()
        
        # 지역별 차트 생성
        if self.detected_columns['location_columns']:
            charts['regional'] = self._create_regional_charts()
        
        # 분포 차트 생성
        charts['distribution'] = self._create_distribution_charts()
        
        return charts
    
    def _create_timeseries_charts(self) -> List[Dict[str, Any]]:
        """시계열 차트 생성"""
        charts = []
        
        time_col = self.detected_columns['time_columns'][0]  # 첫 번째 시간 컬럼 사용
        
        for numeric_col in self.detected_columns['numeric_columns'][:3]:  # 상위 3개만
            try:
                # 데이터 정리
                df_copy = self.df.copy()
                df_copy[numeric_col] = pd.to_numeric(
                    df_copy[numeric_col].astype(str).str.replace(',', '').str.replace('*', '1'),
                    errors='coerce'
                ).fillna(0)
                
                # 시간 컬럼 정리
                time_data = df_copy[time_col].astype(str)
                
                # 그룹별 집계
                if self.detected_columns['location_columns']:
                    location_col = self.detected_columns['location_columns'][0]
                    grouped = df_copy.groupby([time_col, location_col])[numeric_col].sum().reset_index()
                    
                    # 상위 지역만 표시
                    top_locations = df_copy.groupby(location_col)[numeric_col].sum().nlargest(5).index
                    
                    traces = []
                    for location in top_locations:
                        location_data = grouped[grouped[location_col] == location]
                        if len(location_data) > 0:
                            traces.append({
                                'x': location_data[time_col].tolist(),
                                'y': location_data[numeric_col].tolist(),
                                'type': 'scatter',
                                'mode': 'lines+markers',
                                'name': str(location),
                                'line': {'width': 2},
                                'marker': {'size': 8}
                            })
                else:
                    # 지역 컬럼이 없는 경우 전체 합계
                    grouped = df_copy.groupby(time_col)[numeric_col].sum().reset_index()
                    traces = [{
                        'x': grouped[time_col].tolist(),
                        'y': grouped[numeric_col].tolist(),
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': numeric_col,
                        'line': {'width': 3},
                        'marker': {'size': 10}
                    }]
                
                charts.append({
                    'title': f'{numeric_col} 시계열 추이',
                    'traces': traces,
                    'layout': {
                        'title': f'{numeric_col} 시계열 추이',
                        'xaxis': {'title': time_col},
                        'yaxis': {'title': numeric_col, 'tickformat': ','},
                        'hovermode': 'x unified'
                    }
                })
                
            except Exception as e:
                continue
        
        return charts
    
    def _create_regional_charts(self) -> List[Dict[str, Any]]:
        """지역별 차트 생성"""
        charts = []
        
        if not self.detected_columns['location_columns']:
            return charts
        
        location_col = self.detected_columns['location_columns'][0]
        
        for numeric_col in self.detected_columns['numeric_columns'][:3]:
            try:
                # 데이터 정리
                df_copy = self.df.copy()
                df_copy[numeric_col] = pd.to_numeric(
                    df_copy[numeric_col].astype(str).str.replace(',', '').str.replace('*', '1'),
                    errors='coerce'
                ).fillna(0)
                
                # 지역별 집계
                regional_data = df_copy.groupby(location_col)[numeric_col].sum().sort_values(ascending=False)
                top_regions = regional_data.head(10)  # 상위 10개 지역
                
                # 막대 차트
                charts.append({
                    'title': f'{numeric_col} 지역별 현황',
                    'traces': [{
                        'x': top_regions.values.tolist(),
                        'y': top_regions.index.tolist(),
                        'type': 'bar',
                        'orientation': 'h',
                        'name': numeric_col,
                        'marker': {'color': 'rgba(55, 128, 191, 0.7)'}
                    }],
                    'layout': {
                        'title': f'{numeric_col} 지역별 현황',
                        'xaxis': {'title': numeric_col, 'tickformat': ','},
                        'yaxis': {'title': location_col},
                        'height': 500
                    }
                })
                
            except Exception as e:
                continue
        
        return charts
    
    def _create_distribution_charts(self) -> List[Dict[str, Any]]:
        """분포 차트 생성"""
        charts = []
        
        for numeric_col in self.detected_columns['numeric_columns'][:2]:  # 상위 2개만
            try:
                # 데이터 정리
                df_copy = self.df.copy()
                numeric_data = pd.to_numeric(
                    df_copy[numeric_col].astype(str).str.replace(',', '').str.replace('*', '1'),
                    errors='coerce'
                ).fillna(0)
                
                # 히스토그램
                charts.append({
                    'title': f'{numeric_col} 분포',
                    'traces': [{
                        'x': numeric_data.tolist(),
                        'type': 'histogram',
                        'name': numeric_col,
                        'marker': {'color': 'rgba(255, 127, 14, 0.7)'},
                        'nbinsx': 20
                    }],
                    'layout': {
                        'title': f'{numeric_col} 분포',
                        'xaxis': {'title': numeric_col},
                        'yaxis': {'title': '빈도수'},
                        'bargap': 0.1
                    }
                })
                
            except Exception as e:
                continue
        
        return charts
    
    def generate_dashboard_html(self, title: str = "CSV 데이터 대시보드") -> str:
        """동적 대시보드 HTML 생성"""
        charts = self.generate_charts()
        
        html_template = f'''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ background-color: #f8f9fa; }}
        .dashboard-card {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 20px;
            margin-bottom: 20px;
        }}
        .chart-container {{ 
            height: 500px; 
            margin-bottom: 20px; 
        }}
        .stat-box {{
            text-align: center;
            padding: 15px;
            border-radius: 8px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin-bottom: 10px;
        }}
        .stat-number {{ font-size: 24px; font-weight: bold; }}
        .stat-label {{ font-size: 14px; opacity: 0.9; }}
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <h1 class="text-center mb-4">{title}</h1>
        
        <!-- 파일 정보 -->
        <div class="dashboard-card">
            <h3 class="mb-3">파일 정보</h3>
            <div class="row">
                <div class="col-md-3">
                    <div class="stat-box">
                        <div class="stat-number">{self.analysis_results['file_info']['rows']:,}</div>
                        <div class="stat-label">행 수</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-box">
                        <div class="stat-number">{self.analysis_results['file_info']['columns']}</div>
                        <div class="stat-label">컬럼 수</div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="stat-box">
                        <div class="stat-number">{self.analysis_results['file_info']['filename']}</div>
                        <div class="stat-label">파일명 ({self.analysis_results['file_info']['upload_time']})</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 차트 영역 -->
        <div class="row">
'''
        
        chart_id = 0
        # 시계열 차트
        if 'timeseries' in charts and charts['timeseries']:
            for chart in charts['timeseries']:
                html_template += f'''
            <div class="col-lg-6">
                <div class="dashboard-card">
                    <h4>{chart['title']}</h4>
                    <div id="chart_{chart_id}" class="chart-container"></div>
                </div>
            </div>
'''
                chart_id += 1
        
        # 지역별 차트
        if 'regional' in charts and charts['regional']:
            for chart in charts['regional']:
                html_template += f'''
            <div class="col-lg-6">
                <div class="dashboard-card">
                    <h4>{chart['title']}</h4>
                    <div id="chart_{chart_id}" class="chart-container"></div>
                </div>
            </div>
'''
                chart_id += 1
        
        # 분포 차트
        if 'distribution' in charts and charts['distribution']:
            for chart in charts['distribution']:
                html_template += f'''
            <div class="col-lg-6">
                <div class="dashboard-card">
                    <h4>{chart['title']}</h4>
                    <div id="chart_{chart_id}" class="chart-container"></div>
                </div>
            </div>
'''
                chart_id += 1
        
        html_template += '''
        </div>
        
        <!-- 샘플 데이터 -->
        <div class="dashboard-card">
            <h4 class="mb-3">샘플 데이터</h4>
            <div class="table-responsive">
                <table class="table table-hover table-striped">
                    <thead class="table-dark">
                        <tr>
'''
        
        if self.analysis_results['sample_data']:
            for col in self.analysis_results['sample_data'][0].keys():
                html_template += f'<th>{col}</th>'
        
        html_template += '''
                        </tr>
                    </thead>
                    <tbody>
'''
        
        for row in self.analysis_results['sample_data']:
            html_template += '<tr>'
            for value in row.values():
                html_template += f'<td>{value}</td>'
            html_template += '</tr>'
        
        html_template += f'''
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        const chartsData = {json.dumps(charts, ensure_ascii=False)};
        
        $(document).ready(function() {{
            renderCharts();
        }});
        
        function renderCharts() {{
            let chartId = 0;
            
            // 시계열 차트 렌더링
            if (chartsData.timeseries) {{
                chartsData.timeseries.forEach(chart => {{
                    Plotly.newPlot(`chart_${{chartId}}`, chart.traces, chart.layout, {{responsive: true}});
                    chartId++;
                }});
            }}
            
            // 지역별 차트 렌더링
            if (chartsData.regional) {{
                chartsData.regional.forEach(chart => {{
                    Plotly.newPlot(`chart_${{chartId}}`, chart.traces, chart.layout, {{responsive: true}});
                    chartId++;
                }});
            }}
            
            // 분포 차트 렌더링
            if (chartsData.distribution) {{
                chartsData.distribution.forEach(chart => {{
                    Plotly.newPlot(`chart_${{chartId}}`, chart.traces, chart.layout, {{responsive: true}});
                    chartId++;
                }});
            }}
        }}
    </script>
</body>
</html>
'''
        
        return html_template