"""
🛡️ KB 국민은행 AI 가드레일 시스템

이 애플리케이션은 사용자와 LLM 간의 대화에서 입력과 출력을 모두 필터링하여
금융 정책 위반, 개인정보 요구, 피싱/스미싱 등의 위험을 사전에 차단합니다.
"""

import streamlit as st
from src.core.rag_core import check_guardrail, llm
from src.utils.streaming_utils import stream_and_filter_response


def main():
    """메인 애플리케이션 함수"""
    # 페이지 설정
    st.set_page_config(
        page_title="KB 국민은행 AI 가드레일",
        page_icon="🛡️",
        layout="wide"
    )
    
    # 헤더
    st.title("🛡️ KB 국민은행 AI 가드레일 시스템")
    st.caption("안전하고 신뢰할 수 있는 AI 금융 상담 서비스")
    
    # 사이드바 정보
    with st.sidebar:
        st.header("🔒 보안 정책")
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
                "content": "당신은 KB 국민은행의 친절한 AI 상담원입니다. 금융 관련 질문에 도움을 드리겠습니다."
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
            # 안전한 입력 - LLM 답변 생성
            st.write("✅ **입력 검사 통과 - 답변 생성 중...**")
            
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = ""
                is_blocked = False

                try:
                    # 🔍 2단계: 동적 버퍼를 사용한 출력 필터링 (Post-Filter)
                    llm_stream = llm.stream(st.session_state["messages"])
                    
                    for status, content in stream_and_filter_response(llm_stream):
                        if status == "SAFE_CHUNK":
                            full_response += content
                            response_placeholder.markdown(full_response + "▌")
                        
                        elif status == "BLOCKED":
                            full_response = content # 차단 메시지로 응답을 대체
                            response_placeholder.error(full_response)
                            is_blocked = True
                            break # 스트리밍 중단
                        
                        elif status == "ERROR":
                            full_response = content # 오류 메시지로 응답을 대체
                            response_placeholder.error(full_response)
                            is_blocked = True
                            break

                    # 스트리밍 완료 후 커서 제거
                    if not is_blocked:
                        response_placeholder.markdown(full_response)
                        st.write("✅ **답변 검사 완료**")

                except Exception as e:
                    # LLM 스트림 생성 자체에서 오류가 발생한 경우
                    full_response = f"❌ **답변 생성 중 오류가 발생했습니다:** {str(e)}"
                    response_placeholder.error(full_response)
                
                # 최종 응답을 대화 기록에 추가
                st.session_state["messages"].append({
                    "role": "assistant", 
                    "content": full_response
                })
                    
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
                "content": "당신은 KB 국민은행의 친절한 AI 상담원입니다. 금융 관련 질문에 도움을 드리겠습니다."
            }
        ]
        st.rerun()


if __name__ == "__main__":
    main()
