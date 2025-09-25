#!/bin/bash

# Flask Dashboard Docker 배포 스크립트
# 사용법: ./deploy.sh [start|stop|restart|logs|status]

set -e

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수들
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 환경 확인
check_requirements() {
    log_info "시스템 요구사항 확인 중..."

    # Docker 설치 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되어 있지 않습니다."
        log_info "Docker 설치: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Docker Compose 설치 확인
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose가 설치되어 있지 않습니다."
        log_info "Docker Compose 설치: https://docs.docker.com/compose/install/"
        exit 1
    fi

    # .env 파일 확인
    if [ ! -f ".env" ]; then
        log_warning ".env 파일이 없습니다. .env.example을 복사하여 설정을 완료하세요."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info ".env 파일이 생성되었습니다. 설정을 확인하고 수정하세요."
        else
            log_error ".env.example 파일도 없습니다."
            exit 1
        fi
    fi

    log_success "요구사항 확인 완료"
}

# 서비스 시작
start_services() {
    log_info "Flask Dashboard 서비스 시작 중..."

    # 기존 컨테이너 정리 (필요시)
    docker-compose down --remove-orphans 2>/dev/null || true

    # 이미지 빌드 및 서비스 시작
    docker-compose up -d --build

    log_info "서비스 시작 대기 중..."
    sleep 10

    # 헬스체크
    check_health
}

# 서비스 중지
stop_services() {
    log_info "Flask Dashboard 서비스 중지 중..."
    docker-compose down
    log_success "서비스가 중지되었습니다."
}

# 서비스 재시작
restart_services() {
    log_info "Flask Dashboard 서비스 재시작 중..."
    stop_services
    sleep 2
    start_services
}

# 로그 보기
show_logs() {
    log_info "서비스 로그를 표시합니다. (Ctrl+C로 종료)"
    docker-compose logs -f
}

# 서비스 상태 확인
check_status() {
    log_info "서비스 상태 확인 중..."
    echo
    docker-compose ps
    echo

    # 각 서비스별 상태 확인
    if docker-compose ps | grep -q "flask_mariadb.*Up"; then
        log_success "MariaDB: 실행 중"
    else
        log_error "MariaDB: 정지됨"
    fi

    if docker-compose ps | grep -q "flask_dashboard.*Up"; then
        log_success "Flask App: 실행 중"
    else
        log_error "Flask App: 정지됨"
    fi

    if docker-compose ps | grep -q "flask_nginx.*Up"; then
        log_success "Nginx: 실행 중"
    else
        log_error "Nginx: 정지됨"
    fi

    # 웹사이트 접속 테스트
    if curl -s http://localhost/health > /dev/null 2>&1; then
        log_success "웹사이트: 접속 가능 (http://localhost)"
    else
        log_warning "웹사이트: 접속 불가"
    fi
}

# 헬스체크
check_health() {
    log_info "서비스 헬스체크 실행 중..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost/health > /dev/null 2>&1; then
            log_success "모든 서비스가 정상적으로 실행되고 있습니다!"
            log_info "웹사이트 주소: http://localhost"
            return 0
        fi

        log_info "헬스체크 시도 $attempt/$max_attempts..."
        sleep 5
        ((attempt++))
    done

    log_error "서비스 시작에 실패했습니다. 로그를 확인하세요:"
    log_info "로그 확인: ./deploy.sh logs"
    return 1
}

# 개발 모드
dev_mode() {
    log_info "개발 모드로 서비스 시작 중..."

    # 개발용 docker-compose 파일이 있으면 사용
    if [ -f "docker-compose.dev.yml" ]; then
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
    else
        # Flask 앱만 개발 모드로 재시작
        docker-compose up -d mariadb nginx
        docker-compose up --build flask_app
    fi
}

# 데이터베이스 백업
backup_database() {
    log_info "데이터베이스 백업 중..."

    local backup_dir="backups"
    local backup_file="${backup_dir}/db_backup_$(date +%Y%m%d_%H%M%S).sql"

    mkdir -p "$backup_dir"

    docker-compose exec mariadb mysqldump -u root -p$(grep DB_ROOT_PASSWORD .env | cut -d '=' -f2) dashboard_db > "$backup_file"

    if [ $? -eq 0 ]; then
        log_success "데이터베이스 백업 완료: $backup_file"
    else
        log_error "데이터베이스 백업 실패"
        return 1
    fi
}

# 데이터베이스 복원
restore_database() {
    if [ -z "$1" ]; then
        log_error "백업 파일을 지정하세요: ./deploy.sh restore <backup_file>"
        return 1
    fi

    if [ ! -f "$1" ]; then
        log_error "백업 파일이 존재하지 않습니다: $1"
        return 1
    fi

    log_warning "데이터베이스를 복원하면 기존 데이터가 삭제됩니다!"
    read -p "계속하시겠습니까? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "데이터베이스 복원 중..."
        docker-compose exec -T mariadb mysql -u root -p$(grep DB_ROOT_PASSWORD .env | cut -d '=' -f2) dashboard_db < "$1"
        log_success "데이터베이스 복원 완료"
    else
        log_info "복원이 취소되었습니다."
    fi
}

# 도움말
show_help() {
    echo "Flask Dashboard Docker 배포 스크립트"
    echo
    echo "사용법: $0 [명령어]"
    echo
    echo "명령어:"
    echo "  start     - 서비스 시작"
    echo "  stop      - 서비스 중지"
    echo "  restart   - 서비스 재시작"
    echo "  status    - 서비스 상태 확인"
    echo "  logs      - 서비스 로그 보기"
    echo "  dev       - 개발 모드 시작"
    echo "  backup    - 데이터베이스 백업"
    echo "  restore   - 데이터베이스 복원"
    echo "  help      - 이 도움말 표시"
    echo
    echo "예시:"
    echo "  $0 start     # 서비스 시작"
    echo "  $0 logs      # 로그 보기"
    echo "  $0 backup    # DB 백업"
}

# 메인 실행부
main() {
    case "${1:-help}" in
        start)
            check_requirements
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            check_requirements
            restart_services
            ;;
        status)
            check_status
            ;;
        logs)
            show_logs
            ;;
        dev)
            check_requirements
            dev_mode
            ;;
        backup)
            backup_database
            ;;
        restore)
            restore_database "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "알 수 없는 명령어: $1"
            show_help
            exit 1
            ;;
    esac
}

# 스크립트 실행
main "$@"