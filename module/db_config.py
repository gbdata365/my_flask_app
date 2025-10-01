import pymysql
import psycopg2
import psycopg2.extras
import os
from urllib.parse import urlparse


def get_config():
    """MySQL 설정"""
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "user": os.environ.get("DB_USER", "happyUser"),
        "password": os.environ.get("DB_PASS", "happy7471!"),
        "database": os.environ.get("DB_NAME", "gbd_data"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


def get_db_connection():
    """MySQL 연결"""
    return pymysql.connect(**get_config())


def get_postgres_config():
    """PostgreSQL 설정 - DATABASE_URL 또는 개별 환경변수 사용"""
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        # DATABASE_URL 파싱 (예: postgresql://user:pass@host:5432/dbname)
        result = urlparse(database_url)
        return {
            "host": result.hostname,
            "port": result.port or 5432,
            "database": result.path[1:],  # 앞의 '/' 제거
            "user": result.username,
            "password": result.password,
        }
    else:
        # 개별 환경변수 사용
        return {
            "host": os.environ.get("POSTGRES_HOST", "localhost"),
            "port": int(os.environ.get("POSTGRES_PORT", "5432")),
            "database": os.environ.get("POSTGRES_DB", "postgres"),
            "user": os.environ.get("POSTGRES_USER", "postgres"),
            "password": os.environ.get("POSTGRES_PASSWORD", ""),
        }


def get_postgres_connection():
    """PostgreSQL 연결 (딕셔너리 커서 사용)"""
    config = get_postgres_config()
    return psycopg2.connect(
        **config,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
