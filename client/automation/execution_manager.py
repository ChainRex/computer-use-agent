"""
自动化执行管理器 - 负责协调自动化执行过程、用户交互和安全控制
"""

import asyncio
import time
import logging
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer

# 添加项目根目录到Python路径
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.schemas.data_models import ActionPlan, UIElement
from client.automation.automation_engine import AutomationEngine, TaskExecutionResult, ExecutionResult, ExecutionStatus
from client.automation.safety_controller import SafetyController, SafetyAssessment, RiskLevel

logger = logging.getLogger(__name__)

class ExecutionMode(Enum):
    """执行模式枚举"""
    MANUAL = "manual"           # 手动确认每个步骤
    SEMI_AUTO = "semi_auto"     # 自动执行，关键步骤确认
    FULL_AUTO = "full_auto"     # 全自动执行
    STEP_BY_STEP = "step_by_step"  # 逐步执行

@dataclass
class ExecutionConfig:
    """执行配置"""
    mode: ExecutionMode = ExecutionMode.SEMI_AUTO
    confirm_dangerous_actions: bool = True
    max_execution_time: float = 300.0  # 最大执行时间（秒）
    screenshot_enabled: bool = True
    strict_mode: bool = False  # 严格模式：任何失败都停止
    auto_retry: bool = True    # 自动重试失败的操作
    max_retries: int = 2       # 最大重试次数

class ExecutionWorker(QThread):
    """执行工作线程"""
    
    # 信号定义
    execution_started = pyqtSignal(str)  # task_id
    action_started = pyqtSignal(int, str)  # action_index, description
    action_completed = pyqtSignal(int, object)  # action_index, ExecutionResult
    execution_completed = pyqtSignal(object)  # TaskExecutionResult
    execution_paused = pyqtSignal()
    execution_resumed = pyqtSignal()
    execution_stopped = pyqtSignal()
    confirmation_requested = pyqtSignal(int, str, str)  # action_index, action_type, description
    error_occurred = pyqtSignal(str)  # error_message
    
    def __init__(self, engine: AutomationEngine, action_plan: List[ActionPlan], 
                 task_id: str, config: ExecutionConfig, safety_controller: SafetyController):
        super().__init__()
        self.engine = engine
        self.action_plan = action_plan
        self.task_id = task_id
        self.config = config
        self.safety_controller = safety_controller
        
        self.should_stop = False
        self.is_paused = False
        self.waiting_for_confirmation = False
        self.confirmation_result = None
        
        # 重试机制
        self.retry_counts = {}
    
    def run(self):
        """执行线程主循环"""
        try:
            self.execution_started.emit(self.task_id)
            
            action_results = []
            start_time = time.time()
            
            for i, action in enumerate(self.action_plan):
                if self.should_stop:
                    break
                
                # 处理暂停
                while self.is_paused and not self.should_stop:
                    self.msleep(100)
                
                if self.should_stop:
                    break
                
                # 检查是否需要用户确认
                needs_confirmation, confirmation_message = self._should_confirm_action(action, i)
                if needs_confirmation:
                    if not self._request_confirmation(action, i, confirmation_message):
                        # 用户拒绝执行
                        break
                
                # 执行操作（可能包含重试）
                result = self._execute_with_retry(action, i)
                action_results.append(result)
                
                self.action_completed.emit(i, result)
                
                # 检查是否应该停止（严格模式下的失败）
                if (result.status == ExecutionStatus.FAILED and 
                    self.config.strict_mode):
                    logger.error(f"严格模式下操作失败，停止执行: {result.error_message}")
                    break
            
            # 计算最终结果
            total_time = time.time() - start_time
            completed = len([r for r in action_results if r.status == ExecutionStatus.SUCCESS])
            success_rate = completed / len(self.action_plan) if self.action_plan else 0
            
            # 确定整体状态
            if self.should_stop:
                overall_status = ExecutionStatus.CANCELLED
            elif completed == len(self.action_plan):
                overall_status = ExecutionStatus.SUCCESS
            elif completed == 0:
                overall_status = ExecutionStatus.FAILED
            else:
                overall_status = ExecutionStatus.FAILED
            
            final_result = TaskExecutionResult(
                task_id=self.task_id,
                total_actions=len(self.action_plan),
                completed_actions=completed,
                success_rate=success_rate,
                total_execution_time=total_time,
                status=overall_status,
                action_results=action_results
            )
            
            self.execution_completed.emit(final_result)
            
        except Exception as e:
            logger.error(f"执行线程发生异常: {e}")
            self.error_occurred.emit(str(e))
    
    def _should_confirm_action(self, action: ActionPlan, action_index: int) -> tuple[bool, str]:
        """
        判断是否需要用户确认
        
        Returns:
            tuple[bool, str]: (是否需要确认, 确认消息)
        """
        # 首先进行安全评估
        ui_elements = list(self.engine.ui_elements_map.values())
        safety_assessment = self.safety_controller.assess_action_safety(action, action_index, ui_elements)
        
        # 如果安全评估要求阻止执行，直接返回
        if safety_assessment.block_execution:
            return True, f"🚫 安全控制器阻止执行:\n{safety_assessment.warning_message}"
        
        # 根据执行模式和安全评估确定是否需要确认
        needs_confirmation = False
        confirmation_message = ""
        
        if self.config.mode == ExecutionMode.FULL_AUTO:
            # 全自动模式：只有安全评估要求确认才确认
            needs_confirmation = safety_assessment.requires_confirmation
        elif self.config.mode == ExecutionMode.MANUAL:
            # 手动模式：总是需要确认
            needs_confirmation = True
        elif self.config.mode == ExecutionMode.STEP_BY_STEP:
            # 逐步模式：总是需要确认
            needs_confirmation = True
        elif self.config.mode == ExecutionMode.SEMI_AUTO:
            # 半自动模式：安全评估要求确认或操作类型需要确认
            safety_confirmation = safety_assessment.requires_confirmation
            type_confirmation = (action.type.lower() in ['drag', 'key', 'hotkey'] and 
                                self.config.confirm_dangerous_actions)
            needs_confirmation = safety_confirmation or type_confirmation
        
        # 生成确认消息
        if needs_confirmation:
            if safety_assessment.warning_message:
                confirmation_message = safety_assessment.warning_message
            else:
                confirmation_message = f"即将执行 {action.type} 操作:\n{action.description}"
        
        return needs_confirmation, confirmation_message
    
    def _request_confirmation(self, action: ActionPlan, action_index: int, message: str = "") -> bool:
        """请求用户确认"""
        self.waiting_for_confirmation = True
        self.confirmation_result = None
        
        # 使用自定义消息或默认描述
        description = message if message else action.description
        
        self.confirmation_requested.emit(
            action_index, 
            action.type, 
            description
        )
        
        # 等待用户响应
        timeout = 30.0  # 30秒超时
        start_time = time.time()
        
        while (self.waiting_for_confirmation and 
               not self.should_stop and 
               time.time() - start_time < timeout):
            self.msleep(100)
        
        if self.should_stop:
            return False
        elif time.time() - start_time >= timeout:
            logger.warning("用户确认超时，取消执行")
            return False
        
        return self.confirmation_result == True
    
    def _execute_with_retry(self, action: ActionPlan, action_index: int) -> ExecutionResult:
        """执行操作（包含重试机制）"""
        max_retries = self.config.max_retries if self.config.auto_retry else 0
        retry_count = 0
        
        while retry_count <= max_retries:
            self.action_started.emit(action_index, action.description)
            
            # 执行操作
            result = self.engine._execute_single_action(action, action_index)
            
            if result.status == ExecutionStatus.SUCCESS or not self.config.auto_retry:
                break
            
            # 失败且可以重试
            retry_count += 1
            if retry_count <= max_retries:
                logger.info(f"操作 {action_index} 失败，进行第 {retry_count} 次重试")
                self.msleep(1000)  # 等待1秒后重试
        
        # 记录重试次数
        if retry_count > 0:
            self.retry_counts[action_index] = retry_count
        
        return result
    
    def pause(self):
        """暂停执行"""
        self.is_paused = True
        self.execution_paused.emit()
    
    def resume(self):
        """恢复执行"""
        self.is_paused = False
        self.execution_resumed.emit()
    
    def stop(self):
        """停止执行"""
        self.should_stop = True
        self.is_paused = False
        self.waiting_for_confirmation = False
        self.execution_stopped.emit()
    
    def confirm_action(self, confirmed: bool):
        """用户确认操作"""
        self.confirmation_result = confirmed
        self.waiting_for_confirmation = False

class ExecutionManager(QObject):
    """自动化执行管理器"""
    
    # 信号定义
    execution_started = pyqtSignal(str)
    execution_completed = pyqtSignal(object)
    execution_paused = pyqtSignal()
    execution_resumed = pyqtSignal()
    execution_stopped = pyqtSignal()
    action_started = pyqtSignal(int, str)
    action_completed = pyqtSignal(int, object)
    confirmation_requested = pyqtSignal(int, str, str, object)  # 最后一个参数是回调函数
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(dict)
    task_completion_check_requested = pyqtSignal(str, str, str)  # task_id, original_command, previous_claude_output
    
    def __init__(self, config: Optional[ExecutionConfig] = None):
        super().__init__()
        
        self.config = config or ExecutionConfig()
        self.engine = AutomationEngine({
            'failsafe': True,
            'pause_between_actions': 0.5,
            'capture_screenshots': self.config.screenshot_enabled,
            'strict_mode': self.config.strict_mode
        })
        
        # 初始化安全控制器
        safety_config = {
            'strict_mode': self.config.strict_mode,
            'require_confirmation_for_medium': self.config.confirm_dangerous_actions,
            'block_high_risk': False,  # 默认不阻止高风险操作，而是要求确认
            'block_critical_risk': True  # 阻止极高风险操作
        }
        self.safety_controller = SafetyController(safety_config)
        
        self.current_worker = None
        self.current_task_id = None
        self.original_user_command = None  # 保存原始用户指令
        self.previous_claude_output = None  # 保存上一轮Claude输出
        
        # 状态监控定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._emit_status)
        self.status_timer.start(1000)  # 每秒更新状态
        
        logger.info("ExecutionManager initialized")
    
    def execute_action_plan(self, action_plan: List[ActionPlan], ui_elements: List[UIElement], 
                           task_id: str = None, original_command: str = None, 
                           claude_output: str = None) -> bool:
        """
        执行操作计划
        
        Args:
            action_plan: 操作计划列表
            ui_elements: UI元素列表
            task_id: 任务ID
            original_command: 原始用户指令
            claude_output: 上一轮Claude输出
            
        Returns:
            bool: 是否成功启动执行
        """
        if self.is_executing():
            logger.warning("已有任务在执行中，无法启动新任务")
            return False
        
        if not action_plan:
            logger.warning("操作计划为空，无法执行")
            return False
        
        self.current_task_id = task_id or f"task_{int(time.time())}"
        self.original_user_command = original_command
        self.previous_claude_output = claude_output
        
        # 更新UI元素映射
        self.engine.set_ui_elements(ui_elements)
        
        # 创建执行线程
        self.current_worker = ExecutionWorker(
            self.engine, action_plan, self.current_task_id, self.config, self.safety_controller
        )
        
        # 连接信号
        self._connect_worker_signals()
        
        # 启动执行
        self.current_worker.start()
        
        logger.info(f"开始执行任务 {self.current_task_id}，共 {len(action_plan)} 个操作")
        return True
    
    def _connect_worker_signals(self):
        """连接工作线程信号"""
        if not self.current_worker:
            return
        
        self.current_worker.execution_started.connect(self.execution_started.emit)
        self.current_worker.execution_completed.connect(self._on_execution_completed)
        self.current_worker.execution_paused.connect(self.execution_paused.emit)
        self.current_worker.execution_resumed.connect(self.execution_resumed.emit)
        self.current_worker.execution_stopped.connect(self.execution_stopped.emit)
        self.current_worker.action_started.connect(self.action_started.emit)
        self.current_worker.action_completed.connect(self.action_completed.emit)
        self.current_worker.confirmation_requested.connect(self._on_confirmation_requested)
        self.current_worker.error_occurred.connect(self.error_occurred.emit)
    
    def _on_execution_completed(self, result: TaskExecutionResult):
        """执行完成处理"""
        # 触发任务完成度检查
        if (self.original_user_command and 
            result.status == ExecutionStatus.SUCCESS):
            logger.info("开始任务完成度验证...")
            self.task_completion_check_requested.emit(
                self.current_task_id,
                self.original_user_command,
                self.previous_claude_output or ""
            )
        
        self.execution_completed.emit(result)
        self.current_worker = None
        self.current_task_id = None
    
    def _on_confirmation_requested(self, action_index: int, action_type: str, description: str):
        """用户确认请求处理"""
        def confirm_callback(confirmed: bool):
            if self.current_worker:
                self.current_worker.confirm_action(confirmed)
        
        self.confirmation_requested.emit(action_index, action_type, description, confirm_callback)
    
    def pause_execution(self):
        """暂停执行"""
        if self.current_worker:
            self.current_worker.pause()
    
    def resume_execution(self):
        """恢复执行"""
        if self.current_worker:
            self.current_worker.resume()
    
    def stop_execution(self):
        """停止执行"""
        if self.current_worker:
            self.current_worker.stop()
            self.current_worker.wait(5000)  # 等待最多5秒
            if self.current_worker.isRunning():
                self.current_worker.terminate()
            self.current_worker = None
            self.current_task_id = None
    
    def is_executing(self) -> bool:
        """检查是否正在执行"""
        return self.current_worker is not None and self.current_worker.isRunning()
    
    def get_execution_status(self) -> Dict[str, Any]:
        """获取执行状态"""
        base_status = {
            "is_executing": self.is_executing(),
            "current_task_id": self.current_task_id,
            "config": {
                "mode": self.config.mode.value,
                "confirm_dangerous": self.config.confirm_dangerous_actions,
                "screenshot_enabled": self.config.screenshot_enabled,
                "strict_mode": self.config.strict_mode,
                "auto_retry": self.config.auto_retry
            }
        }
        
        if self.engine:
            base_status.update(self.engine.get_status())
        
        return base_status
    
    def _emit_status(self):
        """发送状态更新信号"""
        status = self.get_execution_status()
        self.status_changed.emit(status)
    
    def update_config(self, new_config: ExecutionConfig):
        """更新配置"""
        self.config = new_config
        
        # 更新引擎配置
        if self.engine:
            self.engine.config.update({
                'capture_screenshots': new_config.screenshot_enabled,
                'strict_mode': new_config.strict_mode
            })
        
        # 更新安全控制器配置
        if self.safety_controller:
            safety_config = {
                'strict_mode': new_config.strict_mode,
                'require_confirmation_for_medium': new_config.confirm_dangerous_actions,
                'block_high_risk': False,
                'block_critical_risk': True
            }
            self.safety_controller.update_config(safety_config)
        
        logger.info(f"配置已更新: mode={new_config.mode.value}")
    
    def get_config(self) -> ExecutionConfig:
        """获取当前配置"""
        return self.config