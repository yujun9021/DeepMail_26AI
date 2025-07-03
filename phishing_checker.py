import os
import joblib
from gmail_service import gmail_service, email_parser

MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/rf_phishing_model.pkl')

def check_email_phishing(email_index: int):
    """
    n번째(0-indexed) 이메일의 피싱 여부를 반환합니다.
    :param email_index: 확인할 이메일의 인덱스(0이 최신)
    :return: {'subject': ..., 'sender': ..., 'result': 'phishing' or 'not phishing', 'probability': float}
    """
    try:
        print(f"[DEBUG] Step 1: 인증 및 메일 목록 가져오기")
        gmail_service.authenticate()
        messages = gmail_service.get_messages()
        print(f"[DEBUG] messages count: {len(messages) if messages else 0}, email_index: {email_index}")
        if not messages or email_index >= len(messages):
            return {'error': f'[1] 해당 번호의 메일이 없습니다. (messages={messages}, email_index={email_index})'}

        msg_info = messages[email_index]
        message_id = msg_info['id']
        subject = msg_info['subject']
        sender = msg_info['sender']
        try:
            # Try printing with repr to avoid UnicodeEncodeError
            print("[DEBUG] Step 2: Raw 메일 가져오기, message_id=" + repr(message_id) + ", subject=" + repr(subject))
        except Exception as e:
            print("[DEBUG] Step 2: Raw 메일 가져오기 (repr 출력도 실패):", repr(e))

        email_message = gmail_service.get_raw_message(message_id)
        print(f"[DEBUG] email_message is None? {email_message is None}")
        if email_message is None:
            return {'error': f'[2] 메일 본문을 불러올 수 없습니다. (message_id={message_id})'}

        print(f"[DEBUG] Step 3: 본문 추출")
        text, html = email_parser.extract_text_from_email(email_message)
        full_text = (subject or '') + ' ' + (text or '') + ' ' + (html or '')
        print(f"[DEBUG] 본문 길이: text={len(text)}, html={len(html)}, full_text={len(full_text)}")

        print(f"[DEBUG] Step 4: 모델 로드 및 예측")
        model_path = os.path.abspath(MODEL_PATH)
        print(f"[DEBUG] model_path={model_path}, exists={os.path.exists(model_path)}")
        if not os.path.exists(model_path):
            return {'error': f'[3] 피싱 판별 모델 파일이 없습니다. (model_path={model_path})'}
        model_obj = joblib.load(model_path)
        vectorizer = model_obj['vectorizer']
        classifier = model_obj['classifier']
        X = vectorizer.transform([full_text])
        pred = classifier.predict(X)[0]
        proba = classifier.predict_proba(X)[0][1] if hasattr(classifier, 'predict_proba') else None
        result = 'phishing' if pred == 1 else 'not phishing'
        print(f"[DEBUG] 예측 결과: pred={pred}, proba={proba}")
        return {'subject': subject, 'sender': sender, 'result': result, 'probability': float(proba) if proba is not None else None}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[ERROR] 예외 발생: {e}\n{tb}")
        return {'error': f'[EXCEPTION] {str(e)}', 'traceback': tb}
