"""
DeepMail - OpenAI 서비스 모듈 (정리된 버전)
"""

import streamlit as st
import os
import json
import joblib
from openai import OpenAI
from config import OPENAI_CONFIG
from gmail_service import gmail_service, email_parser
from typing import List, Dict, Any, Optional, Union
from mail_utils import get_mail_full_content


# 모델 경로 정의
MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/rf_phishing_model.pkl')

# Function Calling 스키마 정의 (상수)
FUNCTION_SCHEMA = [
    {
        "name": "check_email_phishing",
        "description": "선택한 번호의 Gmail 메일이 피싱인지 판별합니다. 사용자가 '8번 메일'이라고 하면 인덱스 7을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "피싱 여부를 확인할 메일의 인덱스 (사용자 번호 - 1). 예: 사용자가 '8번 메일'이라고 하면 7"
                }
            },
            "required": ["index"]
        },
    },
    {
        "name": "move_message_to_trash",
        "description": "지정한 Gmail 메시지를 휴지통으로 이동합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "휴지통으로 이동할 Gmail 메시지의 고유 ID"}
            },
            "required": ["message_id"]
        },
    },
    {
        "name": "delete_mails_by_indices",
        "description": "선택한 번호의 Gmail 메일들을 휴지통으로 이동합니다. 사용자가 '8번 메일 삭제해줘'라고 하면 인덱스 7을, '2번, 3번 메일 삭제해줘'라고 하면 인덱스 1, 2를 의미합니다. 삭제 후 UI에서 즉시 사라집니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "indices": {"type": "array", "items": {"type": "integer"}, "description": "삭제할 메일의 인덱스 (사용자 번호 - 1). 예: 사용자가 '8번 메일'이라고 하면 7, '1번 메일'이라고 하면 0"}
            },
            "required": ["indices"]
        },
    },
    {
        "name": "summarize_mails_by_indices",
        "description": "선택한 번호의 Gmail 메일들을 OpenAI GPT로 요약합니다. 사용자가 '8번 메일'이라고 하면 인덱스 7을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "indices": {"type": "array", "items": {"type": "integer"}, "description": "요약할 메일의 인덱스 (사용자 번호 - 1). 예: 사용자가 '8번 메일'이라고 하면 7"}
            },
            "required": ["indices"]
        }
    },
    {
        "name": "get_mail_content",
        "description": "번호로 Gmail 메일의 제목, 발신자, 내용을 반환합니다. 사용자가 '8번 메일'이라고 하면 인덱스 7을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "메일 인덱스 (사용자 번호 - 1). 예: 사용자가 '8번 메일'이라고 하면 7"}
            },
            "required": ["index"]
        }
    },

    {
        "name": "search_mails",
        "description": "메일 제목, 발신자, 내용에서 키워드를 검색하여 관련 메일들을 찾습니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 키워드"},
                "max_results": {"type": "integer", "description": "최대 검색 결과 수", "default": 10}
            },
            "required": ["query"]
        }
    },
    {
        "name": "batch_phishing_delete",
        "description": "최근 메일들을 일괄적으로 피싱 검사하고, 피싱으로 판별된 메일들을 자동으로 삭제합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_mails": {"type": "integer", "description": "검사할 최대 메일 개수 (기본값: 50)", "default": 50},
                "threshold": {"type": "number", "description": "피싱 판별 임계값 (0.0~1.0, 기본값: 0.7)", "default": 0.7}
            },
            "required": []
        }
    },
    {
        "name": "get_mail_statistics",
        "description": "Gmail 메일들의 상세한 통계 정보를 분석하여 제공합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_mails": {"type": "integer", "description": "분석할 최대 메일 개수 (기본값: 100)", "default": 100}
            },
            "required": []
        }
    },
    {
        "name": "analyze_link_risk",
        "description": "메일의 링크와 도메인을 웹서치를 통해 위험도를 분석합니다. 사용자가 '8번 메일'이라고 하면 인덱스 7을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "분석할 메일의 인덱스 (사용자 번호 - 1). 예: 사용자가 '8번 메일'이라고 하면 7"}
            },
            "required": ["index"]
        }
    },
    {
        "name": "batch_analyze_link_risk",
        "description": "최근 n개 메일의 링크와 도메인을 일괄적으로 웹서치로 위험도 분석합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "분석할 메일 개수 (기본값: 5개)", "default": 5}
            },
            "required": []
        }
    },
    {
        "name": "web_search_mail_content",
        "description": "메일의 전체 내용을 웹서치를 통해 자유롭게 분석합니다. 사용자가 '8번 메일'이라고 하면 인덱스 7을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "분석할 메일의 인덱스 (사용자 번호 - 1). 예: 사용자가 '8번 메일'이라고 하면 7"},
                "search_query": {"type": "string", "description": "특정 검색할 내용 (선택사항). 비워두면 메일 전체 내용을 분석합니다.", "default": ""}
            },
            "required": ["index"]
        }
    }
]

class OpenAIService:
    """
    OpenAI 서비스 클래스 (정리된 버전)
    """
    def __init__(self):
        self.client = None
        self.initialize_client()

    def initialize_client(self) -> None:
        """OpenAI 클라이언트 초기화"""
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None

    def handle_error(self, error: Exception) -> str:
        """OpenAI API 오류 처리"""
        error_message = str(error)
        if "authentication" in error_message.lower() or "invalid" in error_message.lower():
            return "❌ API 키가 유효하지 않습니다. .env 파일의 OPENAI_API_KEY를 확인해주세요."
        elif "rate limit" in error_message.lower():
            return "❌ API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
        elif "quota" in error_message.lower():
            return "❌ API 할당량이 소진되었습니다. OpenAI 계정을 확인해주세요."
        else:
            return f"❌ 오류가 발생했습니다: {error_message}"

    def call_openai_chat(self, messages: List[Dict[str, Any]], model: Optional[str]=None, functions: Optional[List[Dict[str, Any]]]=None, function_call: Optional[str]=None, temperature: Optional[float]=None, max_tokens: Optional[int]=None) -> Any:
        """OpenAI Chat API 호출 공통 함수"""
        model = model or OPENAI_CONFIG['model']
        temperature = temperature if temperature is not None else OPENAI_CONFIG['temperature']
        max_tokens = max_tokens or OPENAI_CONFIG['max_tokens']
        try:
            return self.client.chat.completions.create(
                model=model,
                messages=messages,
                functions=functions,
                function_call=function_call,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            raise RuntimeError(self.handle_error(e))

    def get_gmail_messages(self) -> List[Dict[str, Any]]:
        """세션에서 Gmail 메일 목록 반환"""
        return st.session_state.get('gmail_messages', [])

    def set_needs_refresh(self) -> None:
        """메일 목록 새로고침 플래그 설정 (현재 사용하지 않음)"""
        # 자동 새로고침을 제거하여 성능 향상
        # st.session_state['needs_refresh'] = True
        pass

    # ===== 웹서치 기능 (핵심) =====
    
    def web_search_analysis_with_prompt(self, custom_prompt: str) -> str:
        """
        커스텀 프롬프트로 웹서치 분석 (핵심 기능)
        """
        try:
            print(f"🔍 [웹서치] 커스텀 프롬프트 분석 시작...")
            print(f"📝 [웹서치] 프롬프트 미리보기: {custom_prompt[:100]}...")
            
            print("🌐 [웹서치] OpenAI API 호출 중...")
            response = self.client.responses.create(
                model="gpt-4.1",
                tools=[{"type": "web_search_preview"}],
                input=custom_prompt
            )
            
            result = response.output_text
            print(f"✅ [웹서치] 분석 완료! 결과 길이: {len(result)}자")
            print(f"📝 [웹서치] 결과 미리보기: {result[:100]}...")
            
            return result
            
        except Exception as e:
            print(f"💥 [웹서치] 오류 발생: {str(e)}")
            return f"❌ 웹서치 분석 중 오류: {str(e)}"

    # ===== 기존 기능들 =====
    
    def check_email_phishing(self, email_index: int) -> Dict[str, Any]:
        """ML 모델 기반 피싱 검사"""
        try:
            print(f"[DEBUG] Step 1: 인증 및 메일 목록 가져오기")
            messages = self.get_gmail_messages()
            print(f"[DEBUG] messages count: {len(messages) if messages else 0}, email_index: {email_index}")
            
            if not messages or email_index >= len(messages):
                return {'error': f'[1] 해당 번호의 메일이 없습니다. (messages={len(messages) if messages else 0}, email_index={email_index})'}

            msg_info = messages[email_index]
            message_id = msg_info['id']
            subject = msg_info['subject']
            sender = msg_info['sender']
            
            print(f"[DEBUG] Step 2: Raw 메일 가져오기, message_id={repr(message_id)}, subject={repr(subject)}")

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
            
            return {
                'subject': subject, 
                'sender': sender, 
                'result': result, 
                'probability': float(proba) if proba is not None else None
            }
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[ERROR] 예외 발생: {e}\n{tb}")
            return {'error': f'[EXCEPTION] {str(e)}', 'traceback': tb}

    def batch_check_phishing_and_delete(self, max_mails: int = 50, threshold: float = 0.7) -> Dict[str, Any]:
        """일괄 피싱 검사 및 삭제"""
        try:
            print(f"🚀 [일괄 피싱 검사] 최대 {max_mails}개 메일 검사 시작...")
            
            messages = self.get_gmail_messages()
            if not messages:
                return {'error': '메일이 없습니다.'}
            
            # 검사할 메일 수 제한
            messages_to_check = messages[:max_mails]
            total_checked = len(messages_to_check)
            
            print(f"📧 [일괄 피싱 검사] {total_checked}개 메일 검사 중...")
            
            # 모델 로드
            model_path = os.path.abspath(MODEL_PATH)
            if not os.path.exists(model_path):
                return {'error': f'피싱 판별 모델 파일이 없습니다. (model_path={model_path})'}
            
            model_obj = joblib.load(model_path)
            vectorizer = model_obj['vectorizer']
            classifier = model_obj['classifier']
            
            phishing_mails = []
            checked_count = 0
            
            for i, msg in enumerate(messages_to_check):
                try:
                    print(f"🔍 [일괄 피싱 검사] {i+1}/{total_checked}번째 메일 검사 중...")
                    
                    message_id = msg['id']
                    subject = msg['subject']
                    sender = msg['sender']
                    
                    # 메일 본문 가져오기
                    email_message = gmail_service.get_raw_message(message_id)
                    if email_message is None:
                        print(f"⚠️ [일괄 피싱 검사] {i+1}번째 메일 본문 로드 실패, 건너뜀")
                        continue
                    
                    # 본문 추출
                    text, html = email_parser.extract_text_from_email(email_message)
                    full_text = (subject or '') + ' ' + (text or '') + ' ' + (html or '')
                    
                    # 피싱 검사
                    X = vectorizer.transform([full_text])
                    proba = classifier.predict_proba(X)[0][1] if hasattr(classifier, 'predict_proba') else 0.5
                    
                    checked_count += 1
                    
                    # 임계값 이상이면 피싱으로 판단
                    if proba >= threshold:
                        phishing_mails.append({
                            'index': i,
                            'message_id': message_id,
                            'subject': subject,
                            'sender': sender,
                            'probability': float(proba)
                        })
                        print(f"🚨 [일괄 피싱 검사] 피싱 메일 발견: {subject[:50]}... (확률: {proba:.2f})")
                    
                except Exception as e:
                    print(f"❌ [일괄 피싱 검사] {i+1}번째 메일 검사 실패: {str(e)}")
                    continue
            
            print(f"✅ [일괄 피싱 검사] 검사 완료! 총 {checked_count}개 검사, 피싱 {len(phishing_mails)}개 발견")
            
            # 피싱 메일 삭제
            deleted_count = 0
            if phishing_mails:
                print(f"🗑️ [일괄 피싱 검사] {len(phishing_mails)}개 피싱 메일 삭제 시작...")
                
                for phishing_mail in phishing_mails:
                    try:
                        success = gmail_service.move_to_trash(phishing_mail['message_id'])
                        if success:
                            deleted_count += 1
                            print(f"✅ [일괄 피싱 검사] 삭제 성공: {phishing_mail['subject'][:50]}...")
                        else:
                            print(f"❌ [일괄 피싱 검사] 삭제 실패: {phishing_mail['subject'][:50]}...")
                    except Exception as e:
                        print(f"❌ [일괄 피싱 검사] 삭제 중 오류: {str(e)}")
                        continue
            
            return {
                'total_checked': checked_count,
                'phishing_found': len(phishing_mails),
                'deleted_count': deleted_count,
                'phishing_mails': phishing_mails,
                'threshold': threshold
            }
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[ERROR] 일괄 피싱 검사 예외 발생: {e}\n{tb}")
            return {'error': f'일괄 피싱 검사 중 오류: {str(e)}'}

    def get_mail_statistics(self, max_mails: int = 100) -> Dict[str, Any]:
        """메일 통계 분석"""
        try:
            print(f"📊 [메일 통계] 최대 {max_mails}개 메일 분석 시작...")
            
            messages = self.get_gmail_messages()
            if not messages:
                return {'error': '메일이 없습니다.'}
            
            # 분석할 메일 수 제한
            messages_to_analyze = messages[:max_mails]
            total_messages = len(messages_to_analyze)
            
            print(f"📧 [메일 통계] {total_messages}개 메일 분석 중...")
            
            # 기본 통계
            stats = {
                'total_messages': total_messages,
                'total_all_messages': len(messages),
                'sender_stats': {},
                'domain_stats': {},
                'keyword_stats': {}
            }
            
            # 발신자별 통계
            sender_counts = {}
            domain_counts = {}
            
            # 키워드 통계
            keyword_counts = {}
            
            for i, msg in enumerate(messages_to_analyze):
                try:
                    print(f"📊 [메일 통계] {i+1}/{total_messages}번째 메일 분석 중...")
                    
                    # 발신자 통계
                    sender = msg.get('sender', 'Unknown')
                    sender_counts[sender] = sender_counts.get(sender, 0) + 1
                    
                    # 도메인 추출
                    if '@' in sender:
                        domain = sender.split('@')[-1]
                        domain_counts[domain] = domain_counts.get(domain, 0) + 1
                    
                    # 키워드 분석 (제목 + 내용)
                    subject = msg.get('subject', '')
                    snippet = msg.get('snippet', '')
                    text_for_keywords = (subject + ' ' + snippet).lower()
                    
                    # 일반적인 키워드들
                    keywords = [
                        'urgent', 'important', 'notice', 'alert', 'warning',
                        'payment', 'invoice', 'order', 'delivery', 'shipping',
                        'account', 'security', 'password', 'login', 'verify',
                        'confirm', 'update', 'expire', 'limited', 'offer',
                        'free', 'discount', 'sale', 'promotion', 'deal',
                        'newsletter', 'subscription', 'unsubscribe',
                        'support', 'help', 'contact', 'service'
                    ]
                    
                    for keyword in keywords:
                        if keyword in text_for_keywords:
                            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
                    
                except Exception as e:
                    print(f"❌ [메일 통계] {i+1}번째 메일 분석 실패: {str(e)}")
                    continue
            
            # 통계 정리
            stats['sender_stats'] = {
                'unique_senders': len(sender_counts),
                'top_senders': sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            }
            
            stats['domain_stats'] = {
                'unique_domains': len(domain_counts),
                'top_domains': sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            }
            
            stats['keyword_stats'] = {
                'top_keywords': sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:15]
            }
            
            print(f"✅ [메일 통계] 분석 완료!")
            
            return stats
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[ERROR] 메일 통계 분석 예외 발생: {e}\n{tb}")
            return {'error': f'메일 통계 분석 중 오류: {str(e)}'}



    def summarize_mails(self, indices: List[int], model: Optional[str]=None, temperature: Optional[float]=None) -> str:
        """메일 요약 (전체 내용 기반)"""
        if not self.client:
            return "❌ OpenAI API 키가 설정되지 않았습니다."
        model = model or OPENAI_CONFIG['model']
        temperature = temperature if temperature is not None else OPENAI_CONFIG['temperature']
        messages = self.get_gmail_messages()
        summaries = []
        
        for idx in indices:
            if 0 <= idx < len(messages):
                msg = messages[idx]
                full_content = get_mail_full_content(msg['id'])
                if full_content['error']:
                    content_text = msg['snippet']
                else:
                    if full_content['body_text']:
                        content_text = full_content['body_text']
                    elif full_content['body_html']:
                        content_text = email_parser.extract_text_from_html(full_content['body_html'])
                    else:
                        content_text = msg['snippet']
                prompt = f"""다음 이메일을 요약해줘.\n\n제목: {msg['subject']}\n발신자: {msg['sender']}\n내용: {content_text[:2000]}"""
                try:
                    response = self.call_openai_chat(
                        messages=[{"role": "user", "content": prompt}],
                        model=model,
                        temperature=temperature
                    )
                    summary = response.choices[0].message.content.strip()
                except Exception as e:
                    summary = f"[{idx+1}] 요약 실패: {str(e)}"
                summaries.append(f"[{idx+1}] {msg['subject']}\n{summary}")
            else:
                summaries.append(f"[{idx+1}] 존재하지 않는 메일입니다.")
        return "\n\n".join(summaries)

    def chat_with_function_call(self, user_input: str) -> str:
        """Function calling을 활용한 챗봇 대화"""
        if not self.client:
            return "❌ OpenAI API 키가 설정되지 않았습니다."
        try:
            messages = [{"role": "user", "content": user_input}]
            response = self.call_openai_chat(
                messages=messages,
                functions=FUNCTION_SCHEMA,
                function_call="auto"
            )
            message = response.choices[0].message
            if hasattr(message, "function_call") and message.function_call:
                function_name = message.function_call.name
                arguments = json.loads(message.function_call.arguments)
                function_result = self.handle_function_call(function_name, arguments)
                messages.append({
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(function_result, ensure_ascii=False)
                })
                
                # 피싱 검사 결과에 대한 명시적 프롬프트 추가
                if function_name == "check_email_phishing":
                    if "error" not in function_result:
                        # 성공적인 피싱 검사 결과에 대한 프롬프트
                        analysis_prompt = f"""
다음은 {arguments.get('index', 0) + 1}번 메일의 피싱 검사 결과입니다:

제목: {function_result.get('subject', 'N/A')}
발신자: {function_result.get('sender', 'N/A')}
결과: {function_result.get('result', 'N/A')}
확률: {function_result.get('probability', 'N/A')}

이 결과를 바탕으로 사용자에게 친화적이고 명확한 설명을 제공해주세요. 
피싱 메일인 경우 주의사항과 권장 조치를 포함하고, 
정상 메일인 경우 안심할 수 있다는 메시지를 포함해주세요.
"""
                        messages.append({"role": "user", "content": analysis_prompt})
                    else:
                        # 오류 발생 시 프롬프트
                        error_prompt = f"""
피싱 검사 중 오류가 발생했습니다: {function_result.get('error', '알 수 없는 오류')}

사용자에게 오류 상황을 친화적으로 설명하고, 
다시 시도하거나 다른 방법을 제안해주세요.
"""
                        messages.append({"role": "user", "content": error_prompt})
                
                final_response = self.call_openai_chat(
                    messages=messages,
                    functions=FUNCTION_SCHEMA,
                    function_call="none"
                )
                response_content = final_response.choices[0].message.content
                
                # 메일 삭제 시 성공 메시지만 표시 (자동 새로고침 제거)
                if function_name in ["move_message_to_trash", "delete_mails_by_indices", "batch_phishing_delete"]:
                    if function_name == "move_message_to_trash":
                        if function_result.get("success", False):
                            st.success("✅ 메일이 휴지통으로 이동되었습니다.")
                    elif function_name == "delete_mails_by_indices":
                        results = function_result.get("results", [])
                        if results and any(r.get("success", False) for r in results):
                            st.success("✅ 메일 삭제가 완료되었습니다.")
                    elif function_name == "batch_phishing_delete":
                        if "error" not in function_result:
                            total_checked = function_result.get("total_checked", 0)
                            phishing_found = function_result.get("phishing_found", 0)
                            deleted_count = function_result.get("deleted_count", 0)
                            threshold = function_result.get("threshold", 0.7)
                            
                            st.success(f"✅ 피싱 메일 일괄 삭제 완료!")
                            st.info(f"📊 검사 결과: 총 {total_checked}개 메일 검사, 피싱 {phishing_found}개 발견, {deleted_count}개 삭제 (임계값: {threshold*100:.0f}%)")
                            
                            # 삭제된 메일 목록 표시
                            if function_result.get("phishing_mails"):
                                with st.expander("🗑️ 삭제된 피싱 메일 목록"):
                                    for mail in function_result["phishing_mails"]:
                                        st.write(f"• {mail['subject']} (확률: {mail['probability']*100:.1f}%)")
                        else:
                            st.error(f"❌ 피싱 메일 삭제 중 오류: {function_result.get('error', '알 수 없는 오류')}")
                
                return response_content
            else:
                return message.content
        except Exception as e:
            return f"❌ 오류가 발생했습니다: {str(e)}"

    def handle_function_call(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Function calling 결과를 실제 함수로 실행"""
        try:
            if function_name == "check_email_phishing":
                index = arguments.get("index")
                if index is not None:
                    result = self.check_email_phishing(index)
                    return result
                else:
                    return {"error": "index가 필요합니다."}
            elif function_name == "move_message_to_trash":
                message_id = arguments.get("message_id")
                if message_id:
                    success = gmail_service.move_to_trash(message_id)
                    return {"success": success, "message": "메일이 휴지통으로 이동되었습니다." if success else "메일 이동에 실패했습니다."}
                else:
                    return {"success": False, "error": "message_id가 필요합니다."}
            elif function_name == "delete_mails_by_indices":
                indices = arguments.get("indices", [])
                print(f"[DEBUG] 삭제 요청된 인덱스: {indices}")
                if indices:
                    messages = self.get_gmail_messages()
                    if not messages:
                        return {"success": False, "error": "메일 목록이 없습니다."}
                    
                    valid_indices = [idx for idx in indices if 0 <= idx < len(messages)]
                    invalid_indices = [idx for idx in indices if not (0 <= idx < len(messages))]
                    
                    print(f"[DEBUG] 유효한 인덱스: {valid_indices}, 유효하지 않은 번호: {invalid_indices}")
                    
                    if not valid_indices:
                        return {"success": False, "error": f"유효하지 않은 메일 번호: {invalid_indices}"}
                    
                    results = self.delete_mails_by_indices(valid_indices)
                    success_count = sum(1 for r in results if r.get("success", False))
                    
                    # 성공적으로 삭제된 메일들의 제목 목록
                    deleted_subjects = [r.get("subject", "") for r in results if r.get("success", False)]
                    
                    message = f"✅ {success_count}개 메일이 성공적으로 삭제되었습니다!"
                    if deleted_subjects:
                        message += f"\n\n삭제된 메일:\n" + "\n".join([f"• {subject}" for subject in deleted_subjects])
                    
                    if invalid_indices:
                        message += f"\n\n⚠️ 유효하지 않은 번호: {invalid_indices}번"
                    
                    return {"results": results, "message": message, "success": True}
                else:
                    return {"success": False, "error": "삭제할 메일 번호를 지정해주세요."}
            elif function_name == "summarize_mails_by_indices":
                indices = arguments.get("indices", [])
                if indices:
                    summary = self.summarize_mails(indices)
                    return {"summary": summary, "message": f"{len(indices)}개 메일 요약 완료"}
                else:
                    return {"success": False, "error": "indices가 필요합니다."}
            elif function_name == "get_mail_content":
                index = arguments.get("index")
                messages = self.get_gmail_messages()
                if messages and index is not None and 0 <= index < len(messages):
                    return self.get_mail_content(index)
                else:
                    return {"error": f"유효하지 않은 메일 번호: {index + 1}번 (총 {len(messages)}개 메일)"}

            elif function_name == "search_mails":
                query = arguments.get("query")
                max_results = arguments.get("max_results", 10)
                if query:
                    return {"results": self.search_mails(query, max_results)}
                else:
                    return {"error": "query가 필요합니다."}
            elif function_name == "batch_phishing_delete":
                # 일괄 피싱 검사 및 삭제
                max_mails = arguments.get("max_mails", 50)
                threshold = arguments.get("threshold", 0.7)
                result = self.batch_check_phishing_and_delete(max_mails, threshold)
                return result
            elif function_name == "get_mail_statistics":
                # 메일 통계 분석
                max_mails = arguments.get("max_mails", 100)
                result = self.get_mail_statistics(max_mails)
                return result
            elif function_name == "analyze_link_risk":
                # 개별 메일 링크 위험도 분석
                index = arguments.get("index")
                if index is not None:
                    result = self.analyze_link_risk(index)
                    return {"analysis": result}
                else:
                    return {"error": "index가 필요합니다."}
            elif function_name == "batch_analyze_link_risk":
                # 일괄 링크 위험도 분석
                n = arguments.get("n", 5)
                results = self.batch_analyze_link_risk(n)
                return {"results": results, "message": f"{len(results)}개 메일 링크 위험도 일괄 분석 완료"}
            elif function_name == "web_search_mail_content":
                # 메일 전체 내용 웹서치 분석
                index = arguments.get("index")
                search_query = arguments.get("search_query", "")
                if index is not None:
                    result = self.web_search_mail_content(index, search_query)
                    return {"analysis": result}
                else:
                    return {"error": "index가 필요합니다."}
            else:
                return {"error": f"알 수 없는 함수: {function_name}"}
        except Exception as e:
            return {"error": f"함수 실행 중 오류: {str(e)}"}

    def delete_mails_by_indices(self, indices: List[int]) -> List[Dict[str, Any]]:
        """번호(인덱스) 리스트로 여러 메일을 휴지통으로 이동하고 UI 업데이트"""
        results = []
        messages = self.get_gmail_messages()
        
        # 삭제된 메일 ID들을 추적하기 위한 세션 상태 초기화
        if 'deleted_mail_ids' not in st.session_state:
            st.session_state.deleted_mail_ids = set()
        
        for idx in indices:
            if 0 <= idx < len(messages):
                msg_id = messages[idx]['id']
                result = gmail_service.move_to_trash(msg_id)
                
                if result:
                    # 성공적으로 삭제된 경우 UI에서 즉시 사라지도록 세션에 추가
                    st.session_state.deleted_mail_ids.add(msg_id)
                    
                    # 해당 메일의 캐시도 제거
                    cache_key = f"mail_content_{msg_id}"
                    if cache_key in st.session_state:
                        del st.session_state[cache_key]
                
                results.append({
                    "index": idx, 
                    "success": result, 
                    "message_id": msg_id,
                    "subject": messages[idx]['subject']
                })
            else:
                results.append({"index": idx, "success": False, "error": "존재하지 않는 번호"})
        
        return results

    def get_mail_content(self, index: int) -> Dict[str, Any]:
        """번호(인덱스)로 메일의 제목/내용을 반환"""
        messages = self.get_gmail_messages()
        if 0 <= index < len(messages):
            msg = messages[index]
            return {
                "subject": msg["subject"],
                "sender": msg["sender"],
                "snippet": msg["snippet"]
            }
        else:
            return {"error": f"{index+1}번 메일이 존재하지 않습니다."}

    def search_mails(self, query: str, max_results: int = 10) -> list:
        """제목, 발신자, 본문(snippet)에서 키워드로 검색하고 스니펫 기반 요약 생성"""
        messages = self.get_gmail_messages()
        results = []
        query_lower = query.lower()
        
        # 검색 결과 수집
        search_results = []
        for idx, msg in enumerate(messages):
            if (query_lower in msg.get('subject', '').lower() or
                query_lower in msg.get('sender', '').lower() or
                query_lower in msg.get('snippet', '').lower()):
                search_results.append({
                    "index": idx,
                    "mail_number": idx + 1,  # 사용자 번호 (1부터 시작)
                    "subject": msg.get('subject', ''),
                    "sender": msg.get('sender', ''),
                    "snippet": msg.get('snippet', '')
                })
            if len(search_results) >= max_results:
                break
        
        # 각 검색 결과에 대해 개별 요약 생성
        for result in search_results:
            if self.client:
                try:
                    # 개별 메일 요약 생성 (메일 번호 포함)
                    summary_prompt = f"""다음 {result['mail_number']}번 메일을 간단히 요약해주세요:

제목: {result['subject']}
발신자: {result['sender']}
내용: {result['snippet'][:300]}

1-2문장으로 핵심 내용을 요약해주세요."""

                    response = self.call_openai_chat(
                        messages=[{"role": "user", "content": summary_prompt}],
                        temperature=0.3
                    )
                    summary = response.choices[0].message.content.strip()
                    result["summary"] = summary
                except Exception as e:
                    result["summary"] = f"요약 실패: {str(e)}"
            else:
                result["summary"] = "요약을 생성할 수 없습니다."
            
            result["snippet_preview"] = result["snippet"][:100]
            results.append(result)
        
        return results

    def analyze_link_risk(self, email_index: int) -> str:
        """
        개별 메일의 링크와 도메인을 웹서치를 통해 위험도 분석
        """
        try:
            print(f"🔍 [링크분석] {email_index + 1}번 메일 링크 위험도 분석 시작...")
            
            messages = self.get_gmail_messages()
            if not messages or email_index >= len(messages):
                print(f"❌ [링크분석] {email_index + 1}번 메일이 존재하지 않음")
                return "❌ 해당 번호의 메일이 없습니다."
            
            msg = messages[email_index]
            subject = msg['subject']
            
            # 메일 전체 내용 가져오기
            from mail_utils import get_mail_full_content
            mail_content = get_mail_full_content(msg['id'])
            
            if mail_content.get('error', False):
                return "❌ 메일 내용을 가져올 수 없습니다."
            
            body_text = mail_content.get('body_text', '') or ''
            
            # 링크와 도메인 추출
            import re
            links = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', body_text)
            domains = re.findall(r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', body_text)
            
            if not links and not domains:
                return "📭 이 메일에서 링크나 도메인을 찾을 수 없습니다."
            
            # 웹서치 분석 수행
            web_search_prompt = f"""
다음 이메일의 링크와 도메인을 웹 검색을 통해 위험도를 평가해주세요:

제목: {subject}
발견된 링크: {links[:5]}  # 최대 5개
발견된 도메인: {list(set(domains))[:5]}  # 중복 제거 후 최대 5개

각 링크/도메인의 위험도, 악성 여부, 그리고 근거를 웹 검색을 통해 분석해주세요.
결과는 다음과 같은 형식으로 정리해주세요:

**🔗 발견된 링크/도메인:**
- [링크/도메인명]: [위험도] - [분석 결과]

**⚠️ 전체 위험도 평가:**
[전체적인 위험도 평가]

**💡 권장 조치:**
[사용자에게 권장할 조치사항]
"""
            
            print("🌐 [링크분석] OpenAI API 호출 중...")
            response = self.client.responses.create(
                model="gpt-4.1",
                tools=[{"type": "web_search_preview"}],
                input=web_search_prompt
            )
            
            result = response.output_text
            print(f"✅ [링크분석] 분석 완료! 결과 길이: {len(result)}자")
            
            return result
            
        except Exception as e:
            print(f"💥 [링크분석] 오류 발생: {str(e)}")
            return f"❌ 링크 위험도 분석 중 오류: {str(e)}"

    def batch_analyze_link_risk(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        최근 n개 메일의 링크와 도메인을 일괄적으로 웹서치로 위험도 분석
        """
        print(f"🚀 [링크분석] 최근 {n}개 메일 링크 위험도 일괄 분석 시작...")
        
        messages = self.get_gmail_messages()
        results = []
        
        for i, msg in enumerate(messages[:n]):
            print(f"📧 [링크분석] {i+1}/{n}번째 메일 분석 중...")
            
            subject = msg.get('subject', '')
            print(f"   제목: {subject[:50]}...")
            
            try:
                # 개별 메일 링크 분석
                analysis_result = self.analyze_link_risk(i)
                print(f"   ✅ [링크분석] {i+1}번째 메일 분석 완료")
                
            except Exception as e:
                print(f"   💥 [링크분석] {i+1}번째 메일 분석 실패: {str(e)}")
                analysis_result = f"분석 실패: {str(e)}"
            
            results.append({
                "mail_number": i + 1,
                "subject": subject,
                "link_analysis": analysis_result
            })
        
        print(f"🎉 [링크분석] 전체 {len(results)}개 메일 링크 위험도 분석 완료!")
        return results

    def web_search_mail_content(self, email_index: int, search_query: str = "") -> str:
        """
        메일의 전체 내용을 웹서치를 통해 자유롭게 분석
        """
        try:
            print(f"🔍 [웹서치] {email_index + 1}번 메일 전체 내용 분석 시작...")
            
            messages = self.get_gmail_messages()
            if not messages or email_index >= len(messages):
                print(f"❌ [웹서치] {email_index + 1}번 메일이 존재하지 않음")
                return "❌ 해당 번호의 메일이 없습니다."
            
            msg = messages[email_index]
            subject = msg['subject']
            
            # 메일 전체 내용 가져오기
            from mail_utils import get_mail_full_content
            mail_content = get_mail_full_content(msg['id'])
            
            if mail_content.get('error', False):
                return "❌ 메일 내용을 가져올 수 없습니다."
            
            body_text = mail_content.get('body_text', '') or ''
            
            # 검색할 내용 결정
            if search_query:
                # 특정 검색어가 있으면 해당 내용만 사용
                search_content = search_query
                print(f"🔍 [웹서치] 특정 검색어 분석: {search_query[:50]}...")
            else:
                # 검색어가 없으면 메일 전체 내용 사용 (길이 제한)
                search_content = body_text[:2000]  # 처음 2000자만 사용
                print(f"🔍 [웹서치] 메일 전체 내용 분석 (처음 2000자)")
            
            # 웹서치 분석 수행
            web_search_prompt = f"""
다음 이메일의 내용을 웹 검색을 통해 자유롭게 분석해주세요:

제목: {subject}
분석할 내용: {search_content}

웹 검색을 통해 이 내용의 신뢰성, 관련 정보, 위험도, 배경 지식 등을 종합적으로 분석해주세요.
결과는 다음과 같은 형식으로 정리해주세요:

**📧 메일 정보:**
- 제목: {subject}
- 분석 내용: {search_content[:100]}...

**🔍 웹서치 분석 결과:**
[웹 검색을 통해 찾은 관련 정보와 분석]

**⚠️ 위험도 평가:**
[내용의 신뢰성과 위험도 평가]

**💡 추가 정보:**
[관련된 배경 지식이나 참고사항]
"""
            
            print("🌐 [웹서치] OpenAI API 호출 중...")
            response = self.client.responses.create(
                model="gpt-4.1",
                tools=[{"type": "web_search_preview"}],
                input=web_search_prompt
            )
            
            result = response.output_text
            print(f"✅ [웹서치] 분석 완료! 결과 길이: {len(result)}자")
            
            return result
            
        except Exception as e:
            print(f"💥 [웹서치] 오류 발생: {str(e)}")
            return f"❌ 웹서치 분석 중 오류: {str(e)}"

# 전역 OpenAI 서비스 인스턴스
openai_service = OpenAIService()

# 세션에 인증 정보가 있으면 gmail_service에 credentials와 service를 복구
if st.session_state.get('gmail_credentials'):
    gmail_service.credentials = st.session_state['gmail_credentials']
    try:
        from googleapiclient.discovery import build
        gmail_service.service = build('gmail', 'v1', credentials=gmail_service.credentials)
    except Exception as e:
        gmail_service.service = None 