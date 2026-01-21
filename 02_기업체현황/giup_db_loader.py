# -*- coding: utf-8 -*-
"""
기업체현황 집계표 DB 적재 스크립트
- 하이브리드 방식: 메인 테이블 + 시트별 상세 테이블
- 재적재 지원 (전체 삭제 후 INSERT)
- '*' 값은 1로 변환 (3 이하 비식별화)
"""

import sys
import re
from pathlib import Path
from typing import Optional
import pandas as pd
from loguru import logger

# 상위 디렉토리의 module 추가
sys.path.insert(0, str(Path(__file__).parent.parent))
from module.db import get_db_connection


# ============================================================
# 설정
# ============================================================
DATA_DIR = Path(__file__).parent / "data"

# base_ym 변환 규칙
def parse_base_ym(raw_value: str) -> tuple[str, str]:
    """
    원본 기준시기 → (표준화된 base_ym, data_type) 변환

    예시:
        '2023년' → ('202312', 'annual')
        '2024년 1분기' → ('202403', 'quarterly')
        '2024년 2분기' → ('202406', 'quarterly')
        '2024년 3분기' → ('202409', 'quarterly')
        '2024년 4분기' → ('202412', 'quarterly')
        '2025년 10월' → ('202510', 'monthly')
    """
    raw_value = str(raw_value).strip()

    # 연간: "2023년"
    match = re.match(r'(\d{4})년$', raw_value)
    if match:
        year = match.group(1)
        return f"{year}12", "annual"

    # 분기: "2024년 1분기"
    match = re.match(r'(\d{4})년\s*(\d)분기', raw_value)
    if match:
        year = match.group(1)
        quarter = int(match.group(2))
        month = str(quarter * 3).zfill(2)
        return f"{year}{month}", "quarterly"

    # 월간: "2025년 10월"
    match = re.match(r'(\d{4})년\s*(\d{1,2})월', raw_value)
    if match:
        year = match.group(1)
        month = match.group(2).zfill(2)
        return f"{year}{month}", "monthly"

    logger.warning(f"파싱 실패: {raw_value}")
    return raw_value, "unknown"


def clean_value(val, convert_star_to: int = 1):
    """
    값 정리
    - '*' → convert_star_to (기본 1)
    - NaN → None
    - 숫자 변환
    """
    if pd.isna(val):
        return None
    if val == '*':
        return convert_star_to
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return val


# ============================================================
# 테이블 생성 SQL
# ============================================================
CREATE_TABLES_SQL = """
-- 메인 테이블: 공통 정보
DROP TABLE IF EXISTS giup_detail_stats CASCADE;
DROP TABLE IF EXISTS giup_detail_corp_size CASCADE;
DROP TABLE IF EXISTS giup_detail_main_biz CASCADE;
DROP TABLE IF EXISTS giup_detail_age_group CASCADE;
DROP TABLE IF EXISTS giup_detail_industry CASCADE;
DROP TABLE IF EXISTS giup_detail_status CASCADE;
DROP TABLE IF EXISTS giup_detail_gender CASCADE;
DROP TABLE IF EXISTS giup_detail_org_type CASCADE;
DROP TABLE IF EXISTS giup_summary CASCADE;

CREATE TABLE giup_summary (
    id SERIAL PRIMARY KEY,
    base_ym VARCHAR(6) NOT NULL,           -- 표준화된 기준년월 (JOIN용): 202312, 202403 등
    base_ym1 VARCHAR(30) NOT NULL,         -- 원본 기준시기: 2023년, 2024년 1분기
    data_type VARCHAR(15) NOT NULL,        -- annual, quarterly, monthly
    sido_nm VARCHAR(30),                   -- 시도명
    sigun_nm VARCHAR(30),                  -- 시군구명
    sigun_cd VARCHAR(5),                   -- 시군구코드 5자리
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (base_ym, data_type, sido_nm, sigun_nm)
);

CREATE INDEX idx_giup_summary_base_ym ON giup_summary(base_ym);
CREATE INDEX idx_giup_summary_sigun_cd ON giup_summary(sigun_cd);
CREATE INDEX idx_giup_summary_data_type ON giup_summary(data_type);

-- 조직형태별
CREATE TABLE giup_detail_org_type (
    id SERIAL PRIMARY KEY,
    summary_id INTEGER NOT NULL REFERENCES giup_summary(id) ON DELETE CASCADE,
    indiv_biz INTEGER,           -- 개인사업체
    corp INTEGER,                -- 회사법인
    corp_other INTEGER,          -- 회사이외법인
    non_corp INTEGER,            -- 비법인단체
    gov_local INTEGER,           -- 국가지방자치단체
    total INTEGER                -- 합계
);

-- 대표자성별별
CREATE TABLE giup_detail_gender (
    id SERIAL PRIMARY KEY,
    summary_id INTEGER NOT NULL REFERENCES giup_summary(id) ON DELETE CASCADE,
    blank INTEGER,               -- (공백)
    male INTEGER,                -- 남자
    female INTEGER,              -- 여자
    total INTEGER                -- 합계
);

-- 폐업여부별
CREATE TABLE giup_detail_status (
    id SERIAL PRIMARY KEY,
    summary_id INTEGER NOT NULL REFERENCES giup_summary(id) ON DELETE CASCADE,
    active INTEGER,              -- 영업중
    closed INTEGER,              -- 폐업
    total INTEGER                -- 합계
);

-- 산업분류별 (대분류)
CREATE TABLE giup_detail_industry (
    id SERIAL PRIMARY KEY,
    summary_id INTEGER NOT NULL REFERENCES giup_summary(id) ON DELETE CASCADE,
    blank INTEGER,               -- (공백)
    ind_a INTEGER,               -- 농업,임업,어업
    ind_b INTEGER,               -- 광업
    ind_c INTEGER,               -- 제조업
    ind_d INTEGER,               -- 전기가스공급업
    ind_e INTEGER,               -- 수도하수폐기물
    ind_f INTEGER,               -- 건설업
    ind_g INTEGER,               -- 도매및소매업
    ind_h INTEGER,               -- 운수및창고업
    ind_i INTEGER,               -- 숙박및음식점업
    ind_j INTEGER,               -- 정보통신업
    ind_k INTEGER,               -- 금융및보험업
    ind_l INTEGER,               -- 부동산업
    ind_m INTEGER,               -- 전문과학기술서비스
    ind_n INTEGER,               -- 사업시설관리
    ind_o INTEGER,               -- 공공행정
    ind_p INTEGER,               -- 교육서비스업
    ind_q INTEGER,               -- 보건사회복지
    ind_r INTEGER,               -- 예술스포츠여가
    ind_s INTEGER,               -- 협회및개인서비스
    ind_t INTEGER,               -- 가구내고용활동
    ind_u INTEGER,               -- 국제외국기관
    total INTEGER                -- 합계
);

-- 연령그룹별 (연간/월간만)
CREATE TABLE giup_detail_age_group (
    id SERIAL PRIMARY KEY,
    summary_id INTEGER NOT NULL REFERENCES giup_summary(id) ON DELETE CASCADE,
    age_under_19 INTEGER,        -- ~19세이하 / ~19세
    age_20_early INTEGER,        -- 20대초
    age_20_late INTEGER,         -- 20대후
    age_30_early INTEGER,        -- 30대초
    age_30_late INTEGER,         -- 30대후
    age_40_early INTEGER,        -- 40대초
    age_40_late INTEGER,         -- 40대후
    age_50_early INTEGER,        -- 50대초
    age_50_late INTEGER,         -- 50대후
    age_60_early INTEGER,        -- 60대초
    age_60_late INTEGER,         -- 60대후
    age_70_early INTEGER,        -- 70대초
    age_70_late INTEGER,         -- 70대후
    age_80_early INTEGER,        -- 80대초
    age_80_over INTEGER,         -- 80대후이상
    blank INTEGER,               -- (공백)
    total INTEGER                -- 합계
);

-- 대표사업체별
CREATE TABLE giup_detail_main_biz (
    id SERIAL PRIMARY KEY,
    summary_id INTEGER NOT NULL REFERENCES giup_summary(id) ON DELETE CASCADE,
    blank INTEGER,               -- (공백)
    total INTEGER                -- 합계 (본점+지점 구분 없이 합계만)
);

-- 기업규모별 (연간만)
CREATE TABLE giup_detail_corp_size (
    id SERIAL PRIMARY KEY,
    summary_id INTEGER NOT NULL REFERENCES giup_summary(id) ON DELETE CASCADE,
    blank INTEGER,               -- (공백)
    large_other INTEGER,         -- 기타대기업
    mid_large INTEGER,           -- 중견기업
    mid INTEGER,                 -- 중기업
    small INTEGER,               -- 소기업
    micro INTEGER,               -- 소상공인
    excluded INTEGER,            -- 기업규모판정제외사업자
    sangchul INTEGER,            -- 상출기업
    total INTEGER                -- 합계
);

-- 수치형통계
CREATE TABLE giup_detail_stats (
    id SERIAL PRIMARY KEY,
    summary_id INTEGER NOT NULL REFERENCES giup_summary(id) ON DELETE CASCADE,
    emp_count INTEGER,           -- 기업종사자수_건수
    emp_sum BIGINT,              -- 기업종사자수_합계
    emp_avg NUMERIC(15,2),       -- 기업종사자수_평균
    emp_blank INTEGER,           -- 기업종사자수_공백건수
    sales_count INTEGER,         -- 기업매출금액_건수
    sales_sum BIGINT,            -- 기업매출금액_합계
    sales_avg NUMERIC(20,2),     -- 기업매출금액_평균
    sales_blank INTEGER,         -- 기업매출금액_공백건수
    regular_count INTEGER,       -- 기업상용근로자수_건수
    regular_sum BIGINT,          -- 기업상용근로자수_합계
    regular_avg NUMERIC(15,2),   -- 기업상용근로자수_평균
    regular_blank INTEGER,       -- 기업상용근로자수_공백건수
    temp_count INTEGER,          -- 기업임시일용근로자수_건수
    temp_sum BIGINT,             -- 기업임시일용근로자수_합계
    temp_avg NUMERIC(15,2),      -- 기업임시일용근로자수_평균
    temp_blank INTEGER           -- 기업임시일용근로자수_공백건수
);
"""

# ============================================================
# 시군구 코드 매핑 (dim_admin_area 테이블 사용)
# ============================================================
def get_sigun_code_map(conn) -> dict:
    """
    시도명+시군구명 → sigungu_code 매핑 딕셔너리 생성
    dim_admin_area 테이블에서 행정표준코드 5자리(sigungu_code) 사용
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT sido_nm, sigungu_nm, sigungu_code
        FROM dim_admin_area
        WHERE sido_nm IS NOT NULL AND sigungu_nm IS NOT NULL AND sigungu_code IS NOT NULL
    """)
    result = {}
    for row in cursor.fetchall():
        key = (row[0], row[1])
        result[key] = row[2]
    cursor.close()
    return result


# ============================================================
# 데이터 파싱 및 적재
# ============================================================
class GiupDataLoader:
    """기업체현황 데이터 로더"""

    def __init__(self):
        self.conn = get_db_connection()
        self.sigun_map = {}

    def init_tables(self, drop_existing: bool = True):
        """테이블 생성 (재적재 시 기존 테이블 삭제)"""
        cursor = self.conn.cursor()

        if drop_existing:
            logger.info("기존 테이블 삭제 및 재생성...")
            cursor.execute(CREATE_TABLES_SQL)

        self.conn.commit()
        cursor.close()

        # 시군구 코드 매핑 로드 (dim_admin_area 테이블 사용)
        self.sigun_map = get_sigun_code_map(self.conn)
        logger.info(f"시군구 코드 매핑 로드 완료 (dim_admin_area): {len(self.sigun_map)}건")

    def get_sigun_cd(self, sido_nm: str, sigun_nm: str) -> Optional[str]:
        """시도명+시군구명으로 시군구코드 조회"""
        return self.sigun_map.get((sido_nm, sigun_nm))

    def load_excel_file(self, filepath: Path) -> dict:
        """
        엑셀 파일 로드 및 파싱
        Returns: {sheet_name: DataFrame}
        """
        logger.info(f"파일 로드: {filepath.name}")
        xl = pd.ExcelFile(filepath)

        sheets = {}
        for sheet_name in xl.sheet_names:
            if sheet_name == '결측치현황':
                continue  # 결측치현황은 제외
            df = pd.read_excel(filepath, sheet_name=sheet_name)
            sheets[sheet_name] = df
            logger.debug(f"  - {sheet_name}: {len(df)}행")

        return sheets

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        DataFrame 전처리
        - 시도명, 시군구명 forward fill
        - 기준시기 forward fill 및 base_ym 변환
        """
        df = df.copy()

        # 시도명, 시군구명 forward fill
        if '시도명' in df.columns:
            df['시도명'] = df['시도명'].ffill()
        if '시군구명' in df.columns:
            df['시군구명'] = df['시군구명'].ffill()

        # 기준시기 forward fill
        if '기준시기' in df.columns:
            df['기준시기'] = df['기준시기'].ffill()
            # base_ym, data_type 생성
            df['base_ym'] = ''
            df['data_type'] = ''
            for idx, row in df.iterrows():
                base_ym, data_type = parse_base_ym(row['기준시기'])
                df.at[idx, 'base_ym'] = base_ym
                df.at[idx, 'data_type'] = data_type

        return df

    def insert_summary(self, cursor, base_ym: str, base_ym1: str, data_type: str,
                       sido_nm: str, sigun_nm: str) -> int:
        """메인 테이블에 INSERT 후 id 반환"""
        sigun_cd = self.get_sigun_cd(sido_nm, sigun_nm)

        cursor.execute("""
            INSERT INTO giup_summary (base_ym, base_ym1, data_type, sido_nm, sigun_nm, sigun_cd)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (base_ym, data_type, sido_nm, sigun_nm) DO UPDATE
            SET sigun_cd = EXCLUDED.sigun_cd
            RETURNING id
        """, (base_ym, base_ym1, data_type, sido_nm, sigun_nm, sigun_cd))

        return cursor.fetchone()[0]

    def insert_org_type(self, cursor, summary_id: int, row: pd.Series):
        """조직형태별 INSERT"""
        cursor.execute("""
            INSERT INTO giup_detail_org_type
            (summary_id, indiv_biz, corp, corp_other, non_corp, gov_local, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            summary_id,
            clean_value(row.get('개인사업체')),
            clean_value(row.get('회사법인')),
            clean_value(row.get('회사이외법인')),
            clean_value(row.get('비법인단체')),
            clean_value(row.get('국가지방자치단체')),
            clean_value(row.get('합계'))
        ))

    def insert_gender(self, cursor, summary_id: int, row: pd.Series):
        """대표자성별별 INSERT"""
        cursor.execute("""
            INSERT INTO giup_detail_gender
            (summary_id, blank, male, female, total)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            summary_id,
            clean_value(row.get('(공백)')),
            clean_value(row.get('남자')),
            clean_value(row.get('여자')),
            clean_value(row.get('합계'))
        ))

    def insert_status(self, cursor, summary_id: int, row: pd.Series):
        """폐업여부별 INSERT"""
        cursor.execute("""
            INSERT INTO giup_detail_status
            (summary_id, active, closed, total)
            VALUES (%s, %s, %s, %s)
        """, (
            summary_id,
            clean_value(row.get('영업중')),
            clean_value(row.get('폐업')),
            clean_value(row.get('합계'))
        ))

    def insert_industry(self, cursor, summary_id: int, row: pd.Series):
        """산업분류별 INSERT"""
        cursor.execute("""
            INSERT INTO giup_detail_industry
            (summary_id, blank, ind_a, ind_b, ind_c, ind_d, ind_e, ind_f, ind_g, ind_h, ind_i,
             ind_j, ind_k, ind_l, ind_m, ind_n, ind_o, ind_p, ind_q, ind_r, ind_s, ind_t, ind_u, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            summary_id,
            clean_value(row.get('(공백)')),
            clean_value(row.get('농업,임업,어업')),
            clean_value(row.get('광업')),
            clean_value(row.get('제조업')),
            clean_value(row.get('전기가스공급업')),
            clean_value(row.get('수도하수폐기물')),
            clean_value(row.get('건설업')),
            clean_value(row.get('도매및소매업')),
            clean_value(row.get('운수및창고업')),
            clean_value(row.get('숙박및음식점업')),
            clean_value(row.get('정보통신업')),
            clean_value(row.get('금융및보험업')),
            clean_value(row.get('부동산업')),
            clean_value(row.get('전문과학기술서비스')),
            clean_value(row.get('사업시설관리')),
            clean_value(row.get('공공행정')),
            clean_value(row.get('교육서비스업')),
            clean_value(row.get('보건사회복지')),
            clean_value(row.get('예술스포츠여가')),
            clean_value(row.get('협회및개인서비스')),
            clean_value(row.get('가구내고용활동')),
            clean_value(row.get('국제외국기관')),
            clean_value(row.get('합계'))
        ))

    def insert_age_group(self, cursor, summary_id: int, row: pd.Series):
        """연령그룹별 INSERT"""
        # 컬럼명이 파일마다 다를 수 있음 (~19세이하 vs ~19세)
        age_under_19 = row.get('~19세이하') if '~19세이하' in row.index else row.get('~19세')

        cursor.execute("""
            INSERT INTO giup_detail_age_group
            (summary_id, age_under_19, age_20_early, age_20_late, age_30_early, age_30_late,
             age_40_early, age_40_late, age_50_early, age_50_late, age_60_early, age_60_late,
             age_70_early, age_70_late, age_80_early, age_80_over, blank, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            summary_id,
            clean_value(age_under_19),
            clean_value(row.get('20대초')),
            clean_value(row.get('20대후')),
            clean_value(row.get('30대초')),
            clean_value(row.get('30대후')),
            clean_value(row.get('40대초')),
            clean_value(row.get('40대후')),
            clean_value(row.get('50대초')),
            clean_value(row.get('50대후')),
            clean_value(row.get('60대초')),
            clean_value(row.get('60대후')),
            clean_value(row.get('70대초')),
            clean_value(row.get('70대후')),
            clean_value(row.get('80대초')),
            clean_value(row.get('80대후이상')),
            clean_value(row.get('(공백)')),
            clean_value(row.get('합계'))
        ))

    def insert_main_biz(self, cursor, summary_id: int, row: pd.Series):
        """대표사업체별 INSERT"""
        cursor.execute("""
            INSERT INTO giup_detail_main_biz
            (summary_id, blank, total)
            VALUES (%s, %s, %s)
        """, (
            summary_id,
            clean_value(row.get('(공백)')),
            clean_value(row.get('합계'))
        ))

    def insert_corp_size(self, cursor, summary_id: int, row: pd.Series):
        """기업규모별 INSERT"""
        cursor.execute("""
            INSERT INTO giup_detail_corp_size
            (summary_id, blank, large_other, mid_large, mid, small, micro, excluded, sangchul, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            summary_id,
            clean_value(row.get('(공백)')),
            clean_value(row.get('기타대기업')),
            clean_value(row.get('중견기업')),
            clean_value(row.get('중기업')),
            clean_value(row.get('소기업')),
            clean_value(row.get('소상공인')),
            clean_value(row.get('기업규모판정제외사업자')),
            clean_value(row.get('상출기업')),
            clean_value(row.get('합계'))
        ))

    def insert_stats(self, cursor, summary_id: int, row: pd.Series):
        """수치형통계 INSERT"""
        def clean_numeric(val):
            if pd.isna(val) or val == '*':
                return None
            try:
                return float(val)
            except:
                return None

        cursor.execute("""
            INSERT INTO giup_detail_stats
            (summary_id, emp_count, emp_sum, emp_avg, emp_blank,
             sales_count, sales_sum, sales_avg, sales_blank,
             regular_count, regular_sum, regular_avg, regular_blank,
             temp_count, temp_sum, temp_avg, temp_blank)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            summary_id,
            clean_value(row.get('기업종사자수_건수')),
            clean_value(row.get('기업종사자수_합계')),
            clean_numeric(row.get('기업종사자수_평균')),
            clean_value(row.get('기업종사자수_공백건수')),
            clean_value(row.get('기업매출금액_건수')),
            clean_value(row.get('기업매출금액_합계')),
            clean_numeric(row.get('기업매출금액_평균')),
            clean_value(row.get('기업매출금액_공백건수')),
            clean_value(row.get('기업상용근로자수_건수')),
            clean_value(row.get('기업상용근로자수_합계')),
            clean_numeric(row.get('기업상용근로자수_평균')),
            clean_value(row.get('기업상용근로자수_공백건수')),
            clean_value(row.get('기업임시일용근로자수_건수')),
            clean_value(row.get('기업임시일용근로자수_합계')),
            clean_numeric(row.get('기업임시일용근로자수_평균')),
            clean_value(row.get('기업임시일용근로자수_공백건수'))
        ))

    def load_file(self, filepath: Path):
        """단일 파일 로드 및 DB 적재"""
        sheets = self.load_excel_file(filepath)
        cursor = self.conn.cursor()

        # 조직형태별 시트를 기준으로 summary 레코드 생성
        if '조직형태별' not in sheets:
            logger.error(f"조직형태별 시트가 없습니다: {filepath.name}")
            return

        org_df = self.process_dataframe(sheets['조직형태별'])

        # summary_id 캐시 (base_ym, data_type, sido_nm, sigun_nm) → summary_id
        summary_cache = {}

        for idx, row in org_df.iterrows():
            if pd.isna(row.get('시도명')) or pd.isna(row.get('시군구명')):
                continue

            key = (row['base_ym'], row['data_type'], row['시도명'], row['시군구명'])

            # summary INSERT
            summary_id = self.insert_summary(
                cursor,
                row['base_ym'],
                str(row['기준시기']),
                row['data_type'],
                row['시도명'],
                row['시군구명']
            )
            summary_cache[key] = summary_id

            # 조직형태별 INSERT
            self.insert_org_type(cursor, summary_id, row)

        logger.info(f"  - giup_summary: {len(summary_cache)}건")

        # 각 시트별 처리
        sheet_handlers = {
            '대표자성별별': self.insert_gender,
            '폐업여부별': self.insert_status,
            '산업분류별': self.insert_industry,
            '연령그룹별': self.insert_age_group,
            '대표사업체별': self.insert_main_biz,
            '기업규모별': self.insert_corp_size,
            '수치형통계': self.insert_stats,
        }

        for sheet_name, handler in sheet_handlers.items():
            if sheet_name not in sheets:
                continue

            df = self.process_dataframe(sheets[sheet_name])
            count = 0

            for idx, row in df.iterrows():
                if pd.isna(row.get('시도명')) or pd.isna(row.get('시군구명')):
                    continue

                key = (row['base_ym'], row['data_type'], row['시도명'], row['시군구명'])
                summary_id = summary_cache.get(key)

                if summary_id:
                    handler(cursor, summary_id, row)
                    count += 1

            logger.info(f"  - {sheet_name}: {count}건")

        self.conn.commit()
        cursor.close()

    def load_all_files(self):
        """data 폴더의 모든 집계표 파일 로드"""
        files = sorted(DATA_DIR.glob("(수정)집계표_*.xlsx"))

        logger.info(f"총 {len(files)}개 파일 발견")

        for filepath in files:
            self.load_file(filepath)

        logger.info("모든 파일 로드 완료")

    def close(self):
        """연결 종료"""
        self.conn.close()


# ============================================================
# 메인
# ============================================================
def main():
    """메인 실행"""
    logger.info("=" * 60)
    logger.info("기업체현황 집계표 DB 적재 시작")
    logger.info("=" * 60)

    loader = GiupDataLoader()

    try:
        # 테이블 초기화 (재적재 시 기존 데이터 삭제)
        loader.init_tables(drop_existing=True)

        # 모든 파일 로드
        loader.load_all_files()

        # 결과 확인
        cursor = loader.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM giup_summary")
        summary_count = cursor.fetchone()[0]

        cursor.execute("SELECT data_type, COUNT(*) FROM giup_summary GROUP BY data_type")
        type_counts = cursor.fetchall()

        logger.info("=" * 60)
        logger.info(f"적재 완료: giup_summary 총 {summary_count}건")
        for dt, cnt in type_counts:
            logger.info(f"  - {dt}: {cnt}건")
        logger.info("=" * 60)

        cursor.close()

    finally:
        loader.close()


if __name__ == '__main__':
    main()
