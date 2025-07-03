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

def delete_phishing_mails():
    messages = st.session_state.gmail_messages
    if not messages:
        st.info("메일이 없습니다.")
        return

    phishing_indices = []
    for idx, mail in enumerate(messages):
        subject = mail.get('subject', '')
        snippet = mail.get('snippet', '')
        sender = mail.get('sender', mail.get('from', '알 수 없음'))
        combined_text = f"{subject} {snippet}"
        if "피싱" in combined_text or "phishing" in combined_text.lower():
            phishing_indices.append(idx)

    if not phishing_indices:
        st.info("피싱 메일이 없습니다.")
        return

    st.warning(f"GPT가 판단한 피싱 메일 {len(phishing_indices)}건이 있습니다.")
    for idx in phishing_indices:
        mail = messages[idx]
        sender = mail.get('sender', mail.get('from', '알 수 없음'))
        st.markdown(f"**[{idx+1}] {mail.get('subject', '')}**  \n발신자: {sender}  \n내용: {mail.get('snippet', '')}")

    if st.button("❌ 피싱 메일 삭제 진행"):
        results = delete_mails_by_indices(phishing_indices)
        if not results or not isinstance(results, list):
            st.error("삭제 처리 결과가 올바르지 않습니다.")
            return

        success_indices = [r['index'] for r in results if r.get('success')]
        failed_results = [r for r in results if not r.get('success')]

        msg = f"🗑️ 피싱 메일 {len(success_indices)}건을 휴지통으로 이동했습니다.\n\n"
        for idx in success_indices:
            mail = messages[idx]
            sender = mail.get('sender', mail.get('from', '알 수 없음'))
            msg += f"- [{idx+1}] {mail.get('subject', '')} (발신자: {sender})\n"

        if failed_results:
            msg += "\n❌ 삭제 실패한 메일:\n"
            for r in failed_results:
                idx = r.get('index', '?')
                err = r.get('error', '알 수 없는 오류')
                msg += f"- [{idx+1}] {err}\n"

        st.success(msg)

        refresh_gmail_messages()
        st.experimental_rerun()




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
    
def get_raw_mail_content(message_id):
    """Raw 형식으로 메일 가져오기"""
    try:
        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
        msg = service.users().messages().get(userId='me', id=message_id, format='raw').execute()
        
        # Base64 디코딩
        import base64
        raw_data = base64.urlsafe_b64decode(msg['raw'])

        # 이메일 파싱
        import email
        from email import policy
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 전체 구조", "📧 헤더 정보", "📄 본문 내용", "📎 첨부파일", "🔍 상세 분석"])
    
    with tab1:
        st.write("**전체 메일 구조 (JSON):**")
        st.json(full_content)
    
    with tab2:
        st.write("**헤더 정보:**")
        headers = full_content.get('headers', {})
        if headers:
            for key, value in headers.items():
                st.write(f"**{key}:** {value}")
        else:
            st.info("헤더 정보가 없습니다.")
    
    with tab3:
        st.write("**본문 내용:**")
        body_text = full_content.get('body_text', '')
        if body_text:
            st.text_area("메일 본문", body_text, height=300)
        else:
            st.info("본문 내용이 없습니다.")
    
    with tab4:
        st.write("**첨부파일 및 멀티파트 정보:**")
        parts = full_content.get('parts', [])
        if parts:
            for i, part in enumerate(parts):
                with st.expander(f"파트 {i+1}: {part.get('mimeType', 'Unknown')}"):
                    st.json(part)
                    if 'body_text' in part:
                        st.text_area(f"파트 {i+1} 내용", part['body_text'], height=150)
        else:
            st.info("첨부파일이 없습니다.")
    
    with tab5:
        st.write("**상세 분석:**")
        
        # 기본 정보
        col1, col2 = st.columns(2)
        with col1:
            st.metric("메일 크기", f"{full_content.get('sizeEstimate', 0)} bytes")
            st.metric("라벨 수", len(full_content.get('labelIds', [])))
        
        with col2:
            st.metric("파트 수", len(full_content.get('parts', [])))
            st.metric("헤더 수", len(full_content.get('headers', {})))
        
        # 라벨 정보
        if full_content.get('labelIds'):
            st.write("**라벨:**")
            for label in full_content['labelIds']:
                st.write(f"- {label}")
        
        # MIME 타입 분석
        payload = full_content.get('payload', {})
        if payload:
            st.write("**MIME 타입:**")
            st.write(f"- 메인: {payload.get('mimeType', 'Unknown')}")
            if payload.get('parts'):
                for i, part in enumerate(payload['parts']):
                    st.write(f"- 파트 {i+1}: {part.get('mimeType', 'Unknown')}")
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

def refresh_gmail_messages():
    """Gmail 메시지 새로고침"""
    messages = get_gmail_messages(50)
    st.session_state.gmail_messages = messages
    st.session_state.gmail_last_fetch = datetime.now()
    st.session_state.mail_page = 0

def render_mail_management():
    """메일 관리 섹션 - Raw 형식 사용"""
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
                    # Raw 형식으로 메일 전체 내용 가져오기
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
                            st.markdown(full_content['body_html'], unsafe_allow_html=True)
                    
                    # 텍스트 탭
                    if full_content['body_html']:
                        with tab2:
                            st.markdown("**텍스트 본문:**")
                            if full_content['body_text']:
                                st.text_area("텍스트 본문", full_content['body_text'], height=300, key=f"text_{msg['id']}")
                            else:
                                st.info("텍스트 본문이 없습니다.")
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
                                            # 다운로드 버튼 (실제로는 파일 저장 필요)
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
                    
                    # 버튼들
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔍 원본 보기", key=f"original_{msg['id']}"):
                            show_mail_original_format(msg['id'], global_idx + 1)
                    with col2:
                        if st.button("📋 전체 내용 복사", key=f"copy_{msg['id']}"):
                            content_to_copy = full_content['body_text'] if full_content['body_text'] else full_content['body_html']
                            st.success("✅ 전체 내용이 준비되었습니다! (수동으로 복사해주세요)")
                            st.code(content_to_copy, language='text')
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

def safe_rerun():
    version = tuple(map(int, st.__version__.split('.')))
    if version >= (1, 25):
        st.rerun()
    elif version >= (1, 10):
        st.experimental_rerun()
    else:
        st.warning("앱을 다시 새로고침 해주세요.")

def render_chat_interface():
    st.subheader("🤖 AI 챗봇")

    # 스타일 적용
    chat_box_style = """
    <style>
    .chat-box {
        height: 500px;
        overflow-y: auto;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #ddd;
        background-color: #f9f9f9;
    }
    .user-msg {
        text-align: right;
        background-color: #d0e7ff;
        padding: 8px 12px;
        border-radius: 15px;
        margin-bottom: 8px;
        display: inline-block;
        max-width: 80%;
    }
    .assistant-msg {
        text-align: left;
        background-color: #e8e8e8;
        padding: 8px 12px;
        border-radius: 15px;
        margin-bottom: 8px;
        display: inline-block;
        max-width: 80%;
    }
    </style>
    """
    st.markdown(chat_box_style, unsafe_allow_html=True)

    # 채팅 메시지 출력
    chat_html = '<div class="chat-box">'
    for msg in st.session_state.messages:
        role = msg['role']
        content = msg['content']
        if role == "user":
            chat_html += f'<div style="text-align:right;"><div class="user-msg">{content}</div></div>'
        else:
            chat_html += f'<div style="text-align:left;"><div class="assistant-msg">{content}</div></div>'
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)

    # "답변 생성 중..." 메시지 감지 후 API 호출 및 응답 반영
    if st.session_state.messages and st.session_state.messages[-1]["content"] == "🤔 답변 생성 중...":
        # 호출 중복 방지용 플래그 추가
        if not st.session_state.get("processing_response", False):
            st.session_state["processing_response"] = True

            # 가장 최근 user 메시지 가져오기
            last_user_msg = next(
                (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), None
            )
            if last_user_msg:
                try:
                    assistant_response = chat_with_function_call(last_user_msg, client)
                    st.session_state.messages[-1]["content"] = assistant_response

                    mail_keywords = ["삭제", "휴지통", "요약", "메일", "피싱", "새로고침"]
                    if any(kw in last_user_msg.lower() for kw in mail_keywords):
                        if st.session_state.get("gmail_authenticated", False):
                            refresh_gmail_messages()

                except Exception as e:
                    st.session_state.messages[-1]["content"] = f"❌ 응답 생성 중 오류: {str(e)}"

            # API 호출 후 플래그 초기화 및 재실행
            st.session_state["processing_response"] = False
            safe_rerun()

def process_user_prompt(prompt: str):
    global client

    if not client:
        st.error("❌ OpenAI API 키가 설정되지 않았습니다!")
        return

    if len(prompt.strip()) < 3:
        st.warning("⚠️ 너무 짧은 입력입니다. 좀 더 구체적으로 입력해 주세요.")
        return

    # 사용자 메시지 저장
    st.session_state.messages.append({"role": "user", "content": prompt})
    # 답변 생성 중 메시지 추가
    st.session_state.messages.append({"role": "assistant", "content": "🤔 답변 생성 중..."})

    # 앱 재실행하여 답변 생성 로직 트리거
    safe_rerun()

def handle_chat_input():
    global client

    st.markdown("### 💡 예시 프롬프트")
    col1, col2 = st.columns(2)
    if col1.button("📌 최근 메일 요약"):
        process_user_prompt("최근 5개 메일 요약해줘")

    if col2.button("🗑️ 피싱 메일 삭제"):
        delete_phishing_mails()

    prompt = st.chat_input("메시지를 입력하세요...")
    if prompt:
        process_user_prompt(prompt)


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
