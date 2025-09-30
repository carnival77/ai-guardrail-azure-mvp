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
)

# 2.2. 프롬프트 템플릿(Prompt Template) 정의
# 플레이그라운드에서 사용했던 시스템 프롬프트를 코드로 구현
template = """
You are an AI assistant designed to act as a financial security guardrail.
Your sole purpose is to determine if a given text violates any of the policies provided in the retrieved context.
Answer ONLY based on the provided context.

First, state your decision clearly as "SAFE" or "HARMFUL".
Then, explain the reason for your decision by citing the specific policy number and content.
If the provided context is insufficient to make a judgment, you must respond with "CANNOT_DETERMINE".

IMPORTANT: You must also specify which source document(s) you actually used to make your decision.
Extract the filename from the metadata_storage_path or metadata_storage_name in the context.

The final output must be a JSON object with three keys: "decision", "reason", and "source_files".
Example for a harmful text:
{{
  "decision": "HARMFUL",
  "reason": "The text violates policy 1.1 (불완전판매 방지) by using misleading terms like '100%' and '확정 수익'.",
  "source_files": ["bank_policy.txt"]
}}

Example for a safe text:
{{
  "decision": "SAFE",
  "reason": "The text is a general inquiry about banking services and does not violate any policies.",
  "source_files": ["bank_policy.txt"]
}}

Context from policy documents:
{context}

Text to be evaluated:
{question}
"""
prompt = ChatPromptTemplate.from_template(template)

# 2.3. 출력 파서(Output Parser) 정의
# LLM의 JSON 형식 응답을 Python 딕셔너리로 파싱
output_parser = StrOutputParser()


# --- 3. LCEL을 이용한 전체 RAG 체인(Chain) 결합 ---
# LangChain Expression Language (LCEL)를 사용하여 각 컴포넌트를 파이프로 연결
# 체인을 수정하여 검색된 문서(context)가 최종 결과에 포함되도록 합니다.
rag_chain_with_source = RunnableParallel(
    {"context": retriever, "question": RunnablePassthrough()}
).assign(
    answer=prompt | llm | output_parser
)


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
        # 수정된 체인을 호출합니다.
        response = rag_chain_with_source.invoke(text_to_evaluate)
        
        # LLM의 답변(JSON 문자열)과 근거 문서를 추출합니다.
        response_str = response.get("answer", "{}")
        source_documents: List[Document] = response.get("context", [])
        
        response_json = json.loads(response_str)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 반환 객체에 소요 시간과 근거 문서를 추가합니다.
        response_json["elapsed_time"] = elapsed_time
        response_json["source_documents"] = source_documents
        
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
