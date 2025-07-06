"""
DeepMail - 멀티 에이전트 시스템
에이전트 간 위임과 협업을 위한 고급 아키텍처
"""

import streamlit as st
import json
import asyncio
from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentType(Enum):
    """에이전트 타입 정의"""
    COORDINATOR = "coordinator"      # 작업 조율 에이전트
    CLASSIFIER = "classifier"        # 분류 에이전트
    PREDICTOR = "predictor"          # 예측 에이전트
    SEARCHER = "searcher"           # 검색 에이전트
    ANALYZER = "analyzer"           # 분석 에이전트
    EXECUTOR = "executor"           # 실행 에이전트

@dataclass
class AgentTask:
    """에이전트 작업 정의"""
    task_id: str
    task_type: str
    description: str
    parameters: Dict[str, Any]
    priority: int = 1
    dependencies: List[str] = None
    result: Any = None
    status: str = "pending"  # pending, running, completed, failed

class BaseAgent(ABC):
    """기본 에이전트 클래스"""
    
    def __init__(self, agent_id: str, agent_type: AgentType):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities = []
        self.is_available = True
        self.current_task = None
        self.task_history = []
        
    @abstractmethod
    def can_handle(self, task: AgentTask) -> bool:
        """작업 처리 가능 여부 확인"""
        pass
    
    @abstractmethod
    async def execute_task(self, task: AgentTask) -> Any:
        """작업 실행"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """에이전트 상태 반환"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "is_available": self.is_available,
            "current_task": self.current_task.task_id if self.current_task else None,
            "capabilities": self.capabilities
        }

class CoordinatorAgent(BaseAgent):
    """작업 조율 에이전트 - 다른 에이전트들을 관리하고 작업을 분배"""
    
    def __init__(self):
        super().__init__("coordinator_001", AgentType.COORDINATOR)
        self.capabilities = ["task_delegation", "workflow_management", "agent_coordination"]
        self.registered_agents = {}
        self.workflow_templates = {}
        
    def can_handle(self, task: AgentTask) -> bool:
        return task.task_type in ["delegate", "coordinate", "workflow"]
    
    def register_agent(self, agent: BaseAgent):
        """에이전트 등록"""
        self.registered_agents[agent.agent_id] = agent
        logger.info(f"에이전트 등록: {agent.agent_id} ({agent.agent_type.value})")
    
    def find_best_agent(self, task: AgentTask) -> Optional[BaseAgent]:
        """작업에 가장 적합한 에이전트 찾기"""
        available_agents = [
            agent for agent in self.registered_agents.values()
            if agent.is_available and agent.can_handle(task)
        ]
        
        if not available_agents:
            return None
            
        # 우선순위와 능력에 따라 최적 에이전트 선택
        best_agent = max(available_agents, key=lambda a: len(a.capabilities))
        return best_agent
    
    async def execute_task(self, task: AgentTask) -> Any:
        """작업 실행 - 다른 에이전트에게 위임"""
        self.current_task = task
        
        if task.task_type == "delegate":
            # 단일 작업 위임
            target_agent = self.find_best_agent(task)
            if target_agent:
                logger.info(f"작업 위임: {task.task_id} -> {target_agent.agent_id}")
                result = await target_agent.execute_task(task)
                task.result = result
                task.status = "completed"
                return result
            else:
                task.status = "failed"
                return {"error": "적절한 에이전트를 찾을 수 없습니다."}
        
        elif task.task_type == "workflow":
            # 워크플로우 실행
            return await self.execute_workflow(task)
        
        self.current_task = None
        return {"error": "지원하지 않는 작업 타입입니다."}
    
    async def execute_workflow(self, task: AgentTask) -> Any:
        """복잡한 워크플로우 실행"""
        workflow_steps = task.parameters.get("steps", [])
        results = []
        
        for step in workflow_steps:
            step_task = AgentTask(
                task_id=f"{task.task_id}_step_{len(results)}",
                task_type=step["type"],
                description=step["description"],
                parameters=step["parameters"]
            )
            
            # 단계별 에이전트 위임
            target_agent = self.find_best_agent(step_task)
            if target_agent:
                step_result = await target_agent.execute_task(step_task)
                results.append(step_result)
            else:
                results.append({"error": f"단계 {len(results)} 처리 실패"})
        
        return {"workflow_results": results}

class ClassifierAgent(BaseAgent):
    """분류 에이전트 - 메일 분류 및 우선순위 결정"""
    
    def __init__(self):
        super().__init__("classifier_001", AgentType.CLASSIFIER)
        self.capabilities = ["email_classification", "priority_assessment", "category_detection"]
        
    def can_handle(self, task: AgentTask) -> bool:
        return task.task_type in ["classify", "categorize", "assess_priority"]
    
    async def execute_task(self, task: AgentTask) -> Any:
        self.current_task = task
        
        if task.task_type == "classify":
            return await self.classify_email(task.parameters)
        elif task.task_type == "assess_priority":
            return await self.assess_priority(task.parameters)
        
        self.current_task = None
        return {"error": "지원하지 않는 작업입니다."}
    
    async def classify_email(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """메일 분류"""
        email_content = parameters.get("content", "")
        subject = parameters.get("subject", "")
        
        # 간단한 키워드 기반 분류 (실제로는 ML 모델 사용)
        categories = {
            "urgent": ["urgent", "긴급", "immediate", "asap"],
            "spam": ["spam", "광고", "promotion", "sale"],
            "important": ["important", "중요", "notice", "announcement"],
            "personal": ["personal", "개인", "family", "friend"]
        }
        
        detected_categories = []
        for category, keywords in categories.items():
            if any(keyword.lower() in (subject + email_content).lower() for keyword in keywords):
                detected_categories.append(category)
        
        return {
            "categories": detected_categories,
            "confidence": 0.8,
            "recommended_actions": self.get_recommended_actions(detected_categories)
        }
    
    async def assess_priority(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """우선순위 평가"""
        classification = parameters.get("classification", {})
        categories = classification.get("categories", [])
        
        priority_scores = {
            "urgent": 10,
            "important": 8,
            "personal": 6,
            "spam": 2
        }
        
        max_priority = max([priority_scores.get(cat, 5) for cat in categories], default=5)
        
        return {
            "priority_score": max_priority,
            "priority_level": self.get_priority_level(max_priority),
            "processing_order": max_priority
        }
    
    def get_recommended_actions(self, categories: List[str]) -> List[str]:
        """추천 액션 생성"""
        action_map = {
            "urgent": ["immediate_review", "notify_user"],
            "spam": ["mark_as_spam", "delete"],
            "important": ["flag", "schedule_review"],
            "personal": ["normal_processing"]
        }
        
        actions = []
        for category in categories:
            actions.extend(action_map.get(category, []))
        
        return list(set(actions))  # 중복 제거
    
    def get_priority_level(self, score: int) -> str:
        """우선순위 레벨 반환"""
        if score >= 9:
            return "critical"
        elif score >= 7:
            return "high"
        elif score >= 5:
            return "medium"
        else:
            return "low"

class PredictorAgent(BaseAgent):
    """예측 에이전트 - 피싱, 스팸 등 예측 작업"""
    
    def __init__(self):
        super().__init__("predictor_001", AgentType.PREDICTOR)
        self.capabilities = ["phishing_detection", "spam_prediction", "risk_assessment"]
        
    def can_handle(self, task: AgentTask) -> bool:
        return task.task_type in ["predict", "detect", "assess_risk"]
    
    async def execute_task(self, task: AgentTask) -> Any:
        self.current_task = task
        
        if task.task_type == "predict":
            prediction_type = task.parameters.get("prediction_type", "phishing")
            if prediction_type == "phishing":
                return await self.predict_phishing(task.parameters)
            elif prediction_type == "spam":
                return await self.predict_spam(task.parameters)
        
        self.current_task = None
        return {"error": "지원하지 않는 예측 타입입니다."}
    
    async def predict_phishing(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """피싱 예측"""
        # 실제로는 ML 모델을 호출
        from openai_service_clean import openai_service
        
        email_index = parameters.get("email_index")
        if email_index is not None:
            result = openai_service.check_email_phishing(email_index)
            return {
                "prediction_type": "phishing",
                "result": result,
                "confidence": result.get("probability", 0.5),
                "recommendation": self.get_phishing_recommendation(result)
            }
        
        return {"error": "이메일 인덱스가 필요합니다."}
    
    async def predict_spam(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """스팸 예측"""
        email_content = parameters.get("content", "")
        
        # 간단한 스팸 키워드 기반 예측
        spam_keywords = ["buy now", "limited time", "act now", "free money", "lottery", "winner"]
        spam_score = sum(1 for keyword in spam_keywords if keyword.lower() in email_content.lower())
        
        is_spam = spam_score > 2
        confidence = min(spam_score / 3, 1.0)
        
        return {
            "prediction_type": "spam",
            "is_spam": is_spam,
            "confidence": confidence,
            "spam_score": spam_score
        }
    
    def get_phishing_recommendation(self, result: Dict[str, Any]) -> str:
        """피싱 결과에 따른 권장사항"""
        if result.get("result") == "phishing":
            return "delete_immediately"
        elif result.get("probability", 0) > 0.7:
            return "review_carefully"
        else:
            return "safe_to_process"

class SearcherAgent(BaseAgent):
    """검색 에이전트 - 메일 검색 및 정보 수집"""
    
    def __init__(self):
        super().__init__("searcher_001", AgentType.SEARCHER)
        self.capabilities = ["email_search", "web_search", "information_gathering"]
        
    def can_handle(self, task: AgentTask) -> bool:
        return task.task_type in ["search", "gather_info", "web_search"]
    
    async def execute_task(self, task: AgentTask) -> Any:
        self.current_task = task
        
        if task.task_type == "search":
            return await self.search_emails(task.parameters)
        elif task.task_type == "web_search":
            return await self.web_search(task.parameters)
        
        self.current_task = None
        return {"error": "지원하지 않는 검색 타입입니다."}
    
    async def search_emails(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """메일 검색"""
        from openai_service_clean import openai_service
        
        query = parameters.get("query", "")
        max_results = parameters.get("max_results", 10)
        
        if query:
            results = openai_service.search_mails(query, max_results)
            return {
                "search_type": "email",
                "query": query,
                "results": results,
                "total_found": len(results)
            }
        
        return {"error": "검색어가 필요합니다."}
    
    async def web_search(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """웹 검색"""
        from openai_service_clean import openai_service
        
        search_query = parameters.get("search_query", "")
        email_index = parameters.get("email_index")
        
        if email_index is not None:
            result = openai_service.web_search_mail_content(email_index, search_query)
            return {
                "search_type": "web",
                "query": search_query,
                "email_index": email_index,
                "analysis": result
            }
        
        return {"error": "이메일 인덱스가 필요합니다."}

class AnalyzerAgent(BaseAgent):
    """분석 에이전트 - 통계 및 패턴 분석"""
    
    def __init__(self):
        super().__init__("analyzer_001", AgentType.ANALYZER)
        self.capabilities = ["statistical_analysis", "pattern_recognition", "trend_analysis"]
        
    def can_handle(self, task: AgentTask) -> bool:
        return task.task_type in ["analyze", "statistics", "pattern_analysis"]
    
    async def execute_task(self, task: AgentTask) -> Any:
        self.current_task = task
        
        if task.task_type == "analyze":
            analysis_type = task.parameters.get("analysis_type", "statistics")
            if analysis_type == "statistics":
                return await self.analyze_statistics(task.parameters)
            elif analysis_type == "patterns":
                return await self.analyze_patterns(task.parameters)
        
        self.current_task = None
        return {"error": "지원하지 않는 분석 타입입니다."}
    
    async def analyze_statistics(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """통계 분석"""
        from openai_service_clean import openai_service
        
        max_mails = parameters.get("max_mails", 100)
        result = openai_service.get_mail_statistics(max_mails)
        
        return {
            "analysis_type": "statistics",
            "result": result,
            "insights": self.extract_insights(result)
        }
    
    async def analyze_patterns(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """패턴 분석"""
        from openai_service_clean import openai_service
        
        messages = openai_service.get_gmail_messages()
        if not messages:
            return {"error": "분석할 메일이 없습니다."}
        
        # 발신자 패턴 분석
        sender_patterns = {}
        for msg in messages:
            sender = msg.get('sender', 'Unknown')
            sender_patterns[sender] = sender_patterns.get(sender, 0) + 1
        
        # 시간대 패턴 분석 (간단한 예시)
        time_patterns = {
            "morning": 0,
            "afternoon": 0,
            "evening": 0
        }
        
        return {
            "analysis_type": "patterns",
            "sender_patterns": dict(sorted(sender_patterns.items(), key=lambda x: x[1], reverse=True)[:10]),
            "time_patterns": time_patterns,
            "total_analyzed": len(messages)
        }
    
    def extract_insights(self, statistics: Dict[str, Any]) -> List[str]:
        """통계에서 인사이트 추출"""
        insights = []
        
        if "sender_stats" in statistics:
            top_senders = statistics["sender_stats"].get("top_senders", [])
            if top_senders:
                insights.append(f"가장 많은 메일을 보낸 발신자: {top_senders[0][0]}")
        
        if "keyword_stats" in statistics:
            top_keywords = statistics["keyword_stats"].get("top_keywords", [])
            if top_keywords:
                insights.append(f"가장 많이 언급된 키워드: {top_keywords[0][0]}")
        
        return insights

class ExecutorAgent(BaseAgent):
    """실행 에이전트 - 실제 작업 수행"""
    
    def __init__(self):
        super().__init__("executor_001", AgentType.EXECUTOR)
        self.capabilities = ["delete_emails", "move_emails", "batch_operations"]
        
    def can_handle(self, task: AgentTask) -> bool:
        return task.task_type in ["execute", "delete", "move", "batch_operation"]
    
    async def execute_task(self, task: AgentTask) -> Any:
        self.current_task = task
        
        if task.task_type == "delete":
            return await self.delete_emails(task.parameters)
        elif task.task_type == "batch_operation":
            return await self.batch_operation(task.parameters)
        
        self.current_task = None
        return {"error": "지원하지 않는 실행 타입입니다."}
    
    async def delete_emails(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """메일 삭제"""
        from openai_service_clean import openai_service
        
        indices = parameters.get("indices", [])
        if indices:
            results = openai_service.delete_mails_by_indices(indices)
            success_count = sum(1 for r in results if r.get("success", False))
            
            return {
                "operation_type": "delete",
                "requested_count": len(indices),
                "success_count": success_count,
                "results": results
            }
        
        return {"error": "삭제할 메일 인덱스가 필요합니다."}
    
    async def batch_operation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """일괄 작업"""
        from openai_service_clean import openai_service
        
        operation_type = parameters.get("operation_type", "phishing_delete")
        
        if operation_type == "phishing_delete":
            max_mails = parameters.get("max_mails", 50)
            threshold = parameters.get("threshold", 0.7)
            result = openai_service.batch_check_phishing_and_delete(max_mails, threshold)
            return {
                "operation_type": "batch_phishing_delete",
                "result": result
            }
        
        return {"error": "지원하지 않는 일괄 작업 타입입니다."}

class MultiAgentSystem:
    """멀티 에이전트 시스템 관리자"""
    
    def __init__(self):
        self.coordinator = CoordinatorAgent()
        self.agents = {}
        self.initialize_agents()
        
    def initialize_agents(self):
        """에이전트 초기화 및 등록"""
        # 각 에이전트 생성
        self.agents["classifier"] = ClassifierAgent()
        self.agents["predictor"] = PredictorAgent()
        self.agents["searcher"] = SearcherAgent()
        self.agents["analyzer"] = AnalyzerAgent()
        self.agents["executor"] = ExecutorAgent()
        
        # 코디네이터에 등록
        for agent in self.agents.values():
            self.coordinator.register_agent(agent)
        
        logger.info("멀티 에이전트 시스템 초기화 완료")
    
    async def process_user_request(self, user_input: str) -> Dict[str, Any]:
        """사용자 요청 처리"""
        # 1단계: 요청 분석 및 분류
        classification_task = AgentTask(
            task_id="classify_request",
            task_type="classify",
            description="사용자 요청 분류",
            parameters={"content": user_input}
        )
        
        classification_result = await self.coordinator.execute_task(classification_task)
        
        # 2단계: 요청에 따른 워크플로우 생성
        workflow = self.create_workflow(user_input, classification_result)
        
        # 3단계: 워크플로우 실행
        workflow_task = AgentTask(
            task_id="execute_workflow",
            task_type="workflow",
            description="사용자 요청 워크플로우 실행",
            parameters={"steps": workflow}
        )
        
        result = await self.coordinator.execute_task(workflow_task)
        
        return {
            "user_input": user_input,
            "classification": classification_result,
            "workflow_result": result
        }
    
    def create_workflow(self, user_input: str, classification: Dict[str, Any]) -> List[Dict[str, Any]]:
        """사용자 요청에 따른 워크플로우 생성 (개선된 버전)"""
        workflow = []
        
        # 복합 작업: 분석 + 피싱 검사 + 삭제
        if any(keyword in user_input for keyword in ["분석하고", "찾아서", "처리해줘", "정리해줘"]):
            if any(keyword in user_input for keyword in ["피싱", "phishing", "스팸", "spam"]):
                workflow = [
                    {
                        "type": "classify",
                        "description": "메일 분류 및 우선순위 평가",
                        "parameters": {"content": user_input}
                    },
                    {
                        "type": "batch_operation",
                        "description": "피싱 메일 일괄 검사 및 삭제",
                        "parameters": {
                            "operation_type": "phishing_delete",
                            "max_mails": 50,
                            "threshold": 0.7
                        }
                    }
                ]
        
        # 피싱 관련 요청
        elif "피싱" in user_input or "phishing" in user_input.lower():
            if "검사" in user_input or "check" in user_input.lower():
                email_index = self.extract_email_index(user_input)
                if email_index is not None:
                    workflow.append({
                        "type": "predict",
                        "description": "개별 메일 피싱 검사",
                        "parameters": {
                            "prediction_type": "phishing",
                            "email_index": email_index
                        }
                    })
                else:
                    workflow.append({
                        "type": "batch_operation",
                        "description": "일괄 피싱 검사",
                        "parameters": {
                            "operation_type": "phishing_delete",
                            "max_mails": 20,
                            "threshold": 0.7
                        }
                    })
            elif "삭제" in user_input or "delete" in user_input.lower():
                workflow.append({
                    "type": "batch_operation",
                    "description": "피싱 메일 일괄 삭제",
                    "parameters": {
                        "operation_type": "phishing_delete",
                        "max_mails": 50,
                        "threshold": 0.7
                    }
                })
        
        # 검색 관련 요청
        elif "검색" in user_input or "search" in user_input.lower():
            workflow.append({
                "type": "search",
                "description": "메일 검색",
                "parameters": {
                    "query": self.extract_search_query(user_input),
                    "max_results": 10
                }
            })
        
        # 통계 관련 요청
        elif "통계" in user_input or "statistics" in user_input.lower() or "인사이트" in user_input:
            workflow.append({
                "type": "analyze",
                "description": "메일 통계 분석",
                "parameters": {
                    "analysis_type": "statistics",
                    "max_mails": 100
                }
            })
        
        # 링크 분석 요청
        elif "링크" in user_input or "link" in user_input.lower():
            email_index = self.extract_email_index(user_input)
            if email_index is not None:
                workflow.append({
                    "type": "web_search",
                    "description": "링크 위험도 분석",
                    "parameters": {
                        "email_index": email_index,
                        "search_query": "링크 위험도"
                    }
                })
        
        # 기본 워크플로우 (분류 → 예측)
        if not workflow:
            workflow = [
                {
                    "type": "classify",
                    "description": "요청 분류 및 우선순위 평가",
                    "parameters": {"content": user_input}
                },
                {
                    "type": "predict",
                    "description": "위험도 예측",
                    "parameters": {"prediction_type": "phishing"}
                }
            ]
        
        return workflow
    
    def extract_email_index(self, user_input: str) -> Optional[int]:
        """사용자 입력에서 이메일 인덱스 추출"""
        import re
        match = re.search(r'(\d+)번', user_input)
        if match:
            return int(match.group(1)) - 1  # 0-based index
        return None
    
    def extract_search_query(self, user_input: str) -> str:
        """사용자 입력에서 검색어 추출"""
        # 간단한 추출 로직
        if "검색" in user_input:
            return user_input.replace("검색", "").strip()
        return user_input
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 반환"""
        return {
            "coordinator": self.coordinator.get_status(),
            "agents": {name: agent.get_status() for name, agent in self.agents.items()},
            "total_agents": len(self.agents)
        }

# 전역 멀티 에이전트 시스템 인스턴스
multi_agent_system = MultiAgentSystem() 