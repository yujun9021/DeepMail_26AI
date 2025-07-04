#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import joblib
import matplotlib.pyplot as plt
import seaborn as sns



# 데이터셋 불러와서 간단한 정보 확인
df = pd.read_csv('CEAS_08.csv')
df.head()
df.info()
df.isnull().sum()


# sender 전처리  @ 뒷부분만(도메인)
df['sender'] = df['sender'].fillna('unknown')
df['sender_domain'] = df['sender'].str.split('@').str[-1]
sender_ohe = pd.get_dummies(
    df['sender_domain'],
    prefix='sender'
)


# 본문 텍스트 전처리
tfidf_vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)

# 본문 텍스트를 TF-IDF 특성으로 변환
X_tfidf = tfidf_vectorizer.fit_transform(df['body'])

# TF-IDF 특성과 기타 특성 결합
features = pd.DataFrame(X_tfidf.toarray(), columns=tfidf_vectorizer.get_feature_names_out())
features['urls'] = df['urls']
features = pd.concat(
    [features, sender_ohe],
    axis=1
)
features['label'] = df['label']

# 결측치 확인 혹시 몰라..
features = features.dropna()

# 데이터셋을 특징(X)과 타깃(y)으로 분리
X = features.drop('label', axis=1)
y = features['label']
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 모델 정의 및 학습
model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train)

# 모델 저장
joblib.dump(model, 'phishing_model.joblib')

# 모델 예측
y_pred = model.predict(X_test)

# 모델 평가
accuracy = accuracy_score(y_test, y_pred)
conf_matrix = confusion_matrix(y_test, y_pred)
class_report = classification_report(y_test, y_pred, zero_division=1)

print(f'Accuracy: {accuracy}')
print('Confusion Matrix:')
print(conf_matrix)
print('Classification Report:')
print(class_report)

sns.heatmap(conf_matrix, annot=True, fmt='d', cmap='Blues')
plt.title('Confusion Matrix')
plt.xlabel('Predicted')
plt.ylabel('Actual')
plt.show()


import streamlit as st
import plotly.graph_objects as go
import numpy as np


# 예측 확률 값
# 여기선 예시 데이터로 대신함
y_proba = model.predict_proba(X_test)[:, 1]

avg_phishing_risk = np.mean(y_proba) * 100

fig = go.Figure(go.Indicator(
    mode="gauge+number",
    value=avg_phishing_risk,
    title={'text': "평균 피싱 위험도 (%)"},
    gauge={
        'axis': {'range': [0, 100]},
        'bar': {'color': "crimson"},
        'steps': [
            {'range': [0, 30], 'color': "lightgreen"},
            {'range': [30, 70], 'color': "yellow"},
            {'range': [70, 100], 'color': "red"}
        ]
    }
))

# 한글 설정
fig.update_layout(font=dict(family="Malgun Gothic", size=16))

# 평균 피싱 위험도 게이지 차트
st.plotly_chart(fig)

# ----------------------------------------

from sklearn.metrics import precision_score, recall_score, f1_score

precision = precision_score(y_test, y_pred, zero_division=1)
recall = recall_score(y_test, y_pred, zero_division=1)
f1 = f1_score(y_test, y_pred, zero_division=1)

st.subheader("모델 성능 요약")
col1, col2, col3, col4 = st.columns(4)
col1.metric("정확도", f"{accuracy*100:.2f}%")
col2.metric("정밀도", f"{precision*100:.2f}%")
col3.metric("재현율", f"{recall*100:.2f}%")
col4.metric("F1 점수", f"{f1*100:.2f}%")

# ----------------------------------------

# 워드클라우드 + 타임라인 분석 시각화 추가
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud


st.subheader("피싱 이메일 단어 워드클라우드")

# 피싱 이메일 본문만 모아서 단어 연결
phishing_bodies = df[df['label'] == 1]['body'].dropna().astype(str)
phishing_text = " ".join(phishing_bodies.tolist())

# 워드클라우드 생성
wordcloud = WordCloud(
    width=800, height=400, background_color='white',
    font_path='malgun.ttf'  # 한글 폰트
).generate(phishing_text)

fig_wc, ax_wc = plt.subplots(figsize=(10, 5))
ax_wc.imshow(wordcloud, interpolation='bilinear')
ax_wc.axis('off')
st.pyplot(fig_wc)

#---------------------------------------------------

# 피싱 이메일만 필터링
phishing_df = df[df['label'] == 1]

# 발신자 도메인별 빈도 계산 (상위 20개)
domain_counts = phishing_df['sender_domain'].value_counts().head(20)

st.subheader("상위 20개 피싱 이메일 발신자 도메인")

fig, ax = plt.subplots(figsize=(12,6))
sns.barplot(x=domain_counts.values, y=domain_counts.index, palette='viridis', ax=ax)
ax.set_xlabel('이메일 수')
ax.set_ylabel('발신자 도메인')
st.pyplot(fig)

#---------------------------------------------------

# URL 포함 여부와 피싱 여부 시각화
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

font_path = "C:/Windows/Fonts/malgun.ttf"
font_name = fm.FontProperties(fname=font_path).get_name()
plt.rc('font', family=font_name)
plt.rcParams['axes.unicode_minus'] = False

url_label_counts = df.groupby(['urls', 'label']).size().unstack(fill_value=0)

st.subheader("URL 포함 여부에 따른 피싱 이메일 수")

fig, ax = plt.subplots(figsize=(8,5))
url_label_counts.plot(kind='bar', stacked=True, ax=ax)
ax.set_xlabel('URL 포함 여부')
ax.set_ylabel('이메일 수')
ax.legend(['정상', '피싱'])
st.pyplot(fig)