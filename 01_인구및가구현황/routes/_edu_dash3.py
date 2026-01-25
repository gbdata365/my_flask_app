# -*- coding: utf-8 -*-
"""
================================================================================
경북 인구·가구 진단 대시보드 (edu_dash3.py)
================================================================================

[목적]
- 경북 시군별 인구·가구 현황 진단
- 총인구, 유소년, 청년, 고령 인구 비교
- 시군별 추이 분석

[기술 스택]
- Backend: Flask (Python)
- Frontend: Tailwind CSS + Chart.js
- Database: PostgreSQL

================================================================================
"""
import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from module.db import get_db_engine
from module.menu_generator import MenuGenerator
from flask import Response

POP_BASE = Path(__file__).parent.parent


# =============================================================================
# 필터 옵션 조회
# =============================================================================

def get_filter_options():
    """필터 옵션 조회"""
    engine = get_db_engine()

    # 기준년월 목록
    ym_df = pd.read_sql("""
        SELECT DISTINCT TO_CHAR(base_ym, 'YYYYMM') as ym
        FROM cache_sigungu_indicators
        ORDER BY ym DESC
    """, engine)

    # 시도 목록
    sido_df = pd.read_sql("""
        SELECT DISTINCT sido_nm
        FROM dim_admin_area
        WHERE sido_nm IS NOT NULL
        ORDER BY sido_nm
    """, engine)

    return {
        'base_ym_list': ym_df['ym'].tolist(),
        'sido_list': sido_df['sido_nm'].tolist(),
    }


# =============================================================================
# 데이터 조회 함수
# =============================================================================

def get_sigungu_summary(base_ym, sido='경상북도'):
    """시군별 인구 요약"""
    engine = get_db_engine()

    sql = """
        SELECT
            sigungu_nm,
            total_pop,
            COALESCE(youth_pop, 0) as youth_pop,
            COALESCE(young_pop, 0) as young_pop,
            COALESCE(elderly_pop, 0) as elderly_pop,
            COALESCE(elderly_ratio, 0) as elderly_ratio,
            COALESCE(single_cnt, 0) as single_cnt
        FROM cache_sigungu_indicators
        WHERE TO_CHAR(base_ym, 'YYYYMM') = :ym
          AND sido_nm = :sido
          AND sigungu_code LIKE '____0'
        ORDER BY total_pop DESC
    """
    df = pd.read_sql(sql, engine, params={"ym": base_ym, "sido": sido})
    return df.to_dict('records')


def get_sigungu_trend(sigungu_nm):
    """시군구별 추이"""
    engine = get_db_engine()

    sql = """
        SELECT
            TO_CHAR(base_ym, 'YYYYMM') as base_ym,
            total_pop,
            COALESCE(youth_pop, 0) as youth_pop,
            COALESCE(young_pop, 0) as young_pop,
            COALESCE(elderly_pop, 0) as elderly_pop,
            COALESCE(elderly_ratio, 0) as elderly_ratio
        FROM cache_sigungu_indicators
        WHERE sigungu_nm = :sigungu
          AND sigungu_code LIKE '____0'
        ORDER BY base_ym
    """
    df = pd.read_sql(sql, engine, params={"sigungu": sigungu_nm})
    return df.to_dict('records')


# =============================================================================
# API 핸들러
# =============================================================================

def handle_api_request(api_type, request_args):
    """API 요청 처리"""

    if api_type == 'filter_options':
        return get_filter_options()

    base_ym = request_args.get('base_ym', '')
    sido = request_args.get('sido', '경상북도')

    if api_type == 'sigungu_summary':
        return get_sigungu_summary(base_ym, sido)

    elif api_type == 'sigungu_trend':
        sigungu = request_args.get('sigungu', '')
        return get_sigungu_trend(sigungu)

    return {'error': f'Unknown api_type: {api_type}'}


# =============================================================================
# HTML 생성
# =============================================================================

def generate_html(menu_items):
    """메인 대시보드 HTML 생성"""

    # 메뉴 HTML 생성
    menu_html = MenuGenerator.render_menu_html(menu_items)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>경북 인구·가구 진단 대시보드</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --primary-dark: #1243A6;
            --primary: #1D64F2;
            --dark: #011C40;
            --light: #F2EED8;
            --accent: #F24822;
        }}
        body {{ background-color: #f3f4f6; }}
        .header {{ background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%); }}
        .card {{ background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .btn-primary {{ background-color: var(--primary); color: white; }}
        .btn-primary:hover {{ background-color: var(--primary-dark); }}

        .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
        .data-table th {{
            background: var(--primary-dark);
            color: white;
            padding: 10px 8px;
            text-align: center;
        }}
        .data-table td {{
            border: 1px solid #e5e7eb;
            padding: 8px;
            text-align: right;
        }}
        .data-table td:first-child {{ text-align: left; font-weight: 500; }}
        .data-table tr:nth-child(even) {{ background: #f9f9f9; }}
        .data-table tr:hover {{ background: #e0f2fe; cursor: pointer; }}

        .loading-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 9999;
            justify-content: center;
            align-items: center;
        }}
        .loading-overlay.show {{ display: flex; }}
        .loading-spinner {{
            width: 50px; height: 50px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body class="min-h-screen">
    <!-- 로딩 오버레이 -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="bg-white p-6 rounded-lg text-center">
            <div class="loading-spinner mx-auto mb-4"></div>
            <div id="loadingText">데이터를 불러오는 중...</div>
        </div>
    </div>

    <!-- 상단 메뉴 -->
    {menu_html}

    <!-- 메인 컨텐츠 -->
    <main class="max-w-7xl mx-auto p-6">
        <h1 class="text-2xl font-bold text-gray-800 mb-6">경북 시군 인구·가구 진단</h1>

        <!-- 필터 섹션 -->
        <div class="card p-6 mb-6">
            <h2 class="text-lg font-semibold mb-4 text-gray-800">조회 조건</h2>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">기준년월</label>
                    <select id="baseYmSelect" class="w-full border rounded-lg px-3 py-2">
                        <option value="">선택...</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">시도</label>
                    <select id="sidoSelect" class="w-full border rounded-lg px-3 py-2">
                        <option value="경상북도">경상북도</option>
                    </select>
                </div>
                <div class="flex items-end">
                    <button onclick="loadData()" class="btn-primary px-6 py-2 rounded-lg font-medium">
                        조회
                    </button>
                </div>
            </div>
        </div>

        <!-- 데이터 영역 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- 테이블 -->
            <div class="card p-6">
                <h3 class="text-lg font-semibold mb-4">시군별 인구 현황</h3>
                <p class="text-sm text-gray-500 mb-2">* 행 클릭 시 추이 차트 표시</p>
                <div class="overflow-x-auto max-h-[500px] overflow-y-auto">
                    <table id="summaryTable" class="data-table">
                        <thead>
                            <tr>
                                <th>시군</th>
                                <th>총인구</th>
                                <th>유소년</th>
                                <th>청년</th>
                                <th>고령</th>
                                <th>고령화율</th>
                                <th>1인가구</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>

            <!-- 차트 영역 -->
            <div class="card p-6">
                <h3 class="text-lg font-semibold mb-4">시군별 인구 분포</h3>
                <div style="height: 300px;">
                    <canvas id="summaryChart"></canvas>
                </div>

                <h3 class="text-lg font-semibold mt-6 mb-4" id="trendTitle">시군 추이 (시군 선택)</h3>
                <div style="height: 250px;">
                    <canvas id="trendChart"></canvas>
                </div>
            </div>
        </div>
    </main>

    <script>
        let filterOptions = {{}};
        let summaryChart = null;
        let trendChart = null;

        document.addEventListener('DOMContentLoaded', async function() {{
            await loadFilterOptions();
        }});

        async function fetchAPI(apiType, params = {{}}) {{
            const urlParams = new URLSearchParams({{ api_type: apiType, ...params }});
            const response = await fetch(`?${{urlParams}}`);
            return await response.json();
        }}

        async function loadFilterOptions() {{
            showLoading('필터 옵션을 불러오는 중...');
            try {{
                filterOptions = await fetchAPI('filter_options');

                // 기준년월
                const ymSelect = document.getElementById('baseYmSelect');
                ymSelect.innerHTML = '';
                filterOptions.base_ym_list.forEach((ym, idx) => {{
                    const selected = idx === 0 ? 'selected' : '';
                    ymSelect.innerHTML += `<option value="${{ym}}" ${{selected}}>${{ym.substr(0,4)}}년 ${{ym.substr(4,2)}}월</option>`;
                }});

                // 시도
                const sidoSelect = document.getElementById('sidoSelect');
                sidoSelect.innerHTML = '';
                filterOptions.sido_list.forEach(sido => {{
                    const selected = sido === '경상북도' ? 'selected' : '';
                    sidoSelect.innerHTML += `<option value="${{sido}}" ${{selected}}>${{sido}}</option>`;
                }});

                // 초기 데이터 로드
                await loadData();

            }} catch(e) {{
                console.error('Filter load error:', e);
                alert('필터 옵션 로드 실패: ' + e.message);
            }} finally {{
                hideLoading();
            }}
        }}

        async function loadData() {{
            const baseYm = document.getElementById('baseYmSelect').value;
            const sido = document.getElementById('sidoSelect').value;

            if (!baseYm) {{
                alert('기준년월을 선택해주세요.');
                return;
            }}

            showLoading('데이터를 조회하는 중...');

            try {{
                const data = await fetchAPI('sigungu_summary', {{ base_ym: baseYm, sido: sido }});
                renderTable(data);
                renderSummaryChart(data);
            }} catch(e) {{
                console.error('Data load error:', e);
                alert('데이터 로드 실패: ' + e.message);
            }} finally {{
                hideLoading();
            }}
        }}

        function renderTable(data) {{
            const tbody = document.querySelector('#summaryTable tbody');
            tbody.innerHTML = '';

            if (!data || data.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="7" class="text-center p-4 text-gray-500">데이터가 없습니다.</td></tr>';
                return;
            }}

            data.forEach(row => {{
                const tr = document.createElement('tr');
                tr.onclick = () => loadTrend(row.sigungu_nm);
                tr.innerHTML = `
                    <td>${{row.sigungu_nm}}</td>
                    <td>${{(row.total_pop || 0).toLocaleString()}}</td>
                    <td>${{(row.youth_pop || 0).toLocaleString()}}</td>
                    <td>${{(row.young_pop || 0).toLocaleString()}}</td>
                    <td>${{(row.elderly_pop || 0).toLocaleString()}}</td>
                    <td>${{(row.elderly_ratio || 0).toFixed(1)}}%</td>
                    <td>${{(row.single_cnt || 0).toLocaleString()}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function renderSummaryChart(data) {{
            if (!data || data.length === 0) return;

            const ctx = document.getElementById('summaryChart').getContext('2d');
            if (summaryChart) summaryChart.destroy();

            const labels = data.map(r => r.sigungu_nm);
            const totalPop = data.map(r => r.total_pop || 0);
            const elderlyPop = data.map(r => r.elderly_pop || 0);

            summaryChart = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: '총인구',
                            data: totalPop,
                            backgroundColor: 'rgba(29, 100, 242, 0.7)',
                            borderColor: 'rgba(29, 100, 242, 1)',
                            borderWidth: 1
                        }},
                        {{
                            label: '고령인구',
                            data: elderlyPop,
                            backgroundColor: 'rgba(242, 72, 34, 0.7)',
                            borderColor: 'rgba(242, 72, 34, 1)',
                            borderWidth: 1
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ position: 'top' }} }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: v => (v / 10000).toFixed(0) + '만' }}
                        }}
                    }}
                }}
            }});
        }}

        async function loadTrend(sigungu) {{
            document.getElementById('trendTitle').textContent = sigungu + ' 추이';

            try {{
                const data = await fetchAPI('sigungu_trend', {{ sigungu: sigungu }});
                renderTrendChart(data);
            }} catch(e) {{
                console.error('Trend load error:', e);
            }}
        }}

        function renderTrendChart(data) {{
            if (!data || data.length === 0) return;

            const ctx = document.getElementById('trendChart').getContext('2d');
            if (trendChart) trendChart.destroy();

            const labels = data.map(r => r.base_ym);
            const totalPop = data.map(r => r.total_pop || 0);
            const elderlyRatio = data.map(r => r.elderly_ratio || 0);

            trendChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: '총인구',
                            data: totalPop,
                            borderColor: 'rgba(29, 100, 242, 1)',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            yAxisID: 'y'
                        }},
                        {{
                            label: '고령화율(%)',
                            data: elderlyRatio,
                            borderColor: 'rgba(242, 72, 34, 1)',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            yAxisID: 'y1'
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    plugins: {{ legend: {{ position: 'top' }} }},
                    scales: {{
                        y: {{
                            type: 'linear',
                            position: 'left',
                            title: {{ display: true, text: '인구' }},
                            ticks: {{ callback: v => (v / 10000).toFixed(0) + '만' }}
                        }},
                        y1: {{
                            type: 'linear',
                            position: 'right',
                            title: {{ display: true, text: '고령화율(%)' }},
                            grid: {{ drawOnChartArea: false }},
                            min: 0,
                            max: 50
                        }}
                    }}
                }}
            }});
        }}

        function showLoading(text) {{
            document.getElementById('loadingText').textContent = text || '처리 중...';
            document.getElementById('loadingOverlay').classList.add('show');
        }}

        function hideLoading() {{
            document.getElementById('loadingOverlay').classList.remove('show');
        }}
    </script>
</body>
</html>"""


# =============================================================================
# 메인 렌더 함수
# =============================================================================

def render(request_args):
    """메인 렌더 함수"""
    api_type = request_args.get('api_type')

    if api_type:
        result = handle_api_request(api_type, request_args)
        return Response(
            json.dumps(result, ensure_ascii=False, default=str),
            mimetype='application/json'
        )

    # 메뉴 아이템 생성
    menu_items = MenuGenerator.get_category_menu_items(POP_BASE)

    return Response(generate_html(menu_items), mimetype='text/html')
