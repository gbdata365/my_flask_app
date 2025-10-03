import pymysql
import psycopg2
import psycopg2.extras
import os
import socket
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


def is_cloudtype_environment():
    """Cloudtype 환경인지 확인 (내부 호스트명 'postgresql' 접근 가능 여부)"""
    try:
        socket.gethostbyname('postgresql')
        return True
    except socket.gaierror:
        return False


def get_postgres_config():
    """PostgreSQL 설정 - 환경에 따라 자동 선택"""
    # Cloudtype 내부 환경인지 확인
    is_cloudtype = is_cloudtype_environment()

    if is_cloudtype:
        # Cloudtype 내부: 내부 호스트명 사용
        return {
            "host": "postgresql",
            "port": 5432,
            "database": os.environ.get("POSTGRES_DB", "postgres"),
            "user": os.environ.get("POSTGRES_USER", "gbdo"),
            "password": os.environ.get("POSTGRES_PASSWORD", "rudqnrehc-jd11"),
        }
    else:
        # 로컬 환경: 외부 접속 정보 사용
        return {
            "host": os.environ.get("POSTGRES_HOST_EXTERNAL", "svc.sel3.cloudtype.app"),
            "port": int(os.environ.get("POSTGRES_PORT_EXTERNAL", "32596")),
            "database": os.environ.get("POSTGRES_DB", "postgres"),
            "user": os.environ.get("POSTGRES_USER", "gbdo"),
            "password": os.environ.get("POSTGRES_PASSWORD", "rudqnrehc-jd11"),
        }


def get_postgres_connection():
    
    """PostgreSQL 연결 (딕셔너리 커서 사용)"""
    config = get_postgres_config()
    return psycopg2.connect(
        **config,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
