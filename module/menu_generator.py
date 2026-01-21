# -*- coding: utf-8 -*-
"""
동적 메뉴 생성 모듈
카테고리 폴더를 검색하고 메뉴 항목을 자동으로 생성하는 기능을 제공
"""

import re
from pathlib import Path


class MenuGenerator:
    """동적 메뉴 생성을 담당하는 클래스"""

    @staticmethod
    def get_category_folders():
        """
        숫자로 시작하는 카테고리 폴더 이름들을 반환

        Returns:
            list: 정렬된 폴더 이름 리스트
        """
        folders = []
        current_dir = Path(".")

        # 현재 디렉토리에서 숫자로 시작하는 폴더들을 찾음
        for path in current_dir.iterdir():
            if path.is_dir() and re.match(r"^\d+", path.name):
                folders.append(path.name)

        return sorted(folders)

    @staticmethod
    def get_category_menu_items(category_base, category_name=None):
        """
        특정 카테고리의 메뉴 항목들을 동적으로 생성

        Args:
            category_base (Path): 카테고리 폴더 경로 (예: 01_population)
            category_name (str): 카테고리 이름 (없으면 폴더명 사용)

        Returns:
            list: 메뉴 항목 딕셔너리 리스트
        """
        menu_items = []

        # 카테고리 이름 결정
        if category_name is None:
            category_name = category_base.name

        # markdown_docs 폴더의 .md 파일들 처리 (index.md 우선)
        md_dir = category_base / "markdown_docs"
        if md_dir.exists():
            md_files = sorted(md_dir.glob("*.md"))

            # index.md를 맨 앞으로 정렬
            index_file = None
            other_files = []

            for md_file in md_files:
                if md_file.stem == 'index':
                    index_file = md_file
                else:
                    other_files.append(md_file)

            # index.md 먼저, 나머지는 알파벳 순
            ordered_files = [index_file] + other_files if index_file else other_files

            for md_file in ordered_files:
                display_name = md_file.stem.replace('_', ' ')
                menu_items.append({
                    'name': display_name,
                    'url': f'/{category_name}/markdown/{md_file.stem}',
                    'type': 'markdown'
                })

        # html_docs 폴더의 .html 파일들 처리
        html_dir = category_base / "html_docs"
        if html_dir.exists():
            for html_file in sorted(html_dir.glob("*.html")):
                display_name = html_file.stem.replace('_', ' ')
                menu_items.append({
                    'name': display_name,
                    'url': f'/{category_name}/html/{html_file.stem}',
                    'type': 'html'
                })

        # routes 폴더의 .py 파일들 처리
        # 파일명이 곧 메뉴명 (하드코딩 없음)
        routes_dir = category_base / "routes"
        if routes_dir.exists():
            py_files = sorted(routes_dir.glob("*.py"))

            for py_file in py_files:
                # __init__.py와 _로 시작하는 파일들은 제외
                if py_file.name != "__init__.py" and not py_file.name.startswith("_"):
                    stem = py_file.stem
                    # 파일명을 메뉴명으로 사용 (언더스코어 → 공백)
                    display_name = stem.replace('_', ' ')
                    menu_items.append({
                        'name': display_name,
                        'url': f'/{category_name}/routes/{stem}',
                        'type': 'python'
                    })

        return menu_items

    # 하위 호환성을 위한 별칭
    @staticmethod
    def get_giup_menu_items(giup_base):
        """1_giup용 별칭 (하위 호환성)"""
        return MenuGenerator.get_category_menu_items(giup_base, "1_giup")

    @staticmethod
    def get_main_menu_items():
        """
        메인 페이지용 카테고리 메뉴 항목들을 생성

        Returns:
            list: 메인 메뉴 항목 딕셔너리 리스트
        """
        folders = MenuGenerator.get_category_folders()
        menu_items = []

        for folder in folders:
            menu_items.append({
                'name': folder,
                'url': f'/{folder}'
            })

        return menu_items

    @staticmethod
    def generate_navbar_html(menu_items, current_filename=None, category_name=""):
        """
        네비게이션 바 HTML을 생성

        Args:
            menu_items (list): 메뉴 항목 리스트
            current_filename (str): 현재 활성화된 파일명
            category_name (str): 카테고리 이름

        Returns:
            str: 네비게이션 바 HTML
        """
        # 헤더 네비게이션 바
        nav_html = f"""
        <style>
            .injected-header {{
                background: linear-gradient(135deg, #1243A6 0%, #1D64F2 100%);
                color: white;
                padding: 0.75rem 1rem;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            }}
            .injected-header-content {{
                max-width: 1800px;
                margin: 0 auto;
                display: flex;
                align-items: center;
            }}
            .injected-header h1 {{
                margin: 0;
                font-size: 1.25rem;
                font-weight: 600;
            }}
            .injected-header h1 a {{
                color: white;
                text-decoration: none;
            }}
            .injected-nav {{
                display: flex;
                gap: 0.5rem;
                margin-left: 2rem;
            }}
            .injected-nav a {{
                color: rgba(255,255,255,0.8);
                text-decoration: none;
                padding: 0.4rem 0.8rem;
                border-radius: 4px;
                font-size: 0.9rem;
                transition: all 0.3s;
            }}
            .injected-nav a:hover {{
                background: rgba(255,255,255,0.2);
                color: white;
            }}
            .injected-nav a.active {{
                background: #F24822;
                color: white;
                font-weight: 500;
            }}
        </style>
        <header class="injected-header">
            <div class="injected-header-content">
                <h1><a href="/{category_name}">{category_name}</a></h1>
                <nav class="injected-nav">
        """

        # 메뉴 항목들 추가
        for item in menu_items:
            # 현재 파일 활성화 체크
            is_active = current_filename and current_filename == item['name']
            active_class = 'active' if is_active else ''

            # 타입별 아이콘 설정
            icon = '📄' if item.get('type') == 'markdown' else '🌐' if item.get('type') == 'html' else '⚙️'

            nav_html += f"""
                    <a class="{active_class}" href="{item['url']}" data-url="{item['url']}">
                        {icon} {item['name']}
                    </a>
            """

        nav_html += """
                </nav>
            </div>
        </header>
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                const currentPath = window.location.pathname;
                document.querySelectorAll('.injected-nav a').forEach(link => {
                    const linkUrl = link.getAttribute('data-url') || link.getAttribute('href');
                    if (currentPath === linkUrl) {
                        link.classList.add('active');
                    }
                });
            });
        </script>
        """

        return nav_html

    @staticmethod
    def inject_navbar_to_html(html_content, menu_items, current_filename=None):
        """
        완전한 HTML 문서에 네비게이션 바를 삽입

        이미 자체 네비게이션이 있는 HTML (datacong_core 등)은 건너뜁니다.

        Args:
            html_content (str): 원본 HTML 내용
            menu_items (list): 메뉴 항목 리스트
            current_filename (str): 현재 파일명

        Returns:
            str: 네비게이션이 삽입된 HTML
        """
        try:
            # 이미 네비게이션이 있는 HTML인지 확인 (datacong_core 등)
            # main-nav 클래스 또는 navbar-included 메타 태그가 있으면 건너뜀
            if 'class="main-nav"' in html_content or 'name="navbar-included"' in html_content:
                return html_content

            # 네비게이션 HTML 생성
            nav_html = MenuGenerator.generate_navbar_html(menu_items, current_filename)

            # Bootstrap CSS 링크
            bootstrap_css = '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">'

            # HTML 문서에 삽입
            if '<head>' in html_content:
                html_content = html_content.replace('<head>', f'<head>{bootstrap_css}')

            if '<body>' in html_content:
                html_content = html_content.replace('<body>', f'<body>{nav_html}')
            else:
                # body 태그가 없는 경우 맨 앞에 추가
                html_content = nav_html + html_content

            return html_content

        except Exception as e:
            # 오류가 발생하면 원본 HTML 반환
            print(f"네비게이션 삽입 중 오류: {e}")
            return html_content