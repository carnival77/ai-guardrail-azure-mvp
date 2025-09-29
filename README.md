# 🛡️ 기업용 AI 가드레일 시스템

Azure OpenAI와 Azure AI Search를 활용한 금융 정책 기반 AI 가드레일 MVP 시스템

## 📁 프로젝트 구조

```
ai-guardrail-azure-mvp/
├── src/                    # 소스 코드
│   ├── core/              # 핵심 RAG 로직
│   │   └── rag_core.py    # RAG 파이프라인 및 가드레일 검사
│   ├── utils/             # 유틸리티 함수들
│   │   └── streaming_utils.py  # 동적 버퍼링 스트리밍
│   └── web/               # 웹 애플리케이션
│       └── app.py         # Streamlit UI
├── config/                # 설정 파일들
│   ├── config.yaml        # 애플리케이션 설정
│   └── config_loader.py   # 설정 로더
├── scripts/               # 유틸리티 스크립트들
│   ├── create_index.py    # Azure AI Search 인덱스 생성
│   ├── create_skillset.py # Azure AI Search 스킬셋 생성
│   └── upload_to_blob.py  # RAG 소스 파일 업로드
├── tests/                 # 테스트 파일들
│   └── test_guardrail.py  # 가드레일 기능 테스트
├── RAG_source/           # RAG 정책 소스 파일들
│   ├── bank_policy.txt
│   └── default_safety_guard.txt
├── docs/                 # 문서
├── main.py              # 메인 실행 파일
├── requirements.txt     # Python 의존성
└── .env                 # 환경 변수 (git에서 제외)
```

## 🚀 실행 방법

모든 기능은 `main.py`를 통해 통합 실행됩니다:

### 웹 애플리케이션 실행
```bash
python main.py app
```

### 테스트 실행
```bash
python main.py test
```

### 인프라 스크립트 실행
```bash
# Azure AI Search 인덱스 생성
python main.py create-index

# Azure AI Search 스킬셋 생성
python main.py create-skillset

# RAG 소스 파일 업로드
python main.py upload-rag --dry-run  # 미리보기
python main.py upload-rag            # 실제 업로드
```

### 사용 가능한 명령어 확인
```bash
python main.py  # 도움말 표시
```

## 📋 주요 기능

- **이중 가드레일**: 입력과 출력 모두에서 정책 위반 검사
- **동적 버퍼링**: 실시간 스트리밍 중 점진적 안전성 검증
- **하이브리드 검색**: 벡터 검색과 키워드 검색의 조합
- **정책 관리**: RAG 기반 정책 문서 자동 업데이트

## ⚙️ 환경 설정

`.env` 파일에 다음 환경 변수들을 설정하세요:

```env
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_SEARCH_ENDPOINT=your_search_endpoint
AZURE_SEARCH_API_KEY=your_search_key
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection
```
