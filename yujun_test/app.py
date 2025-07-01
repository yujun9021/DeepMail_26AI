import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from googleapiclient.discovery import build

# .env 파일 로드
load_dotenv()

# OpenAI 클라이언트 초기화
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    client = OpenAI(api_key=api_key)
else:
    client = None

# Gmail API 설정 - 삭제 권한 포함
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

# 페이지 설정
st.set_page_config(
    page_title="OpenAI 챗봇",
    page_icon="🤖",
    layout="wide"
)

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "gmail_authenticated" not in st.session_state:
    st.session_state.gmail_authenticated = False
if "gmail_credentials" not in st.session_state:
    st.session_state.gmail_credentials = None

# Gmail 인증 함수
def authenticate_gmail():
    creds = None
    # 토큰 파일이 있으면 로드
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # 유효한 인증 정보가 없거나 만료된 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # credentials.json 파일이 필요합니다 (Google Cloud Console에서 다운로드)
            if os.path.exists('credentials.json'):
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                st.error("credentials.json 파일이 필요합니다!")
                return None
        
        # 토큰 저장
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

# Gmail 메시지 관련 함수들 추가
def get_gmail_messages(max_results=10):
    """Gmail 메시지 목록 가져오기"""
    try:
        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
        results = service.users().messages().list(userId='me', maxResults=max_results).execute()
        messages = results.get('messages', [])
        
        message_details = []
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '제목 없음')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '발신자 없음')
            
            message_details.append({
                'id': message['id'],
                'subject': subject,
                'sender': sender,
                'snippet': msg.get('snippet', '')
            })
        
        return message_details
    except Exception as e:
        st.error(f"메일 목록 가져오기 실패: {str(e)}")
        return []

def delete_gmail_message(message_id):
    """Gmail 메시지 삭제"""
    try:
        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
        service.users().messages().delete(userId='me', id=message_id).execute()
        return True
    except Exception as e:
        st.error(f"메일 삭제 실패: {str(e)}")
        return False

# 채팅 기록 저장 함수
def save_chat_history(messages, filename=None):
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_history_{timestamp}.json"
    
    chat_data = {
        "timestamp": datetime.now().isoformat(),
        "total_messages": len(messages),
        "messages": messages
    }
    
    # chats 폴더가 없으면 생성
    os.makedirs("chats", exist_ok=True)
    filepath = os.path.join("chats", filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=2)
    
    return filepath

# 채팅 기록 로드 함수
def load_chat_history(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        return chat_data["messages"]
    except Exception as e:
        st.error(f"채팅 기록 로드 중 오류 발생: {str(e)}")
        return []

# 저장된 채팅 목록 가져오기
def get_saved_chats():
    if not os.path.exists("chats"):
        return []
    
    chat_files = []
    for filename in os.listdir("chats"):
        if filename.endswith(".json"):
            filepath = os.path.join("chats", filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                chat_files.append({
                    "filename": filename,
                    "filepath": filepath,
                    "timestamp": chat_data.get("timestamp", ""),
                    "total_messages": chat_data.get("total_messages", 0)
                })
            except:
                continue
    
    return sorted(chat_files, key=lambda x: x["timestamp"], reverse=True)

# 사이드바 - 설정
with st.sidebar:
    st.header("⚙️ 챗봇 설정")
    
    # API 키 상태 표시
    if api_key:
        st.success("✅ API 키가 설정되었습니다!")
    else:
        st.error("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        st.info("💡 .env 파일에 OPENAI_API_KEY=your_api_key_here를 추가하세요.")
    
    st.markdown("---")
    
    # Gmail 로그인 섹션
    st.subheader("📧 Gmail 연결")
    
    if not st.session_state.gmail_authenticated:
        if st.button("🔑 Gmail 로그인", type="primary"):
            try:
                creds = authenticate_gmail()
                if creds:
                    st.session_state.gmail_credentials = creds
                    st.session_state.gmail_authenticated = True
                    st.success("✅ Gmail 로그인 성공!")
                    st.rerun()
                else:
                    st.error("❌ Gmail 로그인 실패")
            except Exception as e:
                st.error(f"❌ Gmail 로그인 오류: {str(e)}")
    else:
        st.success("✅ Gmail에 로그인되어 있습니다!")
        
        # 메일 관리 기능 추가
        st.markdown("---")
        st.subheader("📧 메일 관리")
        
        if st.button("📬 메일 목록 보기"):
            messages = get_gmail_messages(5)  # 최근 5개 메일
            if messages:
                for msg in messages:
                    with st.expander(f"📧 {msg['subject']}"):
                        st.write(f"**발신자:** {msg['sender']}")
                        st.write(f"**내용:** {msg['snippet']}")
                        if st.button(f"❌ 삭제", key=f"delete_{msg['id']}"):
                            if delete_gmail_message(msg['id']):
                                st.success("✅ 메일이 삭제되었습니다!")
                                st.rerun()
            else:
                st.info("메일이 없습니다.")
        
        if st.button("🚪 Gmail 로그아웃"):
            st.session_state.gmail_authenticated = False
            st.session_state.gmail_credentials = None
            if os.path.exists('token.pickle'):
                os.remove('token.pickle')
            st.success("✅ Gmail 로그아웃 완료!")
            st.rerun()
    
    st.markdown("---")
    
    # 모델 선택
    model = st.selectbox(
        "모델 선택",
        ["gpt-3.5-turbo", "gpt-4"],
        help="사용할 OpenAI 모델을 선택하세요"
    )
    
    # 온도 설정
    temperature = st.slider(
        "창의성 (Temperature)",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1,
        help="높을수록 더 창의적인 응답을 생성합니다"
    )
    
    st.markdown("---")
    
    # 🔒 채팅 기록 기능이 비활성화되었습니다.

# 메인 영역
st.title("🤖 OpenAI 챗봇")
st.markdown("환경변수에서 API 키를 자동으로 로드합니다!")

for msg in st.session_state.messages:
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])

# 채팅 컨테이너
if prompt := st.chat_input("메시지를 입력하세요..."):
        if not api_key or not client:
            st.error("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다!")
            st.info("💡 .env 파일을 생성하고 OPENAI_API_KEY=your_api_key_here를 추가하세요.")
        else:
            # 사용자 메시지 추가
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # 사용자 메시지 표시
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # 챗봇 응답 생성
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                message_placeholder.markdown("🤔 생각 중...")
                
                try:
                    # OpenAI API 호출
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.messages
                        ],
                        temperature=temperature,
                        max_tokens=1000
                    )
                    
                    # 응답 추출
                    assistant_response = response.choices[0].message.content
                    
                    # 응답 표시
                    message_placeholder.markdown(assistant_response)
                    
                    # 챗봇 응답을 세션에 추가
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                    
                except Exception as e:
                    error_message = str(e)
                    if "authentication" in error_message.lower() or "invalid" in error_message.lower():
                        message_placeholder.error("❌ API 키가 유효하지 않습니다. .env 파일의 OPENAI_API_KEY를 확인해주세요.")
                    elif "rate limit" in error_message.lower():
                        message_placeholder.error("❌ API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.")
                    elif "quota" in error_message.lower():
                        message_placeholder.error("❌ API 할당량이 소진되었습니다. OpenAI 계정을 확인해주세요.")
                    else:
                        message_placeholder.error(f"❌ 오류가 발생했습니다: {error_message}")
