import pandas as pd
from pathlib import Path

def check_generated_file():
    """생성된 202412 파일의 첫 번째 행 확인"""

    data_path = Path(__file__).parent / 'data'
    file_path = data_path / '집계표_202412_최종.xlsx'

    if file_path.exists():
        df = pd.read_excel(file_path)

        print("=== 202412 생성 파일 첫 번째 행 확인 ===")
        first_row = df.iloc[0]

        print(f"시도: {first_row['시도']}")
        print(f"시군구: {first_row['시군구']}")
        print(f"기업체수: {first_row['기업체수']:,}")
        print(f"폐업일자수: {first_row['폐업일자수']:,}")

        print(f"\n폐업구분코드 분배:")
        print(f"1.1 (정상영업): {first_row['1.1']:,}")
        print(f"2.1: {first_row['2.1']:,}")
        print(f"3.1: {first_row['3.1']:,}")
        print(f"4.1: {first_row['4.1']:,}")
        print(f"99: {first_row['99']:,}")

        closure_total = first_row['1.1'] + first_row['2.1'] + first_row['3.1'] + first_row['4.1'] + first_row['99']
        print(f"\n폐업구분코드 합계: {closure_total:,}")
        print(f"기업체수와 일치: {'OK' if closure_total == first_row['기업체수'] else 'NG'}")

        # 폐업일자가 있는 기업들의 분배 확인
        closure_related = first_row['2.1'] + first_row['3.1'] + first_row['4.1'] + first_row['99']
        print(f"\n폐업관련 코드 합계 (2.1+3.1+4.1+99): {closure_related:,}")
        print(f"폐업일자수와 일치: {'OK' if closure_related == first_row['폐업일자수'] else 'NG'}")

        if closure_related != first_row['폐업일자수']:
            print(f"*** 문제 발견: 폐업관련 코드 합계({closure_related})가 폐업일자수({first_row['폐업일자수']})와 다름")
    else:
        print("202412 파일이 존재하지 않습니다.")

if __name__ == "__main__":
    check_generated_file()