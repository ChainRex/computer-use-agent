"""
任务完成度验证器 - 结合用户指令和Claude输出生成验证提示，判断任务是否完成
"""

import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# 添加项目根目录到Python路径
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from client.screenshot.screenshot_manager import ScreenshotManager
from shared.schemas.data_models import CompletionVerificationRequest, CompletionVerificationResponse, CompletionStatus

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务状态枚举"""
    COMPLETED = "completed"       # 任务已完成
    INCOMPLETE = "incomplete"     # 任务未完成，需要继续执行
    FAILED = "failed"            # 任务执行失败
    UNCLEAR = "unclear"          # 无法判断任务状态

@dataclass
class CompletionCheckResult:
    """任务完成度检查结果"""
    task_id: str
    status: TaskStatus
    confidence: float            # 置信度 (0.0-1.0)
    reasoning: str              # 判断理由
    next_steps: Optional[str]   # 如果未完成，建议的下一步操作（文字描述）
    next_actions: Optional[List] = None  # 如果未完成，具体的操作指令
    screenshot_path: Optional[str] = None  # 保留兼容性
    screenshot_base64: Optional[str] = None  # 截图的base64数据
    verification_prompt: Optional[str] = None  # 验证提示词
    check_time: float = 0.0

class TaskCompletionChecker:
    """任务完成度验证器"""
    
    def __init__(self):
        """初始化任务完成度验证器"""
        self.screenshot_manager = ScreenshotManager()
        logger.info("TaskCompletionChecker initialized")
    
    def generate_completion_check_prompt(self, original_command: str, 
                                       previous_claude_output: str,
                                       screenshot_base64: str) -> str:
        """
        生成任务完成度检查的提示词
        
        Args:
            original_command: 原始用户指令
            previous_claude_output: 上一轮Claude的输出
            screenshot_base64: 当前屏幕截图的base64编码
            
        Returns:
            str: 格式化的提示词
        """
        prompt = f"""你是一个智能计算机操作助手，正在验证任务执行结果。

**原始用户指令:**
{original_command}

**上一轮分析和操作计划:**
{previous_claude_output}

**当前屏幕状态:**
请分析当前提供的屏幕截图。

**任务验证要求:**
1. 请仔细对比原始用户指令和当前屏幕状态
2. 判断用户的原始需求是否已经得到满足
3. 考虑上一轮的操作计划是否成功执行
4. 如果任务未完成，分析还需要什么操作

**请按以下JSON格式回复:**
{{
    "status": "completed|incomplete|failed|unclear",
    "confidence": 0.0到1.0之间的数值,
    "reasoning": "详细说明你的判断理由，包括对屏幕状态的分析",
    "next_steps": "如果未完成，请描述建议的下一步操作；如果已完成，设为null"
}}

**判断标准:**
- completed: 用户的原始需求已经完全满足
- incomplete: 部分完成但还需要继续操作
- failed: 操作失败或结果不符合预期
- unclear: 无法从当前信息判断任务状态

请基于当前屏幕截图进行客观、准确的判断。"""

        return prompt
    
    def check_task_completion(self, task_id: str, original_command: str, 
                            previous_claude_output: str) -> CompletionCheckResult:
        """
        检查任务完成度
        
        Args:
            task_id: 任务ID
            original_command: 原始用户指令
            previous_claude_output: 上一轮Claude输出
            
        Returns:
            CompletionCheckResult: 检查结果
        """
        start_time = time.time()
        
        try:
            # 1. 捕获当前屏幕截图
            logger.info("正在捕获完成验证截图...")
            screenshot_base64 = self.screenshot_manager.capture_screen_to_base64()
            
            if not screenshot_base64:
                logger.error("截图失败，无法进行任务完成度验证")
                return CompletionCheckResult(
                    task_id=task_id,
                    status=TaskStatus.UNCLEAR,
                    confidence=0.0,
                    reasoning="截图失败，无法验证任务完成状态",
                    next_steps="请手动检查任务执行结果",
                    next_actions=None,
                    check_time=time.time() - start_time
                )
            
            # 2. 生成验证提示词
            prompt = self.generate_completion_check_prompt(
                original_command, 
                previous_claude_output, 
                screenshot_base64
            )
            
            # 3. 直接返回包含截图数据的结果，不需要保存文件
            return CompletionCheckResult(
                task_id=task_id,
                status=TaskStatus.UNCLEAR,  # 初始状态，等待Claude分析
                confidence=0.0,
                reasoning="等待Claude分析任务完成状态...",
                next_steps=None,
                next_actions=None,
                screenshot_path=None,  # 不需要保存文件
                screenshot_base64=screenshot_base64,  # 直接包含截图数据
                verification_prompt=prompt,  # 包含验证提示词
                check_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"任务完成度检查失败: {e}")
            return CompletionCheckResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                confidence=0.0,
                reasoning=f"检查过程发生异常: {str(e)}",
                next_steps="请手动检查任务执行结果",
                check_time=time.time() - start_time
            )
    
    
    def parse_claude_response(self, response: str, task_id: str, check_time: float) -> CompletionCheckResult:
        """
        解析Claude的响应并生成完成度检查结果
        
        Args:
            response: Claude的JSON响应
            task_id: 任务ID
            check_time: 检查耗时
            
        Returns:
            CompletionCheckResult: 解析后的检查结果
        """
        try:
            import json
            
            # 清理响应字符串
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # 解析JSON
            result_data = json.loads(cleaned_response)
            
            # 验证必需字段
            status_str = result_data.get('status', 'unclear').lower()
            confidence = float(result_data.get('confidence', 0.0))
            reasoning = result_data.get('reasoning', '无详细理由')
            next_steps = result_data.get('next_steps')
            
            # 转换状态枚举
            status_map = {
                'completed': TaskStatus.COMPLETED,
                'incomplete': TaskStatus.INCOMPLETE, 
                'failed': TaskStatus.FAILED,
                'unclear': TaskStatus.UNCLEAR
            }
            status = status_map.get(status_str, TaskStatus.UNCLEAR)
            
            # 验证置信度范围
            confidence = max(0.0, min(1.0, confidence))
            
            logger.info(f"任务 {task_id} 完成度检查结果: {status.value}, 置信度: {confidence:.2f}")
            
            return CompletionCheckResult(
                task_id=task_id,
                status=status,
                confidence=confidence,
                reasoning=reasoning,
                next_steps=next_steps,
                next_actions=None,
                check_time=check_time
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"解析Claude响应失败: {e}")
            return CompletionCheckResult(
                task_id=task_id,
                status=TaskStatus.UNCLEAR,
                confidence=0.0,
                reasoning=f"响应解析失败: {str(e)}",
                next_steps="请重新检查任务状态",
                next_actions=None,
                check_time=check_time
            )
    
    def check_task_completion_simple(self, task_id: str) -> CompletionCheckResult:
        """
        简化的任务完成度检查 - 只需要任务ID和截图
        使用新的简化接口，通过记忆模块获取上下文
        
        Args:
            task_id: 任务ID
            
        Returns:
            CompletionCheckResult: 检查结果
        """
        start_time = time.time()
        
        try:
            # 1. 捕获当前屏幕截图
            logger.info("正在捕获完成验证截图...")
            screenshot_base64 = self.screenshot_manager.capture_screen_to_base64()
            
            if not screenshot_base64:
                logger.error("截图失败，无法进行任务完成度验证")
                return CompletionCheckResult(
                    task_id=task_id,
                    status=TaskStatus.UNCLEAR,
                    confidence=0.0,
                    reasoning="截图失败，无法验证任务完成状态",
                    next_steps="请手动检查任务执行结果",
                    next_actions=None,
                    check_time=time.time() - start_time
                )
            
            # 2. 创建简化的验证请求
            verification_request = CompletionVerificationRequest(
                task_id=task_id,
                screenshot_base64=screenshot_base64
            )
            
            # 3. 返回包含截图数据的结果，等待服务端处理
            return CompletionCheckResult(
                task_id=task_id,
                status=TaskStatus.UNCLEAR,  # 初始状态，等待服务端分析
                confidence=0.0,
                reasoning="等待简化接口分析任务完成状态...",
                next_steps=None,
                next_actions=None,
                screenshot_path=None,
                screenshot_base64=screenshot_base64,
                verification_prompt=None,  # 简化接口不需要提示词
                check_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"简化任务完成度检查失败: {e}")
            return CompletionCheckResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                confidence=0.0,
                reasoning=f"检查过程发生异常: {str(e)}",
                next_steps="请手动检查任务执行结果",
                check_time=time.time() - start_time
            )
    
    def parse_simple_completion_response(self, response: CompletionVerificationResponse, 
                                       task_id: str, check_time: float) -> CompletionCheckResult:
        """
        解析简化验证接口的响应
        
        Args:
            response: 服务端返回的验证响应
            task_id: 任务ID
            check_time: 检查耗时
            
        Returns:
            CompletionCheckResult: 解析后的检查结果
        """
        try:
            # 将CompletionStatus转换为TaskStatus
            status_map = {
                CompletionStatus.COMPLETED: TaskStatus.COMPLETED,
                CompletionStatus.INCOMPLETE: TaskStatus.INCOMPLETE,
                CompletionStatus.FAILED: TaskStatus.FAILED,
                CompletionStatus.UNCLEAR: TaskStatus.UNCLEAR
            }
            
            status = status_map.get(response.status, TaskStatus.UNCLEAR)
            
            logger.info(f"任务 {task_id} 简化验证结果: {status.value}, 置信度: {response.confidence:.2f}")
            
            return CompletionCheckResult(
                task_id=task_id,
                status=status,
                confidence=response.confidence,
                reasoning=response.reasoning,
                next_steps=response.next_steps,
                next_actions=response.next_actions,  # 添加操作指令
                check_time=check_time + (response.verification_time or 0.0)
            )
            
        except Exception as e:
            logger.error(f"解析简化验证响应失败: {e}")
            return CompletionCheckResult(
                task_id=task_id,
                status=TaskStatus.UNCLEAR,
                confidence=0.0,
                reasoning=f"响应解析失败: {str(e)}",
                next_steps="请重新检查任务状态",
                next_actions=None,
                check_time=check_time
            )
    
    def cleanup_verification_screenshots(self, max_age_hours: int = 24):
        """
        清理过期的验证截图
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        try:
            temp_dir = "/root/autodl-tmp/computer-use-agent/server/claude/img/"
            if not os.path.exists(temp_dir):
                return
            
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for filename in os.listdir(temp_dir):
                if filename.startswith('verification_'):
                    filepath = os.path.join(temp_dir, filename)
                    file_age = current_time - os.path.getmtime(filepath)
                    
                    if file_age > max_age_seconds:
                        os.remove(filepath)
                        logger.debug(f"已删除过期验证截图: {filename}")
                        
        except Exception as e:
            logger.error(f"清理验证截图失败: {e}")