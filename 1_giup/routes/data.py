import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import numpy as np
from datetime import datetime, timedelta
import json
import random

def load_data():
    """기업통계등록부 데이터 로드"""
    try:
        file_path = Path(__file__).parent.parent / '분기 기업통계등록부(사업자등록번호 기준) 데이터샘플.xlsx'
        df = pd.read_excel(file_path, header=4)

        # 필요한 컬럼만 선택하고 한글로 변경
        columns_mapping = {
            '시도명': '시도',
            '시군구명': '시군구',
            '기준년도': '년도',
            '분기구분코드': '분기',
        }

        # 데이터 정리
        df = df.rename(columns=columns_mapping)

        # 결측값 제거
        df = df.dropna(subset=['시도', '시군구'])

        # 숫자형 컬럼들 찾아서 정리
        numeric_cols = []
        for col in df.columns:
            if '종사자' in col or '매출액' in col or '수' in col:
                if df[col].dtype == 'object':
                    # 쉼표 제거하고 숫자로 변환
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
                numeric_cols.append(col)

        return df, numeric_cols
    except Exception as e:
        print(f"데이터 로드 중 오류: {e}")
        return pd.DataFrame(), []

def create_time_series_data(base_df, numeric_cols):
    """시계열 데이터 생성 (샘플 데이터 확장)"""
    import random

    # 시계열 데이터를 위한 기간 설정 (2022년 1분기 ~ 2024년 3분기)
    periods = []
    for year in range(2022, 2025):
        for quarter in range(1, 5):
            if year == 2024 and quarter > 3:  # 2024년 3분기까지만
                break
            periods.append((year, quarter))

    time_series_data = []

    # 기존 데이터를 기반으로 각 시도별로 시계열 데이터 생성
    for sido in base_df['시도'].unique():
        sido_data = base_df[base_df['시도'] == sido]

        if len(sido_data) == 0:
            continue

        # 기준값 설정 (현재 데이터를 2024년 3분기로 가정)
        base_values = {}
        for col in numeric_cols:
            if col in sido_data.columns and sido_data[col].notna().sum() > 0:
                base_values[col] = sido_data[col].sum()
            else:
                base_values[col] = random.randint(100, 1000)

        # 각 분기별로 데이터 생성
        for year, quarter in periods:
            # 시간에 따른 성장률 적용
            time_factor = (year - 2022) + (quarter - 1) * 0.25
            growth_rate = 1 + (time_factor * 0.03)  # 연간 약 12% 성장

            # 계절성 효과 추가
            seasonal_factor = 1 + 0.1 * np.sin(2 * np.pi * quarter / 4)

            # 랜덤 노이즈 추가
            noise_factor = random.uniform(0.9, 1.1)

            total_factor = growth_rate * seasonal_factor * noise_factor

            for _, row in sido_data.iterrows():
                new_row = row.copy()
                new_row['년도'] = year
                new_row['분기'] = quarter
                new_row['년분기'] = f"{year}Q{quarter}"

                # 숫자형 컬럼들에 성장률 적용
                for col in numeric_cols:
                    if col in new_row.index and pd.notna(new_row[col]):
                        new_row[col] = new_row[col] * total_factor
                    elif col in base_values:
                        new_row[col] = base_values[col] * total_factor

                time_series_data.append(new_row)

    return pd.DataFrame(time_series_data)

def create_time_series_charts(df, numeric_cols):
    """시계열 차트 생성"""
    if df.empty or not numeric_cols:
        return "<p>데이터를 불러올 수 없습니다.</p>"

    # 기본 분석 지표 선택 (첫 번째 숫자형 컬럼 사용)
    selected_metric = numeric_cols[0]

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>📈 기업통계 시계열 분석 대시보드</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{ background-color: #F2EED8; }}
            .main-container {{
                background: white;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                margin: 20px 0;
                padding: 30px;
            }}
            .metric-card {{
                background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
                color: white;
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 20px;
                text-align: center;
            }}
            .chart-container {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .filter-panel {{
                background: #011C40;
                color: white;
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 20px;
            }}
            .btn-custom {{
                background-color: #F24822;
                border-color: #F24822;
                color: white;
                border-radius: 6px;
                padding: 10px 20px;
                margin: 5px;
            }}
            .btn-custom:hover {{
                background-color: #d73e1a;
                border-color: #d73e1a;
                color: white;
            }}
            .btn-custom.active {{
                background-color: #1243A6;
                border-color: #1243A6;
            }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="main-container">
                <h1 class="text-center mb-4" style="color: #011C40;">
                    📈 기업통계 시계열 분석 대시보드
                </h1>

                <div class="filter-panel">
                    <h5>📊 분석 옵션</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <label class="form-label">분석 지표:</label>
                            <select id="metricSelect" class="form-select" onchange="updateDashboard()">
    """

    # 분석 지표 옵션 추가
    for col in numeric_cols:
        selected = "selected" if col == selected_metric else ""
        html_content += f'<option value="{col}" {selected}>{col}</option>'

    html_content += f"""
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">비교할 시도 선택:</label>
                            <select id="sidoSelect" class="form-select" multiple onchange="updateDashboard()">
                                <option value="전체" selected>전체</option>
    """

    # 시도 옵션 추가
    for sido in sorted(df['시도'].unique()):
        selected = "selected" if sido in ['서울특별시', '부산광역시', '경상북도'] else ""
        html_content += f'<option value="{sido}" {selected}>{sido}</option>'

    # 기간 데이터 생성
    all_periods = sorted(df['년분기'].unique())
    start_period = all_periods[0]
    end_period = all_periods[-1]

    html_content += f"""
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">분석 기간:</label>
                            <div class="row">
                                <div class="col-6">
                                    <select id="startPeriod" class="form-select" onchange="updateDashboard()">
    """

    # 시작 기간 옵션
    for period in all_periods:
        selected = "selected" if period == start_period else ""
        html_content += f'<option value="{period}" {selected}>{period}</option>'

    html_content += f"""
                                    </select>
                                </div>
                                <div class="col-6">
                                    <select id="endPeriod" class="form-select" onchange="updateDashboard()">
    """

    # 종료 기간 옵션
    for period in all_periods:
        selected = "selected" if period == end_period else ""
        html_content += f'<option value="{period}" {selected}>{period}</option>'

    html_content += f"""
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 메트릭 카드들 -->
                <div class="row" id="metricCards">
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h5 id="analysisPeriod">{start_period} ~ {end_period}</h5>
                            <p>분석 기간</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h5 id="regionCount">{len(df['시도'].unique())}</h5>
                            <p>분석 지역 수</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h5 id="dataPoints">{len(df)}</h5>
                            <p>총 데이터 포인트</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h5 id="latestTotal">{df[df['년분기'] == end_period][selected_metric].sum():,.0f}</h5>
                            <p>최신 총 {selected_metric}</p>
                        </div>
                    </div>
                </div>

                <!-- 차트 영역 -->
                <div class="row">
                    <div class="col-12">
                        <div class="chart-container">
                            <h5>📈 시계열 트렌드 분석</h5>
                            <div id="timeSeriesChart" style="height: 500px;"></div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-6">
                        <div class="chart-container">
                            <h5>📊 성장률 분석</h5>
                            <div id="growthChart" style="height: 400px;"></div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-container">
                            <h5>🔄 계절성 분석</h5>
                            <div id="seasonalChart" style="height: 400px;"></div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-6">
                        <div class="chart-container">
                            <h5>📋 기간별 총계</h5>
                            <div class="table-responsive">
                                <table class="table table-striped" id="periodTable">
                                    <thead class="table-dark">
                                        <tr>
                                            <th>년분기</th>
                                            <th id="periodTableHeader">{selected_metric}</th>
                                        </tr>
                                    </thead>
                                    <tbody id="periodTableBody">
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-container">
                            <h5>🔮 추세 예측</h5>
                            <div id="forecastChart" style="height: 400px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // 데이터
            const rawData = {df.to_json(orient='records', force_ascii=False)};
            const numericCols = {json.dumps(numeric_cols)};
            const allPeriods = {json.dumps(all_periods)};

            function updateDashboard() {{
                const selectedMetric = document.getElementById('metricSelect').value;
                const selectedSidos = Array.from(document.getElementById('sidoSelect').selectedOptions).map(option => option.value);
                const startPeriod = document.getElementById('startPeriod').value;
                const endPeriod = document.getElementById('endPeriod').value;

                // 데이터 필터링
                let filteredData = rawData.filter(row =>
                    row['년분기'] >= startPeriod && row['년분기'] <= endPeriod
                );

                if (!selectedSidos.includes('전체')) {{
                    filteredData = filteredData.filter(row => selectedSidos.includes(row['시도']));
                }}

                // 메트릭 카드 업데이트
                updateMetricCards(filteredData, selectedMetric, startPeriod, endPeriod);

                // 시계열 데이터 집계
                const timeSeriesData = aggregateTimeSeriesData(filteredData, selectedMetric);

                // 차트 업데이트
                updateTimeSeriesChart(timeSeriesData, selectedMetric);
                updateGrowthChart(timeSeriesData, selectedMetric);
                updateSeasonalChart(filteredData, selectedMetric);
                updatePeriodTable(filteredData, selectedMetric);
                updateForecastChart(timeSeriesData, selectedMetric);
            }}

            function updateMetricCards(data, metric, startPeriod, endPeriod) {{
                const uniqueSidos = [...new Set(data.map(row => row['시도']))];
                const latestPeriodData = data.filter(row => row['년분기'] === endPeriod);
                const latestTotal = latestPeriodData.reduce((sum, row) => sum + (row[metric] || 0), 0);

                document.getElementById('analysisperiod').textContent = `${{startPeriod}} ~ ${{endPeriod}}`;
                document.getElementById('regionCount').textContent = uniqueSidos.length;
                document.getElementById('dataPoints').textContent = data.length.toLocaleString();
                document.getElementById('latestTotal').textContent = latestTotal.toLocaleString();
            }}

            function aggregateTimeSeriesData(data, metric) {{
                const aggregated = {{}};
                data.forEach(row => {{
                    const key = `${{row['시도']}}_${{row['년분기']}}`;
                    if (!aggregated[key]) {{
                        aggregated[key] = {{
                            시도: row['시도'],
                            년분기: row['년분기'],
                            value: 0
                        }};
                    }}
                    aggregated[key].value += row[metric] || 0;
                }});

                return Object.values(aggregated);
            }}

            function updateTimeSeriesChart(data, metric) {{
                const sidoGroups = {{}};
                data.forEach(row => {{
                    if (!sidoGroups[row.시도]) sidoGroups[row.시도] = [];
                    sidoGroups[row.시도].push(row);
                }});

                const traces = Object.keys(sidoGroups).map(sido => ({
                    x: sidoGroups[sido].map(d => d.년분기),
                    y: sidoGroups[sido].map(d => d.value),
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: sido,
                    line: {{ width: 3 }},
                    marker: {{ size: 8 }}
                }));

                const layout = {{
                    title: `시도별 ${{metric}} 시계열 변화`,
                    xaxis: {{ title: '년분기', tickangle: -45 }},
                    yaxis: {{ title: metric }},
                    margin: {{ l: 50, r: 50, t: 50, b: 100 }},
                    hovermode: 'x unified'
                }};

                Plotly.newPlot('timeSeriesChart', traces, layout, {{responsive: true}});
            }}

            function updateGrowthChart(data, metric) {{
                // 성장률 계산 (간단한 전기 대비 성장률)
                const growthData = [];
                const sidoGroups = {{}};

                data.forEach(row => {{
                    if (!sidoGroups[row.시도]) sidoGroups[row.시도] = [];
                    sidoGroups[row.시도].push(row);
                }});

                Object.keys(sidoGroups).forEach(sido => {{
                    const sorted = sidoGroups[sido].sort((a, b) => a.년분기.localeCompare(b.년분기));
                    for (let i = 1; i < sorted.length; i++) {{
                        const current = sorted[i].value;
                        const previous = sorted[i-1].value;
                        const growthRate = previous > 0 ? ((current - previous) / previous) * 100 : 0;

                        growthData.push({{
                            시도: sido,
                            년분기: sorted[i].년분기,
                            성장률: growthRate
                        }});
                    }}
                }});

                const traces = Object.keys(sidoGroups).map(sido => {{
                    const sidoGrowth = growthData.filter(d => d.시도 === sido);
                    return {{
                        x: sidoGrowth.map(d => d.년분기),
                        y: sidoGrowth.map(d => d.성장률),
                        type: 'scatter',
                        mode: 'lines+markers',
                        name: sido
                    }};
                }});

                const layout = {{
                    title: `${{metric}} 전기 대비 성장률`,
                    xaxis: {{ title: '년분기', tickangle: -45 }},
                    yaxis: {{ title: '성장률 (%)' }},
                    margin: {{ l: 50, r: 50, t: 50, b: 100 }},
                    shapes: [{{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 0, y1: 0, line: {{ color: 'red', width: 2, dash: 'dash' }} }}]
                }};

                Plotly.newPlot('growthChart', traces, layout, {{responsive: true}});
            }}

            function updateSeasonalChart(data, metric) {{
                // 분기별 평균값 계산
                const quarterlyData = {{ 1: [], 2: [], 3: [], 4: [] }};

                data.forEach(row => {{
                    const quarter = parseInt(row['년분기'].split('Q')[1]);
                    if (quarterlyData[quarter]) {{
                        quarterlyData[quarter].push(row[metric] || 0);
                    }}
                }});

                const avgData = Object.keys(quarterlyData).map(quarter => {{
                    const values = quarterlyData[quarter];
                    const avg = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;
                    return {{ quarter: `${{quarter}}분기`, value: avg }};
                }});

                const trace = {{
                    x: avgData.map(d => d.quarter),
                    y: avgData.map(d => d.value),
                    type: 'bar',
                    marker: {{ color: avgData.map(d => d.value), colorscale: 'Blues' }}
                }};

                const layout = {{
                    title: `분기별 평균 ${{metric}}`,
                    xaxis: {{ title: '분기' }},
                    yaxis: {{ title: `평균 ${{metric}}` }},
                    margin: {{ l: 50, r: 50, t: 50, b: 50 }}
                }};

                Plotly.newPlot('seasonalChart', [trace], layout, {{responsive: true}});
            }}

            function updatePeriodTable(data, metric) {{
                const periodSums = {{}};
                data.forEach(row => {{
                    if (!periodSums[row['년분기']]) periodSums[row['년분기']] = 0;
                    periodSums[row['년분기']] += row[metric] || 0;
                }});

                const sortedPeriods = Object.keys(periodSums).sort().slice(-8); // 최근 8분기
                const tbody = document.getElementById('periodTableBody');
                tbody.innerHTML = '';

                sortedPeriods.forEach(period => {{
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${{period}}</td>
                        <td>${{periodSums[period].toLocaleString()}}</td>
                    `;
                }});

                document.getElementById('periodTableHeader').textContent = metric;
            }}

            function updateForecastChart(data, metric) {{
                // 전체 추세 계산
                const periodSums = {{}};
                data.forEach(row => {{
                    if (!periodSums[row['년분기']]) periodSums[row['년분기']] = 0;
                    periodSums[row['년분기']] += row[metric] || 0;
                }});

                const sortedData = Object.keys(periodSums).sort().map((period, index) => ({{
                    period,
                    value: periodSums[period],
                    index
                }}));

                // 간단한 선형 추세 계산
                const n = sortedData.length;
                const sumX = sortedData.reduce((sum, d) => sum + d.index, 0);
                const sumY = sortedData.reduce((sum, d) => sum + d.value, 0);
                const sumXY = sortedData.reduce((sum, d) => sum + d.index * d.value, 0);
                const sumXX = sortedData.reduce((sum, d) => sum + d.index * d.index, 0);

                const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
                const intercept = (sumY - slope * sumX) / n;

                // 예측값 생성 (향후 4분기)
                const predictions = [];
                for (let i = 1; i <= 4; i++) {{
                    const futureIndex = n + i - 1;
                    const predictedValue = slope * futureIndex + intercept;
                    predictions.push({{
                        period: `예측Q${{i}}`,
                        value: Math.max(0, predictedValue),
                        type: '예측'
                    }});
                }}

                // 실제 데이터 트레이스
                const actualTrace = {{
                    x: sortedData.map(d => d.period),
                    y: sortedData.map(d => d.value),
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: '실제',
                    line: {{ color: 'blue' }}
                }};

                // 예측 데이터 트레이스
                const forecastTrace = {{
                    x: predictions.map(d => d.period),
                    y: predictions.map(d => d.value),
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: '예측',
                    line: {{ color: 'red', dash: 'dash' }}
                }};

                const layout = {{
                    title: `${{metric}} 추세 예측`,
                    xaxis: {{ title: '년분기', tickangle: -45 }},
                    yaxis: {{ title: metric }},
                    margin: {{ l: 50, r: 50, t: 50, b: 100 }}
                }};

                Plotly.newPlot('forecastChart', [actualTrace, forecastTrace], layout, {{responsive: true}});
            }}

            // 초기 로드
            document.addEventListener('DOMContentLoaded', function() {{
                updateDashboard();
            }});
        </script>
    </body>
    </html>
    """

    return html_content







def render():
    """Flask main_app.py에서 호출하는 함수"""
    base_df, numeric_cols = load_data()

    if base_df.empty:
        return "<p>데이터를 불러올 수 없습니다.</p>"

    # 시계열 데이터 생성
    df = create_time_series_data(base_df, numeric_cols)

    return create_time_series_charts(df, numeric_cols)