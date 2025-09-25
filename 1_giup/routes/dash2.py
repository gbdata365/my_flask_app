import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json
import numpy as np
import random

class NumpyEncoder(json.JSONEncoder):
    """JSON encoder for numpy data types"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        elif hasattr(obj, 'item'):  # numpy scalar
            return obj.item()
        return super(NumpyEncoder, self).default(obj)

def convert_to_native_types(data):
    """Recursively convert pandas/numpy types to Python native types"""
    if isinstance(data, dict):
        return {key: convert_to_native_types(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_to_native_types(item) for item in data]
    elif isinstance(data, (np.integer, np.int64, np.int32)):
        return int(data)
    elif isinstance(data, (np.floating, np.float64, np.float32)):
        return float(data)
    elif isinstance(data, np.ndarray):
        return data.tolist()
    elif isinstance(data, pd.Series):
        return data.tolist()
    elif hasattr(data, 'item'):  # numpy scalar
        return data.item()
    else:
        return data

def load_data():
    """3개년 모의 데이터 로드 및 통합 (경상북도 지역 특화)"""
    try:
        # 3개년 집계표 파일 경로 설정
        data_path = Path(__file__).parent.parent / 'data'
        files = [
            '집계표_202212.xlsx',  # 2022년 12월
            '집계표_202312.xlsx',  # 2023년 12월
            '집계표_202412.xlsx'   # 2024년 12월
        ]

        # 각 파일 로드 및 통합
        all_data = []

        for file_name in files:
            file_path = data_path / file_name
            if file_path.exists():
                print(f"로드 중: {file_name}")
                df = pd.read_excel(file_path)

                # 기준년월에서 년도와 월 추출
                year_month = file_name.split('_')[1].split('.')[0]  # 202212, 202312, 202412 (.xlsx 제거)
                df['년도'] = int(year_month[:4])
                df['월'] = int(year_month[4:])

                all_data.append(df)
            else:
                print(f"파일이 존재하지 않습니다: {file_name}")

        if not all_data:
            print("로드할 데이터가 없습니다.")
            return pd.DataFrame(), []

        # 모든 데이터 통합
        df = pd.concat(all_data, ignore_index=True)
        print(f"통합 데이터: {len(df)}행, {len(df.columns)}열")

        # 결측값 제거
        df = df.dropna(subset=['시도', '시군구'])

        # 숫자형 컬럼들 정의 (3개년 집계표 구조에 맞게)
        numeric_cols = [
            '기업체수', '임시및일용근로자수', '상용근로자수', '매출액',
            '근로자수', '총종사자수', '평균종사자수', '등록일자수',
            '개업일자수', '폐업일자수'
        ]

        # 숫자형 컬럼들 전처리 (문자열이나 특수문자 처리)
        for col in numeric_cols:
            if col in df.columns:
                if df[col].dtype == 'object':
                    # 쉼표, 특수문자 제거하고 숫자로 변환
                    df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace(',', '').str.replace('*', '1'),
                        errors='coerce'
                    )
                df[col] = df[col].fillna(0)  # NaN을 0으로 대체

        # 실제 존재하는 숫자형 컬럼만 반환
        numeric_cols = [col for col in numeric_cols if col in df.columns]

        print(f"사용 가능한 숫자형 컬럼: {numeric_cols}")
        print(f"시도별 데이터 수: {df['시도'].value_counts().head()}")

        return df, numeric_cols

    except Exception as e:
        print(f"데이터 로드 중 오류: {e}")
        return pd.DataFrame(), []

def get_gyeongbuk_cities():
    """경상북도 시군 목록 반환"""
    gyeongbuk_cities = [
        '포항시', '경주시', '김천시', '안동시', '구미시', '영주시', '영천시', '상주시',
        '문경시', '경산시', '의성군', '청송군', '영양군', '영덕군', '청도군',
        '고령군', '성주군', '칠곡군', '예천군', '봉화군', '울진군', '울릉군'
    ]
    return gyeongbuk_cities

def create_sample_gyeongbuk_data(base_df, numeric_cols):
    """경상북도 샘플 데이터 생성"""
    gyeongbuk_cities = get_gyeongbuk_cities()

    # 샘플 데이터 생성
    sample_data = []
    for city in gyeongbuk_cities[:15]:  # 상위 15개 시군 사용
        row = {
            '시도': '경상북도',
            '시군구': city,
            '년도': 2024,
            '분기': 3
        }

        # 숫자형 컬럼들에 대해 랜덤 값 생성
        for col in numeric_cols:
            if col in base_df.columns:
                base_values = base_df[col].dropna()
                if len(base_values) > 0:
                    # 기존 데이터의 평균과 표준편차를 기반으로 랜덤 값 생성
                    mean_val = base_values.mean()
                    std_val = base_values.std()
                    random_val = max(0, np.random.normal(mean_val, std_val * 0.5))
                    row[col] = random_val
                else:
                    row[col] = random.randint(10, 1000)

        sample_data.append(row)

    return pd.DataFrame(sample_data)

def create_gyeongbuk_charts(df, numeric_cols):
    """경상북도 시군별 3개년 시계열 차트 생성"""
    if df.empty or not numeric_cols:
        return "<p>데이터를 불러올 수 없습니다.</p>"

    # 경상북도 데이터 필터링
    gyeongbuk_df = df[df['시도'] == '경상북도'].copy()

    if len(gyeongbuk_df) == 0:
        # 샘플 데이터 생성 (모의 데이터가 없는 경우)
        gyeongbuk_df = create_sample_gyeongbuk_data(df, numeric_cols)

    # 기본 분석 지표 선택
    selected_metric = numeric_cols[0]

    # 사용자 친화적 지표명 매핑
    metric_display_names = {
        '기업체수': '기업체수',
        '임시및일용근로자수': '임시·일용근로자수',
        '상용근로자수': '상용근로자수',
        '매출액': '매출액',
        '근로자수': '근로자수',
        '총종사자수': '총종사자수',
        '평균종사자수': '평균종사자수',
        '등록일자수': '등록일자수',
        '개업일자수': '개업일자수',
        '폐업일자수': '폐업일자수'
    }

    # 년도별 데이터 확인
    available_years = sorted(gyeongbuk_df['년도'].unique())

    # 최신 년도 기준 시군구별 집계
    latest_year = max(available_years) if available_years else 2024
    latest_gyeongbuk = gyeongbuk_df[gyeongbuk_df['년도'] == latest_year]

    # 시군구별 집계 (최신 년도 기준)
    sigungu_summary = latest_gyeongbuk.groupby('시군구').agg({
        selected_metric: 'sum'
    }).reset_index()
    sigungu_summary = sigungu_summary.sort_values(selected_metric, ascending=False)

    # 3개년 성장률 계산
    growth_data = {}
    if len(available_years) >= 2:
        first_year = min(available_years)
        last_year = max(available_years)

        first_year_data = gyeongbuk_df[gyeongbuk_df['년도'] == first_year].groupby('시군구')[selected_metric].sum()
        last_year_data = gyeongbuk_df[gyeongbuk_df['년도'] == last_year].groupby('시군구')[selected_metric].sum()

        for city in first_year_data.index:
            if city in last_year_data.index and first_year_data[city] > 0:
                growth_rate = ((last_year_data[city] - first_year_data[city]) / first_year_data[city]) * 100
                growth_data[city] = round(growth_rate, 1)

    # 시계열 데이터 생성 (경상북도 전체)
    timeseries_total = gyeongbuk_df.groupby('년도').agg({
        selected_metric: 'sum'
    }).reset_index()

    # JSON 직렬화를 위해 데이터타입 변환
    timeseries_total['년도'] = timeseries_total['년도'].astype(int)
    timeseries_total[selected_metric] = timeseries_total[selected_metric].astype(float)

    # 주요 시군구별 시계열 데이터 (상위 5개)
    top_cities = sigungu_summary.head(5)['시군구'].tolist()
    timeseries_by_city = {}

    for city in top_cities:
        city_data = gyeongbuk_df[gyeongbuk_df['시군구'] == city].groupby('년도').agg({
            selected_metric: 'sum'
        }).reset_index()
        timeseries_by_city[city] = {
            'years': [int(x) for x in city_data['년도'].tolist()],
            'values': [float(x) for x in city_data[selected_metric].tolist()]
        }

    # 요약된 원시 데이터 생성 (DataFrame 전체 대신 필요한 컬럼만)
    summary_raw_data = []
    for _, row in gyeongbuk_df.iterrows():
        row_data = {
            '년도': int(row['년도']),
            '시도': str(row['시도']),
            '시군구': str(row['시군구'])
        }
        # 모든 숫자형 컬럼 추가
        for col in numeric_cols:
            row_data[col] = float(row[col])
        summary_raw_data.append(row_data)

    # 시계열 총합 데이터 변환
    timeseries_total_data = [{
        '년도': int(row['년도']),
        selected_metric: float(row[selected_metric])
    } for _, row in timeseries_total.iterrows()]

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🏛️ 경상북도 3개년 시계열 기업통계 대시보드</title>
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
            .metric-card.growth-positive {{
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            }}
            .metric-card.growth-negative {{
                background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
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
            .insight-card {{
                background: linear-gradient(135deg, #F24822 0%, #ff6b4a 100%);
                color: white;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                margin: 10px 0;
            }}
            .timeseries-chart {{
                height: 450px;
            }}
            .growth-indicator {{
                font-size: 0.9em;
                margin-top: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="main-container">
                <h1 class="text-center mb-4" style="color: #011C40;">
                    🏛️ 경상북도 3개년 시계열 기업통계 대시보드 ({min(available_years) if available_years else 2022}-{max(available_years) if available_years else 2024})
                </h1>

                <div class="filter-panel">
                    <h5>📊 분석 옵션</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <label class="form-label">분석 지표:</label>
                            <select id="metricSelect" class="form-select" onchange="updateDashboard()">
    """

    # 분석 지표 옵션 추가 (사용자 친화적 이름으로)
    for col in numeric_cols:
        display_name = metric_display_names.get(col, col)
        selected = "selected" if col == selected_metric else ""
        html_content += f'<option value="{col}" {selected}>{display_name}</option>'

    html_content += f"""
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">년도 선택:</label>
                            <select id="yearSelect" class="form-select" onchange="updateDashboard()">
                                <option value="전체" selected>전체 (시계열)</option>
    """

    # 년도 옵션 추가
    for year in available_years:
        html_content += f'<option value="{year}">{year}년</option>'

    html_content += f"""
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">상위 시군구 개수:</label>
                            <select id="topNSelect" class="form-select" onchange="updateDashboard()">
                                <option value="10" selected>상위 10개</option>
                                <option value="15">상위 15개</option>
                                <option value="{len(sigungu_summary)}">전체</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- 메트릭 카드들 -->
                <div class="row" id="metricCards">
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h3 id="totalSigungu">{len(sigungu_summary)}</h3>
                            <p>총 시군구 수</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h3 id="totalCompanies">{len(latest_gyeongbuk):,}</h3>
                            <p>총 기업 수 ({latest_year}년)</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h3 id="totalMetric">{latest_gyeongbuk[selected_metric].sum():,.0f}</h3>
                            <p>총 {metric_display_names.get(selected_metric, selected_metric)} ({latest_year}년)</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card" id="growthCard">
                            <h3 id="overallGrowthRate">+5.0%</h3>
                            <p>경북 전체 3년간 성장률</p>
                        </div>
                    </div>
                </div>

                <!-- 핵심 분석 내용 -->
                <div class="chart-container">
                    <h5 style="color: #011C40; margin-bottom: 20px;">🏛️ 경상북도 핵심 분석 결과</h5>
                    <div id="keyInsights" style="background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #F24822;">
                        <div id="insight1" style="margin-bottom: 10px; font-size: 16px; color: #011C40;">
                            <strong>📈 경북 성장 동향:</strong> 데이터 로딩 중...
                        </div>
                        <div id="insight2" style="margin-bottom: 10px; font-size: 16px; color: #011C40;">
                            <strong>🏆 시군구 순위:</strong> 분석을 준비하고 있습니다...
                        </div>
                        <div id="insight3" style="font-size: 16px; color: #011C40;">
                            <strong>📊 지역 특성:</strong> 잠시만 기다려주세요...
                        </div>
                    </div>
                </div>

                <!-- 시계열 차트 영역 -->
                <div class="chart-container">
                    <div id="timeseriesChart" class="timeseries-chart"></div>
                </div>

                <!-- 지역별 차트 영역 -->
                <div class="row">
                    <div class="col-md-6">
                        <div class="chart-container">
                            <div id="barChart" style="height: 500px;"></div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-container">
                            <div id="pieChart" style="height: 500px;"></div>
                        </div>
                    </div>
                </div>

                <!-- 트리맵 차트 -->
                <div class="chart-container">
                    <div id="treemapChart" style="height: 400px;"></div>
                </div>

                <!-- 분포 분석 -->
                <div class="row">
                    <div class="col-md-6">
                        <div class="chart-container">
                            <div id="boxChart" style="height: 400px;"></div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-container">
                            <div id="histChart" style="height: 400px;"></div>
                        </div>
                    </div>
                </div>

                <!-- 상세 테이블 -->
                <div class="chart-container">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>📊 기초 통계량</h5>
                            <table class="table table-sm" id="statsTable">
                                <tbody id="statsBody"></tbody>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <h5>🏆 순위별 현황</h5>
                            <div class="table-responsive" style="max-height: 300px;">
                                <table class="table table-striped table-sm">
                                    <thead class="table-dark">
                                        <tr>
                                            <th>순위</th>
                                            <th>시군구</th>
                                            <th id="rankValueHeader">{selected_metric}</th>
                                        </tr>
                                    </thead>
                                    <tbody id="rankTableBody">
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 인사이트 카드 -->
                <div class="row" id="insightCards">
                    <div class="col-md-4">
                        <div class="insight-card">
                            <h6>최고</h6>
                            <h4 id="topCity">{sigungu_summary.iloc[0]['시군구']}</h4>
                            <p id="topValue">{sigungu_summary.iloc[0][selected_metric]:,.0f}</p>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="insight-card">
                            <h6>평균</h6>
                            <h4 id="avgValue">{sigungu_summary[selected_metric].mean():,.0f}</h4>
                            <p>전체 평균</p>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="insight-card">
                            <h6>최저</h6>
                            <h4 id="bottomCity">{sigungu_summary.iloc[-1]['시군구']}</h4>
                            <p id="bottomValue">{sigungu_summary.iloc[-1][selected_metric]:,.0f}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // 3개년 경상북도 시계열 데이터 (모든 데이터를 Python 네이티브 타입으로 변환)
            const rawData = {json.dumps(convert_to_native_types(summary_raw_data))};
            const numericCols = {json.dumps(convert_to_native_types(numeric_cols))};
            const metricDisplayNames = {json.dumps(convert_to_native_types(metric_display_names))};
            const availableYears = {json.dumps(convert_to_native_types(available_years))};
            const timeseriesTotal = {json.dumps(convert_to_native_types(timeseries_total_data))};
            const timeseriesByCity = {json.dumps(convert_to_native_types(timeseries_by_city))};
            const growthData = {json.dumps(convert_to_native_types(growth_data))};

            function updateDashboard() {{
                const selectedMetric = document.getElementById('metricSelect').value;
                const selectedYear = document.getElementById('yearSelect').value;
                const topN = parseInt(document.getElementById('topNSelect').value);

                // 년도별 데이터 필터링
                let filteredData = rawData;
                if (selectedYear !== '전체') {{
                    const year = parseInt(selectedYear);
                    filteredData = rawData.filter(row => row['년도'] === year);
                }}

                // 시군구별 데이터 계산
                const sigunguSums = {{}};
                filteredData.forEach(row => {{
                    if (!sigunguSums[row['시군구']]) sigunguSums[row['시군구']] = 0;
                    sigunguSums[row['시군구']] += row[selectedMetric] || 0;
                }});

                const sorted = Object.entries(sigunguSums)
                    .sort((a, b) => b[1] - a[1])
                    .filter(([_, value]) => value > 0);

                const topData = sorted.slice(0, topN);
                const names = topData.map(([name, _]) => name);
                const values = topData.map(([_, value]) => value);
                const allValues = sorted.map(([_, value]) => value);

                // 핵심 분석 내용 업데이트
                updateKeyInsights(selectedMetric, selectedYear, topN, sorted);

                // 시계열 차트 업데이트 (항상 표시)
                updateTimeseriesChart(selectedMetric);

                // 메트릭 카드 업데이트
                updateMetricCards(selectedMetric, selectedYear, allValues);

                // 지역별 차트 업데이트
                updateRegionalCharts(names, values, selectedMetric, topN, selectedYear);

                // 테이블 업데이트
                updateTables(sorted, selectedMetric, allValues);

                // 인사이트 카드 업데이트
                updateInsightCards(sorted, selectedMetric);
            }}

            function updateTimeseriesChart(selectedMetric) {{
                // 경상북도 전체 시계열 추이
                const totalYears = timeseriesTotal.map(item => item['년도']);
                const totalValues = timeseriesTotal.map(item => item[selectedMetric]);

                const totalTrace = {{
                    x: totalYears,
                    y: totalValues,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: '경상북도 전체',
                    line: {{
                        color: '#1243A6',
                        width: 4
                    }},
                    marker: {{
                        color: '#F24822',
                        size: 10
                    }}
                }};

                // 상위 시군구별 시계열 (상위 3개만)
                const traces = [totalTrace];
                const colors = ['#20c997', '#fd7e14', '#6f42c1'];

                Object.entries(timeseriesByCity).slice(0, 3).forEach(([city, data], index) => {{
                    traces.push({{
                        x: data.years,
                        y: data.values,
                        type: 'scatter',
                        mode: 'lines+markers',
                        name: city,
                        line: {{
                            color: colors[index],
                            width: 2
                        }},
                        marker: {{
                            size: 6
                        }}
                    }});
                }});

                const timeseriesLayout = {{
                    title: `경상북도 ${{metricDisplayNames[selectedMetric] || selectedMetric}} 시계열 추이`,
                    xaxis: {{
                        title: '년도',
                        tickformat: 'd'
                    }},
                    yaxis: {{
                        title: metricDisplayNames[selectedMetric] || selectedMetric,
                        tickformat: ',.0f'
                    }},
                    margin: {{ l: 80, r: 50, t: 60, b: 80 }},
                    plot_bgcolor: '#f8f9fa',
                    paper_bgcolor: 'white',
                    legend: {{
                        x: 0,
                        y: 1,
                        bgcolor: 'rgba(255,255,255,0.8)'
                    }}
                }};

                Plotly.newPlot('timeseriesChart', traces, timeseriesLayout, {{responsive: true}});
            }}

            function updateKeyInsights(selectedMetric, selectedYear, topN, sortedData) {{
                // 경상북도 전체 성장률 계산
                let growthInfo = '';
                if (availableYears.length >= 2) {{
                    const firstYear = Math.min(...availableYears);
                    const lastYear = Math.max(...availableYears);

                    const firstYearData = rawData.filter(row => row['년도'] === firstYear);
                    const lastYearData = rawData.filter(row => row['년도'] === lastYear);

                    const firstValue = firstYearData.reduce((sum, row) => sum + (row[selectedMetric] || 0), 0);
                    const lastValue = lastYearData.reduce((sum, row) => sum + (row[selectedMetric] || 0), 0);

                    if (firstValue > 0) {{
                        const growthRate = ((lastValue - firstValue) / firstValue) * 100;
                        const trend = growthRate >= 0 ? '성장' : '감소';
                        const trendIcon = growthRate >= 0 ? '📈' : '📉';
                        growthInfo = `${{firstYear}}-${{lastYear}}년 ${{Math.abs(growthRate).toFixed(1)}}% ${{trend}} ${{trendIcon}}`;
                    }}
                }}

                // 선택된 조건에 따른 시군구 순위 정보
                let rankingInfo = '';
                let characteristicsInfo = '';

                if (sortedData.length > 0) {{
                    const topCity = sortedData[0];
                    const topValue = topCity[1];
                    const totalCities = sortedData.length;

                    if (selectedYear === '전체') {{
                        rankingInfo = `시계열 기준 1위: ${{topCity[0]}} (${{topValue.toLocaleString()}})`;

                        // 상위 3개 도시의 격차 분석
                        if (sortedData.length >= 3) {{
                            const secondValue = sortedData[1][1];
                            const gap = ((topValue - secondValue) / secondValue * 100).toFixed(1);
                            characteristicsInfo = `1-2위 격차 ${{gap}}%, 총 ${{totalCities}}개 시군구 분석 중`;
                        }}
                    }} else {{
                        const year = parseInt(selectedYear);
                        rankingInfo = `${{year}}년 1위: ${{topCity[0]}} (${{topValue.toLocaleString()}})`;

                        // 해당 연도의 상위 지역 특성
                        if (sortedData.length >= 2) {{
                            const avgValue = sortedData.reduce((sum, [_, val]) => sum + val, 0) / sortedData.length;
                            const topRatio = (topValue / avgValue).toFixed(1);
                            characteristicsInfo = `평균 대비 ${{topRatio}}배 높음, 상위 ${{topN}}개 지역 표시`;
                        }}
                    }}
                }}

                // 지역별 성장률 정보 (상위 시군구 기준)
                let topGrowthCity = '';
                if (growthData && Object.keys(growthData).length > 0) {{
                    const sortedGrowth = Object.entries(growthData).sort((a, b) => b[1] - a[1]);
                    if (sortedGrowth.length > 0) {{
                        const topGrowth = sortedGrowth[0];
                        topGrowthCity = `성장률 1위: ${{topGrowth[0]}} (+${{topGrowth[1]}}%)`;
                    }}
                }}

                // 분석 결과 업데이트
                const metricName = metricDisplayNames[selectedMetric] || selectedMetric;
                const yearText = selectedYear === '전체' ? '3개년 종합' : selectedYear + '년';

                document.getElementById('insight1').innerHTML =
                    `<strong>📈 경북 성장 동향:</strong> ${{metricName}} ${{growthInfo || '안정적 수준 유지'}}`;

                document.getElementById('insight2').innerHTML =
                    `<strong>🏆 시군구 순위:</strong> ${{rankingInfo}} (${{yearText}} 기준)`;

                document.getElementById('insight3').innerHTML =
                    `<strong>📊 지역 특성:</strong> ${{characteristicsInfo || topGrowthCity || '균형적 발전 양상'}}`;
            }}

            function updateMetricCards(selectedMetric, selectedYear, allValues) {{
                const totalMetric = allValues.reduce((sum, val) => sum + val, 0);

                // 년도별 필터링된 데이터 수
                let filteredData = rawData;
                if (selectedYear !== '전체') {{
                    filteredData = rawData.filter(row => row['년도'] === parseInt(selectedYear));
                }}

                // 경상북도 전체 성장률 계산 (3년간)
                let overallGrowthRate = 0;
                let growthClass = '';
                if (availableYears.length >= 2) {{
                    const firstYear = Math.min(...availableYears);
                    const lastYear = Math.max(...availableYears);

                    const firstYearData = rawData.filter(row => row['년도'] === firstYear);
                    const lastYearData = rawData.filter(row => row['년도'] === lastYear);

                    const firstValue = firstYearData.reduce((sum, row) => sum + (row[selectedMetric] || 0), 0);
                    const lastValue = lastYearData.reduce((sum, row) => sum + (row[selectedMetric] || 0), 0);

                    if (firstValue > 0) {{
                        overallGrowthRate = ((lastValue - firstValue) / firstValue) * 100;
                        growthClass = overallGrowthRate >= 0 ? 'growth-positive' : 'growth-negative';
                    }}
                }}

                // 카드 업데이트
                const uniqueCities = [...new Set(rawData.map(row => row['시군구']))];
                document.getElementById('totalSigungu').textContent = uniqueCities.length;
                document.getElementById('totalCompanies').textContent = filteredData.length.toLocaleString();
                document.getElementById('totalMetric').textContent = totalMetric.toLocaleString();
                document.getElementById('overallGrowthRate').textContent = (overallGrowthRate >= 0 ? '+' : '') + overallGrowthRate.toFixed(1) + '%';

                // 성장률 카드 색상 변경
                const growthCard = document.getElementById('growthCard');
                growthCard.className = 'metric-card ' + growthClass;
            }}

            function updateRegionalCharts(names, values, metric, topN, selectedYear) {{
                // 가로 막대 차트
                const barTrace = {{
                    x: values,
                    y: names,
                    type: 'bar',
                    orientation: 'h',
                    marker: {{
                        color: values,
                        colorscale: 'RdYlBu_r'
                    }}
                }};

                const barLayout = {{
                    title: `시군구별 ${{metric}} (상위 ${{topN}}개)`,
                    xaxis: {{ title: metric }},
                    yaxis: {{ title: '시군구', categoryorder: 'total ascending' }},
                    margin: {{ l: 120, r: 50, t: 50, b: 50 }}
                }};

                Plotly.newPlot('barChart', [barTrace], barLayout, {{responsive: true}});

                // 도넛 차트
                const pieTrace = {{
                    labels: names,
                    values: values,
                    type: 'pie',
                    hole: 0.4
                }};

                const pieLayout = {{
                    title: `시군구별 ${{metric}} 비중 (상위 ${{topN}}개)`,
                    margin: {{ l: 50, r: 50, t: 50, b: 50 }}
                }};

                Plotly.newPlot('pieChart', [pieTrace], pieLayout, {{responsive: true}});

                // 트리맵 차트
                const treemapTrace = {{
                    type: 'treemap',
                    labels: names,
                    values: values,
                    parents: names.map(() => ''),
                    textinfo: 'label+value',
                    marker: {{ colorscale: 'Viridis' }}
                }};

                const treemapLayout = {{
                    title: `경상북도 시군구별 ${{metric}} 트리맵`,
                    margin: {{ l: 0, r: 0, t: 50, b: 0 }}
                }};

                Plotly.newPlot('treemapChart', [treemapTrace], treemapLayout, {{responsive: true}});

                // 박스플롯
                const boxTrace = {{
                    y: values,
                    type: 'box',
                    name: metric,
                    boxpoints: 'all',
                    jitter: 0.3
                }};

                const boxLayout = {{
                    title: `${{metric}} 분포`,
                    yaxis: {{ title: metric }},
                    margin: {{ l: 50, r: 50, t: 50, b: 50 }}
                }};

                Plotly.newPlot('boxChart', [boxTrace], boxLayout, {{responsive: true}});

                // 히스토그램
                const histTrace = {{
                    x: values,
                    type: 'histogram',
                    nbinsx: 8,
                    marker: {{ color: '#1243A6', opacity: 0.7 }}
                }};

                const histLayout = {{
                    title: `${{metric}} 히스토그램`,
                    xaxis: {{ title: metric }},
                    yaxis: {{ title: '빈도' }},
                    margin: {{ l: 50, r: 50, t: 50, b: 50 }}
                }};

                Plotly.newPlot('histChart', [histTrace], histLayout, {{responsive: true}});
            }}

            function updateTables(sorted, metric, allValues) {{
                // 기초 통계량 테이블
                const mean = allValues.reduce((a, b) => a + b, 0) / allValues.length;
                const sortedValues = [...allValues].sort((a, b) => a - b);
                const median = sortedValues.length % 2 === 0
                    ? (sortedValues[sortedValues.length/2 - 1] + sortedValues[sortedValues.length/2]) / 2
                    : sortedValues[Math.floor(sortedValues.length/2)];
                const min = Math.min(...allValues);
                const max = Math.max(...allValues);
                const std = Math.sqrt(allValues.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / allValues.length);

                const statsBody = document.getElementById('statsBody');
                statsBody.innerHTML = `
                    <tr><td><strong>평균</strong></td><td>${{mean.toLocaleString(undefined, {{maximumFractionDigits: 0}})}}</td></tr>
                    <tr><td><strong>중앙값</strong></td><td>${{median.toLocaleString(undefined, {{maximumFractionDigits: 0}})}}</td></tr>
                    <tr><td><strong>최대값</strong></td><td>${{max.toLocaleString()}}</td></tr>
                    <tr><td><strong>최소값</strong></td><td>${{min.toLocaleString()}}</td></tr>
                    <tr><td><strong>표준편차</strong></td><td>${{std.toLocaleString(undefined, {{maximumFractionDigits: 0}})}}</td></tr>
                `;

                // 순위 테이블
                const rankTableBody = document.getElementById('rankTableBody');
                rankTableBody.innerHTML = '';
                document.getElementById('rankValueHeader').textContent = metric;

                sorted.slice(0, 10).forEach(([name, value], index) => {{
                    const row = rankTableBody.insertRow();
                    row.innerHTML = `
                        <td>${{index + 1}}</td>
                        <td>${{name}}</td>
                        <td>${{value.toLocaleString()}}</td>
                    `;
                }});
            }}

            function updateInsightCards(sorted, metric) {{
                const top = sorted[0];
                const bottom = sorted[sorted.length - 1];
                const avg = sorted.reduce((sum, [_, val]) => sum + val, 0) / sorted.length;

                document.getElementById('topCity').textContent = top[0];
                document.getElementById('topValue').textContent = top[1].toLocaleString();
                document.getElementById('avgValue').textContent = avg.toLocaleString(undefined, {{maximumFractionDigits: 0}});
                document.getElementById('bottomCity').textContent = bottom[0];
                document.getElementById('bottomValue').textContent = bottom[1].toLocaleString();
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
    df, numeric_cols = load_data()
    return create_gyeongbuk_charts(df, numeric_cols)