# CloudType 배포 가이드

## 개요
Flask 기반 데이터 분석 대시보드 시스템을 CloudType 클라우드 플랫폼에 배포하는 가이드입니다.

## 준비된 파일들

### 1. 배포 설정 파일
- **`Procfile`**: CloudType에서 애플리케이션을 실행하는 명령어 정의
- **`runtime.txt`**: Python 3.12 버전 지정 (pandas 호환성)
- **`requirements.txt`**: 필요한 Python 패키지 목록
- **`.gitignore`**: Git에서 제외할 파일/폴더 설정

### 2. 배치 파일
- **`git_deploy.bat`**: 최초 GitHub 업로드 및 CloudType 연동용
- **`git_update.bat`**: 기존 프로젝트 업데이트용

## 배포 단계별 가이드

### 1단계: GitHub 저장소 준비

#### 1-1. GitHub에서 새 저장소 생성
1. [GitHub](https://github.com)에 로그인
2. "New repository" 클릭
3. 저장소 이름 입력 (예: `flask-dashboard`)
4. Public 또는 Private 선택
5. "Create repository" 클릭

#### 1-2. 로컬에서 GitHub에 업로드
```batch
# 최초 업로드시
git_deploy.bat

# 이후 업데이트시
git_update.bat
```

### 2단계: CloudType 배포

#### 2-1. CloudType 계정 생성 및 로그인
1. [CloudType](https://cloudtype.io) 접속
2. GitHub 계정으로 로그인

#### 2-2. 새 프로젝트 생성
1. **"새 프로젝트"** 클릭
2. **"GitHub"** 선택
3. **저장소 연동**: 방금 생성한 저장소 선택
4. **브랜치**: `main` 선택

#### 2-3. 빌드 설정
```
Build Command: (비워둠)
Start Command: python main_app.py
Port: 5000
Python Version: 3.12
```

#### 2-4. 환경변수 설정 (선택사항)
데이터베이스를 사용하는 경우:
```
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASS=your_database_password
DB_NAME=your_database_name
```

#### 2-5. 배포 실행
1. **"배포"** 버튼 클릭
2. 빌드 로그 확인
3. 배포 완료 후 제공되는 URL로 접속

## 자동 재배포 설정

### GitHub Actions를 통한 자동 배포 (옵션)
CloudType은 GitHub와 연동되어 있어 `main` 브랜치에 푸시할 때마다 자동으로 재배포됩니다.

```batch
# 코드 수정 후 자동 재배포하려면
git_update.bat
```

## 트러블슈팅

### 1. 빌드 실패시
- **Python 버전 확인**: `runtime.txt`에 `python-3.12` 확인
- **의존성 문제**: `requirements.txt` 패키지 버전 확인
- **포트 설정**: `main_app.py`에서 `PORT` 환경변수 사용 확인

### 2. 데이터베이스 연결 실패시
- CloudType 환경변수에 DB 정보 올바르게 입력했는지 확인
- 데이터베이스 서버가 외부 접속을 허용하는지 확인

### 3. 파일 경로 오류시
- 상대경로 사용 확인 (절대경로 대신)
- 대소문자 구분 확인

### 4. 메모리 부족 오류시
- CloudType에서 더 큰 인스턴스 선택
- 불필요한 데이터 파일 제거

## 주요 기능 확인사항

### 배포 후 확인할 기능들
1. **메인 페이지** (`/`) 로딩 확인
2. **카테고리 페이지** (`/1_giup`, `/2_의료통계` 등) 접근 확인
3. **대시보드** 차트 및 데이터 표시 확인
4. **파일 업로드/다운로드** 기능 확인

### 성능 최적화 팁
1. **정적 파일 캐싱** 설정
2. **데이터베이스 연결 풀** 사용
3. **로그 레벨** 조정 (`debug=False` 확인)

## 비용 관리

### CloudType 요금제
- **Free Tier**: 제한적 리소스, 개발/테스트용
- **Paid Plan**: 운영 환경용, 더 많은 리소스

### 최적화 방안
- 사용하지 않는 기능 비활성화
- 정적 파일은 CDN 사용 고려
- 데이터베이스 쿼리 최적화

## 백업 및 복구

### 데이터 백업
```python
# 정기적으로 데이터베이스 백업
# cron job 또는 스케줄링 작업 설정
```

### 코드 백업
- GitHub 저장소가 자동 백업 역할
- 중요한 설정은 별도 백업 권장

## 지원 및 문의

### CloudType 고객지원
- [CloudType 문서](https://docs.cloudtype.io/)
- [CloudType 고객지원](https://cloudtype.io/support)

### GitHub 이슈
- 코드 관련 문제는 GitHub Issues 활용
- 버전 관리 및 협업 도구로 활용