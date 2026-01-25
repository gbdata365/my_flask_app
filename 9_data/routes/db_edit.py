"""
코드 테이블 편집기 (웹 버전)
- code_age_group, code_indicator 테이블 조회/편집
- code_master.xlsx로 저장
"""

from flask import render_template_string, request, jsonify, Blueprint
import sys
from pathlib import Path
import pandas as pd
from io import BytesIO
from flask import send_file

# 상위 디렉토리를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from module.db import get_db_engine, get_postgres_config
import psycopg2
from psycopg2 import sql

# Blueprint 생성
db_edit_bp = Blueprint('db_edit', __name__)


class CodeTableEditor:
    """코드 테이블 편집 클래스"""

    def __init__(self):
        self.engine = get_db_engine()
        self.config = get_postgres_config()
        self.excel_path = Path(__file__).parent.parent.parent / 'codedata' / 'code_master.xlsx'

    def get_table_data(self, table_name):
        """테이블 데이터 조회"""
        if table_name not in ['code_age_group', 'code_indicator']:
            raise ValueError(f"허용되지 않은 테이블: {table_name}")

        df = pd.read_sql(f"SELECT * FROM {table_name} ORDER BY sort_order, id", self.engine)
        return df

    def update_row(self, table_name, row_id, data):
        """행 업데이트"""
        if table_name not in ['code_age_group', 'code_indicator']:
            raise ValueError(f"허용되지 않은 테이블: {table_name}")

        conn = psycopg2.connect(**self.config)
        cursor = conn.cursor()

        try:
            # 업데이트할 컬럼들 (id, created_at, updated_at 제외)
            update_cols = [k for k in data.keys() if k not in ['id', 'created_at', 'updated_at']]

            set_clause = ", ".join([f"{col} = %s" for col in update_cols])
            set_clause += ", updated_at = CURRENT_TIMESTAMP"

            values = [data[col] for col in update_cols]
            values.append(row_id)

            query = f"UPDATE {table_name} SET {set_clause} WHERE id = %s"
            cursor.execute(query, values)
            conn.commit()

            return True

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def insert_row(self, table_name, data):
        """행 추가"""
        if table_name not in ['code_age_group', 'code_indicator']:
            raise ValueError(f"허용되지 않은 테이블: {table_name}")

        conn = psycopg2.connect(**self.config)
        cursor = conn.cursor()

        try:
            # 삽입할 컬럼들 (id, created_at, updated_at 제외)
            insert_cols = [k for k in data.keys() if k not in ['id', 'created_at', 'updated_at']]

            cols_str = ", ".join(insert_cols)
            placeholders = ", ".join(["%s"] * len(insert_cols))

            values = [data[col] for col in insert_cols]

            query = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders}) RETURNING id"
            cursor.execute(query, values)
            new_id = cursor.fetchone()[0]
            conn.commit()

            return new_id

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def delete_row(self, table_name, row_id):
        """행 삭제"""
        if table_name not in ['code_age_group', 'code_indicator']:
            raise ValueError(f"허용되지 않은 테이블: {table_name}")

        conn = psycopg2.connect(**self.config)
        cursor = conn.cursor()

        try:
            cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", (row_id,))
            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def export_to_excel(self):
        """테이블을 Excel 파일로 내보내기"""
        # age_group 시트
        df_age = pd.read_sql("""
            SELECT category, category_name, code, code_name, column_name,
                   age_start, age_end, sort_order, is_active
            FROM code_age_group
            ORDER BY sort_order, id
        """, self.engine)

        # indicator 시트
        df_ind = pd.read_sql("""
            SELECT category, category_name, column_name, display_name, description,
                   numerator, denominator, multiplier, decimal_places, data_type,
                   sort_order, is_active
            FROM code_indicator
            ORDER BY sort_order, id
        """, self.engine)

        # Excel 파일 생성
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_age.to_excel(writer, sheet_name='age_group', index=False)
            df_ind.to_excel(writer, sheet_name='indicator', index=False)

        output.seek(0)
        return output

    def save_to_excel_file(self):
        """테이블을 code_master.xlsx로 저장"""
        output = self.export_to_excel()

        # 파일로 저장
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.excel_path, 'wb') as f:
            f.write(output.read())

        return str(self.excel_path)


# HTML 템플릿
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>코드 테이블 편집기</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #5e72e4 0%, #825ee4 100%);
            color: white;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 1.8em; }
        .header-buttons { display: flex; gap: 10px; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .btn-primary { background: #28a745; color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-info { background: #17a2b8; color: white; }
        .btn:hover { transform: translateY(-2px); opacity: 0.9; }
        .main-content { padding: 20px; }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 12px 24px;
            background: #f8f9fa;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .tab.active {
            background: #5e72e4;
            color: white;
            border-color: #5e72e4;
        }
        .table-wrapper {
            overflow-x: auto;
            max-height: calc(100vh - 300px);
            overflow-y: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        thead {
            background: linear-gradient(135deg, #5e72e4 0%, #825ee4 100%);
            color: white;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }
        th { font-weight: 600; white-space: nowrap; }
        tbody tr:hover { background: #f8f9fa; }
        tbody tr:nth-child(even) { background: #fafafa; }
        input, select {
            width: 100%;
            padding: 6px 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 13px;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #5e72e4;
            box-shadow: 0 0 0 2px rgba(94, 114, 228, 0.1);
        }
        .action-btns {
            display: flex;
            gap: 5px;
        }
        .action-btn {
            padding: 4px 8px;
            font-size: 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .action-btn.save { background: #28a745; color: white; }
        .action-btn.delete { background: #dc3545; color: white; }
        .action-btn.cancel { background: #6c757d; color: white; }
        .message {
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            display: none;
        }
        .message.success { background: #d4edda; color: #155724; }
        .message.error { background: #f8d7da; color: #721c24; }
        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        .add-row-btn {
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>코드 테이블 편집기</h1>
            <div class="header-buttons">
                <button class="btn btn-info" onclick="downloadExcel()">Excel 다운로드</button>
                <button class="btn btn-primary" onclick="saveToExcel()">code_master.xlsx 저장</button>
            </div>
        </div>

        <div class="main-content">
            <div id="message" class="message"></div>

            <div class="tabs">
                <div class="tab active" data-table="code_age_group" onclick="selectTable('code_age_group')">
                    연령그룹 (code_age_group)
                </div>
                <div class="tab" data-table="code_indicator" onclick="selectTable('code_indicator')">
                    지표 (code_indicator)
                </div>
            </div>

            <button class="btn btn-primary add-row-btn" onclick="addNewRow()">+ 새 행 추가</button>

            <div class="table-wrapper">
                <div id="table-content" class="loading">테이블 로딩 중...</div>
            </div>
        </div>
    </div>

    <script>
        let currentTable = 'code_age_group';
        let tableData = [];

        const AGE_GROUP_COLUMNS = [
            {key: 'id', label: 'ID', readonly: true, width: '50px'},
            {key: 'category', label: '카테고리', type: 'number', width: '80px'},
            {key: 'category_name', label: '카테고리명', width: '100px'},
            {key: 'code', label: '코드', width: '100px'},
            {key: 'code_name', label: '코드명', width: '150px'},
            {key: 'column_name', label: '컬럼명', width: '150px'},
            {key: 'age_start', label: '시작연령', type: 'number', width: '80px'},
            {key: 'age_end', label: '종료연령', type: 'number', width: '80px'},
            {key: 'sort_order', label: '정렬순서', type: 'number', width: '80px'},
            {key: 'is_active', label: '활성화', type: 'boolean', width: '80px'}
        ];

        const INDICATOR_COLUMNS = [
            {key: 'id', label: 'ID', readonly: true, width: '50px'},
            {key: 'category', label: '카테고리', type: 'number', width: '80px'},
            {key: 'category_name', label: '카테고리명', width: '100px'},
            {key: 'column_name', label: '컬럼명', width: '120px'},
            {key: 'display_name', label: '표시명', width: '120px'},
            {key: 'description', label: '설명', width: '200px'},
            {key: 'numerator', label: '분자', width: '150px'},
            {key: 'denominator', label: '분모', width: '150px'},
            {key: 'multiplier', label: '배수', type: 'number', width: '80px'},
            {key: 'decimal_places', label: '소수점', type: 'number', width: '70px'},
            {key: 'data_type', label: '데이터타입', width: '120px'},
            {key: 'sort_order', label: '정렬순서', type: 'number', width: '80px'},
            {key: 'is_active', label: '활성화', type: 'boolean', width: '80px'}
        ];

        function getColumns() {
            return currentTable === 'code_age_group' ? AGE_GROUP_COLUMNS : INDICATOR_COLUMNS;
        }

        function selectTable(tableName) {
            currentTable = tableName;
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.toggle('active', tab.dataset.table === tableName);
            });
            loadTable();
        }

        function loadTable() {
            document.getElementById('table-content').innerHTML = '<div class="loading">테이블 로딩 중...</div>';

            fetch(`/9_data/api/code_table?table=${currentTable}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        tableData = data.data;
                        renderTable();
                    } else {
                        showMessage('오류: ' + data.error, 'error');
                    }
                })
                .catch(error => {
                    showMessage('오류: ' + error.message, 'error');
                });
        }

        function renderTable() {
            const columns = getColumns();
            let html = '<table><thead><tr>';

            columns.forEach(col => {
                html += `<th style="width: ${col.width}">${col.label}</th>`;
            });
            html += '<th style="width: 100px">작업</th></tr></thead><tbody>';

            tableData.forEach((row, idx) => {
                html += `<tr data-id="${row.id}" data-idx="${idx}">`;
                columns.forEach(col => {
                    const value = row[col.key];
                    if (col.readonly) {
                        html += `<td>${value !== null ? value : ''}</td>`;
                    } else if (col.type === 'boolean') {
                        html += `<td><select data-key="${col.key}">
                            <option value="true" ${value === true ? 'selected' : ''}>Y</option>
                            <option value="false" ${value === false ? 'selected' : ''}>N</option>
                        </select></td>`;
                    } else if (col.type === 'number') {
                        html += `<td><input type="number" data-key="${col.key}" value="${value !== null ? value : ''}"></td>`;
                    } else {
                        html += `<td><input type="text" data-key="${col.key}" value="${value !== null ? value : ''}"></td>`;
                    }
                });
                html += `<td class="action-btns">
                    <button class="action-btn save" onclick="saveRow(${row.id}, ${idx})">저장</button>
                    <button class="action-btn delete" onclick="deleteRow(${row.id})">삭제</button>
                </td></tr>`;
            });

            html += '</tbody></table>';
            document.getElementById('table-content').innerHTML = html;
        }

        function getRowData(idx) {
            const row = document.querySelector(`tr[data-idx="${idx}"]`);
            const data = {id: tableData[idx].id};

            row.querySelectorAll('input, select').forEach(input => {
                const key = input.dataset.key;
                let value = input.value;

                if (input.type === 'number') {
                    value = value === '' ? null : Number(value);
                } else if (input.tagName === 'SELECT') {
                    value = value === 'true';
                }

                data[key] = value;
            });

            return data;
        }

        function saveRow(id, idx) {
            const data = getRowData(idx);

            fetch('/9_data/api/code_table/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({table: currentTable, id: id, data: data})
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    showMessage('저장되었습니다.', 'success');
                    loadTable();
                } else {
                    showMessage('오류: ' + result.error, 'error');
                }
            })
            .catch(error => {
                showMessage('오류: ' + error.message, 'error');
            });
        }

        function deleteRow(id) {
            if (!confirm('정말 삭제하시겠습니까?')) return;

            fetch('/9_data/api/code_table/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({table: currentTable, id: id})
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    showMessage('삭제되었습니다.', 'success');
                    loadTable();
                } else {
                    showMessage('오류: ' + result.error, 'error');
                }
            })
            .catch(error => {
                showMessage('오류: ' + error.message, 'error');
            });
        }

        function addNewRow() {
            const columns = getColumns();
            const newRow = {};

            columns.forEach(col => {
                if (col.key === 'id') return;
                if (col.type === 'boolean') newRow[col.key] = true;
                else if (col.type === 'number') newRow[col.key] = 0;
                else newRow[col.key] = '';
            });

            fetch('/9_data/api/code_table/insert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({table: currentTable, data: newRow})
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    showMessage('새 행이 추가되었습니다. (ID: ' + result.id + ')', 'success');
                    loadTable();
                } else {
                    showMessage('오류: ' + result.error, 'error');
                }
            })
            .catch(error => {
                showMessage('오류: ' + error.message, 'error');
            });
        }

        function downloadExcel() {
            window.location.href = '/9_data/api/code_table/export';
        }

        function saveToExcel() {
            fetch('/9_data/api/code_table/save_excel', {method: 'POST'})
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    showMessage('code_master.xlsx 저장 완료: ' + result.path, 'success');
                } else {
                    showMessage('오류: ' + result.error, 'error');
                }
            })
            .catch(error => {
                showMessage('오류: ' + error.message, 'error');
            });
        }

        function showMessage(text, type) {
            const msg = document.getElementById('message');
            msg.textContent = text;
            msg.className = 'message ' + type;
            msg.style.display = 'block';

            setTimeout(() => {
                msg.style.display = 'none';
            }, 5000);
        }

        // 초기 로드
        document.addEventListener('DOMContentLoaded', loadTable);
    </script>
</body>
</html>
"""


# =============================================================================
# API 엔드포인트 (Blueprint)
# =============================================================================

@db_edit_bp.route('/api/code_table')
def api_code_table():
    """코드 테이블 데이터 조회"""
    try:
        table = request.args.get('table', 'code_age_group')
        editor = CodeTableEditor()
        df = editor.get_table_data(table)

        # DataFrame을 JSON 직렬화 가능한 형태로 변환
        data = df.to_dict('records')
        for row in data:
            for key, value in row.items():
                if pd.isna(value):
                    row[key] = None
                elif hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()

        return jsonify({'success': True, 'data': data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@db_edit_bp.route('/api/code_table/update', methods=['POST'])
def api_code_table_update():
    """코드 테이블 행 업데이트"""
    try:
        json_data = request.get_json()
        table = json_data.get('table')
        row_id = json_data.get('id')
        data = json_data.get('data')

        editor = CodeTableEditor()
        editor.update_row(table, row_id, data)

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@db_edit_bp.route('/api/code_table/insert', methods=['POST'])
def api_code_table_insert():
    """코드 테이블 행 추가"""
    try:
        json_data = request.get_json()
        table = json_data.get('table')
        data = json_data.get('data')

        editor = CodeTableEditor()
        new_id = editor.insert_row(table, data)

        return jsonify({'success': True, 'id': new_id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@db_edit_bp.route('/api/code_table/delete', methods=['POST'])
def api_code_table_delete():
    """코드 테이블 행 삭제"""
    try:
        json_data = request.get_json()
        table = json_data.get('table')
        row_id = json_data.get('id')

        editor = CodeTableEditor()
        editor.delete_row(table, row_id)

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@db_edit_bp.route('/api/code_table/export')
def api_code_table_export():
    """Excel 파일 다운로드"""
    try:
        editor = CodeTableEditor()
        output = editor.export_to_excel()

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='code_master.xlsx'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@db_edit_bp.route('/api/code_table/save_excel', methods=['POST'])
def api_code_table_save_excel():
    """code_master.xlsx 파일로 저장"""
    try:
        editor = CodeTableEditor()
        path = editor.save_to_excel_file()

        return jsonify({'success': True, 'path': path})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def render():
    """Flask 라우트에서 호출되는 메인 함수"""
    return render_template_string(HTML_TEMPLATE)
