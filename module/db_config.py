import pymysql
import os


def get_config():
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "user": os.environ.get("DB_USER", "happyUser"),
        "password": os.environ.get("DB_PASS", "happy7471!"),
        "database": os.environ.get("DB_NAME", "gbd_data"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


def get_db_connection():
    return pymysql.connect(**get_config())
