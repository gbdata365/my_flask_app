# -*- coding: utf-8 -*-
"""
마크다운을 PDF로 변환하는 스크립트
study_guide.md → study.pdf
"""

import re
from pathlib import Path
from fpdf import FPDF, XPos, YPos

class StudyPDF(FPDF):
    """한글 지원 PDF 클래스"""

    def __init__(self):
        super().__init__()
        self.font_name = "helvetica"  # 기본값

        # 맑은 고딕 폰트 등록
        font_path = "C:/Windows/Fonts/malgun.ttf"
        bold_font_path = "C:/Windows/Fonts/malgunbd.ttf"

        if Path(font_path).exists():
            self.add_font("malgun", "", font_path)
            if Path(bold_font_path).exists():
                self.add_font("malgun", "B", bold_font_path)
            else:
                self.add_font("malgun", "B", font_path)
            self.font_name = "malgun"
        else:
            print("맑은 고딕 폰트를 찾을 수 없습니다. 기본 폰트 사용")

    def header(self):
        """페이지 헤더"""
        self.set_font(self.font_name, 'B', 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, '인구통계 대시보드 프로젝트 교육 가이드', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        self.ln(5)

    def footer(self):
        """페이지 푸터"""
        self.set_y(-15)
        self.set_font(self.font_name, '', 9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'- {self.page_no()} -', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')

    def chapter_title(self, title, level=1):
        """제목 출력"""
        if level == 1:
            self.set_font(self.font_name, 'B', 18)
            self.set_text_color(0, 51, 102)
        elif level == 2:
            self.set_font(self.font_name, 'B', 14)
            self.set_text_color(0, 102, 153)
        elif level == 3:
            self.set_font(self.font_name, 'B', 12)
            self.set_text_color(51, 51, 51)
        else:
            self.set_font(self.font_name, 'B', 11)
            self.set_text_color(51, 51, 51)

        self.multi_cell(0, 8, title)
        self.ln(2)

    def body_text(self, text):
        """본문 텍스트 출력"""
        self.set_font(self.font_name, '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def code_block(self, code):
        """코드 블록 출력"""
        self.set_fill_color(245, 245, 245)
        self.set_font(self.font_name, '', 8)
        self.set_text_color(51, 51, 51)

        lines = code.split('\n')
        for line in lines:
            # 긴 줄 자르기
            display_line = '  ' + line[:85]
            self.cell(0, 5, display_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(2)

    def table_row(self, cells, is_header=False):
        """테이블 행 출력"""
        if is_header:
            self.set_font(self.font_name, 'B', 9)
            self.set_fill_color(220, 230, 240)
        else:
            self.set_font(self.font_name, '', 9)
            self.set_fill_color(255, 255, 255)

        self.set_text_color(0, 0, 0)

        col_width = (self.w - 20) / len(cells) if cells else self.w - 20
        for cell in cells:
            self.cell(col_width, 7, str(cell)[:30], border=1, fill=True)
        self.ln()


def parse_markdown(md_content):
    """마크다운 파싱하여 요소 리스트 반환"""
    elements = []
    lines = md_content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # 빈 줄
        if not line.strip():
            i += 1
            continue

        # 제목 (# ~ ####)
        if line.startswith('####'):
            elements.append(('h4', line[4:].strip()))
        elif line.startswith('###'):
            elements.append(('h3', line[3:].strip()))
        elif line.startswith('##'):
            elements.append(('h2', line[2:].strip()))
        elif line.startswith('#'):
            elements.append(('h1', line[1:].strip()))

        # 코드 블록
        elif line.strip().startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            elements.append(('code', '\n'.join(code_lines)))

        # 테이블
        elif '|' in line and line.strip().startswith('|'):
            table_rows = []
            while i < len(lines) and '|' in lines[i]:
                row = lines[i]
                if '---' not in row:
                    cells = [c.strip() for c in row.split('|')[1:-1]]
                    if cells:
                        table_rows.append(cells)
                i += 1
            if table_rows:
                elements.append(('table', table_rows))
            continue

        # 구분선
        elif line.strip() == '---':
            elements.append(('hr', ''))

        # 일반 텍스트
        else:
            text_lines = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith('#') and not lines[i + 1].startswith('```') and '|' not in lines[i + 1]:
                i += 1
                text_lines.append(lines[i])
            text = ' '.join(text_lines)
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            text = re.sub(r'`(.+?)`', r'\1', text)
            text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
            elements.append(('text', text.strip()))

        i += 1

    return elements


def create_pdf(md_file, pdf_file):
    """마크다운 파일을 PDF로 변환"""

    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    pdf = StudyPDF()
    pdf.add_page()

    # 표지
    pdf.set_font(pdf.font_name, 'B', 28)
    pdf.set_text_color(0, 51, 102)
    pdf.ln(40)
    pdf.multi_cell(0, 15, '인구통계 대시보드\n프로젝트 교육 가이드', align='C')
    pdf.ln(20)

    pdf.set_font(pdf.font_name, '', 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, '01_population 인구통계 분석 시스템', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(40)

    pdf.set_font(pdf.font_name, '', 12)
    pdf.cell(0, 10, '작성일: 2026-01-11', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.cell(0, 10, '대상: 신규 담당자 및 개발자', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

    # 본문 시작
    pdf.add_page()

    elements = parse_markdown(md_content)

    for elem_type, content in elements:
        if pdf.get_y() > 260:
            pdf.add_page()

        if elem_type == 'h1':
            pdf.add_page()
            pdf.chapter_title(content, 1)
        elif elem_type == 'h2':
            pdf.ln(5)
            pdf.chapter_title(content, 2)
        elif elem_type == 'h3':
            pdf.chapter_title(content, 3)
        elif elem_type == 'h4':
            pdf.chapter_title(content, 4)
        elif elem_type == 'code':
            pdf.code_block(content)
        elif elem_type == 'table':
            if content:
                is_header = True
                for row in content:
                    pdf.table_row(row, is_header)
                    is_header = False
                pdf.ln(3)
        elif elem_type == 'hr':
            pdf.ln(3)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
        elif elem_type == 'text':
            if content:
                pdf.body_text(content)

    pdf.output(pdf_file)
    print(f"PDF 생성 완료: {pdf_file}")


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    md_file = base_dir / "study_guide.md"
    pdf_file = base_dir / "study.pdf"

    create_pdf(md_file, pdf_file)
