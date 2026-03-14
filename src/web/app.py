"""
🛡️ 기업용 AI 가드레일 시스템

이 애플리케이션은 사용자와 LLM 간의 대화에서 입력과 출력을 모두 필터링하여
금융 정책 위반, 개인정보 요구, 피싱/스미싱 등의 위험을 사전에 차단합니다.
"""

import streamlit as st
import os
import urllib.parse
import base64
import subprocess
import sys
from src.core.rag_core import check_guardrail, llm
from src.utils.streaming_utils import stream_and_filter_response
from config.config_loader import CONFIG

def format_source_documents(documents: list, source_files_filter: list = None) -> list:
    """RAG의 근거 문서를 Streamlit에 표시하기 좋게 포맷합니다.

    Args:
        documents: 검색된 문서 리스트
        source_files_filter: LLM이 실제로 사용한 파일명 리스트 (선택적)

    Returns:
        포맷된 문서 정보 리스트 (각 항목은 {"file_name": str, "preview": str, "full_content": str} 딕셔너리)
    """
    if not documents:
        return []

    formatted_docs = []
    unique_documents = {doc.metadata.get("metadata_storage_path"): doc for doc in documents}.values()

    # 매칭 실패 시 폴백 표시를 위해 플래그 유지
    matched_any = False

    for doc in unique_documents:
        file_name = "출처 불명"  # 기본값
        raw_path_for_debug = ""
        try:
            # 1. 가장 이상적인 필드인 metadata_storage_name을 먼저 시도합니다.
            file_name_from_meta = doc.metadata.get("metadata_storage_name")
            if file_name_from_meta:
                file_name = file_name_from_meta
            else:
                # 2. Fallback: metadata_storage_path (Key)를 디코딩하여 파일명을 추출합니다.
                path_key = doc.metadata.get("metadata_storage_path", "")
                raw_path_for_debug = path_key  # 디버깅을 위해 원본 키를 저장합니다.
                if not path_key:
                    raise ValueError("metadata_storage_path is empty")

                decoded_path = path_key
                # Base64로 인코딩된 URL 키인지 확인하고, 안전하게 디코딩을 시도합니다.
                if not path_key.startswith(('http://', 'https://')):
                    # URL-safe Base64 문자( -, _ )를 표준( +, / )으로 변환합니다.
                    path_key_std = path_key.replace('-', '+').replace('_', '/')
                    # 올바른 패딩을 추가합니다.
                    path_key_padded = path_key_std + '=' * (-len(path_key_std) % 4)
                    decoded_path = base64.b64decode(path_key_padded).decode('utf-8')

                # 디코딩된 URL에서 파일명을 파싱합니다.
                parsed_name = os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(decoded_path).path))
                if parsed_name:
                    file_name = parsed_name
                else:
                    raise ValueError("Parsed filename is empty after decoding.")

        except Exception:
            # 모든 파싱 시도가 실패하면, 디버깅을 위해 원본 키 값을 보여줍니다.
            if raw_path_for_debug:
                file_name = f"{raw_path_for_debug} (파싱 실패)"
            else:
                file_name = "메타데이터 없음"

        # LLM이 사용한 파일이 명시된 경우(source_files_filter가 비어있지 않은 경우)에만 필터링 수행
        if source_files_filter:
            # [DEBUG] 필터링 전 정보 출력
            print(f"[DEBUG app.py] Checking file: {file_name}")
            print(f"[DEBUG app.py] Filter list: {source_files_filter}")

            file_name_base, _ = os.path.splitext(file_name)

            # 파일명 정규화 함수 (공백 유지, 괄호/특수문자 정리)
            def normalize_filename(text: str) -> str:
                import re
                text = re.sub(r'\([^)]*\)', '', text)  # 괄호 내용 제거
                text = os.path.splitext(text)[0]        # 확장자 제거
                text = re.sub(r'\s+', ' ', text).strip().lower()  # 다중 공백 정리 + 소문자
                text = re.sub(r'[^0-9a-zA-Z가-힣 ]', '', text)      # 불필요 특수문자 제거 (공백 유지)
                return text

            def token_sets(a: str, b: str):
                sa = set(a.split())
                sb = set(b.split())
                return sa, sb

            def token_jaccard(a: str, b: str) -> float:
                sa, sb = token_sets(a, b)
                if not sa or not sb:
                    return 0.0
                return len(sa & sb) / max(1, len(sa | sb))

            from difflib import SequenceMatcher
            norm_file = normalize_filename(file_name_base)
            scores = []
            overlaps = []
            for cited in source_files_filter:
                norm_cited = normalize_filename(cited)
                sim = SequenceMatcher(None, norm_file, norm_cited).ratio()
                jac = token_jaccard(norm_file, norm_cited)
                sa, sb = token_sets(norm_file, norm_cited)
                overlap_cnt = len(sa & sb)
                scores.append(max(sim, jac))
                overlaps.append(overlap_cnt)

            # 임계값 0.35 또는 최소 1개 토큰 교집합 시 매칭 성사
            is_cited = any(score >= 0.35 or ov >= 1 for score, ov in zip(scores, overlaps))

            # 디버깅 로그
            print(f"[DEBUG app.py] norm_file='{norm_file}', norm_cited={[normalize_filename(c) for c in source_files_filter]}, scores={scores}, overlaps={overlaps}, match={is_cited}")

            # LLM이 인용한 문서가 아니면 건너뜀
            if not is_cited:
                continue

        # 필터를 통과했거나, 필터가 없을 때 문서 표시
        full_content = doc.page_content.replace(chr(10), ' ').strip()
        preview = full_content[:250] + "..." if len(full_content) > 250 else full_content

        formatted_docs.append({
            "file_name": file_name,
            "preview": preview,
            "full_content": full_content
        })

        if source_files_filter:
            matched_any = True

    # 폴백: 인용된 이름이 아무 것도 매칭되지 않으면 전체 검색 문서 표시
    if source_files_filter and not matched_any:
        print("[DEBUG app.py] No documents matched cited names. Falling back to show all retrieved documents.")
        formatted_docs = []
        for doc in {doc.metadata.get("metadata_storage_path"): doc for doc in documents}.values():
            display_name = doc.metadata.get("metadata_storage_name") or os.path.basename(
                urllib.parse.unquote(
                    urllib.parse.urlparse(
                        base64.b64decode(doc.metadata.get("metadata_storage_path", "").replace('-', '+').replace('_', '/').ljust(((len(doc.metadata.get("metadata_storage_path", "")) + 3) // 4) * 4, '=')).decode('utf-8')
                    ).path
                )
            ) if doc.metadata.get("metadata_storage_path") and not doc.metadata.get("metadata_storage_path", "").startswith(('http://', 'https://')) else (
                doc.metadata.get("metadata_storage_name") or os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(doc.metadata.get("metadata_storage_path", "")).path))
            )
            full_content = doc.page_content.replace(chr(10), ' ').strip()
            preview = full_content[:250] + "..." if len(full_content) > 250 else full_content
            formatted_docs.append({
                "file_name": display_name or "출처 불명",
                "preview": preview,
                "full_content": full_content
            })

    return formatted_docs


def main():
    """메인 애플리케이션 함수"""
    # 페이지 설정
    st.set_page_config(
        page_title="기업용 AI 가드레일",
        page_icon="🛡️",
        layout="wide"
    )

    # 헤더
    st.title("🛡️ 기업용 AI 가드레일 시스템")
    st.caption("안전하고 신뢰할 수 있는 AI 금융 상담 서비스")

    with st.sidebar:
        st.header("⚙️ 설정")

        # 진단 정보 표시 옵션 추가
        show_diagnostics = st.checkbox("🔍 진단 정보 표시", value=False, help="가드레일 판단 근거와 성능 정보를 표시합니다")

        st.divider()

        st.header("🔒 보안 정책 관리")

        uploaded_files = st.file_uploader(
            "정책 파일(.txt, .pdf)을 업로드하세요.",
            type=["txt", "pdf"],
            accept_multiple_files=True
        )

        if st.button("업로드 및 지식 베이스 동기화", type="primary"):
            if uploaded_files:
                rag_source_path = CONFIG.get("rag_source_directory", "RAG_source")
                os.makedirs(rag_source_path, exist_ok=True)

                # 파일 저장
                for file in uploaded_files:
                    file_path = os.path.join(rag_source_path, file.name)
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())
                    st.sidebar.write(f"`{file.name}` 저장 완료.")

                # 동기화 스크립트 실행
                with st.spinner("Azure Blob Storage와 동기화 중..."):
                    try:
                        command = [sys.executable, "main.py", "upload-rag"]
                        result = subprocess.run(
                            command,
                            capture_output=True,
                            text=True,
                            check=True,
                            encoding='utf-8'
                        )
                        st.sidebar.success("✅ 동기화 완료!")
                        # 동기화 로그 보기 기능 제거
                    except subprocess.CalledProcessError as e:
                        st.sidebar.error("❌ 동기화 실패.")
                        with st.sidebar.expander("오류 로그 보기"):
                            st.code(e.stderr)
                    except FileNotFoundError:
                        st.sidebar.error("`main.py`를 찾을 수 없습니다. 스크립트를 프로젝트 루트에서 실행하세요.")

            else:
                st.sidebar.warning("업로드할 파일을 먼저 선택해주세요.")

        st.divider() # 구분선 추가

        st.header("📜 기존 보안 정책")
        st.info("""
        **차단되는 내용:**
        - 확정적 투자 수익 표현
        - 개인정보 요구
        - 피싱/스미싱 링크
        - 욕설 및 비하 발언
        """)

        st.header("✅ 안전한 질문 예시")
        st.success("""
        - 은행 지점 위치 문의
        - 금융 상품 일반 정보
        - 계좌 관리 방법
        - 대출 종류 설명
        """)

    # 대화 기록 초기화
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {
                "role": "system",
                "content": "당신은 기업용 AI 가드레일의 친절한 AI 상담원입니다. 금융 관련 질문에 도움을 드리겠습니다."
            }
        ]

    # 기존 대화 내역 표시 (시스템 메시지는 제외)
    for msg in st.session_state["messages"]:
        if msg["role"] != "system":  # 시스템 메시지는 화면에 표시하지 않음
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 사용자 입력 처리
    if user_input := st.chat_input("질문을 입력하세요..."):
        # 사용자 메시지 표시
        with st.chat_message("user"):
            st.markdown(user_input)

        # 사용자 메시지를 세션에 저장
        st.session_state["messages"].append({"role": "user", "content": user_input})

        # 🔍 1단계: 입력 필터링 (Pre-Filter)
        st.write("🔍 **입력 검사 중...**")
        input_check = check_guardrail(user_input)

        # 진단 정보 패널: 사용자가 체크박스를 활성화한 경우에만 표시
        if show_diagnostics:
            is_harmful = input_check.get("decision") == "HARMFUL"
            with st.expander("🛡️ 입력 가드레일 진단 정보", expanded=is_harmful):
                st.metric("판단 소요 시간", f"{input_check.get('elapsed_time', 0):.2f}초")
                st.caption("판단 근거 문서:")

                source_docs = input_check.get("source_documents", [])
                source_files_used = input_check.get("source_files", None)  # LLM이 실제로 사용한 파일명
                formatted_docs = format_source_documents(source_docs, source_files_used)

                if not formatted_docs:
                    st.info("LLM이 사용한 문서를 찾을 수 없습니다.")
                else:
                    for doc_info in formatted_docs:
                        st.markdown(f"**- 문서: `{doc_info['file_name']}`**")
                        st.markdown(f"> {doc_info['preview']}")
                        with st.expander("📄 전체 내용 보기"):
                            st.text(doc_info['full_content'])

        if input_check.get("decision") == "HARMFUL":
            # 유해한 입력 차단
            with st.chat_message("assistant"):
                warning_message = f"""
                ⚠️ **부적절한 질문이 감지되었습니다.**

                **차단 사유:** {input_check.get('reason')}

                안전하고 적절한 질문으로 다시 문의해 주세요.
                """
                st.error(warning_message)

            # 경고 메시지를 대화 기록에 추가
            st.session_state["messages"].append({
                "role": "assistant",
                "content": warning_message
            })

        elif input_check.get("decision") == "SAFE":
            st.write("✅ **입력 검사 통과 - 답변 생성 중...**")

            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = ""
                is_blocked = False
                output_diagnostics = None  # 출력 진단 정보를 저장할 변수

                try:
                    llm_stream = llm.stream(st.session_state["messages"])

                    for status, content in stream_and_filter_response(llm_stream):
                        if status == "SAFE_CHUNK":
                            full_response += content
                            response_placeholder.markdown(full_response + "▌")

                        elif status == "BLOCKED":
                            full_response = content
                            response_placeholder.error(full_response)
                            is_blocked = True
                            # 바로 중단하지 않고, 진단 정보 수신을 위해 대기

                        elif status == "DIAGNOSTICS":
                            output_diagnostics = content
                            if is_blocked:  # 차단된 경우, 진단 정보 수신 후 스트림 처리 종료
                                break

                        elif status == "ERROR":
                            full_response = content
                            response_placeholder.error(full_response)
                            is_blocked = True
                            # 바로 중단하지 않고, 진단 정보 수신을 위해 대기

                    if not is_blocked:
                        response_placeholder.markdown(full_response)
                        st.write("✅ **답변 검사 완료**")

                except Exception as e:
                    full_response = f"❌ **답변 생성 중 오류가 발생했습니다:** {str(e)}"
                    response_placeholder.error(full_response)

                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": full_response
                })

                # 스트림 처리 후, 수신된 출력 진단 정보가 있으면 표시 (사용자가 체크박스를 활성화한 경우에만)
                if show_diagnostics and output_diagnostics:
                    with st.expander("💬 출력 가드레일 진단 정보", expanded=is_blocked):
                        st.metric("총 검사 소요 시간", f"{output_diagnostics.get('elapsed_time', 0):.2f}초")
                        st.caption("판단에 사용된 근거 문서 (중복 제거):")

                        source_docs = output_diagnostics.get("source_documents", [])
                        source_files_used = output_diagnostics.get("source_files", None)  # 집계된 파일명
                        formatted_docs = format_source_documents(source_docs, source_files_used)

                        if not formatted_docs:
                            st.info("LLM이 사용한 문서를 찾을 수 없습니다.")
                        else:
                            for doc_info in formatted_docs:
                                st.markdown(f"**- 문서: `{doc_info['file_name']}`**")
                                st.markdown(f"> {doc_info['preview']}")
                                with st.expander("📄 전체 내용 보기"):
                                    st.text(doc_info['full_content'])

        else:
            # CANNOT_DETERMINE 또는 ERROR 상태
            with st.chat_message("assistant"):
                fallback_message = f"""
                🤔 **질문을 정확히 이해하지 못했습니다.**

                **사유:** {input_check.get('reason')}

                더 구체적으로 질문해 주시면 도움을 드릴 수 있습니다.
                """
                st.warning(fallback_message)

            st.session_state["messages"].append({
                "role": "assistant",
                "content": fallback_message
            })

    # 대화 초기화 버튼
    if st.button("🔄 대화 초기화", type="secondary"):
        st.session_state["messages"] = [
            {
                "role": "system",
                "content": "당신은 기업용 AI 가드레일의 친절한 AI 상담원입니다. 금융 관련 질문에 도움을 드리겠습니다."
            }
        ]
        st.rerun()


if __name__ == "__main__":
    main()
