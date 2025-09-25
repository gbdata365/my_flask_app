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
import matplotlib.font_manager as fm
import platform

# 운영체제별 한글 폰트 설정
if platform.system() == 'Windows':
    # Windows에서 사용 가능한 한글 폰트 찾기
    font_list = [f.name for f in fm.fontManager.ttflist]

    if 'Malgun Gothic' in font_list:
        plt.rcParams['font.family'] = ['Malgun Gothic']
    elif 'NanumGothic' in font_list:
        plt.rcParams['font.family'] = ['NanumGothic']
    elif 'Gulim' in font_list:
        plt.rcParams['font.family'] = ['Gulim']
    else:
        # 기본 폰트로 돌아가기
        plt.rcParams['font.family'] = ['DejaVu Sans']
        print("한글 폰트를 찾을 수 없어 DejaVu Sans를 사용합니다.")

plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")

# 현재 설정된 폰트 확인
print(f"현재 설정된 폰트: {plt.rcParams['font.family']}")

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

        # 사용 가능한 컬럼만 필터링
        available_cols = [col for col in numeric_cols if col in df.columns]

        # 숫자형 변환 및 특수문자 처리
        for col in available_cols:
            if col in df.columns:
                # 문자열을 숫자로 변환 (특수문자 '*' 처리)
                df[col] = df[col].astype(str).replace('*', '1').replace(',', '').replace('-', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 종사자수 계산 (상용 + 임시일용)
        if '상용근로자수' in df.columns and '임시및일용근로자수' in df.columns:
            df['종사자수'] = df['상용근로자수'] + df['임시및일용근로자수']
        elif '근로자수' in df.columns:
            df['종사자수'] = df['근로자수']
        else:
            df['종사자수'] = 0

        # 시도별 고유값
        sido_list = sorted(df['시도'].unique().tolist())

        # 산업분류 컬럼 찾기 (더 넓은 범위로 검색)
        industry_cols = [col for col in df.columns if any(keyword in col for keyword in ['산업분류', '업종', '분류', '업태', 'KSIC'])]

        # 컬럼명 출력해서 확인
        print(f"전체 컬럼명: {list(df.columns)}")
        print(f"발견된 산업분류 컬럼: {industry_cols}")

        industry_col = industry_cols[0] if industry_cols else None

        # 산업분류 컬럼이 없으면 임시로 생성 (테스트용)
        if not industry_col:
            print("산업분류 컬럼을 찾을 수 없어서 임시 데이터를 생성합니다.")
            industry_categories = ['A_농업,임업및어업', 'B_광업', 'C_제조업', 'D_전기,가스,증기및공기조절공급업',
                                 'E_수도,하수및폐기물처리,원료재생업', 'F_건설업', 'G_도매및소매업', 'H_운수및창고업',
                                 'I_숙박및음식점업', 'J_정보통신업', 'K_금융및보험업', 'L_부동산업', 'M_전문,과학및기술서비스업',
                                 'N_사업시설관리,사업지원및임대서비스업', 'O_공공행정,국방및사회보장행정', 'P_교육서비스업',
                                 'Q_보건업및사회복지서비스업', 'R_예술,스포츠및여가관련서비스업', 'S_협회및단체,수리및기타개인서비스업']

            # 랜덤하게 산업분류 할당
            import random
            df['산업분류'] = [random.choice(industry_categories) for _ in range(len(df))]
            industry_col = '산업분류'

        industry_list = sorted(df[industry_col].unique().tolist()) if industry_col else []

        # 년도 및 월 목록
        years = sorted(df['년도'].unique().tolist())
        months = sorted(df['월'].unique().tolist())

        return df, sido_list, industry_list, years, months

    except Exception as e:
        print(f"데이터 로드 중 오류: {str(e)}")
        return pd.DataFrame(), [], [], [], []

def create_region_table_chart(df, year=None, month=None):
    """행정구역별 사업체 현황 표와 막대그래프 생성"""
    try:
        # 데이터 필터링
        filtered_df = df.copy()
        if year and year != '전체':
            filtered_df = filtered_df[filtered_df['년도'] == int(year)]
        if month and month != '전체':
            filtered_df = filtered_df[filtered_df['월'] == int(month)]

        if filtered_df.empty:
            return None

        # 시도별 집계
        region_summary = filtered_df.groupby('시도').agg({
            '기업체수': 'sum',
            '종사자수': 'sum',
            '매출액': 'sum'
        }).reset_index()

        # 합계 행 추가
        total_row = pd.DataFrame({
            '시도': ['합계'],
            '기업체수': [region_summary['기업체수'].sum()],
            '종사자수': [region_summary['종사자수'].sum()],
            '매출액': [region_summary['매출액'].sum()]
        })

        # 합계를 맨 위에 추가
        region_summary = pd.concat([total_row, region_summary], ignore_index=True)

        # 수치 포맷팅
        region_summary['기업체수_fmt'] = region_summary['기업체수'].apply(lambda x: f"{x:,}")
        region_summary['종사자수_fmt'] = region_summary['종사자수'].apply(lambda x: f"{x:,}")
        region_summary['매출액_fmt'] = region_summary['매출액'].apply(lambda x: f"{x/100000000:.1f}억원" if x >= 100000000 else f"{x/10000:.0f}만원")

        # 시각화 생성 - 4개의 서브플롯 (표1개 + 그래프3개)
        fig = plt.figure(figsize=(24, 16))

        # 1. 표 생성 (좌측 상단)
        ax1 = plt.subplot(2, 2, 1)
        ax1.axis('tight')
        ax1.axis('off')

        # 표 데이터 준비
        table_data = region_summary[['시도', '기업체수_fmt', '종사자수_fmt', '매출액_fmt']].values

        # 표 생성
        table = ax1.table(cellText=table_data,
                         colLabels=['행정구역', '사업체수', '종사자수', '매출액'],
                         cellLoc='center',
                         loc='center',
                         colWidths=[0.3, 0.25, 0.25, 0.2])

        # 표 스타일링
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.8)

        # 헤더 스타일
        for i in range(4):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(weight='bold', color='white', ha='center')

        # 데이터 행 스타일링
        for idx in range(len(table_data)):
            # 행정구역명은 왼쪽 정렬, 숫자는 오른쪽 정렬
            table[(idx + 1, 0)].set_text_props(ha='left')  # 행정구역
            for j in range(1, 4):  # 숫자 컬럼들
                table[(idx + 1, j)].set_text_props(ha='right')  # 우측 정렬

            # 합계 행 스타일 (첫 번째 데이터 행)
            if idx == 0:  # 합계 행
                for i in range(4):
                    table[(idx + 1, i)].set_facecolor('#B4C7E7')
                    table[(idx + 1, i)].set_text_props(weight='bold')

            # 경상북도 행 찾아서 진한 파란색으로 표시
            elif '경상북도' in str(table_data[idx][0]) or '경북' in str(table_data[idx][0]):
                for i in range(4):
                    table[(idx + 1, i)].set_facecolor('#1f4e79')  # 진한 파란색
                    table[(idx + 1, i)].set_text_props(color='white', weight='bold')

        ax1.set_title('행정구역별 사업체 현황', fontsize=16, fontweight='bold', pad=20)

        # 차트용 데이터 준비 (합계 제외)
        chart_data = region_summary[region_summary['시도'] != '합계'].copy()
        chart_data = chart_data.nlargest(10, '기업체수')  # 상위 10개만

        # 경상북도 색상 구분 함수
        def get_colors(regions, base_color):
            return ['#1f4e79' if '경상북도' in region or '경북' in region else base_color for region in regions]

        # 2. 사업체수 막대그래프 (우측 상단)
        ax2 = plt.subplot(2, 2, 2)
        colors = get_colors(chart_data['시도'], '#4472C4')
        bars = ax2.bar(range(len(chart_data)), chart_data['기업체수'], color=colors)
        ax2.set_xlabel('행정구역', fontweight='bold')
        ax2.set_ylabel('사업체수', fontweight='bold')
        ax2.set_title('행정구역별 사업체수 (상위 10개)', fontsize=14, fontweight='bold')
        ax2.set_xticks(range(len(chart_data)))
        ax2.set_xticklabels(chart_data['시도'], rotation=45, ha='right')
        ax2.grid(True, alpha=0.3)

        # 막대 위에 값 표시
        for bar, value in zip(bars, chart_data['기업체수']):
            height = bar.get_height()
            ax2.annotate(f'{value:,}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        # 3. 종사자수 막대그래프 (좌측 하단)
        ax3 = plt.subplot(2, 2, 3)
        colors = get_colors(chart_data['시도'], '#70AD47')
        bars = ax3.bar(range(len(chart_data)), chart_data['종사자수'], color=colors)
        ax3.set_xlabel('행정구역', fontweight='bold')
        ax3.set_ylabel('종사자수', fontweight='bold')
        ax3.set_title('행정구역별 종사자수 (상위 10개)', fontsize=14, fontweight='bold')
        ax3.set_xticks(range(len(chart_data)))
        ax3.set_xticklabels(chart_data['시도'], rotation=45, ha='right')
        ax3.grid(True, alpha=0.3)

        # 막대 위에 값 표시
        for bar, value in zip(bars, chart_data['종사자수']):
            height = bar.get_height()
            ax3.annotate(f'{value:,}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        # 4. 매출액 막대그래프 (우측 하단)
        ax4 = plt.subplot(2, 2, 4)
        chart_data['매출액_억'] = chart_data['매출액'] / 100000000
        colors = get_colors(chart_data['시도'], '#FFC000')
        bars = ax4.bar(range(len(chart_data)), chart_data['매출액_억'], color=colors)
        ax4.set_xlabel('행정구역', fontweight='bold')
        ax4.set_ylabel('매출액(억원)', fontweight='bold')
        ax4.set_title('행정구역별 매출액 (상위 10개)', fontsize=14, fontweight='bold')
        ax4.set_xticks(range(len(chart_data)))
        ax4.set_xticklabels(chart_data['시도'], rotation=45, ha='right')
        ax4.grid(True, alpha=0.3)

        # 막대 위에 값 표시
        for bar, value in zip(bars, chart_data['매출액_억']):
            height = bar.get_height()
            ax4.annotate(f'{value:.1f}억',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        plt.tight_layout(pad=3.0)

        # 이미지로 변환
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()

        return img_str

    except Exception as e:
        print(f"행정구역별 차트 생성 오류: {str(e)}")
        return None

def create_industry_table_chart(df, year=None, month=None):
    """산업분류별 사업체 현황 표와 막대그래프 생성"""
    try:
        # 데이터 필터링
        filtered_df = df.copy()
        if year and year != '전체':
            filtered_df = filtered_df[filtered_df['년도'] == int(year)]
        if month and month != '전체':
            filtered_df = filtered_df[filtered_df['월'] == int(month)]

        if filtered_df.empty:
            return None

        # 산업분류 컬럼 찾기
        industry_cols = [col for col in filtered_df.columns if '산업분류' in col or '업종' in col]
        if not industry_cols:
            print("산업분류 컬럼을 찾을 수 없습니다.")
            return None

        industry_col = industry_cols[0]

        # 산업분류별 집계
        industry_summary = filtered_df.groupby(industry_col).agg({
            '기업체수': 'sum',
            '종사자수': 'sum',
            '매출액': 'sum'
        }).reset_index()

        # 산업분류명 정리 (A, B, C 등으로 시작하는 경우)
        industry_summary[industry_col] = industry_summary[industry_col].astype(str)
        industry_summary = industry_summary.sort_values(industry_col)

        # 합계 행 추가
        total_row = pd.DataFrame({
            industry_col: ['합계'],
            '기업체수': [industry_summary['기업체수'].sum()],
            '종사자수': [industry_summary['종사자수'].sum()],
            '매출액': [industry_summary['매출액'].sum()]
        })

        # 합계를 맨 위에 추가
        industry_summary = pd.concat([total_row, industry_summary], ignore_index=True)

        # 수치 포맷팅
        industry_summary['기업체수_fmt'] = industry_summary['기업체수'].apply(lambda x: f"{x:,}")
        industry_summary['종사자수_fmt'] = industry_summary['종사자수'].apply(lambda x: f"{x:,}")
        industry_summary['매출액_fmt'] = industry_summary['매출액'].apply(lambda x: f"{x/100000000:.1f}억원" if x >= 100000000 else f"{x/10000:.0f}만원")

        # 시각화 생성 - 4개의 서브플롯 (표1개 + 그래프3개)
        fig = plt.figure(figsize=(24, 16))

        # 1. 표 생성 (좌측 상단)
        ax1 = plt.subplot(2, 2, 1)
        ax1.axis('tight')
        ax1.axis('off')

        # 표 데이터 준비
        table_data = industry_summary[[industry_col, '기업체수_fmt', '종사자수_fmt', '매출액_fmt']].values

        # 긴 산업분류명 줄바꿈 처리
        for i, row in enumerate(table_data):
            industry_name = str(row[0])
            if len(industry_name) > 25:
                # 25자 이상이면 줄바꿈
                table_data[i][0] = industry_name[:25] + '\\n' + industry_name[25:]

        # 표 생성
        table = ax1.table(cellText=table_data,
                         colLabels=['산업분류', '사업체수', '종사자수', '매출액'],
                         cellLoc='center',
                         loc='center',
                         colWidths=[0.4, 0.2, 0.2, 0.2])

        # 표 스타일링
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.8)

        # 헤더 스타일
        for i in range(4):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(weight='bold', color='white', ha='center')

        # 데이터 행 스타일링
        for idx in range(len(table_data)):
            # 산업분류명은 왼쪽 정렬, 숫자는 오른쪽 정렬
            table[(idx + 1, 0)].set_text_props(ha='left')  # 산업분류
            for j in range(1, 4):  # 숫자 컬럼들
                table[(idx + 1, j)].set_text_props(ha='right')  # 우측 정렬

            # 합계 행 스타일 (첫 번째 데이터 행)
            if idx == 0:  # 합계 행
                for i in range(4):
                    table[(idx + 1, i)].set_facecolor('#B4C7E7')
                    table[(idx + 1, i)].set_text_props(weight='bold')
            else:
                # 나머지 행들은 교대로 색상 적용
                color = '#F2F2F2' if idx % 2 == 0 else 'white'
                for i in range(4):
                    table[(idx + 1, i)].set_facecolor(color)

        ax1.set_title('산업분류별 사업체 현황', fontsize=16, fontweight='bold', pad=20)

        # 차트용 데이터 준비 (합계 제외)
        chart_data = industry_summary[industry_summary[industry_col] != '합계'].copy()
        chart_data = chart_data.nlargest(10, '기업체수')  # 상위 10개만

        # 산업분류명 줄임 (그래프용)
        chart_data['산업분류_short'] = chart_data[industry_col].apply(
            lambda x: x[:12] + '...' if len(str(x)) > 12 else str(x)
        )

        # 2. 사업체수 막대그래프 (우측 상단)
        ax2 = plt.subplot(2, 2, 2)
        bars = ax2.bar(range(len(chart_data)), chart_data['기업체수'], color='#4472C4')
        ax2.set_xlabel('산업분류', fontweight='bold')
        ax2.set_ylabel('사업체수', fontweight='bold')
        ax2.set_title('산업분류별 사업체수 (상위 10개)', fontsize=14, fontweight='bold')
        ax2.set_xticks(range(len(chart_data)))
        ax2.set_xticklabels(chart_data['산업분류_short'], rotation=45, ha='right')
        ax2.grid(True, alpha=0.3)

        # 막대 위에 값 표시
        for bar, value in zip(bars, chart_data['기업체수']):
            height = bar.get_height()
            ax2.annotate(f'{value:,}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        # 3. 종사자수 막대그래프 (좌측 하단)
        ax3 = plt.subplot(2, 2, 3)
        bars = ax3.bar(range(len(chart_data)), chart_data['종사자수'], color='#70AD47')
        ax3.set_xlabel('산업분류', fontweight='bold')
        ax3.set_ylabel('종사자수', fontweight='bold')
        ax3.set_title('산업분류별 종사자수 (상위 10개)', fontsize=14, fontweight='bold')
        ax3.set_xticks(range(len(chart_data)))
        ax3.set_xticklabels(chart_data['산업분류_short'], rotation=45, ha='right')
        ax3.grid(True, alpha=0.3)

        # 막대 위에 값 표시
        for bar, value in zip(bars, chart_data['종사자수']):
            height = bar.get_height()
            ax3.annotate(f'{value:,}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        # 4. 매출액 막대그래프 (우측 하단)
        ax4 = plt.subplot(2, 2, 4)
        chart_data['매출액_억'] = chart_data['매출액'] / 100000000
        bars = ax4.bar(range(len(chart_data)), chart_data['매출액_억'], color='#FFC000')
        ax4.set_xlabel('산업분류', fontweight='bold')
        ax4.set_ylabel('매출액(억원)', fontweight='bold')
        ax4.set_title('산업분류별 매출액 (상위 10개)', fontsize=14, fontweight='bold')
        ax4.set_xticks(range(len(chart_data)))
        ax4.set_xticklabels(chart_data['산업분류_short'], rotation=45, ha='right')
        ax4.grid(True, alpha=0.3)

        # 막대 위에 값 표시
        for bar, value in zip(bars, chart_data['매출액_억']):
            height = bar.get_height()
            ax4.annotate(f'{value:.1f}억',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        plt.tight_layout(pad=3.0)

        # 이미지로 변환
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()

        return img_str

    except Exception as e:
        print(f"산업분류별 차트 생성 오류: {str(e)}")
        return None

def render():
    """Flask에서 호출할 메인 렌더링 함수"""
    try:
        # 데이터 로드
        df, sido_list, industry_list, years, months = load_data()

        if df.empty:
            return """
            <div class="container mt-4">
                <h1>기업통계등록부 현황 분석</h1>
                <div class="alert alert-warning">
                    <h4>데이터를 불러올 수 없습니다</h4>
                    <p>다음 사항을 확인해주세요:</p>
                    <ul>
                        <li>1_giup/data 폴더에 집계표 Excel 파일이 있는지 확인</li>
                        <li>파일명이 '집계표_YYYYMM.xlsx' 형식인지 확인</li>
                    </ul>
                </div>
            </div>
            """

        # 기본값으로 최신 년도 선택
        default_year = str(max(years)) if years else '전체'
        default_month = str(max(months)) if months else '전체'

        # 기본 차트 생성
        region_chart = create_region_table_chart(df, default_year, default_month)
        industry_chart = create_industry_table_chart(df, default_year, default_month)

        # HTML 템플릿
        html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>기업통계등록부 현황 분석</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <style>
        .chart-container {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
            padding: 20px;
        }}
        .control-panel {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .loading {{
            display: none;
            text-align: center;
            padding: 20px;
        }}
        .highlight-gyeongbuk {{
            background-color: #1f4e79 !important;
            color: white !important;
            font-weight: bold;
        }}
    </style>
</head>
<body style="background-color: #f5f5f5;">
    <div class="container-fluid">
        <h1 class="text-center my-4 text-primary">
            📊 기업통계등록부 현황 분석
        </h1>

        <!-- 컨트롤 패널 -->
        <div class="control-panel">
            <div class="row">
                <div class="col-md-3">
                    <label for="yearSelect" class="form-label"><strong>분석 년도</strong></label>
                    <select id="yearSelect" class="form-select">
                        <option value="전체">전체 년도</option>
                        {chr(10).join([f'<option value="{year}" {"selected" if str(year) == default_year else ""}>{year}년</option>' for year in years])}
                    </select>
                </div>
                <div class="col-md-3">
                    <label for="monthSelect" class="form-label"><strong>분석 월</strong></label>
                    <select id="monthSelect" class="form-select">
                        <option value="전체">전체 월</option>
                        {chr(10).join([f'<option value="{month}" {"selected" if str(month) == default_month else ""}>{month}월</option>' for month in months])}
                    </select>
                </div>
                <div class="col-md-3 d-flex align-items-end">
                    <button id="updateBtn" class="btn btn-primary btn-lg w-100">
                        🔄 차트 업데이트
                    </button>
                </div>
                <div class="col-md-3 d-flex align-items-end">
                    <button id="exportBtn" class="btn btn-success btn-lg w-100">
                        💾 PDF 내보내기
                    </button>
                </div>
            </div>
        </div>

        <!-- 로딩 메시지 -->
        <div class="loading" id="loadingMsg">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">차트를 생성 중입니다...</p>
        </div>

        <!-- 1. 행정구역별 현황 -->
        <div class="chart-container">
            <h2 class="text-center mb-4">🏢 행정구역별 사업체 현황</h2>
            <div id="regionChart">
                {f'<img src="data:image/png;base64,{region_chart}" class="img-fluid" alt="행정구역별 현황">' if region_chart else '<p class="text-center">차트를 생성할 수 없습니다.</p>'}
            </div>
            <div class="mt-3">
                <small class="text-muted">
                    * 경상북도는 진한 파란색으로 강조 표시됩니다.<br>
                    * 막대그래프는 상위 15개 지역을 표시합니다.
                </small>
            </div>
        </div>

        <!-- 2. 산업분류별 현황 -->
        <div class="chart-container">
            <h2 class="text-center mb-4">🏭 산업분류별 사업체 현황</h2>
            <div id="industryChart">
                {f'<img src="data:image/png;base64,{industry_chart}" class="img-fluid" alt="산업분류별 현황">' if industry_chart else '<p class="text-center">차트를 생성할 수 없습니다.</p>'}
            </div>
            <div class="mt-3">
                <small class="text-muted">
                    * 산업분류는 A_농업, B_광업 등의 대분류로 구분됩니다.<br>
                    * 막대그래프는 상위 15개 업종을 표시합니다.
                </small>
            </div>
        </div>

        <!-- 푸터 -->
        <footer class="text-center mt-5 mb-3">
            <small class="text-muted">
                기업통계등록부 분석 대시보드 | 데이터: {len(df):,}건 |
                최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </small>
        </footer>
    </div>

    <script>
        // 차트 업데이트 함수
        function updateCharts() {{
            const year = document.getElementById('yearSelect').value;
            const month = document.getElementById('monthSelect').value;

            // 로딩 표시
            document.getElementById('loadingMsg').style.display = 'block';
            document.getElementById('updateBtn').disabled = true;

            // AJAX 요청
            $.ajax({{
                url: '/1_giup/api/dash3_update',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({{
                    year: year,
                    month: month
                }}),
                success: function(response) {{
                    if (response.success) {{
                        // 차트 업데이트
                        if (response.region_chart) {{
                            document.getElementById('regionChart').innerHTML =
                                '<img src="data:image/png;base64,' + response.region_chart + '" class="img-fluid" alt="행정구역별 현황">';
                        }}
                        if (response.industry_chart) {{
                            document.getElementById('industryChart').innerHTML =
                                '<img src="data:image/png;base64,' + response.industry_chart + '" class="img-fluid" alt="산업분류별 현황">';
                        }}
                    }} else {{
                        alert('차트 업데이트 중 오류가 발생했습니다: ' + response.error);
                    }}
                }},
                error: function() {{
                    alert('서버 통신 오류가 발생했습니다.');
                }},
                complete: function() {{
                    // 로딩 숨김
                    document.getElementById('loadingMsg').style.display = 'none';
                    document.getElementById('updateBtn').disabled = false;
                }}
            }});
        }}

        // PDF 내보내기 함수
        function exportPDF() {{
            const year = document.getElementById('yearSelect').value;
            const month = document.getElementById('monthSelect').value;

            const filename = prompt('PDF 파일명을 입력하세요:', `기업통계등록부_현황분석_${{year}}_${{month}}`);
            if (filename) {{
                // 버튼 비활성화 및 로딩 표시
                document.getElementById('exportBtn').disabled = true;
                document.getElementById('exportBtn').textContent = '💾 저장 중...';

                // PDF 다운로드 링크 생성
                const downloadUrl = `/1_giup/api/dash3_export_pdf?year=${{year}}&month=${{month}}&filename=${{encodeURIComponent(filename)}}`;

                // 다운로드 링크 클릭 (브라우저가 자동으로 다운로드 처리)
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = filename + '.pdf';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                // 버튼 복원 (약간의 지연 후)
                setTimeout(function() {{
                    document.getElementById('exportBtn').disabled = false;
                    document.getElementById('exportBtn').textContent = '💾 PDF 내보내기';
                    alert('✅ PDF 파일이 다운로드 폴더에 저장되었습니다.\\n서버 백업: 1_giup/output 폴더');
                }}, 1000);
            }}
        }}

        // 이벤트 리스너
        document.getElementById('updateBtn').addEventListener('click', updateCharts);
        document.getElementById('exportBtn').addEventListener('click', exportPDF);

        // 엔터키로 업데이트
        document.addEventListener('keypress', function(event) {{
            if (event.key === 'Enter') {{
                updateCharts();
            }}
        }});
    </script>
</body>
</html>
        """

        return html_template

    except Exception as e:
        return f"""
        <div class="container mt-4">
            <h1>기업통계등록부 현황 분석</h1>
            <div class="alert alert-danger">
                <h4>오류 발생</h4>
                <p>대시보드를 로드하는 중 오류가 발생했습니다:</p>
                <pre>{str(e)}</pre>
            </div>
        </div>
        """

if __name__ == "__main__":
    print("dash3.py 테스트 실행")
    html_content = render()
    print("HTML 생성 완료")