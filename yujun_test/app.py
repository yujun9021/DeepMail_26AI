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
import email
from email import policy
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import quopri
import plotly.graph_objects as go
import re
from bs4 import BeautifulSoup

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
    if "needs_refresh" not in st.session_state:
        st.session_state.needs_refresh = False

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

def get_gmail_messages(max_results=30):
    """Gmail 메시지 목록 조회"""
    try:
        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
        results = service.users().messages().list(userId='me', maxResults=max_results).execute()
        messages = results.get('messages', [])
        
        message_details = []
        for message in messages:
            # 기본 정보만 가져오기 (전체 내용은 나중에 필요할 때)
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

def get_raw_mail_content(message_id):
    """Raw 형식으로 메일 가져오기"""
    try:
        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
        msg = service.users().messages().get(userId='me', id=message_id, format='raw').execute()
        
        # Base64 디코딩
        import base64
        raw_data = base64.urlsafe_b64decode(msg['raw'])
        
        # 이메일 파싱
        email_message = email.message_from_bytes(raw_data, policy=policy.default)
        
        return email_message
        
    except Exception as e:
        st.error(f"Raw 메일 가져오기 실패: {str(e)}")
        return None

def extract_text_from_email(email_message):
    """이메일에서 텍스트 추출"""
    text_content = ""
    html_content = ""
    
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # 첨부파일이 아닌 경우만 처리
            if "attachment" not in content_disposition:
                if content_type == "text/plain":
                    try:
                        text_content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        text_content += part.get_payload(decode=True).decode('latin-1', errors='ignore')
                elif content_type == "text/html":
                    try:
                        html_content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        html_content += part.get_payload(decode=True).decode('latin-1', errors='ignore')
    else:
        # 단일 파트 메일
        content_type = email_message.get_content_type()
        if content_type == "text/plain":
            try:
                text_content = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                text_content = email_message.get_payload(decode=True).decode('latin-1', errors='ignore')
        elif content_type == "text/html":
            try:
                html_content = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                html_content = email_message.get_payload(decode=True).decode('latin-1', errors='ignore')
    
    return text_content, html_content

def extract_attachments_from_email(email_message):
    """이메일에서 첨부파일 추출"""
    attachments = []
    
    if email_message.is_multipart():
        for part in email_message.walk():
            content_disposition = str(part.get("Content-Disposition"))
            
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    try:
                        file_data = part.get_payload(decode=True)
                        attachments.append({
                            'filename': filename,
                            'data': file_data,
                            'content_type': part.get_content_type(),
                            'size': len(file_data)
                        })
                    except Exception as e:
                        st.warning(f"첨부파일 {filename} 처리 실패: {str(e)}")
    
    return attachments

def get_mail_full_content(message_id):
    """메일의 전체 내용을 가져오는 함수 (Raw 형식 사용)"""
    try:
        # Raw 형식으로 메일 가져오기
        email_message = get_raw_mail_content(message_id)
        if not email_message:
            return {
                'subject': '오류',
                'from': '오류',
                'to': '오류',
                'date': '오류',
                'body_text': '메일을 가져올 수 없습니다.',
                'body_html': '',
                'attachments': [],
                'error': True
            }
        
        # 헤더 정보 추출
        subject = email_message.get('Subject', '제목 없음')
        from_addr = email_message.get('From', '발신자 없음')
        to_addr = email_message.get('To', '수신자 없음')
        date = email_message.get('Date', '날짜 없음')
        
        # 본문 추출
        text_content, html_content = extract_text_from_email(email_message)
        
        # 첨부파일 추출
        attachments = extract_attachments_from_email(email_message)
        
        return {
            'subject': subject,
            'from': from_addr,
            'to': to_addr,
            'date': date,
            'body_text': text_content,
            'body_html': html_content,
            'attachments': attachments,
            'error': False
        }
        
    except Exception as e:
        return {
            'subject': '오류',
            'from': '오류',
            'to': '오류',
            'date': '오류',
            'body_text': f'메일 내용을 가져오는 중 오류가 발생했습니다: {str(e)}',
            'body_html': '',
            'attachments': [],
            'error': True
        }

def debug_mail_structure(message_id):
    """메일 구조를 디버깅하는 함수"""
    try:
        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
        msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        
        st.write("**🔍 메일 구조 디버깅:**")
        st.write(f"**메일 ID:** {msg.get('id')}")
        st.write(f"**스니펫:** {msg.get('snippet')}")
        
        payload = msg.get('payload', {})
        st.write(f"**메인 MIME 타입:** {payload.get('mimeType')}")
        st.write(f"**Body 데이터 존재:** {bool(payload.get('body', {}).get('data'))}")
        st.write(f"**Parts 존재:** {bool(payload.get('parts'))}")
        st.write(f"**Parts 개수:** {len(payload.get('parts', []))}")
        
        if payload.get('parts'):
            st.write("**Parts 상세 정보:**")
            for i, part in enumerate(payload['parts']):
                st.write(f"  파트 {i+1}: {part.get('mimeType')} - Body 데이터: {bool(part.get('body', {}).get('data'))}")
                if part.get('body', {}).get('data'):
                    st.write(f"    데이터 길이: {len(part['body']['data'])}")
        
        return msg
        
    except Exception as e:
        st.error(f"디버깅 중 오류: {str(e)}")
        return None

def show_mail_original_format(message_id, mail_index):
    """메일의 원본 형식을 표시하는 함수"""
    st.subheader(f"📧 [{mail_index}] 메일 원본 형식")
    
    # 로딩 표시
    with st.spinner("메일 원본 데이터를 가져오는 중..."):
        full_content = get_mail_full_content(message_id)
    
    if 'error' in full_content:
        st.error(full_content['error'])
        return
    
    # 탭으로 구분하여 표시
    tab1, tab2, tab3 = st.tabs(["🌐 HTML 보기", "📄 텍스트 보기", "📎 첨부파일"])
    
    with tab1:
        st.markdown("**HTML 렌더링:**")
        st.markdown(full_content['body_html'], unsafe_allow_html=True)
    
    with tab2:
        st.markdown("**텍스트 본문:**")
        if full_content['body_text']:
            st.text_area("텍스트 본문", full_content['body_text'], height=300, key=f"text_{message_id}")
        else:
            st.info("텍스트 본문이 없습니다.")
    
    with tab3:
        if full_content['attachments']:
            st.markdown("**첨부파일 목록:**")
            for i, attachment in enumerate(full_content['attachments']):
                with st.expander(f"📎 {attachment['filename']} ({attachment['size']} bytes)"):
                    st.write(f"**파일명:** {attachment['filename']}")
                    st.write(f"**크기:** {attachment['size']} bytes")
                    st.write(f"**타입:** {attachment['content_type']}")
                    
                    # 이미지인 경우 표시
                    if attachment['content_type'].startswith('image/'):
                        st.image(attachment['data'], caption=attachment['filename'])
                    else:
                        # 다운로드 버튼
                        st.download_button(
                            label=f"📥 {attachment['filename']} 다운로드",
                            data=attachment['data'],
                            file_name=attachment['filename'],
                            mime=attachment['content_type']
                        )
        else:
            st.info("첨부파일이 없습니다.")

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
                # 삭제 성공 시 메일 목록 새로고침
                if success and st.session_state.gmail_authenticated:
                    refresh_gmail_messages()
                return {"success": success, "message": "메일이 휴지통으로 이동되었습니다." if success else "메일 이동에 실패했습니다."}
            else:
                return {"success": False, "error": "message_id가 필요합니다."}
        
        elif function_name == "delete_mails_by_indices":
            indices = arguments.get("indices", [])
            if indices:
                results = delete_mails_by_indices(indices)
                # 삭제 작업 후 메일 목록 새로고침
                if st.session_state.gmail_authenticated:
                    refresh_gmail_messages()
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
            
            response_content = final_response.choices[0].message.content
            
            # 삭제 관련 함수 실행 후 UI 새로고침 플래그 설정
            if function_name in ["move_message_to_trash", "delete_mails_by_indices"]:
                st.session_state.needs_refresh = True
            
            return response_content
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
    messages = get_gmail_messages(30)
    st.session_state.gmail_messages = messages
    st.session_state.gmail_last_fetch = datetime.now()
    st.session_state.mail_page = 0

def clean_html_content(html_content):
    """HTML 콘텐츠를 정리하고 안전하게 렌더링"""
    try:
        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 스크립트 태그 제거
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 위험한 태그들 제거 또는 변환
        dangerous_tags = ['iframe', 'object', 'embed', 'form', 'input', 'button']
        for tag in dangerous_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 외부 링크를 안전하게 처리
        for link in soup.find_all('a'):
            if link.get('href'):
                link['target'] = '_blank'
                link['rel'] = 'noopener noreferrer'
        
        # 이미지 태그 정리
        for img in soup.find_all('img'):
            if not img.get('src'):
                img.decompose()
        
        return str(soup)
        
    except Exception as e:
        # HTML 파싱 실패 시 텍스트만 추출
        return extract_text_from_html(html_content)

def extract_text_from_html(html_content):
    """HTML에서 텍스트만 추출"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator='\n', strip=True)
    except:
        # HTML 태그 제거
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        # HTML 엔티티 디코딩
        clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return clean_text

def render_mail_management():
    """메일 관리 섹션 - 크기 제한 추가"""
    st.markdown("---")
    st.subheader("📧 메일 관리")
    
    if st.session_state.gmail_authenticated:
        # 최초 로그인 시 또는 세션에 메일이 없으면 자동으로 불러오기
        if st.session_state.gmail_messages is None:
            with st.spinner("메일 목록을 불러오는 중..."):
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
                    with st.spinner("메일 목록을 새로고침하는 중..."):
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
                    # 메일 전체 내용을 바로 가져오기
                    with st.spinner("메일 내용을 불러오는 중..."):
                        full_content = get_mail_full_content(msg['id'])
                    
                    if full_content['error']:
                        st.error("메일을 불러올 수 없습니다.")
                        continue
                    
                    # 메일 정보 표시
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.write(f"**📧 발신자:** {full_content['from']}")
                        st.write(f"**📅 날짜:** {full_content['date']}")
                    with col2:
                        st.write(f"**📬 수신자:** {full_content['to']}")
                        if full_content['attachments']:
                            st.write(f"**📎 첨부파일:** {len(full_content['attachments'])}개")
                    
                    st.markdown("---")
                    
                    # 탭으로 구분하여 표시
                    if full_content['body_html']:
                        tab1, tab2, tab3 = st.tabs(["🌐 HTML 보기", "📄 텍스트 보기", "📎 첨부파일"])
                    else:
                        tab1, tab2 = st.tabs(["📄 텍스트 보기", "📎 첨부파일"])
                    
                    # HTML 탭
                    if full_content['body_html']:
                        with tab1:
                            st.markdown("**HTML 렌더링:**")
                            try:
                                # HTML 정리
                                cleaned_html = clean_html_content(full_content['body_html'])
                                
                                # 스크롤 가능한 컨테이너로 감싸기
                                with st.container():
                                    st.markdown("""
                                    <style>
                                    .email-scroll-container {
                                        max-height: 800px;
                                        overflow-y: auto;
                                        border: 1px solid #ddd;
                                        padding: 10px;
                                        border-radius: 5px;
                                    }
                                    </style>
                                    """, unsafe_allow_html=True)
                                    
                                    st.markdown(f"""
                                    <div class="email-scroll-container">
                                    {cleaned_html}
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                            except Exception as e:
                                st.error(f"HTML 렌더링 실패: {str(e)}")
                                st.info("텍스트 버전으로 표시합니다.")
                                text_content = extract_text_from_html(full_content['body_html'])
                                st.text_area("정리된 텍스트", text_content, height=300)
                    
                    # 텍스트 탭
                    if full_content['body_html']:
                        with tab2:
                            st.markdown("**텍스트 본문:**")
                            if full_content['body_text']:
                                st.text_area("텍스트 본문", full_content['body_text'], height=300, key=f"text_{msg['id']}")
                            else:
                                # HTML에서 텍스트 추출
                                text_content = extract_text_from_html(full_content['body_html'])
                                st.text_area("HTML에서 추출한 텍스트", text_content, height=300, key=f"extracted_{msg['id']}")
                    else:
                        with tab1:
                            st.markdown("**텍스트 본문:**")
                            if full_content['body_text']:
                                st.text_area("텍스트 본문", full_content['body_text'], height=300, key=f"text_{msg['id']}")
                            else:
                                st.info("텍스트 본문이 없습니다.")
                    
                    # 첨부파일 탭
                    if full_content['body_html']:
                        with tab3:
                            if full_content['attachments']:
                                st.markdown("**첨부파일 목록:**")
                                for i, attachment in enumerate(full_content['attachments']):
                                    with st.expander(f"📎 {attachment['filename']} ({attachment['size']} bytes)"):
                                        st.write(f"**파일명:** {attachment['filename']}")
                                        st.write(f"**크기:** {attachment['size']} bytes")
                                        st.write(f"**타입:** {attachment['content_type']}")
                                        
                                        # 이미지인 경우 표시
                                        if attachment['content_type'].startswith('image/'):
                                            st.image(attachment['data'], caption=attachment['filename'])
                                        else:
                                            # 다운로드 버튼
                                            st.download_button(
                                                label=f"📥 {attachment['filename']} 다운로드",
                                                data=attachment['data'],
                                                file_name=attachment['filename'],
                                                mime=attachment['content_type']
                                            )
                            else:
                                st.info("첨부파일이 없습니다.")
                    else:
                        with tab2:
                            if full_content['attachments']:
                                st.markdown("**첨부파일 목록:**")
                                for i, attachment in enumerate(full_content['attachments']):
                                    with st.expander(f"📎 {attachment['filename']} ({attachment['size']} bytes)"):
                                        st.write(f"**파일명:** {attachment['filename']}")
                                        st.write(f"**크기:** {attachment['size']} bytes")
                                        st.write(f"**타입:** {attachment['content_type']}")
                                        
                                        # 이미지인 경우 표시
                                        if attachment['content_type'].startswith('image/'):
                                            st.image(attachment['data'], caption=attachment['filename'])
                                        else:
                                            # 다운로드 버튼
                                            st.download_button(
                                                label=f"📥 {attachment['filename']} 다운로드",
                                                data=attachment['data'],
                                                file_name=attachment['filename'],
                                                mime=attachment['content_type']
                                            )
                            else:
                                st.info("첨부파일이 없습니다.")
                    
                    st.markdown("---")
                    
                    # 메일 번호 표시 (사용자가 챗봇에서 참조할 수 있도록)
                    st.info(f"💡 이 메일을 챗봇에서 참조하려면 '{global_idx + 1}번 메일'이라고 말하세요!")
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
                
                # 삭제 관련 작업 후 UI 새로고침
                if st.session_state.get("needs_refresh", False):
                    st.session_state.needs_refresh = False
                    time.sleep(0.5)  # 잠시 대기 후 새로고침
                    st.rerun()
                        
            except Exception as e:
                error_msg = f"❌ 응답 생성 중 오류: {str(e)}"
                message_placeholder.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

def draw_gauge_chart(risk_score):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=risk_score,
        title={'text': "평균 피싱 위험도 (%)"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "darkred"},
            'steps': [
                {'range': [0, 30], 'color': 'lightgreen'},
                {'range': [30, 70], 'color': 'yellow'},
                {'range': [70, 100], 'color': 'red'}
            ]
        }
    ))
    st.plotly_chart(fig, use_container_width=True)

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
        avg_risk = 55.5
        draw_gauge_chart(avg_risk)
        render_mail_management()

        
    # 오른쪽 컬럼: 챗봇
    with col2:
        render_chat_interface()
        handle_chat_input()

if __name__ == "__main__":
    main()
