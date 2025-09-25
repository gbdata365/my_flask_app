from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
import os
import json
from datetime import datetime
from .csv_analyzer import CSVAnalyzer

# Blueprint 생성
dashboard_bp = Blueprint('dashboard', __name__, 
                        template_folder='../templates')

# 업로드 설정
UPLOAD_FOLDER = Path(__file__).parent.parent / 'data'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

def allowed_file(filename):
    """허용된 파일 확장자 확인"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@dashboard_bp.route('/')
def index():
    """메인 페이지 - CSV 업로드 폼"""
    # 기존 업로드된 파일 목록
    uploaded_files = []
    if UPLOAD_FOLDER.exists():
        for file_path in UPLOAD_FOLDER.glob('*.csv'):
            uploaded_files.append({
                'name': file_path.name,
                'size': f"{file_path.stat().st_size / 1024:.1f} KB",
                'modified': datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            })
    
    return render_template('csv_dashboard/upload.html', uploaded_files=uploaded_files)

@dashboard_bp.route('/upload', methods=['POST'])
def upload_file():
    """CSV 파일 업로드 처리"""
    if 'file' not in request.files:
        flash('파일이 선택되지 않았습니다.')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('파일이 선택되지 않았습니다.')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # 파일명 안전하게 처리
        filename = secure_filename(file.filename)
        
        # 업로드 폴더 생성
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        
        # 파일 저장
        file_path = UPLOAD_FOLDER / filename
        file.save(str(file_path))
        
        flash(f'파일 {filename}이 성공적으로 업로드되었습니다!')
        
        # 자동 분석 페이지로 리다이렉트
        return redirect(url_for('dashboard.analyze', filename=filename))
    
    else:
        flash('허용되지 않는 파일 형식입니다. CSV, Excel 파일만 업로드 가능합니다.')
        return redirect(request.url)

@dashboard_bp.route('/analyze/<filename>')
def analyze(filename):
    """CSV 파일 분석 및 대시보드 생성"""
    file_path = UPLOAD_FOLDER / filename
    
    if not file_path.exists():
        flash('파일을 찾을 수 없습니다.')
        return redirect(url_for('dashboard.index'))
    
    try:
        # CSV 분석 실행
        analyzer = CSVAnalyzer(str(file_path))
        analysis_results = analyzer.load_and_analyze_csv()
        
        if 'error' in analysis_results:
            flash(f'파일 분석 중 오류가 발생했습니다: {analysis_results["error"]}')
            return redirect(url_for('dashboard.index'))
        
        # 대시보드 HTML 생성
        dashboard_html = analyzer.generate_dashboard_html(f'{filename} 분석 대시보드')
        
        return dashboard_html
        
    except Exception as e:
        flash(f'분석 중 예상치 못한 오류가 발생했습니다: {str(e)}')
        return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/api/analyze/<filename>')
def api_analyze(filename):
    """API: CSV 파일 분석 결과 JSON 반환"""
    file_path = UPLOAD_FOLDER / filename
    
    if not file_path.exists():
        return jsonify({'error': '파일을 찾을 수 없습니다.'}), 404
    
    try:
        analyzer = CSVAnalyzer(str(file_path))
        analysis_results = analyzer.load_and_analyze_csv()
        
        if 'error' in analysis_results:
            return jsonify(analysis_results), 400
        
        # 차트 데이터도 포함
        charts = analyzer.generate_charts()
        analysis_results['charts'] = charts
        
        return jsonify(analysis_results)
        
    except Exception as e:
        return jsonify({'error': f'분석 중 오류 발생: {str(e)}'}), 500

@dashboard_bp.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    """업로드된 파일 삭제"""
    file_path = UPLOAD_FOLDER / filename
    
    if file_path.exists():
        try:
            file_path.unlink()
            flash(f'파일 {filename}이 삭제되었습니다.')
        except Exception as e:
            flash(f'파일 삭제 중 오류가 발생했습니다: {str(e)}')
    else:
        flash('파일을 찾을 수 없습니다.')
    
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/list')
def list_files():
    """API: 업로드된 파일 목록 JSON 반환"""
    files = []
    if UPLOAD_FOLDER.exists():
        for file_path in UPLOAD_FOLDER.glob('*.*'):
            if file_path.suffix.lower() in ['.csv', '.xlsx', '.xls']:
                files.append({
                    'name': file_path.name,
                    'size': file_path.stat().st_size,
                    'modified': file_path.stat().st_mtime,
                    'extension': file_path.suffix.lower()
                })
    
    return jsonify({'files': files})