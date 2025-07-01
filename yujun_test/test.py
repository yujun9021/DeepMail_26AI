import streamlit as st
import imaplib
import email
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Gmail 연결 테스트",
    page_icon="📧",
    layout="wide"
)

# 세션 상태 초기화
if 'gmail_connected' not in st.session_state:
    st.session_state.gmail_connected = False
if 'gmail_account' not in st.session_state:
    st.session_state.gmail_account = None

# Gmail 연결 함수
def connect_gmail(email, app_password):
    try:
        # Gmail IMAP 서버 연결
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email, app_password)
        return mail, True
    except imaplib.IMAP4.error as e:
        return None, f"IMAP 오류: {str(e)}"
    except Exception as e:
        return None, f"연결 오류: {str(e)}"

# 연결 테스트 함수
def test_gmail_connection(email, app_password):
    mail, result = connect_gmail(email, app_password)
    if mail:
        try:
            # 받은 편지함 선택
            mail.select("INBOX")
            # 메일 개수 확인
            _, message_numbers = mail.search(None, "ALL")
            mail_count = len(message_numbers[0].split())
            mail.logout()
            return True, f"연결 성공! 받은 편지함에 {mail_count}개의 메일이 있습니다."
        except Exception as e:
            mail.logout()
            return False, f"테스트 중 오류: {str(e)}"
    else:
        return False, result

st.title("📧 Gmail 연결 테스트")
st.markdown("Gmail 계정으로 로그인하고 연결을 확인해보세요!")

# 사이드바
with st.sidebar:
    st.header("⚙️ Gmail 설정")
    
    # 연결 상태 표시
    if st.session_state.gmail_connected:
        st.success("✅ Gmail에 연결되었습니다!")
        st.info(f"계정: {st.session_state.gmail_account}")
    else:
        st.warning("⚠️ Gmail에 연결되지 않았습니다.")
    
    st.markdown("---")
    
    # 연결 해제 버튼
    if st.session_state.gmail_connected:
        if st.button("🔌 연결 해제"):
            st.session_state.gmail_connected = False
            st.session_state.gmail_account = None
            st.rerun()

# 메인 영역
if not st.session_state.gmail_connected:
    st.header("🔗 Gmail 로그인")
    
    # 로그인 폼
    with st.form("gmail_login"):
        st.subheader("계정 정보 입력")
        
        email = st.text_input(
            "Gmail 주소",
            placeholder="example@gmail.com",
            help="연결할 Gmail 계정 주소를 입력하세요"
        )
        
        app_password = st.text_input(
            "App Password",
            type="password",
            placeholder="16자리 앱 비밀번호",
            help="Gmail에서 생성한 App Password를 입력하세요"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("🔗 연결 테스트"):
                if email and app_password:
                    with st.spinner("Gmail에 연결하는 중..."):
                        success, message = test_gmail_connection(email, app_password)
                        if success:
                            st.session_state.gmail_connected = True
                            st.session_state.gmail_account = email
                            st.success("✅ 연결 성공!")
                            st.info(message)
                            st.rerun()
                        else:
                            st.error(f"❌ 연결 실패: {message}")
                else:
                    st.error("❌ 이메일과 App Password를 모두 입력해주세요.")
        
        with col2:
            if st.form_submit_button("🧪 연결만 테스트"):
                if email and app_password:
                    with st.spinner("연결을 테스트하는 중..."):
                        success, message = test_gmail_connection(email, app_password)
                        if success:
                            st.success("✅ 연결 테스트 성공!")
                            st.info(message)
                        else:
                            st.error(f"❌ 연결 테스트 실패: {message}")
                else:
                    st.error("❌ 이메일과 App Password를 모두 입력해주세요.")

else:
    st.header("✅ Gmail 연결 완료")
    st.success(f"**{st.session_state.gmail_account}** 계정에 성공적으로 연결되었습니다!")
    
    # 연결 정보 표시
    st.subheader("📊 연결 정보")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("연결 상태", "✅ 연결됨")
    with col2:
        st.metric("계정", st.session_state.gmail_account)
    with col3:
        st.metric("연결 시간", datetime.now().strftime("%H:%M:%S"))
    
    # 다음 단계 안내
    st.subheader("🎯 다음 단계")
    st.markdown("""
    이제 Gmail 연결이 완료되었습니다! 다음 기능들을 구현할 수 있습니다:
    
    - 📥 이메일 읽기
    - 📤 이메일 보내기
    - 🔍 이메일 검색
    - 📁 폴더 관리
    - 📊 이메일 통계
    """)

# App Password 설정 가이드
with st.expander("📖 App Password 설정 방법"):
    st.markdown("""
    ### Gmail App Password 생성 방법:
    
    **1단계: 2단계 인증 활성화**
    - Gmail → 설정 → 보안 → 2단계 인증 활성화
    - 휴대폰 번호 인증 완료
    
    **2단계: App Password 생성**
    - Gmail → 설정 → 보안 → 앱 비밀번호
    - "앱 선택" → "기타" → 이름 입력 (예: "Streamlit")
    - 16자리 앱 비밀번호 생성
    
    **3단계: 애플리케이션에서 사용**
    - 생성된 16자리 앱 비밀번호를 위 입력창에 입력
    - 일반 Gmail 비밀번호가 아닌 앱 비밀번호 사용
    
    **⚠️ 주의사항:**
    - 앱 비밀번호는 한 번만 표시되므로 안전하게 보관하세요
    - 앱 비밀번호는 16자리이며 공백으로 구분됩니다
    - 필요시 언제든지 앱 비밀번호를 재생성할 수 있습니다
    """)

# 하단 정보
st.markdown("---")
st.markdown("**Gmail 연결 테스트** - Streamlit + Gmail App Password")
