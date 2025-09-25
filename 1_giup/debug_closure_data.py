import pandas as pd
from pathlib import Path

def debug_closure_data():
    """폐업일자수와 폐업구분코드 분배 문제 디버깅"""

    # 원본 데이터 읽기
    data_path = Path(__file__).parent / 'data'
    base_file = data_path / '복사본 기업통계등록부.xlsx'

    df_base = pd.read_excel(base_file, sheet_name=0, header=0)

    # 컬럼명 매핑
    df_base.columns = [
        '기준년월_시도', '시도', '시군구', '기업체수', '임시및일용근로자수', '상용근로자수',
        '매출액', '근로자수', '총종사자수', '평균종사자수', '폐업일자수'
    ]

    # 숫자 컬럼 변환
    numeric_cols = ['기업체수', '임시및일용근로자수', '상용근로자수', '매출액', '근로자수', '총종사자수', '평균종사자수', '폐업일자수']
    for col in numeric_cols:
        df_base[col] = pd.to_numeric(df_base[col], errors='coerce').fillna(0)

    print("=== 원본 데이터 첫 5행 확인 ===")
    print(df_base[['시도', '시군구', '기업체수', '폐업일자수']].head())

    # 첫 번째 행 상세 분석
    first_row = df_base.iloc[0]
    total_businesses = first_row['기업체수']
    closure_businesses = first_row['폐업일자수']

    print(f"\n=== 첫 번째 행 ({first_row['시도']} {first_row['시군구']}) 분석 ===")
    print(f"기업체수: {total_businesses:,}")
    print(f"폐업일자수: {closure_businesses:,}")

    if closure_businesses > 0:
        # 정상영업 기업수 = 전체 - 폐업일자가 있는 기업
        normal_businesses = total_businesses - closure_businesses
        print(f"정상영업 기업수 (1.1): {normal_businesses:,}")

        # 폐업일자가 있는 기업들을 나머지 코드로 분배
        closure_codes = ['2.1', '3.1', '4.1', '99']
        closure_ratios_for_closed = [0.3, 0.4, 0.1, 0.2]

        closure_counts = []
        for i, ratio in enumerate(closure_ratios_for_closed[:-1]):
            count = int(closure_businesses * ratio)
            closure_counts.append(count)

        # 마지막은 나머지로 계산
        last_count = closure_businesses - sum(closure_counts)
        closure_counts.append(max(0, last_count))

        print(f"폐업일자가 있는 기업들의 분배:")
        for code, count in zip(closure_codes, closure_counts):
            print(f"  {code}: {count:,}")

        total_closure_distributed = sum(closure_counts)
        print(f"폐업구분코드 분배 총합: {total_closure_distributed:,}")
        print(f"폐업일자수와 일치: {'OK' if total_closure_distributed == closure_businesses else 'NG'}")

        total_all_codes = normal_businesses + total_closure_distributed
        print(f"전체 폐업구분코드 합계: {total_all_codes:,}")
        print(f"기업체수와 일치: {'OK' if total_all_codes == total_businesses else 'NG'}")

if __name__ == "__main__":
    debug_closure_data()