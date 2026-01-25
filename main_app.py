# -*- coding: utf-8 -*-
"""
Flask 데이터 분석 대시보드 메인 애플리케이션
============================================

이 모듈은 다양한 분야(인구, 경제, 환경 등)의 데이터 분석 대시보드를
제공하는 Flask 웹 애플리케이션의 진입점입니다.

주요 기능:
    1. 카테고리 기반 라우트 관리 (01_population, 02_economy 등)
    2. Blueprint 패턴을 사용한 모듈화된 구조
    3. 동적 카테고리 탐색 및 등록
    4. 기본 템플릿 자동 생성

디렉토리 구조:
    01_claude_project/
    ├── main_app.py          # 이 파일 (Flask 메인 앱)
    ├── templates/           # 기본 템플릿 폴더
    │   └── index.html       # 메인 페이지 (자동 생성)
    ├── static/              # 정적 파일 (CSS, JS)
    ├── module/              # 공통 분석 모듈
    ├── 01_population/       # 인구통계 분석
    │   ├── routes/          # Flask Blueprint
    │   └── templates/       # 인구통계 템플릿
    └── 02_economy/          # 경제 분석 (예정)

실행 방법:
    $ python main_app.py

    또는 Flask 개발 서버로:
    $ set FLASK_APP=main_app.py
    $ flask run --debug

환경 변수 (.env):
    - PORT: 서버 포트 (기본값: 5000)
    - POSTGRES_*: 데이터베이스 연결 정보

Author: Claude AI Agent
Created: 2024-12-18
"""

from flask import Flask, render_template, redirect
from pathlib import Path
import sys
import os
import re
import importlib.util
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
# override=False: 기존 환경 변수가 있으면 덮어쓰지 않음
load_dotenv(override=False)

# 현재 파일의 디렉토리를 기준으로 모듈 경로 설정
# 이를 통해 module, routes 등을 임포트할 수 있음
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# 프로젝트 모듈 임포트
from module.menu_generator import MenuGenerator
from module.markdown_renderer import MarkdownRenderer


def create_app():
    """
    Flask 애플리케이션 팩토리 함수.

    Flask 앱 인스턴스를 생성하고 설정합니다.
    애플리케이션 팩토리 패턴을 사용하여 테스트와 확장이 용이합니다.

    Returns:
        Flask: 설정이 완료된 Flask 애플리케이션 인스턴스

    Examples:
        >>> # 기본 실행
        >>> app = create_app()
        >>> app.run(debug=True)

        >>> # 테스트 클라이언트
        >>> app = create_app()
        >>> client = app.test_client()
        >>> response = client.get('/')

    Note:
        - SECRET_KEY는 세션 암호화에 사용됨 (프로덕션에서는 변경 필요)
        - MAX_CONTENT_LENGTH로 업로드 파일 크기 제한 (16MB)
    """
    # Flask 앱 생성
    # template_folder: Jinja2 템플릿 파일 위치
    # static_folder: CSS, JS, 이미지 등 정적 파일 위치
    app = Flask(__name__,
                template_folder=str(BASE_DIR / 'templates'),
                static_folder=str(BASE_DIR / 'static'))

    # 앱 설정
    app.config['SECRET_KEY'] = 'data_analysis_dashboard_2024'  # 세션 암호화 키
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024        # 최대 업로드 16MB

    # 메인 홈페이지 라우트
    @app.route("/")
    def index():
        """
        메인 페이지 렌더링.

        BASE_DIR의 숫자_이름 형식 폴더들을 카테고리로 표시합니다.
        예: 01_population, 02_economy 등

        Returns:
            str: 렌더링된 index.html
        """
        categories = get_category_list()
        return render_template("index.html", categories=categories)

    # 모든 카테고리 자동 등록 (숫자로 시작하는 폴더)
    register_all_categories(app)

    return app


def get_category_list():
    """
    카테고리 폴더 목록을 조회합니다.

    BASE_DIR에서 "숫자_이름" 형식의 디렉토리를 찾아
    카테고리 정보 리스트로 반환합니다.

    Returns:
        list[dict]: 카테고리 정보 딕셔너리 리스트.
            각 딕셔너리 구조:
            - id (str): 전체 폴더명 ('01_population')
            - num (str): 번호 ('01')
            - name (str): 이름 ('population')
            - url (str): 접근 URL ('/01_population')

    Examples:
        >>> categories = get_category_list()
        >>> print(categories)
        [
            {'id': '01_population', 'num': '01', 'name': 'population', 'url': '/01_population'},
            {'id': '02_economy', 'num': '02', 'name': 'economy', 'url': '/02_economy'}
        ]

    Note:
        - 폴더명이 숫자로 시작하고 '_'를 포함해야 인식됨
        - 폴더명 기준 오름차순 정렬
    """
    categories = []

    # BASE_DIR의 모든 항목을 정렬하여 순회
    for path in sorted(BASE_DIR.iterdir()):
        # 디렉토리이고, 숫자로 시작하고, '_'를 포함하는 경우
        if path.is_dir() and path.name[0].isdigit() and '_' in path.name:
            # '01_population' → num='01', name='population'
            num, name = path.name.split('_', 1)
            categories.append({
                'id': path.name,
                'num': num,
                'name': name,
                'url': f'/{path.name}'
            })

    return categories


def register_all_categories(app):
    """
    숫자로 시작하는 모든 카테고리 폴더를 자동으로 등록합니다.

    Args:
        app (Flask): Flask 애플리케이션 인스턴스
    """
    categories = get_category_list()

    for category in categories:
        category_id = category['id']  # 예: '01_population', '02_기업체현황'
        try:
            register_category_routes(app, category_id)
            print(f"{category_id} 동적 라우트 시스템 등록 완료")
        except Exception as e:
            print(f"{category_id} 라우트 등록 실패: {e}")
            import traceback
            traceback.print_exc()


def register_category_routes(app, category_id):
    """
    특정 카테고리의 동적 라우트 시스템을 등록합니다.
    routes, markdown_docs, html_docs 폴더의 파일들을 자동으로 메뉴로 추가합니다.

    Args:
        app (Flask): Flask 애플리케이션 인스턴스
        category_id (str): 카테고리 ID (예: '01_population', '02_기업체현황')
    """
    category_base = BASE_DIR / category_id
    markdown_renderer = MarkdownRenderer()

    # 폴더 존재 확인
    if not category_base.exists():
        raise FileNotFoundError(f"{category_id} 폴더를 찾을 수 없습니다")

    # 모듈 임포트 경로 추가
    sys.path.insert(0, str(category_base))
    if (category_base / "routes").exists():
        sys.path.insert(0, str(category_base / "routes"))

    # Blueprint 임포트 및 등록 (_로 시작하는 API 파일들)
    # 01_인구및가구현황의 경우에만 특정 Blueprint 등록
    if category_id == "01_인구및가구현황":
        try:
            from routes._population_api import population_bp
            from routes._age_api import age_bp
            app.register_blueprint(population_bp, url_prefix=f"/{category_id}")
            app.register_blueprint(age_bp, url_prefix=f"/{category_id}")
        except ImportError:
            pass  # Blueprint가 없으면 무시

    # 9_data의 경우 db_viewer, db_edit Blueprint 등록
    if category_id == "9_data":
        try:
            from db_viewer import db_viewer_bp
            app.register_blueprint(db_viewer_bp, url_prefix=f"/{category_id}")
            print(f"  db_viewer_bp 등록 완료")
        except Exception as e:
            print(f"  db_viewer_bp 등록 실패: {e}")

        try:
            from db_edit import db_edit_bp
            app.register_blueprint(db_edit_bp, url_prefix=f"/{category_id}")
            print(f"  db_edit_bp 등록 완료")
        except Exception as e:
            print(f"  db_edit_bp 등록 실패: {e}")

    # 동적 엔드포인트 이름 생성 (category_id의 특수문자 제거)
    endpoint_prefix = category_id.replace('-', '_').replace(' ', '_')

    # 카테고리 메인 페이지 (메뉴 표시)
    @app.route(f"/{category_id}", endpoint=f"{endpoint_prefix}_index")
    def category_index():
        """카테고리 메인 페이지 - 상단 메뉴와 첫 번째 마크다운 내용 표시"""
        menu_items = MenuGenerator.get_category_menu_items(category_base)
        first_content = get_first_markdown_content(category_base, markdown_renderer)
        return render_template('category_with_navbar.html',
                             menu_items=menu_items,
                             content=first_content,
                             category_name=category_id)

    # Routes 실행 (routes 폴더의 .py 파일들)
    @app.route(f"/{category_id}/routes/<filename>", methods=['GET', 'POST'], endpoint=f"{endpoint_prefix}_route_exec")
    def category_route_exec(filename):
        """routes 폴더의 .py 파일을 동적으로 실행"""
        try:
            from flask import Response, request
            menu_items = MenuGenerator.get_category_menu_items(category_base)
            route_content = execute_route_module(
                category_base / "routes",
                filename,
                dict(request.args),
                dict(request.form) if request.method == 'POST' else None,
                request.method
            )

            # Flask Response 객체인 경우 (jsonify 등) 직접 반환
            if isinstance(route_content, Response):
                return route_content

            # 문자열인 경우 HTML 처리
            if is_complete_html(route_content):
                return MenuGenerator.inject_navbar_to_html(route_content, menu_items, filename)
            else:
                return render_template('category_with_navbar.html',
                                     menu_items=menu_items,
                                     content=route_content,
                                     category_name=category_id)
        except Exception as e:
            return f"<h1>오류 발생</h1><pre>{str(e)}</pre>"

    # HTML 문서 표시 (html_docs 폴더)
    @app.route(f"/{category_id}/html/<filename>", endpoint=f"{endpoint_prefix}_html_view")
    def category_html_view(filename):
        """html_docs 폴더의 .html 파일을 표시"""
        try:
            menu_items = MenuGenerator.get_category_menu_items(category_base)
            html_file = category_base / "html_docs" / f"{filename}.html"

            if html_file.exists():
                content = html_file.read_text(encoding='utf-8')

                if is_complete_html(content):
                    return MenuGenerator.inject_navbar_to_html(content, menu_items, filename)
                else:
                    return render_template('category_with_navbar.html',
                                         menu_items=menu_items,
                                         content=content,
                                         category_name=category_id)
            else:
                return f"<h1>파일을 찾을 수 없습니다</h1><p>{filename}.html</p>"
        except Exception as e:
            return f"<h1>오류 발생</h1><pre>{str(e)}</pre>"

    # 마크다운 문서 표시 (markdown_docs 폴더)
    @app.route(f"/{category_id}/markdown/<filename>", endpoint=f"{endpoint_prefix}_markdown_view")
    def category_markdown_view(filename):
        """markdown_docs 폴더의 .md 파일을 렌더링하여 표시"""
        try:
            menu_items = MenuGenerator.get_category_menu_items(category_base)
            md_file = category_base / "markdown_docs" / f"{filename}.md"

            if md_file.exists():
                styled_content = markdown_renderer.render_file(md_file)
                return render_template('category_with_navbar.html',
                                     menu_items=menu_items,
                                     content=styled_content,
                                     category_name=category_id)
            else:
                return f"<h1>파일을 찾을 수 없습니다</h1><p>{filename}.md</p>"
        except Exception as e:
            return f"<h1>오류 발생</h1><pre>{str(e)}</pre>"


# =============================================================================
# 유틸리티 함수들
# =============================================================================

def get_first_markdown_content(category_base, markdown_renderer):
    """
    첫 번째 마크다운 파일 내용을 가져오기 (index.md 우선)

    Args:
        category_base (Path): 카테고리 폴더 경로
        markdown_renderer (MarkdownRenderer): 마크다운 렌더러 인스턴스

    Returns:
        str: 렌더링된 HTML 내용
    """
    md_dir = category_base / "markdown_docs"
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


def execute_route_module(routes_dir, filename, request_args=None, request_form=None, method='GET'):
    """
    routes 폴더의 파이썬 모듈을 동적으로 실행

    Args:
        routes_dir (Path): routes 폴더 경로
        filename (str): 실행할 파일명 (확장자 제외)
        request_args (dict): HTTP GET 요청 파라미터 (선택)
        request_form (dict): HTTP POST 요청 데이터 (선택)
        method (str): HTTP 메서드 ('GET' 또는 'POST')

    Returns:
        str: 모듈의 render() 함수 실행 결과
    """
    sys.path.insert(0, str(routes_dir))

    # 모듈 동적 임포트
    spec = importlib.util.spec_from_file_location(filename, routes_dir / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # render 함수 실행 (파라미터 유연하게 전달)
    if hasattr(module, 'render'):
        import inspect
        sig = inspect.signature(module.render)
        param_names = list(sig.parameters.keys())

        # 파라미터에 따라 적절히 전달
        kwargs = {}
        if 'request_args' in param_names:
            kwargs['request_args'] = request_args or {}
        if 'request_form' in param_names:
            kwargs['request_form'] = request_form
        if 'method' in param_names:
            kwargs['method'] = method

        if kwargs:
            return module.render(**kwargs)
        elif len(param_names) > 0:
            # 기존 호환성: 첫 번째 파라미터로 request_args 전달
            return module.render(request_args or {})
        else:
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


def ensure_templates():
    """
    기본 템플릿 디렉토리와 파일을 확인하고 생성합니다.

    templates 폴더와 index.html이 없으면 기본 템플릿을 생성합니다.
    그라데이션 배경의 카드형 카테고리 목록 UI를 제공합니다.

    Side Effects:
        - templates/ 디렉토리 생성 (없는 경우)
        - templates/index.html 파일 생성 (없는 경우)

    Examples:
        >>> ensure_templates()
        # templates/index.html이 없으면 기본 템플릿 생성

    Note:
        - 이미 index.html이 있으면 덮어쓰지 않음
        - UTF-8 인코딩으로 저장
    """
    # 템플릿 디렉토리 생성
    templates_dir = BASE_DIR / "templates"
    templates_dir.mkdir(exist_ok=True)

    # index.html 파일 확인 및 생성
    index_file = templates_dir / "index.html"
    if not index_file.exists():
        # 기본 템플릿 HTML 작성
        index_file.write_text('''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>데이터 분석 대시보드</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Pretendard', 'Noto Sans KR', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem;
        }
        h1 {
            color: white;
            margin-bottom: 2rem;
            font-size: 2rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .category-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            max-width: 1200px;
            width: 100%;
        }
        .category-card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            text-decoration: none;
            color: #333;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        .category-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        .category-num {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            width: 50px;
            height: 50px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: bold;
        }
        .category-info h2 {
            font-size: 1.1rem;
            margin-bottom: 0.3rem;
        }
        .category-info p {
            font-size: 0.85rem;
            color: #666;
        }
    </style>
</head>
<body>
    <h1>데이터 분석 대시보드</h1>
    <div class="category-grid">
        {% for cat in categories %}
        <a href="{{ cat.url }}" class="category-card">
            <div class="category-num">{{ cat.num }}</div>
            <div class="category-info">
                <h2>{{ cat.name }}</h2>
                <p>{{ cat.id }}</p>
            </div>
        </a>
        {% endfor %}
    </div>
</body>
</html>
''', encoding='utf-8')


# =============================================================================
# 애플리케이션 실행
# =============================================================================
if __name__ == "__main__":
    """
    스크립트 직접 실행 시 Flask 개발 서버 시작.

    실행 방법:
        $ python main_app.py

    접속 URL:
        - 로컬: http://localhost:5000
        - 네트워크: http://<IP주소>:5000

    환경 변수:
        - PORT: 서버 포트 (기본값: 5000)
    """
    # 기본 템플릿 확인 및 생성
    ensure_templates()

    # Windows 콘솔에서 한글 출력을 위한 인코딩 설정
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass  # Python 3.6 이하에서는 reconfigure 없음

    # Flask 앱 생성 및 실행
    app = create_app()
    print("[INFO] Flask 애플리케이션 시작")
    print(f"[INFO] http://localhost:5000")

    # 환경 변수에서 포트 읽기 (기본값: 5000)
    port = int(os.environ.get('PORT', 5000))

    # 개발 서버 실행
    # debug=True: 코드 변경 시 자동 재시작
    # host='0.0.0.0': 모든 네트워크 인터페이스에서 접속 허용
    app.run(debug=True, host='0.0.0.0', port=port)
