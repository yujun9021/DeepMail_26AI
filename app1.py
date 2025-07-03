import streamlit as st
import os
import json
import re
import joblib
import pickle
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from openai import OpenAI
from wordcloud import WordCloud
import matplotlib.pyplot as plt

with st.sidebar:
    st.header("🔧 설정")
    st.success("✅ OpenAI API 키가 설정되었습니다!")

    st.header("📧 Gmail 연결")
    if st.session_state.get("gmail_authenticated"):
        st.success("✅ Gmail 로그인이 완료되었습니다!")
    else:
        st.button("📧 Gmail 로그인")

    st.header("📨 메일 설정")
    st.number_input("페이지당 메일 개수", min_value=1, max_value=50, value=5)
    st.selectbox("모델 선택", ["gpt-3.5-turbo"])
    st.slider("창의성 (Temperature)", 0.0, 1.0, 0.7, step=0.1)


# 환경변수 로드
load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

st.set_page_config(
    page_title="DeepMail - AI 챗봇",
    page_icon="🤖",
    layout="wide"
)

@st.cache_data
def predict_email_df(messages):
    if not messages:
        return pd.DataFrame()

    df = pd.DataFrame(messages)
    
    # === [중요] 모델과 같은 시점에 학습된 벡터라이저, 모델 불러오기 ===
    vectorizer = joblib.load("tfidf_vectorizer.joblib")  # 반드시 모델과 같은 말뭉치에서 학습된 것
    model = joblib.load("phishing_model.pkl")
    
    # === 이메일 텍스트 벡터화 ===
    X = vectorizer.transform(df["snippet"])

    # === 현재 벡터 특성과 모델의 기대 특성 수 맞추기 ===
    current_features = X.shape[1]
    expected_features = model.n_features_in_  # 모델이 학습할 때 사용한 피처 수

    if current_features < expected_features:
        from scipy.sparse import hstack, csr_matrix
        padding = csr_matrix((X.shape[0], expected_features - current_features))
        X = hstack([X, padding])
    elif current_features > expected_features:
        X = X[:, :expected_features]
    # === 끝 ===

    # === 예측 수행 ===
    df["is_phishing"] = model.predict(X)
    df["has_url"] = df["snippet"].apply(lambda text: 1 if re.search(r"http|www", text, re.IGNORECASE) else 0)
    return df




@st.cache_data
def get_gmail_messages(max_results=50):
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
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '날짜 없음')

            message_details.append({
                'id': message['id'],
                'subject': subject,
                'sender': sender,
                'snippet': msg.get('snippet', ''),
                'date': date_str
            })


        return message_details
    except Exception as e:
        st.error(f"❌ 메일 목록 조회 실패: {str(e)}")
        return []

def authenticate_gmail():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if os.path.exists('credentials.json'):
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    return creds

def initialize_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return OpenAI(api_key=api_key)
    return None

def summarize_text(text, client):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"다음 이메일을 세 줄로 요약해줘:\n{text}"}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"요약 실패: {str(e)}"

def predict_uploaded_email(text):
    vectorizer = joblib.load("tfidf_vectorizer.joblib")
    model = joblib.load("phishing_model.pkl")
    vec = vectorizer.transform([text])

    # DataFrame으로 감싸기
    feature_names = vectorizer.get_feature_names_out()
    vec_df = pd.DataFrame(vec.toarray(), columns=feature_names)

    pred = model.predict(vec_df)[0]

    prob = model.predict_proba(vec)[0].max()
    return pred, prob

def plot_wordcloud(text_series, title):
    text = ' '.join(text_series)
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.set_title(title, fontsize=16)
    ax.axis('off')
    st.pyplot(fig)

if "gmail_authenticated" not in st.session_state:
    st.session_state["gmail_authenticated"] = False
if "gmail_credentials" not in st.session_state:
    st.session_state["gmail_credentials"] = None
if "gmail_messages" not in st.session_state:
    st.session_state["gmail_messages"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = []

st.title("DeepMail - AI 챗봇 & Gmail 관리")
st.write("OpenAI Function Calling 기반 AI Agent로 Gmail을 관리하세요!")

if st.button("🔑 Gmail 로그인"):
    creds = authenticate_gmail()
    if creds:
        st.session_state.gmail_credentials = creds
        st.session_state.gmail_authenticated = True
        st.session_state.gmail_messages = get_gmail_messages()
        st.success("✅ Gmail 로그인 성공!")
    else:
        st.error("❌ Gmail 인증 실패")

client = initialize_openai_client()

if st.session_state.gmail_authenticated and st.session_state.gmail_messages:
    email_df = predict_email_df(st.session_state.gmail_messages)


st.markdown("### 📌 피싱 이메일 통계 요약")

import plotly.graph_objects as go
# 이메일 분석 결과 생성
email_df = predict_email_df(st.session_state.get("messages", []))

# 예시: 평균 피싱 비율 계산
if not email_df.empty:
    avg_phishing_ratio = email_df["is_phishing"].mean() * 100
else:
    avg_phishing_ratio = 0



# 게이지 차트 생성
fig_gauge = go.Figure(go.Indicator(
    mode="gauge+number",
    value=avg_phishing_ratio,
    number={'suffix': "%"},
    title={'text': "평균 피싱 비율 (%)"},
    gauge={
        'axis': {'range': [0, 100]},
        'bar': {'color': "darkblue"},
        'steps': [
            {'range': [0, 30], 'color': "lightgreen"},
            {'range': [30, 70], 'color': "yellow"},
            {'range': [70, 100], 'color': "red"}
        ],
    }
))

import plotly.express as px

if not email_df.empty and "from" in email_df.columns:
    email_df["domain"] = email_df["from"].apply(lambda x: x.split("@")[-1] if "@" in x else "알 수 없음")
    domain_counts = email_df["domain"].value_counts().nlargest(5)
    fig_top_domains = px.bar(
        x=domain_counts.index,
        y=domain_counts.values,
        labels={'x': '도메인', 'y': '개수'},
        title='상위 발신 도메인 분포'
    )
else:
    fig_top_domains = px.bar(title='도메인 데이터 없음')


if not email_df.empty and "has_url" in email_df.columns:
    url_counts = email_df["has_url"].value_counts().sort_index()
    fig_url_count = px.bar(
        x=["없음", "있음"],
        y=url_counts.values,
        labels={'x': 'URL 포함 여부', 'y': '이메일 수'},
        title='URL 포함 이메일 분포'
    )
else:
    fig_url_count = px.bar(title='URL 데이터 없음')


cols = st.columns([2, 1, 1])
with cols[0]:
    st.plotly_chart(fig_gauge, use_container_width=True)  # 게이지 차트
with cols[1]:
    st.plotly_chart(fig_top_domains, use_container_width=True)  # 도메인 분포
with cols[2]:
    st.plotly_chart(fig_url_count, use_container_width=True)  # URL 포함 여부


    if not email_df.empty:
        st.markdown("### 📊 피싱 이메일 통계 요약")

        average_risk = round(email_df["is_phishing"].mean() * 100, 1)

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=average_risk,
            title={'text': "평균 피싱 위험도 (%)"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "darkred"},
                'steps': [
                    {'range': [0, 40], 'color': "lightgreen"},
                    {'range': [40, 70], 'color': "yellow"},
                    {'range': [70, 100], 'color': "red"},
                ],
            }
        ))

        phishing_df = email_df[email_df["is_phishing"] == 1]
        domain_counts = phishing_df["sender"].value_counts().nlargest(20).reset_index()
        domain_counts.columns = ["도메인", "피싱 이메일 수"]
        fig_top_domains = px.bar(domain_counts, x="도메인", y="피싱 이메일 수", title="상위 피싱 발신 도메인")

        url_grouped = email_df.groupby(["has_url", "is_phishing"]).size().reset_index(name="count")
        url_grouped["URL 포함 여부"] = url_grouped["has_url"].map({1: "포함", 0: "미포함"})
        url_grouped["이메일 유형"] = url_grouped["is_phishing"].map({1: "피싱", 0: "정상"})

        fig_url_count = px.bar(url_grouped, x="URL 포함 여부", y="count", color="이메일 유형",
                               barmode="stack", title="URL 포함 여부에 따른 이메일 수")

        st.plotly_chart(fig_gauge)
        st.plotly_chart(fig_top_domains)
        st.plotly_chart(fig_url_count)

        st.markdown("### ☁️ 피싱 이메일 WordCloud")
        if not phishing_df.empty:
            plot_wordcloud(phishing_df["snippet"], "피싱 이메일 단어 구름")

        st.markdown("### 📬 메일 목록")
    
        for idx, row in email_df.iterrows():
            with st.expander(f"[{idx+1}] {row['subject']}"):
                st.write(f"📨 보낸 사람: {row['sender']}")
                st.write(f"📅 날짜: {row['date']}")
                st.write(f"📄 내용: {row['snippet'][:300]}...")

                # 👇 여기에 머신러닝 예측 결과 추가cd
                if row['is_phishing'] == 1:
                    st.markdown("🔴 **피싱 의심 메일입니다!**", unsafe_allow_html=True)
                else:
                    st.markdown("🟢 **정상 메일로 판단됩니다.**", unsafe_allow_html=True)

                if st.button(f"❌ 휴지통으로 이동", key=f"trash_{idxs}"):
                    try:
                        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
                        service.users().messages().trash(userId='me', id=row['id']).execute()
                        st.success("✅ 메일이 휴지통으로 이동되었습니다!")
                    except Exception as e:
                        st.error(f"❌ 메일 이동 실패: {str(e)}")

st.markdown("---")


uploaded_file = st.file_uploader("txt 파일 업로드", type="txt")

if uploaded_file:
    text = uploaded_file.read().decode("utf-8")
    st.text_area("본문 미리보기", text, height=200)
    pred, prob = predict_uploaded_email(text)
    label = "🛑 피싱 메일" if pred == 1 else "✅ 정상 메일"
    st.markdown(f"**예측 결과:** {label}")
    st.markdown(f"**신뢰도:** {prob*100:.2f}%")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=prob * 100,
        title={"text": "Phishing 확률"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "red" if pred == 1 else "green"},
            "steps": [
                {"range": [0, 50], "color": "lightgreen"},
                {"range": [50, 80], "color": "yellow"},
                {"range": [80, 100], "color": "red"},
            ],
        }
    ))
    st.plotly_chart(fig)



col1, col2 = st.columns([2, 3])  # 비율 조정 가능

with col1:
    st.subheader("📨 최근 이메일 내용")

    if email_df.empty:
        st.warning("가져온 이메일이 없습니다.")
    else:
        for idx, row in email_df.iterrows():
            st.markdown(
                f"""
                <div style="background-color:#f0f2f6;padding:10px 15px;border-radius:10px;margin-bottom:10px;">
                    <b>🙋‍♀️ {row['sender']} ({row['date']})</b><br>
                    <span style="margin-left:15px;">{row['snippet']}</span>
                </div>
                <div style="background-color:#e8f4ff;padding:10px 15px;border-radius:10px;margin:-5px 0 20px 30px;">
                    <b>🤖 분석 결과:</b> {'🔴 피싱 의심 메일입니다!' if row['is_phishing']==1 else '🟢 정상 메일로 판단됩니다.'}
                </div>
                """,
                unsafe_allow_html=True
            )


with col2:
    st.subheader("🤖 AI 챗봇")
    user_input = st.text_input("메시지를 입력하세요...", key="chatbot_input")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if st.button("보내기"):
        if user_input:
            # 챗봇 응답 생성 (현재는 예시 응답, 나중에 OpenAI 연동 가능)
            ai_response = "여기에 응답이 표시됩니다."

            # 대화 기록 저장
            st.session_state.chat_history.append(("🙋‍♀️", user_input))
            st.session_state.chat_history.append(("🤖", ai_response))

    # 대화 히스토리 출력
    for speaker, message in st.session_state.chat_history:
        st.markdown(f"{speaker} {message}")

