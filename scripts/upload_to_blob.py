"""RAG 정책 파일을 Azure Blob Storage에 동기화하는 스크립트."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Iterable

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.storage.blob import BlobClient, BlobServiceClient
from dotenv import load_dotenv
from pypdf import PdfReader
from config.config_loader import CONFIG


def iter_source_files(root_dir: str) -> Iterable[Path]:
    """RAG 소스 디렉터리에서 지원하는 파일(txt, pdf) 경로를 반환합니다."""
    path = Path(root_dir)
    if not path.is_dir():
        return []
    
    # .txt와 .pdf 파일을 모두 찾습니다.
    allowed_extensions = ["*.txt", "*.pdf"]
    files = []
    for ext in allowed_extensions:
        files.extend(path.glob(ext))
    
    return sorted(p for p in files if p.is_file())


def md5_hex(file_path: Path) -> str:
    """파일의 MD5 해시를 16진수 문자열로 반환합니다."""
    digest = hashlib.md5()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4096), b""):
            digest.update(chunk)
    return digest.hexdigest()


def blob_md5(blob_client: BlobClient) -> str:
    """Blob의 MD5 해시를 16진수 문자열로 반환합니다."""
    try:
        props = blob_client.get_blob_properties()
    except Exception:
        return ""
    if props.content_settings.content_md5:
        return props.content_settings.content_md5.hex()
    return ""


def sync_files(dry_run: bool = False) -> None:
    """로컬 소스 디렉터리와 Azure Blob Storage를 동기화합니다."""
    container_name = CONFIG["blob_storage_container_name"]
    blob_prefix = CONFIG["blob_storage_policy_path"]
    source_dir = CONFIG["rag_source_directory"]

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise EnvironmentError("AZURE_STORAGE_CONNECTION_STRING 환경 변수가 필요합니다.")

    service_client = BlobServiceClient.from_connection_string(connection_string)

    updated, skipped = 0, 0
    for local_path in iter_source_files(source_dir):
        # PDF 파일의 경우, Blob Storage에 저장될 때 .txt 확장자로 변경합니다.
        if local_path.suffix.lower() == ".pdf":
            target_filename = local_path.with_suffix(".txt").name
        else:
            target_filename = local_path.name
        
        blob_name = f"{blob_prefix}/{target_filename}" if blob_prefix else target_filename
        blob_client = service_client.get_blob_client(container=container_name, blob=blob_name)

        local_hash = md5_hex(local_path)
        remote_hash = blob_md5(blob_client)

        if local_hash == remote_hash:
            skipped += 1
            continue

        print(f"[변경 감지] '{local_path.name}' 업로드가 필요합니다.")
        if dry_run:
            updated += 1
            continue
        
        # --- PDF 처리 로직 추가 ---
        if local_path.suffix.lower() == ".pdf":
            print(f"'{local_path.name}'에서 텍스트를 추출합니다...")
            try:
                reader = PdfReader(local_path)
                text_content = "\n".join(page.extract_text() for page in reader.pages)
                
                # 추출된 텍스트를 바이트로 변환하여 업로드
                with BytesIO(text_content.encode("utf-8")) as data:
                    blob_client.upload_blob(data, overwrite=True)
                
            except Exception as e:
                print(f"'{local_path.name}' PDF 처리 중 오류 발생: {e}")
                skipped += 1 # 오류 발생 시 건너뛰기
                continue
        else:
            # 기존 텍스트 파일 처리 로직
            with local_path.open("rb") as data:
                blob_client.upload_blob(data, overwrite=True)
        # --------------------------

        updated += 1
        print(f"[업로드 완료] {local_path.name}")

    summary = "DRY-RUN" if dry_run else "SYNC"
    print(f"[{summary}] 업로드 {updated}건, 스킵 {skipped}건")


def parse_args() -> argparse.Namespace:
    """명령행 인자를 파싱합니다."""
    parser = argparse.ArgumentParser(
        description="RAG_source 디렉터리와 Blob Storage를 동기화합니다."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="변경 사항만 확인하고 실제 업로드는 수행하지 않습니다.",
    )
    return parser.parse_args()


def main() -> None:
    """스크립트 진입점."""
    load_dotenv()
    args = parse_args()
    sync_files(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

