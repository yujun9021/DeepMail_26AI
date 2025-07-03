"""
DeepMail - OpenAI 서비스 모듈
"""

import streamlit as st
import os
import json
from openai import OpenAI
from config import OPENAI_CONFIG
from gmail_service import gmail_service
from gmail_service import email_parser

# Function Calling 스키마 정의
FunctionSchema = [
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
                "message_id": {
                    "type": "string",
                    "description": "휴지통으로 이동할 Gmail 메시지의 고유 ID"
                }
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
                "indices": {
                    "type": "array",
                    "items": { "type": "integer" },
                    "description": "삭제할 메일의 인덱스 (사용자 번호 - 1). 예: 사용자가 '1번 메일'이라고 하면 [0], '2번, 4번 메일'이라고 하면 [1, 3]"
                }
            },
            "required": ["indices"]
        },
    },
    {
        "name": "summarize_mails_by_indices",
        "description": "선택한 번호의 Gmail 메일들을 OpenAI GPT로 요약합니다. 사용자가 '1번 메일'이라고 하면 인덱스 0을, '2번 메일'이라고 하면 인덱스 1을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "indices": {
                    "type": "array",
                    "items": { "type": "integer" },
                    "description": "요약할 메일의 인덱스 (사용자 번호 - 1). 예: 사용자가 '1번 메일'이라고 하면 [0], '2번, 4번 메일'이라고 하면 [1, 3]"
                }
            },
            "required": ["indices"]
        }
    },
    {
        "name": "get_mail_content",
        "description": "번호로 Gmail 메일의 제목, 발신자, 내용을 반환합니다. 사용자가 '1번 메일'이라고 하면 인덱스 0을, '2번 메일'이라고 하면 인덱스 1을 의미합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "메일 인덱스 (사용자 번호 - 1). 예: 사용자가 '1번 메일'이라고 하면 0, '2번 메일'이라고 하면 1"
                }
            },
            "required": ["index"]
        }
    }
]

class OpenAIService:
    """OpenAI 서비스 클래스"""
    
    def __init__(self):
        self.client = None
        self.initialize_client()
    
    def initialize_client(self):
        """OpenAI 클라이언트 초기화"""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
    
    def handle_error(self, error):
        """OpenAI API 오류 처리"""
        error_message = str(error)
        if "authentication" in error_message.lower() or "invalid" in error_message.lower():
            return "❌ API 키가 유효하지 않습니다. .env 파일의 OPENAI_API_KEY를 확인해주세요."
        elif "rate limit" in error_message.lower():
            return "❌ API 요청 한도가 초과했습니다. 잠시 후 다시 시도해주세요."
        elif "quota" in error_message.lower():
            return "❌ API 할당량이 소진되었습니다. OpenAI 계정을 확인해주세요."
        else:
            return f"❌ 오류가 발생했습니다: {error_message}"
    
    def summarize_mails(self, indices, model=None, temperature=None):
        """메일 요약 (전체 내용 기반으로 개선)"""
        if not self.client:
            return "❌ OpenAI API 키가 설정되지 않았습니다."
        
        model = model or OPENAI_CONFIG['model']
        temperature = temperature or OPENAI_CONFIG['temperature']
        
        messages = st.session_state.gmail_messages
        summaries = []

        for idx in indices:
            if 0 <= idx < len(messages):
                msg = messages[idx]
                
                # 전체 메일 내용 가져오기 (캐시 활용)
                from ui_component import UIComponents
                full_content = UIComponents.get_mail_full_content(msg['id'])
                
                if full_content['error']:
                    # 전체 내용 가져오기 실패 시 스니펫으로 대체
                    content_text = msg['snippet']
                else:
                    # 전체 내용 사용 (텍스트 우선, HTML이 있으면 텍스트로 변환)
                    if full_content['body_text']:
                        content_text = full_content['body_text']
                    elif full_content['body_html']:
                        content_text = email_parser.extract_text_from_html(full_content['body_html'])
                    else:
                        content_text = msg['snippet']  # 폴백
                
                # 요약 프롬프트 생성
                prompt = f"""다음 이메일을 3줄 이내로 요약해줘.

제목: {msg['subject']}
발신자: {msg['sender']}
내용: {content_text[:2000]}"""  # 내용이 너무 길면 잘라내기
                
                try:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=OPENAI_CONFIG['max_tokens']
                    )
                    summary = response.choices[0].message.content.strip()
                except Exception as e:
                    summary = f"[{idx+1}] 요약 실패: {str(e)}"
                summaries.append(f"[{idx+1}] {msg['subject']}\n{summary}")
            else:
                summaries.append(f"[{idx+1}] 존재하지 않는 메일입니다.")
        
        return "\n\n".join(summaries)
    
    def chat_with_function_call(self, user_input):
        """Function calling을 활용한 챗봇 대화 및 함수 결과 반환 (assistant_message, phishing_result or None)"""
        if not self.client:
            return ("❌ OpenAI API 키가 설정되지 않았습니다.", None)
        
        try:
            # 1. 사용자 메시지 준비
            messages = [{"role": "user", "content": user_input}]
            phishing_result = None
            function_name = None
            
            # 2. 함수 스키마와 함께 OpenAI API 호출
            response = self.client.chat.completions.create(
                model=OPENAI_CONFIG['model'],
                messages=messages,
                functions=FunctionSchema,
                function_call="auto"
            )
            message = response.choices[0].message

            # 3. function_call이 있으면 실제 함수 실행
            if hasattr(message, "function_call") and message.function_call:
                function_name = message.function_call.name
                arguments = json.loads(message.function_call.arguments)
                
                # 실제 함수 실행
                function_result = self.handle_function_call(function_name, arguments)

                # 피싱 체크 함수 결과 저장
                if function_name == "check_email_phishing":
                    phishing_result = function_result

                # 4. 함수 실행 결과를 function 역할로 추가
                messages.append({
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(function_result, ensure_ascii=False)
                })

                # 5. 최종 자연어 응답 생성
                final_response = self.client.chat.completions.create(
                    model=OPENAI_CONFIG['model'],
                    messages=messages,
                    functions=FunctionSchema,
                    function_call="none"
                )
                
                response_content = final_response.choices[0].message.content
                
                # 삭제 관련 함수 실행 후 UI 새로고침 플래그 설정
                if function_name in ["move_message_to_trash", "delete_mails_by_indices"]:
                    # 삭제 작업이 성공적으로 수행된 경우에만 새로고침 플래그 설정
                    if function_name == "move_message_to_trash":
                        success = function_result.get("success", False)
                        if success:
                            st.session_state.needs_refresh = True
                            st.success("✅ 메일 삭제 완료! 메일 목록을 새로고침합니다.")
                    elif function_name == "delete_mails_by_indices":
                        results = function_result.get("results", [])
                        if results and any(r.get("success", False) for r in results):
                            st.session_state.needs_refresh = True
                            st.success("✅ 메일 삭제 완료! 메일 목록을 새로고침합니다.")
                
                return (response_content, phishing_result)
            else:
                # 일반 답변
                return (message.content, None)
        
        except Exception as e:
            return (f"❌ 오류가 발생했습니다: {str(e)}", None)

    
    def handle_function_call(self, function_name, arguments):
        """Function calling 결과를 실제 함수로 실행"""
        try:
            # 디버깅: 함수 호출 로그
            print(f"🔍 Function call: {function_name} with arguments: {arguments}")
            
            if function_name == "move_message_to_trash":
                message_id = arguments.get("message_id")
                if message_id:
                    success = gmail_service.move_to_trash(message_id)
                    return {"success": success, "message": "메일이 휴지통으로 이동되었습니다." if success else "메일 이동에 실패했습니다."}
                else:
                    return {"success": False, "error": "message_id가 필요합니다."}
            
            elif function_name == "delete_mails_by_indices":
                indices = arguments.get("indices", [])
                if indices:
                    # 인덱스 유효성 검사 및 변환
                    messages = st.session_state.gmail_messages
                    if not messages:
                        return {"success": False, "error": "메일 목록이 없습니다."}
                    
                    valid_indices = []
                    invalid_indices = []
                    for idx in indices:
                        if 0 <= idx < len(messages):
                            valid_indices.append(idx)
                        else:
                            invalid_indices.append(idx + 1)  # 사용자 번호로 변환
                    
                    if not valid_indices:
                        return {"success": False, "error": f"유효하지 않은 메일 번호: {invalid_indices}"}
                    
                    results = self.delete_mails_by_indices(valid_indices)
                    
                    # 결과 메시지 생성
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
                if index is not None:
                    # 인덱스 유효성 검사
                    messages = st.session_state.gmail_messages
                    if not messages:
                        return {"error": "메일 목록이 없습니다."}
                    
                    if 0 <= index < len(messages):
                        content = self.get_mail_content(index)
                        return content
                    else:
                        return {"error": f"유효하지 않은 메일 번호: {index + 1}번 (총 {len(messages)}개 메일)"}
                else:
                    return {"error": "index가 필요합니다."}
            
            elif function_name == "check_email_phishing":
                index = arguments.get("index")
                if index is not None:
                    from phishing_checker import check_email_phishing
                    result = check_email_phishing(index)
                    return result
                else:
                    return {"error": "index가 필요합니다."}
            
            else:
                return {"error": f"알 수 없는 함수: {function_name}"}
        
        except Exception as e:
            return {"error": f"함수 실행 중 오류: {str(e)}"}
    
    def delete_mails_by_indices(self, indices):
        """번호(인덱스) 리스트로 여러 메일을 휴지통으로 이동"""
        # 디버깅: 삭제 함수 호출 로그
        print(f"🗑️ delete_mails_by_indices called with indices: {indices}")
        
        results = []
        messages = st.session_state.gmail_messages
        
        for idx in indices:
            if 0 <= idx < len(messages):
                msg_id = messages[idx]['id']
                print(f"🗑️ Attempting to delete mail {idx+1} with ID: {msg_id}")
                result = gmail_service.move_to_trash(msg_id)
                print(f"🗑️ Delete result for mail {idx+1}: {result}")
                results.append({"index": idx, "success": result})
            else:
                results.append({"index": idx, "success": False, "error": "존재하지 않는 번호"})
        return results
    
    def get_mail_content(self, index):
        """번호(인덱스)로 메일의 제목/내용을 반환"""
        messages = st.session_state.gmail_messages
        if 0 <= index < len(messages):
            msg = messages[index]
            return {
                "subject": msg["subject"],
                "sender": msg["sender"],
                "snippet": msg["snippet"]
            }
        else:
            return {
                "error": f"{index+1}번 메일이 존재하지 않습니다."
            }

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