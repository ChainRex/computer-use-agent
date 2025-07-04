"""
Claude服务 - 集成Claude模型进行智能任务分析和操作指令生成
"""

import subprocess
import tempfile
import os
import base64
import json
import logging
import time
import re
from typing import Dict, List, Optional, Tuple
from PIL import Image
import io

from shared.schemas.data_models import ActionPlan, UIElement, OSInfo, CompletionVerificationRequest, CompletionVerificationResponse, CompletionStatus

logger = logging.getLogger(__name__)

class TaskMemory:
    """任务记忆模块 - 存储任务上下文信息"""
    
    def __init__(self):
        self.task_contexts: Dict[str, Dict] = {}
    
    def save_task_context(self, task_id: str, original_command: str, actions: List[ActionPlan], reasoning: str, ui_elements: Optional[List[UIElement]] = None):
        """保存任务上下文"""
        self.task_contexts[task_id] = {
            'original_command': original_command,
            'actions': actions,
            'reasoning': reasoning,
            'ui_elements': ui_elements or [],
            'created_at': time.time()
        }
        logger.info(f"Saved context for task {task_id} with {len(ui_elements) if ui_elements else 0} UI elements")
    
    def get_task_context(self, task_id: str) -> Optional[Dict]:
        """获取任务上下文"""
        return self.task_contexts.get(task_id)
    
    def clear_old_contexts(self, max_age_hours: int = 24):
        """清理超过指定时间的上下文"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        expired_tasks = [
            task_id for task_id, context in self.task_contexts.items()
            if current_time - context['created_at'] > max_age_seconds
        ]
        
        for task_id in expired_tasks:
            del self.task_contexts[task_id]
            logger.debug(f"Cleared expired context for task {task_id}")
        
        if expired_tasks:
            logger.info(f"Cleared {len(expired_tasks)} expired task contexts")

class ClaudeService:
    """Claude服务类，提供智能任务分析和操作指令生成功能"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化Claude服务
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        # 使用固定的img目录而不是临时目录
        self.img_dir = "/root/autodl-tmp/computer-use-agent/server/claude/img"
        os.makedirs(self.img_dir, exist_ok=True)
        
        # 初始化记忆模块
        self.memory = TaskMemory()
        
        # 重试配置
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 2.0)
        
        logger.info(f"Claude service initialized with img dir: {self.img_dir}, max_retries: {self.max_retries}")
    
    def analyze_task_with_claude(
        self, 
        text_command: str, 
        screenshot_base64: str, 
        ui_elements: List[UIElement],
        annotated_screenshot_base64: Optional[str] = None,
        os_info: Optional[OSInfo] = None,
        task_id: Optional[str] = None
    ) -> Tuple[List[ActionPlan], str, float]:
        """
        使用Claude分析任务并生成pyautogui操作指令
        
        Args:
            text_command: 用户文本指令
            screenshot_base64: 原始截图的base64编码
            ui_elements: 检测到的UI元素列表
            annotated_screenshot_base64: 标注后的截图base64编码（可选）
            os_info: 操作系统信息
            task_id: 任务ID，用于记忆管理
            
        Returns:
            Tuple[List[ActionPlan], str, float]: (操作计划列表, 推理过程, 置信度)
        """
        try:
            # 保存图像文件
            image_path = self._save_image_from_base64(
                annotated_screenshot_base64 or screenshot_base64, 
                "analysis_image.png"
            )
            
            # 构建Claude分析提示
            prompt = self._build_analysis_prompt(text_command, ui_elements, os_info)
            
            # 执行Claude命令（带重试机制）
            claude_response = self._execute_claude_command_with_retry(prompt, image_path)
            
            # 解析Claude响应
            actions, reasoning, confidence = self._parse_claude_response(claude_response, ui_elements)
            
            # 保存到记忆模块
            if task_id:
                self.memory.save_task_context(task_id, text_command, actions, reasoning, ui_elements)
            
            return actions, reasoning, confidence
            
        except Exception as e:
            logger.error(f"Claude analysis failed: {str(e)}")
            raise
    
    def verify_task_completion(
        self, 
        original_command: str, 
        previous_claude_output: str,
        verification_screenshot_path: str
    ) -> Tuple[str, str, float]:
        """
        使用Claude验证任务完成度
        
        Args:
            original_command: 原始用户指令
            previous_claude_output: 上一轮Claude输出
            verification_screenshot_path: 验证截图文件路径
            
        Returns:
            Tuple[str, str, float]: (状态, 推理过程, 置信度)
        """
        try:
            # 构建任务完成度验证提示
            prompt = self._build_completion_verification_prompt(
                original_command, 
                previous_claude_output
            )
            
            # 执行Claude命令（带重试机制）
            claude_response = self._execute_claude_command_with_retry(prompt, verification_screenshot_path)
            
            # 解析Claude响应
            status, reasoning, confidence = self._parse_completion_response(claude_response)
            
            return status, reasoning, confidence
            
        except Exception as e:
            logger.error(f"Claude task completion verification failed: {str(e)}")
            raise
    
    def verify_task_completion_with_base64(
        self, 
        original_command: str, 
        previous_claude_output: str,
        screenshot_base64: str,
        verification_prompt: str = None
    ) -> Tuple[str, str, float, Optional[str], Optional[List[Dict]]]:
        """
        使用Claude验证任务完成度（使用base64截图数据）
        
        Args:
            original_command: 原始用户指令
            previous_claude_output: 上一轮Claude输出
            screenshot_base64: 截图的base64数据
            verification_prompt: 可选的自定义验证提示词
            
        Returns:
            Tuple[str, str, float, Optional[str], Optional[List[Dict]]]: (状态, 推理过程, 置信度, 下一步建议, 下一步操作)
        """
        try:
            # 如果没有提供自定义提示词，使用默认的构建方法
            if not verification_prompt:
                verification_prompt = self._build_completion_verification_prompt(
                    original_command, 
                    previous_claude_output
                )
            
            # 将base64数据保存为临时文件用于Claude分析
            timestamp = int(time.time())
            temp_filename = f"verification_temp_{timestamp}.png"
            temp_filepath = self._save_image_from_base64(screenshot_base64, temp_filename)
            
            try:
                # 执行Claude命令（带重试机制）
                claude_response = self._execute_claude_command_with_retry(verification_prompt, temp_filepath)
                
                # 解析Claude响应（增强版，支持next_steps和next_actions）
                status, reasoning, confidence, next_steps, next_actions = self._parse_completion_response_enhanced(claude_response)
                
                return status, reasoning, confidence, next_steps, next_actions
                
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
                        logger.debug(f"Cleaned up temp file: {temp_filepath}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file {temp_filepath}: {cleanup_error}")
            
        except Exception as e:
            logger.error(f"Claude task completion verification with base64 failed: {str(e)}")
            raise
    
    def verify_completion_simple(self, task_id: str, screenshot_base64: str) -> CompletionVerificationResponse:
        """
        简化的任务完成验证接口 - 使用记忆模块获取上下文
        
        Args:
            task_id: 任务ID
            screenshot_base64: 当前截图的base64数据
            
        Returns:
            CompletionVerificationResponse: 验证响应
        """
        start_time = time.time()
        
        try:
            # 从记忆模块获取任务上下文
            task_context = self.memory.get_task_context(task_id)
            if not task_context:
                logger.warning(f"No context found for task {task_id}")
                return CompletionVerificationResponse(
                    task_id=task_id,
                    status=CompletionStatus.INCOMPLETE,
                    reasoning="无法找到任务上下文信息",
                    confidence=0.0,
                    next_steps="请重新执行任务分析",
                    verification_time=time.time() - start_time
                )
            
            original_command = task_context['original_command']
            previous_reasoning = task_context['reasoning']
            
            # 构建验证提示，包含上下文信息
            prompt = self._build_memory_based_verification_prompt(
                original_command, 
                previous_reasoning,
                task_context
            )
            
            # 保存截图用于分析
            timestamp = int(time.time())
            temp_filename = f"verification_{task_id}_{timestamp}.png"
            temp_filepath = self._save_image_from_base64(screenshot_base64, temp_filename)
            
            try:
                # 执行Claude命令
                claude_response = self._execute_claude_command_with_retry(prompt, temp_filepath)
                
                # 解析响应（使用增强版解析器，支持坐标提取）
                ui_elements = task_context.get('ui_elements', [])
                status, reasoning, confidence, next_steps, next_actions = self._parse_completion_response_enhanced(claude_response, ui_elements)
                
                verification_time = time.time() - start_time
                
                return CompletionVerificationResponse(
                    task_id=task_id,
                    status=CompletionStatus(status),
                    reasoning=reasoning,
                    confidence=confidence,
                    next_steps=next_steps,
                    next_actions=next_actions,
                    verification_time=verification_time
                )
                
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
                        logger.debug(f"Cleaned up temp file: {temp_filepath}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file {temp_filepath}: {cleanup_error}")
                    
        except Exception as e:
            logger.error(f"Simple completion verification failed for task {task_id}: {str(e)}")
            return CompletionVerificationResponse(
                task_id=task_id,
                status=CompletionStatus.INCOMPLETE,
                reasoning=f"验证过程出错: {str(e)}",
                confidence=0.0,
                next_steps="请检查系统状态后重试",
                verification_time=time.time() - start_time
            )
    
    def _save_image_from_base64(self, image_base64: str, filename: str) -> str:
        """
        将base64图像保存为文件
        
        Args:
            image_base64: base64编码的图像
            filename: 文件名
            
        Returns:
            str: 保存的文件路径
        """
        try:
            # 移除data URL前缀（如果存在）
            if image_base64.startswith('data:image'):
                image_base64 = image_base64.split(',')[1]
            
            # 解码图像数据
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))
            
            # 保存图像到img目录
            image_path = os.path.join(self.img_dir, filename)
            image.save(image_path)
            
            logger.info(f"Image saved to: {image_path}")
            return image_path
            
        except Exception as e:
            logger.error(f"Failed to save image: {str(e)}")
            raise
    
    def _build_analysis_prompt(self, text_command: str, ui_elements: List[UIElement], os_info: Optional[OSInfo] = None) -> str:
        """
        构建Claude分析提示
        
        Args:
            text_command: 用户指令
            ui_elements: UI元素列表
            os_info: 操作系统信息
            
        Returns:
            str: 分析提示
        """
        # 构建UI元素描述
        elements_description = []
        for elem in ui_elements:
            elem_desc = f"ID:{elem.id} 类型:{elem.type} 描述:{elem.description}"
            if elem.coordinates and len(elem.coordinates) >= 4:
                elem_desc += f" 坐标:[{elem.coordinates[0]},{elem.coordinates[1]},{elem.coordinates[2]},{elem.coordinates[3]}]"
            if elem.text:
                elem_desc += f" 文本:'{elem.text}'"
            elements_description.append(elem_desc)
        
        elements_text = "\n".join(elements_description) if elements_description else "无UI元素检测到"
        
        # 构建操作系统信息
        os_text = "未知"
        if os_info:
            system = getattr(os_info, 'system', '未知')
            version = getattr(os_info, 'version', '未知')
            os_text = f"{system} {version}"
        
        
        prompt = f"""请分析这个计算机屏幕截图和用户指令，生成详细的pyautogui操作步骤。

用户指令: {text_command}

操作系统: {os_text}

检测到的UI元素:
{elements_text}

请严格按照以下JSON格式输出，不要添加任何额外的文本或注释:
{{
    "reasoning": "简短的分析推理过程，不要使用双引号",
    "confidence": 0.8,
    "actions": [
        {{
            "type": "click",
            "description": "点击描述，不要使用双引号",
            "element_id": "UI元素的ID"
        }},
        {{
            "type": "type",
            "description": "输入描述，不要使用双引号", 
            "text": "English text only - translate Chinese to English"
        }},
        {{
            "type": "key",
            "description": "按键描述，不要使用双引号",
            "text": "按键组合如ctrl+c或enter"
        }},
        {{
            "type": "wait",
            "description": "等待描述，不要使用双引号",
            "duration": 1.0
        }}
    ]
}}

操作类型说明:
- click: 点击操作，必须提供element_id（引用检测到的UI元素ID），不要提供coordinates
- type: 文本输入操作，需要提供text
- key: 按键操作，需要提供按键组合text
- wait: 等待操作，需要提供duration（秒）

JSON格式要求:
1. 只输出JSON，不要添加任何说明文字或markdown标记
2. reasoning和description字段中不要使用双引号，用单引号或中文标点
3. 确保JSON格式完全有效
4. 对于点击操作，必须使用element_id引用上面列出的UI元素
5. 如果没有合适的UI元素可以点击，在reasoning中说明并提供替代方案

操作系统特定要求:
- Windows系统: 使用Windows特定的快捷键(如Win+R, Alt+Tab等)
- macOS系统: 使用Mac特定的快捷键(如Cmd+Space, Cmd+Tab等)  
- Linux系统: 使用Linux桌面环境相关的快捷键
- 根据操作系统调整操作方式和界面元素识别策略

文本输入要求 (CRITICAL):
- 所有type操作中的text字段必须使用英文，不能包含中文字符
- 如果用户指令包含中文内容，必须将其翻译为英文后再输入
- 例如: 用户要求输入"你好"，应该输入"hello"
- 例如: 用户要求输入"搜索"，应该输入"search"  
- 例如: 用户要求输入"文件"，应该输入"file"
- 确保所有text字段只包含ASCII字符，因为pyautogui无法处理中文字符

"""

        return prompt
    
    def _build_completion_verification_prompt(self, original_command: str, previous_claude_output: str) -> str:
        """
        构建任务完成度验证提示
        
        Args:
            original_command: 原始用户指令
            previous_claude_output: 上一轮Claude输出
            
        Returns:
            str: 验证提示
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
4. 如果任务未完成，分析还需要什么操作，并生成具体的pyautogui操作指令

请严格按照以下JSON格式回复，不要添加任何额外的文本或注释:
{{
    "status": "completed|incomplete",
    "confidence": 0.9,
    "reasoning": "详细说明你的判断理由，包括对屏幕状态的分析，不要使用双引号",
    "next_steps": "如果未完成，请描述建议的下一步操作；如果已完成，设为null",
    "next_actions": [
        {{
            "type": "click",
            "description": "点击操作描述，不要使用双引号",
            "element_id": "UI元素ID或null",
            "coordinates": [x, y]
        }},
        {{
            "type": "key",
            "description": "按键操作描述，不要使用双引号",
            "text": "cmd+space"
        }},
        {{
            "type": "type",
            "description": "输入操作描述，不要使用双引号", 
            "text": "English text only - translate Chinese to English"
        }}
    ]
}}

重要：如果status是incomplete，next_actions数组必须包含至少一个操作！

**状态值说明:**
- completed: 用户的原始需求已经完全满足（next_actions设为null）
- incomplete: 任务未完成或需要继续操作（必须提供next_actions）

**next_actions操作类型说明:**
- click: 点击操作，格式{{"type": "click", "description": "点击描述", "element_id": "UI元素ID或null", "coordinates": [x,y]}}
- type: 文本输入操作，格式{{"type": "type", "description": "输入描述", "text": "要输入的文本"}}
- key: 按键操作，格式{{"type": "key", "description": "按键描述", "text": "按键组合如cmd+space"}}
- wait: 等待操作，格式{{"type": "wait", "description": "等待描述", "duration": 等待秒数}}

**重要提示:**
- 优先使用检测到的UI元素ID进行点击操作
- 对于macOS系统，使用cmd键而不是ctrl键
- 按键组合用加号连接，如"cmd+space", "cmd+tab"
- 确保操作序列逻辑正确，能够完成指定任务
- **CRITICAL: 所有type操作的text字段必须使用英文，不能包含中文字符，因为pyautogui无法处理中文**

**JSON格式要求:**
1. 只输出JSON，不要添加任何说明文字或markdown标记
2. reasoning、next_steps和description字段中不要使用双引号，用单引号或中文标点
3. 确保JSON格式完全有效
4. confidence值必须在0.0到1.0之间
5. 如果status不是completed，必须提供具体的next_actions操作步骤来继续完成任务

请基于当前屏幕截图进行客观、准确的判断。"""

        return prompt
    
    def _build_memory_based_verification_prompt(self, original_command: str, previous_reasoning: str, task_context: Dict) -> str:
        """
        基于记忆模块构建验证提示
        
        Args:
            original_command: 原始用户指令
            previous_reasoning: 之前的推理过程
            task_context: 任务上下文
            
        Returns:
            str: 验证提示
        """
        actions = task_context.get('actions', [])
        actions_summary = []
        
        for i, action in enumerate(actions[:5]):  # 只显示前5个操作
            action_desc = f"{i+1}. {action.type}"
            if hasattr(action, 'description') and action.description:
                action_desc += f": {action.description}"
            actions_summary.append(action_desc)
        
        actions_text = "\n".join(actions_summary) if actions_summary else "无操作记录"
        if len(actions) > 5:
            actions_text += f"\n... (共{len(actions)}个操作)"
        
        prompt = f"""你是一个智能计算机操作助手，正在验证任务执行结果。你有这个任务的完整上下文信息。

**原始用户指令:**
{original_command}

**之前的分析推理:**
{previous_reasoning}

**计划执行的操作:**
{actions_text}

**当前屏幕状态:**
请分析当前提供的屏幕截图。

**任务验证要求:**
1. 请仔细对比原始用户指令和当前屏幕状态
2. 判断用户的原始需求是否已经得到满足
3. 考虑计划的操作是否成功执行并产生了预期结果
4. 如果任务未完成，分析还需要什么操作，并生成具体的pyautogui操作指令

请严格按照以下JSON格式回复，不要添加任何额外的文本或注释:
{{
    "status": "completed|incomplete",
    "confidence": 0.9,
    "reasoning": "详细说明你的判断理由，包括对屏幕状态的分析，不要使用双引号",
    "next_steps": "如果未完成，请描述建议的下一步操作；如果已完成，设为null",
    "next_actions": [
        {{
            "type": "click",
            "description": "点击操作描述，不要使用双引号",
            "element_id": "UI元素ID或null",
            "coordinates": [x, y]
        }},
        {{
            "type": "key",
            "description": "按键操作描述，不要使用双引号",
            "text": "cmd+space"
        }},
        {{
            "type": "type",
            "description": "输入操作描述，不要使用双引号", 
            "text": "English text only - translate Chinese to English"
        }}
    ]
}}

重要：如果status是incomplete，next_actions数组必须包含至少一个操作！

**状态值说明:**
- completed: 用户的原始需求已经完全满足（next_actions设为null）
- incomplete: 任务未完成或需要继续操作（必须提供next_actions）

**next_actions操作类型说明:**
- click: 点击操作，格式{{"type": "click", "description": "点击描述", "element_id": "UI元素ID或null", "coordinates": [x,y]}}
- type: 文本输入操作，格式{{"type": "type", "description": "输入描述", "text": "要输入的文本"}}
- key: 按键操作，格式{{"type": "key", "description": "按键描述", "text": "按键组合如cmd+space"}}
- wait: 等待操作，格式{{"type": "wait", "description": "等待描述", "duration": 等待秒数}}

**重要提示:**
- 优先使用检测到的UI元素ID进行点击操作
- 对于macOS系统，使用cmd键而不是ctrl键
- 按键组合用加号连接，如"cmd+space", "cmd+tab"
- 确保操作序列逻辑正确，能够完成指定任务
- **CRITICAL: 所有type操作的text字段必须使用英文，不能包含中文字符，因为pyautogui无法处理中文**

**JSON格式要求:**
1. 只输出JSON，不要添加任何说明文字或markdown标记
2. reasoning、next_steps和description字段中不要使用双引号，用单引号或中文标点
3. 确保JSON格式完全有效
4. confidence值必须在0.0到1.0之间
5. 如果status不是completed，必须提供具体的next_actions操作步骤来继续完成任务

请基于任务上下文和当前屏幕截图进行客观、准确的判断。"""

        return prompt
    
    def _execute_claude_command_with_retry(self, prompt: str, image_path: str) -> str:
        """
        执行Claude命令（带重试机制）
        
        Args:
            prompt: 分析提示
            image_path: 图像文件路径
            
        Returns:
            str: Claude响应
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Claude命令重试 {attempt}/{self.max_retries}")
                    time.sleep(self.retry_delay * attempt)  # 指数退避
                
                response = self._execute_claude_command(prompt, image_path)
                
                # 验证响应是否为空或无效
                if not response or response.strip() == "":
                    raise RuntimeError("Claude returned empty response")
                
                # 简单验证响应是否包含有效内容
                if len(response.strip()) < 10:
                    raise RuntimeError(f"Claude response too short: {len(response)} chars")
                
                # 检测Claude CLI界面消息，但尝试提取JSON内容
                cli_messages = [
                    "Welcome to Claude Code",
                    "🌟",
                    "You are using the canonical relay", 
                    "If the relay doesn't work",
                    "Execution error",
                    "claude --pick-relay"
                ]
                
                contains_cli_message = any(msg in response for msg in cli_messages)
                if contains_cli_message:
                    logger.warning(f"Claude CLI interface detected, attempting to extract JSON content")
                    # 尝试提取JSON部分
                    if '{' in response and '}' in response:
                        # 找到第一个'{'和最后一个'}'之间的内容
                        start_idx = response.find('{')
                        end_idx = response.rfind('}')
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            json_content = response[start_idx:end_idx+1]
                            logger.info(f"Extracted JSON content from CLI response: {len(json_content)} chars")
                            response = json_content
                        else:
                            raise RuntimeError(f"Could not extract JSON from CLI response: {response[:100]}")
                    else:
                        raise RuntimeError(f"Claude returned CLI interface message without JSON: {response[:100]}")
                
                # 验证响应是否包含JSON格式（基本检查）
                if not ('{' in response and '}' in response):
                    raise RuntimeError(f"Claude response doesn't contain JSON structure: {response[:100]}")
                
                logger.info(f"Claude命令成功 (尝试 {attempt + 1})")
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"Claude命令失败 (尝试 {attempt + 1}): {str(e)}")
                
                if attempt == self.max_retries:
                    break
        
        logger.error(f"Claude命令最终失败，已重试 {self.max_retries} 次")
        raise last_error or RuntimeError("Claude command failed after all retries")
    
    def _execute_claude_command(self, prompt: str, image_path: str) -> str:
        """
        执行Claude命令行工具
        
        Args:
            prompt: 分析提示
            image_path: 图像文件路径
            
        Returns:
            str: Claude响应
        """
        try:
            # 将图片路径包含在prompt中
            full_prompt = f"{prompt}\n\n请分析这个图片文件: {image_path}"
            
            # 构建Claude命令
            cmd = [
                "claude",
                "-p",
                full_prompt
            ]
            
            logger.debug(f"Executing Claude command: {' '.join(cmd[:2])} [prompt with image path]")
            
            # 执行命令（5分钟超时）
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                logger.debug(f"Claude raw response length: {len(response)}")
                logger.debug(f"Claude raw response preview: {response[:200]}...")  # 打印前200字符用于调试
                
                # 如果响应包含CLI消息，记录更详细的信息用于调试
                cli_messages = ["Welcome to Claude Code", "🌟", "You are using the canonical relay", "Execution error"]
                if any(msg in response for msg in cli_messages):
                    logger.warning(f"Claude CLI interface detected in response: {response[:500]}")
                    logger.info("This will trigger retry mechanism")
                
                if not response:
                    logger.warning("Claude returned empty response")
                    raise RuntimeError("Claude returned empty response")
                
                return response
            else:
                error_msg = f"Claude command failed with return code {result.returncode}: {result.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
                
        except subprocess.TimeoutExpired:
            error_msg = "Claude command timed out"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except FileNotFoundError:
            error_msg = "Claude command not found. Please ensure Claude CLI is installed and in PATH."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            logger.error(f"Error executing Claude command: {str(e)}")
            raise
    
    def _extract_coordinates_from_element_id(self, element_id: str, ui_elements: List[UIElement]) -> Optional[List[int]]:
        """
        根据元素ID从UI元素列表中提取边界框中心点坐标
        
        Args:
            element_id: 元素ID（字符串形式，需转换为整数）
            ui_elements: UI元素列表
            
        Returns:
            Optional[List[int]]: [x, y] 中心点坐标，如果未找到则返回None
        """
        if not element_id or not ui_elements:
            return None
            
        try:
            # 元素ID可能是字符串，需要转换为整数
            element_id_int = int(element_id)
            
            # 在UI元素列表中查找对应的元素
            for element in ui_elements:
                if element.id == element_id_int:
                    coordinates = element.coordinates
                    if coordinates and len(coordinates) >= 4:
                        # 计算边界框中心点
                        x1, y1, x2, y2 = coordinates[:4]
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        logger.debug(f"Element {element_id} center coordinates: ({center_x}, {center_y})")
                        return [center_x, center_y]
                    else:
                        logger.warning(f"Element {element_id} has invalid coordinates: {coordinates}")
                        return None
            
            logger.warning(f"Element with ID {element_id} not found in UI elements list")
            return None
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid element_id format: {element_id}, error: {e}")
            return None
    
    def _parse_claude_response(self, response: str, ui_elements: List[UIElement]) -> Tuple[List[ActionPlan], str, float]:
        """
        解析Claude响应，生成ActionPlan列表
        
        Args:
            response: Claude响应文本
            ui_elements: UI元素列表（用于坐标验证）
            
        Returns:
            Tuple[List[ActionPlan], str, float]: (操作计划列表, 推理过程, 置信度)
        """
        if not response or response.strip() == "":
            logger.warning("Claude response is empty")
            return self._create_fallback_actions("Empty response"), "Claude response is empty", 0.1
        
        try:
            # 先尝试提取JSON部分（有时Claude会在响应中包含额外文本）
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                response_data = json.loads(json_str)
                
                reasoning = response_data.get("reasoning", "")
                confidence = float(response_data.get("confidence", 0.5))
                actions_data = response_data.get("actions", [])
                
                # 转换为ActionPlan对象
                actions = []
                for action_data in actions_data:
                    element_id = action_data.get("element_id")
                    coordinates = action_data.get("coordinates")
                    
                    # 如果有element_id但没有coordinates，尝试从UI元素中提取坐标
                    if element_id and not coordinates:
                        extracted_coords = self._extract_coordinates_from_element_id(element_id, ui_elements)
                        if extracted_coords:
                            coordinates = extracted_coords
                            logger.debug(f"Extracted coordinates {coordinates} for element_id {element_id}")
                    
                    action = ActionPlan(
                        type=action_data.get("type", ""),
                        description=action_data.get("description", ""),
                        element_id=element_id,
                        coordinates=coordinates,
                        text=action_data.get("text"),
                        duration=action_data.get("duration")
                    )
                    actions.append(action)
                
                logger.info(f"Parsed {len(actions)} actions from Claude response")
                return actions, reasoning, confidence
            else:
                # 没有找到JSON，尝试解析整个响应
                response_data = json.loads(response)
                
                reasoning = response_data.get("reasoning", "")
                confidence = float(response_data.get("confidence", 0.5))
                actions_data = response_data.get("actions", [])
                
                actions = []
                for action_data in actions_data:
                    element_id = action_data.get("element_id")
                    coordinates = action_data.get("coordinates")
                    
                    # 如果有element_id但没有coordinates，尝试从UI元素中提取坐标
                    if element_id and not coordinates:
                        extracted_coords = self._extract_coordinates_from_element_id(element_id, ui_elements)
                        if extracted_coords:
                            coordinates = extracted_coords
                            logger.debug(f"Extracted coordinates {coordinates} for element_id {element_id}")
                    
                    action = ActionPlan(
                        type=action_data.get("type", ""),
                        description=action_data.get("description", ""),
                        element_id=element_id,
                        coordinates=coordinates,
                        text=action_data.get("text"),
                        duration=action_data.get("duration")
                    )
                    actions.append(action)
                
                logger.info(f"Parsed {len(actions)} actions from Claude response")
                return actions, reasoning, confidence
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Claude response as JSON: {e}")
            logger.warning(f"Raw response length: {len(response)}")
            logger.warning(f"Raw response preview: {response[:500]}...")  # 增加预览长度
            
            # 尝试清理响应文本并重新解析
            cleaned_response = self._clean_claude_response(response)
            if cleaned_response != response:
                logger.info("尝试解析清理后的响应")
                try:
                    return self._parse_claude_response(cleaned_response, ui_elements)
                except Exception as clean_error:
                    logger.warning(f"清理后的响应解析也失败: {clean_error}")
            
            # 降级处理：基于文本内容创建简单操作
            return self._create_text_based_actions(response), f"Text-based parsing: {response[:100]}...", 0.4
        except Exception as e:
            logger.error(f"Error parsing Claude response: {str(e)}")
            return self._create_fallback_actions(response), f"Parsing error: {str(e)}", 0.2
    
    def _parse_completion_response(self, response: str) -> Tuple[str, str, float]:
        """
        解析Claude任务完成度验证响应
        
        Args:
            response: Claude响应文本
            
        Returns:
            Tuple[str, str, float]: (状态, 推理过程, 置信度)
        """
        if not response or response.strip() == "":
            logger.warning("Claude completion verification response is empty")
            return "incomplete", "Empty response from Claude", 0.0
        
        try:
            # 先尝试提取JSON部分
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                response_data = json.loads(json_str)
            else:
                # 尝试解析整个响应
                response_data = json.loads(response)
            
            status = response_data.get("status", "incomplete")
            reasoning = response_data.get("reasoning", "")
            confidence = float(response_data.get("confidence", 0.0))
            
            # 验证状态值
            valid_statuses = ["completed", "incomplete"]
            if status not in valid_statuses:
                logger.warning(f"Invalid status: {status}, defaulting to unclear")
                status = "incomplete"
            
            # 验证置信度范围
            confidence = max(0.0, min(1.0, confidence))
            
            logger.info(f"Parsed completion verification: status={status}, confidence={confidence:.2f}")
            return status, reasoning, confidence
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse completion response as JSON: {e}")
            logger.warning(f"Raw response: {response[:500]}...")
            
            # 尝试清理响应并重新解析
            cleaned_response = self._clean_claude_response(response)
            if cleaned_response != response:
                try:
                    return self._parse_completion_response(cleaned_response)
                except Exception:
                    pass
            
            # 降级处理：基于文本内容判断
            return self._extract_completion_from_text(response)
        except Exception as e:
            logger.error(f"Error parsing completion response: {str(e)}")
            return "incomplete", f"Parsing error: {str(e)}", 0.0
    
    def _extract_completion_from_text(self, response: str) -> Tuple[str, str, float]:
        """
        从文本响应中提取任务完成状态
        
        Args:
            response: Claude文本响应
            
        Returns:
            Tuple[str, str, float]: (状态, 推理过程, 置信度)
        """
        response_lower = response.lower()
        
        # 简单的关键词匹配
        if "completed" in response_lower or "完成" in response:
            return "completed", "基于文本分析：任务已完成", 0.6
        elif "incomplete" in response_lower or "未完成" in response:
            return "incomplete", "基于文本分析：任务未完成", 0.6
        elif "failed" in response_lower or "失败" in response:
            return "incomplete", "基于文本分析：任务执行失败", 0.6
        else:
            return "incomplete", f"无法从文本中确定状态: {response[:100]}...", 0.3
    
    def _extract_next_steps_from_response(self, response: str, status: str) -> Optional[str]:
        """
        从Claude响应中提取next_steps信息
        
        Args:
            response: Claude响应文本
            status: 任务状态
            
        Returns:
            Optional[str]: 下一步操作建议
        """
        try:
            # 如果任务已完成，不需要下一步操作
            if status == "completed":
                return None
                
            # 尝试从JSON中提取next_steps
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                response_data = json.loads(json_str)
                next_steps = response_data.get("next_steps")
                
                # 如果next_steps为null或空字符串，返回None
                if next_steps in [None, "null", ""]:
                    return None
                    
                return next_steps
            
        except Exception as e:
            logger.debug(f"Failed to extract next_steps from JSON: {e}")
        
        # 降级处理：根据状态提供默认建议
        if status == "incomplete":
            return "请继续执行剩余操作或检查当前操作结果"
        
        return None
    
    def _extract_next_actions_from_response(self, response: str, status: str) -> Optional[List[ActionPlan]]:
        """
        从Claude响应中提取next_actions操作指令
        
        Args:
            response: Claude响应文本
            status: 任务状态
            
        Returns:
            Optional[List[ActionPlan]]: 下一步操作指令列表
        """
        try:
            # 如果任务已完成，不需要后续操作
            if status == "completed":
                return None
                
            # 尝试从JSON中提取next_actions
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                response_data = json.loads(json_str)
                next_actions_data = response_data.get("next_actions")
                
                # 如果next_actions为null或空列表，返回None
                if not next_actions_data:
                    return None
                
                # 转换为ActionPlan对象
                actions = []
                for action_data in next_actions_data:
                    action = ActionPlan(
                        type=action_data.get("type", ""),
                        description=action_data.get("description", ""),
                        element_id=action_data.get("element_id"),
                        coordinates=action_data.get("coordinates"),
                        text=action_data.get("text"),
                        duration=action_data.get("duration"),
                        keys=action_data.get("keys")
                    )
                    actions.append(action)
                
                logger.info(f"Extracted {len(actions)} next actions from verification response")
                return actions
            
        except Exception as e:
            logger.debug(f"Failed to extract next_actions from JSON: {e}")
        
        # 降级处理：根据状态生成默认操作
        if status in ["incomplete"]:
            return [
                ActionPlan(
                    type="wait",
                    description="等待用户手动操作或重新分析任务",
                    duration=1.0
                )
            ]
        
        return None
    
    def _create_text_based_actions(self, response: str) -> List[ActionPlan]:
        """
        基于文本响应创建操作计划
        
        Args:
            response: Claude文本响应
            
        Returns:
            List[ActionPlan]: 从文本解析的操作计划列表
        """
        actions = []
        response_lower = response.lower()
        
        # 简单的关键词匹配
        if "点击" in response or "click" in response_lower:
            actions.append(ActionPlan(
                type="click",
                description="基于文本分析的点击操作",
                coordinates=[400, 300]  # 默认屏幕中心
            ))
        
        if "输入" in response or "type" in response_lower or "input" in response_lower:
            actions.append(ActionPlan(
                type="type",
                description="基于文本分析的输入操作",
                text="text input"
            ))
        
        if "等待" in response or "wait" in response_lower:
            actions.append(ActionPlan(
                type="wait",
                description="基于文本分析的等待操作",
                duration=2.0
            ))
        
        # 如果没有匹配到任何操作，返回默认操作
        if not actions:
            actions.append(ActionPlan(
                type="wait",
                description=f"无法解析的操作: {response[:50]}...",
                duration=1.0
            ))
        
        return actions
    
    def _clean_claude_response(self, response: str) -> str:
        """
        清理Claude响应文本，尝试提取有效的JSON部分
        
        Args:
            response: 原始Claude响应
            
        Returns:
            str: 清理后的响应文本
        """
        try:
            # 移除可能的markdown代码块标记
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*$', '', response)
            
            # 修复JSON中的引号问题
            # 1. 先找到reasoning字段的内容
            reasoning_match = re.search(r'"reasoning":\s*"([^"]*(?:"[^"]*"[^"]*)*)"', response)
            if reasoning_match:
                reasoning_content = reasoning_match.group(1)
                # 转义reasoning内容中的双引号
                escaped_reasoning = reasoning_content.replace('"', '\\"')
                response = response.replace(reasoning_match.group(0), f'"reasoning": "{escaped_reasoning}"')
            
            # 2. 处理description字段中的引号问题
            response = re.sub(r'"description":\s*"([^"]*)"([^"]*)"([^"]*)"', 
                            r'"description": "\1\\"\2\\"\3"', response)
            
            # 移除响应开头的说明文字
            lines = response.strip().split('\n')
            json_start_line = -1
            
            for i, line in enumerate(lines):
                if line.strip().startswith('{'):
                    json_start_line = i
                    break
            
            if json_start_line >= 0:
                # 从JSON开始的地方截取
                json_lines = lines[json_start_line:]
                cleaned_response = '\n'.join(json_lines)
                
                # 尝试找到JSON结束位置
                brace_count = 0
                json_end = -1
                in_string = False
                escape_next = False
                
                for i, char in enumerate(cleaned_response):
                    if escape_next:
                        escape_next = False
                        continue
                    
                    if char == '\\':
                        escape_next = True
                        continue
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                
                if json_end > 0:
                    cleaned_response = cleaned_response[:json_end]
                
                logger.debug(f"Cleaned response length: {len(cleaned_response)}")
                return cleaned_response.strip()
            
            return response
            
        except Exception as e:
            logger.warning(f"Error cleaning Claude response: {e}")
            return response

    def _create_fallback_actions(self, response: str) -> List[ActionPlan]:
        """
        创建降级操作计划（当Claude响应解析失败时）
        
        Args:
            response: 原始响应文本
            
        Returns:
            List[ActionPlan]: 基本操作计划列表
        """
        return [
            ActionPlan(
                type="wait",
                description="等待用户手动操作（Claude响应解析失败）",
                duration=1.0
            )
        ]
    
    def _parse_completion_response_enhanced(self, response: str, ui_elements: Optional[List[UIElement]] = None) -> Tuple[str, str, float, Optional[str], Optional[List[Dict]]]:
        """
        增强版Claude任务完成度验证响应解析（支持next_steps和next_actions）
        
        Args:
            response: Claude响应文本
            ui_elements: UI元素列表（用于坐标提取）
            
        Returns:
            Tuple[str, str, float, Optional[str], Optional[List[Dict]]]: (状态, 推理过程, 置信度, 下一步建议, 下一步操作)
        """
        if not response or response.strip() == "":
            logger.warning("Claude completion verification response is empty")
            return "incomplete", "Empty response from Claude", 0.0, None, None
        
        try:
            # 先尝试提取JSON部分
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                response_data = json.loads(json_str)
            else:
                # 尝试解析整个响应
                response_data = json.loads(response)
            
            # 记录Claude原始响应用于调试
            logger.info(f"Claude verification response keys: {list(response_data.keys())}")
            logger.debug(f"Claude verification full response: {response_data}")
            
            status = response_data.get("status", "incomplete")
            reasoning = response_data.get("reasoning", "")
            confidence = float(response_data.get("confidence", 0.0))
            next_steps = response_data.get("next_steps")
            next_actions = response_data.get("next_actions")  # 直接从Claude响应中获取
            
            # 处理next_actions中的element_id，提取坐标信息
            if next_actions and isinstance(next_actions, list) and ui_elements:
                processed_actions = []
                for action_data in next_actions:
                    if isinstance(action_data, dict):
                        element_id = action_data.get("element_id")
                        coordinates = action_data.get("coordinates")
                        
                        # 如果有element_id但没有coordinates，尝试从UI元素中提取坐标
                        if element_id and not coordinates:
                            extracted_coords = self._extract_coordinates_from_element_id(element_id, ui_elements)
                            if extracted_coords:
                                # 创建新的action_data副本，添加坐标信息
                                action_data = action_data.copy()
                                action_data["coordinates"] = extracted_coords
                                logger.debug(f"Enhanced completion: Extracted coordinates {extracted_coords} for element_id {element_id}")
                        
                        processed_actions.append(action_data)
                    else:
                        processed_actions.append(action_data)
                
                next_actions = processed_actions
                logger.info(f"Enhanced completion: Processed {len(processed_actions)} next_actions with coordinate extraction")
            
            # 详细记录next_actions信息
            if next_actions is not None:
                logger.info(f"Claude returned next_actions: {type(next_actions)}, length: {len(next_actions) if isinstance(next_actions, list) else 'N/A'}")
                if isinstance(next_actions, list) and len(next_actions) > 0:
                    logger.info(f"First action: {next_actions[0]}")
            else:
                logger.warning("Claude did not return next_actions field")
            
            # 验证状态值
            valid_statuses = ["completed", "incomplete"]
            if status not in valid_statuses:
                logger.warning(f"Invalid status: {status}, defaulting to unclear")
                status = "incomplete"
            
            # 验证置信度范围
            confidence = max(0.0, min(1.0, confidence))
            
            
            logger.info(f"Enhanced completion parsing: status={status}, confidence={confidence:.2f}, has_next_steps={next_steps is not None}, has_next_actions={next_actions is not None and len(next_actions) > 0 if next_actions else False}")
            return status, reasoning, confidence, next_steps, next_actions
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse enhanced completion response as JSON: {e}")
            logger.warning(f"Raw response: {response[:500]}...")
            
            # 尝试清理响应并重新解析
            cleaned_response = self._clean_claude_response(response)
            if cleaned_response != response:
                try:
                    return self._parse_completion_response_enhanced(cleaned_response, ui_elements)
                except Exception:
                    pass
            
            # 降级处理：基于文本内容判断
            status, reasoning, confidence = self._extract_completion_from_text(response)
            next_steps = self._extract_next_steps_from_text(response, status)
            # 降级情况下不生成具体操作，让用户手动处理
            next_actions = None
            
            return status, reasoning, confidence, next_steps, next_actions
        except Exception as e:
            logger.error(f"Error parsing enhanced completion response: {str(e)}")
            return "incomplete", f"Parsing error: {str(e)}", 0.0, None, None
    
    def _extract_next_steps_from_text(self, response: str, status: str) -> Optional[str]:
        """
        从文本响应中提取next_steps信息
        
        Args:
            response: Claude响应文本
            status: 任务状态
            
        Returns:
            Optional[str]: 下一步操作建议
        """
        if status != "incomplete":
            return None
        
        # 查找包含下一步建议的常见模式
        patterns = [
            r"建议下一步[：:]\s*(.+)",
            r"下一步[操作行动][：:]\s*(.+)",
            r"需要[：:]\s*(.+)",
            r"建议[：:]\s*(.+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # 如果没有找到特定模式，返回通用建议
        return "继续执行原始任务指令"
    
    def cleanup(self):
        """清理临时文件（保留img目录）"""
        try:
            # 只清理分析生成的临时图片，保留img目录
            analysis_files = [f for f in os.listdir(self.img_dir) if f.startswith('analysis_')]
            for file in analysis_files:
                file_path = os.path.join(self.img_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.debug(f"Cleaned up analysis file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup analysis files: {e}")
    
    def __del__(self):
        """析构函数，自动清理"""
        self.cleanup()