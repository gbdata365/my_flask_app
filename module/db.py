# -*- coding: utf-8 -*-
"""
데이터베이스 연결 모듈 (Database Connection Module)
==================================================

이 모듈은 PostgreSQL 데이터베이스 연결 및 쿼리 실행 기능을 제공합니다.
환경 변수에서 접속 정보를 읽어 연결을 생성합니다.

필요 환경 변수 (.env 파일):
    - POSTGRES_HOST: 데이터베이스 호스트 (예: localhost, 192.168.1.100)
    - POSTGRES_PORT: 포트 번호 (기본값: 5432)
    - POSTGRES_DB: 데이터베이스 이름 (예: population, economy)
    - POSTGRES_USER: 사용자 이름 (예: postgres)
    - POSTGRES_PASSWORD: 비밀번호

.env 파일 예시:
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_DB=population
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=your_password

사용 예시:
    >>> from module.db import get_db_connection
    >>> import pandas as pd

    >>> # 방법 1: pandas와 함께 사용
    >>> conn = get_db_connection()
    >>> df = pd.read_sql("SELECT * FROM fact_population_basic", conn)
    >>> conn.close()

    >>> # 방법 2: with 문 사용 (자동 close)
    >>> with get_db_connection() as conn:
    ...     df = pd.read_sql("SELECT * FROM dim_admin_area", conn)

주의사항:
    - 사용 후 반드시 conn.close() 호출 또는 with 문 사용
    - 대량 데이터 조회 시 LIMIT 사용 권장
    - 트랜잭션 필요 시 conn.commit() 호출

Author: Claude AI Agent
Created: 2024-12-18
"""

import os
from pathlib import Path
import psycopg2
from sqlalchemy import create_engine
from loguru import logger
from dotenv import load_dotenv

# SQLAlchemy 엔진 캐시 (싱글톤)
_engine_cache = {}

# .env 파일 로드 (여러 위치에서 검색)
# 1. 현재 모듈 폴더의 .env
# 2. 상위 폴더의 .env
# 3. project 폴더의 .env
_module_dir = Path(__file__).parent
_env_paths = [
    _module_dir / '.env',                          # module/.env
    _module_dir.parent / '.env',                   # 01_claude_project/.env
    _module_dir.parent / 'project' / '.env',       # project/.env
]

for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        logger.info(f".env 파일 로드: {_env_path}")
        break


def get_postgres_config(database: str = None) -> dict:
    """
    PostgreSQL 접속 설정을 딕셔너리로 반환합니다.

    환경 변수에서 접속 정보를 읽어 psycopg2.connect()에 전달할 수 있는
    딕셔너리를 반환합니다.

    Args:
        database (str, optional): 연결할 데이터베이스 이름.
            None이면 POSTGRES_DB 환경 변수 사용.

    Returns:
        dict: PostgreSQL 접속 설정 딕셔너리
            {'host': ..., 'port': ..., 'database': ..., 'user': ..., 'password': ...}

    Examples:
        >>> config = get_postgres_config()
        >>> conn = psycopg2.connect(**config)
    """
    return {
        'host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'port': os.environ.get('POSTGRES_PORT', '5432'),
        'database': database or os.environ.get('POSTGRES_DB', 'postgres'),
        'user': os.environ.get('POSTGRES_USER', 'postgres'),
        'password': os.environ.get('POSTGRES_PASSWORD', '')
    }


def get_db_connection(database: str = None):
    """
    PostgreSQL 데이터베이스 연결을 생성합니다.

    환경 변수에서 접속 정보를 읽어 psycopg2 연결 객체를 반환합니다.
    연결 실패 시 예외가 발생하며, 로그에 에러 메시지가 기록됩니다.

    Args:
        database (str, optional): 연결할 데이터베이스 이름.
            None이면 POSTGRES_DB 환경 변수 사용.
            특정 DB 지정 시 해당 DB로 연결.
            예: 'population', 'economy', 'traffic'

    Returns:
        psycopg2.extensions.connection: PostgreSQL 연결 객체

    Raises:
        psycopg2.OperationalError: 연결 실패 시 (호스트 없음, 인증 실패 등)
        psycopg2.ProgrammingError: 잘못된 데이터베이스 이름

    Examples:
        >>> # 기본 데이터베이스 연결
        >>> conn = get_db_connection()
        >>> cursor = conn.cursor()
        >>> cursor.execute("SELECT COUNT(*) FROM fact_population_basic")
        >>> count = cursor.fetchone()[0]
        >>> print(f"총 {count}개 레코드")
        >>> conn.close()

        >>> # 특정 데이터베이스 연결
        >>> conn = get_db_connection(database='economy')
        >>> df = pd.read_sql("SELECT * FROM gdp_data", conn)
        >>> conn.close()

        >>> # pandas와 함께 사용 (권장)
        >>> conn = get_db_connection()
        >>> df = pd.read_sql('''
        ...     SELECT sido_nm, SUM(total_pop) as pop
        ...     FROM fact_population_basic p
        ...     JOIN dim_admin_area d ON p.admin_code = d.admin_code
        ...     GROUP BY sido_nm
        ... ''', conn)
        >>> conn.close()

    Note:
        - 환경 변수가 설정되지 않으면 기본값 사용 (localhost, 5432, postgres)
        - 연결 후 반드시 close() 호출 필요 (커넥션 풀 반환)
        - 대량 INSERT/UPDATE 후 commit() 필요
    """
    try:
        # 환경 변수에서 접속 정보 읽기 (없으면 기본값 사용)
        conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST', 'localhost'),
            port=os.environ.get('POSTGRES_PORT', '5432'),
            database=database or os.environ.get('POSTGRES_DB', 'postgres'),
            user=os.environ.get('POSTGRES_USER', 'postgres'),
            password=os.environ.get('POSTGRES_PASSWORD', '')
        )
        return conn

    except Exception as e:
        # 연결 실패 시 로그 기록 후 예외 재발생
        logger.error(f"DB 연결 실패: {e}")
        raise


def get_db_engine(database: str = None):
    """
    SQLAlchemy 엔진을 반환합니다.

    pandas의 read_sql() 함수에서 경고 없이 사용할 수 있습니다.
    엔진은 캐시되어 재사용됩니다.

    Args:
        database (str, optional): 연결할 데이터베이스 이름.
            None이면 POSTGRES_DB 환경 변수 사용.

    Returns:
        sqlalchemy.engine.Engine: SQLAlchemy 엔진 객체

    Examples:
        >>> from module.db import get_db_engine
        >>> import pandas as pd
        >>> engine = get_db_engine()
        >>> df = pd.read_sql("SELECT * FROM fact_population_basic", engine)
    """
    db_name = database or os.environ.get('POSTGRES_DB', 'postgres')

    # 캐시된 엔진이 있으면 반환
    if db_name in _engine_cache:
        return _engine_cache[db_name]

    try:
        host = os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('POSTGRES_PORT', '5432')
        user = os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('POSTGRES_PASSWORD', '')

        # SQLAlchemy 연결 문자열 생성
        connection_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
        engine = create_engine(connection_string)

        # 캐시에 저장
        _engine_cache[db_name] = engine
        logger.debug(f"SQLAlchemy 엔진 생성: {db_name}")

        return engine
    except Exception as e:
        logger.error(f"SQLAlchemy 엔진 생성 실패: {e}")
        raise


def execute_query(query: str, params: tuple = None, database: str = None):
    """
    SQL 쿼리를 실행하고 결과를 반환합니다.

    SELECT 쿼리 실행 후 모든 결과를 리스트로 반환합니다.
    연결은 자동으로 생성되고 종료됩니다.

    Args:
        query (str): 실행할 SQL 쿼리문.
            파라미터 바인딩은 %s 사용.
            예: "SELECT * FROM table WHERE id = %s"

        params (tuple, optional): 쿼리 파라미터.
            SQL 인젝션 방지를 위해 직접 문자열 조합 대신 사용.
            예: (123,), ('서울특별시', '202411')

        database (str, optional): 연결할 데이터베이스 이름.
            None이면 기본 데이터베이스 사용.

    Returns:
        list: 쿼리 결과 리스트. 각 행은 튜플.
            예: [(1, '서울', 1000), (2, '부산', 500)]

    Raises:
        psycopg2.Error: SQL 실행 오류 시

    Examples:
        >>> # 전체 조회
        >>> rows = execute_query("SELECT * FROM dim_admin_area LIMIT 5")
        >>> for row in rows:
        ...     print(row)

        >>> # 파라미터 바인딩 (SQL 인젝션 방지)
        >>> rows = execute_query(
        ...     "SELECT * FROM fact_population_basic WHERE base_ym = %s",
        ...     params=('202411',)
        ... )

        >>> # 집계 쿼리
        >>> result = execute_query('''
        ...     SELECT sido_nm, COUNT(*) as cnt
        ...     FROM dim_admin_area
        ...     GROUP BY sido_nm
        ... ''')

    Note:
        - SELECT 쿼리 전용 (INSERT/UPDATE/DELETE는 commit 필요)
        - 대량 데이터는 pandas.read_sql() 권장
        - 연결은 함수 종료 시 자동 close
    """
    conn = get_db_connection(database)
    try:
        with conn.cursor() as cur:
            # 쿼리 실행 (params가 있으면 바인딩)
            cur.execute(query, params)
            # 모든 결과 반환
            return cur.fetchall()
    finally:
        # 예외 발생 여부와 관계없이 연결 종료
        conn.close()
