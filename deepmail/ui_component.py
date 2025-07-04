"""
DeepMail - UI 컴포넌트 모듈 (최적화 버전)
"""

import streamlit as st
import time
import random
import plotly.graph_objects as go
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from config import SESSION_KEYS, MAIL_CONFIG, PAGE_CONFIG
from gmail_service import gmail_service, email_parser
from openai_service_clean import openai_service
from googleapiclient.errors import HttpError
import pandas as pd

# 상수 정의
CHAT_STYLES = """
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
.email-scroll-container {
    max-height: 800px;
    overflow-y: auto;
    border: 1px solid #ddd;
    padding: 10px;
    border-radius: 5px;
}
</style>
"""

QUICK_ACTIONS = [
    ("📰", "최근 메일 요약", "최근 5개 메일 요약해줘", "mail_summary"),
    ("🗑️", "피싱 메일 삭제", "피싱 메일을 찾아서 삭제해줘", "phishing_delete"),
    ("📊", "메일 통계", "메일 통계를 알려줘", "mail_stats"),
]

MAIL_KEYWORDS = ["삭제", "휴지통", "메일", "피싱", "새로고침"]

class UIComponents:
    """UI 컴포넌트 클래스 (최적화 버전)"""

    @staticmethod
    def rerun():
        """Streamlit 재실행 트리거 함수"""
        st.session_state["rerun_flag"] = st.session_state.get("rerun_flag", 0) + 1

    @staticmethod
    def initialize_session_state():
        """세션 상태 초기화"""
        # 기본 세션 키 초기화
        session_defaults = {
            'messages': [],
            'gmail_authenticated': False,
            'needs_refresh': False,
            'gmail_credentials': None,
            'gmail_messages': None,
            'gmail_last_fetch': None,
            'mail_page': 0,
            'mail_page_size': MAIL_CONFIG['default_page_size']
        }
        
        for key, default_value in session_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value

        # Gmail 서비스 복구
        if st.session_state.get('gmail_credentials'):
            UIComponents._restore_gmail_service()

    @staticmethod
    def _restore_gmail_service():
        """Gmail 서비스 복구"""
        gmail_service.credentials = st.session_state['gmail_credentials']
        try:
            from googleapiclient.discovery import build
            gmail_service.service = build('gmail', 'v1', credentials=gmail_service.credentials)
        except Exception:
            gmail_service.service = None

    @staticmethod
    def render_sidebar():
        """사이드바 렌더링"""
        with st.sidebar:
            st.header("⚙️ 설정")
            
            # 각 섹션 렌더링
            UIComponents._render_openai_section()
            UIComponents._render_gmail_section()
            UIComponents._render_mail_settings()
            UIComponents._render_chatbot_settings()
            UIComponents._render_chat_reset()

    @staticmethod
    def _render_openai_section():
        """OpenAI API 상태 섹션"""
        UIComponents.render_openai_status()
        st.markdown("---")

    @staticmethod
    def _render_gmail_section():
        """Gmail 연결 섹션"""
        UIComponents.render_gmail_connection()
        st.markdown("---")

    @staticmethod
    def _render_mail_settings():
        """메일 설정 섹션"""
        if st.session_state.gmail_authenticated:
            st.subheader("📧 메일 설정")
            page_size = st.selectbox(
                "페이지당 메일 개수",
                MAIL_CONFIG['page_size_options'],
                index=0,
                help="한 페이지에 표시할 메일 개수를 선택하세요"
            )
            if page_size != st.session_state.mail_page_size:
                st.session_state.mail_page_size = page_size
                st.session_state.mail_page = 0
                UIComponents.rerun()
            st.markdown("---")

    @staticmethod
    def _render_chatbot_settings():
        """챗봇 설정 섹션"""
        model, temperature = UIComponents.render_chatbot_settings()
        st.session_state["sidebar_model"] = model
        st.session_state["sidebar_temperature"] = temperature

    @staticmethod
    def _render_chat_reset():
        """채팅 기록 초기화 섹션"""
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💬 채팅 기록 초기화"):
                st.session_state.messages = []
                st.success("✅ 채팅 기록이 초기화되었습니다!")
        
        with col2:
            if st.button("🗑️ 메일 캐시 초기화"):
                # 메일 캐시 키들 찾아서 삭제
                cache_keys_to_remove = [key for key in st.session_state.keys() if key.startswith('mail_content_')]
                for key in cache_keys_to_remove:
                    del st.session_state[key]
                st.success(f"✅ {len(cache_keys_to_remove)}개 메일 캐시가 초기화되었습니다!")

    @staticmethod
    def render_openai_status():
        """OpenAI API 상태 표시"""
        if openai_service.client:
            st.success("✅ OpenAI API 키가 설정되었습니다!")
        else:
            st.error("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            st.info("💡 .env 파일에 OPENAI_API_KEY=your_api_key_here를 추가하세요.")

    @staticmethod
    def render_gmail_connection():
        """Gmail 연결 섹션"""
        st.subheader("📧 Gmail 연결")

        if not st.session_state.gmail_authenticated:
            if st.button("🔑 Gmail 로그인", type="primary"):
                UIComponents.handle_gmail_login()
        else:
            if st.button("🚪 Gmail 로그아웃"):
                UIComponents.handle_gmail_logout()

    @staticmethod
    def handle_gmail_login():
        """Gmail 로그인 처리"""
        try:
            creds = gmail_service.authenticate()
            if creds:
                st.session_state.gmail_credentials = creds
                st.session_state.gmail_authenticated = True
                UIComponents.refresh_gmail_messages()
                st.rerun()
            else:
                st.error("❌ Gmail 로그인 실패")
        except Exception as e:
            st.error(f"❌ Gmail 로그인 오류: {str(e)}")

    @staticmethod
    def handle_gmail_logout():
        """Gmail 로그아웃 처리"""
        st.session_state.gmail_authenticated = False
        st.session_state.gmail_credentials = None
        st.session_state.gmail_messages = None
        import os
        if os.path.exists('token.pickle'):
            os.remove('token.pickle')
        st.rerun()

    @staticmethod
    def refresh_gmail_messages():
        """Gmail 메시지 새로고침 (캐시 정리 포함)"""
        UIComponents._clear_mail_cache()
        messages = gmail_service.get_messages()
        st.session_state.gmail_messages = messages
        st.session_state.gmail_last_fetch = datetime.now()
        st.session_state.mail_page = 0

    @staticmethod
    def _clear_mail_cache():
        """메일 캐시 정리"""
        cache_keys_to_remove = [key for key in st.session_state.keys() if key.startswith('mail_content_')]
        for key in cache_keys_to_remove:
            del st.session_state[key]

    @staticmethod
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
    
    @staticmethod
    def safe_rerun():
        """안전한 재실행"""
        version = tuple(map(int, st.__version__.split('.')))
        if version >= (1, 25):
            st.rerun()
        elif version >= (1, 10):
            st.experimental_rerun()
        else:
            st.warning("앱을 다시 새로고침 해주세요.")

    @staticmethod
    def render_chat_interface():
        """채팅 인터페이스 렌더링"""
        st.subheader("🤖 AI 챗봇")
        st.markdown(CHAT_STYLES, unsafe_allow_html=True)
        
        UIComponents._render_chat_messages()
        UIComponents._process_chat_response()

    @staticmethod
    def _render_chat_messages():
        """채팅 메시지 렌더링"""
        chat_html = '<div class="chat-box">'
        for msg in st.session_state.messages:
            role = msg['role']
            content = msg['content']
            css_class = "user-msg" if role == "user" else "assistant-msg"
            align = "right" if role == "user" else "left"
            chat_html += f'<div style="text-align:{align};"><div class="{css_class}">{content}</div></div>'
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

    @staticmethod
    def _process_chat_response():
        """채팅 응답 처리"""
        if (st.session_state.messages and 
            st.session_state.messages[-1]["content"] == "🤔 답변 생성 중..." and
            not st.session_state.get("processing_response", False)):
            
            st.session_state["processing_response"] = True
            last_user_msg = UIComponents._get_last_user_message()
            
            if last_user_msg:
                UIComponents._generate_assistant_response(last_user_msg)
            
            st.session_state["processing_response"] = False
            UIComponents.safe_rerun()

    @staticmethod
    def _get_last_user_message() -> Optional[str]:
        """마지막 사용자 메시지 가져오기"""
        return next(
            (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), 
            None
        )

    @staticmethod
    def _generate_assistant_response(user_message: str):
        """어시스턴트 응답 생성"""
        try:
            assistant_response = openai_service.chat_with_function_call(user_message)
            st.session_state.messages[-1]["content"] = assistant_response

            # 자동 새로고침 제거 - 사용자가 직접 새로고침할 수 있도록 함

        except Exception as e:
            st.session_state.messages[-1]["content"] = f"❌ 응답 생성 중 오류: {str(e)}"

    @staticmethod
    def process_user_prompt(prompt: str):
        """사용자 프롬프트 처리"""
        if not openai_service.client:
            st.error("❌ OpenAI API 키가 설정되지 않았습니다!")
            return

        if len(prompt.strip()) < 3:
            st.warning("⚠️ 너무 짧은 입력입니다. 좀 더 구체적으로 입력해 주세요.")
            return

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": "🤔 답변 생성 중..."})
        UIComponents.safe_rerun()

    @staticmethod
    def handle_chat_input():
        """채팅 입력 처리"""
        prompt = st.chat_input("메시지를 입력하세요...")
        UIComponents._render_quick_actions()
        
        if prompt:
            UIComponents.process_user_prompt(prompt)

    @staticmethod
    def _render_quick_actions():
        """빠른 액션 버튼 렌더링"""
        cols = st.columns(len(QUICK_ACTIONS), gap="small")

        for col, (icon, label, cmd, key) in zip(cols, QUICK_ACTIONS):
            with col:
                clicked = st.button(icon, key=key, help=label)
                if clicked:
                    UIComponents.process_user_prompt(cmd)

                st.markdown(
                    f'''
                    <div style="
                        display:inline-block;
                        width:48px;
                        margin:0px auto 0;
                        text-align:center;
                        font-size:12px;
                        color:#333;
                        white-space:nowrap;
                    ">{label}</div>
                    ''',
                    unsafe_allow_html=True
                )

    @staticmethod
    def draw_gauge_chart(risk_score: float):
        """위험도 게이지 차트"""
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

        fig.update_layout(
            height=400
            # margin=dict(l=20, r=20, t=130, b=10)
        )

        st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def render_phishing_dashboard(model_dict=None, messages=None):
        """
        피싱/스팸 메일 대시보드
        - model_dict: {'vectorizer':..., 'classifier':...}
        - messages: [{ 'subject': ..., 'body': ... }] (ex: st.session_state['gmail_messages'])
        """
        import numpy as np
        st.header("🛡️ 피싱/스팸 메일 대시보드")

        col1, col2 = st.columns([1, 1])

        avg_score = None
        total_count = 0

        # 실제 모델과 메일 리스트가 들어왔을 때
        if model_dict and messages and len(messages) > 0:
            texts = []
            for msg in messages:
                subject = msg.get('subject', '') or ''
                # 본문 필드명은 네 데이터 구조에 따라 맞춰줘!
                body = msg.get('body', '') or msg.get('snippet', '') or msg.get('body_text', '') or ''
                texts.append(subject + ' ' + body)

            try:
                X_vec = model_dict['vectorizer'].transform(texts)
                probas = model_dict['classifier'].predict_proba(X_vec)
                phishing_idx = list(model_dict['classifier'].classes_).index(1)
                scores = probas[:, phishing_idx]
                avg_score = float(np.mean(scores)) * 100  # %
                total_count = len(messages)
            except Exception as e:
                with col1:
                    st.error(f"위험도 계산 오류: {str(e)}")
                avg_score = None

        # 게이지 차트
        with col1:
            if avg_score is not None:
                UIComponents.draw_gauge_chart(avg_score)
                st.caption(f"총 {total_count}개 메일 기준")
            else:
                UIComponents.draw_gauge_chart(0.0)
                st.info("메일 데이터가 없거나, 모델 연결이 필요합니다.")

        with col2:
            UIComponents._render_metrics()

    @staticmethod
    def _render_metrics():
        st.markdown("### 🎣 피싱 메일 키워드 유형 TOP3")

        keyword_data = {
            "순위": ["1위", "2위", "3위"],
            "유형": ["결제·구매", "배송·물류", "공지·알림"],
            "비율": ["27.7%", "20.6%", "8.7%"],
            "대표 키워드": [
                "'Payment(결제)', 'Order(주문)', 'Invoice(청구서)'",
                "'Delivery(배송)', 'Shipment(운송)', 'Customs(세관)'",
                "'Urgent(긴급)', 'Notice(안내)'"
            ]
        }
        df_keywords = pd.DataFrame(keyword_data)
        st.table(df_keywords.set_index("순위"))

        st.markdown("### 🧨 악성 첨부파일 확장자 카테고리 TOP3")

        attachment_data = {
            "순위": ["1위", "2위", "3위"],
            "파일 유형": ["스크립트 파일", "압축파일", "문서"],
            "비율": ["50%", "29%", "12%"],
            "대표 확장자": [
                "'.html', '.shtml', '.htm'",
                "'.zip', '.rar', '.7z'",
                "'.doc', '.xls', '.pdf'"
            ]
        }
        df_attachments = pd.DataFrame(attachment_data)
        st.table(df_attachments.set_index("순위"))

    @staticmethod
    def get_mail_full_content(message_id: str) -> Dict[str, Any]:
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
                    return UIComponents._create_error_result(cache_key, "메일을 가져올 수 없습니다.")

                result = UIComponents._parse_email_message(email_message)
                st.session_state[cache_key] = result
                return result

            except HttpError as http_err:
                if "429" in str(http_err) and attempt < max_retries - 1:
                    st.warning(f"⚠️ 요청이 너무 많습니다. 잠시 후 재시도합니다... ({attempt + 1}/{max_retries})")
                    continue
                else:
                    error_msg = UIComponents._handle_http_error(http_err)
                    return UIComponents._create_error_result(cache_key, error_msg)
            except Exception as e:
                if attempt < max_retries - 1:
                    st.warning(f"⚠️ 메일 로딩 중 오류가 발생했습니다. 재시도합니다... ({attempt + 1}/{max_retries})")
                    continue
                else:
                    error_msg = f"❌ 메일 내용을 가져오는 중 오류가 발생했습니다: {str(e)}"
                    return UIComponents._create_error_result(cache_key, error_msg)

        return UIComponents._create_error_result(cache_key, "최대 재시도 횟수를 초과했습니다.")

    @staticmethod
    def _create_error_result(cache_key: str, error_msg: str) -> Dict[str, Any]:
        """오류 결과 생성"""
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

    @staticmethod
    def _parse_email_message(email_message: Dict) -> Dict[str, Any]:
        """이메일 메시지 파싱"""
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

    @staticmethod
    def _handle_http_error(http_err: HttpError) -> str:
        """HTTP 오류 처리"""
        if http_err.resp.status == 429:
            return "⚠️ 너무 많은 요청이 발생했습니다. 잠시 후 다시 시도해 주세요."
        return f"❌ Gmail API 오류: {str(http_err)}"
    
    @staticmethod
    def render_mail_management():
        """메일 관리 섹션"""
        st.subheader("📧 메일 관리")
        
        if not st.session_state.gmail_authenticated:
            st.info("Gmail에 로그인하면 메일 목록이 표시됩니다.")
            return

        # 메일 목록 로드
        if st.session_state.gmail_messages is None:
            with st.spinner("메일 목록을 불러오는 중..."):
                UIComponents.refresh_gmail_messages()
        
        messages = st.session_state.gmail_messages
        if not messages:
            st.info("📭 메일이 없습니다.")
            return

        # 페이지네이션 및 메일 목록 렌더링
        UIComponents._render_pagination(messages)
        UIComponents._render_mail_list(messages)

    @staticmethod
    def _render_pagination(messages: List[Dict]):
        """페이지네이션 렌더링"""
        total_messages = len(messages)
        total_pages = (total_messages + st.session_state.mail_page_size - 1) // st.session_state.mail_page_size
        
        cols = st.columns([2, 2, 1, 1, 1, 1, 1, 3])

        with cols[0]:
            if st.button("🔄 새로고침"):
                with st.spinner("메일 목록을 새로고침하는 중..."):
                    UIComponents.refresh_gmail_messages()
                    st.rerun()

        # 페이지네이션 버튼들
        pagination_buttons = [
            ("⏮️", "first", 0, st.session_state.mail_page == 0),
            ("◀️", "prev", max(0, st.session_state.mail_page - 1), st.session_state.mail_page == 0),
            ("▶️", "next", min(total_pages - 1, st.session_state.mail_page + 1), st.session_state.mail_page >= total_pages - 1),
            ("⏭️", "last", total_pages - 1, st.session_state.mail_page >= total_pages - 1)
        ]

        for i, (icon, key, target_page, disabled) in enumerate(pagination_buttons):
            with cols[i + 2]:
                if st.button(icon, key=key, disabled=disabled):
                    st.session_state.mail_page = target_page
                    st.rerun()

        with cols[7]:
            st.info(f"총 {total_messages}개 메일 (페이지 {st.session_state.mail_page + 1}/{total_pages})")

    @staticmethod
    def _render_mail_list(messages: List[Dict]):
        """메일 목록 렌더링"""
        start_idx = st.session_state.mail_page * st.session_state.mail_page_size
        end_idx = min(start_idx + st.session_state.mail_page_size, len(messages))
        current_messages = messages[start_idx:end_idx]
        
        for i, msg in enumerate(current_messages):
            global_idx = start_idx + i
            UIComponents._render_mail_item(msg, global_idx)

    @staticmethod
    def _render_mail_item(msg: Dict, global_idx: int):
        """개별 메일 아이템 렌더링"""
        cache_key = f"mail_content_{msg['id']}"
        is_cached = cache_key in st.session_state
        
        with st.expander(f"📧 [{global_idx + 1}] {msg['subject']}", expanded=False):
            # 기본 정보 표시
            st.write(f"**📧 발신자:** {msg['sender']}")
            st.write(f"**📄 내용:** {msg['snippet']}")
            
            # 캐시 상태 표시
            if is_cached:
                st.success("✅ 캐시된 메일 (빠른 로딩)")
            
            # 메일 전체 내용 로드
            if not is_cached:
                with st.spinner("메일 내용을 불러오는 중..."):
                    full_content = UIComponents.get_mail_full_content(msg['id'])
            else:
                full_content = st.session_state[cache_key]
            
            if full_content['error']:
                st.error("메일을 불러올 수 없습니다.")
                return
            
            # 상세 정보 및 탭 렌더링
            UIComponents._render_mail_details(full_content)
            UIComponents._render_mail_tabs(full_content, msg['id'])
            
            # 챗봇 참조 안내
            st.info(f"💡 이 메일을 챗봇에서 참조하려면 '{global_idx + 1}번 메일'이라고 말하세요!")

    @staticmethod
    def _render_mail_details(full_content: Dict):
        """메일 상세 정보 렌더링"""
        col1, col2 = st.columns([1, 1])
        with col1:
            st.write(f"**📅 날짜:** {full_content['date']}")
            st.write(f"**📬 수신자:** {full_content['to']}")
        with col2:
            if full_content['attachments']:
                st.write(f"**📎 첨부파일:** {len(full_content['attachments'])}개")

    @staticmethod
    def _render_mail_tabs(full_content: Dict, msg_id: str):
        """메일 탭 렌더링"""
        has_html = bool(full_content['body_html'])
        
        if has_html:
            tab1, tab2, tab3 = st.tabs(["🌐 HTML 보기", "📄 텍스트 보기", "📎 첨부파일"])
            UIComponents._render_html_tab(tab1, full_content)
            UIComponents._render_text_tab(tab2, full_content, msg_id, has_html)
            UIComponents._render_attachments_tab(tab3, full_content)
        else:
            tab1, tab2 = st.tabs(["📄 텍스트 보기", "📎 첨부파일"])
            UIComponents._render_text_tab(tab1, full_content, msg_id, has_html)
            UIComponents._render_attachments_tab(tab2, full_content)

    @staticmethod
    def _render_html_tab(tab, full_content: Dict):
        """HTML 탭 렌더링"""
        with tab:
            st.markdown("**HTML 렌더링:**")
            try:
                cleaned_html = email_parser.clean_html_content(full_content['body_html'])
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
                text_content = email_parser.extract_text_from_html(full_content['body_html'])
                st.text_area("정리된 텍스트", text_content, height=300)

    @staticmethod
    def _render_text_tab(tab, full_content: Dict, msg_id: str, has_html: bool):
        """텍스트 탭 렌더링"""
        with tab:
            st.markdown("**텍스트 본문:**")
            if full_content['body_text']:
                st.text_area("텍스트 본문", full_content['body_text'], height=300, key=f"text_{msg_id}")
            elif has_html:
                text_content = email_parser.extract_text_from_html(full_content['body_html'])
                st.text_area("HTML에서 추출한 텍스트", text_content, height=300, key=f"extracted_{msg_id}")
            else:
                st.info("텍스트 본문이 없습니다.")

    @staticmethod
    def _render_attachments_tab(tab, full_content: Dict):
        """첨부파일 탭 렌더링"""
        with tab:
            if full_content['attachments']:
                st.markdown("**첨부파일 목록:**")
                for attachment in full_content['attachments']:
                    UIComponents._render_attachment_item(attachment)
            else:
                st.info("첨부파일이 없습니다.")

    @staticmethod
    def _render_attachment_item(attachment: Dict):
        """개별 첨부파일 렌더링"""
        with st.expander(f"📎 {attachment['filename']} ({attachment['size']} bytes)"):
            st.write(f"**파일명:** {attachment['filename']}")
            st.write(f"**크기:** {attachment['size']} bytes")
            st.write(f"**타입:** {attachment['content_type']}")
            
            if attachment['content_type'].startswith('image/'):
                st.image(attachment['data'], caption=attachment['filename'])
            else:
                st.download_button(
                    label=f"📥 {attachment['filename']} 다운로드",
                    data=attachment['data'],
                    file_name=attachment['filename'],
                    mime=attachment['content_type']
                )
