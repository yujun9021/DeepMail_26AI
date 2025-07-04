"""
DeepMail - UI 컴포넌트 모듈
"""

import streamlit as st
import time
import plotly.graph_objects as go
from datetime import datetime
from config import SESSION_KEYS, MAIL_CONFIG, PAGE_CONFIG
from gmail_service import gmail_service, email_parser
from openai_service import openai_service

class UIComponents:
    """UI 컴포넌트 클래스"""
    
    @staticmethod
    def initialize_session_state():
        """세션 상태 초기화"""
        for key, default_value in SESSION_KEYS.items():
            if key not in st.session_state:
                if key == 'messages':
                    st.session_state[key] = []
                elif key in ['gmail_authenticated', 'needs_refresh']:
                    st.session_state[key] = False
                elif key in ['gmail_credentials', 'gmail_messages', 'gmail_last_fetch']:
                    st.session_state[key] = None
                elif key == 'mail_page':
                    st.session_state[key] = 0
                elif key == 'mail_page_size':
                    st.session_state[key] = MAIL_CONFIG['default_page_size']
    
    @staticmethod
    def render_sidebar():
        """사이드바 렌더링"""
        with st.sidebar:
            st.header("⚙️ 설정")
            
            # OpenAI API 상태
            UIComponents.render_openai_status()
            st.markdown("---")
            
            # Gmail 연결
            UIComponents.render_gmail_connection()
            st.markdown("---")
            
            # 메일 페이지 크기 설정
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
                    st.rerun()
                st.markdown("---")
            
            # 챗봇 설정
            model, temperature = UIComponents.render_chatbot_settings()
            st.session_state["sidebar_model"] = model
            st.session_state["sidebar_temperature"] = temperature

            # 채팅 기록 초기화
            st.markdown("---")
            if st.button("💬 채팅 기록 초기화"):
                st.session_state.messages = []
                st.success("✅ 채팅 기록이 초기화되었습니다!")
    
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
            st.success("✅ Gmail에 로그인되어 있습니다!")
            
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
                st.success("✅ Gmail 로그인 성공!")
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
        import os
        if os.path.exists('token.pickle'):
            os.remove('token.pickle')
        st.success("✅ Gmail 로그아웃 완료!")
        st.rerun()
    
    @staticmethod
    def refresh_gmail_messages():
        """Gmail 메시지 새로고침"""
        messages = gmail_service.get_messages()
        st.session_state.gmail_messages = messages
        st.session_state.gmail_last_fetch = datetime.now()
        st.session_state.mail_page = 0
    
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
    def render_chat_interface():
        """채팅 인터페이스 렌더링"""
        st.subheader("🤖 AI 챗봇")
        
        # 기존 메시지 표시
        for msg in st.session_state.messages:
            with st.chat_message(msg['role']):
                st.markdown(msg['content'])
    
    @staticmethod
    def handle_chat_input():
        """채팅 입력 처리"""
        prompt = st.chat_input("메시지를 입력하세요...")
        if prompt:
            if not openai_service.client:
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
                    assistant_response = openai_service.chat_with_function_call(prompt)
                    
                    message_placeholder.markdown(assistant_response)
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                    
                    # 삭제 관련 작업 후에만 UI 새로고침
                    if st.session_state.get("needs_refresh", False):
                        st.session_state.needs_refresh = False
                        # Gmail 인증 상태 확인 후 새로고침
                        if st.session_state.gmail_authenticated:
                            with st.spinner("메일 목록을 새로고침하는 중..."):
                                UIComponents.refresh_gmail_messages()
                                time.sleep(0.5)  # 잠시 대기 후 UI 새로고침
                                st.rerun()
                        else:
                            st.warning("⚠️ Gmail 인증이 필요합니다.")
                            
                except Exception as e:
                    error_msg = f"❌ 응답 생성 중 오류: {str(e)}"
                    message_placeholder.markdown(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    @staticmethod
    def draw_gauge_chart(risk_score):
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
        
        # 차트 크기 조정
        fig.update_layout(
            height=250,  # 높이를 300px로 설정
            margin=dict(l=20, r=20, t=60, b=20)  # 여백 줄이기
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def render_phishing_dashboard():
        """피싱/스팸 메일 대시보드"""
        st.header("🛡️ 피싱/스팸 메일 대시보드")
        
        # 4개 컬럼으로 성능 지표 표시
      
        # 게이지 차트와 추가 통계를 2개 컬럼으로 배치
        col1, col2 = st.columns([1, 1])
        
        with col1:
            UIComponents.draw_gauge_chart(55.5)
        
        with col2:
              col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 메일 수", "1,234", "+12%")
            
        with col2:
            st.metric("피싱 의심", "23", "-5%")
        with col3:
            st.metric("스팸 감지", "156", "+8%")
        with col4:
            st.metric("안전 메일", "1,055", "+15%")
        
    
    @staticmethod
    def get_mail_full_content(message_id):
        """메일의 전체 내용을 가져오는 함수 (Raw 형식 사용)"""
        try:
            # Raw 형식으로 메일 가져오기
            email_message = gmail_service.get_raw_message(message_id)
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
            text_content, html_content = email_parser.extract_text_from_email(email_message)
            
            # 첨부파일 추출
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
    
    @staticmethod
    def render_mail_management():
        """메일 관리 섹션"""
        st.subheader("📧 메일 관리")
        
        if st.session_state.gmail_authenticated:
            # 최초 로그인 시 또는 세션에 메일이 없으면 자동으로 불러오기
            if st.session_state.gmail_messages is None:
                with st.spinner("메일 목록을 불러오는 중..."):
                    UIComponents.refresh_gmail_messages()
            
            # # 마지막 불러온 시간 표시
            # if st.session_state.gmail_last_fetch:
            #     st.caption(f"마지막 업데이트: {st.session_state.gmail_last_fetch.strftime('%Y-%m-%d %H:%M:%S')}")
            
            messages = st.session_state.gmail_messages
            if messages:
                total_messages = len(messages)
                total_pages = (total_messages + st.session_state.mail_page_size - 1) // st.session_state.mail_page_size
                
                # 페이지네이션 버튼
                cols = st.columns([2, 2, 1, 1, 1, 1, 1, 3])

                with cols[0]:
                    if st.button("🔄 새로고침"):
                        with st.spinner("메일 목록을 새로고침하는 중..."):
                            UIComponents.refresh_gmail_messages()
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
                with cols[7]:
                    st.info(f"총 {total_messages}개 메일 (페이지 {st.session_state.mail_page + 1}/{total_pages})")
                
                
                # 현재 페이지의 메일들 표시
                start_idx = st.session_state.mail_page * st.session_state.mail_page_size
                end_idx = min(start_idx + st.session_state.mail_page_size, total_messages)
                current_messages = messages[start_idx:end_idx]
                
                for i, msg in enumerate(current_messages):
                    global_idx = start_idx + i
                    
                    # 메일별로 확장패널만 표시
                    with st.expander(f"📧 [{global_idx + 1}] {msg['subject']}", expanded=False):
                        # 메일 기본 정보 표시
                        st.write(f"**📧 발신자:** {msg['sender']}")
                        st.write(f"**📄 내용:** {msg['snippet']}")
                        
                        # 메일 전체 내용을 지연 로딩
                        with st.spinner("메일 내용을 불러오는 중..."):
                            full_content = UIComponents.get_mail_full_content(msg['id'])
                        
                        if full_content['error']:
                            st.error("메일을 불러올 수 없습니다.")
                            continue
                        
                        # 메일 상세 정보 표시
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.write(f"**📅 날짜:** {full_content['date']}")
                            st.write(f"**📬 수신자:** {full_content['to']}")
                        with col2:
                            if full_content['attachments']:
                                st.write(f"**📎 첨부파일:** {len(full_content['attachments'])}개")
                        
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
                                    cleaned_html = email_parser.clean_html_content(full_content['body_html'])
                                    
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
                                    text_content = email_parser.extract_text_from_html(full_content['body_html'])
                                    st.text_area("정리된 텍스트", text_content, height=300)
                        
                        # 텍스트 탭
                        if full_content['body_html']:
                            with tab2:
                                st.markdown("**텍스트 본문:**")
                                if full_content['body_text']:
                                    st.text_area("텍스트 본문", full_content['body_text'], height=300, key=f"text_{msg['id']}")
                                else:
                                    # HTML에서 텍스트 추출
                                    text_content = email_parser.extract_text_from_html(full_content['body_html'])
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
                        
                        # 메일 번호 표시 (사용자가 챗봇에서 참조할 수 있도록)
                        st.info(f"💡 이 메일을 챗봇에서 참조하려면 '{global_idx + 1}번 메일'이라고 말하세요!")
                    
                    # 구분선 제거 - 메일들이 다닥다닥 붙도록
            else:
                st.info("📭 메일이 없습니다.")
        else:
            st.info(" Gmail에 로그인하면 메일 목록이 표시됩니다.") 