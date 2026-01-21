"""
PostgreSQL 데이터베이스 관리 GUI 프로그램
- 데이터베이스 생성 (gbdodata)
- 테이블 생성 (gbdo_code)
- 데이터베이스 목록 조회 및 선택
- 테이블 목록 조회 및 선택
- 테이블 데이터 조회
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import os

# 상위 디렉토리를 Python 경로에 추가 (module 폴더 접근용)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module.db_config import get_postgres_config


class PostgresDBManager:
    """PostgreSQL 데이터베이스 및 테이블 관리 클래스"""

    def __init__(self):
        """초기화: PostgreSQL 설정 로드"""
        self.config = get_postgres_config()
        self.target_db = "gbdodata"  # 생성할 데이터베이스 이름
        self.table_name = "gbdo_code"  # 생성할 테이블 이름

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

    def create_database(self):
        """데이터베이스 생성 (이미 존재하면 패스)"""
        conn = self.connect_to_postgres()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        try:
            # 데이터베이스 존재 여부 확인
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (self.target_db,)
            )
            exists = cursor.fetchone()

            if not exists:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(self.target_db)
                    )
                )
                return f"✅ 데이터베이스 '{self.target_db}' 생성 완료!"
            else:
                return f"ℹ️  데이터베이스 '{self.target_db}'가 이미 존재합니다."

        except Exception as e:
            raise Exception(f"데이터베이스 생성 실패: {e}")
        finally:
            cursor.close()
            conn.close()

    def create_table(self):
        """gbdo_code 테이블 생성"""
        conn = self.connect_to_postgres(database=self.target_db)
        cursor = conn.cursor()

        try:
            # 테이블 존재 여부 확인
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (self.table_name,)
            )
            exists = cursor.fetchone()

            if not exists:
                create_table_query = f"""
                CREATE TABLE {self.table_name} (
                    id SERIAL PRIMARY KEY,
                    구분1 VARCHAR(100) NOT NULL,
                    구분2 VARCHAR(100),
                    코드 VARCHAR(50) NOT NULL,
                    코드명 VARCHAR(200) NOT NULL,
                    생성일시 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    수정일시 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(구분1, 코드)
                )
                """
                cursor.execute(create_table_query)
                conn.commit()
                return f"✅ 테이블 '{self.table_name}' 생성 완료!"
            else:
                return f"ℹ️  테이블 '{self.table_name}'가 이미 존재합니다."

        except Exception as e:
            conn.rollback()
            raise Exception(f"테이블 생성 실패: {e}")
        finally:
            cursor.close()
            conn.close()

    def insert_sample_data(self):
        """샘플 데이터 삽입"""
        conn = self.connect_to_postgres(database=self.target_db)
        cursor = conn.cursor()

        try:
            # 기존 데이터 확인
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            count = cursor.fetchone()[0]

            if count > 0:
                return f"ℹ️  이미 {count}개의 데이터가 존재합니다."

            # 샘플 데이터 삽입
            sample_data = [
                ("직급", "일반직", "001", "사원"),
                ("직급", "일반직", "002", "주임"),
                ("직급", "일반직", "003", "대리"),
                ("직급", "일반직", "004", "과장"),
                ("직급", "일반직", "005", "차장"),
                ("부서", None, "D01", "개발팀"),
                ("부서", None, "D02", "영업팀"),
                ("부서", None, "D03", "인사팀"),
                ("지역", None, "SEL", "서울"),
                ("지역", None, "BUS", "부산"),
            ]

            insert_query = f"""
            INSERT INTO {self.table_name} (구분1, 구분2, 코드, 코드명)
            VALUES (%s, %s, %s, %s)
            """
            cursor.executemany(insert_query, sample_data)
            conn.commit()

            return f"✅ 샘플 데이터 {len(sample_data)}개 삽입 완료!"

        except Exception as e:
            conn.rollback()
            raise Exception(f"샘플 데이터 삽입 실패: {e}")
        finally:
            cursor.close()
            conn.close()

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
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
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

            # 데이터 조회
            cursor.execute(
                sql.SQL("SELECT * FROM {} ORDER BY 1 LIMIT 1000").format(sql.Identifier(table))
            )
            rows = cursor.fetchall()

            return columns, rows

        except Exception as e:
            raise Exception(f"테이블 데이터 조회 실패: {e}")
        finally:
            cursor.close()
            conn.close()


class DatabaseGUI:
    """PostgreSQL 데이터베이스 관리 GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("PostgreSQL 데이터베이스 관리")
        self.root.geometry("1200x700")

        self.db_manager = PostgresDBManager()
        self.selected_database = None
        self.selected_table = None

        self.create_widgets()

    def create_widgets(self):
        """GUI 위젯 생성"""
        # 상단 프레임: 초기화 버튼
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E))

        ttk.Button(
            top_frame,
            text="🔧 데이터베이스 초기화 (gbdodata/gbdo_code 생성)",
            command=self.initialize_database,
            width=50
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            top_frame,
            text="🔄 새로고침",
            command=self.refresh_database_list,
            width=15
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            top_frame,
            text="ℹ️ 연결 정보",
            command=self.show_connection_info,
            width=15
        ).pack(side=tk.LEFT, padx=5)

        # 중앙 프레임: 데이터베이스 목록, 테이블 목록, 데이터 표시
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 데이터베이스 목록 (왼쪽)
        db_frame = ttk.LabelFrame(main_frame, text="📁 데이터베이스 목록", padding="10")
        db_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        self.db_listbox = tk.Listbox(db_frame, width=25, height=25)
        self.db_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.db_listbox.bind("<<ListboxSelect>>", self.on_database_select)

        db_scrollbar = ttk.Scrollbar(db_frame, orient=tk.VERTICAL, command=self.db_listbox.yview)
        db_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.db_listbox.config(yscrollcommand=db_scrollbar.set)

        # 테이블 목록 (중간)
        table_frame = ttk.LabelFrame(main_frame, text="📋 테이블 목록", padding="10")
        table_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)

        self.table_listbox = tk.Listbox(table_frame, width=25, height=25)
        self.table_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.table_listbox.bind("<<ListboxSelect>>", self.on_table_select)

        table_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.table_listbox.yview)
        table_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.table_listbox.config(yscrollcommand=table_scrollbar.set)

        # 데이터 표시 (오른쪽)
        data_frame = ttk.LabelFrame(main_frame, text="📊 테이블 데이터", padding="10")
        data_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))

        # Treeview로 테이블 데이터 표시
        self.tree_scroll_y = ttk.Scrollbar(data_frame, orient=tk.VERTICAL)
        self.tree_scroll_x = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL)

        self.data_tree = ttk.Treeview(
            data_frame,
            yscrollcommand=self.tree_scroll_y.set,
            xscrollcommand=self.tree_scroll_x.set
        )

        self.tree_scroll_y.config(command=self.data_tree.yview)
        self.tree_scroll_x.config(command=self.data_tree.xview)

        self.tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.data_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 하단 프레임: 로그 메시지
        log_frame = ttk.LabelFrame(self.root, text="📝 로그", padding="10")
        log_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=10, pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 그리드 가중치 설정
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=3)
        main_frame.rowconfigure(0, weight=1)

        # 초기 데이터베이스 목록 로드 (연결 실패 시에도 GUI는 표시)
        self.log_message("🚀 PostgreSQL 데이터베이스 관리 프로그램 시작")
        self.log_message("💡 '새로고침' 버튼을 눌러 데이터베이스 목록을 불러오세요")

        # 자동으로 데이터베이스 목록 로드 시도 (실패해도 무시)
        try:
            self.refresh_database_list()
        except Exception as e:
            self.log_message(f"⚠️  초기 연결 실패: {str(e)}")
            self.log_message("⚠️  PostgreSQL 연결 정보를 확인하고 '새로고침'을 눌러주세요")

    def log_message(self, message):
        """로그 메시지 출력"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def initialize_database(self):
        """데이터베이스 및 테이블 초기화"""
        try:
            self.log_message("=" * 60)
            self.log_message("🚀 데이터베이스 초기화 시작...")

            # 1. 데이터베이스 생성
            msg = self.db_manager.create_database()
            self.log_message(msg)

            # 2. 테이블 생성
            msg = self.db_manager.create_table()
            self.log_message(msg)

            # 3. 샘플 데이터 삽입
            msg = self.db_manager.insert_sample_data()
            self.log_message(msg)

            self.log_message("✅ 초기화 완료!")
            self.log_message("=" * 60)

            # 데이터베이스 목록 새로고침
            self.refresh_database_list()

            messagebox.showinfo("완료", "데이터베이스 초기화가 완료되었습니다!")

        except Exception as e:
            error_msg = f"❌ 초기화 실패: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("오류", error_msg)

    def refresh_database_list(self):
        """데이터베이스 목록 새로고침"""
        try:
            databases = self.db_manager.get_databases()

            self.db_listbox.delete(0, tk.END)
            for db in databases:
                self.db_listbox.insert(tk.END, db)

            self.log_message(f"📁 데이터베이스 {len(databases)}개 조회 완료")

        except Exception as e:
            error_msg = f"❌ 데이터베이스 목록 조회 실패: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("오류", error_msg)

    def on_database_select(self, event):
        """데이터베이스 선택 이벤트"""
        selection = self.db_listbox.curselection()
        if not selection:
            return

        self.selected_database = self.db_listbox.get(selection[0])
        self.log_message(f"📁 선택된 데이터베이스: {self.selected_database}")

        # 테이블 목록 로드
        try:
            tables = self.db_manager.get_tables(self.selected_database)

            self.table_listbox.delete(0, tk.END)
            for table in tables:
                self.table_listbox.insert(tk.END, table)

            self.log_message(f"📋 테이블 {len(tables)}개 조회 완료")

            # 데이터 트리 초기화
            self.clear_data_tree()

        except Exception as e:
            error_msg = f"❌ 테이블 목록 조회 실패: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("오류", error_msg)

    def on_table_select(self, event):
        """테이블 선택 이벤트"""
        selection = self.table_listbox.curselection()
        if not selection:
            return

        self.selected_table = self.table_listbox.get(selection[0])
        self.log_message(f"📋 선택된 테이블: {self.selected_table}")

        # 테이블 데이터 로드
        try:
            columns, rows = self.db_manager.get_table_data(
                self.selected_database,
                self.selected_table
            )

            # 트리뷰 초기화
            self.clear_data_tree()

            # 컬럼 설정
            self.data_tree["columns"] = columns
            self.data_tree["show"] = "headings"

            for col in columns:
                self.data_tree.heading(col, text=col)
                self.data_tree.column(col, width=120, anchor=tk.W)

            # 데이터 삽입
            for row in rows:
                self.data_tree.insert("", tk.END, values=row)

            self.log_message(f"📊 {len(rows)}개의 행 조회 완료")

        except Exception as e:
            error_msg = f"❌ 테이블 데이터 조회 실패: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("오류", error_msg)

    def clear_data_tree(self):
        """데이터 트리뷰 초기화"""
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        self.data_tree["columns"] = ()

    def show_connection_info(self):
        """PostgreSQL 연결 정보 표시"""
        config = self.db_manager.config
        info = f"""
PostgreSQL 연결 정보:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
호스트: {config.get('host', 'N/A')}
포트: {config.get('port', 'N/A')}
데이터베이스: {config.get('database', 'N/A')}
사용자: {config.get('user', 'N/A')}
비밀번호: {'설정됨' if config.get('password') else '미설정'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 .env 파일 또는 환경변수에서 설정을 확인하세요
"""
        self.log_message(info)
        messagebox.showinfo("연결 정보", info)


def main():
    """메인 실행 함수"""
    root = tk.Tk()
    app = DatabaseGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
