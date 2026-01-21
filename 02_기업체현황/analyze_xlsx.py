# -*- coding: utf-8 -*-
"""
엑셀 파일 구조 분석 스크립트
"""

import sys
import pandas as pd
from pathlib import Path
from loguru import logger

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_excel(file_path: str):
    """엑셀 파일의 구조를 분석"""
    print("\n" + "=" * 80)
    print(f"파일: {Path(file_path).name}")
    print("=" * 80)

    try:
        xl = pd.ExcelFile(file_path)
        print(f"\n시트 개수: {len(xl.sheet_names)}")
        print(f"시트 목록: {xl.sheet_names}")

        for sheet_name in xl.sheet_names:
            print(f"\n{'─' * 80}")
            print(f"시트명: {sheet_name}")
            print(f"{'─' * 80}")

            df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
            print(f"행 수: {len(df)}, 열 수: {len(df.columns)}")

            # 처음 10행 출력
            print("\n처음 10행:")
            print(df.head(10).to_string())

    except Exception as e:
        logger.error(f"파일 읽기 실패: {e}")

def main():
    base_dir = Path(__file__).parent / "data"

    files = [
        "(수정)집계표_24년1분기.xlsx",
        "2. 분기_기업통계등록부_표준화 연계 레이아웃.xlsx",
        "코드.xlsx"
    ]

    for file_name in files:
        file_path = base_dir / file_name
        if file_path.exists():
            analyze_excel(str(file_path))
        else:
            print(f"\n파일 없음: {file_path}")

if __name__ == '__main__':
    main()
