# -*- coding: utf-8 -*-
"""
PDF 생성 모듈
dash3 데이터를 PDF 형태로 내보내는 기능을 제공
"""

import os
import re
import tempfile
import base64
import shutil
import urllib.parse
from pathlib import Path


class PDFGenerator:
    """PDF 생성을 담당하는 클래스"""

    def __init__(self):
        """PDF 생성기 초기화"""
        self.korean_font_name = self._register_korean_font()

    def _register_korean_font(self):
        """
        PDF 생성을 위한 한글 폰트 등록

        Returns:
            str: 등록된 폰트명 또는 기본 폰트명
        """
        try:
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.pdfbase import pdfmetrics

            # Windows 한글 폰트 경로들
            font_paths = [
                'C:/Windows/Fonts/malgun.ttf',  # 맑은 고딕
                'C:/Windows/Fonts/gulim.ttc',   # 굴림
                'C:/Windows/Fonts/batang.ttc',  # 바탕
            ]

            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('KoreanFont', font_path))
                        print(f"한글 폰트 등록 성공: {font_path}")
                        return 'KoreanFont'
                    except Exception as fe:
                        print(f"폰트 등록 실패 {font_path}: {fe}")
                        continue

            print("한글 폰트 등록 실패, 기본 폰트 사용")
            return 'Helvetica'

        except Exception as e:
            print(f"폰트 등록 중 오류: {e}")
            return 'Helvetica'

    def create_pdf_content(self, region_chart, industry_chart, year, month):
        """
        PDF 내용 생성

        Args:
            region_chart (str): 지역별 차트 이미지 데이터
            industry_chart (str): 산업별 차트 이미지 데이터
            year (str): 년도
            month (str): 월

        Returns:
            list: PDF 콘텐츠 스토리
        """
        from reportlab.platypus import Paragraph, Spacer, Image, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch

        story = []
        styles = getSampleStyleSheet()

        # 한글 제목 스타일 정의
        korean_title_style = ParagraphStyle(
            'KoreanTitle',
            parent=styles['Title'],
            fontName=self.korean_font_name,
            fontSize=18,
            spaceAfter=30,
            alignment=1  # 중앙 정렬
        )

        korean_heading_style = ParagraphStyle(
            'KoreanHeading',
            parent=styles['Heading1'],
            fontName=self.korean_font_name,
            fontSize=14,
            spaceAfter=20,
            alignment=1  # 중앙 정렬
        )

        # 제목 추가
        title_text = f"기업통계등록부 현황 분석<br/>({year}년 {month}월)"
        title = Paragraph(title_text, korean_title_style)
        story.append(title)
        story.append(Spacer(1, 0.3*inch))

        # 지역별 현황 차트
        if region_chart:
            section_title = Paragraph("1. 행정구역별 사업체 현황", korean_heading_style)
            story.append(section_title)
            story.append(Spacer(1, 0.2*inch))

            # 차트 이미지 처리
            region_img_data = base64.b64decode(region_chart)
            region_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            region_temp.write(region_img_data)
            region_temp.close()

            region_image = Image(region_temp.name, width=7*inch, height=4.2*inch)
            story.append(region_image)
            story.append(PageBreak())

        # 산업별 현황 차트
        if industry_chart:
            section_title = Paragraph("2. 산업분류별 사업체 현황", korean_heading_style)
            story.append(section_title)
            story.append(Spacer(1, 0.2*inch))

            industry_img_data = base64.b64decode(industry_chart)
            industry_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            industry_temp.write(industry_img_data)
            industry_temp.close()

            industry_image = Image(industry_temp.name, width=7*inch, height=4.2*inch)
            story.append(industry_image)

        return story

    def generate_pdf(self, region_chart, industry_chart, year, month, filename, output_dir):
        """
        PDF 파일을 생성하고 다운로드 가능한 파일 경로를 반환

        Args:
            region_chart (str): 지역별 차트 이미지 데이터
            industry_chart (str): 산업별 차트 이미지 데이터
            year (str): 년도
            month (str): 월
            filename (str): 파일명
            output_dir (Path): 출력 디렉토리

        Returns:
            str: 임시 파일 경로
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate

        # 파일명 처리
        filename = urllib.parse.unquote(filename, encoding='utf-8')
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

        # 출력 디렉토리 생성
        output_dir.mkdir(exist_ok=True)

        # PDF 파일 경로 생성
        pdf_filename = f"{filename}.pdf" if not filename.endswith('.pdf') else filename
        pdf_path = output_dir / pdf_filename

        # PDF 생성
        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, topMargin=72, bottomMargin=72)
        story = self.create_pdf_content(region_chart, industry_chart, year, month)

        doc.build(story)

        # 클라이언트 다운로드용 임시 파일 생성
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        shutil.copy2(str(pdf_path), temp_file.name)

        return temp_file.name, pdf_filename