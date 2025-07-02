"""
PyAutoGUI自动化执行引擎 - 将AI生成的操作计划转换为实际的计算机操作
"""

import pyautogui
import time
import logging
import platform
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# 添加项目根目录到Python路径
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.schemas.data_models import ActionPlan, UIElement
from .result_validator import ResultValidator, ValidationResult

logger = logging.getLogger(__name__)

class ExecutionStatus(Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

@dataclass
class ExecutionResult:
    """单个操作的执行结果"""
    action_index: int
    action_type: str
    description: str
    status: ExecutionStatus
    execution_time: float
    error_message: Optional[str] = None
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None

@dataclass
class TaskExecutionResult:
    """整个任务的执行结果"""
    task_id: str
    total_actions: int
    completed_actions: int
    success_rate: float
    total_execution_time: float
    status: ExecutionStatus
    action_results: List[ExecutionResult]
    final_error: Optional[str] = None

class AutomationEngine:
    """PyAutoGUI自动化执行引擎"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化自动化引擎
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        
        # 安全设置
        pyautogui.FAILSAFE = self.config.get('failsafe', True)  # 启用安全模式
        pyautogui.PAUSE = self.config.get('pause_between_actions', 0.5)  # 操作间隔
        
        # 执行控制
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        
        # 截图功能
        self.capture_screenshots = self.config.get('capture_screenshots', True)
        
        # 操作系统特定设置
        self.os_name = platform.system()
        self._setup_os_specific()
        
        # UI元素映射
        self.ui_elements_map = {}
        
        # 初始化结果验证器
        validator_config = {
            'validation_timeout': self.config.get('validation_timeout', 5.0),
            'capture_screenshots': self.capture_screenshots,
            'pixel_tolerance': self.config.get('pixel_tolerance', 10),
            'confidence_threshold': self.config.get('confidence_threshold', 0.7)
        }
        self.validator = ResultValidator(validator_config)
        
        logger.info(f"AutomationEngine initialized for {self.os_name}")
    
    def _setup_os_specific(self):
        """设置操作系统特定的配置"""
        if self.os_name == "Darwin":  # macOS
            # macOS特定设置
            self.key_mappings = {
                'cmd': 'command',
                'ctrl': 'command',  # 在Mac上Ctrl通常映射为Command
                'alt': 'option',
                'win': 'command'
            }
        elif self.os_name == "Windows":
            # Windows特定设置
            self.key_mappings = {
                'cmd': 'win',
                'command': 'win',
                'alt': 'alt',
                'win': 'win'
            }
        else:  # Linux
            # Linux特定设置
            self.key_mappings = {
                'cmd': 'ctrl',
                'command': 'ctrl',
                'alt': 'alt',
                'win': 'super'
            }
    
    def set_ui_elements(self, ui_elements: List[UIElement]):
        """
        设置UI元素映射
        
        Args:
            ui_elements: UI元素列表
        """
        self.ui_elements_map = {str(elem.id): elem for elem in ui_elements}
        logger.info(f"Updated UI elements map with {len(ui_elements)} elements")
    
    def execute_action_plan(self, action_plan: List[ActionPlan], task_id: str = "unknown") -> TaskExecutionResult:
        """
        执行完整的操作计划
        
        Args:
            action_plan: 操作计划列表
            task_id: 任务ID
            
        Returns:
            TaskExecutionResult: 执行结果
        """
        start_time = time.time()
        self.is_running = True
        self.should_stop = False
        action_results = []
        
        logger.info(f"开始执行任务 {task_id}，共 {len(action_plan)} 个操作")
        
        try:
            for i, action in enumerate(action_plan):
                if self.should_stop:
                    logger.info("收到停止信号，中断执行")
                    break
                
                # 处理暂停
                while self.is_paused and not self.should_stop:
                    time.sleep(0.1)
                
                if self.should_stop:
                    break
                
                # 执行单个操作
                result = self._execute_single_action(action, i)
                action_results.append(result)
                
                # 如果操作失败且配置为严格模式，停止执行
                if result.status == ExecutionStatus.FAILED and self.config.get('strict_mode', False):
                    logger.error(f"操作 {i} 失败，严格模式下停止执行")
                    break
        
        except Exception as e:
            logger.error(f"执行过程中发生异常: {e}")
            final_error = str(e)
        else:
            final_error = None
        finally:
            self.is_running = False
        
        # 计算执行结果统计
        total_time = time.time() - start_time
        completed = len([r for r in action_results if r.status == ExecutionStatus.SUCCESS])
        success_rate = completed / len(action_plan) if action_plan else 0
        
        # 确定整体状态
        if self.should_stop:
            overall_status = ExecutionStatus.CANCELLED
        elif completed == len(action_plan):
            overall_status = ExecutionStatus.SUCCESS
        elif completed == 0:
            overall_status = ExecutionStatus.FAILED
        else:
            overall_status = ExecutionStatus.FAILED  # 部分成功也算失败
        
        result = TaskExecutionResult(
            task_id=task_id,
            total_actions=len(action_plan),
            completed_actions=completed,
            success_rate=success_rate,
            total_execution_time=total_time,
            status=overall_status,
            action_results=action_results,
            final_error=final_error
        )
        
        logger.info(f"任务 {task_id} 执行完成: {completed}/{len(action_plan)} 成功, 耗时 {total_time:.2f}s")
        return result
    
    def _execute_single_action(self, action: ActionPlan, action_index: int) -> ExecutionResult:
        """
        执行单个操作
        
        Args:
            action: 操作计划
            action_index: 操作索引
            
        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        screenshot_before = None
        screenshot_after = None
        
        logger.info(f"执行操作 {action_index}: {action.type} - {action.description}")
        
        try:
            # 执行前截图
            if self.capture_screenshots:
                screenshot_before = self._capture_screenshot()
            
            # 根据操作类型执行相应操作
            success = self._dispatch_action(action)
            
            # 执行后截图
            if self.capture_screenshots:
                time.sleep(0.5)  # 等待界面更新
                screenshot_after = self._capture_screenshot()
            
            execution_time = time.time() - start_time
            
            # 执行结果验证
            if success and self.config.get('enable_validation', True):
                try:
                    validation_report = self.validator.validate_action_result(
                        action, action_index, list(self.ui_elements_map.values()),
                        screenshot_before, screenshot_after
                    )
                    
                    # 根据验证结果调整执行状态
                    if validation_report.result == ValidationResult.SUCCESS:
                        status = ExecutionStatus.SUCCESS
                        error_message = None
                        logger.info(f"操作 {action_index} 执行并验证成功，置信度: {validation_report.confidence:.2f}")
                    elif validation_report.result == ValidationResult.PARTIAL:
                        status = ExecutionStatus.SUCCESS  # 部分成功仍算成功，但记录警告
                        error_message = f"部分成功 (置信度: {validation_report.confidence:.2f})"
                        logger.warning(f"操作 {action_index} 部分成功: {validation_report.error_message}")
                    else:
                        status = ExecutionStatus.FAILED
                        error_message = f"验证失败: {validation_report.error_message or '未知错误'}"
                        logger.error(f"操作 {action_index} 验证失败: {error_message}")
                        
                except Exception as e:
                    logger.warning(f"操作 {action_index} 验证过程出错: {e}")
                    # 验证失败不影响操作成功状态
                    status = ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED
                    error_message = f"验证异常: {str(e)}" if success else "操作执行失败"
            else:
                if success:
                    logger.info(f"操作 {action_index} 执行成功，耗时 {execution_time:.2f}s")
                    status = ExecutionStatus.SUCCESS
                    error_message = None
                else:
                    logger.warning(f"操作 {action_index} 执行失败")
                    status = ExecutionStatus.FAILED
                    error_message = "操作执行失败"
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"操作 {action_index} 发生异常: {e}")
            status = ExecutionStatus.FAILED
            error_message = str(e)
        
        return ExecutionResult(
            action_index=action_index,
            action_type=action.type,
            description=action.description,
            status=status,
            execution_time=execution_time,
            error_message=error_message,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after
        )
    
    def _dispatch_action(self, action: ActionPlan) -> bool:
        """
        分发操作到具体的执行方法
        
        Args:
            action: 操作计划
            
        Returns:
            bool: 执行是否成功
        """
        action_type = action.type.lower()
        
        try:
            if action_type == "click":
                return self._execute_click(action)
            elif action_type == "double_click":
                return self._execute_double_click(action)
            elif action_type == "right_click":
                return self._execute_right_click(action)
            elif action_type == "type":
                return self._execute_type(action)
            elif action_type == "key":
                return self._execute_key(action)
            elif action_type == "hotkey":
                return self._execute_hotkey(action)
            elif action_type == "scroll":
                return self._execute_scroll(action)
            elif action_type == "drag":
                return self._execute_drag(action)
            elif action_type == "wait":
                return self._execute_wait(action)
            elif action_type == "move":
                return self._execute_move(action)
            else:
                logger.warning(f"未知操作类型: {action_type}")
                return False
        except Exception as e:
            logger.error(f"执行 {action_type} 操作时发生异常: {e}")
            return False
    
    def _execute_click(self, action: ActionPlan) -> bool:
        """执行点击操作"""
        position = self._get_click_position(action)
        if position:
            pyautogui.click(position[0], position[1])
            return True
        return False
    
    def _execute_double_click(self, action: ActionPlan) -> bool:
        """执行双击操作"""
        position = self._get_click_position(action)
        if position:
            pyautogui.doubleClick(position[0], position[1])
            return True
        return False
    
    def _execute_right_click(self, action: ActionPlan) -> bool:
        """执行右键点击操作"""
        position = self._get_click_position(action)
        if position:
            pyautogui.rightClick(position[0], position[1])
            return True
        return False
    
    def _execute_type(self, action: ActionPlan) -> bool:
        """执行文本输入操作"""
        if action.text:
            interval = action.interval or 0.05
            pyautogui.typewrite(action.text, interval=interval)
            return True
        return False
    
    def _execute_key(self, action: ActionPlan) -> bool:
        """执行按键操作"""
        if action.text:
            # 处理组合键
            keys = action.text.lower().split('+')
            keys = [self.key_mappings.get(key.strip(), key.strip()) for key in keys]
            
            if len(keys) == 1:
                pyautogui.press(keys[0])
            else:
                # 优化组合键处理：按住第一个键，然后按其他键
                self._execute_sequential_hotkey(keys)
            return True
        return False
    
    def _execute_sequential_hotkey(self, keys: List[str]):
        """
        顺序执行组合键：先按住第一个键，然后依次按其他键
        
        Args:
            keys: 按键列表
        """
        if len(keys) < 2:
            return
        
        # 按住第一个键
        pyautogui.keyDown(keys[0])
        
        try:
            # 依次按下并释放其他键
            for key in keys[1:]:
                pyautogui.keyDown(key)
                pyautogui.keyUp(key)
                time.sleep(0.05)  # 小延迟确保按键注册
        finally:
            # 确保释放第一个键
            pyautogui.keyUp(keys[0])
    
    def _execute_hotkey(self, action: ActionPlan) -> bool:
        """执行热键操作"""
        if action.keys:
            mapped_keys = [self.key_mappings.get(key, key) for key in action.keys]
            # 使用顺序按键方式执行热键
            if len(mapped_keys) > 1:
                self._execute_sequential_hotkey(mapped_keys)
            else:
                pyautogui.press(mapped_keys[0])
            return True
        return False
    
    def _execute_scroll(self, action: ActionPlan) -> bool:
        """执行滚动操作"""
        position = self._get_click_position(action)
        clicks = action.clicks or 3
        
        if position:
            pyautogui.scroll(clicks, x=position[0], y=position[1])
        else:
            pyautogui.scroll(clicks)
        return True
    
    def _execute_drag(self, action: ActionPlan) -> bool:
        """执行拖拽操作"""
        if action.coordinates and len(action.coordinates) >= 4:
            x1, y1, x2, y2 = action.coordinates[:4]
            duration = action.duration or 1.0
            pyautogui.drag(x2 - x1, y2 - y1, x1, y1, duration=duration)
            return True
        return False
    
    def _execute_wait(self, action: ActionPlan) -> bool:
        """执行等待操作"""
        duration = action.duration or 1.0
        time.sleep(duration)
        return True
    
    def _execute_move(self, action: ActionPlan) -> bool:
        """执行鼠标移动操作"""
        position = self._get_click_position(action)
        if position:
            duration = action.duration or 1.0
            pyautogui.moveTo(position[0], position[1], duration=duration)
            return True
        return False
    
    def _get_click_position(self, action: ActionPlan) -> Optional[Tuple[int, int]]:
        """
        获取点击位置
        
        Args:
            action: 操作计划
            
        Returns:
            Optional[Tuple[int, int]]: 点击坐标 (x, y)
        """
        # 优先使用element_id
        if action.element_id and action.element_id in self.ui_elements_map:
            element = self.ui_elements_map[action.element_id]
            if element.coordinates and len(element.coordinates) >= 4:
                x1, y1, x2, y2 = element.coordinates
                # 计算中心点
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                logger.debug(f"使用元素 {action.element_id} 的中心点: ({center_x}, {center_y})")
                return (center_x, center_y)
        
        # 备用：使用直接坐标
        if action.coordinates:
            if len(action.coordinates) == 2:
                return (int(action.coordinates[0]), int(action.coordinates[1]))
            elif len(action.coordinates) == 4:
                x1, y1, x2, y2 = action.coordinates
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                return (center_x, center_y)
        
        logger.warning(f"无法确定操作位置: element_id={action.element_id}, coordinates={action.coordinates}")
        return None
    
    def _capture_screenshot(self) -> Optional[str]:
        """
        捕获屏幕截图并返回base64编码
        
        Returns:
            Optional[str]: base64编码的截图，失败时返回None
        """
        try:
            screenshot = pyautogui.screenshot()
            # 这里可以集成ScreenshotManager来处理base64转换
            # 暂时返回占位符
            return "screenshot_placeholder"
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None
    
    def pause_execution(self):
        """暂停执行"""
        self.is_paused = True
        logger.info("执行已暂停")
    
    def resume_execution(self):
        """恢复执行"""
        self.is_paused = False
        logger.info("执行已恢复")
    
    def stop_execution(self):
        """停止执行"""
        self.should_stop = True
        self.is_paused = False
        logger.info("执行已停止")
    
    def is_execution_running(self) -> bool:
        """检查是否正在执行"""
        return self.is_running
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取引擎状态
        
        Returns:
            Dict[str, Any]: 状态信息
        """
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "should_stop": self.should_stop,
            "os_name": self.os_name,
            "failsafe_enabled": pyautogui.FAILSAFE,
            "pause_duration": pyautogui.PAUSE,
            "ui_elements_count": len(self.ui_elements_map)
        }