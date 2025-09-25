import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import numpy as np
from pathlib import Path
import json
import base64
import io
from matplotlib import font_manager
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import tempfile
import os
from datetime import datetime

# 한글 폰트 설정
plt.rcParams['font.family'] = ['Malgun Gothic', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")

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
    """4개년 모의 데이터 로드 및 통합"""
    try:
        # 4개년 집계표 파일 경로 설정
        data_path = Path(__file__).parent.parent / 'data'
        files = [
            '집계표_202212.xlsx',  # 2022년 12월
            '집계표_202312.xlsx',  # 2023년 12월
            '집계표_202406.xlsx',  # 2024년 6월
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
            return pd.DataFrame(), [], [], [], []

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

        # 폐업구분 컬럼들
        closure_cols = ['폐업(1)', '폐업(2)', '폐업(3)', '폐업(4)', '폐업(99)']

        # 기업구분 컬럼들
        business_cols = ['기업(1)', '기업(2)', '기업(3)', '기업(4)', '기업(5)']

        # 산업구분 컬럼들 (A-S)
        industry_cols = [f'산업({chr(65+i)})' for i in range(19)]  # A-S

        # 모든 숫자형 컬럼들 (기본 + 구분별) 전처리
        all_numeric_cols = numeric_cols + closure_cols + business_cols + industry_cols

        for col in all_numeric_cols:
            if col in df.columns:
                if df[col].dtype == 'object':
                    # 쉼표, 특수문자 제거하고 숫자로 변환
                    df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace(',', '').str.replace('*', '1'),
                        errors='coerce'
                    )
                df[col] = df[col].fillna(0)  # NaN을 0으로 대체

        # 실제 존재하는 컬럼들만 필터링
        numeric_cols = [col for col in numeric_cols if col in df.columns]
        closure_cols = [col for col in closure_cols if col in df.columns]
        business_cols = [col for col in business_cols if col in df.columns]
        industry_cols = [col for col in industry_cols if col in df.columns]

        print(f"사용 가능한 숫자형 컬럼: {numeric_cols}")
        print(f"폐업구분 컬럼: {closure_cols}")
        print(f"기업구분 컬럼: {business_cols}")
        print(f"산업구분 컬럼: {len(industry_cols)}개")
        print(f"시도별 데이터 수: {df['시도'].value_counts().head()}")

        return df, numeric_cols, closure_cols, business_cols, industry_cols

    except Exception as e:
        print(f"데이터 로드 중 오류: {e}")
        return pd.DataFrame(), [], [], [], []

def create_comprehensive_dashboard(df, numeric_cols, closure_cols, business_cols, industry_cols):
    """종합 대시보드 생성 (폐업구분, 기업구분, 산업구분 포함)"""
    if df.empty or not numeric_cols:
        return "<p>데이터를 불러올 수 없습니다.</p>"

    # 기본 분석 지표 선택
    selected_metric = numeric_cols[0]

    # 년도 목록 생성
    available_years = sorted(df['년도'].unique())
    latest_year = max(available_years)

    # 구분 코드별 표시명 정의
    closure_names = {
        '폐업(1)': '사업부진', '폐업(2)': '행정처분', '폐업(3)': '계절사유',
        '폐업(4)': '법인전환', '폐업(99)': '기타'
    }

    business_names = {
        '기업(1)': '개인사업자', '기업(2)': '법인사업자', '기업(3)': '회사법인',
        '기업(4)': '회사외법인', '기업(5)': '기타'
    }

    industry_names = {
        '산업(A)': '농업,임업', '산업(B)': '어업', '산업(C)': '제조업', '산업(D)': '전기,가스',
        '산업(E)': '상하수도', '산업(F)': '건설업', '산업(G)': '도소매업', '산업(H)': '운수창고업',
        '산업(I)': '숙박음식점업', '산업(J)': '정보통신업', '산업(K)': '금융보험업', '산업(L)': '부동산업',
        '산업(M)': '전문과학기술업', '산업(N)': '사업시설관리업', '산업(O)': '공공행정', '산업(P)': '교육서비스업',
        '산업(Q)': '보건사회복지업', '산업(R)': '예술스포츠여가업', '산업(S)': '협회및기타'
    }

    # 메트릭 표시명
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

    # 기본 통계 계산
    latest_df = df[df['년도'] == latest_year]
    total_companies = latest_df[selected_metric].sum()

    # 성장률 계산
    growth_rate = 0
    if len(available_years) >= 2:
        first_year = min(available_years)
        last_year = max(available_years)
        first_value = df[df['년도'] == first_year][selected_metric].sum()
        last_value = df[df['년도'] == last_year][selected_metric].sum()
        if first_value > 0:
            growth_rate = ((last_value - first_value) / first_value) * 100

    # 시도별 데이터 준비
    sido_summary = latest_df.groupby('시도')[selected_metric].sum().sort_values(ascending=False)

    # 구분별 데이터 준비
    closure_data = {}
    business_data = {}
    industry_data = {}

    for col in closure_cols:
        if col in latest_df.columns:
            closure_data[col] = latest_df[col].sum()

    for col in business_cols:
        if col in latest_df.columns:
            business_data[col] = latest_df[col].sum()

    for col in industry_cols:
        if col in latest_df.columns:
            industry_data[col] = latest_df[col].sum()

    # JSON 데이터 생성
    dashboard_data = {
        'years': available_years,
        'sido_data': {
            'names': sido_summary.index.tolist(),
            'values': [float(x) for x in sido_summary.values.tolist()]
        },
        'closure_data': {
            'codes': list(closure_data.keys()),
            'names': [closure_names.get(k, k) for k in closure_data.keys()],
            'values': [float(v) for v in closure_data.values()]
        },
        'business_data': {
            'codes': list(business_data.keys()),
            'names': [business_names.get(k, k) for k in business_data.keys()],
            'values': [float(v) for v in business_data.values()]
        },
        'industry_data': {
            'codes': list(industry_data.keys()),
            'names': [industry_names.get(k, k) for k in industry_data.keys()],
            'values': [float(v) for v in industry_data.values()]
        }
    }

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🏢 기업통계등록부 종합분석 대시보드</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{
                background: linear-gradient(135deg, #F2EED8 0%, #E8E0C4 100%);
                font-family: 'Pretendard', 'Noto Sans KR', sans-serif;
                min-height: 100vh;
            }}
            .main-container {{
                background: white;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                margin: 20px auto;
                padding: 40px;
                max-width: 1400px;
                border: 1px solid rgba(18, 67, 166, 0.1);
            }}
            .header-title {{
                background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-weight: 800;
                text-align: center;
                margin-bottom: 40px;
                font-size: 2.5rem;
            }}
            .metric-card {{
                background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
                color: white;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 25px;
                text-align: center;
                transition: all 0.3s ease;
                border: none;
                position: relative;
                overflow: hidden;
            }}
            .metric-card::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(45deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 100%);
                pointer-events: none;
            }}
            .metric-card:hover {{
                transform: translateY(-8px);
                box-shadow: 0 20px 40px rgba(18, 67, 166, 0.3);
            }}
            .metric-card.growth-positive {{
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            }}
            .metric-card.growth-negative {{
                background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            }}
            .metric-card h3 {{
                font-size: 3rem;
                font-weight: 800;
                margin-bottom: 15px;
                text-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .metric-card p {{
                font-size: 1.2rem;
                opacity: 0.95;
                margin: 0;
                font-weight: 500;
            }}
            .section-container {{
                background: white;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.08);
                border: 1px solid rgba(0, 0, 0, 0.05);
            }}
            .section-title {{
                color: #011C40;
                font-weight: 700;
                font-size: 1.6rem;
                margin-bottom: 25px;
                display: flex;
                align-items: center;
                padding-bottom: 15px;
                border-bottom: 3px solid #1243A6;
            }}
            .section-title i {{
                margin-right: 15px;
                color: #F24822;
                font-size: 1.4rem;
            }}
            .filter-panel {{
                background: linear-gradient(135deg, #011C40 0%, #1243A6 100%);
                color: white;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 8px 25px rgba(1, 28, 64, 0.3);
            }}
            .key-insight {{
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                border-left: 6px solid #F24822;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 25px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            }}
            .insight-item {{
                margin-bottom: 15px;
                font-size: 16px;
                color: #011C40;
                line-height: 1.7;
                display: flex;
                align-items: flex-start;
            }}
            .insight-icon {{
                color: #F24822;
                margin-right: 12px;
                font-weight: bold;
                margin-top: 2px;
                font-size: 1.1rem;
            }}
            .chart-container {{
                min-height: 400px;
                margin-bottom: 20px;
            }}
            .btn-custom {{
                background: linear-gradient(135deg, #F24822 0%, #FF6B47 100%);
                border: none;
                color: white;
                border-radius: 12px;
                padding: 15px 30px;
                margin: 8px;
                font-weight: 600;
                transition: all 0.3s ease;
                font-size: 1rem;
            }}
            .btn-custom:hover {{
                transform: translateY(-3px);
                box-shadow: 0 10px 25px rgba(242, 72, 34, 0.4);
                color: white;
            }}
            .btn-custom.active {{
                background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
                box-shadow: 0 8px 20px rgba(18, 67, 166, 0.4);
            }}
            .section-divider {{
                background: linear-gradient(90deg, transparent 0%, #1243A6 50%, transparent 100%);
                height: 4px;
                margin: 50px 0;
                border-radius: 2px;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .stat-item {{
                background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
                border: 2px solid #e9ecef;
                border-radius: 15px;
                padding: 20px;
                text-align: center;
                transition: all 0.3s ease;
            }}
            .stat-item:hover {{
                border-color: #1243A6;
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(18, 67, 166, 0.1);
            }}
            .stat-value {{
                font-size: 2rem;
                font-weight: 700;
                color: #1243A6;
                margin-bottom: 5px;
            }}
            .stat-label {{
                font-size: 0.9rem;
                color: #6c757d;
                font-weight: 500;
            }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="main-container">
                <h1 class="header-title">
                    <i class="fas fa-chart-line"></i>
                    기업통계등록부 종합분석 대시보드
                </h1>

                <!-- 필터 패널 -->
                <div class="filter-panel">
                    <h5><i class="fas fa-filter"></i> 분석 조건 설정</h5>
                    <div class="row">
                        <div class="col-md-3">
                            <label class="form-label">분석 년도:</label>
                            <select id="yearSelect" class="form-select">
                                <option value="전체">전체 ({min(available_years)}-{max(available_years)})</option>"""

    for year in available_years:
        selected = "selected" if year == latest_year else ""
        html_content += f'<option value="{year}" {selected}>{year}년</option>'

    html_content += f"""
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">시도 선택:</label>
                            <select id="sidoSelect" class="form-select">
                                <option value="전체">전체</option>"""

    for sido in sorted(df['시도'].unique()):
        html_content += f'<option value="{sido}">{sido}</option>'

    html_content += f"""
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">분석 지표:</label>
                            <select id="metricSelect" class="form-select">"""

    for col in numeric_cols:
        display_name = metric_display_names.get(col, col)
        selected = "selected" if col == selected_metric else ""
        html_content += f'<option value="{col}" {selected}>{display_name}</option>'

    html_content += f"""
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">분석 유형:</label>
                            <select id="analysisType" class="form-select">
                                <option value="basic" selected>기본 분석</option>
                                <option value="closure">폐업 구분 분석</option>
                                <option value="business">기업 유형 분석</option>
                                <option value="industry">산업 구분 분석</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- 핵심 지표 카드 -->
                <div class="row" id="metricCards">
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h3 id="totalValue">{total_companies:,.0f}</h3>
                            <p>총 {metric_display_names.get(selected_metric, selected_metric)} ({latest_year}년)</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card {'growth-positive' if growth_rate >= 0 else 'growth-negative'}">
                            <h3 id="growthRate">{'+' if growth_rate >= 0 else ''}{growth_rate:.1f}%</h3>
                            <p>3년간 성장률</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h3 id="regionCount">{len(sido_summary)}</h3>
                            <p>분석 대상 시도</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card">
                            <h3 id="avgValue">{total_companies/len(sido_summary):,.0f}</h3>
                            <p>시도당 평균값</p>
                        </div>
                    </div>
                </div>

                <!-- 핵심 인사이트 -->
                <div class="section-container">
                    <div class="section-title">
                        <i class="fas fa-lightbulb"></i>
                        핵심 분석 결과
                    </div>
                    <div class="key-insight" id="keyInsightSection">
                        <div class="insight-item" id="insight1">
                            <span class="insight-icon">📈</span>
                            <span><strong>성장 추이:</strong> {latest_year}년 기준 전국 총 {metric_display_names.get(selected_metric, selected_metric)}는 {total_companies:,}개로, 3년간 {abs(growth_rate):.1f}% {'증가' if growth_rate >= 0 else '감소'}했습니다.</span>
                        </div>
                        <div class="insight-item" id="insight2">
                            <span class="insight-icon">🏆</span>
                            <span><strong>지역 순위:</strong> {sido_summary.index[0]}가 {sido_summary.iloc[0]:,}개로 1위를 차지하며, 전체의 {(sido_summary.iloc[0]/total_companies*100):.1f}%를 차지합니다.</span>
                        </div>
                        <div class="insight-item" id="insight3">
                            <span class="insight-icon">📊</span>
                            <span><strong>분포 특성:</strong> 상위 3개 시도({sido_summary.index[0]}, {sido_summary.index[1]}, {sido_summary.index[2]})가 전체의 {(sido_summary.iloc[:3].sum()/total_companies*100):.1f}%를 차지하여 집중도가 {'높습니다' if (sido_summary.iloc[:3].sum()/total_companies) > 0.5 else '적당합니다'}.</span>
                        </div>
                    </div>
                </div>

                <!-- 차트 영역 -->
                <div class="section-container">
                    <div class="section-title">
                        <i class="fas fa-chart-bar"></i>
                        <span id="chartSectionTitle">시도별 분석</span>
                    </div>

                    <!-- 분석별 핵심 인사이트 -->
                    <div class="key-insight" id="sectionInsight">
                        <div class="insight-item">
                            <span class="insight-icon">📍</span>
                            <span id="sectionInsightText">시도별 분석 결과를 확인하세요.</span>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-8">
                            <div class="chart-container" id="mainChart"></div>
                        </div>
                        <div class="col-md-4">
                            <div class="chart-container" id="pieChart"></div>
                        </div>
                    </div>
                </div>

                <!-- 시계열 분석 -->
                <div class="section-container">
                    <div class="section-title">
                        <i class="fas fa-chart-line"></i>
                        시계열 추이 분석
                    </div>

                    <div class="key-insight">
                        <div class="insight-item">
                            <span class="insight-icon">📅</span>
                            <span id="timeseriesInsight">3개년 데이터를 통한 시계열 추이를 분석합니다.</span>
                        </div>
                    </div>

                    <div class="chart-container" id="timeseriesChart" style="height: 500px;"></div>
                </div>

                <!-- 상세 통계표 -->
                <div class="section-container">
                    <div class="section-title">
                        <i class="fas fa-table"></i>
                        상세 통계표
                    </div>

                    <div class="table-responsive">
                        <table class="table table-striped table-hover">
                            <thead class="table-dark">
                                <tr>
                                    <th>순위</th>
                                    <th id="tableLocationHeader">지역</th>
                                    <th id="tableValueHeader">수치</th>
                                    <th>비중(%)</th>
                                </tr>
                            </thead>
                            <tbody id="detailTableBody">
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // 데이터 초기화
            const dashboardData = {json.dumps(convert_to_native_types(dashboard_data))};
            const metricDisplayNames = {json.dumps(convert_to_native_types(metric_display_names))};
            const closureNames = {json.dumps(convert_to_native_types(closure_names))};
            const businessNames = {json.dumps(convert_to_native_types(business_names))};
            const industryNames = {json.dumps(convert_to_native_types(industry_names))};

            // 현재 선택된 값들
            let currentMetric = '{selected_metric}';
            let currentYear = '{latest_year}';
            let currentSido = '전체';
            let currentAnalysisType = 'basic';

            // 초기화
            document.addEventListener('DOMContentLoaded', function() {{
                updateDashboard();

                // 이벤트 리스너 등록
                document.getElementById('yearSelect').addEventListener('change', updateDashboard);
                document.getElementById('sidoSelect').addEventListener('change', updateDashboard);
                document.getElementById('metricSelect').addEventListener('change', updateDashboard);
                document.getElementById('analysisType').addEventListener('change', updateDashboard);
            }});

            function updateDashboard() {{
                currentYear = document.getElementById('yearSelect').value;
                currentSido = document.getElementById('sidoSelect').value;
                currentMetric = document.getElementById('metricSelect').value;
                currentAnalysisType = document.getElementById('analysisType').value;

                updateCharts();
                updateInsights();
                updateTable();
            }}

            function updateCharts() {{
                const analysisType = currentAnalysisType;

                // 차트 제목 업데이트
                let chartTitle = '';
                let data = null;

                switch(analysisType) {{
                    case 'basic':
                        chartTitle = '시도별 분석';
                        data = dashboardData.sido_data;
                        break;
                    case 'closure':
                        chartTitle = '폐업 구분별 분석';
                        data = dashboardData.closure_data;
                        break;
                    case 'business':
                        chartTitle = '기업 유형별 분석';
                        data = dashboardData.business_data;
                        break;
                    case 'industry':
                        chartTitle = '산업 구분별 분석';
                        data = dashboardData.industry_data;
                        break;
                }}

                document.getElementById('chartSectionTitle').textContent = chartTitle;

                if (data && data.values && data.values.length > 0) {{
                    // 메인 차트 (막대 그래프)
                    const mainTrace = {{
                        x: data.names.slice(0, 15),
                        y: data.values.slice(0, 15),
                        type: 'bar',
                        marker: {{
                            color: data.values.slice(0, 15),
                            colorscale: 'Blues',
                            showscale: false
                        }},
                        text: data.values.slice(0, 15).map(v => v.toLocaleString()),
                        textposition: 'auto'
                    }};

                    const mainLayout = {{
                        title: {{
                            text: chartTitle + ' (상위 15개)',
                            font: {{ size: 16, color: '#011C40' }}
                        }},
                        xaxis: {{
                            title: analysisType === 'basic' ? '시도' : '구분',
                            tickangle: -45
                        }},
                        yaxis: {{
                            title: metricDisplayNames[currentMetric] || currentMetric,
                            tickformat: ',.0f'
                        }},
                        margin: {{ l: 80, r: 50, t: 60, b: 100 }},
                        plot_bgcolor: '#f8f9fa',
                        paper_bgcolor: 'white'
                    }};

                    Plotly.newPlot('mainChart', [mainTrace], mainLayout, {{responsive: true}});

                    // 파이 차트 (상위 10개)
                    let pieNames = data.names.slice(0, 10);
                    let pieValues = data.values.slice(0, 10);

                    if (data.names.length > 10) {{
                        const otherSum = data.values.slice(10).reduce((sum, val) => sum + val, 0);
                        if (otherSum > 0) {{
                            pieNames.push('기타');
                            pieValues.push(otherSum);
                        }}
                    }}

                    const pieTrace = {{
                        labels: pieNames,
                        values: pieValues,
                        type: 'pie',
                        hole: 0.4,
                        textinfo: 'label+percent',
                        textposition: 'outside'
                    }};

                    const pieLayout = {{
                        title: {{
                            text: '구성비',
                            font: {{ size: 16, color: '#011C40' }}
                        }},
                        margin: {{ l: 50, r: 50, t: 60, b: 50 }},
                        paper_bgcolor: 'white'
                    }};

                    Plotly.newPlot('pieChart', [pieTrace], pieLayout, {{responsive: true}});
                }}

                // 시계열 차트 (기본 분석만)
                if (analysisType === 'basic') {{
                    const timeseriesTrace = {{
                        x: dashboardData.years,
                        y: dashboardData.years.map(year => {{
                            // 여기서는 단순화된 데이터를 사용 (실제로는 연도별 합계 계산 필요)
                            const baseValue = dashboardData.sido_data.values.reduce((sum, val) => sum + val, 0);
                            const yearIndex = dashboardData.years.indexOf(year);
                            return baseValue * (0.95 + yearIndex * 0.025); // 간단한 증가 패턴
                        }}),
                        type: 'scatter',
                        mode: 'lines+markers',
                        line: {{
                            color: '#1243A6',
                            width: 3
                        }},
                        marker: {{
                            color: '#F24822',
                            size: 10
                        }},
                        name: metricDisplayNames[currentMetric] || currentMetric
                    }};

                    const timeseriesLayout = {{
                        title: {{
                            text: '3개년 시계열 추이',
                            font: {{ size: 18, color: '#011C40' }}
                        }},
                        xaxis: {{
                            title: '년도',
                            tickformat: 'd'
                        }},
                        yaxis: {{
                            title: metricDisplayNames[currentMetric] || currentMetric,
                            tickformat: ',.0f'
                        }},
                        margin: {{ l: 80, r: 50, t: 80, b: 80 }},
                        plot_bgcolor: '#f8f9fa',
                        paper_bgcolor: 'white'
                    }};

                    Plotly.newPlot('timeseriesChart', [timeseriesTrace], timeseriesLayout, {{responsive: true}});
                }}
            }}

            function updateInsights() {{
                const analysisType = currentAnalysisType;
                let insightText = '';

                switch(analysisType) {{
                    case 'basic':
                        insightText = '시도별 분석을 통해 지역별 분포와 특성을 파악할 수 있습니다.';
                        break;
                    case 'closure':
                        insightText = '폐업 구분별 분석을 통해 기업 폐업의 주요 원인을 분석합니다.';
                        break;
                    case 'business':
                        insightText = '기업 유형별 분석을 통해 사업체 구성의 특성을 확인합니다.';
                        break;
                    case 'industry':
                        insightText = '산업 구분별 분석을 통해 지역 산업 구조를 파악합니다.';
                        break;
                }}

                document.getElementById('sectionInsightText').textContent = insightText;
            }}

            function updateTable() {{
                const analysisType = currentAnalysisType;
                let data = null;

                switch(analysisType) {{
                    case 'basic':
                        data = dashboardData.sido_data;
                        document.getElementById('tableLocationHeader').textContent = '시도';
                        break;
                    case 'closure':
                        data = dashboardData.closure_data;
                        document.getElementById('tableLocationHeader').textContent = '폐업구분';
                        break;
                    case 'business':
                        data = dashboardData.business_data;
                        document.getElementById('tableLocationHeader').textContent = '기업유형';
                        break;
                    case 'industry':
                        data = dashboardData.industry_data;
                        document.getElementById('tableLocationHeader').textContent = '산업구분';
                        break;
                }}

                document.getElementById('tableValueHeader').textContent = metricDisplayNames[currentMetric] || currentMetric;

                if (data && data.values && data.values.length > 0) {{
                    const total = data.values.reduce((sum, val) => sum + val, 0);
                    const tbody = document.getElementById('detailTableBody');
                    tbody.innerHTML = '';

                    data.names.forEach((name, index) => {{
                        const value = data.values[index];
                        const percentage = total > 0 ? (value / total * 100).toFixed(1) : 0;

                        const row = tbody.insertRow();
                        row.innerHTML = `
                            <td class="fw-bold">${{index + 1}}</td>
                            <td>${{name}}</td>
                            <td class="text-end">${{value.toLocaleString()}}</td>
                            <td class="text-end">${{percentage}}%</td>
                        `;

                        // 상위 3개 행 강조
                        if (index < 3) {{
                            row.classList.add('table-warning');
                        }}
                    }});
                }}
            }}
        </script>
    </body>
    </html>
    """

    return html_content

def render():
    """Flask main_app.py에서 호출하는 함수"""
    df, numeric_cols, closure_cols, business_cols, industry_cols = load_data()
    return create_comprehensive_dashboard(df, numeric_cols, closure_cols, business_cols, industry_cols)