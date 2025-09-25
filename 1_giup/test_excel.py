import pandas as pd
import os

# Excel 파일 경로
file_path = r'분기 기업통계등록부(사업자등록번호 기준) 데이터샘플.xlsx'

print("파일 존재 여부:", os.path.exists(file_path))

# 다양한 헤더 위치로 시도
for header_row in range(5):
    try:
        df = pd.read_excel(file_path, header=header_row)
        print(f"\n=== 헤더 {header_row}행으로 읽기 ===")
        print(f"데이터 형태: {df.shape}")
        print("컬럼명 (처음 10개):", list(df.columns)[:10])

        # 시도, 시군구 컬럼이 있는지 확인
        for col in df.columns:
            if '시도' in str(col) or '지역' in str(col) or '시군' in str(col):
                print(f"지역 관련 컬럼 발견: {col}")
                if df[col].notna().sum() > 0:
                    print(f"  -> 고유값: {sorted(df[col].dropna().unique())}")

        # 처음 3행 데이터 확인
        print("처음 3행 데이터:")
        for i in range(min(3, len(df))):
            print(f"행 {i}: {[str(x)[:30] + '...' if len(str(x)) > 30 else str(x) for x in df.iloc[i].values[:5]]}")

    except Exception as e:
        print(f"헤더 {header_row}행으로 읽기 실패: {e}")

print("\n=== 전체 시트 확인 ===")
try:
    xl_file = pd.ExcelFile(file_path)
    print("시트 목록:", xl_file.sheet_names)
except Exception as e:
    print(f"시트 확인 실패: {e}")