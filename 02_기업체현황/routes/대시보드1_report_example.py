# -*- coding: utf-8 -*-
"""
대시보드1.py에서 report_generator 사용 예시
==========================================

이 파일은 대시보드1.py에 추가해야 할 코드를 보여줍니다.
실제로는 대시보드1.py에 이 코드들을 통합하면 됩니다.

사용 흐름:
    1. "MD 저장" 버튼 클릭 → handle_md_save() → 대시보드1.md 생성
    2. "PPT 저장" 버튼 클릭 → handle_ppt_save() → 대시보드1.pptx 생성
"""

import sys
from pathlib import Path

# 상위 module 폴더 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from module.report_generator import DashboardReport


def get_dashboard_data(selected_year, selected_quarter, view_type, selected_sido):
    """
    대시보드 데이터를 수집하여 DashboardReport 객체로 반환

    이 함수를 대시보드1.py에 추가하세요.
    기존 render() 함수에서 데이터를 조회하는 부분을 재사용합니다.

    Returns:
        DashboardReport: 보고서 객체
    """
    # 기존 함수들 호출 (대시보드1.py에 이미 있음)
    # df_aggregated = get_aggregated_data(selected_year, selected_quarter, view_type, selected_sido)
    # df_ts = get_timeseries_data(view_type, selected_sido)
    # df_pop_biz = get_population_density_data(selected_year, selected_quarter, view_type, selected_sido)
    # insights = generate_insights(df_aggregated, df_ts, df_pop_biz, view_type, selected_sido)

    # 예시 데이터 (실제로는 위 함수들의 결과 사용)
    df_aggregated = None  # 실제 데이터로 대체
    df_ts = None
    df_pop_biz = None
    insights = []

    # 레이블 생성
    latest_quarter_label = f"{selected_year}년 {selected_quarter}분기"
    if view_type == '전체':
        region_label = "전국 (시도별)"
    elif view_type == '권역별':
        region_label = "권역별"
    elif view_type == '시도별':
        region_label = f"{selected_sido} (시군구별)"
    else:
        region_label = "전국"

    # DashboardReport 객체 생성
    report = DashboardReport(
        title="기업통계등록부(SBR) 분석 보고서",
        subtitle=f"{latest_quarter_label} | {region_label}",
        source_file=__file__  # 현재 파일 경로 → MD는 같은 폴더에 저장됨
    )

    # 주요 지표 추가
    if df_aggregated is not None:
        total_businesses = df_aggregated['총사업체수'].sum()
        total_employees = df_aggregated['총종사자수'].sum()
        avg_hhi = df_aggregated['HHI'].mean() if 'HHI' in df_aggregated.columns else 0
        avg_sales = df_aggregated['1인당매출액'].mean() if '1인당매출액' in df_aggregated.columns else 0

        report.add_metrics([
            {'label': '총 사업체수', 'value': f'{total_businesses:,.0f}', 'unit': '개'},
            {'label': '총 종사자수', 'value': f'{total_employees:,.0f}', 'unit': '명'},
            {'label': '평균 HHI', 'value': f'{avg_hhi:.1f}', 'unit': '낮을수록 다양함'},
            {'label': '평균 1인당 매출액', 'value': f'{avg_sales:.1f}', 'unit': '백만원'},
        ])

    # 표 데이터 추가
    if df_aggregated is not None:
        # 필요한 컬럼만 선택
        df_table = df_aggregated[['지역명', '총사업체수', '총종사자수', 'HHI', '1인당매출액']].copy()
        report.add_table('지역별 현황', df_table, max_rows=15)

    if df_pop_biz is not None:
        df_density = df_pop_biz[['시도명', '총인구', '사업체수', '인구천명당사업체수']].copy()
        report.add_table('인구 대비 사업체 밀도', df_density, max_rows=15)

    # 인사이트 추가
    if insights:
        report.add_insights(insights)

    return report


def handle_md_save(form_data):
    """
    MD 저장 요청 처리

    대시보드1.py의 handle_hwp_save()와 비슷한 구조로 작성합니다.
    """
    from flask import Response

    try:
        # 파라미터 추출
        selected_year = form_data.get('year')
        selected_quarter = form_data.get('quarter')
        view_type = form_data.get('view_type', '시도별')
        selected_sido = form_data.get('sido', '경상북도')

        # 보고서 객체 생성
        report = get_dashboard_data(selected_year, selected_quarter, view_type, selected_sido)

        # MD 저장 (같은 폴더에 같은 이름으로)
        md_path = report.save_markdown()

        return Response(
            f"<script>alert('MD 저장 완료: {md_path.name}'); history.back();</script>",
            mimetype='text/html'
        )

    except Exception as e:
        return Response(
            f"<script>alert('MD 저장 오류: {str(e)}'); history.back();</script>",
            mimetype='text/html'
        )


def handle_ppt_save_new(form_data, template_path=None):
    """
    PPT 저장 요청 처리 (report_generator 사용)

    기존 handle_ppt_save()를 이 방식으로 교체하거나 병행 사용 가능
    """
    from flask import Response, send_file
    import tempfile

    try:
        # 파라미터 추출
        selected_year = form_data.get('year')
        selected_quarter = form_data.get('quarter')
        view_type = form_data.get('view_type', '시도별')
        selected_sido = form_data.get('sido', '경상북도')

        # 보고서 객체 생성
        report = get_dashboard_data(selected_year, selected_quarter, view_type, selected_sido)

        # 차트 이미지 생성 (기존 generate_ppt_report 함수의 차트 생성 로직 사용)
        # chart_paths = generate_charts(df_aggregated, df_ts, df_pop_biz, region_label)
        # for title, path in chart_paths.items():
        #     report.add_chart(title, path)

        # PPT 저장
        ppt_path = report.save_ppt(template_path=template_path)

        # 파일 다운로드
        filename = f"기업통계등록부_{selected_year}년{selected_quarter}분기.pptx"
        return send_file(
            str(ppt_path),
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation'
        )

    except Exception as e:
        return Response(
            f"<script>alert('PPT 저장 오류: {str(e)}'); history.back();</script>",
            mimetype='text/html'
        )


# =============================================================================
# HTML에 추가할 버튼 코드
# =============================================================================

HTML_BUTTONS_EXAMPLE = """
<!-- 저장 버튼들 (MD, PPT, HWP) -->
<div class="save-buttons-container">
    <!-- MD 저장 폼 -->
    <form method="post" class="save-form">
        <input type="hidden" name="action" value="save_md">
        <input type="hidden" name="year" value="{selected_year}">
        <input type="hidden" name="quarter" value="{selected_quarter}">
        <input type="hidden" name="view_type" value="{view_type}">
        <input type="hidden" name="sido" value="{selected_sido}">
        <button type="submit" class="md-btn">
            📝 MD 저장
        </button>
    </form>

    <!-- PPT 저장 폼 -->
    <form method="post" class="save-form">
        <input type="hidden" name="action" value="save_ppt">
        <input type="hidden" name="year" value="{selected_year}">
        <input type="hidden" name="quarter" value="{selected_quarter}">
        <input type="hidden" name="view_type" value="{view_type}">
        <input type="hidden" name="sido" value="{selected_sido}">
        <button type="submit" class="ppt-btn">
            📊 PPT 저장
        </button>
    </form>
</div>

<!-- CSS 추가 -->
<style>
.md-btn {
    background: linear-gradient(135deg, #3498db, #2980b9);
    color: white;
    padding: 12px 30px;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
    font-weight: 600;
    transition: transform 0.2s;
}
.md-btn:hover {
    transform: translateY(-2px);
}
</style>
"""


# =============================================================================
# render() 함수에 추가할 POST 처리 코드
# =============================================================================

RENDER_POST_EXAMPLE = """
# render() 함수 내부에 추가:

if request.method == 'POST':
    action = request.form.get('action')

    if action == 'save_md':
        return handle_md_save(request.form)
    elif action == 'save_ppt':
        return handle_ppt_save(request.form)  # 또는 handle_ppt_save_new()
    elif action == 'save_hwp':
        return handle_hwp_save(request.form)
"""


# =============================================================================
# 테스트
# =============================================================================

if __name__ == "__main__":
    print("대시보드 보고서 생성 테스트")
    print("-" * 40)

    # 테스트용 보고서 생성
    report = DashboardReport(
        title="기업통계등록부(SBR) 분석 보고서",
        subtitle="2024년 4분기 | 경상북도 (시군구별)",
        source_file=__file__
    )

    # 테스트 데이터
    report.add_metrics([
        {'label': '총 사업체수', 'value': '123,456', 'unit': '개'},
        {'label': '총 종사자수', 'value': '567,890', 'unit': '명'},
        {'label': '평균 HHI', 'value': '1,523.4', 'unit': '낮을수록 다양함'},
        {'label': '1인당 매출액', 'value': '125.6', 'unit': '백만원'},
    ])

    report.add_insights([
        {'icon': '📍', 'title': '사업체 밀도 최고', 'content': '포항시가 인구 천명당 45.3개로 가장 높습니다.'},
        {'icon': '📊', 'title': '산업 다양성', 'content': '경산시의 HHI가 1200으로 가장 다양합니다.'},
        {'icon': '📈', 'title': '성장세', 'content': '전분기 대비 2.3% 증가했습니다.'},
    ])

    # MD 저장
    md_path = report.save_markdown()
    print(f"\nMD 저장 완료: {md_path}")
    print(f"저장 위치: {md_path.parent}")

    # MD 내용 미리보기
    print("\n=== MD 내용 미리보기 ===")
    print(report.to_markdown()[:800])
    print("...")

    # PPT 저장
    try:
        ppt_path = report.save_ppt()
        print(f"\nPPT 저장 완료: {ppt_path}")
    except RuntimeError as e:
        print(f"\nPPT 저장 불가: {e}")
