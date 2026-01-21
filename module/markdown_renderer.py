# -*- coding: utf-8 -*-
"""
마크다운 렌더링 모듈
markdown 파일을 HTML로 변환하고 스타일을 적용하는 기능을 제공
"""

import markdown
from pathlib import Path


class MarkdownRenderer:
    """마크다운 파일을 HTML로 렌더링하는 클래스"""

    def __init__(self):
        """마크다운 렌더러 초기화"""
        # 마크다운 파서 설정 (확장 기능 포함)
        self.md = markdown.Markdown(
            extensions=['tables', 'fenced_code', 'toc', 'codehilite'],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'use_pygments': False
                }
            }
        )

    def get_markdown_styles(self):
        """마크다운 콘텐츠용 CSS 스타일 반환"""
        return """
        <style>
            .markdown-content {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
            }
            .markdown-content h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-bottom: 20px;
                font-size: 2.2rem;
            }
            .markdown-content h2 {
                color: #34495e;
                border-bottom: 2px solid #95a5a6;
                padding-bottom: 5px;
                margin-top: 30px;
                margin-bottom: 15px;
                font-size: 1.8rem;
            }
            .markdown-content h3 {
                color: #7f8c8d;
                margin-top: 25px;
                margin-bottom: 10px;
                font-size: 1.4rem;
            }
            .markdown-content h4 {
                color: #8b949e;
                margin-top: 20px;
                margin-bottom: 10px;
                font-size: 1.2rem;
            }
            .markdown-content pre {
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
                margin: 15px 0;
            }
            .markdown-content code {
                background: #ecf0f1;
                color: #e74c3c;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }
            .markdown-content pre code {
                background: transparent;
                color: #ecf0f1;
                padding: 0;
            }
            .markdown-content ul, .markdown-content ol {
                margin: 15px 0;
                padding-left: 30px;
            }
            .markdown-content li {
                margin: 8px 0;
            }
            .markdown-content blockquote {
                border-left: 4px solid #3498db;
                margin: 20px 0;
                padding: 10px 20px;
                background-color: #f8f9fa;
                font-style: italic;
            }
            .markdown-content table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            .markdown-content th, .markdown-content td {
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }
            .markdown-content th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            .markdown-content strong {
                color: #2c3e50;
                font-weight: bold;
            }
            .markdown-content em {
                color: #7f8c8d;
                font-style: italic;
            }
            .markdown-content a {
                color: #3498db;
                text-decoration: none;
            }
            .markdown-content a:hover {
                color: #2980b9;
                text-decoration: underline;
            }
        </style>
        """

    def render_file(self, file_path):
        """
        마크다운 파일을 읽어서 HTML로 렌더링

        Args:
            file_path (Path): 마크다운 파일 경로

        Returns:
            str: 스타일이 적용된 HTML 문자열
        """
        try:
            # 마크다운 파일 읽기
            content = file_path.read_text(encoding='utf-8')

            # HTML로 변환
            html_content = self.md.convert(content)

            # 스타일과 함께 래핑
            styled_content = f"""
            {self.get_markdown_styles()}
            <div class="markdown-content">
                {html_content}
            </div>
            """

            return styled_content

        except Exception as e:
            return f"<p>파일을 읽는 중 오류가 발생했습니다: {str(e)}</p>"

    def render_text(self, markdown_text):
        """
        마크다운 텍스트를 HTML로 렌더링

        Args:
            markdown_text (str): 마크다운 텍스트

        Returns:
            str: 스타일이 적용된 HTML 문자열
        """
        try:
            # HTML로 변환
            html_content = self.md.convert(markdown_text)

            # 스타일과 함께 래핑
            styled_content = f"""
            {self.get_markdown_styles()}
            <div class="markdown-content">
                {html_content}
            </div>
            """

            return styled_content

        except Exception as e:
            return f"<p>마크다운 변환 중 오류가 발생했습니다: {str(e)}</p>"