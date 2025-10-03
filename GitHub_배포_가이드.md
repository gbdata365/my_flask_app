# GitHub 배포 배치 파일 사용 가이드

## 개요
이 가이드는 프로젝트를 GitHub에 업로드하고 CloudType에 배포하기 위한 배치 파일 사용법을 설명합니다.

## 배치 파일 설명

### 📁 `git_deploy.bat` (추천)
**용도**: 스마트한 GitHub 배포 - 저장소가 없으면 새로 만들고, 있으면 업데이트

**특징**:
- ✅ 기존 Git 설정이 있는지 확인 후 필요시에만 초기화
- ✅ 원격 저장소가 설정되어 있으면 기존 설정 유지
- ✅ 안전한 일반 `git push` 사용
- ✅ 기존 커밋 히스토리 보존
- ✅ 최초 배포와 업데이트 모두 지원

### 📁 `git_deploy_fixed.bat` (위험)
**용도**: 강제 초기화 배포

**특징**:
- ⚠️ 기존 `.git` 폴더를 완전히 삭제
- ⚠️ 항상 새로운 Git 저장소로 시작
- ⚠️ `git push --force` 사용으로 기존 히스토리 덮어씀
- 🚫 **사용 권장하지 않음**

### 📁 `git_update.bat` (제한적)
**용도**: 기존 저장소 업데이트 전용

**특징**:
- 📋 이미 설정된 Git 저장소에서만 동작
- 📋 변경사항을 보여주고 사용자 승인 요청
- 📋 기존 히스토리 유지
- ❌ 최초 배포 불가

## 사용법

### 1. git_deploy.bat 실행 (추천)

```batch
git_deploy.bat
```

**실행 단계**:
1. **Git 사용자 정보 설정** - 최초 1회만
2. **Git 저장소 초기화** - 없을 때만 실행
3. **원격 저장소 설정** - 없을 때만 실행
4. **메인 브랜치 설정** - main 브랜치로 통일
5. **파일 스테이징** - 모든 변경사항 추가
6. **커밋** - 변경사항 확정
7. **GitHub 업로드** - 원격 저장소에 푸시

### 2. 실행 중 입력사항

#### GitHub 저장소 URL 설정
```
기본 저장소: https://github.com/gbdata365/my_flask_app.git
GitHub 저장소 URL (기본값 사용하려면 Enter, 다른 URL 사용시 입력):
```
- **Enter** 키만 누르면 기본 저장소 사용
- 다른 저장소를 사용하려면 전체 URL 입력

#### 커밋 메시지 입력
```
커밋 메시지를 입력하세요 (기본값: Update application):
```
- **Enter** 키만 누르면 기본 메시지 사용
- 구체적인 변경사항을 설명하는 메시지 입력 권장

## Git 명령어 설명

### 기본 Git 명령어
```bash
git init                    # Git 저장소 초기화
git config --global user.name "이름"     # 사용자 이름 설정
git config --global user.email "이메일"  # 사용자 이메일 설정
git remote add origin <URL> # 원격 저장소 연결
git branch -M main          # 메인 브랜치를 main으로 설정
git add .                   # 모든 파일을 스테이징 영역에 추가
git commit -m "메시지"      # 변경사항을 커밋
git push -u origin main     # 원격 저장소에 업로드 (최초)
git push origin main        # 원격 저장소에 업로드 (이후)
```

### 고급 명령어
```bash
git status                  # 현재 Git 상태 확인
git diff --name-only HEAD   # 변경된 파일 목록 보기
git remote -v               # 원격 저장소 설정 확인
git push --force            # 강제 푸시 (위험)
```

## GitHub 저장소 확인

### 기본 설정된 저장소
**저장소 URL**: https://github.com/gbdata365/my_flask_app.git

이 저장소에 접속하여 현재 업로드된 내용을 확인할 수 있습니다:
- **파일 목록**: 프로젝트의 모든 파일
- **커밋 히스토리**: 지금까지의 변경 이력
- **브랜치**: main 브랜치 사용

### 저장소 내용 확인 방법
1. 웹 브라우저에서 https://github.com/gbdata365/my_flask_app.git 접속
2. 또는 GitHub에서 "gbdata365/my_flask_app" 검색
3. Files 탭에서 현재 업로드된 파일들 확인
4. Commits 탭에서 업로드 히스토리 확인

## CloudType 배포 설정

배치 파일 실행 후 CloudType 배포를 위한 설정:

### 1. CloudType 로그인
- https://cloudtype.io 접속
- GitHub 계정으로 로그인

### 2. 프로젝트 생성
1. "새 프로젝트" 클릭
2. "GitHub 연동" 선택
3. 저장소 선택: `gbdata365/my_flask_app`
4. 브랜치: `main` 선택

### 3. 빌드 설정
```
Build Command: (빈칸으로 둠)
Start Command: python main_app.py
Port: 5000
```

### 4. 환경변수 설정 (선택사항)
```
DB_HOST: 데이터베이스 호스트
DB_USER: 데이터베이스 사용자명
DB_PASS: 데이터베이스 비밀번호
DB_NAME: 데이터베이스 이름
```

## 문제 해결

### 1. 푸시 실패시
```
⚠️ 푸시 실패! 다음을 확인하세요:
- GitHub 저장소가 존재하는지 확인
- 인증 정보가 올바른지 확인
- 네트워크 연결 상태 확인
```

**해결 방법**:
1. GitHub에 로그인되어 있는지 확인
2. GitHub Desktop이 설치되어 있다면 로그인 상태 확인
3. 저장소 URL이 올바른지 확인
4. 인터넷 연결 상태 확인

### 2. Git 사용자 정보 오류
```bash
git config --global user.name "본인이름"
git config --global user.email "본인이메일@gmail.com"
```

### 3. 원격 저장소 변경
기존 원격 저장소를 변경하려면:
```bash
git remote remove origin
git remote add origin <새로운_URL>
```

## 권장사항

1. **git_deploy.bat 사용** - 가장 안전하고 완전한 기능
2. **정기적인 백업** - 중요한 코드 변경 전 백업
3. **명확한 커밋 메시지** - 변경사항을 구체적으로 설명
4. **GitHub 웹에서 확인** - 업로드 후 웹에서 파일 확인

## 추가 참고사항

- **문자 인코딩**: `chcp 65001`로 UTF-8 설정
- **에러 처리**: 각 단계별 에러 검사 및 안내
- **사용자 입력**: 기본값 제공으로 편의성 증대
- **상태 확인**: 각 단계별 진행 상황 표시