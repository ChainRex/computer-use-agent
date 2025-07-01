"""
安全控制器 - 实现自动化执行的安全控制和用户确认机制
"""

import time
import logging
import re
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# 添加项目根目录到Python路径
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.schemas.data_models import ActionPlan, UIElement

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"           # 低风险，可以自动执行
    MEDIUM = "medium"     # 中等风险，需要用户确认
    HIGH = "high"         # 高风险，强制用户确认
    CRITICAL = "critical" # 极高风险，禁止执行

@dataclass
class SafetyRule:
    """安全规则"""
    name: str
    description: str
    pattern: str          # 匹配模式（正则表达式或关键词）
    risk_level: RiskLevel
    applies_to: List[str] # 适用的操作类型
    enabled: bool = True

@dataclass
class SafetyAssessment:
    """安全评估结果"""
    action_index: int
    action: ActionPlan
    risk_level: RiskLevel
    triggered_rules: List[SafetyRule]
    requires_confirmation: bool
    block_execution: bool
    warning_message: str
    assessment_time: float

class SafetyController:
    """安全控制器"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化安全控制器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        
        # 安全配置
        self.strict_mode = self.config.get('strict_mode', False)
        self.require_confirmation_for_medium = self.config.get('require_confirmation_for_medium', True)
        self.block_high_risk = self.config.get('block_high_risk', False)
        self.block_critical_risk = self.config.get('block_critical_risk', True)
        
        # 初始化安全规则
        self.safety_rules = self._initialize_safety_rules()
        
        # 用户自定义规则
        self.custom_rules = []
        
        # 执行统计
        self.execution_stats = {
            'total_actions': 0,
            'blocked_actions': 0,
            'confirmed_actions': 0,
            'auto_executed_actions': 0
        }
        
        logger.info("SafetyController initialized")
    
    def _initialize_safety_rules(self) -> List[SafetyRule]:
        """初始化默认安全规则"""
        rules = [
            # 文件操作相关
            SafetyRule(
                name="文件删除操作",
                description="检测可能的文件删除操作",
                pattern=r"(删除|delete|remove|rm|del).*文件|文件.*删除",
                risk_level=RiskLevel.HIGH,
                applies_to=["key", "type"]
            ),
            
            SafetyRule(
                name="格式化操作",
                description="检测磁盘格式化等危险操作",
                pattern=r"(格式化|format|fdisk|mkfs)",
                risk_level=RiskLevel.CRITICAL,
                applies_to=["key", "type"]
            ),
            
            SafetyRule(
                name="系统关机",
                description="检测系统关机或重启操作",
                pattern=r"(关机|重启|shutdown|restart|reboot)",
                risk_level=RiskLevel.HIGH,
                applies_to=["key", "type"]
            ),
            
            # 网络和安全相关
            SafetyRule(
                name="密码输入",
                description="检测密码输入操作",
                pattern=r"(密码|password|passwd|pwd)",
                risk_level=RiskLevel.MEDIUM,
                applies_to=["type"]
            ),
            
            SafetyRule(
                name="管理员权限",
                description="检测管理员权限提升",
                pattern=r"(sudo|admin|administrator|管理员)",
                risk_level=RiskLevel.HIGH,
                applies_to=["key", "type"]
            ),
            
            SafetyRule(
                name="网络配置",
                description="检测网络配置修改",
                pattern=r"(网络|network|wifi|ip.*config|防火墙|firewall)",
                risk_level=RiskLevel.MEDIUM,
                applies_to=["type", "key"]
            ),
            
            # 应用程序相关
            SafetyRule(
                name="浏览器隐私",
                description="检测浏览器隐私相关操作",
                pattern=r"(清除.*历史|清除.*缓存|隐私|privacy|clear.*history)",
                risk_level=RiskLevel.MEDIUM,
                applies_to=["click", "key"]
            ),
            
            SafetyRule(
                name="软件安装",
                description="检测软件安装操作",
                pattern=r"(安装|install|setup\.exe|\.msi|\.pkg|\.deb|\.rpm)",
                risk_level=RiskLevel.MEDIUM,
                applies_to=["click", "type"]
            ),
            
            # 金融和支付相关
            SafetyRule(
                name="支付操作",
                description="检测支付相关操作",
                pattern=r"(支付|付款|转账|pay|payment|transfer|银行|bank)",
                risk_level=RiskLevel.CRITICAL,
                applies_to=["click", "type"]
            ),
            
            SafetyRule(
                name="信用卡信息",
                description="检测信用卡信息输入",
                pattern=r"(\d{4}[\s-]*\d{4}[\s-]*\d{4}[\s-]*\d{4}|信用卡|credit.*card|cvv|cvc)",
                risk_level=RiskLevel.CRITICAL,
                applies_to=["type"]
            ),
            
            # 系统设置相关
            SafetyRule(
                name="注册表操作",
                description="检测注册表编辑",
                pattern=r"(注册表|regedit|registry)",
                risk_level=RiskLevel.HIGH,
                applies_to=["type", "key"]
            ),
            
            SafetyRule(
                name="系统文件",
                description="检测系统文件操作",
                pattern=r"(system32|windows|boot|etc|usr|bin)",
                risk_level=RiskLevel.HIGH,
                applies_to=["type", "click"]
            ),
            
            # 快捷键相关
            SafetyRule(
                name="危险快捷键",
                description="检测危险快捷键组合",
                pattern=r"(alt\+f4|ctrl\+alt\+del|cmd\+q)",
                risk_level=RiskLevel.MEDIUM,
                applies_to=["key", "hotkey"]
            ),
            
            # 坐标相关安全检查
            SafetyRule(
                name="屏幕边缘点击",
                description="检测屏幕边缘的潜在危险点击",
                pattern="screen_edge_click",  # 特殊标识，在assess_coordinate_safety中处理
                risk_level=RiskLevel.LOW,
                applies_to=["click", "double_click", "right_click"]
            )
        ]
        
        return rules
    
    def assess_action_safety(self, action: ActionPlan, action_index: int, 
                           ui_elements: List[UIElement] = None) -> SafetyAssessment:
        """
        评估操作的安全性
        
        Args:
            action: 要评估的操作
            action_index: 操作索引
            ui_elements: UI元素列表
            
        Returns:
            SafetyAssessment: 安全评估结果
        """
        start_time = time.time()
        triggered_rules = []
        max_risk_level = RiskLevel.LOW
        
        try:
            # 检查文本内容安全性
            if action.description:
                text_rules = self._check_text_safety(action.description, action.type)
                triggered_rules.extend(text_rules)
            
            if action.text:
                text_rules = self._check_text_safety(action.text, action.type)
                triggered_rules.extend(text_rules)
            
            # 检查坐标安全性
            if action.coordinates:
                coord_rules = self._check_coordinate_safety(action, ui_elements)
                triggered_rules.extend(coord_rules)
            
            # 检查UI元素安全性
            if action.element_id and ui_elements:
                element_rules = self._check_element_safety(action, ui_elements)
                triggered_rules.extend(element_rules)
            
            # 检查操作类型安全性
            type_rules = self._check_action_type_safety(action)
            triggered_rules.extend(type_rules)
            
            # 确定最高风险等级
            if triggered_rules:
                risk_levels = [rule.risk_level for rule in triggered_rules]
                max_risk_level = max(risk_levels, key=lambda x: list(RiskLevel).index(x))
            
            # 确定是否需要确认和是否阻止执行
            requires_confirmation = self._requires_confirmation(max_risk_level)
            block_execution = self._should_block_execution(max_risk_level)
            
            # 生成警告消息
            warning_message = self._generate_warning_message(action, triggered_rules, max_risk_level)
            
            assessment_time = time.time() - start_time
            
            # 更新统计
            self.execution_stats['total_actions'] += 1
            if block_execution:
                self.execution_stats['blocked_actions'] += 1
            elif requires_confirmation:
                self.execution_stats['confirmed_actions'] += 1
            else:
                self.execution_stats['auto_executed_actions'] += 1
            
            return SafetyAssessment(
                action_index=action_index,
                action=action,
                risk_level=max_risk_level,
                triggered_rules=triggered_rules,
                requires_confirmation=requires_confirmation,
                block_execution=block_execution,
                warning_message=warning_message,
                assessment_time=assessment_time
            )
            
        except Exception as e:
            logger.error(f"安全评估失败: {e}")
            assessment_time = time.time() - start_time
            
            # 出错时采用保守策略
            return SafetyAssessment(
                action_index=action_index,
                action=action,
                risk_level=RiskLevel.HIGH,
                triggered_rules=[],
                requires_confirmation=True,
                block_execution=False,
                warning_message=f"安全评估异常: {str(e)}，建议手动确认",
                assessment_time=assessment_time
            )
    
    def _check_text_safety(self, text: str, action_type: str) -> List[SafetyRule]:
        """检查文本内容安全性"""
        triggered_rules = []
        text_lower = text.lower()
        
        for rule in self.safety_rules + self.custom_rules:
            if not rule.enabled or action_type not in rule.applies_to:
                continue
            
            # 检查是否匹配规则
            if self._matches_pattern(text_lower, rule.pattern):
                triggered_rules.append(rule)
                logger.debug(f"文本 '{text}' 触发安全规则: {rule.name}")
        
        return triggered_rules
    
    def _check_coordinate_safety(self, action: ActionPlan, ui_elements: List[UIElement]) -> List[SafetyRule]:
        """检查坐标安全性"""
        triggered_rules = []
        
        if not action.coordinates:
            return triggered_rules
        
        # 检查是否在屏幕边缘（可能是意外点击）
        x, y = action.click_position or (0, 0)
        
        try:
            import pyautogui
            screen_width, screen_height = pyautogui.size()
            
            edge_threshold = 20  # 边缘阈值
            
            if (x <= edge_threshold or x >= screen_width - edge_threshold or
                y <= edge_threshold or y >= screen_height - edge_threshold):
                
                for rule in self.safety_rules:
                    if rule.pattern == "screen_edge_click" and action.type in rule.applies_to:
                        triggered_rules.append(rule)
                        break
        
        except Exception as e:
            logger.warning(f"屏幕尺寸检查失败: {e}")
        
        return triggered_rules
    
    def _check_element_safety(self, action: ActionPlan, ui_elements: List[UIElement]) -> List[SafetyRule]:
        """检查UI元素安全性"""
        triggered_rules = []
        
        # 查找目标元素
        target_element = None
        for elem in ui_elements:
            if str(elem.id) == str(action.element_id):
                target_element = elem
                break
        
        if not target_element:
            return triggered_rules
        
        # 检查元素描述和文本
        for text in [target_element.description, target_element.text]:
            if text:
                text_rules = self._check_text_safety(text, action.type)
                triggered_rules.extend(text_rules)
        
        return triggered_rules
    
    def _check_action_type_safety(self, action: ActionPlan) -> List[SafetyRule]:
        """检查操作类型安全性"""
        triggered_rules = []
        
        # 检查特定操作类型的风险
        high_risk_types = ['key', 'hotkey']  # 快捷键操作风险较高
        
        if action.type in high_risk_types and self.strict_mode:
            # 在严格模式下，快捷键操作需要额外检查
            pass  # 这里可以添加额外的检查逻辑
        
        return triggered_rules
    
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """检查文本是否匹配模式"""
        try:
            # 尝试正则表达式匹配
            return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error:
            # 如果不是有效的正则表达式，进行简单的关键词匹配
            return pattern.lower() in text.lower()
    
    def _requires_confirmation(self, risk_level: RiskLevel) -> bool:
        """判断是否需要用户确认"""
        if risk_level == RiskLevel.LOW:
            return False
        elif risk_level == RiskLevel.MEDIUM:
            return self.require_confirmation_for_medium
        elif risk_level == RiskLevel.HIGH:
            return True
        elif risk_level == RiskLevel.CRITICAL:
            return True
        
        return True  # 默认需要确认
    
    def _should_block_execution(self, risk_level: RiskLevel) -> bool:
        """判断是否应该阻止执行"""
        if risk_level == RiskLevel.CRITICAL and self.block_critical_risk:
            return True
        elif risk_level == RiskLevel.HIGH and self.block_high_risk:
            return True
        
        return False
    
    def _generate_warning_message(self, action: ActionPlan, triggered_rules: List[SafetyRule], 
                                risk_level: RiskLevel) -> str:
        """生成警告消息"""
        if not triggered_rules:
            return ""
        
        risk_descriptions = {
            RiskLevel.LOW: "低风险",
            RiskLevel.MEDIUM: "中等风险", 
            RiskLevel.HIGH: "高风险",
            RiskLevel.CRITICAL: "极高风险"
        }
        
        risk_desc = risk_descriptions.get(risk_level, "未知风险")
        
        messages = [f"⚠️ 检测到{risk_desc}操作:"]
        
        # 添加触发的规则信息
        for rule in triggered_rules[:3]:  # 最多显示3个规则
            messages.append(f"• {rule.name}: {rule.description}")
        
        if len(triggered_rules) > 3:
            messages.append(f"• ... 还有 {len(triggered_rules) - 3} 个安全规则被触发")
        
        # 添加操作信息
        messages.append(f"\n操作详情:")
        messages.append(f"• 类型: {action.type}")
        messages.append(f"• 描述: {action.description}")
        
        if action.text:
            messages.append(f"• 文本: '{action.text}'")
        
        return "\n".join(messages)
    
    def add_custom_rule(self, rule: SafetyRule):
        """添加自定义安全规则"""
        self.custom_rules.append(rule)
        logger.info(f"添加自定义安全规则: {rule.name}")
    
    def remove_custom_rule(self, rule_name: str) -> bool:
        """移除自定义安全规则"""
        for i, rule in enumerate(self.custom_rules):
            if rule.name == rule_name:
                del self.custom_rules[i]
                logger.info(f"移除自定义安全规则: {rule_name}")
                return True
        return False
    
    def enable_rule(self, rule_name: str) -> bool:
        """启用安全规则"""
        for rule in self.safety_rules + self.custom_rules:
            if rule.name == rule_name:
                rule.enabled = True
                logger.info(f"启用安全规则: {rule_name}")
                return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """禁用安全规则"""
        for rule in self.safety_rules + self.custom_rules:
            if rule.name == rule_name:
                rule.enabled = False
                logger.info(f"禁用安全规则: {rule_name}")
                return True
        return False
    
    def get_all_rules(self) -> List[SafetyRule]:
        """获取所有安全规则"""
        return self.safety_rules + self.custom_rules
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        stats = self.execution_stats.copy()
        if stats['total_actions'] > 0:
            stats['auto_execution_rate'] = stats['auto_executed_actions'] / stats['total_actions']
            stats['confirmation_rate'] = stats['confirmed_actions'] / stats['total_actions']
            stats['block_rate'] = stats['blocked_actions'] / stats['total_actions']
        else:
            stats['auto_execution_rate'] = 0.0
            stats['confirmation_rate'] = 0.0
            stats['block_rate'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """重置执行统计"""
        self.execution_stats = {
            'total_actions': 0,
            'blocked_actions': 0,
            'confirmed_actions': 0,
            'auto_executed_actions': 0
        }
        logger.info("执行统计已重置")
    
    def update_config(self, config: Dict[str, Any]):
        """更新安全配置"""
        self.config.update(config)
        
        # 更新相关设置
        self.strict_mode = self.config.get('strict_mode', self.strict_mode)
        self.require_confirmation_for_medium = self.config.get('require_confirmation_for_medium', self.require_confirmation_for_medium)
        self.block_high_risk = self.config.get('block_high_risk', self.block_high_risk)
        self.block_critical_risk = self.config.get('block_critical_risk', self.block_critical_risk)
        
        logger.info("安全配置已更新")