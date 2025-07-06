"""
DeepMail - 설정 및 상수
"""

import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Gmail API 설정
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

# 페이지 설정
PAGE_CONFIG = {
    'page_title': "DeepMail - AI 챗봇",
    'page_icon': "🤖",
    'layout': "wide"
}

# 메일 설정
MAIL_CONFIG = {
    'max_results': 50,
    'default_page_size': 10,
    'page_size_options': [10, 15, 20, 25, 30],
    'load_count_options': [10, 30, 50, 100, 200, 500]
}

# OpenAI 설정
OPENAI_CONFIG = {
    'model': "gpt-4o",
    'temperature': 0.7,
    'max_tokens': 500
}

# 세션 상태 키
SESSION_KEYS = {
    'messages': 'messages',
    'gmail_authenticated': 'gmail_authenticated',
    'gmail_credentials': 'gmail_credentials',
    'gmail_messages': 'gmail_messages',
    'gmail_last_fetch': 'gmail_last_fetch',
    'mail_page': 'mail_page',
    'mail_page_size': 'mail_page_size',
    'needs_refresh': 'needs_refresh'
} 