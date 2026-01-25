"""
code_master.xlsx를 데이터베이스에 로드하는 스크립트

사용법:
    python load_code_master.py                    # 기본 (증분 업데이트)
    python load_code_master.py --replace          # 테이블 데이터 전체 교체
    python load_code_master.py --file path.xlsx   # 특정 파일 지정
"""

import sys
import argparse
from pathlib import Path
import pandas as pd

# 상위 디렉토리를 Python 경로에 추가 (module 폴더 접근용)
sys.path.insert(0, str(Path(__file__).parent.parent))

from module.db import get_db_engine, get_postgres_config
import psycopg2
from loguru import logger


class CodeMasterLoader:
    """code_master.xlsx 로더 클래스"""

    def __init__(self, excel_path=None):
        """
        초기화

        Args:
            excel_path: Excel 파일 경로 (기본값: codedata/code_master.xlsx)
        """
        self.engine = get_db_engine()
        self.config = get_postgres_config()

        if excel_path:
            self.excel_path = Path(excel_path)
        else:
            self.excel_path = Path(__file__).parent.parent / 'codedata' / 'code_master.xlsx'

        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel 파일을 찾을 수 없습니다: {self.excel_path}")

    def load_excel(self):
        """Excel 파일 로드"""
        logger.info(f"Excel 파일 로드: {self.excel_path}")

        xls = pd.ExcelFile(self.excel_path)
        sheets = {}

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            sheets[sheet_name] = df
            logger.info(f"  - {sheet_name}: {len(df)}개 행")

        return sheets

    def replace_table(self, table_name, df):
        """
        테이블 데이터 전체 교체 (TRUNCATE + INSERT)

        Args:
            table_name: 테이블명
            df: 데이터프레임
        """
        conn = psycopg2.connect(**self.config)
        cursor = conn.cursor()

        try:
            # 테이블 비우기
            cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
            logger.info(f"테이블 {table_name} 비움")

            # 데이터 삽입
            columns = df.columns.tolist()
            placeholders = ', '.join(['%s'] * len(columns))
            cols_str = ', '.join(columns)

            insert_query = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"

            for _, row in df.iterrows():
                values = [None if pd.isna(v) else v for v in row.values]
                cursor.execute(insert_query, values)

            conn.commit()
            logger.info(f"테이블 {table_name}에 {len(df)}개 행 삽입 완료")

        except Exception as e:
            conn.rollback()
            logger.error(f"테이블 {table_name} 교체 실패: {e}")
            raise

        finally:
            cursor.close()
            conn.close()

    def upsert_table(self, table_name, df, key_columns):
        """
        테이블 데이터 증분 업데이트 (UPSERT)

        Args:
            table_name: 테이블명
            df: 데이터프레임
            key_columns: 키 컬럼 리스트 (중복 체크용)
        """
        conn = psycopg2.connect(**self.config)
        cursor = conn.cursor()

        try:
            columns = df.columns.tolist()
            update_columns = [c for c in columns if c not in key_columns]

            inserted = 0
            updated = 0

            for _, row in df.iterrows():
                values = [None if pd.isna(v) else v for v in row.values]
                row_dict = dict(zip(columns, values))

                # 키 조건으로 기존 데이터 확인
                key_conditions = ' AND '.join([f"{k} = %s" for k in key_columns])
                key_values = [row_dict[k] for k in key_columns]

                cursor.execute(
                    f"SELECT id FROM {table_name} WHERE {key_conditions}",
                    key_values
                )
                existing = cursor.fetchone()

                if existing:
                    # 업데이트
                    set_clause = ', '.join([f"{c} = %s" for c in update_columns])
                    set_clause += ", updated_at = CURRENT_TIMESTAMP"
                    update_values = [row_dict[c] for c in update_columns]
                    update_values.append(existing[0])

                    cursor.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE id = %s",
                        update_values
                    )
                    updated += 1
                else:
                    # 삽입
                    placeholders = ', '.join(['%s'] * len(columns))
                    cols_str = ', '.join(columns)

                    cursor.execute(
                        f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})",
                        values
                    )
                    inserted += 1

            conn.commit()
            logger.info(f"테이블 {table_name}: {inserted}개 삽입, {updated}개 업데이트")

        except Exception as e:
            conn.rollback()
            logger.error(f"테이블 {table_name} 업데이트 실패: {e}")
            raise

        finally:
            cursor.close()
            conn.close()

    def load(self, replace=False):
        """
        Excel을 데이터베이스에 로드

        Args:
            replace: True면 전체 교체, False면 증분 업데이트
        """
        sheets = self.load_excel()

        # age_group 시트 → code_age_group 테이블
        if 'age_group' in sheets:
            df = sheets['age_group']
            if replace:
                self.replace_table('code_age_group', df)
            else:
                self.upsert_table('code_age_group', df, ['category', 'code'])

        # indicator 시트 → code_indicator 테이블
        if 'indicator' in sheets:
            df = sheets['indicator']
            if replace:
                self.replace_table('code_indicator', df)
            else:
                self.upsert_table('code_indicator', df, ['category', 'column_name'])

        logger.info("Excel 로드 완료!")

    def compare_with_db(self):
        """
        Excel과 DB 비교

        Returns:
            dict: 비교 결과
        """
        sheets = self.load_excel()
        result = {}

        # age_group 비교
        if 'age_group' in sheets:
            excel_df = sheets['age_group']
            db_df = pd.read_sql("""
                SELECT category, category_name, code, code_name, column_name,
                       age_start, age_end, sort_order, is_active
                FROM code_age_group
                ORDER BY sort_order, id
            """, self.engine)

            excel_codes = set(zip(excel_df['category'], excel_df['code']))
            db_codes = set(zip(db_df['category'], db_df['code']))

            result['age_group'] = {
                'excel_count': len(excel_df),
                'db_count': len(db_df),
                'only_in_excel': excel_codes - db_codes,
                'only_in_db': db_codes - excel_codes
            }

        # indicator 비교
        if 'indicator' in sheets:
            excel_df = sheets['indicator']
            db_df = pd.read_sql("""
                SELECT category, category_name, column_name, display_name, description,
                       numerator, denominator, multiplier, decimal_places, data_type,
                       sort_order, is_active
                FROM code_indicator
                ORDER BY sort_order, id
            """, self.engine)

            excel_codes = set(zip(excel_df['category'], excel_df['column_name']))
            db_codes = set(zip(db_df['category'], db_df['column_name']))

            result['indicator'] = {
                'excel_count': len(excel_df),
                'db_count': len(db_df),
                'only_in_excel': excel_codes - db_codes,
                'only_in_db': db_codes - excel_codes
            }

        return result


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='code_master.xlsx를 데이터베이스에 로드')
    parser.add_argument('--file', '-f', type=str, help='Excel 파일 경로')
    parser.add_argument('--replace', '-r', action='store_true',
                        help='테이블 데이터 전체 교체 (기본값: 증분 업데이트)')
    parser.add_argument('--compare', '-c', action='store_true',
                        help='Excel과 DB 비교만 수행')

    args = parser.parse_args()

    try:
        loader = CodeMasterLoader(args.file)

        if args.compare:
            # 비교 모드
            result = loader.compare_with_db()

            for table, info in result.items():
                print(f"\n=== {table} ===")
                print(f"Excel: {info['excel_count']}개, DB: {info['db_count']}개")

                if info['only_in_excel']:
                    print(f"Excel에만 있는 항목: {len(info['only_in_excel'])}개")
                    for item in list(info['only_in_excel'])[:5]:
                        print(f"  - {item}")

                if info['only_in_db']:
                    print(f"DB에만 있는 항목: {len(info['only_in_db'])}개")
                    for item in list(info['only_in_db'])[:5]:
                        print(f"  - {item}")

                if not info['only_in_excel'] and not info['only_in_db']:
                    print("Excel과 DB가 동일합니다.")

        else:
            # 로드 모드
            mode = "전체 교체" if args.replace else "증분 업데이트"
            logger.info(f"로드 모드: {mode}")
            loader.load(replace=args.replace)

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
