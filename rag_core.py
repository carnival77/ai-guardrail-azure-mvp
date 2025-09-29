import openai
import json
import os
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

# --- 1. 환경 설정 및 Azure 서비스 클라이언트 초기화 ---
load_dotenv()

# Azure OpenAI 클라이언트 초기화 (LLM 및 임베딩 모델)
openai.api_type = os.getenv("AZURE_OPENAI_API_TYPE", "azure")
openai.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
openai.api_key = os.getenv("AZURE_OPENAI_API_KEY")
openai.azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4.1")
openai.azure_embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
openai.azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
openai.azure_search_key = os.getenv("AZURE_SEARCH_API_KEY")
openai.azure_search_index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

llm=AzureChatOpenAI(
        azure_endpoint=openai.azure_endpoint,
        api_key=openai.api_key,
        api_version=openai.api_version,
        azure_deployment=openai.azure_deployment,
        temperature=0,
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

The final output must be a JSON object with two keys: "decision" and "reason".
Example for a harmful text:
{{
  "decision": "HARMFUL",
  "reason": "The text violates policy 1.1 (불완전판매 방지) by using misleading terms like '100%' and '확정 수익'."
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
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | output_parser
)


# --- 4. 가드레일 실행 함수 정의 ---
def check_guardrail(text_to_evaluate: str) -> Dict[str, Any]:
    """
    주어진 텍스트에 대해 AI 가드레일 정책 위반 여부를 검사합니다.

    Args:
        text_to_evaluate: 검사할 텍스트 (사용자 질문 또는 LLM 답변).

    Returns:
        A dictionary containing the decision ('SAFE', 'HARMFUL', 'CANNOT_DETERMINE')
        and the reason for the decision.
    """
    try:
        # RAG 체인을 실행하여 LLM의 판단 결과를 얻음
        response_str = rag_chain.invoke(text_to_evaluate)
        # LLM이 생성한 JSON 문자열을 파싱
        response_json = json.loads(response_str)
        return response_json
    except json.JSONDecodeError:
        # LLM이 유효한 JSON을 생성하지 못한 경우
        return {"decision": "ERROR", "reason": "Failed to parse LLM response as JSON."}
    except Exception as e:
        # 기타 예외 처리
        return {"decision": "ERROR", "reason": f"An unexpected error occurred: {e}"}


if __name__ == "__main__":
    # 라이브러리로 사용될 때는 실행되지 않음
    print("AI 가드레일 RAG 시스템이 초기화되었습니다.")
    print("사용법: from rag_core import check_guardrail")
    print("테스트: python test_guardrail.py 실행")
