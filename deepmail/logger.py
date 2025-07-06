"""
DeepMail - 로그 시스템
체계적인 로깅을 위한 모듈
"""

import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import traceback
import sys


class DeepMailLogger:
    """DeepMail 전용 로거 클래스"""
    
    def __init__(self, name: str = "DeepMail"):
        self.name = name
        self.logger = None
        self.log_dir = None
        self.setup_logger()
    
    def setup_logger(self):
        """로거 설정"""
        # 로그 디렉토리 설정
        self.log_dir = Path(__file__).parent.parent / "log"
        self.log_dir.mkdir(exist_ok=True)
        
        # 로거 생성
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        
        # 기존 핸들러 제거 (중복 방지)
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 파일 핸들러 (일반 로그)
        general_log_file = self.log_dir / "deepmail.log"
        file_handler = logging.FileHandler(general_log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 에러 로그 파일 핸들러
        error_log_file = self.log_dir / "error.log"
        error_handler = logging.FileHandler(error_log_file, mode='a', encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        
        # 디버그 로그 파일 핸들러
        debug_log_file = self.log_dir / "debug.log"
        debug_handler = logging.FileHandler(debug_log_file, mode='a', encoding='utf-8')
        debug_handler.setLevel(logging.DEBUG)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # 포맷터 설정
        detailed_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        simple_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        )
        
        # 핸들러에 포맷터 적용
        file_handler.setFormatter(detailed_formatter)
        error_handler.setFormatter(detailed_formatter)
        debug_handler.setFormatter(detailed_formatter)
        console_handler.setFormatter(simple_formatter)
        
        # 핸들러 추가
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(debug_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str, **kwargs):
        """정보 로그"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """경고 로그"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """에러 로그"""
        if exception:
            message += f"\nException: {str(exception)}\nTraceback: {traceback.format_exc()}"
        self.logger.error(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """디버그 로그"""
        self.logger.debug(message, extra=kwargs)
    
    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """치명적 오류 로그"""
        if exception:
            message += f"\nException: {str(exception)}\nTraceback: {traceback.format_exc()}"
        self.logger.critical(message, extra=kwargs)


class ActivityLogger:
    """사용자 활동 로그 클래스"""
    
    def __init__(self):
        self.log_dir = Path(__file__).parent.parent / "log"
        self.log_dir.mkdir(exist_ok=True)
        self.activity_log_file = self.log_dir / "activity.log"
    
    def log_user_action(self, action: str, details: Dict[str, Any], user_id: str = "anonymous"):
        """사용자 활동 로그"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "details": details
        }
        
        with open(self.activity_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_chat_interaction(self, user_input: str, ai_response: str, processing_time: float):
        """챗봇 상호작용 로그"""
        self.log_user_action(
            action="chat_interaction",
            details={
                "user_input": user_input,
                "ai_response": ai_response,
                "processing_time": processing_time
            }
        )
    
    def log_mail_operation(self, operation: str, mail_ids: list, success: bool):
        """메일 작업 로그"""
        self.log_user_action(
            action="mail_operation",
            details={
                "operation": operation,
                "mail_ids": mail_ids,
                "success": success
            }
        )
    
    def log_api_call(self, api_name: str, success: bool, response_time: float, error: str = None):
        """API 호출 로그"""
        self.log_user_action(
            action="api_call",
            details={
                "api_name": api_name,
                "success": success,
                "response_time": response_time,
                "error": error
            }
        )


class PerformanceLogger:
    """성능 모니터링 로그 클래스"""
    
    def __init__(self):
        self.log_dir = Path(__file__).parent.parent / "log"
        self.log_dir.mkdir(exist_ok=True)
        self.performance_log_file = self.log_dir / "performance.log"
    
    def log_performance(self, operation: str, duration: float, memory_usage: float = None):
        """성능 로그"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "duration": duration,
            "memory_usage": memory_usage
        }
        
        with open(self.performance_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')


class LogManager:
    """로그 관리자 클래스"""
    
    def __init__(self):
        self.logger = DeepMailLogger()
        self.activity_logger = ActivityLogger()
        self.performance_logger = PerformanceLogger()
        self.log_dir = Path(__file__).parent.parent / "log"
    
    def cleanup_old_logs(self, days: int = 30):
        """오래된 로그 파일 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for log_file in self.log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                try:
                    log_file.unlink()
                    self.logger.info(f"오래된 로그 파일 삭제: {log_file.name}")
                except Exception as e:
                    self.logger.error(f"로그 파일 삭제 실패: {log_file.name}", exception=e)
    
    def get_log_stats(self) -> Dict[str, Any]:
        """로그 통계 반환"""
        stats = {}
        
        for log_file in self.log_dir.glob("*.log"):
            try:
                file_size = log_file.stat().st_size
                stats[log_file.name] = {
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2)
                }
            except Exception as e:
                self.logger.error(f"로그 파일 통계 수집 실패: {log_file.name}", exception=e)
        
        return stats
    
    def export_logs(self, output_file: str, log_types: list = None):
        """로그 내보내기"""
        if log_types is None:
            log_types = ["deepmail.log", "error.log", "activity.log"]
        
        exported_data = {}
        
        for log_type in log_types:
            log_file = self.log_dir / log_type
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        exported_data[log_type] = f.read()
                except Exception as e:
                    self.logger.error(f"로그 내보내기 실패: {log_type}", exception=e)
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(exported_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"로그 내보내기 완료: {output_file}")
        except Exception as e:
            self.logger.error(f"로그 내보내기 실패: {output_file}", exception=e)


# 전역 로그 매니저 인스턴스
log_manager = LogManager()
logger = log_manager.logger
activity_logger = log_manager.activity_logger
performance_logger = log_manager.performance_logger


def log_function_call(func):
    """함수 호출 로깅 데코레이터"""
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"함수 실행 완료: {func.__name__}", duration=duration)
            performance_logger.log_performance(func.__name__, duration)
            return result
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"함수 실행 실패: {func.__name__}", exception=e)
            performance_logger.log_performance(func.__name__, duration)
            raise
    return wrapper


def log_api_call(api_name: str):
    """API 호출 로깅 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                activity_logger.log_api_call(api_name, True, duration)
                logger.info(f"API 호출 성공: {api_name}", duration=duration)
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                activity_logger.log_api_call(api_name, False, duration, str(e))
                logger.error(f"API 호출 실패: {api_name}", exception=e)
                raise
        return wrapper
    return decorator 