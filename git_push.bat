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
echo ⚠️  .env 파일 업로드 선택
echo ==========================================
echo .env 파일에는 데이터베이스 비밀번호, API 키 등
echo 민감한 정보가 포함되어 있습니다.
echo.
echo GitHub Private 저장소에만 업로드하세요!
echo Public 저장소에 올리면 보안 위험이 있습니다.
echo ==========================================
echo.
set /p UPLOAD_ENV=".env 파일을 GitHub에 업로드하시겠습니까? (Y/N, 기본값: N): "
if /i "%UPLOAD_ENV%"=="" set UPLOAD_ENV=N

REM 모든 파일 스테이징
echo.
echo [2단계] 파일 스테이징...

if /i "%UPLOAD_ENV%"=="Y" (
    echo ✅ .env 파일 포함하여 업로드합니다.
    git add -f .env
    git add .
) else (
    echo ℹ️  .env 파일 제외하고 업로드합니다.
    git add .
)

echo 파일 스테이징 완료
echo.

REM 커밋 메시지 입력
echo [3단계] 커밋 메시지 입력
set /p COMMIT_MSG="커밋 메시지를 입력하세요 (기본값: Update application): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update application

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo.
    echo ℹ️  커밋할 변경사항이 없습니다.
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
    echo ⚠️  푸시 실패!
    echo.
    echo 다음을 확인하세요:
    echo - 네트워크 연결 상태
    echo - GitHub 인증 정보
    echo - git pull 필요 여부 (충돌 가능성)
    echo.
    echo 필요시 다음 명령어를 실행하세요:
    echo   git pull origin main --rebase
    echo   git push origin main
    echo.
    pause
    exit /b 1
)
echo.

echo ==========================================
echo   ✅ 업로드 완료!
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
echo YAML 파일 변경으로 인한 배포 내용:
echo - DATABASE_URL 설정 적용
echo - PostgreSQL 연결 환경변수 업데이트
echo - 컨테이너 재시작 및 환경변수 주입
echo.
pause
