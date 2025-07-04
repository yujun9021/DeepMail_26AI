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
/* 사용자 말풍선 (오른쪽) */
.user-msg {
    background: linear-gradient(135deg, #a0c4ff, #3b82f6);
    color: white;
    padding: 12px 20px;
    border-radius: 24px 24px 0 24px;
    margin-bottom: 12px;
    max-width: 75%;
    float: right;
    clear: both;
    box-shadow: 0 2px 6px rgba(59, 130, 246, 0.4);
    transition: background-color 0.3s ease;
    word-break: break-word;
}

/* 마우스 오버시 약간 밝아짐 */
.user-msg:hover {
    background: linear-gradient(135deg, #83b2ff, #2563eb);
}

/* 어시스턴트 말풍선 (왼쪽) */
.assistant-msg {
    background-color: #f3f4f6;
    color: #1f2937;
    padding: 12px 20px;
    border-radius: 24px 24px 24px 0;
    margin-bottom: 12px;
    max-width: 75%;
    float: left;
    clear: both;
    box-shadow: 0 2px 6px rgba(156, 163, 175, 0.3);
    word-break: break-word;
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
        """Gmail 메시지 스마트 새로고침 (캐시 유지 + 새 메일만 추가)"""
        # 현재 캐시된 메일 ID들 확인
        cached_mail_ids = set()
        for key in st.session_state.keys():
            if key.startswith('mail_content_'):
                mail_id = key.replace('mail_content_', '')
                cached_mail_ids.add(mail_id)
        
        # Gmail에서 최신 메일 목록 가져오기
        new_messages = gmail_service.get_messages()
        
        if new_messages:
            # 새로 추가된 메일 ID들 찾기
            new_mail_ids = {msg['id'] for msg in new_messages}
            newly_added_ids = new_mail_ids - cached_mail_ids
            
            # 삭제된 메일 ID들 찾기 (캐시에는 있지만 Gmail에는 없는 경우)
            deleted_mail_ids = cached_mail_ids - new_mail_ids
            
            # 삭제된 메일의 캐시 정리
            for mail_id in deleted_mail_ids:
                cache_key = f"mail_content_{mail_id}"
                if cache_key in st.session_state:
                    del st.session_state[cache_key]
            
            # 새로 추가된 메일이 있으면 알림
            if newly_added_ids:
                st.success(f"✅ {len(newly_added_ids)}개의 새 메일이 추가되었습니다!")
            
            # 삭제된 메일이 있으면 알림
            if deleted_mail_ids:
                st.info(f"📭 {len(deleted_mail_ids)}개의 메일이 삭제되었습니다.")
        
        # 메일 목록 업데이트
        st.session_state.gmail_messages = new_messages
        st.session_state.gmail_last_fetch = datetime.now()
        
        # 삭제 추적 초기화 (실제 Gmail 상태와 동기화)
        st.session_state.deleted_mail_ids = set()

    @staticmethod
    def _clear_mail_cache():
        """메일 캐시 정리 (전체 캐시 삭제)"""
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

        # 삭제된 메일 추적 (세션에 저장)
        if 'deleted_mail_ids' not in st.session_state:
            st.session_state.deleted_mail_ids = set()
        
        # 삭제된 메일 필터링
        filtered_messages = [msg for msg in messages if msg['id'] not in st.session_state.deleted_mail_ids]
        
        # 페이지네이션 및 메일 목록 렌더링
        UIComponents._render_pagination(filtered_messages)
        UIComponents._render_mail_list(filtered_messages)

    # AI 분석 블록 추가
        st.markdown("---")
        st.subheader("원하는 메일을 AI로 분석할 수 있습니다.")

        mail_options = [
            f"{i+1}번 메일: {msg['subject'][:40]}"
            for i, msg in enumerate(messages)
        ]
        selected_idx = st.selectbox(
            "분석할 메일을 선택하세요",
            options=range(len(messages)),
            format_func=lambda i: mail_options[i]
        )
        selected_msg = messages[selected_idx]

        st.markdown("**분석 종류를 선택하세요**")
        analysis_type = st.radio(
            "분석 타입 선택",
            ("피싱 위험 분석", "요약", "링크 위험도 웹서치 분석"),
            horizontal=True,
            index=0
        )

        if st.button("🔍 선택한 메일 AI 분석하기"):
            with st.spinner("메일 전체 내용을 가져오는 중..."):
                from mail_utils import get_mail_full_content
                mail_content = get_mail_full_content(selected_msg['id'])
            if mail_content['error']:
                st.error("메일 본문이 없습니다.")
            else:
                if analysis_type == "피싱 위험 분석":
                    prompt = "이 메일의 피싱 위험도를 평가하고. 그 이유도 설명해줘."
                elif analysis_type == "요약":
                    prompt = "이 메일의 주요 내용을 짧게 요약해줘."
                elif analysis_type == "링크 위험도 웹서치 분석":
                    prompt = "이 메일 본문에 포함된 링크나 도메인을 웹서치를 통해 위험도를 평가하고 설명해줘."
                else:
                    prompt = "이 메일을 분석해줘."

                input_text = f"{prompt}\n\n[메일 제목]\n{mail_content['subject']}\n[본문]\n{mail_content['body_text'][:3000]}"
                with st.spinner("메일을 분석 중..."):
                    if analysis_type == "피싱 위험 분석":
                        # 우리 프로젝트의 피싱 검사 함수 사용
                        try:
                            # 현재 메일의 인덱스 찾기
                            messages = st.session_state.get('gmail_messages', [])
                            mail_index = None
                            for i, msg in enumerate(messages):
                                if msg['id'] == selected_msg['id']:
                                    mail_index = i
                                    break
                            
                            if mail_index is not None:
                                # check_email_phishing 함수 호출
                                phishing_result = openai_service.check_email_phishing(mail_index)
                                
                                if 'error' in phishing_result:
                                    result = f"❌ 피싱 검사 오류: {phishing_result['error']}"
                                else:
                                    # 결과를 친화적으로 포맷팅
                                    risk_level = "🔴 높음" if phishing_result['result'] == 'phishing' else "🟢 낮음"
                                    probability = phishing_result.get('probability', 0)
                                    if probability:
                                        probability_percent = f"{probability * 100:.1f}%"
                                    else:
                                        probability_percent = "확률 계산 불가"
                                    
                                    result = f"""
**📊 피싱 위험도 분석 결과**

**제목:** {phishing_result['subject']}
**발신자:** {phishing_result['sender']}
**위험도:** {risk_level}
**피싱 확률:** {probability_percent}

**분석 결과:** {phishing_result['result'] == 'phishing' and '이 메일은 피싱 메일로 판별되었습니다.' or '이 메일은 정상 메일로 판별되었습니다.'}

**권장 조치:** {phishing_result['result'] == 'phishing' and '⚠️ 이 메일을 삭제하고 링크를 클릭하지 마세요.' or '✅ 안전한 메일입니다.'}
"""
                            else:
                                result = "❌ 메일을 찾을 수 없습니다."
                        except Exception as e:
                            result = f"❌ 피싱 검사 중 오류가 발생했습니다: {str(e)}"
                    elif analysis_type == "링크 위험도 웹서치 분석":
                        # 웹서치를 통한 분석
                        try:
                            # 메일에서 링크나 도메인 추출
                            import re
                            links = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', mail_content['body_text'] or '')
                            domains = re.findall(r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', mail_content['body_text'] or '')
                            
                            if links or domains:
                                # 웹서치 분석 수행
                                web_search_prompt = f"""
다음 이메일의 링크와 도메인을 웹 검색을 통해 위험도를 평가해주세요:

제목: {mail_content['subject']}
발견된 링크: {links[:5]}  # 최대 5개
발견된 도메인: {list(set(domains))[:5]}  # 중복 제거 후 최대 5개

각 링크/도메인의 위험도, 악성 여부, 그리고 근거를 웹 검색을 통해 분석해주세요.
"""
                                result = openai_service.web_search_analysis_with_prompt(web_search_prompt)
                            else:
                                result = "이 메일에서 링크나 도메인을 찾을 수 없습니다."
                        except Exception as e:
                            result = f"웹서치 분석 중 오류가 발생했습니다: {str(e)}"
                    else:
                        # 일반 챗봇 분석 (요약 등)
                        result = openai_service.chat_with_function_call(input_text)
                st.success(f"**분석 결과:**\n\n{result}")
                
                # 대화창 연동
                st.session_state.messages.append({
                    "role":"user",
                    "content": f"[{mail_content['subject']}] {analysis_type}"    
                })
                st.session_state.messages.append({
                    "role":"assistant",
                    "content": result
                })



    

    @staticmethod
    def _render_pagination(messages: List[Dict]):
        """페이지네이션 렌더링"""
        total_messages = len(messages)
        total_pages = (total_messages + st.session_state.mail_page_size - 1) // st.session_state.mail_page_size
        
        # 페이지 번호 자동 조정 (현재 페이지가 총 페이지 수를 초과하는 경우)
        if total_pages > 0 and st.session_state.mail_page >= total_pages:
            st.session_state.mail_page = total_pages - 1
        
        cols = st.columns([2, 2, 1, 1, 1, 1, 1, 3])

        with cols[0]:
            if st.button("🔄 스마트 새로고침"):
                with st.spinner("메일 목록을 새로고침하는 중..."):
                    UIComponents.refresh_gmail_messages()
                    # 삭제된 메일 추적 초기화
                    st.session_state.deleted_mail_ids = set()
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
        
        # 삭제된 메일인지 확인
        if msg['id'] in st.session_state.get('deleted_mail_ids', set()):
            return  # 삭제된 메일은 렌더링하지 않음
        
        with st.expander(f"📧 [{global_idx + 1}] {msg['subject']}", expanded=False):
            # 기본 정보 표시
            st.write(f"**📧 발신자:** {msg['sender']}")
            st.write(f"**📄 내용:** {msg['snippet']}")
            
            # 삭제 버튼 추가
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🗑️ 삭제", key=f"delete_{msg['id']}"):
                    # 메일 삭제 처리
                    success = gmail_service.move_to_trash(msg['id'])
                    if success:
                        # 삭제된 메일 ID를 세션에 추가
                        if 'deleted_mail_ids' not in st.session_state:
                            st.session_state.deleted_mail_ids = set()
                        st.session_state.deleted_mail_ids.add(msg['id'])
                        # 해당 메일의 캐시도 제거
                        if cache_key in st.session_state:
                            del st.session_state[cache_key]
                        st.success("✅ 메일이 삭제되었습니다!")
                        # 즉시 페이지 다시 렌더링
                        st.rerun()
                    else:
                        st.error("❌ 메일 삭제에 실패했습니다.")
            
            # 캐시 상태 표시
            if is_cached:
                st.success("✅ 캐시된 메일 (빠른 로딩)")
            
            # 메일 전체 내용 로드
            if not is_cached:
                with st.spinner("메일 내용을 불러오는 중..."):
                    from mail_utils import get_mail_full_content
                    full_content = get_mail_full_content(msg['id'])
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
