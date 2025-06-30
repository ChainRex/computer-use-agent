from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class MessageType(str, Enum):
    ANALYZE_TASK = "analyze_task"
    ANALYSIS_RESULT = "analysis_result"
    ERROR = "error"

class TaskAnalysisRequest(BaseModel):
    """客户端发送给服务端的任务分析请求"""
    text_command: str
    screenshot_base64: str
    user_id: str = "default"

class ActionPlan(BaseModel):
    """执行计划中的单个动作"""
    type: str  # click, type, key, wait
    description: str
    element_id: Optional[str] = None
    coordinates: Optional[List[int]] = None
    text: Optional[str] = None
    duration: Optional[float] = None

class TaskAnalysisResponse(BaseModel):
    """服务端返回给客户端的分析结果"""
    task_id: str
    success: bool
    reasoning: Optional[str] = None
    actions: Optional[List[ActionPlan]] = None
    expected_outcome: Optional[str] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None