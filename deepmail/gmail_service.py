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
from logger import logger, activity_logger, performance_logger, log_api_call

class GmailService:
    """Gmail 서비스 클래스"""
    
    def __init__(self):
        self.credentials = None
        self.service = None
    
    @log_api_call("Gmail_Authentication")
    def authenticate(self):
        """Gmail OAuth 인증"""
        logger.info("Gmail 인증 시작")
        creds = None
        
        # 기존 토큰 로드
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
            logger.debug("기존 토큰 로드됨")
        
        # 토큰 유효성 검사 및 갱신
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("토큰 갱신 시도")
                    creds.refresh(Request())
                    logger.info("토큰 갱신 성공")
                except Exception as e:
                    logger.warning(f"토큰 갱신 실패: {str(e)}")
                    if os.path.exists('token.pickle'):
                        os.remove('token.pickle')
                    creds = None
            
            # 새 인증 진행
            if not creds:
                if os.path.exists('credentials.json'):
                    logger.info("새 OAuth 인증 시작")
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                    logger.info("OAuth 인증 완료")
                else:
                    logger.error("credentials.json 파일이 없음")
                    st.error("❌ credentials.json 파일이 필요합니다!")
                    return None
            
            # 토큰 저장
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
            logger.info("토큰 저장 완료")
        
        self.credentials = creds
        if creds:
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail 서비스 빌드 완료")
        return creds
    
    @log_api_call("Gmail_GetMessages")
    def get_messages(self, max_results=None):
        """Gmail 메시지 목록 조회 (최소한의 정보만 가져오기)"""
        if not self.service:
            logger.error("Gmail 서비스가 초기화되지 않음")
            st.error("❌ Gmail 서비스가 초기화되지 않았습니다.")
            return []
        
        try:
            max_results = max_results or MAIL_CONFIG['max_results']
            logger.info(f"메일 목록 조회 시작 (최대 {max_results}개)")
            
            results = self.service.users().messages().list(userId='me', maxResults=max_results).execute()
            messages = results.get('messages', [])
            
            if not messages:
                logger.info("조회된 메일이 없음")
                return []
            
            logger.info(f"총 {len(messages)}개 메일 발견")
            
            # 최소한의 정보만 가져오기 (제목, 발신자, 스니펫)
            # 배치 요청 대신 개별 요청으로 변경하여 429 에러 방지
            message_details = []
            success_count = 0
            error_count = 0
            
            for i, message in enumerate(messages):
                try:
                    # 개별 메일 정보 가져오기 (필수 정보만)
                    msg = self.service.users().messages().get(
                        userId='me', 
                        id=message['id'],
                        format='metadata',
                        metadataHeaders=['Subject', 'From']
                    ).execute()
                    
                    headers = msg['payload']['headers']
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '제목 없음')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), '발신자 없음')
                    
                    message_details.append({
                        'id': msg['id'],
                        'subject': subject,
                        'sender': sender,
                        'snippet': msg.get('snippet', '')
                    })
                    success_count += 1
                    
                    # 진행률 표시 (숫자만 업데이트)
                    if i % 10 == 0:
                        # 기존 진행률 메시지가 있으면 업데이트, 없으면 새로 생성
                        progress_key = "mail_loading_progress"
                        if progress_key not in st.session_state:
                            st.session_state[progress_key] = st.empty()
                        
                        st.session_state[progress_key].info(f"📧 메일 정보 로딩 중... ({i+1}/{len(messages)})")
                        
                except Exception as e:
                    logger.warning(f"메일 {message['id']} 정보 가져오기 실패: {str(e)}")
                    st.warning(f"메일 {message['id']} 정보 가져오기 실패: {str(e)}")
                    # 실패한 메일은 기본 정보로 추가
                    message_details.append({
                        'id': message['id'],
                        'subject': '로딩 실패',
                        'sender': '알 수 없음',
                        'snippet': '메일 정보를 가져올 수 없습니다.'
                    })
                    error_count += 1
            
            # 로딩 완료 시 진행률 메시지 제거
            progress_key = "mail_loading_progress"
            if progress_key in st.session_state:
                st.session_state[progress_key].empty()
                del st.session_state[progress_key]
            
            logger.info(f"메일 목록 조회 완료: 성공 {success_count}개, 실패 {error_count}개")
            return message_details
            
        except Exception as e:
            # 에러 발생 시에도 진행률 메시지 제거
            progress_key = "mail_loading_progress"
            if progress_key in st.session_state:
                st.session_state[progress_key].empty()
                del st.session_state[progress_key]
            
            logger.error(f"메일 목록 조회 실패: {str(e)}")
            st.error(f"❌ 메일 목록 조회 실패: {str(e)}")
            return []
    
    @log_api_call("Gmail_MoveToTrash")
    def move_to_trash(self, message_id):
        """메일을 휴지통으로 이동"""
        if not self.service:
            logger.error("Gmail 인증이 필요함")
            st.error("❌ Gmail 인증이 필요합니다.")
            return False
        
        try:
            logger.info(f"메일 휴지통 이동 시작: {message_id}")
            result = self.service.users().messages().trash(userId='me', id=message_id).execute()
            
            if result and 'id' in result:
                logger.info(f"메일 휴지통 이동 성공: {message_id}")
                activity_logger.log_mail_operation("move_to_trash", [message_id], True)
                return True
            else:
                logger.error(f"휴지통 이동 결과 확인 불가: {message_id}")
                st.error("❌ 휴지통 이동 결과를 확인할 수 없습니다.")
                activity_logger.log_mail_operation("move_to_trash", [message_id], False)
                return False
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"메일 휴지통 이동 실패: {message_id}, 오류: {error_msg}")
            activity_logger.log_mail_operation("move_to_trash", [message_id], False)
            
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