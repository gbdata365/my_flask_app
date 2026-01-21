# -*- coding: utf-8 -*-
"""
아래아한글(HWP) 문서 생성 유틸리티
====================================

win32com을 사용하여 아래아한글 문서를 생성하고 데이터를 삽입합니다.

주요 기능:
    1. HWP 문서 열기/닫기
    2. 필드에 텍스트 삽입
    3. 표 데이터 삽입
    4. 이미지 삽입
    5. 문서 저장

필수 조건:
    - Windows 운영체제
    - 아래아한글 프로그램 설치
    - pywin32 패키지 설치 (pip install pywin32)

사용 예:
    from module.hwp_utils import HwpDocument

    with HwpDocument() as hwp:
        hwp.open("템플릿.hwp")
        hwp.put_field("제목", "기업통계등록부 분석 보고서")
        hwp.insert_table_data("표1", df)
        hwp.save_as("결과.hwp")

Author: Claude AI Agent
Created: 2024-12-18
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime
import pandas as pd

# Windows 환경에서만 win32com 사용 가능
if sys.platform == 'win32':
    try:
        import win32com.client as win32
        HWP_AVAILABLE = True
    except ImportError:
        HWP_AVAILABLE = False
        print("[WARNING] pywin32가 설치되지 않았습니다. pip install pywin32 로 설치하세요.")
else:
    HWP_AVAILABLE = False


class HwpDocument:
    """
    아래아한글 문서 제어 클래스

    Context Manager 패턴을 지원하여 with 문으로 사용 가능합니다.
    """

    def __init__(self, visible=True):
        """
        HWP 문서 객체 초기화

        Args:
            visible (bool): HWP 창 표시 여부 (기본값: True)
        """
        self.hwp = None
        self.visible = visible
        self.is_open = False

    def __enter__(self):
        """Context Manager 진입"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager 종료"""
        self.close()
        return False

    def connect(self):
        """
        아래아한글 프로그램에 연결

        Returns:
            bool: 연결 성공 여부
        """
        if not HWP_AVAILABLE:
            raise RuntimeError("아래아한글 연결 불가: Windows 환경이 아니거나 pywin32가 설치되지 않았습니다.")

        try:
            self.hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
            self.hwp.XHwpWindows.Item(0).Visible = self.visible
            # 보안 모듈 실행 (API 사용 허용)
            self.hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
            self.is_open = True
            return True
        except Exception as e:
            raise RuntimeError(f"아래아한글 연결 실패: {str(e)}")

    def open(self, filepath):
        """
        HWP 파일 열기

        Args:
            filepath (str): HWP 파일 경로
        """
        if not self.is_open:
            self.connect()

        filepath = str(Path(filepath).resolve())
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

        self.hwp.Open(filepath)

    def create_new(self):
        """
        새 문서 생성
        """
        if not self.is_open:
            self.connect()
        self.hwp.HAction.Run("FileNew")

    def put_field(self, field_name, text):
        """
        필드에 텍스트 삽입

        Args:
            field_name (str): 필드 이름
            text (str): 삽입할 텍스트
        """
        self.hwp.PutFieldText(Field=field_name, Text=str(text))

    def get_field_list(self):
        """
        문서의 모든 필드 목록 조회

        Returns:
            list: 필드 이름 리스트
        """
        field_list = self.hwp.GetFieldList()
        if field_list:
            return field_list.split('\x02')
        return []

    def move_to_field(self, field_name):
        """
        특정 필드로 커서 이동

        Args:
            field_name (str): 필드 이름
        """
        self.hwp.MoveToField(Field=field_name)

    def insert_text(self, text):
        """
        현재 커서 위치에 텍스트 삽입

        Args:
            text (str): 삽입할 텍스트
        """
        self.hwp.HAction.GetDefault("InsertText", self.hwp.HParameterSet.HInsertText.HSet)
        self.hwp.HParameterSet.HInsertText.Text = str(text)
        self.hwp.HAction.Execute("InsertText", self.hwp.HParameterSet.HInsertText.HSet)

    def move_right(self):
        """커서를 오른쪽으로 이동"""
        self.hwp.HAction.Run("MoveRight")

    def move_down(self):
        """커서를 아래로 이동"""
        self.hwp.HAction.Run("MoveDown")

    def set_text_color(self, color):
        """
        텍스트 색상 설정

        Args:
            color (str): 'red', 'blue', 'black' 중 하나
        """
        color_map = {
            'red': "CharShapeTextColorRed",
            'blue': "CharShapeTextColorBlue",
            'black': "CharShapeTextColorBlack"
        }
        if color in color_map:
            self.hwp.HAction.Run(color_map[color])

    def insert_table_data(self, field_name, df, format_func=None):
        """
        표 필드에 DataFrame 데이터 삽입

        Args:
            field_name (str): 표 시작 필드 이름
            df (pd.DataFrame): 삽입할 데이터프레임
            format_func (callable, optional): 셀 값 포맷팅 함수
        """
        self.move_to_field(field_name)
        self.move_right()

        for i in range(len(df)):
            for j in range(len(df.columns)):
                value = df.iloc[i, j]

                # 포맷팅 함수가 있으면 적용
                if format_func:
                    text = format_func(value, i, j)
                else:
                    if pd.isna(value):
                        text = '-'
                    elif isinstance(value, (int, float)):
                        text = f'{value:,.0f}' if value == int(value) else f'{value:,.2f}'
                    else:
                        text = str(value)

                # 증감 표시 색상 처리
                if '▲' in str(text):
                    self.set_text_color('red')
                elif '▼' in str(text):
                    self.set_text_color('blue')
                else:
                    self.set_text_color('black')

                self.insert_text(text)
                self.move_right()

            # 다음 행으로 이동
            self.move_to_field(field_name)
            for k in range(i + 1):
                self.move_down()

    def insert_picture(self, filepath, embedded=True, size_option=3):
        """
        현재 커서 위치에 이미지 삽입

        Args:
            filepath (str): 이미지 파일 경로
            embedded (bool): 문서에 포함 여부 (기본값: True)
            size_option (int): 크기 옵션 (기본값: 3 - 셀에 맞춤)
        """
        filepath = str(Path(filepath).resolve())
        self.hwp.InsertPicture(filepath, Embedded=embedded, sizeoption=size_option)

    def save(self):
        """현재 문서 저장"""
        self.hwp.HAction.Run("FileSave")

    def save_as(self, filepath, format="HWP"):
        """
        다른 이름으로 저장

        Args:
            filepath (str): 저장할 파일 경로
            format (str): 파일 형식 (HWP, HWPX, PDF 등)
        """
        filepath = str(Path(filepath).resolve())

        # 디렉토리 생성
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # 형식에 따른 저장
        if format.upper() == "PDF":
            self.hwp.HAction.GetDefault("FileSaveAsPdf", self.hwp.HParameterSet.HFileOpenSave.HSet)
            self.hwp.HParameterSet.HFileOpenSave.filename = filepath
            self.hwp.HAction.Execute("FileSaveAsPdf", self.hwp.HParameterSet.HFileOpenSave.HSet)
        else:
            self.hwp.HAction.GetDefault("FileSaveAs_S", self.hwp.HParameterSet.HFileOpenSave.HSet)
            self.hwp.HParameterSet.HFileOpenSave.filename = filepath
            self.hwp.HAction.Execute("FileSaveAs_S", self.hwp.HParameterSet.HFileOpenSave.HSet)

    def close(self):
        """HWP 프로그램 종료"""
        if self.hwp:
            try:
                self.hwp.Quit()
            except:
                pass
            self.hwp = None
            self.is_open = False


def create_dashboard_template(output_path, title="기업통계등록부 분석 보고서"):
    """
    대시보드용 HWP 템플릿 파일 생성

    필드가 정의된 기본 HWP 템플릿을 생성합니다.

    Args:
        output_path (str): 저장할 파일 경로
        title (str): 문서 제목

    Returns:
        str: 생성된 파일 경로

    Note:
        이 함수는 기본 구조만 생성합니다.
        세부적인 레이아웃은 한글 프로그램에서 직접 수정해야 합니다.
    """
    if not HWP_AVAILABLE:
        raise RuntimeError("HWP 템플릿 생성 불가: Windows 환경이 아니거나 pywin32가 설치되지 않았습니다.")

    with HwpDocument(visible=False) as hwp:
        # 새 문서 생성
        hwp.create_new()

        # 문서 제목 입력
        hwp.insert_text(f"{title}\n")
        hwp.insert_text(f"작성일: {datetime.now().strftime('%Y년 %m월 %d일')}\n\n")

        # 필드 생성을 위한 안내
        hwp.insert_text("=" * 50 + "\n")
        hwp.insert_text("[안내] 이 템플릿에 필드를 추가하려면:\n")
        hwp.insert_text("1. 한글 프로그램에서 이 파일을 엽니다\n")
        hwp.insert_text("2. 입력 > 필드 메뉴에서 필드를 추가합니다\n")
        hwp.insert_text("3. 필드 이름 예시: 총사업체수, 총종사자수, 표1, 차트1 등\n")
        hwp.insert_text("=" * 50 + "\n\n")

        # 기본 섹션들
        sections = [
            ("1. 주요 지표 요약", ["총사업체수", "총종사자수", "평균HHI", "1인당매출액"]),
            ("2. 지역별 현황", ["표1"]),
            ("3. 시계열 분석", ["차트1"]),
            ("4. 인구 대비 사업체 밀도", ["차트2"]),
            ("5. 주요 인사이트", ["인사이트1", "인사이트2", "인사이트3"])
        ]

        for section_title, fields in sections:
            hwp.insert_text(f"\n{section_title}\n")
            hwp.insert_text("-" * 30 + "\n")
            for field in fields:
                hwp.insert_text(f"[{field} 필드 위치]\n")
            hwp.insert_text("\n")

        # 저장
        hwp.save_as(output_path)

    return output_path


def generate_report_from_data(template_path, output_path, data_dict, charts_dict=None):
    """
    데이터를 사용하여 HWP 보고서 생성

    Args:
        template_path (str): 템플릿 HWP 파일 경로
        output_path (str): 출력 HWP 파일 경로
        data_dict (dict): 필드명 -> 값 매핑
        charts_dict (dict, optional): 차트 필드명 -> 이미지 경로 매핑

    Returns:
        str: 생성된 파일 경로
    """
    if not HWP_AVAILABLE:
        raise RuntimeError("HWP 보고서 생성 불가: Windows 환경이 아니거나 pywin32가 설치되지 않았습니다.")

    with HwpDocument(visible=False) as hwp:
        hwp.open(template_path)

        # 텍스트 필드 채우기
        for field_name, value in data_dict.items():
            try:
                hwp.put_field(field_name, value)
            except:
                pass  # 필드가 없으면 무시

        # 차트 이미지 삽입
        if charts_dict:
            for field_name, image_path in charts_dict.items():
                try:
                    hwp.move_to_field(field_name)
                    hwp.insert_picture(image_path)
                except:
                    pass  # 필드가 없거나 이미지가 없으면 무시

        # 저장
        hwp.save_as(output_path)

    return output_path


# 테스트용 코드
if __name__ == "__main__":
    if HWP_AVAILABLE:
        print("아래아한글 연결 가능")

        # 템플릿 생성 테스트
        test_path = "C:/Users/user/01_claude_project/02_기업체현황/templates/test_template.hwp"
        try:
            create_dashboard_template(test_path)
            print(f"템플릿 생성 완료: {test_path}")
        except Exception as e:
            print(f"템플릿 생성 실패: {e}")
    else:
        print("아래아한글 연결 불가")
