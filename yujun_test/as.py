import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

client = OpenAI(api_key=OPENAI_API_KEY)

# 사이드바
with st.sidebar:
    st.title("메뉴")
    
    # 모델 선택
    model_options = {
        "GPT-4": "gpt-4.1",
        "GPT-3.5 Turbo": "gpt-3.5-turbo",
        "GPT-4 Turbo": "gpt-4-turbo-preview"
    }
    
    selected_model = st.selectbox(
        "모델 선택",
        options=list(model_options.keys()),
        index=0
    )
    
    # 말투 선택
    tone_options = {
        "약간모자란GPT": "바보같고 뚱딴지같은 대답을해주세요",
        "해적 말투": "거친 바다 사나이와 같은 호탕한 해적의 말투로 대화해주세요. 'Arr!', '~라고!!' 같은 추임새와 문장 끝을 힘차게 내지르며 마무리해주세요.",
        "외계인 말투": "(치치지직...), (전송 오류...)등 멀리서 통신하는 느낌을 주세요.""우주에서 온 외계인의 말투로 대화해주세요. '~이다', '~하라', '지구인' 같은 표현을 사용하고, 신비롭고 이상한 말투 그리고 특수문자를 사용하여 외계기호처럼 답변해주세요.",
        "노인 말투": "경험과 지혜가 담긴 노인 말투로 대화해주세요. '~다', '~거든', '~지' 같은 표현을 사용하고, 인생 경험을 바탕으로 답변해주세요.",
        "로봇 말투": "기계적인 로봇 말투로 대화해주세요. '~입니다', '~합니다', '분석 결과' 같은 표현을 사용하고, 정확하고 논리적으로 답변해주세요.",
        "시인 말투": "시적이고 감성적인 시인 말투로 대화해주세요. '~이네', '~구나', '~아' 같은 표현을 사용하고, 아름답고 은유적인 언어로 답변해주세요.",
        "귀찮은 말투": "매우 부정적이고 귀찮아하는 말투로 대화해주세요. '하...', '뭐야', '별로', '귀찮다', '~인데 뭐' 같은 표현을 사용하고, 짧고 무관심하게 답변해주세요.",
        "츤데레 말투": "츤데레 캐릭터의 말투로 대화해주세요. '~인데 뭐', '~같은 건 아니고', '별로 신경 쓰지 않지만', '~라고 생각하는 건 아니야' 같은 표현을 사용하고, 겉으로는 차갑지만 속으로는 따뜻한 마음을 보여주세요.",
        "겁쟁이 말투": "겁이 많고 소심한 겁쟁이 말투로 대화해주세요. '어...', '음...', '그게...', '아마도...', '혹시...', '~일 수도 있고...' 같은 표현을 사용하고, 불확실하고 조심스럽게 답변해주세요."
    }
    
    selected_tone = st.selectbox(
        "말투 선택",
        options=list(tone_options.keys()),
        index=0
    )
    
    # 선택된 모델과 말투를 세션에 저장
    st.session_state.openai_model = model_options[selected_model]
    st.session_state.selected_tone = tone_options[selected_tone]
    
    st.divider()
    
    # 대화내용 초기화 버튼
    if st.button("대화 초기화", type="primary"):
        st.session_state.messages = []
        st.rerun()

st.title('나만의 GPT')
st.write('# 사이드바를 열고 옵션을 골라주세요!')

# st.session_state : 세션에 키-값 형식으로 데이터를 저장하는 변수
# openai_model=>str, messages=>[]
if 'openai_model' not in st.session_state:
    st.session_state.openai_model = 'gpt-4.1' # 'gpt-3.5-turbo'

if 'messages' not in st.session_state:
    st.session_state.messages=[]

# 기존의 메시지가 있다면 출력
for msg in st.session_state.messages:
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])

# prompt => 사용자 입력창
if prompt := st.chat_input('메시지를 입력하세요!') :
    # messages => [] , 대화 내용 추가
    st.session_state.messages.append({
        "role" : "user",
        "content": prompt
    })

    with st.chat_message('user'):
        st.markdown(prompt)

    with st.chat_message('assistant'):
        # 시스템 메시지와 대화 내용을 포함한 메시지 리스트 생성
        messages = [{"role": "system", "content": st.session_state.selected_tone}]
        messages.extend([
            {"role": m['role'], "content": m['content']}
            for m in st.session_state.messages
        ])
        
        stream = client.chat.completions.create(
            model=st.session_state.openai_model,
            messages=messages,
            stream=True
        )
        response = st.write_stream(stream)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response
        }
    )
