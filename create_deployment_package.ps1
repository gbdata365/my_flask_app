# Flask Dashboard 배포 패키지 생성 스크립트 (PowerShell)
# 사용법: .\create_deployment_package.ps1

param(
    [string]$OutputPath = "flask_dashboard_deployment_$(Get-Date -Format 'yyyyMMdd_HHmmss')",
    [switch]$IncludeData = $false,
    [switch]$Help = $false
)

# 색상 설정
$colors = @{
    Red = "Red"
    Green = "Green"
    Yellow = "Yellow"
    Blue = "Blue"
    Cyan = "Cyan"
}

# 로그 함수들
function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor $colors.Blue
}

function Write-Success($message) {
    Write-Host "[SUCCESS] $message" -ForegroundColor $colors.Green
}

function Write-Warning($message) {
    Write-Host "[WARNING] $message" -ForegroundColor $colors.Yellow
}

function Write-Error($message) {
    Write-Host "[ERROR] $message" -ForegroundColor $colors.Red
}

# 도움말 표시
function Show-Help {
    Write-Host @"
Flask Dashboard 배포 패키지 생성 스크립트

사용법:
  .\create_deployment_package.ps1 [옵션]

옵션:
  -OutputPath <경로>   출력 디렉토리 경로 (기본값: flask_dashboard_deployment_YYYYMMDD_HHMMSS)
  -IncludeData        데이터 폴더 포함 여부 (기본값: 제외)
  -Help               이 도움말 표시

예시:
  .\create_deployment_package.ps1
  .\create_deployment_package.ps1 -OutputPath "my_deployment" -IncludeData
"@ -ForegroundColor $colors.Cyan
}

if ($Help) {
    Show-Help
    exit 0
}

Write-Info "Flask Dashboard 배포 패키지 생성을 시작합니다..."
Write-Info "출력 경로: $OutputPath"

# 현재 디렉토리 확인
if (!(Test-Path "main_app.py")) {
    Write-Error "main_app.py 파일이 없습니다. 프로젝트 루트 디렉토리에서 실행하세요."
    exit 1
}

# 출력 디렉토리 생성
if (Test-Path $OutputPath) {
    Write-Warning "출력 디렉토리가 이미 존재합니다. 삭제 후 재생성합니다."
    Remove-Item $OutputPath -Recurse -Force
}

New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
Write-Success "출력 디렉토리 생성: $OutputPath"

# 복사할 파일 및 폴더 목록
$essentialItems = @(
    # Docker 설정 파일
    "docker-compose.yml",
    "Dockerfile",
    ".dockerignore",

    # 환경 설정
    ".env.example",
    "requirements.txt",

    # 메인 애플리케이션
    "main_app.py",
    "CLAUDE.md",

    # 배포 스크립트
    "deploy.sh",
    "deploy.bat",
    "Docker_배포_가이드.md",

    # 디렉토리
    "module",
    "templates",
    "static",
    "nginx",
    "database",
    "1_giup",
    "2_의료통계",
    "3_csv_dashboard"
)

# 선택적으로 포함할 항목들
$optionalItems = @()
if ($IncludeData) {
    Write-Info "데이터 폴더를 포함합니다..."
    $optionalItems += @("uploads")
}

# 제외할 패턴들
$excludePatterns = @(
    "*.pyc",
    "__pycache__",
    ".git",
    "*.log",
    "*.tmp",
    ".env",  # 보안을 위해 실제 .env는 제외
    "backups",
    ".vscode",
    ".idea",
    "*.backup"
)

Write-Info "필수 파일 및 폴더 복사 중..."

foreach ($item in $essentialItems) {
    if (Test-Path $item) {
        $destination = Join-Path $OutputPath $item

        if (Test-Path $item -PathType Container) {
            # 디렉토리 복사 (제외 패턴 적용)
            Write-Info "디렉토리 복사: $item"
            Copy-Directory -Source $item -Destination $destination -ExcludePatterns $excludePatterns
        } else {
            # 파일 복사
            Write-Info "파일 복사: $item"
            Copy-Item $item -Destination $destination -Force
        }
    } else {
        Write-Warning "파일/폴더를 찾을 수 없습니다: $item"
    }
}

# 선택적 항목 복사
foreach ($item in $optionalItems) {
    if (Test-Path $item) {
        $destination = Join-Path $OutputPath $item
        Write-Info "선택적 항목 복사: $item"
        Copy-Directory -Source $item -Destination $destination -ExcludePatterns $excludePatterns
    }
}

# 디렉토리 복사 함수 (제외 패턴 적용)
function Copy-Directory {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExcludePatterns = @()
    )

    # robocopy를 사용한 고급 복사 (Windows 기본 제공)
    $excludeFiles = ($ExcludePatterns | ForEach-Object { $_ }) -join " "
    $robocopyArgs = @($Source, $Destination, "/E", "/NFL", "/NDL", "/NJS")

    if ($ExcludePatterns.Count -gt 0) {
        foreach ($pattern in $ExcludePatterns) {
            $robocopyArgs += "/XD"
            $robocopyArgs += $pattern
            $robocopyArgs += "/XF"
            $robocopyArgs += $pattern
        }
    }

    try {
        $result = & robocopy @robocopyArgs
        # robocopy 종료 코드 8 이하는 성공으로 간주
        if ($LASTEXITCODE -le 8) {
            return $true
        }
    } catch {
        # robocopy 실패 시 PowerShell 기본 복사 사용
        Copy-Item $Source -Destination $Destination -Recurse -Force
    }
}

# README 파일 생성
$readmeContent = @"
# Flask Dashboard 배포 패키지

생성일: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
생성자: $(whoami)

## 📦 패키지 내용

이 패키지에는 Flask Dashboard를 Docker로 배포하는데 필요한 모든 파일이 포함되어 있습니다.

### 핵심 구성요소

- **Docker 설정**: docker-compose.yml, Dockerfile
- **Flask 애플리케이션**: main_app.py, module/, templates/
- **웹 서버 설정**: nginx/ 디렉토리
- **데이터베이스 설정**: database/ 디렉토리
- **배포 스크립트**: deploy.bat (Windows), deploy.sh (Linux)

## 🚀 빠른 설치 가이드

### 1. 요구사항
- Docker Desktop (Windows) 또는 Docker Engine (Linux)
- PowerShell 5.1+ (Windows) 또는 Bash (Linux)

### 2. 설치 과정

#### Windows PowerShell:
``````powershell
# 1. 환경 설정 파일 생성
Copy-Item ".env.example" ".env"

# 2. .env 파일 편집 (비밀번호 변경 필수!)
notepad .env

# 3. 서비스 시작
.\deploy.bat start

# 4. 웹 브라우저에서 접속
# http://localhost
``````

#### Linux:
``````bash
# 1. 실행 권한 부여
chmod +x deploy.sh

# 2. 환경 설정
cp .env.example .env
vi .env

# 3. 서비스 시작
./deploy.sh start
``````

## ⚠️ 보안 주의사항

1. **.env 파일 수정 필수**: 기본 비밀번호를 반드시 변경하세요
2. **방화벽 설정**: 필요한 포트만 개방하세요
3. **SSL 인증서**: 운영 환경에서는 HTTPS 설정을 권장합니다

## 📖 상세 가이드

자세한 설치 및 운영 가이드는 **Docker_배포_가이드.md** 파일을 참고하세요.

## 🆘 문제 해결

문제 발생 시 다음 명령어로 로그를 확인하세요:

``````powershell
# Windows
.\deploy.bat logs

# Linux
./deploy.sh logs
``````

---
생성된 배포 패키지 버전: $(Get-Date -Format 'yyyy.MM.dd.HHmmss')
"@

$readmeContent | Out-File -FilePath (Join-Path $OutputPath "README.md") -Encoding UTF8

# 설치 스크립트 생성 (Windows용)
$installScript = @"
@echo off
echo Flask Dashboard 자동 설치 스크립트
echo.

REM 환경 설정 파일 생성
if not exist ".env" (
    echo .env 파일을 생성합니다...
    copy ".env.example" ".env"
    echo.
    echo ⚠️  중요: .env 파일의 비밀번호를 변경하세요!
    echo    notepad .env 명령으로 편집할 수 있습니다.
    echo.
    pause
)

REM Docker 설치 확인
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker가 설치되어 있지 않습니다.
    echo    Docker Desktop을 설치한 후 다시 실행하세요.
    echo    다운로드: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

echo ✅ Docker가 설치되어 있습니다.
echo.

REM 서비스 시작
echo Flask Dashboard 서비스를 시작합니다...
deploy.bat start

echo.
echo 🎉 설치가 완료되었습니다!
echo 웹 브라우저에서 http://localhost 에 접속하세요.
echo.
pause
"@

$installScript | Out-File -FilePath (Join-Path $OutputPath "install.bat") -Encoding Default

# 배포 패키지 압축 생성
$zipPath = "$OutputPath.zip"
Write-Info "배포 패키지 압축 파일 생성 중..."

try {
    Compress-Archive -Path "$OutputPath\*" -DestinationPath $zipPath -CompressionLevel Optimal
    Write-Success "배포 패키지 압축 파일 생성 완료: $zipPath"
} catch {
    Write-Warning "압축 파일 생성에 실패했습니다: $($_.Exception.Message)"
}

# 요약 정보 출력
Write-Success "`n=== 배포 패키지 생성 완료 ==="
Write-Info "📁 디렉토리: $OutputPath"
Write-Info "📦 압축파일: $zipPath"
Write-Info "📄 설치가이드: $OutputPath\README.md"
Write-Info "🚀 자동설치: $OutputPath\install.bat"

Write-Host "`n다음 단계:" -ForegroundColor $colors.Cyan
Write-Host "1. $zipPath 파일을 대상 서버로 복사" -ForegroundColor $colors.Yellow
Write-Host "2. 서버에서 압축 해제" -ForegroundColor $colors.Yellow
Write-Host "3. install.bat 실행 (Windows) 또는 deploy.sh start (Linux)" -ForegroundColor $colors.Yellow
Write-Host "4. 웹 브라우저에서 http://서버IP 접속" -ForegroundColor $colors.Yellow

Write-Warning "`n⚠️  중요: .env 파일의 기본 비밀번호를 반드시 변경하세요!"