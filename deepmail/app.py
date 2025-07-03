# app.py
import streamlit as st
from ui_components import UIComponents
from config import PAGE_CONFIG

def main():
    UIComponents.initialize_session_state()
    st.set_page_config(**PAGE_CONFIG)
    st.title("DeepMail - AI 챗봇 & Gmail 관리")
    st.markdown("OpenAI Function Calling 기반 AI Agent로 Gmail을 관리하세요!")

    UIComponents.render_sidebar()
    col1, col2 = st.columns([1, 1])
    with col1:
        UIComponents.draw_gauge_chart(55.5)
        UIComponents.render_mail_management()
    with col2:
        UIComponents.render_chat_interface()
        UIComponents.handle_chat_input()

if __name__ == "__main__":
    main()