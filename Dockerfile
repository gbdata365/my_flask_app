# Python 3.13 공식 이미지 사용
FROM python:3.13-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    wget \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Python 종속성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 복사
COPY . .

# uploads 디렉토리 생성 및 권한 설정
RUN mkdir -p uploads && chmod 755 uploads

# 데이터 디렉토리들 생성
RUN mkdir -p 1_giup/data 2_의료통계/data 3_csv_dashboard/data

# 애플리케이션 사용자 생성 (보안을 위해)
RUN groupadd -r flaskapp && useradd -r -g flaskapp flaskapp
RUN chown -R flaskapp:flaskapp /app

# 포트 8000 노출 (Gunicorn 기본 포트)
EXPOSE 8000

# 헬스체크 엔드포인트 추가를 위한 간단한 스크립트
RUN echo '#!/bin/bash\necho "from flask import Flask; app = Flask(__name__); @app.route(\"/health\"); def health(): return \"OK\", 200; app.run(host=\"0.0.0.0\", port=8001)" > /tmp/health.py' > /tmp/create_health.sh && chmod +x /tmp/create_health.sh

# 헬스체크 스크립트 생성
COPY <<EOF /app/health_check.py
from flask import Flask
import sys
import os

# 메인 앱 경로 추가
sys.path.insert(0, '/app')

app = Flask(__name__)

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=False)
EOF

# Gunicorn 설정 파일
COPY <<EOF /app/gunicorn.conf.py
# Gunicorn 설정 파일
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 5
preload_app = True
user = "flaskapp"
group = "flaskapp"

# 로깅 설정
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 프로세스 이름
proc_name = "flask_dashboard"

# 메모리 사용량 제한
max_requests_jitter = 100
worker_tmp_dir = "/dev/shm"

# 성능 튜닝
worker_connections = 1000
EOF

# 시작 스크립트 생성
COPY <<EOF /app/start.sh
#!/bin/bash
set -e

echo "Flask Dashboard App 시작 중..."

# 데이터베이스 연결 대기
echo "데이터베이스 연결 확인 중..."
while ! python -c "
import pymysql
import os
import time
for i in range(30):
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', 'mariadb'),
            user=os.getenv('DB_USER', 'dashuser'),
            password=os.getenv('DB_PASSWORD', 'dashpass'),
            database=os.getenv('DB_NAME', 'dashboard_db'),
            port=int(os.getenv('DB_PORT', '3306'))
        )
        conn.close()
        print('데이터베이스 연결 성공!')
        break
    except Exception as e:
        print(f'데이터베이스 연결 시도 {i+1}/30: {e}')
        time.sleep(2)
else:
    print('데이터베이스 연결 실패!')
    exit(1)
"; do
    echo "데이터베이스 연결 대기 중..."
    sleep 2
done

echo "헬스체크 서버 시작..."
python /app/health_check.py &

echo "Gunicorn으로 Flask 앱 시작..."
exec gunicorn --config gunicorn.conf.py main_app:app
EOF

RUN chmod +x /app/start.sh

# 비루트 사용자로 전환
USER flaskapp

# 컨테이너 시작 시 실행할 명령어
CMD ["/app/start.sh"]