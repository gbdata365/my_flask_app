@echo off
chcp 65001 > nul
echo ==========================================
echo   GitHub 업로드 및 CloudType 배포 스크립트
echo ==========================================
echo.

REM 현재 디렉토리 확인
echo 현재 작업 디렉토리: %CD%
echo.

REM Git 사용자 정보 설정
echo [0단계] Git 사용자 정보 설정...
git config --global user.name "gbdata365"
git config --global user.email "gbdata365@gmail.com"
echo Git 사용자 정보가 설정되었습니다.
echo.

REM 기존 .git 폴더가 있으면 삭제 (깨끗하게 시작)
if exist ".git" (
    echo 기존 Git 설정을 삭제하고 새로 시작합니다...
    rmdir /s /q .git
    echo.
)

REM Git 저장소 초기화
echo [1단계] Git 저장소 초기화...
git init
git branch -M main
echo Git 저장소가 초기화되었습니다.
echo.

REM 원격 저장소 설정
echo [2단계] GitHub 원격 저장소 설정
echo 기본 저장소: https://github.com/gbdata365/my_flask_app.git
set REPO_URL=https://github.com/gbdata365/my_flask_app.git
set /p USER_INPUT="기본값을 사용하려면 Enter, 다른 URL 사용시 입력하세요: "
if not "%USER_INPUT%"=="" set REPO_URL=%USER_INPUT%

git remote add origin %REPO_URL%
echo 원격 저장소가 설정되었습니다: %REPO_URL%
echo.

REM 모든 파일 스테이징
echo [3단계] 파일 스테이징...
git add .
echo 모든 파일이 스테이징되었습니다.
echo.

REM 커밋 메시지 입력
echo [4단계] 변경사항 커밋
set /p COMMIT_MSG="커밋 메시지를 입력하세요 (기본값: Initial commit): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Initial commit

git commit -m "%COMMIT_MSG%"
echo 커밋이 완료되었습니다.
echo.

REM GitHub에 푸시
echo [5단계] GitHub에 업로드...
git push --force -u origin main
if errorlevel 1 (
    echo.
    echo ⚠️  푸시 실패! 다음을 확인하세요:
    echo    - GitHub 저장소가 존재하는지 확인: %REPO_URL%
    echo    - 인증 정보가 올바른지 확인
    echo    - 네트워크 연결 상태 확인
    echo.
    echo 수동으로 GitHub 인증이 필요할 수 있습니다.
    echo GitHub Desktop 또는 웹에서 로그인을 확인해주세요.
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
echo 4. 저장소 선택: %REPO_URL%
echo 5. 브랜치: main 선택
echo 6. 빌드 설정:
echo    - Build Command: 없음 (빈칸으로 둠)
echo    - Start Command: python main_app.py
echo    - Port: 5000
echo 7. 환경변수 설정 (필요시):
echo    - DB_HOST: 데이터베이스 호스트
echo    - DB_USER: 데이터베이스 사용자명
echo    - DB_PASS: 데이터베이스 비밀번호
echo    - DB_NAME: 데이터베이스 이름
echo 8. "배포" 버튼 클릭
echo.
echo 배포가 완료되면 CloudType에서 제공하는 URL로 접속 가능합니다.
echo.
pause