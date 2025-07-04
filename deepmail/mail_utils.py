import streamlit as st
import random
import time
from gmail_service import gmail_service, email_parser
from googleapiclient.errors import HttpError

def get_mail_full_content(message_id: str) -> dict:
    """메일의 전체 내용을 가져오는 함수 (재시도 로직 포함)"""
    cache_key = f"mail_content_{message_id}"

    if cache_key in st.session_state:
        return st.session_state[cache_key]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 재시도 시 더 긴 딜레이 (0.5~1.5초)
            if attempt > 0:
                delay = random.uniform(0.5, 1.5) * (2 ** attempt)  # 지수 백오프
                time.sleep(delay)
            else:
                time.sleep(random.uniform(0.2, 0.6))  # 첫 시도는 짧은 딜레이
            
            email_message = gmail_service.get_raw_message(message_id)
            
            if not email_message:
                return _create_error_result(cache_key, "메일을 가져올 수 없습니다.")

            result = _parse_email_message(email_message)
            st.session_state[cache_key] = result
            return result

        except HttpError as http_err:
            if "429" in str(http_err) and attempt < max_retries - 1:
                st.warning(f"⚠️ 요청이 너무 많습니다. 잠시 후 재시도합니다... ({attempt + 1}/{max_retries})")
                continue
            else:
                error_msg = str(http_err)
                return _create_error_result(cache_key, error_msg)
        except Exception as e:
            if attempt < max_retries - 1:
                st.warning(f"⚠️ 메일 로딩 중 오류가 발생했습니다. 재시도합니다... ({attempt + 1}/{max_retries})")
                continue
            else:
                error_msg = f"❌ 메일 내용을 가져오는 중 오류가 발생했습니다: {str(e)}"
                return _create_error_result(cache_key, error_msg)

    return _create_error_result(cache_key, "최대 재시도 횟수를 초과했습니다.")

def _create_error_result(cache_key: str, error_msg: str) -> dict:
    result = {
        'subject': '오류',
        'from': '오류',
        'to': '오류',
        'date': '오류',
        'body_text': error_msg,
        'body_html': '',
        'attachments': [],
        'error': True
    }
    st.session_state[cache_key] = result
    return result

def _parse_email_message(email_message: dict) -> dict:
    subject = email_message.get('Subject', '제목 없음')
    from_addr = email_message.get('From', '발신자 없음')
    to_addr = email_message.get('To', '수신자 없음')
    date = email_message.get('Date', '날짜 없음')

    text_content, html_content = email_parser.extract_text_from_email(email_message)
    attachments = email_parser.extract_attachments(email_message)

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