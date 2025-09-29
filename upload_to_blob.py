"""RAG 정책 파일을 Azure Blob Storage에 동기화하는 스크립트."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Iterable

from azure.storage.blob import BlobClient, BlobServiceClient
from dotenv import load_dotenv

from config_loader import CONFIG


def iter_source_files(root_dir: str) -> Iterable[Path]:
    """RAG 소스 디렉터리에서 txt 파일 경로를 반환합니다."""
    path = Path(root_dir)
    if not path.exists():
        return []
    return sorted(p for p in path.glob("*.txt") if p.is_file())


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
    """로컬 RAG 파일을 Blob Storage와 동기화합니다."""
    container_name = CONFIG["blob_storage_container_name"]
    blob_prefix = CONFIG["blob_storage_policy_path"]
    source_dir = CONFIG["rag_source_directory"]

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise EnvironmentError("AZURE_STORAGE_CONNECTION_STRING 환경 변수가 필요합니다.")

    service_client = BlobServiceClient.from_connection_string(connection_string)

    updated, skipped = 0, 0
    for local_path in iter_source_files(source_dir):
        blob_name = f"{blob_prefix}/{local_path.name}" if blob_prefix else local_path.name
        blob_client = service_client.get_blob_client(container=container_name, blob=blob_name)

        local_hash = md5_hex(local_path)
        remote_hash = blob_md5(blob_client)

        if local_hash == remote_hash:
            skipped += 1
            continue

        if dry_run:
            print(f"[변경 감지] {local_path.name}")
            updated += 1
            continue

        with local_path.open("rb") as data:
            blob_client.upload_blob(data, overwrite=True)
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

