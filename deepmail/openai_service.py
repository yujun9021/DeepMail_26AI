"""
DeepMail - OpenAI 서비스 모듈 (최적화 리팩토링)
"""

import streamlit as st
import os
import json
import joblib
from openai import OpenAI
from config import OPENAI_CONFIG
from gmail_service import gmail_service, email_parser
from typing import List, Dict, Any, Optional, Union

# 모델 경로 정의
MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/rf_phishing_model.pkl')

# Function Calling 스키마 정의 (상수)
FUNCTION_SCHEMA = [
    {
        "name": "check_email_phishing",
        "description": "선택한 번호의 Gmail 메일이 피싱인지 판별합니다. 사용자가 '1번 메일'이라고 하면 인덱스 0을, '2번 메일'이라고 하면 인덱스 1을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "피싱 여부를 확인할 메일의 인덱스 (사용자 번호 - 1). 예: 사용자가 '1번 메일'이라고 하면 0, '2번 메일'이라고 하면 1"
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
        "description": "선택한 번호의 Gmail 메일들을 휴지통으로 이동합니다. 사용자가 '1번 메일'이라고 하면 인덱스 0을, '2번 메일'이라고 하면 인덱스 1을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "indices": {"type": "array", "items": {"type": "integer"}, "description": "삭제할 메일의 인덱스 (사용자 번호 - 1)"}
            },
            "required": ["indices"]
        },
    },
    {
        "name": "summarize_mails_by_indices",
        "description": "선택한 번호의 Gmail 메일들을 OpenAI GPT로 요약합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "indices": {"type": "array", "items": {"type": "integer"}, "description": "요약할 메일의 인덱스 (사용자 번호 - 1)"}
            },
            "required": ["indices"]
        }
    },
    {
        "name": "get_mail_content",
        "description": "번호로 Gmail 메일의 제목, 발신자, 내용을 반환합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "메일 인덱스 (사용자 번호 - 1)"}
            },
            "required": ["index"]
        }
    }
]

class OpenAIService:
    """
    OpenAI 서비스 클래스 (최적화)
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
        """메일 목록 새로고침 플래그 설정"""
        st.session_state['needs_refresh'] = True

    def check_email_phishing(self, email_index: int) -> Dict[str, Any]:
        """
        n번째(0-indexed) 이메일의 피싱 여부를 반환합니다.
        :param email_index: 확인할 이메일의 인덱스(0이 최신)
        :return: {'subject': ..., 'sender': ..., 'result': 'phishing' or 'not phishing', 'probability': float}
        """
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
                from ui_component import UIComponents
                full_content = UIComponents.get_mail_full_content(msg['id'])
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
                if function_name in ["move_message_to_trash", "delete_mails_by_indices"]:
                    if function_name == "move_message_to_trash":
                        if function_result.get("success", False):
                            self.set_needs_refresh()
                            st.success("✅ 메일 삭제 완료! 메일 목록을 새로고침합니다.")
                    elif function_name == "delete_mails_by_indices":
                        results = function_result.get("results", [])
                        if results and any(r.get("success", False) for r in results):
                            self.set_needs_refresh()
                            st.success("✅ 메일 삭제 완료! 메일 목록을 새로고침합니다.")
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
                if indices:
                    messages = self.get_gmail_messages()
                    if not messages:
                        return {"success": False, "error": "메일 목록이 없습니다."}
                    valid_indices = [idx for idx in indices if 0 <= idx < len(messages)]
                    invalid_indices = [idx + 1 for idx in indices if not (0 <= idx < len(messages))]
                    if not valid_indices:
                        return {"success": False, "error": f"유효하지 않은 메일 번호: {invalid_indices}"}
                    results = self.delete_mails_by_indices(valid_indices)
                    success_count = sum(1 for r in results if r.get("success", False))
                    message = f"{success_count}개 메일 삭제 완료"
                    if invalid_indices:
                        message += f" (유효하지 않은 번호: {invalid_indices})"
                    return {"results": results, "message": message}
                else:
                    return {"success": False, "error": "indices가 필요합니다."}
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
            else:
                return {"error": f"알 수 없는 함수: {function_name}"}
        except Exception as e:
            return {"error": f"함수 실행 중 오류: {str(e)}"}

    def delete_mails_by_indices(self, indices: List[int]) -> List[Dict[str, Any]]:
        """번호(인덱스) 리스트로 여러 메일을 휴지통으로 이동"""
        results = []
        messages = self.get_gmail_messages()
        for idx in indices:
            if 0 <= idx < len(messages):
                msg_id = messages[idx]['id']
                result = gmail_service.move_to_trash(msg_id)
                results.append({"index": idx, "success": result})
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

def analyze_recent_mails_with_websearch(n: int = 5) -> List[Dict[str, Any]]:
    """
    최근 n개 메일을 웹서치 기반으로 피싱 여부, 확률, 근거를 분석합니다.
    반환값: [{subject, snippet, gpt_analysis} ...]
    """
    client = OpenAI()
    messages = st.session_state.get('gmail_messages', [])
    results = []
    for msg in messages[:n]:
        subject = msg.get('subject', '')
        snippet = msg.get('snippet', '')
        prompt = (
            f"아래는 이메일 제목과 내용입니다.\n"
            f"제목: {subject}\n"
            f"내용: {snippet}\n"
            "이 메일이 피싱일 가능성이 있는지, 확률(0~1)과 판단 근거를 웹 검색을 활용해 알려줘."
        )
        response = client.responses.create(
            model="gpt-4o",
            tools=[{"type": "web_search"}],
            input=prompt
        )
        answer = response.output_text
        results.append({
            "subject": subject,
            "snippet": snippet,
            "gpt_analysis": answer
        })
    return results

def analyze_mail_with_agent(index: int) -> Union[str, None]:
    """
    OpenAI tool_calls(function calling + web_search)를 결합한 에이전트 스타일 메일 분석 함수.
    """
    client = OpenAI()
    tools = [
        {"type": "web_search"}
    ]
    for func_schema in FUNCTION_SCHEMA:
        tools.append({"type": "function", "function": func_schema})
    user_prompt = f"{index + 1}번 메일의 피싱 여부를 분석해줘."
    messages = [{"role": "user", "content": user_prompt}]
    while True:
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            response_message = response.choices[0].message
            if response_message.tool_calls:
                messages.append(response_message)
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    if function_name != "web_search":
                        arguments = json.loads(tool_call.function.arguments)
                        from deepmail.openai_service import openai_service
                        function_result = openai_service.handle_function_call(function_name, arguments)
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(function_result, ensure_ascii=False)
                        })
                continue
            final_content = response_message.content
            return final_content
        except Exception as e:
            return f"❌ 분석 중 오류가 발생했습니다: {str(e)}"
    return None

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