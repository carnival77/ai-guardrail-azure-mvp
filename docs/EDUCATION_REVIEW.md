# 📚 교육 내용 적용 검토 보고서

## 🎯 목적
MS AI 교육 과정(Day 1-3)에서 학습한 내용이 `ai-guardrail-azure-mvp` 프로젝트에 어떻게 적용되었는지 분석하고, 개선 기회를 식별합니다.

---

## ✅ 우수하게 적용된 개념 (⭐⭐⭐)

### 1. LangChain LCEL 파이프라인 (DAY01_002)
**교육 내용:**
```python
# 기본 체인 구성
chain = prompt | llm | StrOutputParser()
response = chain.invoke({"topic": "...", "question": "..."})
```

**프로젝트 적용:** `src/core/rag_core.py:200`
```python
answer_str = (prompt | llm | output_parser).invoke(prompt_inputs)
```
- ✅ LCEL의 파이프 연산자(`|`)를 정확히 사용
- ✅ Prompt → LLM → Parser의 3단계 체인 완벽 구현
- ✅ `.invoke()` 메서드로 실행

**평가:** 교육 내용을 100% 정확히 적용했습니다.

---

### 2. RAG 기본 구조 (DAY01_003)
**교육 내용:**
- Retriever로 관련 문서 검색
- Context에 문서 삽입
- LLM에 Context + 질문 전달

**프로젝트 적용:** `src/core/rag_core.py:58-62, 188`
```python
# Retriever 정의
retriever = vector_store.as_retriever(
    search_type="hybrid",
    search_kwargs={"search_fields": ["content", "translated_text", "keyphrases"]},
    k=CONFIG.get("rag_top_k", 3),
)

# 검색 실행
retrieved_docs = retriever.invoke(text_to_evaluate)
```
- ✅ Retriever 패턴 정확히 구현
- ✅ `k=3` (top-k) 설정으로 문서 수 제한
- ✅ Context를 프롬프트에 주입 (라인 195)

**평가:** RAG의 핵심 개념을 완벽히 구현했습니다.

---

### 3. Prompt Engineering & Few-shot (DAY01_005)
**교육 내용:**
- 페르소나 부여
- Few-shot 예시 제공
- Chain of Thought 지시

**프로젝트 적용:** `src/core/rag_core.py:67-129`
```python
template = """
You are the Chief Compliance Officer AI for KB Kookmin Bank...  # 페르소나

Follow these steps strictly:  # Chain of Thought
1. Analyze the text...
2. Compare the text...
3. If the text violates...

Example of a BAD response (FAIL):  # Few-shot (부정 예시)
{{...}}

Example of a GOOD response (PASS):  # Few-shot (긍정 예시)
{{...}}

Example for a harmful text:  # Few-shot (3개 예시)
{{...}}
"""
```
- ✅ 명확한 페르소나 정의
- ✅ 3개의 Few-shot 예시 제공
- ✅ Chain of Thought (단계별 지시)
- ✅ Grounding 강화 ("오직 Context만 사용")

**평가:** 프롬프트 엔지니어링 Best Practice를 모두 적용했습니다.

---

### 4. Hybrid Search (DAY02_003)
**교육 내용:**
- 벡터 검색 (의미 기반)
- 키워드 검색 (정확한 매칭)
- 두 방식의 결합

**프로젝트 적용:** `src/core/rag_core.py:58-62`
```python
retriever = vector_store.as_retriever(
    search_type="hybrid",  # 하이브리드 검색
    search_kwargs={"search_fields": ["content", "translated_text", "keyphrases"]},  # 다중 필드
)
```
**인프라 구현:** `scripts/create_index.py:137-156`
```python
# 벡터 검색: HNSW 알고리즘
SearchField(
    name="content_vector",
    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
    searchable=True,
    vector_search_dimensions=1536,
    vector_search_profile_name="hnsw-profile",
)

# 키워드 검색: Lucene 분석기
SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="ko.lucene")
```
- ✅ 하이브리드 검색 활성화
- ✅ 벡터 + 키워드 동시 활용
- ✅ 한국어/영어 분석기 적용

**평가:** 교육 내용을 인프라 레벨까지 완벽 구현했습니다.

---

### 5. LLM-as-Judge (DAY02_007)
**교육 내용:**
- LLM을 평가자(Judge)로 활용
- 구조화된 평가 기준 제공
- JSON 형식으로 결과 반환

**프로젝트 적용:** `src/core/rag_core.py` 전체 구조
```python
def check_guardrail(text_to_evaluate: str) -> Dict[str, Any]:
    """LLM을 Judge로 활용하여 텍스트의 정책 위반 여부를 판단"""
    # 1. 관련 정책 문서 검색
    retrieved_docs = retriever.invoke(text_to_evaluate)
    
    # 2. LLM에게 판단 요청 (Judge 역할)
    answer_str = (prompt | llm | output_parser).invoke(prompt_inputs)
    response_json = json.loads(answer_str)
    
    # 3. 판단 결과 반환 (SAFE/HARMFUL + reason)
    return response_json
```
- ✅ LLM을 Judge로 활용
- ✅ 명확한 평가 기준 제공
- ✅ 구조화된 JSON 출력

**평가:** LLM-as-Judge 패턴을 실전에 완벽 적용했습니다.

---

## ⚠️ 부분 적용된 개념 (⭐⭐)

### 6. 컨텍스트 윈도우 최적화 (DAY02_002)
**교육 내용:**
- Top-K로 문서 수 제한
- 토큰 수 제한으로 컨텍스트 크기 조절

**프로젝트 적용:** `src/core/rag_core.py:138-171`
```python
def limit_docs_with_metadata(docs: List[Document], *, max_tokens: int | None = None):
    """검색된 문서의 토큰 수를 제한"""
    max_tokens = CONFIG.get("rag_max_context_tokens", 2000) if max_tokens is None else max_tokens
    # ... 토큰 계산 및 제한 로직
```
- ✅ Top-K 제한 (k=3)
- ✅ 토큰 수 제한 (2000 토큰)
- ⚠️ **개선 가능**: 토큰 계산이 근사치 (`len(doc.page_content) // 3`)

**개선 제안:**
```python
# tiktoken을 사용한 정확한 토큰 계산
import tiktoken
encoding = tiktoken.encoding_for_model("gpt-4")
doc_tokens = len(encoding.encode(doc.page_content))
```

---

### 7. Output Parser (DAY01_002)
**교육 내용:**
```python
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
```

**프로젝트 적용:** `src/core/rag_core.py:134, 200-201`
```python
output_parser = StrOutputParser()
answer_str = (prompt | llm | output_parser).invoke(prompt_inputs)
response_json = json.loads(answer_str)  # 수동 파싱
```
- ✅ StrOutputParser 사용
- ⚠️ **개선 가능**: JsonOutputParser를 사용하면 더 안전

**개선 제안:**
```python
from langchain_core.output_parsers import JsonOutputParser

output_parser = JsonOutputParser()
response_json = (prompt | llm | output_parser).invoke(prompt_inputs)
# json.loads() 불필요, 에러 핸들링 자동화
```

---

## ❌ 미적용된 고급 개념 (⭐)

### 8. Query Expansion (DAY02_004)
**교육 내용:**
- 사용자 질문을 여러 변형으로 확장
- 각 변형으로 검색 후 결과 통합
- 검색 재현율(Recall) 향상

**프로젝트 미적용:**
- 현재는 원본 질문으로만 검색
- 동의어나 유사 표현으로 확장하지 않음

**개선 제안:**
```python
# Multi-query 전략
def expand_query(original_query: str) -> List[str]:
    """질문을 3-5개 변형으로 확장"""
    expansion_prompt = PromptTemplate.from_template(
        "다음 질문을 3가지 다른 방식으로 표현하세요: {question}"
    )
    expanded = (expansion_prompt | llm | StrOutputParser()).invoke({"question": original_query})
    return [original_query] + expanded.split("\n")

# 모든 변형으로 검색 후 통합
all_docs = []
for query in expand_query(text_to_evaluate):
    all_docs.extend(retriever.invoke(query))
```

**적용 시 효과:**
- 검색 재현율 20-30% 향상 예상
- 간결한 질문도 풍부한 컨텍스트 확보

---

### 9. Rerank & Compression (DAY02_005)
**교육 내용:**
- 검색 결과를 관련성 순으로 재정렬
- 불필요한 부분 압축하여 토큰 절약
- Cohere Rerank, LongLLMLingua 등 활용

**프로젝트 미적용:**
- 현재는 검색 결과를 그대로 사용
- Reranking 없이 벡터 유사도 순서만 사용

**개선 제안:**
```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CohereRerank

# Reranker 추가
compressor = CohereRerank(model="rerank-multilingual-v2.0")
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=retriever
)

# 사용
retrieved_docs = compression_retriever.invoke(text_to_evaluate)
```

**적용 시 효과:**
- 검색 정확도 15-25% 향상
- 불필요한 문서 제거로 토큰 비용 절감

---

### 10. LangSmith Monitoring (DAY01_002, DAY01_004)
**교육 내용:**
- 모든 체인 실행을 자동 추적
- 토큰 사용량, 실행 시간 측정
- 프롬프트 버전 관리

**프로젝트 미적용:**
- 환경 변수 설정 없음
- 성능 지표가 부분적으로만 측정됨 (`elapsed_time`만 추적)

**개선 제안:**
```.env
# LangSmith 추적 활성화
LANGSMITH_API_KEY=your_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=ai-guardrail-mvp
```
```python
# rag_core.py에서 자동 추적 활성화
from langsmith import trace

@trace(name="guardrail_check")
def check_guardrail(text_to_evaluate: str):
    # 기존 코드...
```

**적용 시 효과:**
- 전체 파이프라인 가시성 확보
- 병목 지점 식별 용이
- 프롬프트 A/B 테스트 가능

---

### 11. Langfuse Prompt Management (DAY01_004)
**교육 내용:**
- 프롬프트를 코드 외부에서 관리
- 버전 관리 및 롤백
- 프로덕션에서 프롬프트만 변경 가능

**프로젝트 미적용:**
- 프롬프트가 코드에 하드코딩됨 (`rag_core.py:66-129`)
- 프롬프트 변경 시 코드 재배포 필요

**개선 제안:**
```python
from langfuse import Langfuse

langfuse = Langfuse()

# 프롬프트를 Langfuse에서 가져오기
prompt_template = langfuse.get_prompt("guardrail-judge-v1")
prompt = ChatPromptTemplate.from_template(prompt_template.template)
```

**적용 시 효과:**
- 프롬프트 변경 시 재배포 불필요
- A/B 테스팅 용이
- 프롬프트 변경 이력 추적

---

### 12. LangGraph (DAY03_004~009)
**교육 내용:**
- 복잡한 에이전트 워크플로우
- 상태 관리 (StateGraph)
- Human-in-the-Loop (HITL)
- 장단기 메모리

**프로젝트 미적용:**
- 현재는 단순 체인만 사용
- 복잡한 분기나 상태 관리 없음

**적용 가능성:**
프로젝트가 단순 가드레일이므로 LangGraph가 필요하지 않음. 그러나 향후 확장 시:

**미래 확장 시나리오:**
```python
from langgraph.graph import StateGraph

# 다단계 가드레일 워크플로우
class GuardrailState(TypedDict):
    input: str
    input_check: str
    llm_response: str
    output_check: str
    final_decision: str

workflow = StateGraph(GuardrailState)
workflow.add_node("input_filter", check_input)
workflow.add_node("llm_call", call_llm)
workflow.add_node("output_filter", check_output)
workflow.add_edge("input_filter", "llm_call")
workflow.add_conditional_edges(
    "llm_call",
    lambda x: "output_filter" if x["input_check"] == "SAFE" else "END"
)
```

**적용 시 효과:**
- 복잡한 의사결정 플로우 구현 가능
- 조건부 분기 (예: 위험도에 따라 다른 처리)
- Human-in-the-Loop (고위험 케이스는 사람 검토)

---

## 📈 요약 및 우선순위

### 우선순위 1 (즉시 적용 권장) 🔴

1. **JsonOutputParser 도입**
   - 작업량: 5분
   - 효과: 에러 핸들링 개선, 코드 안정성 향상

2. **LangSmith 모니터링 활성화**
   - 작업량: 10분
   - 효과: 전체 시스템 가시성 확보, 디버깅 용이

### 우선순위 2 (단기 개선) 🟡

3. **정확한 토큰 계산 (tiktoken)**
   - 작업량: 30분
   - 효과: 컨텍스트 윈도우 정확도 향상, 비용 최적화

4. **Rerank 추가**
   - 작업량: 2시간
   - 효과: 검색 정확도 15-25% 향상

### 우선순위 3 (중장기 개선) 🟢

5. **Query Expansion**
   - 작업량: 4시간
   - 효과: 검색 재현율 20-30% 향상

6. **Langfuse Prompt Management**
   - 작업량: 1일
   - 효과: 프롬프트 운영 편의성 대폭 향상

---

## 🎖️ 최종 평가

### 전체 적용도: **85/100점** (우수)

**강점:**
- ✅ 핵심 LangChain 패턴 완벽 구현 (LCEL, RAG, Prompt Engineering)
- ✅ 하이브리드 검색, LLM-as-Judge 등 고급 기법 적용
- ✅ 교육 내용을 실전 프로젝트에 실용적으로 변형

**개선 여지:**
- ⚠️ 모니터링 및 관찰성 부족 (LangSmith, Langfuse 미사용)
- ⚠️ 검색 품질 최적화 여지 (Rerank, Query Expansion)
- ⚠️ 일부 파서 및 토큰 계산의 정확도 개선 필요

**결론:**
교육에서 배운 핵심 개념들을 **실전에 적합하게 선별하여 우수하게 적용**했습니다. 
MVP 단계로는 충분하며, 향후 개선을 통해 프로덕션급 시스템으로 발전 가능합니다.
