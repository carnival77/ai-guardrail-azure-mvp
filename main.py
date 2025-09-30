"""
기업용 AI 가드레일 시스템 - 메인 실행 파일

이 파일은 프로젝트의 다양한 기능을 실행할 수 있는 통합 진입점입니다.
"""

import subprocess
import sys
import os

# 프로젝트 루트를 Python 경로에 추가 (모든 스크립트에서 공통 사용)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def run_streamlit_app():
    """Streamlit 웹 애플리케이션을 실행합니다."""
    print("기업용 AI 가드레일 애플리케이션을 시작합니다...")
    # Streamlit 앱은 src/web/app.py에 있습니다.
    # Azure App Service의 시작 명령과 동일하게 설정
    command = [
        sys.executable, "-m", "streamlit", "run", "src/web/app.py",
        "--server.port", "8000",
        "--server.address", "localhost"
    ]
    subprocess.run(command)

def run_tests():
    """테스트 스크립트를 실행합니다."""
    print("AI 가드레일 테스트를 실행합니다...")
    command = [sys.executable, "tests/test_guardrail.py"]
    subprocess.run(command)

def upload_rag_sources(dry_run: bool = False):
    """RAG 소스 파일을 Blob Storage에 업로드합니다."""
    print("RAG 소스 파일을 Blob Storage에 업로드합니다...")
    command = [sys.executable, "scripts/upload_to_blob.py"]
    if dry_run:
        command.append("--dry-run")
    subprocess.run(command)

def create_ai_search_index():
    """Azure AI Search 인덱스를 생성/업데이트합니다."""
    print("Azure AI Search 인덱스를 생성/업데이트합니다...")
    command = [sys.executable, "scripts/create_index.py"]
    subprocess.run(command)

def create_ai_search_skillset():
    """Azure AI Search 기술 집합을 생성/업데이트합니다."""
    print("Azure AI Search 기술 집합을 생성/업데이트합니다...")
    command = [sys.executable, "scripts/create_skillset.py"]
    subprocess.run(command)

if __name__ == "__main__":
    print("기업용 AI 가드레일 프로젝트 메인 진입점")
    print("사용 가능한 명령어:")
    print("  - app: Streamlit 웹 애플리케이션 실행")
    print("  - test: 가드레일 테스트 실행")
    print("  - upload-rag [--dry-run]: RAG 소스 파일을 Blob Storage에 업로드")
    print("  - create-index: Azure AI Search 인덱스 생성/업데이트")
    print("  - create-skillset: Azure AI Search 기술 집합 생성/업데이트")
    print("\n예시: python main.py app")

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "app":
            run_streamlit_app()
        elif command == "test":
            run_tests()
        elif command == "upload-rag":
            dry_run = "--dry-run" in sys.argv
            upload_rag_sources(dry_run=dry_run)
        elif command == "create-index":
            create_ai_search_index()
        elif command == "create-skillset":
            create_ai_search_skillset()
        else:
            print(f"알 수 없는 명령어: {command}")
    else:
        print("명령어를 입력해주세요.")
