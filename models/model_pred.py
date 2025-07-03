import re
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import joblib

def predict_phishing(subject, body, tfidf_path='tfidf_vectorizer.joblib', model_path='phishing_Detecting_model.joblib'):
    """
    제목(subject)과 본문(body) 문자열을 받아 피싱 여부와 확률을 반환합니다.
    반환값 예시: {'label': 1, 'phishing_prob': 0.87}
    """
    # 데이터프레임 생성
    df_new = pd.DataFrame([{'subject': subject, 'body': body}])

    # 텍스트 전처리 함수
    def clean_text(text):
        if pd.isna(text):
            return ''
        text = BeautifulSoup(text, 'html.parser').get_text()
        text = re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip().lower()
        return text

    def extract_urls(text):
        return re.findall(r'http[s]?://\S+', str(text))

    def extract_domains(urls):
        domains = []
        for url in urls:
            try:
                domain = urlparse(url).netloc
                if domain:
                    domains.append(domain.lower())
            except:
                continue
        return domains

    # 피처 생성
    df_new['clean_subject'] = df_new['subject'].apply(clean_text)
    df_new['clean_body'] = df_new['body'].apply(clean_text)
    df_new['subject_len'] = df_new['clean_subject'].apply(len)
    df_new['body_len'] = df_new['clean_body'].apply(len)
    df_new['extracted_urls'] = df_new['body'].apply(extract_urls)
    df_new['num_urls'] = df_new['extracted_urls'].apply(len)
    df_new['url_domains'] = df_new['extracted_urls'].apply(extract_domains)
    df_new['num_unique_domains'] = df_new['url_domains'].apply(lambda x: len(set(x)))

    # TF-IDF
    tfidf_vectorizer = joblib.load(tfidf_path)
    X_tfidf_new = tfidf_vectorizer.transform(df_new['clean_body'])
    tfidf_df_new = pd.DataFrame(
        X_tfidf_new.toarray(),
        columns=tfidf_vectorizer.get_feature_names_out(),
        index=df_new.index
    )
    num_feats_new = df_new[['subject_len', 'body_len', 'num_urls', 'num_unique_domains']].reset_index(drop=True)
    X_final_new = pd.concat([tfidf_df_new, num_feats_new], axis=1)

    # 모델 예측
    model = joblib.load(model_path)
    pred = model.predict(X_final_new)[0]
    prob = model.predict_proba(X_final_new)[:, 1][0]
    return {'label': int(pred), 'phishing_prob': float(prob)}

def get_best_body_text(full_content, snippet=None):
    """
    full_content: get_mail_full_content의 반환값(dict)
    snippet: (선택) Gmail 메시지의 snippet
    """
    body = full_content.get('body_text', '')
    if not body or len(body.strip()) < 10:
        # body_text가 없거나 너무 짧으면 html에서 텍스트 추출
        from deepmail.email_parser import extract_text_from_html  # 필요시 import
        body = extract_text_from_html(full_content.get('body_html', ''))
        if not body or len(body.strip()) < 10:
            body = snippet or ''
    return body

full_content = UIComponents.get_mail_full_content(msg['id'])
body = get_best_body_text(full_content, msg.get('snippet', ''))
result = predict_phishing(full_content['subject'], body) 