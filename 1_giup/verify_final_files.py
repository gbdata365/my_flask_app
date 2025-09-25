import pandas as pd
from pathlib import Path

def verify_final_files():
    """최종 생성된 집계표 파일들을 검증"""

    data_path = Path(__file__).parent / 'data'
    files = ['집계표_202212_최종.xlsx', '집계표_202312_최종.xlsx', '집계표_202412_최종.xlsx']

    for file_name in files:
        file_path = data_path / file_name
        if file_path.exists():
            print(f"\n{file_name} 검증:")
            df = pd.read_excel(file_path)
            print(f"  - 행 수: {len(df):,}")
            print(f"  - 열 수: {len(df.columns)}")
            print(f"  - 컬럼명: {list(df.columns)}")

            # 주요 합계 검증
            if '기업체수' in df.columns:
                total_business = df['기업체수'].sum()
                print(f"  - 총 기업체수: {total_business:,}")

                # 법인구분코드 합계 검증
                org_cols = ['1', '2', '3', '4', '5']
                if all(col in df.columns for col in org_cols):
                    org_total = df[org_cols].sum().sum()
                    print(f"  - 법인구분코드 합계: {org_total:,} {'OK' if org_total == total_business else 'NG'}")

                # 폐업구분코드 합계 검증
                closure_cols = ['1.1', '2.1', '3.1', '4.1', '99']
                if all(col in df.columns for col in closure_cols):
                    closure_total = df[closure_cols].sum().sum()
                    print(f"  - 폐업구분코드 합계: {closure_total:,} {'OK' if closure_total == total_business else 'NG'}")

                # 산업분류코드 합계 검증
                industry_cols = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S']
                if all(col in df.columns for col in industry_cols):
                    industry_total = df[industry_cols].sum().sum()
                    print(f"  - 산업분류코드 합계: {industry_total:,} {'OK' if industry_total == total_business else 'NG'}")

            # 일자 관련 검증
            date_cols = ['등록일자수', '개업일자수', '폐업일자수']
            if all(col in df.columns for col in date_cols):
                print(f"  - 등록일자수: {df['등록일자수'].sum():,}")
                print(f"  - 개업일자수: {df['개업일자수'].sum():,}")
                print(f"  - 폐업일자수: {df['폐업일자수'].sum():,}")

        else:
            print(f"\n{file_name}: 파일이 존재하지 않습니다.")

if __name__ == "__main__":
    verify_final_files()