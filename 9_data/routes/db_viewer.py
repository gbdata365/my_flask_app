"""
PostgreSQL 데이터베이스 뷰어 (웹 버전)
- 데이터베이스 목록 조회
- 테이블 목록 조회
- 테이블 데이터 조회
"""

from flask import render_template_string, request, jsonify
import sys
from pathlib import Path

# 상위 디렉토리를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from module.db_config import get_postgres_config
import psycopg2
from psycopg2 import sql


class PostgresWebViewer:
    """PostgreSQL 웹 뷰어 클래스"""

    def __init__(self):
        """초기화: PostgreSQL 설정 로드"""
        self.config = get_postgres_config()

    def connect_to_postgres(self, database=None):
        """PostgreSQL 서버에 연결"""
        config = self.config.copy()
        if database:
            config["database"] = database

        # 연결 타임아웃 설정 (5초)
        config["connect_timeout"] = 5

        try:
            conn = psycopg2.connect(**config)
            return conn
        except Exception as e:
            raise Exception(f"PostgreSQL 연결 실패: {e}")

    def get_databases(self):
        """데이터베이스 목록 조회"""
        conn = self.connect_to_postgres()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT datname
                FROM pg_database
                WHERE datistemplate = false
                ORDER BY datname
            """)
            databases = [row[0] for row in cursor.fetchall()]
            return databases

        except Exception as e:
            raise Exception(f"데이터베이스 목록 조회 실패: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_tables(self, database):
        """특정 데이터베이스의 테이블 목록 조회"""
        conn = self.connect_to_postgres(database=database)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT table_name,
                       (SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = t.table_name) as column_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [{"name": row[0], "columns": row[1]} for row in cursor.fetchall()]
            return tables

        except Exception as e:
            raise Exception(f"테이블 목록 조회 실패: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_table_data(self, database, table):
        """특정 테이블의 데이터 조회"""
        conn = self.connect_to_postgres(database=database)
        cursor = conn.cursor()

        try:
            # 컬럼 정보 조회
            cursor.execute(
                sql.SQL("SELECT * FROM {} LIMIT 0").format(sql.Identifier(table))
            )
            columns = [desc[0] for desc in cursor.description]

            # 데이터 조회 (최대 100개)
            cursor.execute(
                sql.SQL("SELECT * FROM {} ORDER BY 1 LIMIT 100").format(sql.Identifier(table))
            )
            rows = cursor.fetchall()

            # 전체 행 수 조회
            cursor.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
            )
            total_count = cursor.fetchone()[0]

            return {
                "columns": columns,
                "rows": rows,
                "count": len(rows),
                "total": total_count
            }

        except Exception as e:
            raise Exception(f"테이블 데이터 조회 실패: {e}")
        finally:
            cursor.close()
            conn.close()


# 웹 페이지 HTML 템플릿
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PostgreSQL 데이터베이스 뷰어</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #5e72e4 0%, #825ee4 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }

        .main-content {
            padding: 30px;
        }

        .selector-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        .selector-box {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #e9ecef;
        }

        .selector-box h3 {
            color: #5e72e4;
            margin-bottom: 12px;
            font-size: 1.1em;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .select-dropdown {
            width: 100%;
            padding: 12px 15px;
            font-size: 1em;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            background: white;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .select-dropdown:hover {
            border-color: #5e72e4;
        }

        .select-dropdown:focus {
            outline: none;
            border-color: #5e72e4;
            box-shadow: 0 0 0 3px rgba(94, 114, 228, 0.1);
        }

        .select-dropdown option {
            padding: 10px;
        }

        .content-area {
            overflow-x: auto;
        }

        .content-area h2 {
            color: #2d3748;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #5e72e4;
        }

        .info-box {
            background: #f8f9fa;
            border-left: 4px solid #5e72e4;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }

        thead {
            background: linear-gradient(135deg, #5e72e4 0%, #825ee4 100%);
            color: white;
        }

        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }

        th {
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.9em;
            letter-spacing: 0.5px;
        }

        tbody tr:hover {
            background: #f8f9fa;
        }

        tbody tr:nth-child(even) {
            background: #f8f9fa;
        }

        tbody tr:nth-child(even):hover {
            background: #e9ecef;
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }

        .empty-state svg {
            width: 100px;
            height: 100px;
            margin-bottom: 20px;
            opacity: 0.5;
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            background: #5e72e4;
            color: white;
            border-radius: 12px;
            font-size: 0.85em;
            margin-left: 8px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }

        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #dc3545;
            margin-bottom: 20px;
        }

        @media (max-width: 768px) {
            .selector-container {
                grid-template-columns: 1fr;
                gap: 15px;
            }

            .header h1 {
                font-size: 1.8em;
            }

            .header p {
                font-size: 0.95em;
            }

            .main-content {
                padding: 20px;
            }

            .selector-box {
                padding: 15px;
            }

            table {
                font-size: 0.9em;
            }

            th, td {
                padding: 8px 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗄️ PostgreSQL 데이터베이스 뷰어</h1>
            <p>데이터베이스와 테이블을 선택하여 데이터를 조회하세요</p>
        </div>

        <div class="main-content">
            <!-- 상단 선택 영역 -->
            <div class="selector-container">
                <!-- 데이터베이스 선택 -->
                <div class="selector-box">
                    <h3>📁 데이터베이스 선택</h3>
                    <select class="select-dropdown" id="database-select" onchange="selectDatabase()">
                        <option value="">-- 데이터베이스를 선택하세요 --</option>
                        {% if databases %}
                            {% for db in databases %}
                            <option value="{{ db }}">{{ db }}</option>
                            {% endfor %}
                        {% endif %}
                    </select>
                </div>

                <!-- 테이블 선택 -->
                <div class="selector-box">
                    <h3>📋 테이블 선택</h3>
                    <select class="select-dropdown" id="table-select" onchange="selectTable()" disabled>
                        <option value="">-- 먼저 데이터베이스를 선택하세요 --</option>
                    </select>
                </div>
            </div>

            <!-- 데이터 표시 영역 -->
            <div class="content-area" id="content-area">
                <div class="empty-state">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                    </svg>
                    <h3>데이터베이스와 테이블을 선택하세요</h3>
                    <p>상단에서 데이터베이스와 테이블을 선택하면<br>데이터가 여기에 표시됩니다</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let selectedDatabase = null;

        function selectDatabase() {
            const dbSelect = document.getElementById('database-select');
            const tableSelect = document.getElementById('table-select');
            const contentArea = document.getElementById('content-area');

            selectedDatabase = dbSelect.value;

            if (!selectedDatabase) {
                // 데이터베이스 선택 해제
                tableSelect.disabled = true;
                tableSelect.innerHTML = '<option value="">-- 먼저 데이터베이스를 선택하세요 --</option>';
                contentArea.innerHTML = `
                    <div class="empty-state">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                        </svg>
                        <h3>데이터베이스와 테이블을 선택하세요</h3>
                        <p>상단에서 데이터베이스와 테이블을 선택하면<br>데이터가 여기에 표시됩니다</p>
                    </div>
                `;
                return;
            }

            // 테이블 목록 로드
            loadTables(selectedDatabase);
        }

        function loadTables(dbName) {
            const tableSelect = document.getElementById('table-select');
            tableSelect.disabled = true;
            tableSelect.innerHTML = '<option value="">테이블 목록 로딩 중...</option>';

            fetch(`/9_data/api/tables?database=${dbName}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        if (data.tables.length > 0) {
                            tableSelect.innerHTML = '<option value="">-- 테이블을 선택하세요 --</option>' +
                                data.tables.map(table =>
                                    `<option value="${table.name}">${table.name} (${table.columns}개 컬럼)</option>`
                                ).join('');
                            tableSelect.disabled = false;
                        } else {
                            tableSelect.innerHTML = '<option value="">테이블이 없습니다</option>';
                        }
                    } else {
                        tableSelect.innerHTML = `<option value="">오류: ${data.error}</option>`;
                    }
                })
                .catch(error => {
                    tableSelect.innerHTML = `<option value="">오류: ${error.message}</option>`;
                });
        }

        function selectTable() {
            if (!selectedDatabase) return;

            const tableSelect = document.getElementById('table-select');
            const tableName = tableSelect.value;

            if (!tableName) {
                return;
            }

            // 테이블 데이터 로드
            loadTableData(selectedDatabase, tableName);
        }

        function loadTableData(dbName, tableName) {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = '<div class="loading">데이터 로딩 중...</div>';

            fetch(`/9_data/api/data?database=${dbName}&table=${tableName}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        renderTable(dbName, tableName, data.data);
                    } else {
                        contentArea.innerHTML = `<div class="error">${data.error}</div>`;
                    }
                })
                .catch(error => {
                    contentArea.innerHTML = `<div class="error">오류: ${error.message}</div>`;
                });
        }

        function renderTable(dbName, tableName, tableData) {
            const contentArea = document.getElementById('content-area');

            let html = `
                <h2>${tableName}</h2>
                <div class="info-box">
                    <strong>📊 데이터베이스:</strong> ${dbName}<br>
                    <strong>📈 표시된 행:</strong> ${tableData.count}개
                    <strong>📦 전체 행:</strong> ${tableData.total}개
                    ${tableData.total > 100 ? '<br><em style="color: #e74c3c;">※ 최대 100개까지만 표시됩니다</em>' : ''}
                </div>
            `;

            if (tableData.rows.length > 0) {
                html += '<table><thead><tr>';
                tableData.columns.forEach(col => {
                    html += `<th>${col}</th>`;
                });
                html += '</tr></thead><tbody>';

                tableData.rows.forEach(row => {
                    html += '<tr>';
                    row.forEach(cell => {
                        html += `<td>${cell !== null ? cell : '<em style="color: #999;">NULL</em>'}</td>`;
                    });
                    html += '</tr>';
                });

                html += '</tbody></table>';
            } else {
                html += '<div class="empty-state"><p>데이터가 없습니다</p></div>';
            }

            contentArea.innerHTML = html;
        }
    </script>
</body>
</html>
"""


def render():
    """Flask 라우트에서 호출되는 메인 함수"""
    try:
        viewer = PostgresWebViewer()
        databases = viewer.get_databases()

        return render_template_string(HTML_TEMPLATE, databases=databases)

    except Exception as e:
        error_html = f"""
        <div style="padding: 40px; text-align: center;">
            <h1 style="color: #dc3545;">❌ 오류 발생</h1>
            <p style="color: #6c757d; margin-top: 20px;">{str(e)}</p>
            <p style="color: #6c757d; margin-top: 10px;">PostgreSQL 연결 정보를 확인하세요.</p>
        </div>
        """
        return error_html
