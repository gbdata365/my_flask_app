@echo off
chcp 65001 > nul
echo ==========================================
echo   GitHub 업로드 및 CloudType 배포 스크립트
echo ==========================================
echo.

REM 현재 디렉토리 확인
echo 현재 작업 디렉토리: %CD%
echo.

REM Git 사용자 정보 설정 확인
git config user.name > nul 2>&1
if errorlevel 1 (
    echo [0단계] Git 사용자 정보 설정...
    git config --global user.name "gbdata365"
    git config --global user.email "gbdata365@gmail.com"
    echo Git 사용자 정보가 설정되었습니다.
    echo.
)

REM Git 저장소 초기화 (처음 실행시에만)
if not exist ".git" (
    echo [1단계] Git 저장소 초기화...
    git init
    echo Git 저장소가 초기화되었습니다.
    echo.
) else (
    echo [1단계] 기존 Git 저장소를 사용합니다.
    echo.
)

REM 원격 저장소 설정 (사용자가 입력하지 않은 경우에만)
git remote -v | findstr origin > nul
if errorlevel 1 (
    echo [2단계] GitHub 원격 저장소 설정
    echo 기본 저장소: https://github.com/gbdata365/my_flask_app.git
    set /p REPO_URL="GitHub 저장소 URL (기본값 사용하려면 Enter, 다른 URL 사용시 입력): "
    if "%REPO_URL%"=="" set REPO_URL=https://github.com/gbdata365/my_flask_app.git
    git remote add origin %REPO_URL%
    echo 원격 저장소가 설정되었습니다: %REPO_URL%
    echo.
) else (
    echo [2단계] 기존 원격 저장소를 사용합니다.
    git remote -v
    echo.
)

REM 브랜치 확인 및 설정
echo [3단계] 메인 브랜치 설정...
git branch -M main
echo.

REM 모든 파일 스테이징
echo [4단계] 파일 스테이징...
git add -A
git status
echo.

REM 커밋 메시지 입력
echo [5단계] 변경사항 커밋
set /p COMMIT_MSG="커밋 메시지를 입력하세요 (기본값: Update application): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update application

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo 커밋할 변경사항이 없습니다.
) else (
    echo 커밋이 완료되었습니다.
)
echo.

REM GitHub에 푸시 (force)
echo [6단계] GitHub에 강제 업로드...
echo 경고: 원격 저장소를 로컬 상태로 덮어씁니다.
git push -f origin main
if errorlevel 1 (
    echo.
    echo ⚠️  푸시 실패! 다음을 확인하세요:
    echo    - GitHub 저장소가 존재하는지 확인
    echo    - 인증 정보가 올바른지 확인
    echo    - 네트워크 연결 상태 확인
    echo.
    pause
    exit /b 1
)
echo.
echo ✅ GitHub 업로드 완료!
echo.

REM CloudType 배포 안내
echo ==========================================
echo   CloudType 배포 안내
echo ==========================================
echo.
echo 1. CloudType (https://cloudtype.io)에 로그인
echo 2. "새 프로젝트" 생성
echo 3. GitHub 연동 선택
echo 4. 방금 업로드한 저장소 선택
echo 5. 브랜치: main 선택
echo 6. 빌드 설정:
echo    - Build Command: 없음 (빈칸으로 둠)
echo    - Start Command: python main_app.py
echo    - Port: 5000
echo 7. 환경변수 설정 (필요시):
echo    PostgreSQL (필수):
echo    - DATABASE_URL: PostgreSQL 연결 문자열
echo      또는
echo    - POSTGRES_HOST: PostgreSQL 호스트 (예: postgresql)
echo    - POSTGRES_PORT: PostgreSQL 포트 (예: 5432)
echo    - POSTGRES_DB: 데이터베이스 이름 (예: postgres)
echo    - POSTGRES_USER: 사용자명
echo    - POSTGRES_PASSWORD: 비밀번호
echo.
echo    MySQL (선택):
echo    - DB_HOST: MySQL 호스트
echo    - DB_USER: MySQL 사용자명
echo    - DB_PASS: MySQL 비밀번호
echo    - DB_NAME: MySQL 데이터베이스 이름
echo 8. "배포" 버튼 클릭
echo.
echo 배포가 완료되면 CloudType에서 제공하는 URL로 접속 가능합니다.
echo.
pause