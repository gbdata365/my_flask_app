-- Flask Dashboard 데이터베이스 초기화 스크립트
-- MariaDB/MySQL용

-- 문자셋 설정
SET NAMES utf8mb4;
SET character_set_client = utf8mb4;

-- 데이터베이스가 존재하지 않으면 생성
CREATE DATABASE IF NOT EXISTS `dashboard_db`
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE `dashboard_db`;

-- 사용자 테이블 (향후 확장용)
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_active` BOOLEAN DEFAULT TRUE,
    INDEX `idx_username` (`username`),
    INDEX `idx_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 업로드 파일 관리 테이블
CREATE TABLE IF NOT EXISTS `uploaded_files` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `original_filename` VARCHAR(255) NOT NULL,
    `stored_filename` VARCHAR(255) NOT NULL,
    `file_path` VARCHAR(500) NOT NULL,
    `file_size` BIGINT NOT NULL,
    `file_type` VARCHAR(50) NOT NULL,
    `upload_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `category` VARCHAR(50) DEFAULT NULL,
    `user_id` INT DEFAULT NULL,
    `is_processed` BOOLEAN DEFAULT FALSE,
    INDEX `idx_category` (`category`),
    INDEX `idx_upload_date` (`upload_date`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 데이터 분석 결과 저장 테이블 (1_giup용)
CREATE TABLE IF NOT EXISTS `giup_analysis_results` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `file_id` INT NOT NULL,
    `analysis_type` VARCHAR(50) NOT NULL,
    `result_data` JSON NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `year` INT DEFAULT NULL,
    `month` INT DEFAULT NULL,
    `region` VARCHAR(100) DEFAULT NULL,
    INDEX `idx_file_id` (`file_id`),
    INDEX `idx_year_month` (`year`, `month`),
    INDEX `idx_region` (`region`),
    FOREIGN KEY (`file_id`) REFERENCES `uploaded_files`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 의료통계 데이터 테이블 (2_의료통계용)
CREATE TABLE IF NOT EXISTS `medical_statistics` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `year` INT NOT NULL,
    `month` INT DEFAULT NULL,
    `region_code` VARCHAR(10) NOT NULL,
    `region_name` VARCHAR(100) NOT NULL,
    `hospital_count` INT DEFAULT 0,
    `clinic_count` INT DEFAULT 0,
    `patient_count` INT DEFAULT 0,
    `statistics_data` JSON DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_year_month` (`year`, `month`),
    INDEX `idx_region` (`region_code`, `region_name`),
    UNIQUE KEY `unique_year_month_region` (`year`, `month`, `region_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- CSV 대시보드 분석 결과 (3_csv_dashboard용)
CREATE TABLE IF NOT EXISTS `csv_analysis_cache` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `file_hash` VARCHAR(64) NOT NULL UNIQUE,
    `file_name` VARCHAR(255) NOT NULL,
    `analysis_result` JSON NOT NULL,
    `chart_data` JSON DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `accessed_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_file_hash` (`file_hash`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 시스템 로그 테이블
CREATE TABLE IF NOT EXISTS `system_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `level` ENUM('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') NOT NULL,
    `message` TEXT NOT NULL,
    `module` VARCHAR(50) DEFAULT NULL,
    `user_id` INT DEFAULT NULL,
    `ip_address` VARCHAR(45) DEFAULT NULL,
    `user_agent` TEXT DEFAULT NULL,
    `request_data` JSON DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_level` (`level`),
    INDEX `idx_module` (`module`),
    INDEX `idx_created_at` (`created_at`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 설정 테이블
CREATE TABLE IF NOT EXISTS `app_settings` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `setting_key` VARCHAR(100) NOT NULL UNIQUE,
    `setting_value` TEXT NOT NULL,
    `description` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_setting_key` (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 기본 설정값 삽입
INSERT INTO `app_settings` (`setting_key`, `setting_value`, `description`) VALUES
('app_version', '1.0.0', 'Application version'),
('maintenance_mode', 'false', 'Maintenance mode flag'),
('max_upload_size', '104857600', 'Maximum upload file size in bytes (100MB)'),
('allowed_file_types', 'csv,xlsx,xls', 'Allowed file extensions for upload'),
('data_retention_days', '365', 'Data retention period in days')
ON DUPLICATE KEY UPDATE
    `setting_value` = VALUES(`setting_value`),
    `updated_at` = CURRENT_TIMESTAMP;

-- 기본 관리자 사용자 생성 (비밀번호: admin123)
-- 실제 운영 시에는 반드시 변경하세요!
INSERT INTO `users` (`username`, `email`, `password_hash`) VALUES
('admin', 'admin@dashboard.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewggrW4gFd7Rms4G')
ON DUPLICATE KEY UPDATE
    `email` = VALUES(`email`),
    `updated_at` = CURRENT_TIMESTAMP;

-- 인덱스 최적화를 위한 추가 설정
OPTIMIZE TABLE `users`;
OPTIMIZE TABLE `uploaded_files`;
OPTIMIZE TABLE `giup_analysis_results`;
OPTIMIZE TABLE `medical_statistics`;
OPTIMIZE TABLE `csv_analysis_cache`;
OPTIMIZE TABLE `system_logs`;
OPTIMIZE TABLE `app_settings`;

-- 권한 확인 및 설정
SHOW GRANTS FOR CURRENT_USER;