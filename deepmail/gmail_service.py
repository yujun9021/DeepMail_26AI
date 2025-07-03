"""
DeepMail - Gmail 서비스 모듈
"""

import streamlit as st
import os
import pickle
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import email
from email import policy
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import quopri
import re
from bs4 import BeautifulSoup
from config import SCOPES, MAIL_CONFIG

class GmailService:
    """Gmail 서비스 클래스"""
    
    def __init__(self):
        self.credentials = None
        self.service = None
    
    def authenticate(self):
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
        
        self.credentials = creds
        if creds:
            self.service = build('gmail', 'v1', credentials=creds)
        return creds
    
    def get_messages(self, max_results=None):
        """Gmail 메시지 목록 조회 (배치 요청으로 최적화)"""
        if not self.service:
            st.error("❌ Gmail 서비스가 초기화되지 않았습니다.")
            return []
        
        try:
            max_results = max_results or MAIL_CONFIG['max_results']
            results = self.service.users().messages().list(userId='me', maxResults=max_results).execute()
            messages = results.get('messages', [])
            
            if not messages:
                return []
            
            # 배치 요청으로 메일 상세 정보 가져오기
            batch = self.service.new_batch_http_request()
            message_details = []
            
            def callback(request_id, response, exception):
                if exception is None:
                    headers = response['payload']['headers']
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '제목 없음')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), '발신자 없음')
                    
                    message_details.append({
                        'id': response['id'],
                        'subject': subject,
                        'sender': sender,
                        'snippet': response.get('snippet', '')
                    })
                else:
                    st.warning(f"메일 정보 가져오기 실패: {exception}")
            
            # 배치 요청에 메일 ID들 추가
            for message in messages:
                batch.add(
                    self.service.users().messages().get(userId='me', id=message['id']),
                    callback=callback
                )
            
            # 배치 요청 실행
            batch.execute()
            
            return message_details
            
        except Exception as e:
            st.error(f"❌ 메일 목록 조회 실패: {str(e)}")
            return []
    
    def move_to_trash(self, message_id):
        """메일을 휴지통으로 이동"""
        if not self.service:
            st.error("❌ Gmail 인증이 필요합니다.")
            return False
        
        try:
            result = self.service.users().messages().trash(userId='me', id=message_id).execute()
            
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
    
    def get_raw_message(self, message_id):
        """Raw 형식으로 메일 가져오기"""
        if not self.service:
            st.error("❌ Gmail 서비스가 초기화되지 않았습니다.")
            return None
        
        try:
            msg = self.service.users().messages().get(userId='me', id=message_id, format='raw').execute()
            
            # Base64 디코딩
            import base64
            raw_data = base64.urlsafe_b64decode(msg['raw'])
            
            # 이메일 파싱
            email_message = email.message_from_bytes(raw_data, policy=policy.default)
            
            return email_message
            
        except Exception as e:
            st.error(f"Raw 메일 가져오기 실패: {str(e)}")
            return None

class EmailParser:
    """이메일 파싱 클래스"""
    
    @staticmethod
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
    
    @staticmethod
    def extract_attachments(email_message):
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
    
    @staticmethod
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
            return EmailParser.extract_text_from_html(html_content)
    
    @staticmethod
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

# 전역 Gmail 서비스 인스턴스
gmail_service = GmailService()
email_parser = EmailParser() 