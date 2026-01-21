# -*- coding: utf-8 -*-
"""
온톨로지 로더 모듈
==================

여러 도메인의 온톨로지를 조합하여 로드하는 모듈입니다.

주요 기능:
1. 호출 파일 위치에 따른 기본 도메인 자동 감지
2. 질문 내용에서 도메인 키워드 감지하여 추가 로드
3. 공통 온톨로지는 항상 포함

사용 예시:
    >>> from module.ontology_loader import OntologyLoader
    >>>
    >>> # 자동 감지 (호출 위치 + 질문 분석)
    >>> loader = OntologyLoader.auto_detect(__file__, "인구와 복지 비교해줘")
    >>> ontology = loader.load()
    >>>
    >>> # 수동 지정
    >>> loader = OntologyLoader(domains=['01_population', '02_welfare'])
    >>> ontology = loader.load()
"""

import re
from pathlib import Path
from typing import List, Optional, Dict, Set
from loguru import logger


class OntologyLoader:
    """
    모듈형 온톨로지 로더

    호출 파일 위치와 질문 내용을 분석하여 필요한 도메인 온톨로지를 자동으로 로드합니다.
    공통 온톨로지(common_ontology.md)는 항상 포함됩니다.
    """

    # 프로젝트 루트 경로
    BASE_DIR = Path(__file__).parent.parent

    # 도메인 설정: 폴더명 → (표시명, 키워드 목록)
    # 새 도메인 추가 시 여기에 등록
    DOMAIN_CONFIG: Dict[str, Dict] = {
        '01_population': {
            'name': '인구통계',
            'keywords': ['인구', '고령화', '유소년', '세대', '가구', '1인가구', '노인', '청년',
                        '생산인구', '인구수', '주민등록', '성비', '노령화', '소멸'],
            'always_include': True,  # 항상 포함되는 기본 도메인
        },
        '02_welfare': {
            'name': '복지',
            'keywords': ['복지', '기초생활', '수급자', '장애인', '노인복지', '아동복지',
                        '사회복지', '돌봄', '요양', '연금'],
            'always_include': False,
        },
        '02_기업체현황': {
            'name': '기업체현황',
            'keywords': ['기업', '사업체', '사업자', '법인', '개인사업', '종사자', '제조업',
                        '도소매', '서비스업', '산업', '폐업', '창업', '조직형태', '대표자',
                        'SBR', '기업통계', '영업', '업종'],
            'always_include': False,
        },
        '03_economy': {
            'name': '경제',
            'keywords': ['경제', '고용', '실업', '취업', 'GRDP', '소득', '임금', '사업체',
                        '창업', '폐업', '산업'],
            'always_include': False,
        },
        '04_health': {
            'name': '보건의료',
            'keywords': ['보건', '의료', '병원', '의원', '건강', '질병', '사망', '출생',
                        '진료', '약국', '응급'],
            'always_include': False,
        },
        '05_education': {
            'name': '교육',
            'keywords': ['교육', '학교', '학생', '학원', '유치원', '초등', '중학', '고등',
                        '대학', '진학', '취학'],
            'always_include': False,
        },
        '06_environment': {
            'name': '환경',
            'keywords': ['환경', '대기', '수질', '폐기물', '재활용', '미세먼지', '오염'],
            'always_include': False,
        },
        '07_transport': {
            'name': '교통',
            'keywords': ['교통', '도로', '버스', '지하철', '철도', '자동차', '주차', '통행'],
            'always_include': False,
        },
        '08_safety': {
            'name': '안전',
            'keywords': ['안전', '범죄', '사고', '재난', '화재', '112', '119', '치안'],
            'always_include': False,
        },
        '09_culture': {
            'name': '문화관광',
            'keywords': ['문화', '관광', '여행', '축제', '공연', '박물관', '도서관', '체육'],
            'always_include': False,
        },
        '10_housing': {
            'name': '주택',
            'keywords': ['주택', '아파트', '주거', '부동산', '공시지가', '건축', '빈집'],
            'always_include': False,
        },
    }

    def __init__(
        self,
        domains: List[str] = None,
        include_common: bool = True,
        caller_file: str = None
    ):
        """
        Args:
            domains: 로드할 도메인 목록 (예: ['01_population', '02_welfare'])
            include_common: 공통 온톨로지 포함 여부 (기본 True)
            caller_file: 호출자 파일 경로 (__file__)
        """
        self.domains = set(domains) if domains else set()
        self.include_common = include_common
        self.caller_file = caller_file

        self._loaded_content = None
        self._loaded_files = []

        # 항상 포함되는 도메인 추가
        for domain, config in self.DOMAIN_CONFIG.items():
            if config.get('always_include', False):
                self.domains.add(domain)

    @classmethod
    def auto_detect(
        cls,
        caller_file: str,
        question: str = None,
        extra_domains: List[str] = None
    ) -> 'OntologyLoader':
        """
        호출 파일 위치와 질문 내용을 분석하여 자동으로 도메인 감지

        Args:
            caller_file: 호출하는 파일의 __file__
            question: 사용자 질문 (도메인 키워드 분석용)
            extra_domains: 추가로 포함할 도메인 목록

        Returns:
            설정된 OntologyLoader 인스턴스

        Examples:
            # 데이터콩.py에서 호출
            loader = OntologyLoader.auto_detect(__file__, user_question)
            ontology = loader.load()
        """
        detected_domains = set()

        # 1. 호출 파일 위치에서 도메인 감지
        if caller_file:
            caller_path = Path(caller_file)
            for part in caller_path.parts:
                if part in cls.DOMAIN_CONFIG:
                    detected_domains.add(part)
                    logger.debug(f"파일 위치에서 도메인 감지: {part}")
                    break

        # 2. 질문 내용에서 도메인 키워드 감지
        if question:
            question_lower = question.lower()
            for domain, config in cls.DOMAIN_CONFIG.items():
                keywords = config.get('keywords', [])
                for keyword in keywords:
                    if keyword in question_lower:
                        detected_domains.add(domain)
                        logger.debug(f"질문에서 도메인 감지: {domain} (키워드: {keyword})")
                        break

        # 3. 추가 도메인 포함
        if extra_domains:
            detected_domains.update(extra_domains)

        # 4. 항상 포함되는 도메인 추가
        for domain, config in cls.DOMAIN_CONFIG.items():
            if config.get('always_include', False):
                detected_domains.add(domain)

        logger.info(f"감지된 도메인: {list(detected_domains)}")

        return cls(
            domains=list(detected_domains),
            caller_file=caller_file
        )

    @classmethod
    def from_question(cls, question: str) -> 'OntologyLoader':
        """
        질문 내용만으로 도메인 감지

        Args:
            question: 사용자 질문

        Returns:
            설정된 OntologyLoader 인스턴스
        """
        return cls.auto_detect(caller_file=None, question=question)

    def add_domain(self, domain: str) -> 'OntologyLoader':
        """도메인 추가 (체이닝 지원)"""
        if domain in self.DOMAIN_CONFIG:
            self.domains.add(domain)
        else:
            logger.warning(f"등록되지 않은 도메인: {domain}")
        return self

    def add_domains_from_question(self, question: str) -> 'OntologyLoader':
        """질문에서 추가 도메인 감지하여 추가 (체이닝 지원)"""
        question_lower = question.lower()
        for domain, config in self.DOMAIN_CONFIG.items():
            keywords = config.get('keywords', [])
            for keyword in keywords:
                if keyword in question_lower:
                    self.domains.add(domain)
                    break
        return self

    def load(self) -> str:
        """
        선택된 도메인들의 온톨로지를 조합하여 반환

        Returns:
            조합된 온톨로지 문자열
        """
        contents = []
        self._loaded_files = []

        # 1. 공통 온톨로지 (항상 먼저)
        if self.include_common:
            common_path = self.BASE_DIR / "module" / "ontology" / "common_ontology.md"
            common_content = self._load_file(common_path)
            if common_content:
                contents.append(f"# [공통 온톨로지]\n\n{common_content}")
                self._loaded_files.append("module/ontology/common_ontology.md")

        # 2. 각 도메인 온톨로지 로드 (정렬된 순서)
        for domain in sorted(self.domains):
            if domain not in self.DOMAIN_CONFIG:
                logger.warning(f"등록되지 않은 도메인 건너뜀: {domain}")
                continue

            domain_name = self.DOMAIN_CONFIG[domain]['name']
            domain_ontology_dir = self.BASE_DIR / domain / "ontology"

            if not domain_ontology_dir.exists():
                logger.warning(f"온톨로지 폴더 없음: {domain}/ontology")
                continue

            # 해당 도메인의 모든 .md 파일 로드
            md_files = sorted(domain_ontology_dir.glob("*.md"))
            for md_file in md_files:
                content = self._load_file(md_file)
                if content:
                    contents.append(f"\n\n# [{domain_name}] {md_file.name}\n\n{content}")
                    self._loaded_files.append(f"{domain}/ontology/{md_file.name}")

        # 3. 합치기
        self._loaded_content = "\n\n---\n\n".join(contents)

        # 4. 로드 결과 로깅
        logger.info(f"온톨로지 로드 완료: {self._loaded_files}")

        # 5. 토큰 수 경고
        estimated_tokens = len(self._loaded_content) // 4
        if estimated_tokens > 50000:
            logger.warning(f"온톨로지 토큰 수 많음: 약 {estimated_tokens:,}개")
        else:
            logger.debug(f"온톨로지 토큰 수: 약 {estimated_tokens:,}개")

        return self._loaded_content

    def _load_file(self, path: Path) -> Optional[str]:
        """파일 내용 로드"""
        if path.exists():
            try:
                return path.read_text(encoding='utf-8')
            except Exception as e:
                logger.error(f"온톨로지 파일 로드 실패 ({path}): {e}")
        return None

    def get_loaded_files(self) -> List[str]:
        """로드된 파일 목록 반환"""
        return self._loaded_files.copy()

    def get_loaded_domains(self) -> List[str]:
        """로드된 도메인 목록 반환"""
        return sorted(list(self.domains))

    def get_domain_names(self) -> List[str]:
        """로드된 도메인의 한글명 목록 반환"""
        return [
            self.DOMAIN_CONFIG[d]['name']
            for d in sorted(self.domains)
            if d in self.DOMAIN_CONFIG
        ]

    @classmethod
    def get_available_domains(cls) -> Dict[str, str]:
        """사용 가능한 도메인 목록 반환 {폴더명: 한글명}"""
        return {
            domain: config['name']
            for domain, config in cls.DOMAIN_CONFIG.items()
        }

    @classmethod
    def get_existing_domains(cls) -> List[str]:
        """실제 폴더가 존재하는 도메인 목록 반환"""
        existing = []
        for domain in cls.DOMAIN_CONFIG.keys():
            ontology_path = cls.BASE_DIR / domain / "ontology"
            if ontology_path.exists():
                existing.append(domain)
        return existing

    @classmethod
    def get_domain_info(cls) -> Dict:
        """온톨로지 현황 정보 반환"""
        info = {
            "registered_domains": cls.get_available_domains(),
            "existing_domains": cls.get_existing_domains(),
            "common_exists": (cls.BASE_DIR / "module" / "ontology" / "common_ontology.md").exists(),
            "details": {}
        }

        for domain in info["existing_domains"]:
            domain_dir = cls.BASE_DIR / domain / "ontology"
            files = list(domain_dir.glob("*.md"))
            info["details"][domain] = {
                "name": cls.DOMAIN_CONFIG[domain]['name'],
                "files": [f.name for f in files],
                "total_size_kb": round(sum(f.stat().st_size for f in files) / 1024, 2),
                "keywords": cls.DOMAIN_CONFIG[domain].get('keywords', [])[:5]  # 상위 5개만
            }

        return info


# =============================================================================
# 편의 함수들
# =============================================================================

def load_ontology(
    domains: List[str] = None,
    question: str = None,
    caller_file: str = None
) -> str:
    """
    온톨로지 로드 편의 함수

    Args:
        domains: 로드할 도메인 목록 (None이면 자동 감지)
        question: 사용자 질문 (도메인 키워드 분석용)
        caller_file: 호출자 파일 경로 (__file__)

    Returns:
        조합된 온톨로지 문자열

    Examples:
        # 가장 간단한 사용법 - 질문으로 자동 감지
        ontology = load_ontology(question="인구와 복지 현황 알려줘")

        # 명시적 도메인 지정
        ontology = load_ontology(domains=["01_population", "02_welfare"])

        # 파일 위치 + 질문 조합
        ontology = load_ontology(caller_file=__file__, question=user_question)
    """
    if domains:
        # 명시적 도메인 지정
        loader = OntologyLoader(domains=domains)
    elif caller_file or question:
        # 자동 감지
        loader = OntologyLoader.auto_detect(
            caller_file=caller_file,
            question=question
        )
    else:
        # 기본 도메인만 (always_include=True인 것들)
        loader = OntologyLoader()

    return loader.load()


def detect_domains_from_question(question: str) -> List[str]:
    """
    질문에서 관련 도메인 감지

    Args:
        question: 사용자 질문

    Returns:
        감지된 도메인 목록

    Examples:
        >>> detect_domains_from_question("인구와 복지 비교해줘")
        ['01_population', '02_welfare']
    """
    detected = set()
    question_lower = question.lower()

    for domain, config in OntologyLoader.DOMAIN_CONFIG.items():
        keywords = config.get('keywords', [])
        for keyword in keywords:
            if keyword in question_lower:
                detected.add(domain)
                break

    # 항상 포함되는 도메인 추가
    for domain, config in OntologyLoader.DOMAIN_CONFIG.items():
        if config.get('always_include', False):
            detected.add(domain)

    return sorted(list(detected))


def get_ontology_status() -> str:
    """온톨로지 현황을 문자열로 반환"""
    info = OntologyLoader.get_domain_info()

    lines = ["=" * 50, "온톨로지 현황", "=" * 50, ""]

    # 공통 온톨로지
    common_status = "있음" if info["common_exists"] else "없음"
    lines.append(f"공통 온톨로지: {common_status}")
    lines.append("")

    # 도메인별 현황
    lines.append("도메인별 현황:")
    lines.append("-" * 40)

    for domain, config in OntologyLoader.DOMAIN_CONFIG.items():
        exists = domain in info["existing_domains"]
        status = "O" if exists else "X"
        name = config['name']

        if exists:
            detail = info["details"][domain]
            files = len(detail["files"])
            size = detail["total_size_kb"]
            lines.append(f"  [{status}] {domain} ({name}): {files}개 파일, {size}KB")
        else:
            lines.append(f"  [{status}] {domain} ({name}): 폴더 없음")

    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)
