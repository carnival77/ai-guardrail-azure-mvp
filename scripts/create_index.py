import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    ComplexField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)
from dotenv import load_dotenv
from config.config_loader import CONFIG

# --- 1. 필수 정보 로드 ---
load_dotenv()

search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT")
search_api_key: str = os.getenv("AZURE_SEARCH_API_KEY")
index_name: str = CONFIG["azure_search_index_name"]

if not all([search_endpoint, search_api_key, index_name]):
    raise ValueError("환경변수가 올바르게 설정되지 않았습니다. .env 파일을 확인해주세요.")

# --- 2. 클라이언트 연결 ---
credential = AzureKeyCredential(search_api_key)
index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)


# --- 3. 인덱스 스키마 정의 (모든 설정 포함) ---
fields = [
    # 문서의 고유 ID 역할을 하는 키 필드
    SimpleField(name="metadata_storage_path", 
                type=SearchFieldDataType.String, 
                key=True),
    # RAG의 컨텍스트 및 한국어 키워드 검색을 위한 필드
    SearchableField(name="content",
                    type=SearchFieldDataType.String, 
                    retrievable=True, 
                    analyzer_name="ko.lucene"),
    # 영어 키워드 검색을 위한 필드
    SearchableField(
        name="translated_text", 
        type=SearchFieldDataType.String, 
        retrievable=True, 
        analyzer_name="en.lucene"
    ),
    # people 필드 (필요 시 활성화)
    SearchableField(
        name="people",
        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
        retrievable=True,
        filterable=False,
        facetable=False,
        analyzer_name="ko.lucene",
    ),
    # locations 필드
    SearchableField(
        name="locations",
        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
        retrievable=True,
        filterable=False,
        facetable=False,
        analyzer_name="ko.lucene",
    ),
    # keyphrases 필드
    SearchableField(
        name="keyphrases",
        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
        retrievable=True,
        filterable=False,
        facetable=False,
        analyzer_name="ko.lucene",
    ),
    # organizations 필드
    SearchableField(
        name="organizations",
        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
        retrievable=True,
        filterable=False,
        facetable=False,
        analyzer_name="ko.lucene",
    ),
    # metadata_storage_name: retrievable=True로 변경 (UI 파일명 표기 편의)
    SimpleField(
        name="metadata_storage_name",
        type=SearchFieldDataType.String,
        retrievable=True,
    ),
    # language 필드 추가 (최적화)
    SearchableField(
        name="language",
        type=SearchFieldDataType.String,
        retrievable=True,
        filterable=True,
        facetable=True,
        analyzer_name="ko.lucene",
    ),
    # 개인정보 탐지(PII) 결과를 저장하기 위한 복합 필드
    ComplexField(
        name="pii_entities",
        collection=True,
        fields=[
            SearchableField(name="text", type=SearchFieldDataType.String, retrievable=True, analyzer_name="ko.lucene"),
            SearchableField(
                name="type",
                type=SearchFieldDataType.String,
                retrievable=True,
                filterable=False,
                facetable=False,
                analyzer_name="ko.lucene",
            ),
            SearchableField(
                name="subtype",
                type=SearchFieldDataType.String,
                retrievable=True,
                filterable=False,
                facetable=False,
                analyzer_name="ko.lucene",
            ),
            SimpleField(name="offset", type=SearchFieldDataType.Int32, retrievable=True),
            SimpleField(name="length", type=SearchFieldDataType.Int32, retrievable=True),
            SimpleField(name="score", type=SearchFieldDataType.Double, retrievable=True),
        ],
    ),
    # masked_text: analyzer=ko.lucene (한국어 마스킹 텍스트 검색)
    SearchableField(name="masked_text", type=SearchFieldDataType.String, retrievable=True, analyzer_name="ko.lucene"),
    # content_vector: searchable=False, retrievable=False (벡터 전용)
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=1536,
        vector_search_profile_name="hnsw-profile",
    ),
]

# --- 4. 벡터 검색 프로필 정의 ---
vector_search = VectorSearch(
    profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-config")],
    algorithms=[
        HnswAlgorithmConfiguration(
            name="hnsw-config",
            kind="hnsw",
            parameters={"metric": "cosine", "m": 12, "efConstruction": 200, "efSearch": 150},
        )
    ],
)

# --- 5. 인덱스 객체 생성 ---
index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)

# --- 6. 인덱스 생성 또는 업데이트 ---
try:
    print(f"'{index_name}' 인덱스를 생성 또는 업데이트합니다...")
    result = index_client.create_or_update_index(index)
    print(f"'{result.name}' 인덱스가 성공적으로 생성/업데이트되었습니다.")
    print("이제 AI Search 인덱스가 하이브리드 검색을 수행할 모든 준비를 마쳤습니다.")
except Exception as e:
    print(f"인덱스 생성 중 오류가 발생했습니다: {e}")
