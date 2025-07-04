"""
agent_analysis 메서드 테스트 스크립트
"""

import streamlit as st
import os
from dotenv import load_dotenv
from openai_service_clean import openai_service

# 환경변수 로드
load_dotenv()

def test_agent_analysis():
    """agent_analysis 메서드 테스트"""
    
    print("🤖 agent_analysis 테스트 시작...")
    
    # 1. API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY가 설정되지 않았습니다!")
        return
    
    print("✅ API 키 확인됨")
    
    # 2. Gmail 메일 목록 확인 (세션 상태 시뮬레이션)
    test_messages = [
        {
            "id": "test_1",
            "subject": "긴급: 계정 보안 확인 필요",
            "sender": "security@fakebank.com",
            "snippet": "귀하의 계정이 해킹되었습니다. 즉시 확인해주세요."
        },
        {
            "id": "test_2", 
            "subject": "회의 일정 안내",
            "sender": "meeting@company.com",
            "snippet": "내일 오후 2시에 팀 회의가 있습니다."
        }
    ]
    
    # 세션 상태에 테스트 메일 설정
    st.session_state['gmail_messages'] = test_messages
    print(f"📧 테스트 메일 {len(test_messages)}개 설정됨")
    
    # 3. agent_analysis 실행
    try:
        print("🔍 1번 메일 에이전트 분석 시작...")
        result = openai_service.agent_analysis(0)  # 1번 메일 (인덱스 0)
        
        print("🎉 분석 완료!")
        print("📝 결과:")
        print(result)
        
    except Exception as e:
        print(f"💥 오류 발생: {str(e)}")

def test_web_search_only():
    """웹서치만 테스트"""
    
    print("🌐 웹서치만 테스트...")
    
    # 테스트 메일 설정
    test_messages = [
        {
            "id": "test_1",
            "subject": "긴급: 계정 보안 확인 필요",
            "sender": "security@fakebank.com", 
            "snippet": "귀하의 계정이 해킹되었습니다. 즉시 확인해주세요."
        }
    ]
    
    st.session_state['gmail_messages'] = test_messages
    
    try:
        result = openai_service.web_search_analysis(0)
        print("✅ 웹서치 분석 완료!")
        print("📝 결과:")
        print(result)
        
    except Exception as e:
        print(f"💥 웹서치 오류: {str(e)}")

if __name__ == "__main__":
    print("🚀 DeepMail Agent 테스트")
    print("=" * 50)
    
    # 웹서치만 테스트
    test_web_search_only()
    
    print("\n" + "=" * 50)
    
    # 전체 에이전트 테스트
    test_agent_analysis() 