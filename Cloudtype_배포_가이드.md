# Cloudtype PostgreSQL 연동 및 배포 가이드

## 목차
1. [환경 구성 개요](#환경-구성-개요)
2. [로컬 환경 설정](#로컬-환경-설정)
3. [Cloudtype 배포 설정](#cloudtype-배포-설정)
4. [DBeaver 연결 설정](#dbeaver-연결-설정)
5. [트러블슈팅](#트러블슈팅)

---

## 환경 구성 개요

### 시스템 아키텍처

```
┌─────────────────────────────────────────────┐
│           Cloudtype 환경                     │
│  ┌──────────────┐      ┌──────────────┐    │
│  │ Flask App    │─────→│ PostgreSQL   │    │
│  │ (내부 연결)   │      │ postgresql:  │    │
│  │              │      │ 5432         │    │
│  └──────────────┘      └──────────────┘    │
└─────────────────────────────────────────────┘
                              │
                              │ 외부 접속
                              │ svc.sel3.cloudtype.app:32596
                              ↓
┌─────────────────────────────────────────────┐
│           로컬 개발 환경                      │
│  ┌──────────────┐      ┌──────────────┐    │
│  │ Flask App    │─────→│ PostgreSQL   │    │
│  │ (외부 연결)   │      │ (외부 엔드    │    │
│  │              │      │  포인트)      │    │
│  └──────────────┘      └──────────────┘    │
│                                             │
│  ┌──────────────┐                          │
│  │ DBeaver      │─────→ 외부 접속           │
│  └──────────────┘                          │
└─────────────────────────────────────────────┘
```

### 주요 개념

- **내부 호스트명**: `postgresql:5432` (Cloudtype 내부에서만 사용)
- **외부 엔드포인트**: `svc.sel3.cloudtype.app:32596` (로컬 개발 및 DBeaver 연결용)
- **환경 자동 감지**: `module/db_config.py`가 실행 환경을 자동 판단

---

## 로컬 환경 설정

### 1. `.env` 파일 구성

프로젝트 루트에 `.env` 파일 생성:

```env
# PostgreSQL 설정 (Cloudtype)
# 내부 연결 (Cloudtype 내부에서만 사용)
DATABASE_URL=postgresql://gbdo:rudqnrehc-jd11@postgresql:5432/postgres

# PostgreSQL 개별 항목
POSTGRES_DB=postgres
POSTGRES_USER=gbdo
POSTGRES_PASSWORD=rudqnrehc-jd11

# PostgreSQL 외부 접속 (로컬 개발용)
POSTGRES_HOST_EXTERNAL=svc.sel3.cloudtype.app
POSTGRES_PORT_EXTERNAL=32596

# Flask 애플리케이션 설정
FLASK_ENV=production
SECRET_KEY=csv_dashboard_secret_key_2024_docker

# 서버 설정
SERVER_HOST=0.0.0.0
SERVER_PORT=5000

# 로그 레벨
LOG_LEVEL=INFO
```

### 2. `.gitignore` 확인

`.env` 파일이 Git에 커밋되지 않도록 확인:

```gitignore
# .gitignore
.env
.env.local
```

### 3. 환경 자동 감지 코드

`module/db_config.py`는 실행 환경을 자동으로 감지합니다:

```python
def is_cloudtype_environment():
    """Cloudtype 환경인지 확인 (내부 호스트명 'postgresql' 접근 가능 여부)"""
    try:
        socket.gethostbyname('postgresql')
        return True
    except socket.gaierror:
        return False

def get_postgres_config():
    """PostgreSQL 설정 - 환경에 따라 자동 선택"""
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
```

### 4. 로컬 실행

```bash
cd C:\Users\user\00_claude_project\project
python main_app.py
```

브라우저에서 `http://localhost:5000` 접속

---

## Cloudtype 배포 설정

### 방법 1: 시크릿(Secret) 사용 (권장)

#### 장점
- ✅ GitHub에 민감한 정보를 커밋하지 않음
- ✅ YAML 파일에 비밀번호 노출 안 됨
- ✅ 비밀번호 변경 시 코드 수정 불필요

#### 설정 방법

1. **Cloudtype 대시보드 접속**
   - 프로젝트 선택 → **서비스** 탭 → 해당 서비스(my-flask-app11) 클릭
   - **설정** 탭 클릭

2. **시크릿 섹션에서 환경 변수 추가**

   | 키(Key) | 값(Value) |
   |---------|-----------|
   | `DATABASE_URL` | `postgresql://gbdo:rudqnrehc-jd11@postgresql:5432/postgres` |
   | `POSTGRES_DB` | `postgres` |
   | `POSTGRES_USER` | `gbdo` |
   | `POSTGRES_PASSWORD` | `rudqnrehc-jd11` |
   | `POSTGRES_HOST_EXTERNAL` | `svc.sel3.cloudtype.app` |
   | `POSTGRES_PORT_EXTERNAL` | `32596` |
   | `FLASK_ENV` | `production` |
   | `SECRET_KEY` | `csv_dashboard_secret_key_2024_docker` |
   | `SERVER_HOST` | `0.0.0.0` |
   | `SERVER_PORT` | `5000` |
   | `LOG_LEVEL` | `INFO` |

3. **서비스 재배포**
   - 변경사항 저장 후 재배포

---

### 방법 2: YAML 파일 사용

#### YAML 파일 구조

`.cloudtype.yaml` 또는 `@gb.data23_myflask_python_main.yaml`:

```yaml
name: my-flask-app11
app: python@3.12
options:
  ports: "5000"
  start: python main_app.py
  healthz: /
  env:
    - name: DATABASE_URL
      value: postgresql://gbdo:rudqnrehc-jd11@postgresql:5432/postgres
    - name: POSTGRES_DB
      value: postgres
    - name: POSTGRES_USER
      value: gbdo
    - name: POSTGRES_PASSWORD
      value: rudqnrehc-jd11
    - name: POSTGRES_HOST_EXTERNAL
      value: svc.sel3.cloudtype.app
    - name: POSTGRES_PORT_EXTERNAL
      value: "32596"
    - name: FLASK_ENV
      value: production
    - name: SECRET_KEY
      value: csv_dashboard_secret_key_2024_docker
    - name: SERVER_HOST
      value: 0.0.0.0
    - name: SERVER_PORT
      value: "5000"
    - name: LOG_LEVEL
      value: INFO
  buildenv: []
resources:
  spot: false
  memory: 0.5
context:
  git:
    url: https://github.com/gbdata365/my_flask_app.git
    branch: main
---
name: postgresql
app: postgresql@16
options:
  rootusername: gbdo
  rootpassword: rudqnrehcjd1!
resources:
  spot: false
  cpu: 0
  memory: 0.5
  disk: 1
  replicas: 1
context:
  preset: postgresql
```

#### YAML 파일 업로드 방법

1. Cloudtype 대시보드 → **서비스** 탭
2. 우측 상단 **YAML 다운로드** 버튼 근처의 업로드 옵션
3. 또는 GitHub에 YAML 파일 푸시 후 자동 배포

---

### 방법 3: 여러 서비스 운영 (Flask + Streamlit)

```yaml
# Flask 앱
name: my-flask-app11
app: python@3.12
options:
  ports: "5000"
  start: python main_app.py
  env:
    - name: DATABASE_URL
      value: postgresql://gbdo:rudqnrehc-jd11@postgresql:5432/postgres
    - name: FLASK_ENV
      value: production
resources:
  memory: 0.5
context:
  git:
    url: https://github.com/gbdata365/my_flask_app.git
    branch: main
---
# Streamlit 앱
name: my-streamlit-app
app: python@3.12
options:
  ports: "8501"
  start: streamlit run app.py --server.port=8501
  env:
    - name: DATABASE_URL
      value: postgresql://gbdo:rudqnrehc-jd11@postgresql:5432/postgres
    - name: STREAMLIT_SERVER_HEADLESS
      value: "true"
resources:
  memory: 0.5
context:
  git:
    url: https://github.com/gbdata365/my_streamlit_app.git
    branch: main
---
# PostgreSQL
name: postgresql
app: postgresql@16
options:
  rootusername: gbdo
  rootpassword: rudqnrehcjd1!
resources:
  memory: 0.5
  disk: 1
context:
  preset: postgresql
```

**중요**: 각 서비스마다 Cloudtype 대시보드에서 **별도로 시크릿 설정** 필요

---

## DBeaver 연결 설정

### 연결 정보

로컬 DBeaver에서 Cloudtype PostgreSQL에 연결하려면 **외부 접속 정보** 사용:

| 항목 | 값 |
|------|-----|
| **Host** | `svc.sel3.cloudtype.app` |
| **Port** | `32596` |
| **Database** | `postgres` |
| **Username** | `gbdo` |
| **Password** | `rudqnrehc-jd11` |

### 연결 단계

1. **DBeaver 실행**
2. **Database** → **New Database Connection** → **PostgreSQL** 선택
3. **Main 탭**에서 위 연결 정보 입력
4. **Test Connection** 클릭하여 연결 테스트
5. 성공하면 **Finish** 클릭

### SSL 설정 (필요시)

**SSL 탭**에서:
- **SSL Mode**: `require` 또는 `prefer` 시도

---

## 트러블슈팅

### 1. 로컬에서 PostgreSQL 연결 실패

**오류**: `could not translate host name "postgresql" to address`

**원인**: 로컬 환경에서 Cloudtype 내부 호스트명 사용 시도

**해결**:
- `.env` 파일에 `POSTGRES_HOST_EXTERNAL`와 `POSTGRES_PORT_EXTERNAL` 설정 확인
- `module/db_config.py`의 `is_cloudtype_environment()` 함수 동작 확인

```bash
# 테스트
python -c "import socket; socket.gethostbyname('postgresql')"
# 로컬에서는 에러 발생 → 정상 (외부 접속 사용)
```

---

### 2. DBeaver 연결 타임아웃

**원인**:
- Cloudtype 방화벽 설정
- 외부 포트 변경

**해결**:
1. Cloudtype 대시보드에서 PostgreSQL 서비스의 **외부 엔드포인트** 확인
2. 포트가 변경되었을 수 있음 (예: 32596 → 다른 포트)
3. `.env` 파일의 `POSTGRES_PORT_EXTERNAL` 업데이트

---

### 3. Cloudtype 배포 후 DB 연결 실패

**확인 사항**:
1. **환경 변수 설정 확인**
   - Cloudtype 대시보드 → 서비스 → 설정 → 시크릿
   - 모든 필수 환경 변수가 설정되어 있는지 확인

2. **PostgreSQL 서비스 실행 상태**
   - Cloudtype 대시보드에서 PostgreSQL 서비스가 실행 중인지 확인
   - 로그 확인

3. **네트워크 연결 확인**
   - Flask 앱과 PostgreSQL이 같은 프로젝트 내에 있는지 확인
   - 내부 호스트명 `postgresql`이 정확히 설정되어 있는지 확인

---

### 4. GitHub에 .env 파일이 커밋됨

**해결**:
```bash
# .env 파일을 Git에서 제거 (파일은 유지)
git rm --cached .env

# .gitignore에 추가 확인
echo ".env" >> .gitignore

# 커밋
git add .gitignore
git commit -m "Remove .env from git tracking"
git push
```

---

### 5. 1_giup/routes/load.py 실행 시 오류

**오류**: `render() 함수가 없습니다`

**해결**: `routes` 폴더의 Python 파일은 반드시 `render()` 함수 필요

```python
def render():
    """동적 라우트 시스템에서 호출되는 메인 함수"""
    from flask import request

    if request and request.method == 'POST':
        # POST 요청 처리
        return execute_and_show_result()
    else:
        # GET 요청 처리
        return show_upload_page()
```

---

## 배포 체크리스트

### 로컬 개발 환경

- [ ] `.env` 파일 생성 및 설정
- [ ] `.env`가 `.gitignore`에 포함되어 있음
- [ ] `requirements.txt` 최신 상태
- [ ] 로컬에서 정상 실행 확인 (`python main_app.py`)

### GitHub

- [ ] `.env` 파일이 Git에 포함되지 않음
- [ ] 코드 커밋 및 푸시
- [ ] `main` 브랜치에 최신 코드 반영

### Cloudtype

- [ ] PostgreSQL 서비스 실행 중
- [ ] Flask 서비스의 시크릿(환경 변수) 설정 완료
- [ ] YAML 파일 설정 확인 (사용 시)
- [ ] 서비스 배포 및 실행 상태 확인
- [ ] 로그에서 에러 없는지 확인

### 데이터베이스

- [ ] DBeaver에서 연결 테스트 성공
- [ ] 필요한 테이블 생성 완료
- [ ] 데이터 업로드 테스트 (1_giup/routes/load.py)

---

## 참고 자료

### 프로젝트 구조

```
project/
├── main_app.py              # Flask 메인 앱
├── .env                     # 환경 변수 (Git 제외)
├── .gitignore               # Git 제외 파일 목록
├── requirements.txt         # Python 패키지 목록
├── .cloudtype.yaml          # Cloudtype 배포 설정 (선택)
├── module/
│   ├── db_config.py         # DB 연결 설정 (환경 자동 감지)
│   ├── menu_generator.py
│   └── ...
├── 1_giup/
│   ├── routes/
│   │   └── load.py          # 데이터 업로드 라우트
│   ├── data/
│   │   └── 집계표_202312.xlsx
│   └── ...
└── templates/
    └── ...
```

### 주요 파일

#### `main_app.py:76-116`
```python
def register_giup_routes(app):
    """1_giup 카테고리의 동적 라우트 시스템"""
    # Routes 실행
    @app.route("/1_giup/routes/<filename>", methods=['GET', 'POST'])
    def giup_route_exec(filename):
        """routes 폴더의 .py 파일을 동적으로 실행"""
        # ...
```

#### `module/db_config.py:26-57`
- `is_cloudtype_environment()`: 환경 자동 감지
- `get_postgres_config()`: 환경별 설정 반환
- `get_postgres_connection()`: PostgreSQL 연결

---

## 문의 및 지원

문제가 발생하면 다음을 확인하세요:

1. **로그 확인**: Cloudtype 대시보드 → 서비스 → 로그
2. **환경 변수**: 모든 필수 변수가 설정되어 있는지
3. **네트워크**: 서비스 간 연결 상태
4. **버전**: Python, PostgreSQL 버전 호환성

---

**작성일**: 2025-10-02
**버전**: 1.0
