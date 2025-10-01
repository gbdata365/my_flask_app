# 클라우드타입 배포 가이드

## 1. 사전 준비

### 1.1 필요한 것들
- GitHub 계정
- CloudType 계정 (https://cloudtype.io)
- PostgreSQL 데이터베이스 (CloudType에서 제공)

### 1.2 파일 확인
```
project/
├── main_app.py              # Flask 애플리케이션
├── requirements.txt         # Python 패키지 목록
├── .env.example            # 환경변수 예시
├── .gitignore              # Git 제외 파일 목록
├── 1_giup/
│   ├── load.py            # 자동 데이터 업로드
│   └── load_select.py     # 선택적 데이터 업로드
└── module/
    └── db_config.py        # 데이터베이스 설정
```

---

## 2. GitHub에 코드 업로드

### 2.1 자동 배포 (추천)
```bash
git_deploy.bat
```

배치 파일을 실행하면 자동으로:
1. Git 저장소 초기화
2. 파일 스테이징
3. 커밋
4. GitHub에 푸시

### 2.2 수동 배포
```bash
git add .
git commit -m "Update application"
git push origin main
```

---

## 3. CloudType 설정

### 3.1 PostgreSQL 데이터베이스 생성

1. **CloudType 대시보드** 접속
2. **"새 서비스"** → **"데이터베이스"** 선택
3. **PostgreSQL** 템플릿 선택
4. 서비스 이름: `postgresql` (권장)
5. **"배포"** 클릭

#### 연결 정보 확인
배포 완료 후:
1. PostgreSQL 서비스 클릭
2. **"환경변수"** 탭 확인
3. 다음 정보 복사:
   ```
   POSTGRES_HOST=xxx
   POSTGRES_PORT=5432
   POSTGRES_DB=xxx
   POSTGRES_USER=xxx
   POSTGRES_PASSWORD=xxx
   ```

### 3.2 Flask 애플리케이션 배포

1. **"새 서비스"** → **"웹 서비스"** 선택
2. **GitHub 연동** 선택
3. 저장소 선택: `my_flask_app` (또는 본인의 저장소명)
4. 브랜치: `main`

#### 빌드 설정
```
Build Command: (비워둠)
Start Command: python main_app.py
Port: 5000
```

#### 환경변수 설정 (중요!)

**방법 1: DATABASE_URL 사용 (권장)**
```
DATABASE_URL=postgresql://사용자명:비밀번호@postgresql:5432/데이터베이스명
```

예시:
```
DATABASE_URL=postgresql://gbdo:rudqnrehc-jd11@postgresql:5432/postgres
```

**방법 2: 개별 변수 사용**
```
POSTGRES_HOST=postgresql
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=gbdo
POSTGRES_PASSWORD=rudqnrehc-jd11
```

> **💡 팁**: PostgreSQL 서비스와 Flask 앱이 같은 프로젝트에 있으면 호스트는 `postgresql` (서비스 이름)을 사용하면 됩니다.

5. **"배포"** 클릭
6. 배포 로그 확인

---

## 4. 데이터 업로드

### 4.1 로컬에서 업로드 (추천)

배포 완료 후, 로컬에서 데이터를 업로드할 수 있습니다:

#### 방법 1: 자동 업로드
```bash
cd 1_giup
python load.py
```
- `data/집계표_202312.xlsx` 파일을 자동으로 업로드

#### 방법 2: 파일 선택 업로드
```bash
cd 1_giup
python load_select.py
```
- 여러 집계표 파일 중 선택하여 업로드
- 같은 년월 데이터가 있으면 덮어쓰기 확인

### 4.2 서버에서 직접 업로드

CloudType에서:
1. Flask 앱 서비스 클릭
2. **"터미널"** 또는 **"콘솔"** 메뉴 선택
3. 다음 명령어 실행:
   ```bash
   cd 1_giup
   python load_select.py
   ```

---

## 5. 확인 및 테스트

### 5.1 애플리케이션 접속
1. CloudType 대시보드에서 Flask 앱 URL 확인
2. 브라우저에서 접속
3. 메인 페이지 확인

### 5.2 데이터베이스 연결 확인
```bash
# 로컬에서 테스트
cd 1_giup
python -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path.cwd().parent)); from module.db_config import get_postgres_connection; conn = get_postgres_connection(); print('연결 성공!'); conn.close()"
```

### 5.3 데이터 확인
PostgreSQL 서비스의 터미널에서:
```sql
\c postgres
SELECT COUNT(*) FROM giup_statistics;
SELECT 기준년월, COUNT(*) FROM giup_statistics GROUP BY 기준년월;
```

---

## 6. 업데이트 및 재배포

코드를 수정한 후:

```bash
# 1. 변경사항 커밋
git add .
git commit -m "변경 내용 설명"
git push origin main

# 2. CloudType에서 자동으로 재배포됨
```

또는 `git_deploy.bat` 실행

---

## 7. 문제 해결

### 7.1 연결 실패
**증상**: `could not translate host name "postgresql"`

**해결**:
1. Flask 앱과 PostgreSQL이 같은 프로젝트에 있는지 확인
2. 환경변수에서 `POSTGRES_HOST=postgresql` 확인
3. PostgreSQL 서비스가 실행 중인지 확인

### 7.2 데이터 업로드 실패
**증상**: 권한 오류 또는 테이블 없음

**해결**:
1. 테이블이 자동 생성되는지 확인 (load.py가 CREATE TABLE 실행)
2. PostgreSQL 사용자 권한 확인
3. 데이터베이스 이름 확인

### 7.3 로그 확인
CloudType에서:
1. 서비스 클릭
2. **"로그"** 탭 확인
3. 오류 메시지 확인

---

## 8. 보안 주의사항

### 8.1 .env 파일
- ❌ **절대** GitHub에 업로드하지 않기
- ✅ `.gitignore`에 `.env` 추가됨
- ✅ `.env.example`만 GitHub에 업로드

### 8.2 비밀번호 관리
- CloudType 환경변수에만 실제 비밀번호 입력
- 코드에 하드코딩하지 않기

---

## 9. 추가 기능

### 9.1 다른 Excel 파일 추가
1. `1_giup/data/` 폴더에 `집계표_YYYYMM.xlsx` 형식으로 파일 추가
2. `python load_select.py` 실행
3. 파일 목록에서 선택

### 9.2 자동화
Cron job이나 스케줄러로 정기적 업로드 가능:
```python
# 매월 1일 자동 업로드 예시
import schedule
import time

def upload_data():
    # load.py 로직 실행
    pass

schedule.every().month.at("00:00").do(upload_data)
```

---

## 10. 참고 자료

- CloudType 공식 문서: https://docs.cloudtype.io
- PostgreSQL 문서: https://www.postgresql.org/docs/
- Flask 문서: https://flask.palletsprojects.com/

---

## 문의 및 지원

문제가 발생하면:
1. CloudType 로그 확인
2. GitHub Issues에 문의
3. 이 가이드 재확인
