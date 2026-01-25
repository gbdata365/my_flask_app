# 파이썬 샘플데이터생성, 탐색, 데이터분석, 예측 모델링을 위한 claude AI 에이전트

## 프로젝트 개요

이 프로젝트는 다음과 같은 작업을 수행할 수 있는 파이썬 기반 AI 에이전트를 구축하는 것을 목표로 합니다.



*   **데이터 분석:** `pandas` 및 `numpy`를 사용하여 수집된 데이터 처리 및 분석
*   **데이터 시각화:** `matplotlib` 및 `seaborn`을 사용하여 데이터를 시각화하는 차트 및 그래프 생성
*   **예측 모델링:** `scikit-learn`을 사용하여 머신러닝 모델 구축 및 평가

## 설정 지침

### 1. 가상 환경 (uv 사용)

`uv`는 Rust로 작성된 매우 빠른 파이썬 패키지 설치 및 해결 도구입니다. `venv`와 `pip`를 함께 사용하는 것보다 훨씬 빠릅니다.

**uv 설치:**
*   **macOS/Linux:**
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
*   **Windows:**
    ```bash
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

**가상 환경 생성 및 활성화:**
```bash
uv venv
source .venv/bin/activate
```

### 2. 의존성 설치 (uv 사용)

`uv pip`를 사용하여 필요한 파이썬 라이브러리를 설치합니다.

```bash
uv pip install requests beautifulsoup4 pandas numpy matplotlib seaborn scikit-learn koreanize-matplotlib loguru
```

### 3. Matplotlib 한글 설정 (koreanize-matplotlib 사용)

`koreanize-matplotlib` 라이브러리를 사용하면 복잡한 설정 없이 `matplotlib`에서 한글을 쉽게 사용할 수 있습니다.

**사용법:**
파이썬 스크립트 상단에 다음 코드를 추가하기만 하면 됩니다.

```python
import koreanize_matplotlib
```

* seaborn의 스타일 설정은 사용하지 말 것

### 4. 로깅 (loguru 사용)

`loguru`는 파이썬 로깅을 쉽고 강력하게 만들어주는 라이브러리입니다.

**기본 사용법:**
```python
from loguru import logger

logger.debug("디버그 메시지")
logger.info("정보 메시지")
logger.warning("경고 메시지")
logger.error("에러 메시지")
logger.critical("심각한 에러 메시지")
```

**파일 로깅 설정:**
```python
logger.add("file_{time}.log", rotation="500 MB") # 500MB 마다 로그 파일 교체
```

## 인구 데이터베이스 규칙 (01_인구및가구현황)

### 행정구역 코드 체계 (sigungu_code 5자리)

```
sigungu_code = AABBC
- AA: 시도코드 (2자리)
- BB: 시군구코드 (2자리)
- C: 하위구분 (1자리)
  - 0: 시군구 레벨 (기본)
  - 1-9: 하위 행정구 (대도시 구, 행정시 등)
```

**예시:**
- `11110` = 서울 종로구 (마지막 0 → 시군구 레벨)
- `41110` = 경기 수원시 (마지막 0 → 시군구 레벨)
- `41111` = 경기 수원시 장안구 (마지막 1 → 하위 행정구)
- `41115` = 경기 수원시 팔달구 (마지막 5 → 하위 행정구)

### 캐시 테이블 (cache_sigungu_indicators) 규칙

1. **저장**: sigungu_code 5자리 전체로 저장 (행정구 레벨 포함)
2. **기본 조회**: `sigungu_code LIKE '____0'` - 마지막 자리가 0인 시군구만
3. **상세 조회**: 5자리 전체 사용 (행정구 레벨 포함)

### transfer.py 규칙

- **원본 데이터**: fact_population_by_age는 **읍면동 단위**로 저장됨
- **캐시 생성 시**: 읍면동 데이터를 sigungu_code 기준으로 GROUP BY 집계
- **WHERE 조건**: `eupmyeondong_nm IS NULL` 조건 사용 금지 (데이터 누락 발생)

### 시도명 정규화

```
강원도 / 강원특별자치도 → 강원특별자치도 (42)
전라북도 / 전북특별자치도 → 전북특별자치도 (45)
제주도 / 제주특별자치도 → 제주특별자치도 (50)
```

### 연령 그룹 정의

- **code_age_group 테이블**: 5세별, 10세별, 정책연령 등 모든 연령 그룹 정의
- **transfer.py**: code_age_group 테이블에서 동적으로 컬럼 생성
- **새 연령 그룹 추가 시**: code_age_group에 INSERT 후 `python transfer.py --init` 실행

## 개발 규칙

*   **언어:** Python 3
*   **디렉토리 구조:**
    가상 환경(`.venv`)은 프로젝트 루트에 위치시키고, 각 개별 프로젝트는 별도의 하위 폴더로 관리하는 구조를 권장합니다. 이렇게 하면 여러 프로젝트가 하나의 가상 환경을 공유할 수 있습니다.

    ```
    .
    ├── .venv/
    ├── project_A/
    │   ├── src/
    │   ├── data/
    │   └── tests/
    ├── project_B/
    │   ├── src/
    │   ├── data/
    │   └── tests/
    └── ...
    ```
    *   **`.venv/`**: 모든 프로젝트가 공유하는 파이썬 가상 환경입니다.
    *   **`project_A/`, `project_B/`**: 개별 프로젝트 폴더입니다. 각 폴더는 자체 소스 코드(`src`), 데이터(`data`), 테스트(`tests`) 등을 가집니다.


