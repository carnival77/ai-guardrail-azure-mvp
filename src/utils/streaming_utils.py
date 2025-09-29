"""
동적 버퍼링 및 실시간 가드레일 필터링 유틸리티

이 모듈은 LLM의 응답 스트림을 실시간으로 검증하여,
안전성이 확인된 텍스트 조각(chunk)만 점진적으로 반환하는
'동적 버퍼' 패턴을 구현합니다.
"""
from typing import Iterator, Tuple
from src.core.rag_core import check_guardrail
from config.config_loader import CONFIG

# --- config.yaml에서 버퍼 크기 설정 읽기 ---
INITIAL_BUFFER_SIZE = CONFIG["initial_buffer_size"]         # 빠른 첫 응답을 위한 초기 버퍼 크기 (문자 수)
SUBSEQUENT_BUFFER_SIZE = CONFIG["subsequent_buffer_size"]   # 효율성을 위한 후속 버퍼 크기

def stream_and_filter_response(llm_stream: Iterator) -> Iterator[Tuple[str, str]]:
    """
    LLM 응답 스트림을 동적 버퍼를 사용하여 실시간으로 필터링합니다.

    Args:
        llm_stream: LLM의 응답 스트림 (예: llm.stream()의 반환값).

    Yields:
        A tuple containing the status ('SAFE_CHUNK', 'BLOCKED', 'ERROR')
        and the corresponding content (text chunk or reason message).
    """
    buffer = ""
    is_first_chunk = True
    
    try:
        for chunk in llm_stream:
            buffer += chunk.content
            
            # 현재 적용할 버퍼 크기 결정
            current_buffer_size = INITIAL_BUFFER_SIZE if is_first_chunk else SUBSEQUENT_BUFFER_SIZE
            
            # 버퍼가 가득 찰 때마다 검사 수행
            while len(buffer) >= current_buffer_size:
                # 검사할 텍스트를 버퍼에서 분리
                text_to_check = buffer[:current_buffer_size]
                buffer = buffer[current_buffer_size:] # 나머지 부분은 버퍼에 남김

                # 가드레일 검사
                guardrail_result = check_guardrail(text_to_check)
                
                if guardrail_result.get("decision") == "HARMFUL":
                    # 유해 콘텐츠 감지 시 즉시 중단 및 차단 메시지 반환
                    reason = guardrail_result.get("reason", "No reason provided.")
                    yield "BLOCKED", f"⚠️ **콘텐츠가 내부 정책에 위배되어 차단되었습니다.**\n\n**사유:** {reason}"
                    return # 제너레이터 실행 완전 종료
                
                # 안전한 텍스트 조각 반환
                yield "SAFE_CHUNK", text_to_check
                
                # 첫 번째 버퍼 처리가 끝났음을 표시
                if is_first_chunk:
                    is_first_chunk = False
                    # 다음부터는 큰 버퍼를 사용하도록 current_buffer_size를 직접 바꾸지 않고, is_first_chunk 플래그만 변경
        
        # 스트림이 끝나고 버퍼에 남은 텍스트 처리
        if buffer:
            guardrail_result = check_guardrail(buffer)
            if guardrail_result.get("decision") == "HARMFUL":
                reason = guardrail_result.get("reason", "No reason provided.")
                yield "BLOCKED", f"⚠️ **콘텐츠가 내부 정책에 위배되어 차단되었습니다.**\n\n**사유:** {reason}"
                return
            
            yield "SAFE_CHUNK", buffer

    except Exception as e:
        yield "ERROR", f"❌ **스트리밍 중 오류가 발생했습니다:** {str(e)}"
