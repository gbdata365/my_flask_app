import pandas as pd
import numpy as np
import random
from pathlib import Path

def generate_timeseries_data():
    """복사본 기업통계등록부.xlsx 기반으로 3개년도 시계열 집계표 생성"""

    print("시계열 집계표 생성 시작")
    print("=" * 50)

    # 기본 데이터 읽기
    data_path = Path(__file__).parent / 'data'
    base_file = data_path / '복사본 기업통계등록부.xlsx'

    # 기본 데이터 읽기 (header=4 기준)
    df_base = pd.read_excel(base_file, sheet_name=0, header=4)

    print(f"기본 데이터 로드: {len(df_base)}행")
    print(f"컬럼: {list(df_base.columns)}")

    # 컬럼명 정리 (숫자로 된 컬럼들을 의미있는 이름으로 변경)
    df_base.columns = [
        '기준년월', '시도', '시군구', '기업체수', '임시및일용근로자수', '상용근로자수',
        '매출액', '근로자수', '총종사자수', '평균종사자수', '전년동월'
    ]

    # 숫자 컬럼들의 데이터 타입 변환
    numeric_cols = ['기업체수', '임시및일용근로자수', '상용근로자수', '매출액', '근로자수', '총종사자수', '평균종사자수', '전년동월']
    for col in numeric_cols:
        if col in df_base.columns:
            # 문자열인 경우 숫자로 변환
            df_base[col] = pd.to_numeric(df_base[col], errors='coerce').fillna(0)

    # 3개년도별 집계표 생성
    years = ['202212', '202312', '202412']

    for year_month in years:
        print(f"\n{year_month} 집계표 생성 중...")

        # 기본 데이터 복사
        df_year = df_base.copy()
        df_year['기준년월'] = year_month

        # 년도에 따른 증감률 적용 (2022 → 2023 → 2024로 갈수록 약간 증가)
        if year_month == '202212':
            growth_rate = 0.95  # 2022년은 기준보다 5% 적게
        elif year_month == '202312':
            growth_rate = 1.0   # 2023년은 기준
        else:  # 202412
            growth_rate = 1.05  # 2024년은 5% 증가

        # 수치 데이터에 증감률 적용
        numeric_cols = ['기업체수', '임시및일용근로자수', '상용근로자수', '매출액', '근로자수', '총종사자수', '평균종사자수']
        for col in numeric_cols:
            if col in df_year.columns:
                # 약간의 랜덤 변동도 추가 (±5%)
                random_factor = np.random.normal(1.0, 0.05, len(df_year))
                df_year[col] = (df_year[col] * growth_rate * random_factor).round().astype(int)

        # 법인구분코드별 분배 (1:개인사업자가 가장 많도록)
        total_businesses = df_year['기업체수'].sum()

        # 법인구분코드 비율 설정 (개인사업자가 가장 많도록)
        org_ratios = {
            1: 0.65,  # 개인사업자 65%
            2: 0.25,  # 회사법인 25%
            3: 0.06,  # 회사외법인 6%
            4: 0.03,  # 기관및단체 3%
            5: 0.01   # 국가.지방자치단체 1%
        }

        # 각 지역별로 법인구분코드별 기업수 분배
        for idx, row in df_year.iterrows():
            business_count = row['기업체수']

            # 법인구분코드별 분배
            for code, ratio in org_ratios.items():
                # 약간의 랜덤 변동 추가
                actual_ratio = ratio * np.random.normal(1.0, 0.1)
                actual_ratio = max(0, min(1, actual_ratio))  # 0-1 범위로 제한
                df_year.loc[idx, str(code)] = int(business_count * actual_ratio)

        # 법인구분코드합계 계산
        df_year['법인구분코드합계'] = df_year[['1', '2', '3', '4', '5']].sum(axis=1)

        # 폐업구분코드별 분배 (폐업일자 개수 기반)
        # 폐업일자가 있는 기업의 비율을 시뮬레이션
        closure_ratios = {
            '1.1': 0.85,  # 정상영업 85%
            '2.1': 0.05,  # 휴업중 5%
            '3.1': 0.03,  # 폐업중 3%
            '4.1': 0.02,  # 주소변환 2%
            '99': 0.05    # 기타 5%
        }

        for idx, row in df_year.iterrows():
            business_count = row['기업체수']

            # 폐업구분코드별 분배
            for code, ratio in closure_ratios.items():
                # 약간의 랜덤 변동 추가
                actual_ratio = ratio * np.random.normal(1.0, 0.1)
                actual_ratio = max(0, min(1, actual_ratio))
                df_year.loc[idx, code] = int(business_count * actual_ratio)

        # 산업분류코드별 분배
        industry_codes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S']
        industry_ratios = {
            'A': 0.05, 'B': 0.02, 'C': 0.25, 'D': 0.03, 'E': 0.02, 'F': 0.08, 'G': 0.15,
            'H': 0.06, 'I': 0.08, 'J': 0.05, 'K': 0.03, 'L': 0.04, 'M': 0.08, 'N': 0.05,
            'O': 0.02, 'P': 0.03, 'Q': 0.04, 'R': 0.02, 'S': 0.01
        }

        for idx, row in df_year.iterrows():
            business_count = row['기업체수']

            # 산업분류코드별 분배
            for code, ratio in industry_ratios.items():
                actual_ratio = ratio * np.random.normal(1.0, 0.1)
                actual_ratio = max(0, min(1, actual_ratio))
                df_year.loc[idx, code] = int(business_count * actual_ratio)

        # 컬럼 순서 정리
        base_columns = [
            '기준년월', '시도', '시군구', '기업체수', '임시및일용근로자수', '상용근로자수',
            '매출액', '근로자수', '총종사자수', '평균종사자수', '전년동월'
        ]

        org_code_columns = ['1', '2', '3', '4', '5', '법인구분코드합계']
        closure_code_columns = ['1.1', '2.1', '3.1', '4.1', '99']
        industry_code_columns = industry_codes

        final_columns = base_columns + org_code_columns + closure_code_columns + industry_code_columns

        # 존재하지 않는 컬럼은 0으로 채움
        for col in final_columns:
            if col not in df_year.columns:
                df_year[col] = 0

        # 최종 데이터프레임 생성
        df_final = df_year[final_columns]

        # 컬럼명 변경 (기준년월_시도로)
        df_final = df_final.rename(columns={'기준년월': '기준년월_시도'})

        # Excel 파일로 저장
        output_file = data_path / f'집계표_{year_month}.xlsx'
        df_final.to_excel(output_file, index=False, engine='openpyxl')

        print(f"저장 완료: {output_file}")
        print(f"  - 총 {len(df_final)}행, {len(df_final.columns)}열")
        print(f"  - 총 기업체수: {df_final['기업체수'].sum():,}개")
        print(f"  - 법인구분코드별: 1({df_final['1'].sum():,}) 2({df_final['2'].sum():,}) 3({df_final['3'].sum():,}) 4({df_final['4'].sum():,}) 5({df_final['5'].sum():,})")

    print(f"\n시계열 집계표 생성 완료!")
    print(f"생성된 파일: 집계표_202212.xlsx, 집계표_202312.xlsx, 집계표_202412.xlsx")

if __name__ == "__main__":
    generate_timeseries_data()