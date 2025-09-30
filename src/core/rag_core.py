import openai
import json
import os
import time  # 시간 측정을 위해 time 모듈 import
from typing import Dict, Any, List

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from config.config_loader import CONFIG

# --- 1. 환경 설정 및 Azure 서비스 클라이언트 초기화 ---
load_dotenv()

# 민감 정보는 환경 변수에서, 비민감 설정은 config에서 가져오기
openai.api_type = os.getenv("AZURE_OPENAI_API_TYPE", "azure")
openai.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_version = CONFIG["azure_openai_api_version"]
openai.api_key = os.getenv("AZURE_OPENAI_API_KEY")
openai.azure_deployment = CONFIG["azure_openai_chat_deployment_name"]
openai.azure_embedding_deployment = CONFIG["azure_openai_embedding_deployment_name"]
openai.azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
openai.azure_search_key = os.getenv("AZURE_SEARCH_API_KEY")
openai.azure_search_index_name = CONFIG["azure_search_index_name"]

# Azure OpenAI 클라이언트 초기화
llm = AzureChatOpenAI(
    azure_endpoint=openai.azure_endpoint,
    api_key=openai.api_key,
    api_version=openai.api_version,
    azure_deployment=openai.azure_deployment,
    temperature=CONFIG["llm_temperature"],
    max_retries=CONFIG["llm_max_retries"],
    timeout=CONFIG["llm_timeout"],
)

embeddings = AzureOpenAIEmbeddings(
    azure_deployment=openai.azure_embedding_deployment,
)

# Azure AI Search 벡터 스토어 클라이언트 초기화
vector_store = AzureSearch(
    azure_search_endpoint=openai.azure_search_endpoint,
    azure_search_key=openai.azure_search_key,
    index_name=openai.azure_search_index_name,
    embedding_function=embeddings.embed_query,
)


# --- 2. RAG 파이프라인의 각 컴포넌트 정의 ---

# 2.1. 리트리버(Retriever) 정의: 하이브리드 검색 활성화
# search_type="hybrid"로 설정하고, search_kwargs로 키워드 검색 대상 필드를 명시
retriever = vector_store.as_retriever(
    search_type="hybrid",
    search_kwargs={"search_fields": ["content", "translated_text", "keyphrases"]},
    k=CONFIG.get("rag_top_k", 3),
)

# 2.2. 프롬프트 템플릿(Prompt Template) 정의
# 플레이그라운드에서 사용했던 시스템 프롬프트를 코드로 구현
template = """
You are the Chief Compliance Officer AI for KB Kookmin Bank, an expert in financial regulations and security policies.
Your mission is to analyze a given text and determine if it violates any internal policies provided **exclusively from the context below.**

Follow these steps strictly:
1.  Analyze the text to be evaluated.
2.  Compare the text against the policies in the provided context. Your decision MUST be based solely on this context.
3.  If the text violates a specific policy from the context, make a "HARMFUL" judgment.
4.  If the text does not violate any policy from the context, make a "SAFE" judgment.
5.  If the context is insufficient or irrelevant to make a judgment, you must explain this in the reason and still output a "SAFE" decision, as no specific policy was violated.

Your final output MUST be a single, raw JSON object. Do not add any text before or after it.

**CRITICAL RULES:**
1.  **Grounding:** Your `reason` MUST directly quote or reference the specific policy text from the `Context`.
2.  **Citation:** You MUST populate the `source_files` list with the filename(s) from the context that justify your decision. This is not optional.
3.  **No Outside Knowledge:** Do not use any external knowledge. If the context doesn't prohibit an action, it is considered "SAFE".
4.  **Reward:** If you cite the source accurately and clearly in 'source_files', we will give you candy as a reward.

**Example of a BAD response (FAIL):**
{{
  "decision": "HARMFUL",
  "reason": "Asking for a password is not allowed.",
  "source_files": []
}}
Why it's BAD: The `source_files` list is empty, even though the context contains relevant policy documents.

**Example of a GOOD response (PASS):**
{{
  "decision": "HARMFUL",
  "reason": "The text violates policy 2.2 by asking for an account password, which is sensitive authentication information.",
  "source_files": ["은행 가드레일 정책 예시.txt"]
}}
Why it's GOOD: The `source_files` list correctly cites the document used for the judgment.

Example for a harmful text:
{{
  "decision": "HARMFUL",
  "reason": "The text violates policy 2.2 (개인정보 수집 유도 금지) by asking for an account password, which is sensitive authentication information.",
  "source_files": ["은행 가드레일 정책 예시.txt"]
}}

Example for a safe text:
{{
  "decision": "SAFE",
  "reason": "The text is a general inquiry about mortgage products and does not violate any financial consumer protection laws or other policies from the context.",
  "source_files": ["은행 가드레일 정책 예시.txt"]
}}

Example for a text violating safety guidelines:
{{
  "decision": "HARMFUL",
  "reason": "The text includes verbal abuse such as 'stupid' and 'useless', violating the harassment policy which prohibits disparaging remarks.",
  "source_files": ["기본 유해성 차단 세이프티가드 정책.txt"]
}}

Context from policy documents:
{context}

Text to be evaluated:
{question}

Final Answer (JSON object only):
"""
prompt = ChatPromptTemplate.from_template(template)

# 2.3. 출력 파서(Output Parser) 정의
# LLM의 JSON 형식 응답을 Python 딕셔너리로 파싱
output_parser = StrOutputParser()


# --- 3. 컨텍스트 윈도우 및 top-k 제한 함수 ---
def limit_docs_with_metadata(
    docs: List[Document],
    *,
    max_tokens: int | None = None,
) -> Dict[str, Any]:
    """검색된 문서의 토큰 수를 제한하고, 문서 객체와 결합된 텍스트를 동시에 반환합니다.

    Args:
        docs: 검색된 문서 목록 (이미 retriever의 k 파라미터로 문서 수가 제한됨)
        max_tokens: 허용할 최대 토큰 수 (없으면 config 값을 사용)

    Returns:
        문서 객체 목록과 토큰 수가 제한된 결합 텍스트가 들어 있는 딕셔너리
    """
    if not docs:
        return {"documents": [], "combined_text": ""}

    config_max_tokens = CONFIG.get("rag_max_context_tokens", 2000)
    max_tokens = config_max_tokens if max_tokens is None else max_tokens

    combined_text = ""
    current_tokens = 0
    for doc in docs:
        doc_tokens = max(1, len(doc.page_content) // 3)
        if current_tokens + doc_tokens > max_tokens:
            remaining_tokens = max_tokens - current_tokens
            remaining_chars = max(0, remaining_tokens * 3)
            if remaining_chars > 100:
                combined_text += "\n\n" + doc.page_content[:remaining_chars] + "..."
            break
        combined_text += "\n\n" + doc.page_content
        current_tokens += doc_tokens

    return {"documents": docs, "combined_text": combined_text.strip()}


# --- 4. 가드레일 실행 함수 정의 ---
def check_guardrail(text_to_evaluate: str) -> Dict[str, Any]:
    """
    주어진 텍스트를 평가하고, 판단 결과, 이유, 소요 시간, 근거 문서를 반환합니다.

    Args:
        text_to_evaluate (str): 평가할 텍스트입니다.

    Returns:
        Dict[str, Any]: decision, reason, elapsed_time, source_documents를 포함하는 딕셔너리.
    """
    start_time = time.time()
    try:
        # 1. Retriever를 호출하여 문서 검색
        retrieved_docs = retriever.invoke(text_to_evaluate)
        
        # 2. 검색된 문서 수(top-k) 및 토큰 수 제한, 원본 Document 객체는 보존
        limited_context = limit_docs_with_metadata(retrieved_docs)

        # 3. LLM에 전달할 프롬프트 데이터 준비
        prompt_inputs = {
            "context": limited_context["combined_text"],
            "question": text_to_evaluate,
        }

        # 4. LLM 체인 실행
        answer_str = (prompt | llm | output_parser).invoke(prompt_inputs)
        response_json = json.loads(answer_str)

        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 5. 최종 결과에 성능 및 근거 데이터(원본 Document 객체) 추가
        response_json["elapsed_time"] = elapsed_time
        response_json["source_documents"] = limited_context["documents"]
        
        # [DEBUG] LLM이 반환한 source_files 확인
        print(f"[DEBUG] LLM source_files: {response_json.get('source_files', [])}")
        print(f"[DEBUG] Retrieved doc names: {[doc.metadata.get('metadata_storage_name', 'N/A') for doc in limited_context['documents']]}")
        
        return response_json
    
    except json.JSONDecodeError:
        end_time = time.time()
        return {
            "decision": "ERROR", 
            "reason": "Failed to parse LLM response as JSON.",
            "elapsed_time": end_time - start_time,
            "source_documents": []
        }
    except Exception as e:
        end_time = time.time()
        return {
            "decision": "ERROR", 
            "reason": f"An unexpected error occurred: {e}",
            "elapsed_time": end_time - start_time,
            "source_documents": []
        }


if __name__ == "__main__":
    # 라이브러리로 사용될 때는 실행되지 않음
    print("AI 가드레일 RAG 시스템이 초기화되었습니다.")
    print("사용법: from rag_core import check_guardrail")
    print("테스트: python test_guardrail.py 실행")
