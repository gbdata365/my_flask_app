@echo off
REM Flask Dashboard Docker 배포 스크립트 (Windows용)
REM 사용법: deploy.bat [start|stop|restart|logs|status]

setlocal EnableDelayedExpansion

REM 색상 설정 (Windows 10 이상)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM 로그 함수들
:log_info
echo %BLUE%[INFO]%NC% %~1
goto :eof

:log_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:log_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:log_error
echo %RED%[ERROR]%NC% %~1
goto :eof

REM 환경 확인
:check_requirements
call :log_info "시스템 요구사항 확인 중..."

REM Docker 설치 확인
docker --version >nul 2>&1
if errorlevel 1 (
    call :log_error "Docker가 설치되어 있지 않습니다."
    call :log_info "Docker 설치: https://docs.docker.com/get-docker/"
    pause
    exit /b 1
)

REM Docker Compose 설치 확인
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        call :log_error "Docker Compose가 설치되어 있지 않습니다."
        call :log_info "Docker Compose 설치: https://docs.docker.com/compose/install/"
        pause
        exit /b 1
    )
)

REM .env 파일 확인
if not exist ".env" (
    call :log_warning ".env 파일이 없습니다. .env.example을 복사하여 설정을 완료하세요."
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        call :log_info ".env 파일이 생성되었습니다. 설정을 확인하고 수정하세요."
    ) else (
        call :log_error ".env.example 파일도 없습니다."
        pause
        exit /b 1
    )
)

call :log_success "요구사항 확인 완료"
goto :eof

REM 서비스 시작
:start_services
call :log_info "Flask Dashboard 서비스 시작 중..."

REM 기존 컨테이너 정리
docker-compose down --remove-orphans >nul 2>&1

REM 이미지 빌드 및 서비스 시작
docker-compose up -d --build

call :log_info "서비스 시작 대기 중..."
timeout /t 10 /nobreak >nul

REM 헬스체크
call :check_health
goto :eof

REM 서비스 중지
:stop_services
call :log_info "Flask Dashboard 서비스 중지 중..."
docker-compose down
call :log_success "서비스가 중지되었습니다."
goto :eof

REM 서비스 재시작
:restart_services
call :log_info "Flask Dashboard 서비스 재시작 중..."
call :stop_services
timeout /t 2 /nobreak >nul
call :start_services
goto :eof

REM 로그 보기
:show_logs
call :log_info "서비스 로그를 표시합니다. (Ctrl+C로 종료)"
docker-compose logs -f
goto :eof

REM 서비스 상태 확인
:check_status
call :log_info "서비스 상태 확인 중..."
echo.
docker-compose ps
echo.

REM 각 서비스별 상태 확인
docker-compose ps | findstr "flask_mariadb.*Up" >nul 2>&1
if errorlevel 1 (
    call :log_error "MariaDB: 정지됨"
) else (
    call :log_success "MariaDB: 실행 중"
)

docker-compose ps | findstr "flask_dashboard.*Up" >nul 2>&1
if errorlevel 1 (
    call :log_error "Flask App: 정지됨"
) else (
    call :log_success "Flask App: 실행 중"
)

docker-compose ps | findstr "flask_nginx.*Up" >nul 2>&1
if errorlevel 1 (
    call :log_error "Nginx: 정지됨"
) else (
    call :log_success "Nginx: 실행 중"
)

REM 웹사이트 접속 테스트
curl -s http://localhost/health >nul 2>&1
if errorlevel 1 (
    call :log_warning "웹사이트: 접속 불가"
) else (
    call :log_success "웹사이트: 접속 가능 (http://localhost)"
)
goto :eof

REM 헬스체크
:check_health
call :log_info "서비스 헬스체크 실행 중..."

set "max_attempts=30"
set "attempt=1"

:health_loop
if !attempt! gtr !max_attempts! goto :health_failed

curl -s http://localhost/health >nul 2>&1
if not errorlevel 1 (
    call :log_success "모든 서비스가 정상적으로 실행되고 있습니다!"
    call :log_info "웹사이트 주소: http://localhost"
    goto :eof
)

call :log_info "헬스체크 시도 !attempt!/!max_attempts!..."
timeout /t 5 /nobreak >nul
set /a attempt+=1
goto :health_loop

:health_failed
call :log_error "서비스 시작에 실패했습니다. 로그를 확인하세요:"
call :log_info "로그 확인: deploy.bat logs"
goto :eof

REM 데이터베이스 백업
:backup_database
call :log_info "데이터베이스 백업 중..."

if not exist "backups" mkdir backups

for /f "tokens=2 delims==" %%a in ('findstr "DB_ROOT_PASSWORD" .env') do set "DB_PASS=%%a"

set "backup_file=backups\db_backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%.sql"
set "backup_file=%backup_file: =0%"

docker-compose exec mariadb mysqldump -u root -p%DB_PASS% dashboard_db > "%backup_file%"

if errorlevel 1 (
    call :log_error "데이터베이스 백업 실패"
) else (
    call :log_success "데이터베이스 백업 완료: %backup_file%"
)
goto :eof

REM 도움말
:show_help
echo Flask Dashboard Docker 배포 스크립트 (Windows)
echo.
echo 사용법: %~nx0 [명령어]
echo.
echo 명령어:
echo   start     - 서비스 시작
echo   stop      - 서비스 중지
echo   restart   - 서비스 재시작
echo   status    - 서비스 상태 확인
echo   logs      - 서비스 로그 보기
echo   backup    - 데이터베이스 백업
echo   help      - 이 도움말 표시
echo.
echo 예시:
echo   %~nx0 start     # 서비스 시작
echo   %~nx0 logs      # 로그 보기
echo   %~nx0 backup    # DB 백업
goto :eof

REM 메인 실행부
set "command=%~1"
if "%command%"=="" set "command=help"

if "%command%"=="start" (
    call :check_requirements
    if not errorlevel 1 call :start_services
) else if "%command%"=="stop" (
    call :stop_services
) else if "%command%"=="restart" (
    call :check_requirements
    if not errorlevel 1 call :restart_services
) else if "%command%"=="status" (
    call :check_status
) else if "%command%"=="logs" (
    call :show_logs
) else if "%command%"=="backup" (
    call :backup_database
) else if "%command%"=="help" (
    call :show_help
) else (
    call :log_error "알 수 없는 명령어: %command%"
    call :show_help
)

pause