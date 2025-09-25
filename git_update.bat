@echo off
chcp 65001 > nul
echo ==========================================
echo   GitHub 업데이트 스크립트
echo ==========================================
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

REM 현재 상태 확인
echo [1단계] Git 상태 확인...
git status
echo.

REM 변경사항 확인
echo [2단계] 변경된 파일 목록:
git diff --name-only HEAD
echo.

REM 사용자에게 계속 진행할지 확인
set /p CONTINUE="업데이트를 계속하시겠습니까? (y/N): "
if /i not "%CONTINUE%"=="y" (
    echo 업데이트를 취소했습니다.
    pause
    exit /b 0
)

REM 모든 파일 스테이징
echo [3단계] 파일 스테이징...
git add .
echo.

REM 커밋 메시지 입력
echo [4단계] 변경사항 커밋
set /p COMMIT_MSG="커밋 메시지를 입력하세요 (기본값: Update application): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update application

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo 변경사항이 없어서 커밋하지 않았습니다.
    echo.
) else (
    echo 커밋이 완료되었습니다.
    echo.
)

REM GitHub에 푸시
echo [5단계] GitHub에 업로드...
git push origin main
if errorlevel 1 (
    echo.
    echo ⚠️  푸시 실패! 네트워크 또는 인증을 확인하세요.
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ GitHub 업데이트 완료!
echo CloudType에서 자동으로 재배포됩니다.
echo.
pause