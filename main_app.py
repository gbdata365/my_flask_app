# -*- coding: utf-8 -*-
"""
Flask 기반 데이터 분석 대시보드 시스템
동적 카테고리 폴더 검색 및 라우트 자동 생성을 지원하는 메인 애플리케이션
"""

from flask import Flask, render_template
from pathlib import Path
import re
import sys
import importlib.util
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 모듈 임포트
from module.menu_generator import MenuGenerator
from module.markdown_renderer import MarkdownRenderer
from module.api_routes import APIRoutes


def create_app():
    """
    Flask 애플리케이션 팩토리 함수

    Returns:
        Flask: 설정된 Flask 애플리케이션 인스턴스
    """
    app = Flask(__name__)

    # 기본 설정
    app.config['SECRET_KEY'] = 'csv_dashboard_secret_key_2024'  # 세션 및 보안을 위한 시크릿 키
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 최대 파일 크기 제한

    # 템플릿에서 사용할 유틸리티 함수들을 등록
    @app.context_processor
    def utility_processor():
        """템플릿에서 사용할 함수들을 전역으로 등록"""
        return dict(get_category_folders=MenuGenerator.get_category_folders)

    # 메인 홈페이지
    @app.route("/")
    def index():
        """메인 페이지 - 모든 카테고리를 보여주는 인덱스 페이지"""
        menu_items = MenuGenerator.get_main_menu_items()
        return render_template("index.html", menu_items=menu_items)

    # 각 카테고리별 시스템 등록
    register_csv_dashboard_blueprint(app)
    register_giup_routes(app)
    register_other_category_routes(app)

    return app


def register_csv_dashboard_blueprint(app):
    """
    CSV 대시보드 블루프린트를 등록 (3_csv_dashboard)

    Args:
        app (Flask): Flask 애플리케이션 인스턴스
    """
    try:
        csv_dashboard_path = Path("3_csv_dashboard")
        if csv_dashboard_path.exists():
            sys.path.insert(0, str(csv_dashboard_path))
            from routes.dashboard_routes import dashboard_bp
            app.register_blueprint(dashboard_bp, url_prefix="/3_csv_dashboard")
            print("CSV 대시보드 블루프린트 등록 완료")
    except ImportError as e:
        print(f"CSV 대시보드 블루프린트 등록 실패: {e}")


def register_giup_routes(app):
    """
    1_giup 카테고리의 동적 라우트 시스템을 등록
    routes 폴더의 .py 파일들을 자동으로 메뉴로 추가

    Args:
        app (Flask): Flask 애플리케이션 인스턴스
    """
    try:
        giup_base = Path("1_giup")
        markdown_renderer = MarkdownRenderer()

        # 1_giup 메인 페이지
        @app.route("/1_giup", endpoint="giup_index")
        def giup_index():
            """1_giup 카테고리 메인 페이지 - 상단 메뉴와 첫 번째 마크다운 내용 표시"""
            menu_items = MenuGenerator.get_giup_menu_items(giup_base)
            first_content = get_first_markdown_content(giup_base, markdown_renderer)

            return render_template('category_with_navbar.html',
                                 menu_items=menu_items,
                                 content=first_content,
                                 category_name="1_giup")

        # Routes 실행 (routes 폴더의 .py 파일들)
        @app.route("/1_giup/routes/<filename>", methods=['GET', 'POST'])
        def giup_route_exec(filename):
            """routes 폴더의 .py 파일을 동적으로 실행"""
            try:
                menu_items = MenuGenerator.get_giup_menu_items(giup_base)
                route_content = execute_route_module(giup_base / "routes", filename)

                if is_complete_html(route_content):
                    return MenuGenerator.inject_navbar_to_html(route_content, menu_items, filename)
                else:
                    return render_template('category_with_navbar.html',
                                         menu_items=menu_items,
                                         content=route_content,
                                         category_name="1_giup")
            except Exception as e:
                return f"<h1>오류 발생</h1><pre>{str(e)}</pre>"

        # HTML 문서 표시 (html_docs 폴더)
        @app.route("/1_giup/html/<filename>")
        def giup_html_view(filename):
            """html_docs 폴더의 .html 파일을 표시"""
            try:
                menu_items = MenuGenerator.get_giup_menu_items(giup_base)
                html_file = giup_base / "html_docs" / f"{filename}.html"

                if html_file.exists():
                    content = html_file.read_text(encoding='utf-8')

                    if is_complete_html(content):
                        return MenuGenerator.inject_navbar_to_html(content, menu_items, filename)
                    else:
                        return render_template('category_with_navbar.html',
                                             menu_items=menu_items,
                                             content=content,
                                             category_name="1_giup")
                else:
                    return f"<h1>파일을 찾을 수 없습니다</h1><p>{filename}.html</p>"
            except Exception as e:
                return f"<h1>오류 발생</h1><pre>{str(e)}</pre>"

        # 마크다운 문서 표시 (markdown_docs 폴더)
        @app.route("/1_giup/markdown/<filename>")
        def giup_markdown_view(filename):
            """markdown_docs 폴더의 .md 파일을 렌더링하여 표시"""
            try:
                menu_items = MenuGenerator.get_giup_menu_items(giup_base)
                md_file = giup_base / "markdown_docs" / f"{filename}.md"

                if md_file.exists():
                    styled_content = markdown_renderer.render_file(md_file)
                    return render_template('category_with_navbar.html',
                                         menu_items=menu_items,
                                         content=styled_content,
                                         category_name="1_giup")
                else:
                    return f"<h1>파일을 찾을 수 없습니다</h1><p>{filename}.md</p>"
            except Exception as e:
                return f"<h1>오류 발생</h1><pre>{str(e)}</pre>"

        # API 엔드포인트들 등록
        APIRoutes(app, giup_base)

        print("1_giup 동적 라우트 시스템 등록 완료")

    except Exception as e:
        print(f"1_giup 라우트 등록 실패: {e}")
        # fallback 라우트 등록
        @app.route("/1_giup", endpoint="giup_index")
        def giup_index():
            return f"<h1>1_giup 카테고리</h1><p>시스템 오류입니다: {str(e)}</p>"


def register_other_category_routes(app):
    """
    1_giup과 3_csv_dashboard를 제외한 기타 카테고리들의 기본 라우트 생성

    Args:
        app (Flask): Flask 애플리케이션 인스턴스
    """
    # 2_의료통계 카테고리 기본 라우트
    @app.route("/2_의료통계", endpoint="medical_index")
    def medical_index():
        return f"<h1>2_의료통계 카테고리</h1><p>준비 중입니다.</p>"

    # 나머지 카테고리들을 위한 동적 기본 라우트 생성
    current_dir = Path(".")
    excluded_categories = ["1_giup", "2_의료통계", "3_csv_dashboard"]

    for path in current_dir.iterdir():
        if (path.is_dir() and
            re.match(r"^\d+", path.name) and
            path.name not in excluded_categories):

            category = path.name
            category_name = re.sub(r'^\d+_', '', category)
            endpoint_name = f"{category_name}_index"

            # 클로저를 사용하여 category 값을 캡처
            def make_route_function(cat):
                def category_index():
                    return f"<h1>{cat} 카테고리</h1><p>준비 중입니다.</p>"
                return category_index

            # 라우트 등록
            route_func = make_route_function(category)
            route_func.__name__ = endpoint_name
            app.add_url_rule(f"/{category}", endpoint=endpoint_name, view_func=route_func)


# 유틸리티 함수들

def get_first_markdown_content(giup_base, markdown_renderer):
    """
    첫 번째 마크다운 파일 내용을 가져오기 (index.md 우선)

    Args:
        giup_base (Path): 1_giup 폴더 경로
        markdown_renderer (MarkdownRenderer): 마크다운 렌더러 인스턴스

    Returns:
        str: 렌더링된 HTML 내용
    """
    md_dir = giup_base / "markdown_docs"
    if not md_dir.exists():
        return "<p>마크다운 문서가 없습니다.</p>"

    # index.md 파일 우선 확인
    index_file = md_dir / "index.md"
    if index_file.exists():
        return markdown_renderer.render_file(index_file)

    # index.md가 없으면 첫 번째 .md 파일 사용
    md_files = sorted(md_dir.glob("*.md"))
    if md_files:
        return markdown_renderer.render_file(md_files[0])

    return "<p>표시할 마크다운 파일이 없습니다.</p>"


def execute_route_module(routes_dir, filename):
    """
    routes 폴더의 파이썬 모듈을 동적으로 실행

    Args:
        routes_dir (Path): routes 폴더 경로
        filename (str): 실행할 파일명 (확장자 제외)

    Returns:
        str: 모듈의 render() 함수 실행 결과
    """
    sys.path.insert(0, str(routes_dir))

    # 모듈 동적 임포트
    spec = importlib.util.spec_from_file_location(filename, routes_dir / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # render 함수 실행
    if hasattr(module, 'render'):
        return module.render()
    else:
        return f"<h1>{filename}</h1><p>render() 함수가 없습니다.</p>"


def is_complete_html(content):
    """
    HTML 내용이 완전한 문서인지 확인

    Args:
        content (str): HTML 내용

    Returns:
        bool: 완전한 HTML 문서 여부
    """
    content_lower = content.strip().lower()
    return (content_lower.startswith('<!doctype') or
            content_lower.startswith('<html'))


# 애플리케이션 실행
if __name__ == "__main__":
    import os
    import sys

    # Windows 콘솔 인코딩 설정
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

    app = create_app()
    print("[INFO] Flask 애플리케이션 시작")
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)