# app.py
import streamlit as st
from ui_component import UIComponents
from config import PAGE_CONFIG

def main():
    UIComponents.initialize_session_state()
    st.set_page_config(**PAGE_CONFIG)
    st.title("DeepMail - 챗봇을 통한 메일 관리 시스템")

    UIComponents.render_sidebar()
    
    # 위쪽 섹션: 피싱/스팸 메일 대시보드
    UIComponents.render_phishing_dashboard()
    
    # 수평선으로 구분
    st.markdown("---")
    
    # 아래쪽 섹션: 메일 관리와 챗봇 (반으로 나누기)
    col1, col2 = st.columns([1, 1])
    
    # 왼쪽 컬럼: 메일 관리
    with col1:
        UIComponents.render_mail_management()
        
    # 오른쪽 컬럼: 챗봇
    with col2:
        UIComponents.render_chat_interface()
        UIComponents.handle_chat_input()

if __name__ == "__main__":
    main()