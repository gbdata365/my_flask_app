@echo off
chcp 65001 >nul
echo ========================================
echo Flask Dashboard 배포 패키지 생성
echo ========================================
echo.

REM 현재 날짜와 시간으로 폴더명 생성
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "datestamp=%YYYY%%MM%%DD%_%HH%%Min%%Sec%"

set "DEPLOY_FOLDER=flask_dashboard_deployment_%datestamp%"
set "ZIP_FILE=%DEPLOY_FOLDER%.zip"

echo 📦 배포 패키지명: %DEPLOY_FOLDER%
echo 📁 압축 파일명: %ZIP_FILE%
echo.

REM main_app.py 확인
if not exist "main_app.py" (
    echo ❌ 오류: main_app.py 파일이 없습니다.
    echo    프로젝트 루트 디렉토리에서 실행하세요.
    pause
    exit /b 1
)

echo ✅ 프로젝트 디렉토리 확인 완료
echo.

REM 기존 폴더가 있으면 삭제
if exist "%DEPLOY_FOLDER%" (
    echo 🗑️  기존 배포 폴더 삭제 중...
    rmdir /s /q "%DEPLOY_FOLDER%"
)

REM 배포 폴더 생성
mkdir "%DEPLOY_FOLDER%"
echo ✅ 배포 폴더 생성: %DEPLOY_FOLDER%

echo.
echo 📋 필수 파일 복사 중...

REM Docker 설정 파일 복사
if exist "docker-compose.yml" copy "docker-compose.yml" "%DEPLOY_FOLDER%\" >nul && echo ✅ docker-compose.yml
if exist "Dockerfile" copy "Dockerfile" "%DEPLOY_FOLDER%\" >nul && echo ✅ Dockerfile
if exist ".dockerignore" copy ".dockerignore" "%DEPLOY_FOLDER%\" >nul && echo ✅ .dockerignore

REM 환경 설정 파일
if exist ".env.example" copy ".env.example" "%DEPLOY_FOLDER%\" >nul && echo ✅ .env.example
if exist "requirements.txt" copy "requirements.txt" "%DEPLOY_FOLDER%\" >nul && echo ✅ requirements.txt

REM 메인 애플리케이션 파일
if exist "main_app.py" copy "main_app.py" "%DEPLOY_FOLDER%\" >nul && echo ✅ main_app.py
if exist "CLAUDE.md" copy "CLAUDE.md" "%DEPLOY_FOLDER%\" >nul && echo ✅ CLAUDE.md

REM 배포 스크립트 및 가이드
if exist "deploy.sh" copy "deploy.sh" "%DEPLOY_FOLDER%\" >nul && echo ✅ deploy.sh
if exist "deploy.bat" copy "deploy.bat" "%DEPLOY_FOLDER%\" >nul && echo ✅ deploy.bat
if exist "Docker_배포_가이드.md" copy "Docker_배포_가이드.md" "%DEPLOY_FOLDER%\" >nul && echo ✅ Docker_배포_가이드.md

echo.
echo 📁 디렉토리 복사 중...

REM 디렉토리 복사 (xcopy 사용)
if exist "module" (
    xcopy "module" "%DEPLOY_FOLDER%\module\" /E /I /Q /H >nul 2>&1
    echo ✅ module/
)

if exist "templates" (
    xcopy "templates" "%DEPLOY_FOLDER%\templates\" /E /I /Q /H >nul 2>&1
    echo ✅ templates/
)

if exist "static" (
    xcopy "static" "%DEPLOY_FOLDER%\static\" /E /I /Q /H >nul 2>&1
    echo ✅ static/
)

if exist "nginx" (
    xcopy "nginx" "%DEPLOY_FOLDER%\nginx\" /E /I /Q /H >nul 2>&1
    echo ✅ nginx/
)

if exist "database" (
    xcopy "database" "%DEPLOY_FOLDER%\database\" /E /I /Q /H >nul 2>&1
    echo ✅ database/
)

if exist "1_giup" (
    xcopy "1_giup" "%DEPLOY_FOLDER%\1_giup\" /E /I /Q /H >nul 2>&1
    echo ✅ 1_giup/
)

if exist "2_의료통계" (
    xcopy "2_의료통계" "%DEPLOY_FOLDER%\2_의료통계\" /E /I /Q /H >nul 2>&1
    echo ✅ 2_의료통계/
)

if exist "3_csv_dashboard" (
    xcopy "3_csv_dashboard" "%DEPLOY_FOLDER%\3_csv_dashboard\" /E /I /Q /H >nul 2>&1
    echo ✅ 3_csv_dashboard/
)

REM uploads 폴더 (선택사항)
set /p include_uploads="📤 uploads 폴더를 포함하시겠습니까? (y/N): "
if /i "%include_uploads%"=="y" (
    if exist "uploads" (
        xcopy "uploads" "%DEPLOY_FOLDER%\uploads\" /E /I /Q /H >nul 2>&1
        echo ✅ uploads/
    )
)

echo.
echo 📄 설치 가이드 및 스크립트 생성 중...

REM README 파일 생성
(
echo # Flask Dashboard 배포 패키지
echo.
echo 생성일: %date% %time%
echo 생성자: %username%
echo.
echo ## 📦 패키지 내용
echo.
echo 이 패키지에는 Flask Dashboard를 Docker로 배포하는데 필요한 모든 파일이 포함되어 있습니다.
echo.
echo ### 핵심 구성요소
echo - Docker 설정: docker-compose.yml, Dockerfile
echo - Flask 애플리케이션: main_app.py, module/, templates/
echo - 웹 서버 설정: nginx/ 디렉토리
echo - 데이터베이스 설정: database/ 디렉토리
echo - 배포 스크립트: deploy.bat
echo.
echo ## 🚀 빠른 설치 가이드
echo.
echo ### 1. 요구사항
echo - Docker Desktop for Windows
echo - Windows 10/11
echo.
echo ### 2. 설치 과정
echo 1. install.bat 더블클릭 또는
echo 2. PowerShell에서 .\install.bat 실행
echo 3. 웹 브라우저에서 http://localhost 접속
echo.
echo ## ⚠️ 보안 주의사항
echo 1. .env 파일의 기본 비밀번호를 반드시 변경하세요
echo 2. 방화벽에서 필요한 포트만 개방하세요
echo.
echo ## 📖 상세 가이드
echo Docker_배포_가이드.md 파일을 참고하세요.
echo.
echo ---
echo 배포 패키지 버전: %datestamp%
) > "%DEPLOY_FOLDER%\README.md"

REM 자동 설치 스크립트 생성
(
echo @echo off
echo chcp 65001 ^>nul
echo echo ========================================
echo echo Flask Dashboard 자동 설치
echo echo ========================================
echo echo.
echo.
echo REM Docker 설치 확인
echo docker --version ^>nul 2^>^&1
echo if errorlevel 1 ^(
echo     echo ❌ Docker가 설치되어 있지 않습니다.
echo     echo    Docker Desktop을 설치한 후 다시 실행하세요.
echo     echo    다운로드: https://www.docker.com/products/docker-desktop/
echo     echo.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo echo ✅ Docker가 설치되어 있습니다.
echo echo.
echo.
echo REM 환경 설정 파일 생성
echo if not exist ".env" ^(
echo     echo 📝 환경 설정 파일을 생성합니다...
echo     copy ".env.example" ".env" ^>nul
echo     echo.
echo     echo ⚠️  중요: .env 파일의 비밀번호를 변경하세요!
echo     echo    notepad .env 명령으로 편집할 수 있습니다.
echo     echo.
echo     set /p edit_env="지금 .env 파일을 편집하시겠습니까? ^(Y/n^): "
echo     if /i "!edit_env!" neq "n" ^(
echo         notepad .env
echo     ^)
echo     echo.
echo ^)
echo.
echo echo 🚀 Flask Dashboard 서비스를 시작합니다...
echo deploy.bat start
echo.
echo if errorlevel 0 ^(
echo     echo.
echo     echo 🎉 설치가 완료되었습니다!
echo     echo 📱 웹 브라우저에서 다음 주소로 접속하세요:
echo     echo    http://localhost
echo     echo    http://localhost/health ^(헬스체크^)
echo     echo.
echo     echo 💡 관리 명령어:
echo     echo    deploy.bat status  - 상태 확인
echo     echo    deploy.bat logs    - 로그 확인
echo     echo    deploy.bat stop    - 서비스 중지
echo     echo    deploy.bat restart - 서비스 재시작
echo     echo.
echo ^) else ^(
echo     echo ❌ 서비스 시작에 실패했습니다.
echo     echo    deploy.bat logs 명령으로 로그를 확인하세요.
echo ^)
echo.
echo pause
) > "%DEPLOY_FOLDER%\install.bat"

echo ✅ README.md 생성
echo ✅ install.bat 생성

echo.
echo 🗂️  불필요한 파일 정리 중...

REM __pycache__ 폴더 삭제
for /d /r "%DEPLOY_FOLDER%" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" >nul 2>&1

REM .pyc 파일 삭제
del /s /q "%DEPLOY_FOLDER%\*.pyc" >nul 2>&1

REM .log 파일 삭제
del /s /q "%DEPLOY_FOLDER%\*.log" >nul 2>&1

REM .tmp 파일 삭제
del /s /q "%DEPLOY_FOLDER%\*.tmp" >nul 2>&1

echo ✅ 불필요한 파일 정리 완료

echo.
echo 🗜️  ZIP 압축 파일 생성 중...

REM PowerShell을 사용한 ZIP 압축
powershell -Command "Compress-Archive -Path '%DEPLOY_FOLDER%\*' -DestinationPath '%ZIP_FILE%' -CompressionLevel Optimal" >nul 2>&1

if exist "%ZIP_FILE%" (
    echo ✅ ZIP 압축 완료: %ZIP_FILE%
) else (
    echo ❌ ZIP 압축 실패
)

echo.
echo ========================================
echo 🎉 배포 패키지 생성 완료!
echo ========================================
echo.
echo 📁 배포 폴더: %DEPLOY_FOLDER%
echo 📦 압축 파일: %ZIP_FILE%
echo 📄 설치 가이드: %DEPLOY_FOLDER%\README.md
echo 🚀 자동 설치: %DEPLOY_FOLDER%\install.bat
echo.
echo 📍 파일 위치: %cd%
echo.
echo =======================================
echo 다음 단계:
echo =======================================
echo 1️⃣  %ZIP_FILE% 파일을 대상 PC로 복사
echo 2️⃣  대상 PC에서 압축 해제
echo 3️⃣  install.bat 더블클릭 또는 실행
echo 4️⃣  웹 브라우저에서 http://localhost 접속
echo.
echo ⚠️  중요: .env 파일의 기본 비밀번호를 반드시 변경하세요!
echo.
pause