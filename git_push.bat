@echo off
chcp 65001 > nul
echo ==========================================
echo   GitHub 업데이트 및 CloudType 자동 배포
echo ==========================================
echo.

REM 현재 디렉토리 확인
echo 현재 작업 디렉토리: %CD%
echo.

REM Git 상태 확인
echo [1단계] 변경된 파일 확인...
git status
echo.

REM 사용자에게 확인
set /p CONFIRM="계속 진행하시겠습니까? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo 취소되었습니다.
    pause
    exit /b 0
)
echo.

REM .env 파일 업로드 여부 확인
echo.
echo [!] .env 파일 업로드 선택
echo ==========================================
echo .env 파일에는 데이터베이스 비밀번호, API 키 등 민감한 정보가 포함되어 있습니다.
echo.
echo GitHub Private 저장소에도 업로드하지 않는 것을 권장합니다!
echo GitHub Push Protection이 API 키를 감지하면 push가 차단됩니다.
echo ==========================================
echo.
set /p UPLOAD_ENV=".env 파일을 GitHub에 업로드하시겠습니까? (Y/N, 기본값: N): "
if /i "%UPLOAD_ENV%"=="" set UPLOAD_ENV=N

REM 모든 파일 스테이징
echo.
echo [2단계] 파일 스테이징...

REM 먼저 모든 파일 추가
git add .

if /i "%UPLOAD_ENV%"=="Y" (
    echo [O] .env 파일 포함하여 업로드합니다.
    echo [!] 경고: GitHub Push Protection에 의해 차단될 수 있습니다.
    git add -f .env
    git add -f module/.env 2>nul
) else (
    echo [i] .env 파일 제외하고 업로드합니다.
    REM .env 파일들을 스테이징에서 명시적으로 제외
    git reset HEAD .env 2>nul
    git reset HEAD module/.env 2>nul
    REM .gitignore에 .env가 없으면 추가
    findstr /x /c:".env" .gitignore >nul 2>&1
    if errorlevel 1 (
        echo .env>> .gitignore
        echo [i] .gitignore에 .env 추가됨
        git add .gitignore
    )
    findstr /x /c:"module/.env" .gitignore >nul 2>&1
    if errorlevel 1 (
        echo module/.env>> .gitignore
        echo [i] .gitignore에 module/.env 추가됨
        git add .gitignore
    )
)

echo 파일 스테이징 완료
echo.

REM 스테이징된 파일 확인
echo [2-1단계] 스테이징된 파일 확인...
git diff --cached --name-only
echo.

REM 커밋 메시지 입력
echo [3단계] 커밋 메시지 입력
set /p COMMIT_MSG="커밋 메시지를 입력하세요 (기본값: Update application): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update application

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo.
    echo [i] 커밋할 변경사항이 없습니다.
    echo.
    pause
    exit /b 0
)
echo 커밋 완료
echo.

REM GitHub에 푸시
echo [4단계] GitHub에 업로드...
git push origin main
if errorlevel 1 (
    echo.
    echo [!] 푸시 실패!
    echo.
    echo 가능한 원인:
    echo - GitHub Push Protection: .env 또는 API 키가 포함된 경우
    echo - 네트워크 연결 상태
    echo - GitHub 인증 정보
    echo - git pull 필요 여부 (충돌 가능성)
    echo.
    echo Push Protection 오류인 경우:
    echo   git reset --soft HEAD~1
    echo   그 후 이 스크립트를 다시 실행하고 .env 제외 선택
    echo.
    echo 충돌 오류인 경우:
    echo   git pull origin main --rebase
    echo   git push origin main
    echo.
    pause
    exit /b 1
)
echo.

echo ==========================================
echo   [OK] 업로드 완료!
echo ==========================================
echo.
echo GitHub 저장소: https://github.com/gbdata365/my_flask_app.git
echo.
echo CloudType가 변경사항을 감지하고 자동으로 배포를 시작합니다.
echo.
echo 배포 상태 확인:
echo 1. https://cloudtype.io 접속
echo 2. 프로젝트 선택
echo 3. "Deployments" 또는 "배포" 탭에서 진행 상황 확인
echo.
pause
