# AI 어시스턴트용 개발 가이드

## 프로젝트 개요
이 문서는 기업통계등록부 분석 대시보드 시스템의 개발과 유지보수를 위한 AI 어시스턴트 가이드입니다.

## 시스템 아키텍처

### 기본 구조
```
C:\Users\user\00_claude_project\project\1_giup\
├── routes/              # Flask 라우트 파일들
│   ├── dash1.py        # 메인 대시보드 (matplotlib 버전)
│   ├── dash1_backup.py # Plotly 백업 버전
│   └── dash2.py        # 경상북도 전용 대시보드
├── data/               # 데이터 파일들
│   ├── 집계표_YYYYMM.xlsx  # 집계표 데이터 (패턴: 년도월)
│   └── *.xlsx          # 기타 Excel 데이터
├── static/             # 정적 파일 (CSS, JS, 이미지, 외부 라이브러리)
├── templates/          # HTML 템플릿
├── html_docs/          # HTML 문서
└── markdown_docs/      # 마크다운 문서
```

### 핵심 기술 스택
- **백엔드**: Python, Flask, pandas, numpy, matplotlib, seaborn, reportlab
- **프론트엔드**: Bootstrap 5, jQuery, Select2, Font Awesome
- **데이터**: Excel (xlsx), JSON, Base64 이미지 인코딩

## 개발 패턴

### 1. 데이터 로딩 패턴
```python
def load_data():
    """집계표_YYYYMM.xlsx 형식의 모든 데이터 자동 로드 및 통합"""
    # 1. glob으로 패턴 매칭 파일 찾기
    # 2. 정규식으로 년월 정보 추출
    # 3. 파일별 DataFrame 생성 후 통합
    # 4. 숫자형 컬럼 전처리 (쉼표, 특수문자 제거)
    # 5. 컬럼별 분류 (numeric_cols, closure_cols, business_cols, industry_cols)
```

### 2. 차트 생성 패턴
```python
def create_chart_base64(fig):
    """matplotlib figure를 base64 문자열로 변환"""
    # 1. BytesIO 버퍼 생성
    # 2. figure를 PNG로 저장 (DPI 150, bbox_inches='tight')
    # 3. base64 인코딩
    # 4. 메모리 해제 (plt.close)
    # 5. base64 문자열 반환
```

### 3. Flask 라우트 패턴
```python
def create_comprehensive_dashboard(df, numeric_cols, closure_cols, business_cols, industry_cols):
    """종합 대시보드 생성 (matplotlib/seaborn 기반)"""
    # 1. 데이터 검증 및 기본 통계 계산
    # 2. 각 차트 유형별 데이터 준비
    # 3. matplotlib 차트 생성 및 base64 변환
    # 4. HTML 템플릿에 차트 이미지 임베드
    # 5. JavaScript로 인터랙티브 기능 추가
```

## 코딩 규칙

### 1. 한글 처리
```python
# matplotlib 한글 폰트 설정 (필수)
plt.rcParams['font.family'] = ['Malgun Gothic', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
```

### 2. JSON 직렬화
```python
# pandas/numpy 타입을 Python 네이티브 타입으로 변환
def convert_to_native_types(data):
    # int64 → int, float64 → float, ndarray → list 변환
    # 딕셔너리와 리스트는 재귀적으로 처리
```

### 3. 메모리 관리
```python
# matplotlib figure는 반드시 메모리 해제
def create_chart_base64(fig):
    # ... 차트 생성 로직 ...
    plt.close(fig)  # 필수!
    return img_str
```

### 4. 에러 처리
```python
# 데이터가 없을 때 빈 차트 표시
if len(data) == 0:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.text(0.5, 0.5, '데이터가 없습니다', ha='center', va='center', fontsize=16)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return create_chart_base64(fig)
```

## 개발 지침

### 새로운 차트 추가
1. `create_[chart_type]_chart()` 함수 생성
2. base64 인코딩 적용
3. HTML 템플릿에 `<img src="data:image/png;base64,{chart_data}">` 추가
4. 필요시 JavaScript 인터랙션 추가

### 새로운 분석 유형 추가
1. 데이터 전처리 로직 추가 (load_data 함수)
2. 구분별 표시명 딕셔너리 정의
3. 차트 생성 함수 구현
4. HTML 필터 옵션 추가
5. JavaScript 이벤트 핸들러 업데이트

### 새로운 필터 추가
1. HTML select 엘리먼트 추가
2. JavaScript 업데이트 함수 수정
3. 백엔드 데이터 필터링 로직 구현
4. 차트 재생성 트리거 연결

## 외부 의존성 관리

### CDN → 로컬 파일 변환
폐쇄망 환경을 위해 CDN 리소스를 로컬로 저장:

1. **Bootstrap 5**
   - CSS: `https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css`
   - JS: `https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js`
   - 저장 위치: `static/css/bootstrap.min.css`, `static/js/bootstrap.bundle.min.js`

2. **jQuery**
   - JS: `https://code.jquery.com/jquery-3.6.0.min.js`
   - 저장 위치: `static/js/jquery-3.6.0.min.js`

3. **Select2**
   - CSS: `https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css`
   - JS: `https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js`
   - 저장 위치: `static/css/select2.min.css`, `static/js/select2.min.js`

4. **Font Awesome**
   - CSS: `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css`
   - 저장 위치: `static/css/fontawesome.min.css`

### HTML 참조 변경
```html
<!-- CDN (개발용) -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">

<!-- 로컬 파일 (운영용) -->
<link href="{{ url_for('static', filename='css/bootstrap.min.css') }}" rel="stylesheet">
```

## 일반적인 작업 흐름

### 새로운 기능 개발
1. **요구사항 분석**: 사용자가 원하는 기능 파악
2. **데이터 구조 확인**: 필요한 데이터가 있는지 검증
3. **백엔드 구현**: Python 함수로 데이터 처리 및 차트 생성
4. **프론트엔드 구현**: HTML/CSS/JS로 UI 구성
5. **통합 테스트**: 전체 시스템 동작 확인
6. **문서 업데이트**: guide.md 및 통계등록부.md 갱신

### 버그 수정
1. **문제 재현**: 에러 상황 재현 및 로그 확인
2. **원인 분석**: 코드 검토 및 디버깅
3. **수정 적용**: 최소한의 변경으로 문제 해결
4. **테스트**: 수정 사항이 다른 기능에 영향 없는지 확인
5. **백업**: 원본 파일 보존 (`_backup.py` 형태)

### 성능 최적화
1. **병목 지점 파악**: 프로파일링으로 느린 부분 찾기
2. **데이터 최적화**: 불필요한 데이터 로딩 제거
3. **차트 최적화**: DPI 조정, 이미지 압축
4. **메모리 관리**: figure 해제, 가비지 컬렉션
5. **캐싱 적용**: 중복 계산 방지

## 트러블슈팅

### 자주 발생하는 문제들

1. **한글 깨짐**
   - 원인: matplotlib 폰트 설정 누락
   - 해결: `plt.rcParams['font.family'] = ['Malgun Gothic', 'DejaVu Sans']`

2. **JSON 직렬화 에러**
   - 원인: numpy/pandas 타입이 JSON으로 변환되지 않음
   - 해결: `convert_to_native_types()` 함수 사용

3. **메모리 누수**
   - 원인: matplotlib figure가 해제되지 않음
   - 해결: 모든 차트 생성 후 `plt.close(fig)` 호출

4. **데이터 파일 없음**
   - 원인: 예상한 파일명 패턴과 다름
   - 해결: glob 패턴 확인 및 정규식 수정

5. **Select2 동작 안함**
   - 원인: jQuery 로드 순서 문제
   - 해결: jQuery → Bootstrap → Select2 순서로 로드

### 디버깅 방법

1. **콘솔 로그**: `python main_app.py` 실행 후 터미널 메시지 확인
2. **브라우저 개발자 도구**: Network 탭에서 API 응답 상태 확인
3. **Python 디버거**: `import pdb; pdb.set_trace()` 사용
4. **로그 파일**: 필요시 logging 모듈로 상세 로그 기록

## 확장 가이드

### 새로운 데이터 소스 추가
1. 데이터 포맷 분석 (Excel, CSV, JSON 등)
2. 로딩 함수 구현 (`load_[source_name]_data`)
3. 기존 데이터와 통합 방식 정의
4. 새로운 컬럼 타입 분류
5. 차트 매핑 정의

### API 엔드포인트 추가
1. Flask 라우트 함수 생성
2. 요청 파라미터 검증
3. 데이터 처리 및 응답 포맷 정의
4. 에러 처리 및 상태 코드 설정
5. 프론트엔드 연동

### 새로운 차트 라이브러리 추가
1. 라이브러리 설치 및 import
2. 기존 matplotlib 패턴과 동일한 인터페이스 구현
3. base64 인코딩 지원 확인
4. 한글 폰트 설정 적용
5. 성능 및 메모리 사용량 테스트

## 배포 가이드

### 개발 환경
```bash
cd C:\Users\user\00_claude_project\project
python main_app.py
# 브라우저에서 http://localhost:5000/1_giup/dash1 접속
```

### 폐쇄망 환경 준비
1. 모든 외부 CDN 파일을 static 폴더에 다운로드
2. HTML 템플릿의 CDN 링크를 로컬 파일로 변경
3. 필요한 Python 패키지를 오프라인으로 설치
4. 데이터 파일 경로 확인 및 권한 설정

### 보안 고려사항2

1. 데이터 파일 접근 권한 제한
2. 업로드 파일 검증 및 크기 제한
3. SQL 인젝션 방지 (pandas 사용으로 자동 방지)
4. XSS 방지 (템플릿 이스케이핑 활용)

---

## 마지막 업데이트
- 날짜: 2025년 1월
- 버전: matplotlib 기반 대시보드 v1.0
- 작성자: AI Assistant
- 목적: 향후 AI 어시스턴트가 이 시스템을 효율적으로 개발/유지보수할 수 있도록 가이드 제공

**중요**: 이 가이드는 AI 어시스턴트가 사용자의 요청을 정확히 이해하고 일관된 방식으로 개발할 수 있도록 작성되었습니다. 새로운 기능을 추가할 때는 반드시 이 가이드의 패턴을 따라야 합니다.