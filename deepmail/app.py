# app.py
import streamlit as st
from ui_component import UIComponents
from config import PAGE_CONFIG
import joblib
import os
import logging


def setup_logger():
    # 루트 디렉토리의 log 폴더 생성
    log_dir = os.path.join(os.path.dirname(__file__), "..", "log")
    os.makedirs(log_dir, exist_ok=True)
    
    # log 폴더 안에 deepmail.log 파일 생성
    log_file = os.path.join(log_dir, "deepmail.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

# 로거 설정
setup_logger()
logger = logging.getLogger(__name__)

# 로그 기록 테스트
logger.info("DeepMail 로그 시스템 작동 시작")

def main():
    UIComponents.initialize_session_state()
    st.set_page_config(**PAGE_CONFIG)
    st.title("DeepMail - 챗봇을 통한 메일 관리 시스템")

    UIComponents.render_sidebar()
    
    # 모델 로드
    model_dict = None
    model_path = os.path.join(os.path.dirname(__file__), '../models/rf_phishing_model.pkl')
    if os.path.exists(model_path):
        model_dict = joblib.load(model_path)

    # 메일 데이터 준비
    messages = st.session_state.get('gmail_messages', [])

    # 위쪽 섹션: 피싱/스팸 메일 대시보드
    UIComponents.render_phishing_dashboard(model_dict=model_dict, messages=messages)
    
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