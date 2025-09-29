import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchSkillsetClient
from azure.search.documents.indexes.models import (
    EntityRecognitionSkill,
    InputFieldMappingEntry,
    KeyPhraseExtractionSkill,
    LanguageDetectionSkill,
    OutputFieldMappingEntry,
    PIIDetectionSkill,
    SearchSkillset,
    TextTranslationSkill,
    EntityCategory,
)
from dotenv import load_dotenv
from config.config_loader import CONFIG

# --- 1. 필수 정보 로드 ---
load_dotenv()

search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT")
search_api_key: str = os.getenv("AZURE_SEARCH_API_KEY")
skillset_name: str = CONFIG["azure_skillset_name"]

if not all([search_endpoint, search_api_key]):
    raise ValueError("환경변수가 올바르게 설정되지 않았습니다. .env 파일을 확인해주세요.")

# --- 2. 클라이언트 연결 (SearchSkillsetClient 사용) ---
credential = AzureKeyCredential(search_api_key)
skillset_client = SearchSkillsetClient(endpoint=search_endpoint, credential=credential)


# --- 3. Skill 정의 ---
# Skill 1: 언어 감지 (다른 Skill들보다 먼저 실행되어야 함)
language_detection_skill = LanguageDetectionSkill(
    name="LanguageDetection",
    description="Detect the language of the document",
    context="/document",
    inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
    outputs=[OutputFieldMappingEntry(name="languageCode", targetName="language")],
)

# Skill 2: 텍스트 번역 (한국어 -> 영어)
translation_skill = TextTranslationSkill(
    name="Translation",
    description="Translate Korean content to English",
    context="/document/content",
    default_to_language_code="en",
    default_from_language_code="ko", # 원본 언어를 한국어로 명시
    inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
    outputs=[OutputFieldMappingEntry(name="translatedText", targetName="translated_text")],
)

# Skill 3: 엔터티 인식 (사람, 조직, 장소 등)
entity_recognition_skill = EntityRecognitionSkill(
    name="EntityRecognition",
    description="Recognize entities like people, organizations, locations",
    context="/document/content",
    categories=[EntityCategory.PERSON, EntityCategory.ORGANIZATION, EntityCategory.LOCATION],
    inputs=[
        InputFieldMappingEntry(name="text", source="/document/content"),
        InputFieldMappingEntry(name="languageCode", source="/document/language"), # 언어 감지 결과 사용
    ],
    outputs=[
        OutputFieldMappingEntry(name="persons", targetName="people"),
        OutputFieldMappingEntry(name="organizations", targetName="organizations"),
        OutputFieldMappingEntry(name="locations", targetName="locations"),
    ],
)

# Skill 4: 핵심 구문 추출
key_phrase_extraction_skill = KeyPhraseExtractionSkill(
    name="KeyPhraseExtraction",
    description="Extract key phrases from the document",
    context="/document/content",
    inputs=[
        InputFieldMappingEntry(name="text", source="/document/content"),
        InputFieldMappingEntry(name="languageCode", source="/document/language"), # 언어 감지 결과 사용
    ],
    outputs=[OutputFieldMappingEntry(name="keyPhrases", targetName="keyphrases")],
)

# Skill 5: 개인정보 탐지 (PII) - 가드레일의 핵심
pii_detection_skill = PIIDetectionSkill(
    name="PIIDetection",
    description="Detect Personally Identifiable Information",
    context="/document/content",
    masking_mode="replace",
    inputs=[
        InputFieldMappingEntry(name="text", source="/document/content"),
        InputFieldMappingEntry(name="languageCode", source="/document/language"), # 언어 감지 결과 사용
    ],
    outputs=[
        OutputFieldMappingEntry(name="piiEntities", targetName="pii_entities"),
        OutputFieldMappingEntry(name="maskedText", targetName="masked_text"),
    ],
)


# --- 4. 기술 집합(Skillset) 객체 생성 ---
# Skill 실행 순서가 중요: 언어 감지가 먼저 실행되어야 다른 Skill들이 그 결과를 사용할 수 있음
skillset = SearchSkillset(
    name=skillset_name,
    description="AI skillset for financial policy document processing",
    skills=[
        language_detection_skill,
        translation_skill,
        entity_recognition_skill,
        key_phrase_extraction_skill,
        pii_detection_skill,
    ],
)

# --- 5. 기술 집합 생성 또는 업데이트 ---
try:
    print(f"'{skillset_name}' 기술 집합을 생성 또는 업데이트합니다...")
    result = skillset_client.create_or_update_skillset(skillset=skillset)
    print(f"'{result.name}' 기술 집합이 성공적으로 생성/업데이트되었습니다.")
except Exception as e:
    print(f"기술 집합 생성 중 오류가 발생했습니다: {e}")
