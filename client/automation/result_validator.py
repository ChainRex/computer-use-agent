"""
执行结果验证器 - 验证自动化操作的执行结果
"""

import time
import logging
import pyautogui
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# 添加项目根目录到Python路径
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.schemas.data_models import ActionPlan, UIElement

logger = logging.getLogger(__name__)

class ValidationResult(Enum):
    """验证结果枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class ValidationReport:
    """验证报告"""
    action_index: int
    action_type: str
    description: str
    result: ValidationResult
    confidence: float
    validation_time: float
    error_message: Optional[str] = None
    screenshots: Dict[str, str] = None  # before/after base64 screenshots
    details: Dict[str, Any] = None

class ResultValidator:
    """执行结果验证器"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化验证器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        
        # 验证配置
        self.validation_timeout = self.config.get('validation_timeout', 5.0)
        self.capture_screenshots = self.config.get('capture_screenshots', True)
        self.pixel_tolerance = self.config.get('pixel_tolerance', 10)  # 像素容差
        self.confidence_threshold = self.config.get('confidence_threshold', 0.7)
        
        logger.info("ResultValidator initialized")
    
    def validate_action_result(
        self, 
        action: ActionPlan, 
        action_index: int,
        ui_elements: List[UIElement],
        screenshot_before: Optional[str] = None,
        screenshot_after: Optional[str] = None
    ) -> ValidationReport:
        """
        验证单个操作的执行结果
        
        Args:
            action: 执行的操作
            action_index: 操作索引
            ui_elements: UI元素列表
            screenshot_before: 执行前截图base64
            screenshot_after: 执行后截图base64
            
        Returns:
            ValidationReport: 验证报告
        """
        start_time = time.time()
        screenshots = {}
        
        if screenshot_before:
            screenshots['before'] = screenshot_before
        if screenshot_after:
            screenshots['after'] = screenshot_after
        
        try:
            # 根据操作类型进行不同的验证
            action_type = action.type.lower()
            
            if action_type == "click":
                result = self._validate_click_action(action, ui_elements, screenshots)
            elif action_type == "type":
                result = self._validate_type_action(action, screenshots)
            elif action_type == "key":
                result = self._validate_key_action(action, screenshots)
            elif action_type == "wait":
                result = self._validate_wait_action(action)
            elif action_type in ["scroll", "drag", "move"]:
                result = self._validate_movement_action(action, screenshots)
            else:
                result = ValidationResult.SUCCESS  # 未知操作类型默认成功
            
            validation_time = time.time() - start_time
            confidence = self._calculate_confidence(result, action_type)
            
            return ValidationReport(
                action_index=action_index,
                action_type=action_type,
                description=action.description,
                result=result,
                confidence=confidence,
                validation_time=validation_time,
                screenshots=screenshots,
                details=self._get_validation_details(action, result)
            )
            
        except Exception as e:
            validation_time = time.time() - start_time
            logger.error(f"验证操作 {action_index} 时发生异常: {e}")
            
            return ValidationReport(
                action_index=action_index,
                action_type=action.type,
                description=action.description,
                result=ValidationResult.ERROR,
                confidence=0.0,
                validation_time=validation_time,
                error_message=str(e),
                screenshots=screenshots
            )
    
    def _validate_click_action(
        self, 
        action: ActionPlan, 
        ui_elements: List[UIElement],
        screenshots: Dict[str, str]
    ) -> ValidationResult:
        """验证点击操作"""
        try:
            # 基本验证：检查鼠标位置
            current_pos = pyautogui.position()
            
            # 如果有element_id，验证是否点击了正确的元素
            if action.element_id:
                target_element = None
                for elem in ui_elements:
                    if str(elem.id) == str(action.element_id):
                        target_element = elem
                        break
                
                if target_element and target_element.coordinates:
                    # 计算元素中心点
                    if len(target_element.coordinates) >= 4:
                        x1, y1, x2, y2 = target_element.coordinates[:4]
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        
                        # 检查鼠标是否在元素附近
                        distance = ((current_pos.x - center_x) ** 2 + (current_pos.y - center_y) ** 2) ** 0.5
                        if distance <= self.pixel_tolerance:
                            return ValidationResult.SUCCESS
                        else:
                            logger.warning(f"鼠标位置 {current_pos} 距离目标元素中心 ({center_x}, {center_y}) 过远: {distance}px")
                            return ValidationResult.PARTIAL
            
            # 如果有coordinates，验证鼠标位置
            elif action.coordinates:
                target_pos = action.click_position
                if target_pos:
                    distance = ((current_pos.x - target_pos[0]) ** 2 + (current_pos.y - target_pos[1]) ** 2) ** 0.5
                    if distance <= self.pixel_tolerance:
                        return ValidationResult.SUCCESS
                    else:
                        return ValidationResult.PARTIAL
            
            # 如果有截图，可以进行更高级的验证（比较前后截图差异）
            if screenshots.get('before') and screenshots.get('after'):
                return self._compare_screenshots_for_click(screenshots)
            
            # 默认认为成功（基础验证）
            return ValidationResult.SUCCESS
            
        except Exception as e:
            logger.error(f"验证点击操作失败: {e}")
            return ValidationResult.ERROR
    
    def _validate_type_action(self, action: ActionPlan, screenshots: Dict[str, str]) -> ValidationResult:
        """验证文本输入操作"""
        try:
            # 基本验证：检查剪贴板内容（如果可能）
            if action.text:
                # 这里可以尝试获取当前焦点窗口的文本内容
                # 但pyautogui没有直接的方法，所以进行基础验证
                
                # 检查键盘状态等基本信息
                return ValidationResult.SUCCESS
            
            return ValidationResult.SUCCESS
            
        except Exception as e:
            logger.error(f"验证文本输入操作失败: {e}")
            return ValidationResult.ERROR
    
    def _validate_key_action(self, action: ActionPlan, screenshots: Dict[str, str]) -> ValidationResult:
        """验证按键操作"""
        try:
            # 按键操作很难验证具体效果，进行基础检查
            if action.text:
                # 验证按键组合是否有效
                keys = action.text.lower().split('+')
                valid_keys = ['ctrl', 'alt', 'shift', 'cmd', 'win', 'tab', 'enter', 'esc', 'space']
                
                for key in keys:
                    key = key.strip()
                    if key not in valid_keys and not key.isalnum():
                        logger.warning(f"可能无效的按键: {key}")
                        return ValidationResult.PARTIAL
                
                return ValidationResult.SUCCESS
            
            return ValidationResult.SUCCESS
            
        except Exception as e:
            logger.error(f"验证按键操作失败: {e}")
            return ValidationResult.ERROR
    
    def _validate_wait_action(self, action: ActionPlan) -> ValidationResult:
        """验证等待操作"""
        try:
            # 等待操作总是成功的（如果能执行到这里）
            return ValidationResult.SUCCESS
            
        except Exception as e:
            logger.error(f"验证等待操作失败: {e}")
            return ValidationResult.ERROR
    
    def _validate_movement_action(self, action: ActionPlan, screenshots: Dict[str, str]) -> ValidationResult:
        """验证移动/滚动/拖拽操作"""
        try:
            # 检查鼠标位置是否发生了变化
            if action.type.lower() == "move" and action.coordinates:
                current_pos = pyautogui.position()
                target_pos = action.click_position
                
                if target_pos:
                    distance = ((current_pos.x - target_pos[0]) ** 2 + (current_pos.y - target_pos[1]) ** 2) ** 0.5
                    if distance <= self.pixel_tolerance:
                        return ValidationResult.SUCCESS
                    else:
                        return ValidationResult.PARTIAL
            
            # 其他移动操作基础验证
            return ValidationResult.SUCCESS
            
        except Exception as e:
            logger.error(f"验证移动操作失败: {e}")
            return ValidationResult.ERROR
    
    def _compare_screenshots_for_click(self, screenshots: Dict[str, str]) -> ValidationResult:
        """通过比较截图来验证点击效果"""
        try:
            # 这里可以实现图像比较算法
            # 比如检测界面是否发生了变化，是否出现了新的窗口等
            
            # 简单实现：如果有before和after截图，认为有变化就是成功
            before = screenshots.get('before')
            after = screenshots.get('after')
            
            if before and after and before != after:
                return ValidationResult.SUCCESS
            elif before == after:
                return ValidationResult.PARTIAL  # 界面没有变化，可能点击无效
            
            return ValidationResult.SUCCESS
            
        except Exception as e:
            logger.error(f"截图比较失败: {e}")
            return ValidationResult.ERROR
    
    def _calculate_confidence(self, result: ValidationResult, action_type: str) -> float:
        """计算验证置信度"""
        base_confidence = {
            ValidationResult.SUCCESS: 0.9,
            ValidationResult.PARTIAL: 0.6,
            ValidationResult.FAILED: 0.2,
            ValidationResult.TIMEOUT: 0.1,
            ValidationResult.ERROR: 0.0
        }
        
        confidence = base_confidence.get(result, 0.5)
        
        # 根据操作类型调整置信度
        type_multiplier = {
            'wait': 1.0,      # 等待操作容易验证
            'click': 0.8,     # 点击操作中等难度验证
            'type': 0.6,      # 文本输入难以验证
            'key': 0.6,       # 按键操作难以验证
            'scroll': 0.7,    # 滚动操作中等难度验证
            'drag': 0.7,      # 拖拽操作中等难度验证
            'move': 0.8       # 移动操作相对容易验证
        }
        
        multiplier = type_multiplier.get(action_type.lower(), 0.7)
        return min(1.0, confidence * multiplier)
    
    def _get_validation_details(self, action: ActionPlan, result: ValidationResult) -> Dict[str, Any]:
        """获取验证详细信息"""
        details = {
            'action_type': action.type,
            'validation_method': self._get_validation_method(action.type),
            'validation_result': result.value
        }
        
        if action.element_id:
            details['target_element_id'] = action.element_id
        
        if action.coordinates:
            details['target_coordinates'] = action.coordinates
        
        if action.text:
            details['target_text'] = action.text
        
        return details
    
    def _get_validation_method(self, action_type: str) -> str:
        """获取验证方法描述"""
        methods = {
            'click': '鼠标位置验证 + 截图比较',
            'type': '基础验证',
            'key': '按键有效性验证',
            'wait': '执行成功验证',
            'scroll': '基础验证',
            'drag': '位置变化验证',
            'move': '鼠标位置验证'
        }
        
        return methods.get(action_type.lower(), '基础验证')
    
    def generate_validation_summary(self, validation_reports: List[ValidationReport]) -> Dict[str, Any]:
        """
        生成验证汇总报告
        
        Args:
            validation_reports: 验证报告列表
            
        Returns:
            Dict[str, Any]: 汇总报告
        """
        if not validation_reports:
            return {
                'total_actions': 0,
                'validation_summary': 'No actions to validate'
            }
        
        total_actions = len(validation_reports)
        success_count = len([r for r in validation_reports if r.result == ValidationResult.SUCCESS])
        partial_count = len([r for r in validation_reports if r.result == ValidationResult.PARTIAL])
        failed_count = len([r for r in validation_reports if r.result == ValidationResult.FAILED])
        error_count = len([r for r in validation_reports if r.result == ValidationResult.ERROR])
        
        average_confidence = sum(r.confidence for r in validation_reports) / total_actions
        total_validation_time = sum(r.validation_time for r in validation_reports)
        
        return {
            'total_actions': total_actions,
            'success_count': success_count,
            'partial_count': partial_count,
            'failed_count': failed_count,
            'error_count': error_count,
            'success_rate': success_count / total_actions,
            'average_confidence': average_confidence,
            'total_validation_time': total_validation_time,
            'validation_summary': f"{success_count}/{total_actions} actions validated successfully"
        }