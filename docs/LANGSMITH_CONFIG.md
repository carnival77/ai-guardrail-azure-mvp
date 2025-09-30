# 🔍 LangSmith 모니터링 설정 가이드 (CONFIG 기반)

## 📌 설정 철학

**민감 정보**는 `.env`에, **비민감 설정**은 `config.yaml`에 관리합니다.

| 설정 항목 | 위치 | 이유 |
|-----------|------|------|
| **API 키** | `.env` | 민감 정보, Git에 올리면 안 됨 |
| **활성화 여부** | `config.yaml` | 팀 공유, 환경별 관리 용이 |
| **프로젝트명** | `config.yaml` | 팀 공유, 환경별 관리 용이 |

---

## ⚙️ 설정 방법 (5분)

### 1단계: config.yaml 확인
`config/config.yaml` 파일에 이미 설정되어 있습니다:

```yaml
# LangSmith 모니터링 설정
langsmith_enabled: true  # 추적 활성화 (false로 변경 시 비활성화)
langsmith_project_name: "ai-guardrail-mvp"  # 프로젝트명
```

**환경별 설정 예시:**
```yaml
# 개발 환경
langsmith_enabled: true
langsmith_project_name: "ai-guardrail-dev"

# 스테이징 환경
langsmith_enabled: true
langsmith_project_name: "ai-guardrail-staging"

# 프로덕션 환경 (선택적)
langsmith_enabled: false  # 개인정보 로깅 주의
langsmith_project_name: "ai-guardrail-prod"
```

---

### 2단계: LangSmith API 키 발급
1. [https://smith.langchain.com/](https://smith.langchain.com/) 접속
2. 회원가입 (GitHub 계정 연동 가능)
3. Settings → API Keys → Create API Key
4. 생성된 키 복사 (`lsv2_pt_`로 시작)

---

### 3단계: .env 파일에 API 키만 추가

`.env` 파일에 **API 키만** 추가:

```env
# 기존 Azure 설정들...
AZURE_OPENAI_API_KEY=...
AZURE_SEARCH_API_KEY=...

# LangSmith API 키 (민감 정보)
LANGSMITH_API_KEY=lsv2_pt_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**주의:** 
- ✅ `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`는 **불필요** (config.yaml에서 자동 설정)
- ✅ API 키만 `.env`에 추가하면 됨

---

### 4단계: 애플리케이션 재시작

```bash
python main.py app
```

---

## 🎯 작동 원리

### 내부 동작 (`src/core/rag_core.py`)

```python
# config.yaml 설정 읽기
if CONFIG.get("langsmith_enabled", False):
    # 환경 변수 자동 설정
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", CONFIG["langsmith_project_name"])
```

**결과:**
- `config.yaml`의 `langsmith_enabled: true` → LangSmith 자동 활성화
- `config.yaml`의 `langsmith_project_name` → 프로젝트명 자동 설정
- `.env`의 `LANGSMITH_API_KEY` → 인증

---

## 🔧 환경별 설정 예시

### 로컬 개발 환경
**`config.yaml`:**
```yaml
langsmith_enabled: true
langsmith_project_name: "ai-guardrail-dev"
```

**`.env`:**
```env
LANGSMITH_API_KEY=lsv2_pt_dev_key
```

---

### 스테이징 환경 (Azure Web App)
**`config.yaml`:** (Git에 커밋)
```yaml
langsmith_enabled: true
langsmith_project_name: "ai-guardrail-staging"
```

**Azure App Settings:** (Azure Portal에서 설정)
```
LANGSMITH_API_KEY=lsv2_pt_staging_key
```

---

### 프로덕션 환경 (개인정보 주의)
**`config.yaml`:**
```yaml
langsmith_enabled: false  # 프로덕션에서는 비활성화 권장
```

**이유:** LangSmith는 모든 입력/출력을 로깅하므로 개인정보가 포함될 수 있음

---

## 📊 사용 방법

### 대시보드 접속
1. [https://smith.langchain.com/](https://smith.langchain.com/) 로그인
2. 프로젝트 선택: `ai-guardrail-mvp` (또는 설정한 프로젝트명)
3. Runs 탭에서 실행 기록 확인

### 확인 가능한 정보
```
check_guardrail (Total: 2.5초)
├── retriever.invoke        → 0.3초
├── limit_docs_with_metadata → 0.01초
├── prompt.format           → 0.01초
├── llm.invoke              → 2.1초 (입력 150 토큰, 출력 50 토큰)
└── output_parser.parse     → 0.08초
```

---

## 🎛️ 온/오프 제어

### LangSmith 비활성화
`config.yaml`에서:
```yaml
langsmith_enabled: false  # 한 줄만 수정
```

**효과:** 앱 재시작 시 LangSmith 추적 완전 중단

### 환경별 분리
```yaml
# config-dev.yaml
langsmith_enabled: true
langsmith_project_name: "dev"

# config-prod.yaml
langsmith_enabled: false
```

---

## ✅ 장점 요약

| 항목 | 환경 변수만 | CONFIG 활용 | 개선 |
|------|------------|------------|------|
| **설정 가시성** | ❌ 숨겨짐 | ✅ 명확함 | +100% |
| **팀 공유** | ❌ 각자 설정 | ✅ Git 공유 | +100% |
| **환경별 관리** | ⚠️ 복잡 | ✅ 쉬움 | +80% |
| **온/오프 제어** | ⚠️ .env 수정 | ✅ 한 줄 | +90% |

---

## 🔐 보안 Best Practice

### ✅ 권장
```yaml
# config.yaml (Git 커밋 ✅)
langsmith_enabled: true
langsmith_project_name: "my-project"
```
```env
# .env (Git 무시 ✅)
LANGSMITH_API_KEY=lsv2_pt_secret_key
```

### ❌ 비권장
```yaml
# config.yaml (Git 커밋 ❌ 위험!)
langsmith_api_key: "lsv2_pt_secret_key"  # 절대 이렇게 하지 마세요!
```

---

## 🎉 결론

**CONFIG 기반 설정의 장점:**
- ✅ 팀원 모두 동일한 프로젝트명 사용
- ✅ 환경별 설정 한눈에 확인
- ✅ 온/오프 제어 간편
- ✅ Git으로 설정 변경 이력 추적
- ✅ 민감 정보는 여전히 안전하게 보호

**이제 설정 관리가 훨씬 편해졌습니다!** 🚀
