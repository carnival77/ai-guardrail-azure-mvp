"""
설정 파일 로더 유틸리티

config.yaml 파일을 읽어서 애플리케이션 설정을 로드하는 모듈입니다.
민감하지 않은 환경 설정 값들을 관리합니다.
"""

import os
import yaml
from typing import Dict, Any


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    YAML 설정 파일을 로드합니다.
    
    Args:
        config_path: 설정 파일 경로 (기본값: "config.yaml")
        
    Returns:
        설정 딕셔너리
        
    Raises:
        FileNotFoundError: 설정 파일이 없는 경우
        yaml.YAMLError: YAML 파싱 오류가 발생한 경우
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"YAML 파싱 오류: {e}")


def get_config_value(key: str, default: Any = None) -> Any:
    """
    설정 값을 가져옵니다.
    
    Args:
        key: 설정 키
        default: 기본값
        
    Returns:
        설정 값
    """
    config = load_config()
    return config.get(key, default)


# 전역 설정 로드 (모듈 import 시 실행)
try:
    # __file__은 현재 파일(config_loader.py)의 경로를 나타냅니다.
    # os.path.dirname()으로 현재 파일이 있는 디렉터리 경로를 얻고,
    # os.path.join()으로 'config.yaml' 파일의 절대 경로를 만듭니다.
    config_file_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    CONFIG = load_config(config_file_path)
except (FileNotFoundError, yaml.YAMLError) as e:
    print(f"경고: 설정 파일 로드 실패 - {e}")
    # 설정 파일이 없어도 기본값으로 동작하도록 fallback 설정
    CONFIG = {
        "azure_openai_chat_deployment_name": "GPT-4.1",
        "azure_openai_embedding_deployment_name": "text-embedding-3-small",
        "azure_openai_api_version": "2024-12-01-preview",
        "azure_search_index_name": "bank-financial-policy-index",
        # "azure_skillset_name": "bank-financial-policy-skillset",
        "blob_storage_container_name": "container",
        "rag_source_directory": "RAG_source",
        "blob_storage_policy_path": "policy",
        "initial_buffer_size": 50,
        "subsequent_buffer_size": 200,
        "llm_temperature": 0,
        "llm_max_retries": 3,
        "llm_timeout": 30
    }
