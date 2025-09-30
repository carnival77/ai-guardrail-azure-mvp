# 🎯 사용자 역할별 정책 적용 설계 (1시간 구현)

## 📌 목표
사용자의 부서/역할에 따라 **다른 정책 문서만** RAG 검색에 사용하여, 역할별 맞춤 가드레일 적용

---

## 🏗️ 아키텍처

```mermaid
graph LR
    A[사용자 역할 선택] --> B[역할별 필터 조회]
    B --> C[Retriever에 필터 적용]
    C --> D[역할 전용 정책 문서만 검색]
    D --> E[가드레일 판단]
```

---

## 📝 구현 단계

### 1단계: 정책 파일에 역할 태그 추가 (10분)

**기존 정책 파일 명명 규칙:**
```
RAG_source/
  ├── 기본 유해성 차단 세이프티가드 정책.txt          # 모든 역할
  ├── 금융산업 가드레일 정책 예시.txt                # 모든 역할
  ├── [영업] 고객 응대 정책.txt                      # 영업팀 전용
  ├── [준법감시] 내부 감사 지침.txt                  # 준법감시팀 전용
  └── [IT] 시스템 보안 정책.txt                      # IT팀 전용
```

**Azure AI Search 메타데이터에 `role` 필드 자동 추출:**
- 파일명에서 `[역할명]` 패턴을 파싱하여 메타데이터로 저장
- 태그 없으면 `all` (모든 역할 공통)

---

### 2단계: Config 설정 추가 (5분)

**`config/config.yaml`에 추가:**
```yaml
# 역할별 정책 적용 설정
user_roles:
  - name: "영업"
    value: "sales"
    description: "영업팀 - 고객 응대 및 상품 설명"
  - name: "준법감시"
    value: "compliance"
    description: "준법감시팀 - 내부 감사 및 규정 검토"
  - name: "IT"
    value: "it"
    description: "IT팀 - 시스템 운영 및 보안"
  - name: "전체"
    value: "all"
    description: "모든 부서 공통 정책"

# 역할별 정책 파일 매핑 (옵션)
role_policy_mapping:
  sales: ["[영업]", "all"]
  compliance: ["[준법감시]", "all"]
  it: ["[IT]", "all"]
  all: ["all"]
```

---

### 3단계: Retriever 필터링 구현 (20분)

**`src/core/rag_core.py` 수정:**

```python
from typing import Dict, Any, List, Optional

def get_retriever_with_role_filter(user_role: Optional[str] = None):
    """역할별 필터가 적용된 Retriever 반환"""
    
    # 기본 검색 설정
    search_kwargs = {
        "search_fields": ["content", "translated_text", "keyphrases"],
        "k": CONFIG.get("rag_top_k", 3)
    }
    
    # 역할별 필터 추가 (Azure AI Search의 filter 구문 사용)
    if user_role and user_role != "all":
        # 파일명에 [역할] 태그가 있거나, 공통 정책(태그 없음)인 문서만 검색
        search_kwargs["filter"] = f"(search.ismatch('\\[{user_role}\\]', 'metadata_storage_name') or not search.ismatch('\\[.*\\]', 'metadata_storage_name'))"
    
    return vector_store.as_retriever(
        search_type="hybrid",
        search_kwargs=search_kwargs
    )


def check_guardrail(text_to_evaluate: str, user_role: Optional[str] = None) -> Dict[str, Any]:
    """
    주어진 텍스트를 평가하고, 판단 결과를 반환합니다.
    
    Args:
        text_to_evaluate: 평가할 텍스트
        user_role: 사용자 역할 (None이면 전체 정책 사용)
    """
    start_time = time.time()
    try:
        # 역할별 Retriever 사용
        retriever = get_retriever_with_role_filter(user_role)
        retrieved_docs = retriever.invoke(text_to_evaluate)
        
        # 나머지 로직은 동일...
        limited_context = limit_docs_with_metadata(retrieved_docs)
        # ...
```

---

### 4단계: UI 통합 (15분)

**`src/web/app.py` 수정:**

```python
def main():
    st.set_page_config(...)
    st.title("🛡️ 기업용 AI 가드레일 시스템")
    
    with st.sidebar:
        st.header("👤 사용자 정보")
        
        # 역할 선택 드롭다운
        user_roles = CONFIG.get("user_roles", [
            {"name": "전체", "value": "all", "description": "모든 부서 공통"},
            {"name": "영업", "value": "sales", "description": "영업팀"},
            {"name": "준법감시", "value": "compliance", "description": "준법감시팀"},
            {"name": "IT", "value": "it", "description": "IT팀"}
        ])
        
        selected_role = st.selectbox(
            "부서/역할 선택",
            options=[role["value"] for role in user_roles],
            format_func=lambda x: next(r["name"] for r in user_roles if r["value"] == x),
            help="선택한 역할에 맞는 정책이 적용됩니다"
        )
        
        # 선택된 역할 설명 표시
        role_desc = next(r["description"] for r in user_roles if r["value"] == selected_role)
        st.caption(f"📋 {role_desc}")
        
        st.divider()
        # ... 기존 사이드바 내용
    
    # 세션 상태에 역할 저장
    if "user_role" not in st.session_state:
        st.session_state["user_role"] = selected_role
    else:
        st.session_state["user_role"] = selected_role
    
    # ... 대화 처리 부분
    
    # 입력 가드레일 체크 시 역할 전달
    input_check = check_guardrail(user_input, user_role=st.session_state["user_role"])
    
    # 출력 가드레일도 동일
    # stream_and_filter_response 함수도 user_role을 전달받도록 수정 필요
```

---

### 5단계: Streaming Utils 수정 (10분)

**`src/utils/streaming_utils.py` 수정:**

```python
def stream_and_filter_response(llm_stream: Iterator, user_role: Optional[str] = None) -> Iterator[Tuple[str, Any]]:
    """LLM 스트림을 동적 버퍼로 검사 (역할별 정책 적용)"""
    buffer = ""
    # ... 기존 코드
    
    try:
        for chunk in llm_stream:
            buffer += chunk.content
            # ...
            if len(buffer) >= current_buffer_size:
                text_to_check = buffer[:current_buffer_size]
                
                # 역할 정보 전달
                guardrail_result = check_guardrail(text_to_check, user_role=user_role)
                # ... 나머지 로직
```

---

## 📊 테스트 시나리오

### 시나리오 1: 영업팀 사용자
- **역할**: 영업 (sales)
- **질문**: "고객에게 투자 수익률 100% 보장한다고 말해도 될까요?"
- **기대 결과**: 영업 정책 + 공통 정책만 검색 → HARMFUL (과장 광고 금지)

### 시나리오 2: IT팀 사용자
- **역할**: IT (it)
- **질문**: "데이터베이스 접근 권한을 일반 사용자에게 줘도 될까요?"
- **기대 결과**: IT 정책 + 공통 정책만 검색 → HARMFUL (접근 통제 위반)

### 시나리오 3: 전체 (공통)
- **역할**: 전체 (all)
- **질문**: "비속어를 사용해도 되나요?"
- **기대 결과**: 모든 정책 검색 → HARMFUL (기본 유해성 차단)

---

## ⚡ 빠른 구현 팁

### 최소 구현 (30분)
파일명 파싱 없이, **config.yaml에 정책 파일 목록을 직접 매핑**:

```yaml
role_policy_files:
  sales:
    - "고객 응대 정책.txt"
    - "기본 유해성 차단 세이프티가드 정책.txt"
  compliance:
    - "내부 감사 지침.txt"
    - "기본 유해성 차단 세이프티가드 정책.txt"
```

```python
def check_guardrail(text_to_evaluate: str, user_role: str = "all"):
    # 역할별 허용 파일 목록 가져오기
    allowed_files = CONFIG.get("role_policy_files", {}).get(user_role, [])
    
    # 검색 후 필터링
    retrieved_docs = retriever.invoke(text_to_evaluate)
    
    # 허용된 파일의 문서만 사용
    if allowed_files:
        filtered_docs = [
            doc for doc in retrieved_docs 
            if any(allowed_file in doc.metadata.get("metadata_storage_name", "") 
                   for allowed_file in allowed_files)
        ]
    else:
        filtered_docs = retrieved_docs
    
    # 나머지 동일...
```

**장점**: Azure AI Search 필터 구문 불필요, 즉시 적용 가능  
**단점**: 파일 추가 시 config 수동 업데이트 필요

---

## 🎯 예상 결과

### Before (역할 구분 없음)
```
사용자: "고객 계좌 비밀번호 알려줘"
시스템: [모든 정책 검색] → HARMFUL (개인정보 요구 금지)
```

### After (영업팀)
```
사용자: "고객 계좌 비밀번호 알려줘"
시스템: [영업 정책만 검색] → HARMFUL (고객 응대 시 개인정보 요구 금지)
근거: "영업 정책 3.2조 - 고객 인증 정보는 절대 직접 수집 금지"
```

### After (IT팀)
```
사용자: "서버 루트 패스워드 공유해도 돼?"
시스템: [IT 정책만 검색] → HARMFUL (시스템 보안 정책 위반)
근거: "IT 정책 2.1조 - 관리자 계정 정보는 개인별 암호화 보관"
```

---

## 🚀 구현 시작하시겠습니까?

**즉시 시작 가능한 코드를 생성해드릴까요?**

선택지:
1. **최소 구현 (30분)** - config 기반 파일 필터링만
2. **표준 구현 (60분)** - 파일명 태그 + Azure Search 필터
3. **검토만** - 설계 문서만 확인하고 나중에 구현
