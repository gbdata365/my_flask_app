# -*- coding: utf-8 -*-
"""
레이아웃 파일에서 컬럼 매핑 정보 추출
"""

import sys
import pandas as pd
from pathlib import Path
import json

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def extract_layout_mapping(file_path: str, sheet_name: str):
    """레이아웃 파일에서 컬럼 매핑 추출"""
    print(f"\n{'=' * 80}")
    print(f"시트: {sheet_name}")
    print('=' * 80)

    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    # 헤더 행 찾기 (번호, 영문항목명 등이 있는 행)
    header_row = None
    for idx, row in df.iterrows():
        if '번호' in str(row.values):
            header_row = idx
            break

    if header_row is None:
        print("헤더를 찾을 수 없습니다.")
        return None

    print(f"헤더 행: {header_row}")
    print(f"헤더: {df.iloc[header_row].tolist()}")

    # 헤더 다음 행부터 데이터
    data_df = df.iloc[header_row + 1:].copy()
    data_df.columns = df.iloc[header_row]

    # NaN 행 제거
    data_df = data_df.dropna(how='all')

    print(f"\n추출된 컬럼 매핑 ({len(data_df)}개):")
    print("-" * 80)

    mappings = []
    for idx, row in data_df.iterrows():
        번호 = row.get('번호', '')
        if pd.isna(번호) or 번호 == '':
            continue

        영문표준화전 = row.get('영문항목명(표준화 전)', '')
        영문표준화 = row.get('영문항목명(표준화)', '')
        한글표준화전 = row.get('한글항목명(표준화 전)', '')
        한글표준화 = row.get('한글항목명(표준화)', '')
        속성 = row.get('속성', '')
        길이 = row.get('길이', '')
        항목설명 = row.get('항목설명', '')

        mapping = {
            '번호': 번호,
            '영문명(표준화전)': 영문표준화전,
            '영문명': 영문표준화,
            '한글명(표준화전)': 한글표준화전,
            '한글명': 한글표준화,
            '속성': 속성,
            '길이': 길이,
            '설명': 항목설명
        }
        mappings.append(mapping)

        print(f"{번호:3} | {영문표준화:20} | {한글표준화:20} | {속성:10} | {길이}")

    return mappings

def main():
    layout_file = Path(__file__).parent / "data" / "2. 분기_기업통계등록부_표준화 연계 레이아웃.xlsx"

    if not layout_file.exists():
        print(f"파일 없음: {layout_file}")
        return

    # 사업자등록기준 시트
    mappings_bizrno = extract_layout_mapping(
        str(layout_file),
        "분기기업통계등록부_사업자등록기준"
    )

    # 대표자기준 시트
    mappings_rep = extract_layout_mapping(
        str(layout_file),
        "분기기업통계등록부_대표자기준"
    )

    # JSON으로 저장
    result = {
        '사업자등록기준': mappings_bizrno,
        '대표자기준': mappings_rep
    }

    output_file = Path(__file__).parent / "column_mappings.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n\n매핑 정보 저장: {output_file}")

if __name__ == '__main__':
    main()
