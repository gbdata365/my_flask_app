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
    def get_giup_menu_items(giup_base):
        """
        1_giup 카테고리의 메뉴 항목들을 생성

        Args:
            giup_base (Path): 1_giup 폴더 경로

        Returns:
            list: 메뉴 항목 딕셔너리 리스트
        """
        menu_items = []

        # markdown_docs 폴더의 .md 파일들 처리 (index.md 우선)
        md_dir = giup_base / "markdown_docs"
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
                    'url': f'/1_giup/markdown/{md_file.stem}',
                    'type': 'markdown'
                })

        # html_docs 폴더의 .html 파일들 처리
        html_dir = giup_base / "html_docs"
        if html_dir.exists():
            for html_file in sorted(html_dir.glob("*.html")):
                display_name = html_file.stem.replace('_', ' ')
                menu_items.append({
                    'name': display_name,
                    'url': f'/1_giup/html/{html_file.stem}',
                    'type': 'html'
                })

        # routes 폴더의 .py 파일들 처리
        routes_dir = giup_base / "routes"
        if routes_dir.exists():
            py_files = sorted(routes_dir.glob("*.py"))
            print(f"[DEBUG] routes_dir: {routes_dir}")
            print(f"[DEBUG] routes_dir.exists(): {routes_dir.exists()}")
            print(f"[DEBUG] Found .py files: {[f.name for f in py_files]}")

            for py_file in py_files:
                # __init__.py와 _로 시작하는 파일들은 제외
                if py_file.name != "__init__.py" and not py_file.name.startswith("_"):
                    display_name = py_file.stem.replace('_', ' ')
                    print(f"[DEBUG] Adding menu item: {display_name} -> {py_file.stem}")
                    menu_items.append({
                        'name': display_name,
                        'url': f'/1_giup/routes/{py_file.stem}',
                        'type': 'python'
                    })
                else:
                    print(f"[DEBUG] Skipping file: {py_file.name}")

        return menu_items

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
        # 메인 네비게이션 바
        nav_html = f"""
        <!-- 상단 메인 네비게이션 -->
        <nav class="navbar navbar-expand-lg navbar-dark" style="background-color: #1243A6 !important; padding: 1rem 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <div class="container-fluid">
                <a class="navbar-brand" href="/" style="color: white !important; font-weight: bold; font-size: 1.5rem;">📊 데이터 분석 대시보드</a>
                <div class="d-flex">
                    <a href="/" style="background-color: #F24822; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; text-decoration: none;">🏠 홈으로</a>
                </div>
            </div>
        </nav>

        <!-- 서브 네비게이션 (파일 메뉴) -->
        <nav style="background-color: white; border-bottom: 2px solid #1243A6; padding: 0;">
            <div class="container-fluid">
                <ul class="nav nav-pills nav-fill" style="margin: 0;">
        """

        # 메뉴 항목들 추가
        for item in menu_items:
            # 현재 파일 활성화 체크
            is_active = (current_filename == item['name'] and
                        item.get('type') == 'python') or False
            active_class = 'active' if is_active else ''

            # 타입별 아이콘 설정
            icon = '📄' if item.get('type') == 'markdown' else '🌐' if item.get('type') == 'html' else '⚙️'

            nav_html += f"""
                    <li class="nav-item">
                        <a class="nav-link {active_class}" href="{item['url']}"
                           style="color: #011C40; border-radius: 0; padding: 1rem 1.5rem; margin: 0; border-bottom: 3px solid transparent;">
                            <span style="margin-right: 0.5rem;">{icon}</span>
                            {item['name']}
                        </a>
                    </li>
            """

        nav_html += """
                </ul>
            </div>
        </nav>
        """

        return nav_html

    @staticmethod
    def inject_navbar_to_html(html_content, menu_items, current_filename=None):
        """
        완전한 HTML 문서에 네비게이션 바를 삽입

        Args:
            html_content (str): 원본 HTML 내용
            menu_items (list): 메뉴 항목 리스트
            current_filename (str): 현재 파일명

        Returns:
            str: 네비게이션이 삽입된 HTML
        """
        try:
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