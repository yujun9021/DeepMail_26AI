import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# OpenAI 클라이언트 초기화
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    client = OpenAI(api_key=api_key)
else:
    client = None

# 페이지 설정
st.set_page_config(
    page_title="OpenAI 챗봇",
    page_icon="🤖",
    layout="wide"
)

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 채팅 기록 저장 함수
def save_chat_history(messages, filename=None):
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_history_{timestamp}.json"
    
    chat_data = {
        "timestamp": datetime.now().isoformat(),
        "total_messages": len(messages),
        "messages": messages
    }
    
    # chats 폴더가 없으면 생성
    os.makedirs("chats", exist_ok=True)
    filepath = os.path.join("chats", filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=2)
    
    return filepath

# 채팅 기록 로드 함수
def load_chat_history(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        return chat_data["messages"]
    except Exception as e:
        st.error(f"채팅 기록 로드 중 오류 발생: {str(e)}")
        return []

# 저장된 채팅 목록 가져오기
def get_saved_chats():
    if not os.path.exists("chats"):
        return []
    
    chat_files = []
    for filename in os.listdir("chats"):
        if filename.endswith(".json"):
            filepath = os.path.join("chats", filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                chat_files.append({
                    "filename": filename,
                    "filepath": filepath,
                    "timestamp": chat_data.get("timestamp", ""),
                    "total_messages": chat_data.get("total_messages", 0)
                })
            except:
                continue
    
    return sorted(chat_files, key=lambda x: x["timestamp"], reverse=True)

# 사이드바 - 설정
with st.sidebar:
    st.header("⚙️ 챗봇 설정")
    
    # API 키 상태 표시
    if api_key:
        st.success("✅ API 키가 설정되었습니다!")
    else:
        st.error("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        st.info("💡 .env 파일에 OPENAI_API_KEY=your_api_key_here를 추가하세요.")
    
    st.markdown("---")
    
    # 모델 선택
    model = st.selectbox(
        "모델 선택",
        ["gpt-3.5-turbo", "gpt-4"],
        help="사용할 OpenAI 모델을 선택하세요"
    )
    
    # 온도 설정
    temperature = st.slider(
        "창의성 (Temperature)",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1,
        help="높을수록 더 창의적인 응답을 생성합니다"
    )
    
    st.markdown("---")
    
    # 채팅 기록 관리
    st.subheader("💾 채팅 기록")
    
    # 현재 대화 저장
    if st.session_state.messages:
        custom_filename = st.text_input(
            "저장할 파일명 (선택사항)",
            placeholder="my_chat.json"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 저장"):
                if custom_filename and not custom_filename.endswith('.json'):
                    custom_filename += '.json'
                
                filepath = save_chat_history(st.session_state.messages, custom_filename)
                st.success(f"✅ 저장 완료: {os.path.basename(filepath)}")
                st.rerun()
        
        with col2:
            if st.button("🗑️ 초기화"):
                st.session_state.messages = []
                st.rerun()
    
    # 저장된 채팅 목록
    saved_chats = get_saved_chats()
    if saved_chats:
        st.markdown("**저장된 대화:**")
        for chat in saved_chats:
            timestamp = datetime.fromisoformat(chat["timestamp"]).strftime("%Y-%m-%d %H:%M")
            with st.expander(f"📄 {chat['filename']} ({timestamp})"):
                st.write(f"메시지 수: {chat['total_messages']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"📂 로드", key=f"load_{chat['filename']}"):
                        st.session_state.messages = load_chat_history(chat["filepath"])
                        st.success("✅ 채팅 기록을 로드했습니다!")
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ 삭제", key=f"delete_{chat['filename']}"):
                        try:
                            os.remove(chat["filepath"])
                            st.success("✅ 파일이 삭제되었습니다!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 실패: {str(e)}")
    else:
        st.info("저장된 채팅 기록이 없습니다.")

# 메인 영역
st.title("🤖 OpenAI 챗봇")
st.markdown("환경변수에서 API 키를 자동으로 로드합니다!")

# 채팅 컨테이너
chat_container = st.container()

with chat_container:
    # 이전 메시지들 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # 사용자 입력
    if prompt := st.chat_input("메시지를 입력하세요..."):
        if not api_key or not client:
            st.error("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다!")
            st.info("💡 .env 파일을 생성하고 OPENAI_API_KEY=your_api_key_here를 추가하세요.")
        else:
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
                    # OpenAI API 호출
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.messages
                        ],
                        temperature=temperature,
                        max_tokens=1000
                    )
                    
                    # 응답 추출
                    assistant_response = response.choices[0].message.content
                    
                    # 응답 표시
                    message_placeholder.markdown(assistant_response)
                    
                    # 챗봇 응답을 세션에 추가
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                    
                except Exception as e:
                    error_message = str(e)
                    if "authentication" in error_message.lower() or "invalid" in error_message.lower():
                        message_placeholder.error("❌ API 키가 유효하지 않습니다. .env 파일의 OPENAI_API_KEY를 확인해주세요.")
                    elif "rate limit" in error_message.lower():
                        message_placeholder.error("❌ API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.")
                    elif "quota" in error_message.lower():
                        message_placeholder.error("❌ API 할당량이 소진되었습니다. OpenAI 계정을 확인해주세요.")
                    else:
                        message_placeholder.error(f"❌ 오류가 발생했습니다: {error_message}")

# 하단 정보
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**모델:** " + model)
with col2:
    st.markdown("**온도:** " + str(temperature))
with col3:
    st.markdown("**메시지 수:** " + str(len(st.session_state.messages)))

st.markdown("**OpenAI 챗봇** - Streamlit + OpenAI API로 제작") 