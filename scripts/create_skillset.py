import os
import sys
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchSkillsetClient
from azure.search.documents.indexes.models import SearchSkillset
from dotenv import load_dotenv
from config.config_loader import CONFIG

def create_skillset_from_json(skillset_client: SearchSkillsetClient, skillset_definition: dict) -> None:
    """JSON 정의를 기반으로 기술 집합을 생성 또는 업데이트합니다."""
    try:
        skillset_name = skillset_definition.get("name")
        print(f"'{skillset_name}' 기술 집합을 생성 또는 업데이트합니다...")
        
        # SDK가 dict를 SearchSkillset 객체로 변환할 수 있도록 from_dict 클래스 메서드 사용 고려
        # 하지만 최신 SDK는 dict를 직접 받을 수 있음
        skillset = SearchSkillset.from_dict(skillset_definition)
        result = skillset_client.create_or_update_skillset(skillset=skillset)
        
        print(f"'{result.name}' 기술 집합이 성공적으로 생성/업데이트되었습니다.")
    except Exception as e:
        print(f"기술 집합 생성 중 오류가 발생했습니다: {e}")

def main():
    """메인 실행 함수"""
    # --- 1. 필수 정보 로드 ---
    load_dotenv()

    search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_api_key: str = os.getenv("AZURE_SEARCH_API_KEY")
    
    # 설정 파일에서 스킬셋 이름과 JSON 파일 경로 가져오기
    skillset_name: str = CONFIG.get("azure_skillset_name", "default-skillset")
    json_path: str = CONFIG.get("azure_skillset_definition_path", "config/skillset_definition.json")

    if not all([search_endpoint, search_api_key]):
        raise ValueError("환경변수가 올바르게 설정되지 않았습니다. .env 파일을 확인해주세요.")

    # --- 2. JSON 파일 로드 및 이름 설정 ---
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            skillset_definition = json.load(f)
        # config.yaml에 정의된 이름으로 JSON 내부의 skillset 이름을 동적으로 설정
        skillset_definition["name"] = skillset_name
    except FileNotFoundError:
        print(f"오류: 스킬셋 정의 파일 '{json_path}'을(를) 찾을 수 없습니다.")
        return
    except json.JSONDecodeError:
        print(f"오류: '{json_path}' 파일의 JSON 형식이 올바르지 않습니다.")
        return

    # --- 3. 클라이언트 연결 및 스킬셋 생성 ---
    credential = AzureKeyCredential(search_api_key)
    skillset_client = SearchSkillsetClient(endpoint=search_endpoint, credential=credential)
    create_skillset_from_json(skillset_client, skillset_definition)

if __name__ == "__main__":
    main()
