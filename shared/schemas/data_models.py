from pydantic import BaseModel
from typing import List, Optional, Union, Dict, Any
from enum import Enum

class MessageType(str, Enum):
    ANALYZE_TASK = "analyze_task"
    ANALYSIS_RESULT = "analysis_result"
    OMNIPARSER_RESULT = "omniparser_result"  # OmniParser中间结果
    CLAUDE_RESULT = "claude_result"  # Claude分析结果
    VERIFY_COMPLETION = "verify_completion"  # 简化的任务完成验证
    COMPLETION_RESULT = "completion_result"  # 验证结果
    ERROR = "error"

class OSInfo(BaseModel):
    """操作系统信息"""
    system: str  # Windows, macOS, Linux
    version: str
    release: str
    machine: str
    processor: str
    platform: str
    error: Optional[str] = None

class TaskAnalysisRequest(BaseModel):
    """客户端发送给服务端的任务分析请求"""
    text_command: str
    screenshot_base64: str
    user_id: str = "default"
    os_info: Optional[OSInfo] = None

class ActionType(str, Enum):
    """pyautogui操作类型枚举"""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    KEY = "key"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    DRAG = "drag"
    WAIT = "wait"
    MOVE = "move"

class ActionPlan(BaseModel):
    """执行计划中的单个动作 - 支持pyautogui所有操作类型"""
    type: Union[ActionType, str]  # 兼容字符串类型
    description: str
    element_id: Optional[str] = None
    
    # 坐标相关
    coordinates: Optional[List[Union[int, float]]] = None  # [x, y] 或 [x1, y1, x2, y2]
    
    # 文本输入相关
    text: Optional[str] = None
    
    # 时间相关
    duration: Optional[float] = None
    interval: Optional[float] = None  # 输入间隔
    
    # 滚动相关
    clicks: Optional[int] = None  # 滚动次数
    
    # 按键相关
    keys: Optional[List[str]] = None  # 组合键列表
    
    # 验证相关
    verify_element: Optional[str] = None  # 操作后验证的元素ID
    
    @property
    def click_position(self) -> Optional[tuple]:
        """获取点击位置（中心点）"""
        if not self.coordinates:
            return None
        if len(self.coordinates) == 2:
            return tuple(self.coordinates)
        elif len(self.coordinates) == 4:
            # 从bbox计算中心点
            x1, y1, x2, y2 = self.coordinates
            return (int((x1 + x2) / 2), int((y1 + y2) / 2))
        return None

class UIElement(BaseModel):
    """屏幕UI元素"""
    id: int
    type: str
    description: str
    coordinates: List[float]  # [x1, y1, x2, y2] 或 [x, y, width, height]
    text: str
    confidence: float

class OmniParserResult(BaseModel):
    """OmniParser分析结果（中间结果）"""
    task_id: str
    success: bool
    ui_elements: List[UIElement]
    annotated_screenshot_base64: Optional[str] = None
    processing_time: Optional[float] = None
    element_count: Optional[int] = None

class ClaudeAnalysisResult(BaseModel):
    """Claude分析结果"""
    task_id: str
    success: bool
    reasoning: str
    actions: List[ActionPlan]
    expected_outcome: Optional[str] = None
    confidence: float
    processing_time: Optional[float] = None
    error_message: Optional[str] = None

class TaskAnalysisResponse(BaseModel):
    """服务端返回给客户端的最终分析结果（保持兼容性）"""
    task_id: str
    success: bool
    reasoning: Optional[str] = None
    actions: Optional[List[ActionPlan]] = None
    expected_outcome: Optional[str] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    # OmniParser相关字段
    ui_elements: Optional[List[UIElement]] = None
    annotated_screenshot_base64: Optional[str] = None

class CompletionVerificationRequest(BaseModel):
    """简化的任务完成验证请求 - 只需要截图"""
    task_id: str
    screenshot_base64: str

class CompletionStatus(str, Enum):
    """任务完成状态"""
    COMPLETED = "completed"
    INCOMPLETE = "incomplete" 
    FAILED = "failed"
    UNCLEAR = "unclear"

class CompletionVerificationResponse(BaseModel):
    """任务完成验证响应"""
    task_id: str
    status: CompletionStatus
    reasoning: str
    confidence: float  # 0.0-1.0
    next_steps: Optional[str] = None  # 如果未完成，建议的下一步操作（文字描述）
    next_actions: Optional[List[ActionPlan]] = None  # 如果未完成，具体的操作指令
    verification_time: Optional[float] = None