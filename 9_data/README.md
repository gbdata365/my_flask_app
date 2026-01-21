# 9_data - PostgreSQL 데이터베이스 관리

PostgreSQL 데이터베이스를 관리하고 조회하는 도구들을 포함합니다.

## 📁 파일 구조

```
9_data/
├── db_code_create.py    # GUI 데스크톱 애플리케이션 (tkinter)
├── routes/
│   └── db_viewer.py     # Flask 웹 애플리케이션용 뷰어
└── README.md
```

## 🚀 사용 방법

### 1️⃣ CLI 초기화 (데이터베이스/테이블 생성)

프로젝트 **루트 폴더**에서 실행:

```bash
python db_code_create.py
```

**기능:**
- 데이터베이스 `gbdodata` 생성
- 테이블 `gbdo_code` 생성
- 샘플 데이터 삽입

**테이블 구조 (gbdo_code):**
- `구분1` VARCHAR(100) - 필수 ✅
- `구분2` VARCHAR(100) - 선택
- `코드` VARCHAR(50) - 필수 ✅
- `코드명` VARCHAR(200) - 필수 ✅

---

### 2️⃣ GUI 데스크톱 애플리케이션

9_data 폴더에서 실행:

```bash
cd 9_data
python db_code_create.py
```

**기능:**
- 데이터베이스 목록 조회 (리스트박스)
- 테이블 목록 조회 (리스트박스)
- 테이블 데이터 조회 (트리뷰)
- 데이터베이스/테이블 초기화 버튼

**스크린샷:**
- 왼쪽: 데이터베이스 목록
- 중간: 테이블 목록
- 오른쪽: 선택된 테이블 데이터
- 하단: 로그 출력

---

### 3️⃣ Flask 웹 애플리케이션

Flask 앱 실행:

```bash
python main_app.py
```

웹 브라우저에서 접속:
```
http://localhost:5000/9_data
```

**기능:**
- 데이터베이스 목록 (왼쪽 패널)
- 테이블 목록 (중간 패널, 컬럼 수 표시)
- 테이블 데이터 (오른쪽, 최대 100행)
- 반응형 디자인 (모바일 지원)

---

## 🔧 설정

PostgreSQL 연결 정보는 `.env` 파일 또는 환경변수에서 설정:

```env
# DATABASE_URL 사용 (권장)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# 또는 개별 설정
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

연결 정보는 `module/db_config.py`에서 관리됩니다.

---

## 📋 API 엔드포인트 (Flask)

### 테이블 목록 조회
```
GET /9_data/api/tables?database=dbname
```

**응답:**
```json
{
  "success": true,
  "tables": [
    {"name": "gbdo_code", "columns": 7},
    {"name": "users", "columns": 5}
  ]
}
```

### 테이블 데이터 조회
```
GET /9_data/api/data?database=dbname&table=tablename
```

**응답:**
```json
{
  "success": true,
  "data": {
    "columns": ["id", "구분1", "코드", "코드명"],
    "rows": [[1, "직급", "001", "사원"], ...],
    "count": 10,
    "total": 100
  }
}
```

---

## ⚠️ 주의사항

- GUI 애플리케이션은 tkinter가 필요합니다 (Python 기본 포함)
- 웹 애플리케이션은 Flask가 필요합니다
- PostgreSQL 서버 연결이 필요합니다
- 연결 타임아웃: 5초

---

## 🐛 문제 해결

### "준비중입니다" 만 나타날 때
- Flask 앱이 제대로 시작되었는지 확인
- `9_data 라우트 시스템 등록 완료` 메시지 확인
- 브라우저 캐시 삭제 후 새로고침

### PostgreSQL 연결 실패
- `.env` 파일의 연결 정보 확인
- PostgreSQL 서버 실행 상태 확인
- 방화벽 설정 확인

### GUI 창이 안 뜰 때
- 올바른 폴더에서 실행하는지 확인
  - CLI 초기화: `python db_code_create.py` (프로젝트 루트)
  - GUI: `python db_code_create.py` (9_data 폴더)
