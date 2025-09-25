# Flask 대시보드 Docker 배포 가이드 (PowerShell)

## 📋 개요

이 가이드는 Flask 기반 데이터 분석 대시보드를 Docker를 사용하여 Windows PowerShell 환경에서 배포하는 방법을 설명합니다.

### 🏗️ 아키텍처

- **Flask App**: Python 3.13 + Gunicorn (포트 8000)
- **MariaDB**: 데이터베이스 서버 (포트 3306)
- **Nginx**: 리버스 프록시 웹 서버 (포트 80, 443)

## 🔧 시스템 요구사항

### 필수 소프트웨어

- **Docker Desktop for Windows**: 20.10.0 이상
- **PowerShell**: 5.1 이상 (PowerShell 7+ 권장)
- **Windows**: Windows 10/11 (WSL2 활성화 권장)
- **Docker Compose**: Docker Desktop에 포함됨

### 하드웨어 권장사양

- **CPU**: 2코어 이상
- **메모리**: 4GB 이상
- **디스크**: 10GB 이상의 여유 공간

## 🚀 빠른 시작

### 1. PowerShell 설정 확인

```powershell
# PowerShell 버전 확인
$PSVersionTable.PSVersion

# Docker Desktop 실행 상태 확인
docker --version
docker compose version

# WSL2 활성화 확인 (권장)
wsl --status
```

### 2. 프로젝트 준비

```powershell
# 프로젝트 디렉토리로 이동
Set-Location "C:\path\to\your-project-directory"

# 환경 설정 파일 복사 및 수정
Copy-Item ".env.example" ".env"

# .env 파일을 편집기로 열기
notepad .env
# 또는 VS Code 사용 시
code .env
```

### 3. 환경 설정 (.env 파일)

`.env` 파일에서 다음 설정들을 확인하고 수정하세요:

```env
# 데이터베이스 설정 (⚠️ 운영 환경에서는 반드시 변경!)
DB_ROOT_PASSWORD=your_secure_password_here
DB_NAME=dashboard_db
DB_USER=dashuser
DB_PASSWORD=your_db_password_here

# Flask 애플리케이션 설정
FLASK_ENV=production
SECRET_KEY=your_secret_key_here_change_this
```

### 4. 서비스 시작

#### PowerShell에서 배치 파일 실행

```powershell
# 서비스 시작
.\deploy.bat start

# 서비스 상태 확인
.\deploy.bat status

# 로그 확인
.\deploy.bat logs
```

#### PowerShell에서 직접 Docker Compose 실행

```powershell
# 서비스 시작
docker compose up -d --build

# 서비스 상태 확인
docker compose ps

# 로그 실시간 모니터링
docker compose logs -f
```

### 5. 웹사이트 접속

브라우저에서 다음 주소로 접속하세요:
- **메인 사이트**: http://localhost
- **헬스체크**: http://localhost/health

## 📚 상세 배포 가이드

### PowerShell에서 Docker Compose 관리

배포 스크립트를 사용하지 않고 PowerShell에서 직접 Docker Compose를 관리하려면:

```powershell
# 백그라운드에서 서비스 시작
docker compose up -d --build

# 로그 확인 (실시간)
docker compose logs -f

# 특정 서비스 로그만 확인
docker compose logs flask_app
docker compose logs mariadb
docker compose logs nginx

# 서비스 중지
docker compose down

# 컨테이너와 볼륨까지 완전 제거
docker compose down -v --remove-orphans
```

### 환경별 설정

#### 개발 환경

```powershell
# 개발 모드로 실행 (실시간 코드 변경 반영)
.\deploy.bat dev

# 또는 직접 실행
docker compose up --build flask_app
```

#### Windows 운영 환경

1. **SSL 인증서 설정** (선택사항)
   ```powershell
   # SSL 디렉토리 생성
   New-Item -ItemType Directory -Path "ssl" -Force

   # 인증서 파일 복사
   Copy-Item "your-cert.pem" "ssl/cert.pem"
   Copy-Item "your-key.pem" "ssl/key.pem"
   ```

2. **Nginx 설정 수정**
   - `nginx/conf.d/default.conf`에서 HTTPS 설정 활성화

3. **Windows 방화벽 설정**
   ```powershell
   # 관리자 권한으로 PowerShell 실행 필요
   # HTTP 포트 80 허용
   New-NetFirewallRule -DisplayName "Docker HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow

   # HTTPS 포트 443 허용
   New-NetFirewallRule -DisplayName "Docker HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow

   # 또는 Windows Defender 방화벽 GUI에서 설정
   Start-Process "wf.msc"
   ```

## 🔍 트러블슈팅

### 일반적인 문제들

#### 1. 포트 충돌

**문제**: "Port already in use" 오류

**해결방법**:
```powershell
# 포트 사용 중인 프로세스 확인
netstat -ano | findstr ":80"
netstat -ano | findstr ":443"

# 특정 포트를 사용하는 프로세스 종료
# PID 확인 후
Stop-Process -Id [PID] -Force

# IIS 서비스 중지 (관리자 권한 필요)
Stop-Service -Name "W3SVC" -Force
Stop-Service -Name "WAS" -Force

# Skype 등 다른 애플리케이션이 포트 80을 사용하는 경우 확인
Get-Process | Where-Object {$_.Name -like "*skype*"}
```

#### 2. 데이터베이스 연결 실패

**문제**: Flask 앱이 데이터베이스에 연결할 수 없음

**해결방법**:
```powershell
# 데이터베이스 컨테이너 로그 확인
docker compose logs mariadb

# 데이터베이스 연결 테스트
docker compose exec mariadb mysql -u root -p

# 환경 변수 확인
docker compose exec flask_app env | Select-String "DB_"

# .env 파일 내용 확인
Get-Content .env | Select-String "DB_"
```

#### 3. 메모리 부족

**문제**: 컨테이너가 OOM (Out of Memory)으로 종료됨

**해결방법**:
```powershell
# 메모리 사용량 확인
docker stats

# Docker Desktop 메모리 설정 확인 (GUI에서)
# Settings > Resources > Memory

# Docker 시스템 정리
docker system prune -a

# WSL2 메모리 사용량 제한 설정
# %UserProfile%\.wslconfig 파일 생성/편집
@"
[wsl2]
memory=4GB
processors=2
"@ | Out-File -FilePath "$env:USERPROFILE\.wslconfig" -Encoding UTF8

# WSL 재시작
wsl --shutdown
```

#### 4. Docker Desktop 관련 문제

**문제**: Docker Desktop이 시작되지 않거나 오류 발생

**해결방법**:
```powershell
# Docker Desktop 서비스 상태 확인
Get-Service "*docker*"

# WSL2 설치 및 활성화 확인
wsl --list --verbose

# Hyper-V 활성화 확인 (관리자 권한 필요)
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All

# Docker Desktop 재시작
Stop-Process -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
Start-Process -FilePath "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
```

#### 5. 파일 권한 문제 (Windows/WSL2)

**문제**: 파일 업로드나 로그 생성 실패

**해결방법**:
```powershell
# uploads 디렉토리 생성 및 권한 설정
New-Item -ItemType Directory -Path "uploads" -Force
icacls "uploads" /grant Everyone:F /T

# logs 디렉토리 생성 및 권한 설정
New-Item -ItemType Directory -Path "logs" -Force
icacls "logs" /grant Everyone:F /T

# WSL2 환경에서 실행 중인 경우
wsl -e bash -c "chmod -R 755 uploads/ logs/"
```

### PowerShell 디버깅 명령어

```powershell
# 컨테이너 내부 접속
docker compose exec flask_app bash
docker compose exec mariadb bash

# Windows 컨테이너의 경우 PowerShell 접속
docker compose exec flask_app powershell

# 특정 컨테이너 로그만 보기
docker compose logs flask_app
docker compose logs mariadb
docker compose logs nginx

# 실시간 로그 모니터링 (최근 100라인)
docker compose logs -f --tail=100

# 특정 서비스만 실시간 로그
docker compose logs -f flask_app

# 컨테이너 상태 확인
docker compose ps
docker stats

# 컨테이너 상세 정보
docker inspect $(docker compose ps -q flask_app)

# 네트워크 정보 확인
docker network ls
docker network inspect project_flask_network

# 볼륨 정보 확인
docker volume ls
docker volume inspect project_mariadb_data
```

## 🔒 보안 설정

### 필수 보안 체크리스트

- [ ] `.env` 파일의 기본 비밀번호 변경
- [ ] 데이터베이스 root 비밀번호 변경
- [ ] Flask SECRET_KEY 변경
- [ ] 불필요한 포트 차단
- [ ] SSL/TLS 인증서 설정 (운영환경)
- [ ] 정기적인 보안 업데이트

### 고급 보안 설정

1. **데이터베이스 보안**
   ```sql
   -- 불필요한 사용자 제거
   DROP USER IF EXISTS ''@'localhost';
   DROP USER IF EXISTS ''@'%';

   -- 테스트 데이터베이스 제거
   DROP DATABASE IF EXISTS test;
   ```

2. **네트워크 보안**
   ```yaml
   # docker-compose.yml에 추가
   networks:
     flask_network:
       driver: bridge
       ipam:
         config:
           - subnet: 172.20.0.0/16
   ```

## 📊 모니터링

### 로그 관리 (Windows)

```powershell
# Docker Desktop의 daemon.json 설정 확인 경로
# %UserProfile%\.docker\daemon.json

# PowerShell로 daemon.json 설정
$daemonConfig = @{
    "log-driver" = "json-file"
    "log-opts" = @{
        "max-size" = "100m"
        "max-file" = "3"
    }
} | ConvertTo-Json

# 설정 파일 저장
$daemonConfig | Out-File -FilePath "$env:USERPROFILE\.docker\daemon.json" -Encoding UTF8

# Docker Desktop 재시작 필요
Write-Host "Docker Desktop을 재시작해주세요."
```

### PowerShell 성능 모니터링

```powershell
# 실시간 리소스 사용량 (테이블 형식)
docker stats --format "table {{.Container}}`t{{.CPUPerc}}`t{{.MemUsage}}`t{{.NetIO}}"

# JSON 형식으로 상세 정보
docker stats --format json --no-stream

# 컨테이너별 상세 정보
docker inspect flask_dashboard | ConvertFrom-Json

# PowerShell을 사용한 성능 모니터링 스크립트
while ($true) {
    Clear-Host
    Write-Host "=== Docker 컨테이너 성능 모니터링 ===" -ForegroundColor Green
    docker stats --no-stream
    Write-Host "`n업데이트: $(Get-Date)" -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
```

## 🔄 업데이트 및 백업

### PowerShell 애플리케이션 업데이트

```powershell
# Git을 통한 코드 업데이트
git pull

# 서비스 재시작
.\deploy.bat restart

# 또는 직접 Docker Compose 사용
docker compose down
docker compose up -d --build
```

### PowerShell 데이터베이스 백업

```powershell
# 배치 파일을 통한 자동 백업
.\deploy.bat backup

# 수동 백업
$backupPath = "backups\db_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
New-Item -ItemType Directory -Path "backups" -Force
docker compose exec mariadb mysqldump -u root -p dashboard_db > $backupPath

# 백업 복원 (예시)
# $restoreFile = "backups\db_backup_20241201_120000.sql"
# Get-Content $restoreFile | docker compose exec -T mariadb mysql -u root -p dashboard_db
```

### Windows 작업 스케줄러를 이용한 정기 백업

```powershell
# 백업 스크립트 생성
@"
Set-Location "C:\path\to\your-project"
.\deploy.bat backup
"@ | Out-File -FilePath "backup_script.ps1" -Encoding UTF8

# 작업 스케줄러에 등록 (관리자 권한 필요)
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\path\to\your-project\backup_script.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00AM"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask -TaskName "Flask Dashboard Backup" -Action $action -Trigger $trigger -Settings $settings -Description "Daily backup of Flask Dashboard database"

# 작업 스케줄러 GUI 열기
Start-Process "taskschd.msc"
```

## 🆘 지원 및 문의

### PowerShell 로그 수집

문제 발생 시 다음 정보를 PowerShell로 수집하여 문의하세요:

```powershell
# 시스템 정보 수집
@"
=== 시스템 정보 ===
Windows 버전: $(Get-ComputerInfo -Property WindowsProductName, WindowsVersion | Format-List | Out-String)
PowerShell 버전: $($PSVersionTable.PSVersion)
Docker 버전: $(docker --version)
Docker Compose 버전: $(docker compose version)
WSL 버전: $(wsl --version 2>$null)

=== Docker 상태 ===
$(docker compose ps -a)

=== 최근 로그 ===
$(docker compose logs --tail=100)
"@ | Out-File -FilePath "system_info.txt" -Encoding UTF8

Write-Host "시스템 정보가 system_info.txt 파일에 저장되었습니다." -ForegroundColor Green

# 개별 로그 파일 생성
docker compose logs flask_app --tail=50 | Out-File -FilePath "flask_app.log" -Encoding UTF8
docker compose logs mariadb --tail=50 | Out-File -FilePath "mariadb.log" -Encoding UTF8
docker compose logs nginx --tail=50 | Out-File -FilePath "nginx.log" -Encoding UTF8
```

### 시스템 진단 스크립트

```powershell
# 자동 진단 스크립트
function Test-DockerEnvironment {
    Write-Host "=== Flask Dashboard Docker 환경 진단 ===" -ForegroundColor Cyan

    # Docker Desktop 상태 확인
    Write-Host "`n1. Docker Desktop 상태:" -ForegroundColor Yellow
    try {
        $dockerVersion = docker --version
        Write-Host "✓ Docker 설치됨: $dockerVersion" -ForegroundColor Green
    } catch {
        Write-Host "✗ Docker가 설치되지 않았거나 실행되지 않음" -ForegroundColor Red
        return
    }

    # .env 파일 확인
    Write-Host "`n2. 환경 설정 확인:" -ForegroundColor Yellow
    if (Test-Path ".env") {
        Write-Host "✓ .env 파일 존재" -ForegroundColor Green
        $envContent = Get-Content ".env" | Where-Object {$_ -notmatch "^#" -and $_ -match "="}
        Write-Host "환경 변수 개수: $($envContent.Count)" -ForegroundColor Green
    } else {
        Write-Host "✗ .env 파일이 없음" -ForegroundColor Red
    }

    # 포트 사용 상태 확인
    Write-Host "`n3. 포트 사용 상태:" -ForegroundColor Yellow
    $ports = @(80, 443, 3306, 8000)
    foreach ($port in $ports) {
        $portInUse = netstat -ano | findstr ":$port "
        if ($portInUse) {
            Write-Host "⚠ 포트 $port 사용 중" -ForegroundColor Yellow
        } else {
            Write-Host "✓ 포트 $port 사용 가능" -ForegroundColor Green
        }
    }

    # 컨테이너 상태 확인
    Write-Host "`n4. 컨테이너 상태:" -ForegroundColor Yellow
    try {
        $containers = docker compose ps -a --format json | ConvertFrom-Json
        if ($containers) {
            foreach ($container in $containers) {
                $status = if ($container.State -eq "running") { "✓" } else { "✗" }
                $color = if ($container.State -eq "running") { "Green" } else { "Red" }
                Write-Host "$status $($container.Service): $($container.State)" -ForegroundColor $color
            }
        } else {
            Write-Host "컨테이너가 없습니다." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "컨테이너 상태를 확인할 수 없습니다." -ForegroundColor Red
    }

    Write-Host "`n진단 완료!" -ForegroundColor Cyan
}

# 진단 실행
Test-DockerEnvironment
```

### 추가 리소스

- **Docker Desktop for Windows**: https://docs.docker.com/desktop/windows/
- **PowerShell 공식 문서**: https://docs.microsoft.com/powershell/
- **WSL2 설정 가이드**: https://docs.microsoft.com/windows/wsl/
- **Flask 공식 문서**: https://flask.palletsprojects.com/
- **MariaDB 공식 문서**: https://mariadb.org/documentation/
- **Nginx 공식 문서**: https://nginx.org/en/docs/

---

## 📝 Windows 환경 주의사항

1. **Docker Desktop 설정**: WSL2 백엔드 사용을 권장합니다.
2. **방화벽 설정**: Windows Defender 방화벽에서 Docker 포트를 허용해야 합니다.
3. **경로 구분자**: Windows에서는 백슬래시(`\`)를 사용하지만, Docker 내부에서는 슬래시(`/`)를 사용합니다.
4. **권한 문제**: 일부 작업은 관리자 권한이 필요할 수 있습니다.
5. **메모리 관리**: WSL2의 메모리 사용량을 `.wslconfig` 파일로 제한할 수 있습니다.

## 🚦 운영 환경 체크리스트

### 배포 전 확인사항

- [ ] `.env` 파일의 모든 기본 비밀번호 변경
- [ ] Docker Desktop 최신 버전 설치 및 WSL2 활성화
- [ ] 방화벽 설정으로 필요한 포트만 개방
- [ ] SSL 인증서 설정 (HTTPS 사용 시)
- [ ] 백업 스크립트 테스트 및 정기 백업 설정
- [ ] 모니터링 시스템 구축
- [ ] 로그 순환 정책 설정

### 보안 강화

- [ ] 데이터베이스 root 비밀번호 복잡성 증대
- [ ] Flask SECRET_KEY를 강력한 랜덤 값으로 설정
- [ ] 불필요한 서비스 비활성화
- [ ] 컨테이너 업데이트 자동화 설정
- [ ] 침입 탐지 시스템 구축 검토

> 이 PowerShell 기반 가이드는 Windows 환경에 최적화되어 있습니다. 최신 버전은 프로젝트 저장소에서 확인하세요.