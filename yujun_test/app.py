"""
DeepMail - OpenAI 챗봇 with Gmail 연동
Function Calling 기반 AI Agent 구현
"""

import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from googleapiclient.discovery import build
import time

# =============================================================================
# 설정 및 초기화
# =============================================================================

# 환경변수 로드
load_dotenv()

# Gmail API 설정
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

# 페이지 설정
st.set_page_config(
    page_title="DeepMail - AI 챗봇",
    page_icon="🤖",
    layout="wide"
)

# =============================================================================
# 세션 상태 초기화
# =============================================================================

def initialize_session_state():
    """세션 상태 초기화"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "gmail_authenticated" not in st.session_state:
        st.session_state.gmail_authenticated = False
    if "gmail_credentials" not in st.session_state:
        st.session_state.gmail_credentials = None
    if "gmail_messages" not in st.session_state:
        st.session_state.gmail_messages = None
    if "gmail_last_fetch" not in st.session_state:
        st.session_state.gmail_last_fetch = None
    if "mail_page" not in st.session_state:
        st.session_state.mail_page = 0
    if "mail_page_size" not in st.session_state:
        st.session_state.mail_page_size = 5
    if "selected_mail_index" not in st.session_state:
        st.session_state.selected_mail_index = None

initialize_session_state()

# =============================================================================
# Gmail 관련 함수들
# =============================================================================

def authenticate_gmail():
    """Gmail OAuth 인증"""
    creds = None
    
    # 기존 토큰 로드
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # 토큰 유효성 검사 및 갱신
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                creds = None
        
        # 새 인증 진행
        if not creds:
            if os.path.exists('credentials.json'):
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                st.error("❌ credentials.json 파일이 필요합니다!")
                return None
        
        # 토큰 저장
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def get_gmail_messages(max_results=50):
    """Gmail 메시지 목록 조회"""
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
        st.error(f"❌ 메일 목록 조회 실패: {str(e)}")
        return []

def move_message_to_trash(message_id):
    """메일을 휴지통으로 이동"""
    if not st.session_state.gmail_credentials:
        st.error("❌ Gmail 인증이 필요합니다.")
        return False
    
    try:
        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
        result = service.users().messages().trash(userId='me', id=message_id).execute()
        
        if result and 'id' in result:
            return True
        else:
            st.error("❌ 휴지통 이동 결과를 확인할 수 없습니다.")
            return False
            
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            st.error("❌ 메일을 찾을 수 없습니다. 이미 삭제되었을 수 있습니다.")
        elif "403" in error_msg:
            st.error("❌ 메일 삭제 권한이 없습니다.")
        else:
            st.error(f"❌ 메일 이동 실패: {error_msg}")
        return False

def delete_mails_by_indices(indices):
    """번호(인덱스) 리스트로 여러 메일을 휴지통으로 이동"""
    results = []
    messages = st.session_state.gmail_messages
    for idx in indices:
        if 0 <= idx < len(messages):
            msg_id = messages[idx]['id']
            result = move_message_to_trash(msg_id)
            results.append({"index": idx, "success": result})
        else:
            results.append({"index": idx, "success": False, "error": "존재하지 않는 번호"})
    return results

def summarize_mails_by_indices(indices, model="gpt-3.5-turbo", temperature=0.5):
    """번호(인덱스) 리스트로 여러 메일을 OpenAI GPT로 요약"""
    messages = st.session_state.gmail_messages
    summaries = []
    client = initialize_openai_client()

    for idx in indices:
        if 0 <= idx < len(messages):
            msg = messages[idx]
            prompt = f"다음 이메일을 3줄 이내로 요약해줘.\n\n제목: {msg['subject']}\n내용: {msg['snippet']}"
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=300
                )
                summary = response.choices[0].message.content.strip()
            except Exception as e:
                summary = f"[{idx+1}] 요약 실패: {str(e)}"
            summaries.append(f"[{idx+1}] {msg['subject']}\n{summary}")
        else:
            summaries.append(f"[{idx+1}] 존재하지 않는 메일입니다.")
    return "\n\n".join(summaries)

def get_mail_content(index):
    """번호(인덱스)로 메일의 제목/내용을 반환"""
    messages = st.session_state.gmail_messages
    if 0 <= index < len(messages):
        msg = messages[index]
        return {
            "subject": msg["subject"],
            "sender": msg["sender"],
            "snippet": msg["snippet"]
        }
    else:
        return {
            "error": f"{index+1}번 메일이 존재하지 않습니다."
        }

# =============================================================================
# Function Calling 스키마 정의
# =============================================================================

FunctionSchema = [
    {
        "name": "move_message_to_trash",
        "description": "지정한 Gmail 메시지를 휴지통으로 이동합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "휴지통으로 이동할 Gmail 메시지의 고유 ID"
                }
            },
            "required": ["message_id"]
        },
    },
    {
        "name": "delete_mails_by_indices",
        "description": "선택한 번호(인덱스)의 Gmail 메일들을 휴지통으로 이동합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "indices": {
                    "type": "array",
                    "items": { "type": "integer" },
                    "description": "삭제할 메일의 번호(0부터 시작, 예: [0, 2, 4])"
                }
            },
            "required": ["indices"]
        },
    },
    {
        "name": "summarize_mails_by_indices",
        "description": "선택한 번호(인덱스)의 Gmail 메일들을 OpenAI GPT로 요약합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "indices": {
                    "type": "array",
                    "items": { "type": "integer" },
                    "description": "요약할 메일의 번호(0부터 시작, 예: [0, 2, 4])"
                }
            },
            "required": ["indices"]
        }
    },
    {
        "name": "get_mail_content",
        "description": "번호(인덱스)로 Gmail 메일의 제목, 발신자, 내용을 반환합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "메일 번호(0부터 시작, 예: 0은 1번 메일)"
                }
            },
            "required": ["index"]
        }
    }
]

# =============================================================================
# OpenAI 관련 함수들
# =============================================================================

def initialize_openai_client():
    """OpenAI 클라이언트 초기화"""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return OpenAI(api_key=api_key)
    return None

def handle_openai_error(error):
    """OpenAI API 오류 처리"""
    error_message = str(error)
    if "authentication" in error_message.lower() or "invalid" in error_message.lower():
        return "❌ API 키가 유효하지 않습니다. .env 파일의 OPENAI_API_KEY를 확인해주세요."
    elif "rate limit" in error_message.lower():
        return "❌ API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
    elif "quota" in error_message.lower():
        return "❌ API 할당량이 소진되었습니다. OpenAI 계정을 확인해주세요."
    else:
        return f"❌ 오류가 발생했습니다: {error_message}"

# =============================================================================
# Function Calling 핸들러
# =============================================================================

def handle_function_call(function_name, arguments):
    """Function calling 결과를 실제 함수로 실행"""
    try:
        if function_name == "move_message_to_trash":
            message_id = arguments.get("message_id")
            if message_id:
                success = move_message_to_trash(message_id)
                return {"success": success, "message": "메일이 휴지통으로 이동되었습니다." if success else "메일 이동에 실패했습니다."}
            else:
                return {"success": False, "error": "message_id가 필요합니다."}
        
        elif function_name == "delete_mails_by_indices":
            indices = arguments.get("indices", [])
            if indices:
                results = delete_mails_by_indices(indices)
                return {"results": results, "message": f"{len(indices)}개 메일 처리 완료"}
            else:
                return {"success": False, "error": "indices가 필요합니다."}
        
        elif function_name == "summarize_mails_by_indices":
            indices = arguments.get("indices", [])
            if indices:
                summary = summarize_mails_by_indices(indices)
                return {"summary": summary, "message": f"{len(indices)}개 메일 요약 완료"}
            else:
                return {"success": False, "error": "indices가 필요합니다."}
        
        elif function_name == "get_mail_content":
            index = arguments.get("index")
            if index is not None:
                content = get_mail_content(index)
                return content
            else:
                return {"error": "index가 필요합니다."}
        
        else:
            return {"error": f"알 수 없는 함수: {function_name}"}
    
    except Exception as e:
        return {"error": f"함수 실행 중 오류: {str(e)}"}

def chat_with_function_call(user_input, client):
    """Function calling을 활용한 챗봇 대화"""
    try:
        # 1. 사용자 메시지 준비
        messages = [{"role": "user", "content": user_input}]
        
        # 2. 함수 스키마와 함께 OpenAI API 호출
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            functions=FunctionSchema,
            function_call="auto"
        )
        message = response.choices[0].message

        # 3. function_call이 있으면 실제 함수 실행
        if hasattr(message, "function_call") and message.function_call:
            function_name = message.function_call.name
            arguments = json.loads(message.function_call.arguments)
            
            # 실제 함수 실행
            function_result = handle_function_call(function_name, arguments)

            # 4. 함수 실행 결과를 function 역할로 추가
            messages.append({
                "role": "function",
                "name": function_name,
                "content": json.dumps(function_result, ensure_ascii=False)
            })

            # 5. 최종 자연어 응답 생성
            final_response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                functions=FunctionSchema,
                function_call="none"
            )
            return final_response.choices[0].message.content
        else:
            # 일반 답변
            return message.content
    
    except Exception as e:
        return f"❌ 오류가 발생했습니다: {str(e)}"

# =============================================================================
# UI 컴포넌트들
# =============================================================================

def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # OpenAI API 상태
        render_openai_status()
        st.markdown("---")
        
        # Gmail 연결
        render_gmail_connection()
        st.markdown("---")
        
        # 메일 페이지 크기 설정
        if st.session_state.gmail_authenticated:
            st.subheader("📧 메일 설정")
            page_size = st.selectbox(
                "페이지당 메일 개수",
                [5, 10, 15, 20],
                index=0,
                help="한 페이지에 표시할 메일 개수를 선택하세요"
            )
            if page_size != st.session_state.mail_page_size:
                st.session_state.mail_page_size = page_size
                st.session_state.mail_page = 0
                st.rerun()
            st.markdown("---")
        
        # 챗봇 설정
        model, temperature = render_chatbot_settings()
        st.session_state["sidebar_model"] = model
        st.session_state["sidebar_temperature"] = temperature

        # 채팅 기록 초기화
        st.markdown("---")
        if st.button("💬 채팅 기록 초기화"):
            st.session_state.messages = []
            st.success("✅ 채팅 기록이 초기화되었습니다!")

def render_openai_status():
    """OpenAI API 상태 표시"""
    if client:
        st.success("✅ OpenAI API 키가 설정되었습니다!")
    else:
        st.error("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        st.info("💡 .env 파일에 OPENAI_API_KEY=your_api_key_here를 추가하세요.")

def render_gmail_connection():
    """Gmail 연결 섹션"""
    st.subheader("📧 Gmail 연결")
    
    if not st.session_state.gmail_authenticated:
        if st.button("🔑 Gmail 로그인", type="primary"):
            handle_gmail_login()
    else:
        st.success("✅ Gmail에 로그인되어 있습니다!")
        
        if st.button("🚪 Gmail 로그아웃"):
            handle_gmail_logout()

def handle_gmail_login():
    """Gmail 로그인 처리"""
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

def handle_gmail_logout():
    """Gmail 로그아웃 처리"""
    st.session_state.gmail_authenticated = False
    st.session_state.gmail_credentials = None
    if os.path.exists('token.pickle'):
        os.remove('token.pickle')
    st.success("✅ Gmail 로그아웃 완료!")
    st.rerun()

def refresh_gmail_messages():
    """Gmail 메시지 새로고침"""
    messages = get_gmail_messages(50)
    st.session_state.gmail_messages = messages
    st.session_state.gmail_last_fetch = datetime.now()
    st.session_state.mail_page = 0

def render_mail_management():
    """메일 관리 섹션"""
    st.markdown("---")
    st.subheader("📧 메일 관리")
    
    if st.session_state.gmail_authenticated:
        # 최초 로그인 시 또는 세션에 메일이 없으면 자동으로 불러오기
        if st.session_state.gmail_messages is None:
            refresh_gmail_messages()
        
        # 마지막 불러온 시간 표시
        if st.session_state.gmail_last_fetch:
            st.caption(f"마지막 업데이트: {st.session_state.gmail_last_fetch.strftime('%Y-%m-%d %H:%M:%S')}")
        
        messages = st.session_state.gmail_messages
        if messages:
            total_messages = len(messages)
            total_pages = (total_messages + st.session_state.mail_page_size - 1) // st.session_state.mail_page_size
            
            # 페이지 정보 표시
            st.info(f"총 {total_messages}개 메일 (페이지 {st.session_state.mail_page + 1}/{total_pages})")
            
            # 페이지네이션 버튼
            cols = st.columns([2, 2, 1, 1, 1, 1, 2, 2])

            with cols[0]:
                if st.button("🔄 새로고침"):
                    refresh_gmail_messages()
                    st.rerun()

            with cols[2]:
                if st.button("⏮️", key="first", disabled=st.session_state.mail_page == 0):
                    st.session_state.mail_page = 0
                    st.rerun()
            with cols[3]:
                if st.button("◀️", key="prev", disabled=st.session_state.mail_page == 0):
                    st.session_state.mail_page = max(0, st.session_state.mail_page - 1)
                    st.rerun()
            with cols[4]:
                if st.button("▶️", key="next", disabled=st.session_state.mail_page >= total_pages - 1):
                    st.session_state.mail_page = min(total_pages - 1, st.session_state.mail_page + 1)
                    st.rerun()
            with cols[5]:
                if st.button("⏭️", key="last", disabled=st.session_state.mail_page >= total_pages - 1):
                    st.session_state.mail_page = total_pages - 1
                    st.rerun()
            
            # 현재 페이지의 메일들 표시
            start_idx = st.session_state.mail_page * st.session_state.mail_page_size
            end_idx = min(start_idx + st.session_state.mail_page_size, total_messages)
            current_messages = messages[start_idx:end_idx]
            
            for i, msg in enumerate(current_messages):
                global_idx = start_idx + i
                with st.expander(f"[{global_idx + 1}] {msg['subject']}"):
                    st.write(f"**발신자:** {msg['sender']}")
                    st.write(f"**내용:** {msg['snippet']}")
                    
                    # 선택 버튼
                    if st.button("이 메일 선택", key=f"select_{msg['id']}"):
                        st.session_state.selected_mail_index = global_idx
                    
                    # 삭제 버튼
                    if st.button(f"❌ 휴지통으로 이동", key=f"trash_{msg['id']}", type="secondary"):
                        status_placeholder = st.empty()
                        status_placeholder.info("🔄 메일을 휴지통으로 이동하는 중...")
                        success = move_message_to_trash(msg['id'])
                        if success:
                            status_placeholder.success("✅ 메일이 휴지통으로 이동되었습니다!")
                            refresh_gmail_messages()
                            st.rerun()
                        else:
                            status_placeholder.error("❌ 메일 이동에 실패했습니다.")

            # 선택된 메일 정보 표시
            if st.session_state.selected_mail_index is not None:
                sel = st.session_state.selected_mail_index
                st.success(f"현재 선택된 메일: [{sel+1}] {messages[sel]['subject']}")
        else:
            st.info("📭 메일이 없습니다.")
    else:
        st.info(" Gmail에 로그인하면 메일 목록이 표시됩니다.")

def render_chatbot_settings():
    """챗봇 설정 섹션"""
    model = st.selectbox(
        "모델 선택",
        ["gpt-3.5-turbo", "gpt-4"],
        help="사용할 OpenAI 모델을 선택하세요"
    )
    
    temperature = st.slider(
        "창의성 (Temperature)",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1,
        help="높을수록 더 창의적인 응답을 생성합니다"
    )
    
    return model, temperature

def render_chat_interface():
    """채팅 인터페이스 렌더링"""
    st.subheader("🤖 AI 챗봇")
    
    # 기존 메시지 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])

def handle_chat_input():
    """채팅 입력 처리"""
    prompt = st.chat_input("메시지를 입력하세요...")
    if prompt:
        if not client:
            st.error("❌ OpenAI API 키가 설정되지 않았습니다!")
            return
        
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
                # Function calling을 활용한 응답 생성
                assistant_response = chat_with_function_call(prompt, client)
                
                message_placeholder.markdown(assistant_response)
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                
                # 메일 관련 작업 후 메일 목록 새로고침
                if any(keyword in prompt.lower() for keyword in ["삭제", "휴지통", "요약", "메일"]):
                    if st.session_state.gmail_authenticated:
                        refresh_gmail_messages()
                        st.rerun()
                        
            except Exception as e:
                error_msg = f"❌ 응답 생성 중 오류: {str(e)}"
                message_placeholder.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# =============================================================================
# 메인 애플리케이션
# =============================================================================

def main():
    """메인 애플리케이션"""
    global client
    client = initialize_openai_client()
    
    # 헤더
    st.title("DeepMail - AI 챗봇 & Gmail 관리")
    st.markdown("OpenAI Function Calling 기반 AI Agent로 Gmail을 관리하세요!")
    
    # 사이드바 렌더링
    render_sidebar()
    
    # 메인 화면을 두 컬럼으로 분할
    col1, col2 = st.columns([1, 1])
    
    # 왼쪽 컬럼: 메일 관리
    with col1:
        render_mail_management()
    
    # 오른쪽 컬럼: 챗봇
    with col2:
        render_chat_interface()
        handle_chat_input()

if __name__ == "__main__":
    main()
