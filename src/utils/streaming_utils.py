"""
동적 버퍼링 및 실시간 가드레일 필터링 유틸리티

이 모듈은 LLM의 응답 스트림을 실시간으로 검증하여,
안전성이 확인된 텍스트 조각(chunk)만 점진적으로 반환하는
'동적 버퍼' 패턴을 구현합니다.
"""
from typing import Iterator, Tuple, Any
from src.core.rag_core import check_guardrail
from config.config_loader import CONFIG

# --- config.yaml에서 버퍼 크기 설정 읽기 ---
INITIAL_BUFFER_SIZE = CONFIG.get("initial_buffer_size", 50)         # 빠른 첫 응답을 위한 초기 버퍼 크기 (문자 수)
SUBSEQUENT_BUFFER_SIZE = CONFIG.get("subsequent_buffer_size", 200)   # 효율성을 위한 후속 버퍼 크기

def stream_and_filter_response(llm_stream: Iterator) -> Iterator[Tuple[str, Any]]:
    """LLM 스트림을 동적 버퍼로 검사하고, 최종 진단 정보를 포함하여 반환합니다."""
    buffer = ""
    is_first_chunk = True
    
    # 최종적으로 반환할 진단 정보를 누적하기 위한 변수
    total_elapsed_time = 0.0
    all_source_documents = []
    all_source_files = set()  # LLM이 실제로 사용한 파일명을 중복 없이 수집

    try:
        for chunk in llm_stream:
            buffer += chunk.content
            current_buffer_size = INITIAL_BUFFER_SIZE if is_first_chunk else SUBSEQUENT_BUFFER_SIZE

            while len(buffer) >= current_buffer_size:
                text_to_check = buffer[:current_buffer_size]
                buffer = buffer[current_buffer_size:]

                guardrail_result = check_guardrail(text_to_check)

                # 진단 정보 누적
                total_elapsed_time += guardrail_result.get("elapsed_time", 0.0)
                all_source_documents.extend(guardrail_result.get("source_documents", []))
                
                # LLM이 실제로 사용한 파일명 수집
                source_files = guardrail_result.get("source_files", [])
                if source_files:
                    all_source_files.update(source_files)

                if guardrail_result.get("decision") == "HARMFUL":
                    reason = guardrail_result.get("reason", "No reason provided.")
                    yield "BLOCKED", f"⚠️ **콘텐츠가 내부 정책에 위배되어 차단되었습니다.**\n\n**사유:** {reason}"
                    # 차단 시에도 지금까지의 진단 정보 반환
                    yield "DIAGNOSTICS", {
                        "elapsed_time": total_elapsed_time, 
                        "source_documents": all_source_documents,
                        "source_files": list(all_source_files)
                    }
                    return

                yield "SAFE_CHUNK", text_to_check

                if is_first_chunk:
                    is_first_chunk = False
        
        # 마지막 남은 버퍼 처리
        if buffer:
            guardrail_result = check_guardrail(buffer)
            total_elapsed_time += guardrail_result.get("elapsed_time", 0.0)
            all_source_documents.extend(guardrail_result.get("source_documents", []))
            
            # LLM이 실제로 사용한 파일명 수집
            source_files = guardrail_result.get("source_files", [])
            if source_files:
                all_source_files.update(source_files)
            
            if guardrail_result.get("decision") == "HARMFUL":
                reason = guardrail_result.get("reason", "No reason provided.")
                yield "BLOCKED", f"⚠️ **콘텐츠가 내부 정책에 위배되어 차단되었습니다.**\n\n**사유:** {reason}"
                yield "DIAGNOSTICS", {
                    "elapsed_time": total_elapsed_time, 
                    "source_documents": all_source_documents,
                    "source_files": list(all_source_files)
                }
                return

            yield "SAFE_CHUNK", buffer

        # 스트림이 성공적으로 끝나면 최종 진단 정보 반환
        yield "DIAGNOSTICS", {
            "elapsed_time": total_elapsed_time, 
            "source_documents": all_source_documents,
            "source_files": list(all_source_files)
        }

    except Exception as e:
        yield "ERROR", f"❌ **스트리밍 중 오류가 발생했습니다:** {str(e)}"
        # 오류 발생 시에도 지금까지의 진단 정보 반환
        yield "DIAGNOSTICS", {
            "elapsed_time": total_elapsed_time, 
            "source_documents": all_source_documents,
            "source_files": list(all_source_files)
        }
