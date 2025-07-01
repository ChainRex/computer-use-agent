"""
Claude服务 - 集成Claude模型进行智能任务分析和操作指令生成
"""

import subprocess
import tempfile
import os
import base64
import json
import logging
from typing import Dict, List, Optional, Tuple
from PIL import Image
import io

from shared.schemas.data_models import ActionPlan, UIElement

logger = logging.getLogger(__name__)

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
        logger.info(f"Claude service initialized with img dir: {self.img_dir}")
    
    def analyze_task_with_claude(
        self, 
        text_command: str, 
        screenshot_base64: str, 
        ui_elements: List[UIElement],
        annotated_screenshot_base64: Optional[str] = None
    ) -> Tuple[List[ActionPlan], str, float]:
        """
        使用Claude分析任务并生成pyautogui操作指令
        
        Args:
            text_command: 用户文本指令
            screenshot_base64: 原始截图的base64编码
            ui_elements: 检测到的UI元素列表
            annotated_screenshot_base64: 标注后的截图base64编码（可选）
            
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
            prompt = self._build_analysis_prompt(text_command, ui_elements)
            
            # 执行Claude命令
            claude_response = self._execute_claude_command(prompt, image_path)
            
            # 解析Claude响应
            actions, reasoning, confidence = self._parse_claude_response(claude_response, ui_elements)
            
            return actions, reasoning, confidence
            
        except Exception as e:
            logger.error(f"Claude analysis failed: {str(e)}")
            raise
    
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
    
    def _build_analysis_prompt(self, text_command: str, ui_elements: List[UIElement]) -> str:
        """
        构建Claude分析提示
        
        Args:
            text_command: 用户指令
            ui_elements: UI元素列表
            
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
        
        prompt = f"""请分析这个计算机屏幕截图和用户指令，生成详细的pyautogui操作步骤。

用户指令: {text_command}

检测到的UI元素:
{elements_text}

请提供JSON格式的响应，包含以下字段:
{{
    "reasoning": "你的分析推理过程",
    "confidence": 0.8,
    "actions": [
        {{
            "type": "click",
            "description": "点击描述",
            "coordinates": [x, y],
            "element_id": "元素ID（如果适用）"
        }},
        {{
            "type": "type",
            "description": "输入描述", 
            "text": "要输入的文本"
        }},
        {{
            "type": "key",
            "description": "按键描述",
            "text": "按键组合，如'ctrl+c'或'enter'"
        }},
        {{
            "type": "wait",
            "description": "等待描述",
            "duration": 1.0
        }}
    ]
}}

操作类型说明:
- click: 点击操作，需要提供coordinates [x, y]
- type: 文本输入操作，需要提供text
- key: 按键操作，需要提供按键组合text
- wait: 等待操作，需要提供duration（秒）

请确保:
1. 操作步骤逻辑正确且可执行
2. 点击坐标基于检测到的UI元素
3. 考虑操作之间的时序关系
4. 提供清晰的操作描述"""

        return prompt
    
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
            # 构建Claude命令
            cmd = [
                "claude",
                "-p", prompt,
                image_path
            ]
            
            logger.debug(f"Executing Claude command: {' '.join(cmd)}")
            
            # 执行命令（5分钟超时）
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.debug("Claude command executed successfully")
                response = result.stdout.strip()
                logger.debug(f"Claude raw response: {response[:500]}...")  # 打印前500字符用于调试
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
                    action = ActionPlan(
                        type=action_data.get("type", ""),
                        description=action_data.get("description", ""),
                        element_id=action_data.get("element_id"),
                        coordinates=action_data.get("coordinates"),
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
                    action = ActionPlan(
                        type=action_data.get("type", ""),
                        description=action_data.get("description", ""),
                        element_id=action_data.get("element_id"),
                        coordinates=action_data.get("coordinates"),
                        text=action_data.get("text"),
                        duration=action_data.get("duration")
                    )
                    actions.append(action)
                
                logger.info(f"Parsed {len(actions)} actions from Claude response")
                return actions, reasoning, confidence
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Raw response: {response[:200]}...")
            # 降级处理：基于文本内容创建简单操作
            return self._create_text_based_actions(response), f"Text-based parsing: {response[:100]}...", 0.4
        except Exception as e:
            logger.error(f"Error parsing Claude response: {str(e)}")
            return self._create_fallback_actions(response), f"Parsing error: {str(e)}", 0.2
    
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