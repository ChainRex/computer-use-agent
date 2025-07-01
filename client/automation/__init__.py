"""
Client Automation Package - PyAutoGUI自动化执行模块

这个包提供了将AI生成的操作计划转换为实际计算机操作的功能。

主要组件:
- AutomationEngine: 核心执行引擎
- ExecutionManager: 执行管理器，处理用户交互和安全控制
- ExecutionConfig: 执行配置
- ExecutionResult: 执行结果数据结构
"""

from .automation_engine import AutomationEngine, ExecutionStatus, ExecutionResult, TaskExecutionResult
from .execution_manager import ExecutionManager, ExecutionConfig, ExecutionMode
from .result_validator import ResultValidator, ValidationResult, ValidationReport
from .safety_controller import SafetyController, SafetyRule, SafetyAssessment, RiskLevel

__all__ = [
    'AutomationEngine',
    'ExecutionManager', 
    'ExecutionConfig',
    'ExecutionMode',
    'ExecutionStatus',
    'ExecutionResult',
    'TaskExecutionResult',
    'ResultValidator',
    'ValidationResult',
    'ValidationReport',
    'SafetyController',
    'SafetyRule',
    'SafetyAssessment',
    'RiskLevel'
]