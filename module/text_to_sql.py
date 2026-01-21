# -*- coding: utf-8 -*-
"""
Text-to-SQL 모듈
================

자연어 질문을 SQL로 변환하는 LLM 기반 모듈입니다.
DB 스키마와 온톨로지 정보를 활용하여 정확한 SQL을 생성합니다.

사용 예시:
    >>> from module.text_to_sql import TextToSQL
    >>> t2s = TextToSQL()
    >>> sql = t2s.generate_sql("고령화율이 높은 시군구 10개")
    >>> print(sql)
"""

import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
from loguru import logger
from dotenv import load_dotenv

# .env 파일 로드
_module_dir = Path(__file__).parent
for _env_path in [_module_dir / '.env', _module_dir.parent / '.env']:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

from .db import get_db_connection
from .llm_client import LLMClient
from .ontology_loader import OntologyLoader


class SchemaExtractor:
    """DB 스키마 자동 추출 클래스"""

    def __init__(self):
        self._schema_cache = None

    def get_tables(self) -> pd.DataFrame:
        """모든 테이블과 뷰 목록 조회"""
        conn = get_db_connection()
        try:
            sql = """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_type, table_name
            """
            return pd.read_sql(sql, conn)
        finally:
            conn.close()

    def get_columns(self, table_name: str = None) -> pd.DataFrame:
        """테이블 컬럼 정보 조회"""
        conn = get_db_connection()
        try:
            sql = """
            SELECT
                c.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default
            FROM information_schema.columns c
            WHERE c.table_schema = 'public'
            """
            if table_name:
                sql += f" AND c.table_name = '{table_name}'"
            sql += " ORDER BY c.table_name, c.ordinal_position"
            return pd.read_sql(sql, conn)
        finally:
            conn.close()

    def get_schema_summary(self) -> str:
        """스키마 요약 문자열 생성 (LLM 프롬프트용)"""
        if self._schema_cache:
            return self._schema_cache

        tables = self.get_tables()
        columns = self.get_columns()

        lines = ["## 데이터베이스 스키마\n"]

        for _, row in tables.iterrows():
            tbl_name = row['table_name']
            tbl_type = "VIEW" if row['table_type'] == 'VIEW' else "TABLE"
            lines.append(f"\n### {tbl_name} ({tbl_type})")

            tbl_cols = columns[columns['table_name'] == tbl_name]
            for _, col in tbl_cols.iterrows():
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                lines.append(f"  - {col['column_name']}: {col['data_type']} ({nullable})")

        self._schema_cache = "\n".join(lines)
        return self._schema_cache

    def get_sample_data(self, table_name: str, limit: int = 3) -> pd.DataFrame:
        """테이블 샘플 데이터 조회"""
        conn = get_db_connection()
        try:
            sql = f"SELECT * FROM {table_name} LIMIT {limit}"
            return pd.read_sql(sql, conn)
        except Exception as e:
            logger.warning(f"샘플 데이터 조회 실패 ({table_name}): {e}")
            return pd.DataFrame()
        finally:
            conn.close()


class TextToSQL:
    """
    자연어를 SQL로 변환하는 클래스

    Args:
        llm_provider: 사용할 LLM ('claude' 또는 'solar')
        ontology_path: 온톨로지 MD 파일 경로 (단일 파일 모드, 하위 호환)
        ontology_content: 온톨로지 내용 문자열 (직접 전달 모드)
        domains: 추가 도메인 목록 ['finance', 'health', 'transport']
                 인구(population)는 항상 포함됨

    Examples:
        >>> t2s = TextToSQL()  # 인구만
        >>> t2s = TextToSQL(domains=['finance'])  # 인구 + 재정
        >>> t2s = TextToSQL(domains=['finance', 'health'])  # 인구 + 재정 + 보건
        >>> t2s = TextToSQL(ontology_content=loader.load())  # 온톨로지 내용 직접 전달
    """

    def __init__(
        self,
        llm_provider: str = None,
        ontology_path: str = None,
        ontology_content: str = None,
        domains: List[str] = None
    ):
        self.llm = LLMClient(provider=llm_provider)
        self.schema_extractor = SchemaExtractor()
        self.domains = domains or []

        # 온톨로지 로드 방식 결정 (우선순위: content > path > loader)
        if ontology_content:
            # 새 방식: 온톨로지 내용 직접 전달
            self.ontology_path = None
            self._ontology_loader = None
            self._ontology_content = ontology_content
        elif ontology_path:
            # 하위 호환: 단일 파일 경로가 주어진 경우
            self.ontology_path = Path(ontology_path)
            self._ontology_loader = None
            self._ontology_content = None
        else:
            # 기본 방식: OntologyLoader 사용
            self.ontology_path = None
            self._ontology_loader = OntologyLoader(domains=self.domains)
            self._ontology_content = None

        self._system_prompt = None

    def _load_ontology(self) -> str:
        """온톨로지 파일 로드"""
        if self._ontology_content:
            return self._ontology_content

        if self._ontology_loader:
            # 새 방식: OntologyLoader 사용
            self._ontology_content = self._ontology_loader.load()
            loaded = self._ontology_loader.get_loaded_domains()
            logger.info(f"온톨로지 로드 (domains: {loaded})")
        elif self.ontology_path and self.ontology_path.exists():
            # 하위 호환: 단일 파일
            self._ontology_content = self.ontology_path.read_text(encoding='utf-8')
            logger.info(f"온톨로지 로드: {self.ontology_path}")
        else:
            self._ontology_content = ""
            logger.warning(f"온톨로지 파일 없음")

        return self._ontology_content

    def get_loaded_domains(self) -> List[str]:
        """로드된 도메인 목록 반환"""
        if self._ontology_loader:
            return self._ontology_loader.get_loaded_domains()
        return ['population']  # 단일 파일 모드면 기본값

    def _build_system_prompt(self) -> str:
        """시스템 프롬프트 생성"""
        if self._system_prompt:
            return self._system_prompt

        ontology = self._load_ontology()

        self._system_prompt = f"""당신은 PostgreSQL 전문가입니다. 사용자의 자연어 질문을 SQL 쿼리로 변환합니다.

## 규칙
1. 반드시 유효한 PostgreSQL SQL만 출력하세요.
2. SQL 외의 설명은 하지 마세요.
3. SQL은 ```sql 코드블록 없이 순수 SQL만 출력하세요.
4. 최신 데이터 조회 시: WHERE base_ym = (SELECT MAX(base_ym) FROM 테이블명)
5. 정렬 시 NULL 처리: ORDER BY 컬럼 DESC NULLS LAST
6. 개수 미지정 시 기본 LIMIT 10
7. 시군구 단위 조회는 cache_sigungu_indicators 테이블 우선 사용

## ⚠️ base_ym (기준년월) 날짜 형식 (필수!)
- base_ym은 DATE 타입입니다 (문자열이 아님!)
- ❌ 잘못된 형식: WHERE base_ym = '202511' (에러 발생!)
- ✅ 올바른 형식: WHERE base_ym = '2025-11-01' (YYYY-MM-DD)
- 최신 데이터 조회 시: WHERE base_ym = (SELECT MAX(base_ym) FROM 테이블명)
- 특정 월 조회 시: WHERE base_ym = '2025-11-01' (해당 월의 1일)

## ⭐⭐⭐ 시군구 코드 규칙 (반드시 준수!) ⭐⭐⭐
"시군구" 단위 질문 시 하위시군구 합산이 기본. 아래 패턴 정확히 사용:

```sql
SELECT d.sigungu_nm as 시군구,
       SUM(c.total_pop) as 총인구,
       ROUND(SUM(c.elderly_pop)::numeric / NULLIF(SUM(c.total_pop), 0) * 100, 2) as 고령화율
FROM cache_sigungu_indicators c
JOIN (SELECT DISTINCT sigungu_code, sigungu_nm, sido_nm FROM dim_admin_area WHERE sigungu_nm IS NOT NULL) d
  ON LEFT(c.sigungu_code, 4) || '0' = d.sigungu_code
WHERE c.base_ym = (SELECT MAX(base_ym) FROM cache_sigungu_indicators)
  AND d.sido_nm = '경기도'  -- 시도 조건은 d 테이블에
GROUP BY LEFT(c.sigungu_code, 4), d.sigungu_nm
ORDER BY 고령화율 ASC
LIMIT 5;
```

주의사항:
- SELECT/ORDER BY에서 반드시 d.sigungu_nm 사용 (c.sigungu_nm 아님)
- 시도 조건은 d.sido_nm 사용
- dim_admin_area는 읍면동 단위라 DISTINCT 필수
- 예외: "하위시군구 구분", "자치구별"이면 cache 테이블 직접 조회

{ontology}

## 동적 스키마 정보
{self.schema_extractor.get_schema_summary()}
"""
        return self._system_prompt

    def generate_sql(self, question: str) -> Tuple[str, Optional[str]]:
        """
        자연어 질문을 SQL로 변환

        Args:
            question: 사용자 질문

        Returns:
            (SQL 문자열, 에러 메시지 또는 None)
        """
        if not question or not question.strip():
            return "", "질문을 입력해주세요."

        try:
            system_prompt = self._build_system_prompt()
            user_message = f"다음 질문을 SQL로 변환해주세요:\n\n{question}"

            sql = self.llm.chat(user_message, system_prompt)

            # SQL 정리 (코드블록 제거 등)
            sql = self._clean_sql(sql)

            logger.info(f"생성된 SQL: {sql}")
            return sql, None

        except Exception as e:
            logger.error(f"SQL 생성 실패: {e}")
            return "", str(e)

    def _clean_sql(self, sql: str) -> str:
        """SQL 문자열 정리 - LLM이 추가 설명을 포함해도 SQL만 추출"""
        import re

        sql = sql.strip()

        # 방법 1: ```sql...``` 코드블록에서 SQL만 추출
        sql_block_pattern = r'```sql\s*(.*?)\s*```'
        match = re.search(sql_block_pattern, sql, re.DOTALL | re.IGNORECASE)
        if match:
            sql = match.group(1).strip()
            return sql

        # 방법 2: ```...``` 일반 코드블록에서 추출
        code_block_pattern = r'```\s*(.*?)\s*```'
        match = re.search(code_block_pattern, sql, re.DOTALL)
        if match:
            sql = match.group(1).strip()
            return sql

        # 방법 3: 코드블록 없이 시작하는 경우, 첫 번째 ; 까지만 추출
        # (LLM이 SQL 이후에 설명을 추가하는 경우 대응)
        if sql.startswith("SELECT") or sql.startswith("select"):
            # 마지막 세미콜론 이후의 모든 내용 제거
            if ';' in sql:
                # 마지막 세미콜론 위치 찾기
                last_semicolon = sql.rfind(';')
                sql = sql[:last_semicolon + 1]

        # 기존 방식 - 코드블록 마커만 제거
        if sql.startswith("```sql"):
            sql = sql[6:]
        if sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]

        return sql.strip()

    def execute_sql(self, sql: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """SQL 실행 및 결과 반환"""
        if not sql:
            return None, "SQL이 비어있습니다."

        conn = get_db_connection()
        try:
            df = pd.read_sql(sql, conn)
            return df, None
        except Exception as e:
            logger.error(f"SQL 실행 오류: {e}")
            return None, str(e)
        finally:
            conn.close()

    def ask(self, question: str) -> Dict[str, Any]:
        """
        질문에 대한 전체 처리 (SQL 생성 + 실행 + 결과)
        SQL 실행 실패 시 LLM이 직접 분석하여 답변

        Args:
            question: 사용자 질문

        Returns:
            {
                'question': 원본 질문,
                'sql': 생성된 SQL,
                'data': 결과 DataFrame,
                'answer': LLM 자연어 답변 (SQL 실패 시),
                'error': 에러 메시지 (없으면 None),
                'provider': 사용된 LLM
            }
        """
        result = {
            'question': question,
            'sql': None,
            'data': None,
            'answer': None,
            'error': None,
            'provider': self.llm.get_provider_name()
        }

        # 1. SQL 생성
        sql, error = self.generate_sql(question)
        if error:
            result['error'] = error
            return result

        result['sql'] = sql

        # 2. SQL 실행
        df, error = self.execute_sql(sql)
        if error:
            # SQL 실행 실패 시 LLM에게 직접 분석 요청
            logger.warning(f"SQL 실행 실패, LLM 분석으로 전환: {error}")
            answer = self._analyze_with_llm(question)
            result['answer'] = answer
            result['sql'] = None  # 실패한 SQL은 표시하지 않음
            return result

        result['data'] = df
        return result

    def _analyze_with_llm(self, question: str) -> str:
        """
        SQL로 처리 불가능한 질문에 대해 LLM이 직접 분석

        기본 데이터를 가져와서 LLM에게 분석을 요청합니다.
        요약 통계와 전체 시군구 데이터를 활용하여 정확한 분석을 제공합니다.
        """
        try:
            conn = get_db_connection()

            # 1. 사용 가능한 모든 월 확인
            months_sql = """
            SELECT DISTINCT base_ym
            FROM cache_sigungu_indicators
            ORDER BY base_ym DESC
            """
            df_months = pd.read_sql(months_sql, conn)
            # datetime.date 객체를 문자열로 변환
            # SQL용 (YYYY-MM-DD), 표시용 (YYYYMM) 두 형식 준비
            available_months_sql = []  # SQL WHERE절용 (YYYY-MM-DD)
            available_months_display = []  # 표시용 (YYYYMM)
            for m in df_months['base_ym'].tolist():
                if hasattr(m, 'strftime'):
                    available_months_sql.append(m.strftime('%Y-%m-%d'))
                    available_months_display.append(m.strftime('%Y%m'))
                else:
                    # 문자열인 경우 그대로 사용
                    available_months_sql.append(str(m))
                    available_months_display.append(str(m).replace('-', '')[:6])

            # 2. 최신 2개월 데이터 (전체 시군구)
            latest_month_sql = available_months_sql[0] if available_months_sql else None
            prev_month_sql = available_months_sql[1] if len(available_months_sql) > 1 else None
            latest_month_display = available_months_display[0] if available_months_display else None
            prev_month_display = available_months_display[1] if len(available_months_display) > 1 else None

            # 3. 최신월 전체 데이터
            current_sql = f"""
            SELECT sido_nm, sigungu_nm, total_pop, elderly_ratio,
                   youth_ratio, single_ratio, aging_index, sex_ratio,
                   household_cnt, elderly_pop, base_ym
            FROM cache_sigungu_indicators
            WHERE base_ym = '{latest_month_sql}'
            ORDER BY sido_nm, sigungu_nm
            """
            df_current = pd.read_sql(current_sql, conn)

            # 4. 전월 데이터 (있는 경우)
            df_prev = None
            if prev_month_sql:
                prev_sql = f"""
                SELECT sido_nm, sigungu_nm, total_pop, elderly_ratio,
                       youth_ratio, single_ratio, aging_index, sex_ratio,
                       household_cnt, elderly_pop, base_ym
                FROM cache_sigungu_indicators
                WHERE base_ym = '{prev_month_sql}'
                ORDER BY sido_nm, sigungu_nm
                """
                df_prev = pd.read_sql(prev_sql, conn)

            # 5. 시도별 요약 통계 (최신월)
            summary_sql = f"""
            SELECT sido_nm,
                   COUNT(*) as sigungu_cnt,
                   SUM(total_pop) as total_pop_sum,
                   AVG(elderly_ratio) as avg_elderly_ratio,
                   AVG(youth_ratio) as avg_youth_ratio,
                   AVG(single_ratio) as avg_single_ratio,
                   SUM(household_cnt) as total_households
            FROM cache_sigungu_indicators
            WHERE base_ym = '{latest_month_sql}'
            GROUP BY sido_nm
            ORDER BY total_pop_sum DESC
            """
            df_summary = pd.read_sql(summary_sql, conn)
            conn.close()

            # 프롬프트 구성
            current_summary = df_current.to_string()
            sido_summary = df_summary.to_string()

            prompt = f"""사용자 질문: {question}

## 데이터 현황
- 사용 가능한 월: {', '.join(available_months_display[:6])}{'...' if len(available_months_display) > 6 else ''}
- 최신 기준월: {latest_month_display}
- 전월: {prev_month_display if prev_month_display else '없음'}
- 전체 시군구 수: {len(df_current)}개

## 시도별 요약 통계 (최신월: {latest_month_display})
{sido_summary}

## 전체 시군구 데이터 (최신월: {latest_month_display})
{current_summary}
"""

            # 전월 데이터가 있으면 비교 정보 추가
            if df_prev is not None and not df_prev.empty:
                # 전월 대비 변화량 계산 (주요 지표)
                merged = df_current.merge(
                    df_prev[['sido_nm', 'sigungu_nm', 'total_pop', 'elderly_ratio']],
                    on=['sido_nm', 'sigungu_nm'],
                    suffixes=('_현재', '_전월'),
                    how='left'
                )
                merged['인구변화'] = merged['total_pop_현재'] - merged['total_pop_전월']
                merged['고령화율변화'] = merged['elderly_ratio_현재'] - merged['elderly_ratio_전월']

                # 변화가 큰 지역 Top 10
                top_increase = merged.nlargest(10, '인구변화')[['sido_nm', 'sigungu_nm', '인구변화', '고령화율변화']]
                top_decrease = merged.nsmallest(10, '인구변화')[['sido_nm', 'sigungu_nm', '인구변화', '고령화율변화']]

                prompt += f"""

## 전월({prev_month_display}) 대비 변화

### 인구 증가 상위 10개 시군구
{top_increase.to_string()}

### 인구 감소 상위 10개 시군구
{top_decrease.to_string()}
"""

            prompt += """

## 근거 기반 인사이트 가이드라인

### 핵심 원칙: 데이터가 말하게 하되, 의미를 부여하라

### 1. 수치 + 맥락 = 인사이트
- ❌ 수치만: "경북 1.22%, 전국 0.77%입니다" (So what?)
- ❌ 근거 없는 판단: "경북이 양호합니다"
- ✅ 근거 기반 인사이트: "경북은 전국 평균(0.77%) 대비 1.6배 높은 1.22%로, 초고령 인구 비중이 큰 편"

### 2. 비교 기준 명확화
- 비교할 때는 반드시 기준 제시 (전국, 시도 내, 유사 지역 대비)
- 순위뿐 아니라 전체 분포에서의 위치도 설명
- 예: "전국 TOP 50 중 11개 지역이 경북 소재로, 시도별 최다"

### 3. 정책적 시사점 도출
- 단순 현황 나열이 아닌, 실행 가능한 인사이트 제공
- 예: "90세 이상 비율이 전국 대비 0.45%p 높아 초고령자 돌봄 인프라 확충이 시급"

### 4. 판단의 근거 명시
- ✅ 데이터로 확인된 사실 → 단정적 표현 OK
  예: "경북은 고령화 상위 지역이다" (TOP 50 중 11개 = 팩트)
- ⚠️ 추론이 필요한 경우 → 가능성으로 표현
  예: "농촌 지역 집중은 청년층 유출과 관련될 수 있다"

### 5. 다면적 해석 (필요시)
- 하나의 지표가 여러 의미를 가질 때만 양면 제시
- 모든 분석에 양면 해석을 넣을 필요 없음

### 출력 형식
1. **핵심 인사이트**: 가장 중요한 발견 (수치 + 의미)
2. **상세 분석**: 비교, 순위, 분포 등 근거 데이터
3. **시사점/제언**: 정책적 함의나 주의할 점
"""

            response = self.llm.chat(prompt)
            return response

        except Exception as e:
            logger.error(f"LLM 분석 실패: {e}")
            return f"분석 중 오류가 발생했습니다: {str(e)}"

    def get_available_providers(self) -> List[str]:
        """사용 가능한 LLM 제공자 목록"""
        return LLMClient.get_available_providers()

    def switch_provider(self, provider: str):
        """LLM 제공자 변경"""
        self.llm = LLMClient(provider=provider)
        logger.info(f"LLM 제공자 변경: {provider}")


def generate_natural_response(question: str, df: pd.DataFrame, llm_provider: str = None) -> str:
    """
    SQL 결과를 자연어 응답으로 변환

    Args:
        question: 원본 질문
        df: SQL 실행 결과 DataFrame
        llm_provider: LLM 제공자

    Returns:
        자연어 응답 문자열
    """
    if df is None or df.empty:
        return "조회 결과가 없습니다."

    try:
        llm = LLMClient(provider=llm_provider)

        # DataFrame을 문자열로 변환
        data_str = df.head(20).to_string()

        prompt = f"""사용자 질문: {question}

조회 결과:
{data_str}

## 근거 기반 인사이트 가이드라인
1. 핵심 인사이트를 2-3문장으로 요약 (수치 + 의미)
2. 비교 시 기준 명시 (전국 대비, 평균 대비 등)
3. 데이터로 확인된 사실은 명확히 판단해도 됨
4. 가능하면 정책적 시사점이나 함의 제시
5. 추론이 필요한 부분만 "~일 수 있다"로 표현"""

        response = llm.chat(prompt)
        return response

    except Exception as e:
        logger.error(f"자연어 응답 생성 실패: {e}")
        return f"결과: {len(df)}건 조회됨"
