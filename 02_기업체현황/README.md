# 기업체현황 데이터 처리 프로젝트

## 프로젝트 개요

분기별 기업통계등록부(SBR) 집계표 데이터를 표준화된 형식으로 데이터베이스에 저장하는 시스템입니다.

## 작업 수행 내용

### 1. 데이터 소스 분석

#### 1.1 실제 데이터 파일
- **파일명**: `data/(수정)집계표_24년1분기.xlsx`
- **구조**: 7개의 시트로 구성
  - 조직형태별: 개인사업체, 회사법인 등
  - 대표자성별별: 남자, 여자
  - 폐업여부별: 영업중, 폐업
  - 산업분류별: 한국표준산업분류 대분류
  - 대표사업체별: 본점/지점 구분
  - 수치형통계: 종사자수, 매출금액 등
  - 결측치현황: 데이터 품질 정보

#### 1.2 표준화 레이아웃
- **파일명**: `data/2. 분기_기업통계등록부_표준화 연계 레이아웃.xlsx`
- **내용**:
  - 영문 컬럼명(표준화 전/후)
  - 한글 컬럼명(표준화 전/후)
  - 데이터 타입 및 길이
  - 컬럼 설명
- **추출 결과**: 70개의 표준화 컬럼 정의 (JSON 파일로 저장)

#### 1.3 코드 테이블
- **파일명**: `data/코드.xlsx`
- **내용**:
  - 조직형태코드 (1-5)
  - 대표자성별코드 (1-2)
  - 폐업사유코드 (01-19)
  - 활동구분코드 (1-3)
  - 행정구역분류코드 (11-39)
  - 산업분류_대분류 (A-U)
  - 기타 코드 정의

### 2. 데이터베이스 스키마 설계

#### 2.1 주소 테이블 활용
- **테이블명**: `gb_address`
- **구조**:
  - 시도명, 시군구명 (한글)
  - 행정구역코드 (8자리 숫자)
    - 앞 2자리: 시도코드
    - 앞 5자리: 시군구코드
    - 6-8자리: 읍면동코드

#### 2.2 집계표 테이블 설계
- **테이블명**: `sbr_quarter_summary`
- **주요 컬럼**:
  - **기준 정보**:
    - `CRTR_YR` (CHAR(4)): 기준연도
    - `QU_SE_CD` (VARCHAR(1)): 분기구분코드 (1,2,3,4)
  - **지역 정보**:
    - `ADCLSF_CTPV_CD` (VARCHAR(2)): 행정구역분류시도코드
    - `ADCLSF_SGG_CD` (VARCHAR(5)): 행정구역분류시군구코드
    - `CTPV_NM` (VARCHAR(40)): 시도명
    - `SGG_NM` (VARCHAR(100)): 시군구명
  - **조직형태별 통계** (ORG_ 접두사):
    - `ORG_개인사업체`, `ORG_회사법인`, `ORG_합계` 등
  - **성별 통계** (GENDER_ 접두사):
    - `GENDER_남자`, `GENDER_여자`, `GENDER_합계` 등
  - **영업상태별 통계** (STATUS_ 접두사):
    - `STATUS_영업중`, `STATUS_폐업`, `STATUS_합계`
  - **산업분류별 통계** (IND_ 접두사):
    - `IND_농업,임업,어업`, `IND_제조업`, `IND_합계` 등
  - **수치형 통계** (STATS_ 접두사):
    - 종사자수: `STATS_기업종사자수_건수`, `STATS_기업종사자수_합계`, `STATS_기업종사자수_평균`
    - 매출금액: `STATS_기업매출금액_건수`, `STATS_기업매출금액_합계`, `STATS_기업매출금액_평균`
    - 상용근로자수, 임시일용근로자수 통계

### 3. 데이터 처리 프로세스

#### 3.1 엑셀 데이터 읽기
```python
def read_sheet(file_path: str, sheet_name: str) -> pd.DataFrame:
    """
    1. 엑셀 시트 읽기
    2. NaN 컬럼 제거
    3. 기준시기, 시도명 ffill 처리
    4. '*' 값을 NULL로 변환
    5. 시트별 접두사 추가 (ORG_, GENDER_, STATUS_, IND_, STATS_)
    """
```

#### 3.2 시트 병합
```python
def merge_all_sheets(file_path: str) -> pd.DataFrame:
    """
    1. 6개 시트를 순차적으로 읽기
    2. 기준시기, 시도명, 시군구명을 키로 outer join
    3. 컬럼 중복 방지를 위해 시트별 접두사 사용
    """
```

#### 3.3 지역 코드 매핑
```python
def get_address_codes(sido_nm: str, sigungu_nm: str) -> Tuple:
    """
    1. gb_address 테이블에서 시도명, 시군구명으로 검색
    2. 행정구역코드에서 시도코드, 시군구코드 추출
    3. 매핑 실패 시 경고 로그 기록
    """
```

#### 3.4 기준시기 파싱
```python
def parse_period(period_str: str) -> Tuple:
    """
    "2024년 1분기" -> (year="2024", quarter="1", type="분기")
    정규식을 사용하여 파싱
    """
```

### 4. 데이터베이스 저장

#### 4.1 테이블 생성
```sql
CREATE TABLE sbr_quarter_summary (
    id SERIAL PRIMARY KEY,
    CRTR_YR CHAR(4),
    QU_SE_CD VARCHAR(1),
    ADCLSF_CTPV_CD VARCHAR(2),
    ADCLSF_SGG_CD VARCHAR(5),
    CTPV_NM VARCHAR(40),
    SGG_NM VARCHAR(100),
    ... (60개 컬럼)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX idx_sbr_quarter_summary_year ON sbr_quarter_summary(CRTR_YR);
CREATE INDEX idx_sbr_quarter_summary_quarter ON sbr_quarter_summary(QU_SE_CD);
CREATE INDEX idx_sbr_quarter_summary_sido ON sbr_quarter_summary(ADCLSF_CTPV_CD);
CREATE INDEX idx_sbr_quarter_summary_sigungu ON sbr_quarter_summary(ADCLSF_SGG_CD);

-- 컬럼 COMMENT 추가
COMMENT ON COLUMN sbr_quarter_summary.CRTR_YR IS '기준연도';
COMMENT ON COLUMN sbr_quarter_summary.QU_SE_CD IS '분기구분코드';
... (모든 컬럼에 한글 설명 추가)
```

#### 4.2 데이터 삽입
- **삽입 건수**: 251행
- **삽입 속도**: 초당 약 100행
- **데이터 품질**:
  - 대부분의 시군구 코드 매핑 성공
  - 일부 시군구명 오류로 인한 매핑 실패 (10건 미만)

## 데이터 온톨로지

### 엔티티-관계 모델

```
┌─────────────────┐
│  gb_address     │ (기존 테이블)
├─────────────────┤
│ 시도명          │
│ 시군구명        │
│ 행정구역코드    │
│ 법정동코드      │
└─────────────────┘
         │
         │ 참조 (시도명, 시군구명)
         ↓
┌─────────────────────────────────┐
│  sbr_quarter_summary           │ (신규 생성)
├─────────────────────────────────┤
│ **기준 정보**                  │
│  - CRTR_YR (기준연도)          │
│  - QU_SE_CD (분기구분코드)     │
│                                 │
│ **지역 정보**                  │
│  - ADCLSF_CTPV_CD (시도코드)   │
│  - ADCLSF_SGG_CD (시군구코드)  │
│  - CTPV_NM (시도명)            │
│  - SGG_NM (시군구명)           │
│                                 │
│ **조직형태별 통계** (6개)      │
│  - ORG_* (개인, 법인 등)       │
│                                 │
│ **성별 통계** (4개)            │
│  - GENDER_* (남자, 여자 등)    │
│                                 │
│ **영업상태별 통계** (3개)      │
│  - STATUS_* (영업중, 폐업)     │
│                                 │
│ **산업분류별 통계** (22개)     │
│  - IND_* (제조업, 건설업 등)   │
│                                 │
│ **대표사업체 통계** (2개)      │
│  - MAINBIZ_* (본점, 지점)      │
│                                 │
│ **수치형 통계** (16개)         │
│  - STATS_* (종사자, 매출 등)   │
└─────────────────────────────────┘
```

### 데이터 계층 구조

```
분기 기업통계등록부 집계표
│
├─ 시간 차원
│   ├─ 기준연도 (CRTR_YR)
│   └─ 분기구분 (QU_SE_CD)
│
├─ 공간 차원
│   ├─ 시도 (ADCLSF_CTPV_CD, CTPV_NM)
│   └─ 시군구 (ADCLSF_SGG_CD, SGG_NM)
│
└─ 측정 차원
    ├─ 조직형태별 (ORG_*)
    │   ├─ 개인사업체
    │   ├─ 회사법인
    │   ├─ 회사이외법인
    │   ├─ 비법인단체
    │   └─ 국가지방자치단체
    │
    ├─ 성별 (GENDER_*)
    │   ├─ 남자
    │   ├─ 여자
    │   └─ 미상
    │
    ├─ 영업상태 (STATUS_*)
    │   ├─ 영업중
    │   └─ 폐업
    │
    ├─ 산업분류 (IND_*)
    │   ├─ A: 농업, 임업 및 어업
    │   ├─ B: 광업
    │   ├─ C: 제조업
    │   ├─ ... (한국표준산업분류 대분류)
    │   └─ U: 국제기관
    │
    └─ 수치형 통계 (STATS_*)
        ├─ 종사자수 (건수, 합계, 평균, 공백건수)
        ├─ 매출금액 (건수, 합계, 평균, 공백건수)
        ├─ 상용근로자수 (건수, 합계, 평균, 공백건수)
        └─ 임시일용근로자수 (건수, 합계, 평균, 공백건수)
```

### 코드 체계

#### 시도코드 (ADCLSF_CTPV_CD)
```
11: 서울특별시
21: 부산광역시
22: 대구광역시
23: 인천광역시
24: 광주광역시
25: 대전광역시
26: 울산광역시
29: 세종특별자치시
31: 경기도
32: 강원특별자치도
33: 충청북도
34: 충청남도
35: 전북특별자치도
36: 전라남도
37: 경상북도
38: 경상남도
39: 제주특별자치도
```

#### 분기구분코드 (QU_SE_CD)
```
1: 1분기 (1-3월)
2: 2분기 (4-6월)
3: 3분기 (7-9월)
4: 4분기 (10-12월)
```

#### 조직형태코드 (OGNZ_SHAPE_CD)
```
1: 개인사업체
2: 회사법인
3: 회사이외법인
4: 비법인단체
5: 국가지방자치단체
```

## 사용 방법

### 1. 데이터 처리 및 저장

```bash
# 1단계: 테이블 생성 및 데이터 삽입
python read_xlsx_new.py --file "data/(수정)집계표_24년1분기.xlsx" --init --insert

# 2단계: CSV로 내보내기 (선택사항)
python read_xlsx_new.py --file "data/(수정)집계표_24년1분기.xlsx" --output output.csv
```

### 2. 데이터 조회 예시

```sql
-- 1. 전국 통계 조회
SELECT
    CRTR_YR,
    QU_SE_CD,
    SUM("ORG_합계") as 총사업체수,
    SUM("STATS_기업종사자수_합계") as 총종사자수,
    SUM("STATS_기업매출금액_합계") as 총매출액
FROM sbr_quarter_summary
GROUP BY CRTR_YR, QU_SE_CD
ORDER BY CRTR_YR, QU_SE_CD;

-- 2. 시도별 산업분류 통계
SELECT
    CTPV_NM as 시도명,
    SUM("IND_제조업") as 제조업,
    SUM("IND_건설업") as 건설업,
    SUM("IND_도매및소매업") as 도소매업
FROM sbr_quarter_summary
WHERE CRTR_YR = '2024' AND QU_SE_CD = '1'
GROUP BY CTPV_NM
ORDER BY 제조업 DESC;

-- 3. 시군구별 상위 10개 지역
SELECT
    CTPV_NM || ' ' || SGG_NM as 지역,
    "ORG_합계" as 총사업체수,
    "STATS_기업종사자수_합계" as 총종사자수
FROM sbr_quarter_summary
WHERE CRTR_YR = '2024' AND QU_SE_CD = '1'
ORDER BY "ORG_합계" DESC
LIMIT 10;
```

## 파일 구조

```
02_기업체현황/
├── data/
│   ├── (수정)집계표_24년1분기.xlsx         # 원본 데이터
│   ├── 2. 분기_기업통계등록부_표준화 연계 레이아웃.xlsx
│   ├── 2. 2025년 2분기 기업통계등록부(SBR) 설명자료.pdf
│   └── 코드.xlsx
│
├── read_xlsx.py                          # 기존 스크립트 (백업)
├── read_xlsx_old.py                      # 백업 파일
├── read_xlsx_new.py                      # 새로운 표준화 스크립트 ⭐
│
├── analyze_xlsx.py                       # 엑셀 구조 분석 도구
├── extract_layout.py                     # 레이아웃 추출 도구
├── check_address_table.py                # 주소 테이블 확인 도구
├── check_gb_address.py                   # gb_address 상세 확인 도구
│
├── column_mappings.json                  # 추출된 컬럼 매핑 정보
│
└── README.md                             # 이 문서
```

## 주요 기능

### ✅ 완료된 기능

1. **엑셀 데이터 읽기 및 병합**
   - 6개 시트의 데이터를 하나로 통합
   - 컬럼 중복 방지 (시트별 접두사)
   - 특수 값('*') 처리

2. **지역 코드 매핑**
   - gb_address 테이블에서 시도코드, 시군구코드 자동 조회
   - 매핑 실패 시 경고 로그

3. **표준화된 데이터베이스 저장**
   - 레이아웃 파일 기반 컬럼명
   - 한글 COMMENT 자동 추가
   - 인덱스 자동 생성

4. **데이터 품질 관리**
   - NULL 값 처리
   - 숫자형 자동 변환
   - 데이터 타입 검증

### 🔄 향후 개선 사항

1. **컬럼명 완전 영문화**
   - 현재: `ORG_개인사업체`, `GENDER_남자` (한글 포함)
   - 개선안: `ORG_INDIVIDUAL`, `GENDER_MALE` (완전 영문)

2. **코드 테이블 연계**
   - 조직형태코드, 산업분류코드 등을 별도 테이블로 관리
   - 외래키 제약조건 추가

3. **데이터 검증**
   - 합계 컬럼 검증 (세부 항목의 합 = 합계)
   - 분기별 데이터 일관성 검증

4. **배치 처리**
   - 여러 분기 데이터 자동 처리
   - 증분 업데이트 지원

## 참고 자료

- 통계청 기업통계등록부(SBR) 가이드
- 한국표준산업분류(KSIC) 10차 개정
- 행정구역분류코드 (행정안전부)

## 작업 이력

- **2024-01-14**:
  - 프로젝트 초기 설정
  - 엑셀 데이터 구조 분석
  - 표준화 레이아웃 추출
  - gb_address 테이블 확인
  - read_xlsx_new.py 스크립트 작성
  - 데이터베이스 테이블 생성 및 데이터 삽입 (251행)
  - 문서화 완료
