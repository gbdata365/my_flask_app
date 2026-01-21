# -*- coding: utf-8 -*-
"""
대시보드 보고서 저장 공통 모듈
==============================

대시보드 페이지에서 MD/PPT 저장 기능을 제공하는 공통 모듈입니다.
각 폴더의 대시보드*.py에서 이 모듈을 import하여 사용합니다.

사용법:
    from module.dashboard_report import DashboardReportMixin, handle_report_save

    # 방법 1: Mixin 클래스 사용
    class MyDashboard(DashboardReportMixin):
        def get_dashboard_data(self):
            return {...}

    # 방법 2: 함수 직접 사용
    handle_report_save(request.form, get_dashboard_data_func, __file__)

저장 위치:
    - MD: 소스 파일과 같은 폴더에 같은 이름으로 (대시보드1.py → 대시보드1.md)
    - PPT: 소스 파일과 같은 폴더에 같은 이름으로 (대시보드1.py → 대시보드1.pptx)

Author: Claude AI Agent
Created: 2025-01-15
"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
import tempfile
import base64
import io

import pandas as pd
from loguru import logger

# matplotlib 백엔드 설정
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import koreanize_matplotlib


# =============================================================================
# 데이터 구조
# =============================================================================

@dataclass
class DashboardData:
    """
    대시보드 데이터 구조

    대시보드에서 수집한 데이터를 담는 구조체입니다.
    """
    # 기본 정보
    title: str
    subtitle: str = ""
    source_file: str = ""  # __file__

    # 데이터
    metrics: List[Dict[str, str]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)  # {'title': str, 'df': DataFrame}
    charts: List[Dict[str, str]] = field(default_factory=list)  # {'title': str, 'image_path': str}
    insights: List[Dict[str, str]] = field(default_factory=list)

    # 메타 정보
    created_at: datetime = field(default_factory=datetime.now)
    params: Dict[str, Any] = field(default_factory=dict)  # 필터 파라미터 등


# =============================================================================
# 핵심 함수
# =============================================================================

def create_report_from_data(data: DashboardData):
    """
    DashboardData로부터 DashboardReport 객체 생성

    Args:
        data: DashboardData 인스턴스

    Returns:
        DashboardReport 객체
    """
    from module.report_generator import DashboardReport

    report = DashboardReport(
        title=data.title,
        subtitle=data.subtitle,
        source_file=data.source_file
    )

    # 지표 추가
    if data.metrics:
        report.add_metrics(data.metrics)

    # 표 추가
    for table in data.tables:
        df = table.get('df')
        if df is not None and not df.empty:
            report.add_table(
                title=table.get('title', '데이터'),
                df=df,
                max_rows=table.get('max_rows', 15)
            )

    # 차트 추가
    for chart in data.charts:
        report.add_chart(
            title=chart.get('title', '차트'),
            image_path=chart.get('image_path', ''),
            description=chart.get('description', '')
        )

    # 인사이트 추가
    if data.insights:
        report.add_insights(data.insights)

    return report


def save_dashboard_md(
    data: DashboardData,
    output_path: Optional[str] = None
) -> Optional[Path]:
    """
    대시보드 데이터를 MD 파일로 저장

    Args:
        data: DashboardData 인스턴스
        output_path: 저장 경로 (None이면 source_file과 같은 이름으로)

    Returns:
        Path: 저장된 파일 경로
    """
    try:
        report = create_report_from_data(data)

        if output_path:
            md_path = report.save_markdown(output_path)
        else:
            # source_file과 같은 이름으로 저장
            if data.source_file:
                source_path = Path(data.source_file)
                md_path = source_path.parent / f"{source_path.stem}.md"
                md_path.write_text(report.to_markdown(), encoding='utf-8')
            else:
                md_path = report.save_markdown()

        logger.info(f"대시보드 MD 저장 완료: {md_path}")
        return md_path

    except Exception as e:
        logger.error(f"대시보드 MD 저장 오류: {e}")
        return None


def save_dashboard_ppt(
    data: DashboardData,
    output_path: Optional[str] = None,
    template_path: Optional[str] = None
) -> Optional[Path]:
    """
    대시보드 데이터를 PPT 파일로 저장

    Args:
        data: DashboardData 인스턴스
        output_path: 저장 경로 (None이면 source_file과 같은 이름으로)
        template_path: PPT 템플릿 경로

    Returns:
        Path: 저장된 파일 경로
    """
    try:
        from module.report_generator import PPT_AVAILABLE

        if not PPT_AVAILABLE:
            logger.warning("python-pptx가 설치되지 않았습니다.")
            return None

        report = create_report_from_data(data)

        if output_path:
            ppt_path = report.save_ppt(output_path, template_path)
        else:
            # source_file과 같은 이름으로 저장
            if data.source_file:
                source_path = Path(data.source_file)
                ppt_path = source_path.parent / f"{source_path.stem}.pptx"
                report.save_ppt(str(ppt_path), template_path)
            else:
                ppt_path = report.save_ppt(template_path=template_path)

        logger.info(f"대시보드 PPT 저장 완료: {ppt_path}")
        return ppt_path

    except Exception as e:
        logger.error(f"대시보드 PPT 저장 오류: {e}")
        return None


def save_chart_image(
    df: pd.DataFrame,
    output_dir: Path,
    filename: str,
    chart_type: str = 'bar',
    title: str = None
) -> Optional[Path]:
    """
    DataFrame을 차트 이미지로 저장

    Args:
        df: 차트 데이터
        output_dir: 저장 디렉토리
        filename: 파일명
        chart_type: 차트 타입 ('bar', 'line', 'pie')
        title: 차트 제목

    Returns:
        Path: 저장된 이미지 경로
    """
    if df is None or df.empty:
        return None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        fig, ax = plt.subplots(figsize=(12, max(6, len(df) * 0.4)))

        label_col = df.columns[0]
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric_cols:
            return None
        value_col = numeric_cols[-1]

        if chart_type == 'bar':
            df_sorted = df.sort_values(value_col, ascending=True)
            ax.barh(df_sorted[label_col].astype(str), df_sorted[value_col])
        elif chart_type == 'line':
            ax.plot(df[label_col], df[value_col], marker='o')
            plt.xticks(rotation=45, ha='right')
        elif chart_type == 'pie':
            ax.pie(df[value_col], labels=df[label_col], autopct='%1.1f%%')

        chart_title = title or f'{label_col}별 {value_col}'
        ax.set_title(chart_title, fontsize=13, fontweight='bold')

        plt.tight_layout()

        output_path = output_dir / filename
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

        return output_path

    except Exception as e:
        logger.error(f"차트 이미지 저장 오류: {e}")
        plt.close('all')
        return None


# =============================================================================
# Flask 핸들러
# =============================================================================

def handle_report_save(
    form_data: Dict[str, Any],
    get_data_func: Callable[..., DashboardData],
    source_file: str,
    template_path: Optional[str] = None
):
    """
    Flask에서 MD/PPT 저장 요청 처리

    대시보드*.py의 render() 함수에서 POST 요청을 받았을 때 사용합니다.

    사용 예:
        if request.method == 'POST':
            action = request.form.get('action')
            if action in ('save_md', 'save_ppt'):
                return handle_report_save(
                    request.form,
                    get_dashboard_data,
                    __file__
                )

    Args:
        form_data: request.form 딕셔너리
        get_data_func: DashboardData를 반환하는 함수
        source_file: __file__ (저장 위치 결정)
        template_path: PPT 템플릿 경로

    Returns:
        Flask Response
    """
    from flask import Response, send_file

    action = form_data.get('action')

    try:
        # 데이터 수집 함수 호출
        data = get_data_func(form_data)
        data.source_file = source_file

        if action == 'save_md':
            md_path = save_dashboard_md(data)
            if md_path and md_path.exists():
                return send_file(
                    str(md_path),
                    as_attachment=True,
                    download_name=md_path.name,
                    mimetype='text/markdown'
                )
            return Response(
                "<script>alert('MD 저장에 실패했습니다.'); history.back();</script>",
                mimetype='text/html'
            )

        elif action == 'save_ppt':
            ppt_path = save_dashboard_ppt(data, template_path=template_path)
            if ppt_path and ppt_path.exists():
                return send_file(
                    str(ppt_path),
                    as_attachment=True,
                    download_name=ppt_path.name,
                    mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation'
                )
            return Response(
                "<script>alert('PPT 저장에 실패했습니다. python-pptx가 설치되어 있는지 확인하세요.'); history.back();</script>",
                mimetype='text/html'
            )

        return Response(
            "<script>alert('잘못된 요청입니다.'); history.back();</script>",
            mimetype='text/html'
        )

    except Exception as e:
        logger.error(f"보고서 저장 오류: {e}")
        return Response(
            f"<script>alert('저장 중 오류가 발생했습니다: {str(e)}'); history.back();</script>",
            mimetype='text/html'
        )


# =============================================================================
# HTML 헬퍼
# =============================================================================

def get_save_buttons_html(params: Dict[str, str]) -> str:
    """
    MD/PPT 저장 버튼 HTML 생성

    대시보드 페이지에 저장 버튼을 추가할 때 사용합니다.

    Args:
        params: 현재 필터 파라미터 (year, quarter, sido 등)

    Returns:
        str: HTML 문자열
    """
    hidden_inputs = '\n'.join([
        f'<input type="hidden" name="{k}" value="{v}">'
        for k, v in params.items()
    ])

    return f'''
<div class="save-buttons-container" style="margin-top: 1.5rem; padding: 1rem; background: #f8f9fc; border-radius: 10px; text-align: center;">
    <span style="font-weight: 600; color: #333; margin-right: 1rem;">보고서 저장:</span>

    <form method="post" style="display: inline-block; margin: 0 0.3rem;">
        <input type="hidden" name="action" value="save_md">
        {hidden_inputs}
        <button type="submit" style="
            padding: 0.6rem 1.2rem;
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
            📝 MD 저장
        </button>
    </form>

    <form method="post" style="display: inline-block; margin: 0 0.3rem;">
        <input type="hidden" name="action" value="save_ppt">
        {hidden_inputs}
        <button type="submit" style="
            padding: 0.6rem 1.2rem;
            background: linear-gradient(135deg, #e67e22, #d35400);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
            📊 PPT 저장
        </button>
    </form>
</div>
'''


# =============================================================================
# 테스트
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("대시보드 보고서 모듈 테스트")
    print("=" * 60)

    # 테스트 데이터 생성
    test_data = DashboardData(
        title="테스트 대시보드 보고서",
        subtitle="2024년 4분기 | 경상북도",
        source_file=__file__,
        metrics=[
            {'label': '총 사업체수', 'value': '123,456', 'unit': '개'},
            {'label': '총 종사자수', 'value': '567,890', 'unit': '명'},
        ],
        insights=[
            {'icon': '📍', 'title': '지역 특성', 'content': '경상북도 사업체 밀도가 높습니다.'},
            {'icon': '📈', 'title': '성장세', 'content': '전분기 대비 2.3% 증가했습니다.'},
        ],
        params={'year': '2024', 'quarter': '4', 'sido': '경상북도'}
    )

    # MD 저장 테스트
    md_path = save_dashboard_md(test_data)
    if md_path:
        print(f"✅ MD 저장 완료: {md_path}")
    else:
        print("❌ MD 저장 실패")

    # PPT 저장 테스트
    ppt_path = save_dashboard_ppt(test_data)
    if ppt_path:
        print(f"✅ PPT 저장 완료: {ppt_path}")
    else:
        print("❌ PPT 저장 실패 (python-pptx 미설치?)")

    # HTML 버튼 테스트
    html = get_save_buttons_html({'year': '2024', 'quarter': '4'})
    print(f"\n버튼 HTML 길이: {len(html)} 문자")

    print("\n" + "=" * 60)
