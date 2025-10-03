#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""마크다운 파일을 PDF로 변환"""

from markdown_pdf import MarkdownPdf, Section

# PDF 생성
pdf = MarkdownPdf()

# 마크다운 파일 읽기 및 변환
pdf.add_section(Section("20251002.md"))

# PDF 파일 저장
pdf.save("20251002.pdf")

print("PDF file created: 20251002.pdf")
