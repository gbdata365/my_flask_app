# -*- coding: utf-8 -*-
"""
API 라우트 모듈
1_giup 카테고리의 API 엔드포인트들을 관리
"""

import sys
import os
import importlib.util
from pathlib import Path
from flask import request, jsonify, send_file

from .pdf_generator import PDFGenerator


class APIRoutes:
    """API 라우트 관리 클래스"""

    def __init__(self, app, giup_base):
        """
        API 라우트 초기화

        Args:
            app (Flask): Flask 애플리케이션 인스턴스
            giup_base (Path): 1_giup 폴더 경로
        """
        self.app = app
        self.giup_base = giup_base
        self.pdf_generator = PDFGenerator()
        self._register_routes()

    def _register_routes(self):
        """API 라우트들을 등록"""
        self._register_dash3_update()
        self._register_dash3_export_pdf()

    def _register_dash3_update(self):
        """dash3 업데이트 API 등록"""
        @self.app.route("/1_giup/api/dash3_update", methods=['POST'])
        def dash3_update():
            """dash3 차트 데이터 업데이트 API"""
            try:
                data = request.get_json()
                year = data.get('year')
                month = data.get('month')

                # dash3 모듈 동적 로드
                dash3_module = self._load_dash3_module()

                # 데이터 로드 및 차트 생성
                df, sido_list, industry_list, years, months = dash3_module.load_data()
                region_chart = dash3_module.create_region_table_chart(df, year, month)
                industry_chart = dash3_module.create_industry_table_chart(df, year, month)

                return jsonify({
                    'success': True,
                    'region_chart': region_chart,
                    'industry_chart': industry_chart
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                })

    def _register_dash3_export_pdf(self):
        """dash3 PDF 내보내기 API 등록"""
        @self.app.route("/1_giup/api/dash3_export_pdf")
        def dash3_export_pdf():
            """dash3 데이터를 PDF로 내보내기"""
            try:
                # 요청 파라미터 가져오기
                year = request.args.get('year', '전체')
                month = request.args.get('month', '전체')
                filename = request.args.get('filename', 'dashboard_export')

                # dash3 모듈 로드 및 데이터 생성
                dash3_module = self._load_dash3_module()

                df, _, _, _, _ = dash3_module.load_data()
                region_chart = dash3_module.create_region_table_chart(df, year, month)
                industry_chart = dash3_module.create_industry_table_chart(df, year, month)

                # PDF 생성
                output_dir = self.giup_base / "output"
                temp_file_path, pdf_filename = self.pdf_generator.generate_pdf(
                    region_chart, industry_chart, year, month, filename, output_dir
                )

                # 파일 전송
                response = send_file(
                    temp_file_path,
                    as_attachment=True,
                    download_name=pdf_filename,
                    mimetype='application/pdf'
                )

                # 임시 파일 정리
                @response.call_on_close
                def cleanup():
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass

                return response

            except Exception as e:
                return f"PDF 생성 오류: {str(e)}", 500

    def _load_dash3_module(self):
        """
        dash3 모듈을 동적으로 로드

        Returns:
            module: 로드된 dash3 모듈
        """
        routes_dir = self.giup_base / "routes"
        sys.path.insert(0, str(routes_dir))

        spec = importlib.util.spec_from_file_location("dash3", routes_dir / "dash3.py")
        dash3_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dash3_module)

        return dash3_module