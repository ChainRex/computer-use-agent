# Claude Integration Module Documentation

## 模块概述

Claude集成模块为Computer Use Agent系统提供智能任务分析和操作指令生成功能。该模块通过Claude CLI集成，实现从用户文本指令到具体pyautogui操作的智能转换。

## 核心功能

### 1. 智能任务分析
- **输入**: 用户文本指令 + 屏幕截图 + UI元素列表 + 操作系统信息
- **输出**: 结构化的操作计划（ActionPlan列表）
- **AI推理**: 包含分析过程和置信度评估

### 2. 跨平台操作支持
- **Windows**: 支持Win+R、Alt+Tab等Windows特定快捷键
- **macOS**: 支持Cmd+Space、Cmd+Tab等Mac特定快捷键  
- **Linux**: 支持各种Linux桌面环境的快捷键
- **自适应**: 根据客户端操作系统动态调整操作策略

### 3. 元素基础操作
- **精确定位**: 通过UI元素ID而非坐标进行操作
- **智能选择**: 基于OmniParser检测结果选择最合适的UI元素
- **容错处理**: 当目标元素不可用时提供替代方案

## 技术架构

### 客户端增强 (`client/ui/main_window.py`)

#### 操作系统检测
```python
def _get_os_info(self):
    """获取操作系统信息"""
    return {
        "system": platform.system(),        # Windows/Darwin/Linux
        "version": platform.version(),      # 系统版本
        "release": platform.release(),      # 发行版本
        "machine": platform.machine(),      # 硬件架构
        "processor": platform.processor(),  # 处理器信息
        "platform": platform.platform()    # 完整平台信息
    }
```

#### UI显示增强
- **元素ID显示**: `[元素ID: element_123]`
- **操作类型**: click, type, key, wait等
- **详细参数**: 坐标、文本、时长等完整信息

### 服务端核心 (`server/claude/claude_service.py`)

#### 重试机制
```python
# 配置参数
max_retries = 3          # 最大重试次数
retry_delay = 2.0        # 重试延迟（指数退避）
timeout = 300           # 单次执行超时（5分钟）
```

#### JSON响应清理
- **引号转义**: 自动处理reasoning字段中的双引号问题
- **格式提取**: 智能提取JSON部分，忽略额外文本
- **语法修复**: 自动修复常见的JSON格式错误

#### 提示词工程
```python
prompt = f"""请分析这个计算机屏幕截图和用户指令，生成详细的pyautogui操作步骤。

用户指令: {text_command}
操作系统: {os_text}

检测到的UI元素:
{elements_text}

JSON格式要求:
1. 只输出JSON，不要添加任何说明文字或markdown标记
2. reasoning和description字段中不要使用双引号，用单引号或中文标点
3. 对于点击操作，必须使用element_id引用上面列出的UI元素
4. 根据操作系统调整操作方式和界面元素识别策略
"""
```

### 数据模型 (`shared/schemas/data_models.py`)

#### OSInfo模型
```python
class OSInfo(BaseModel):
    system: str      # 操作系统类型
    version: str     # 系统版本  
    release: str     # 发行版本
    machine: str     # 硬件架构
    processor: str   # 处理器信息
    platform: str    # 完整平台信息
    error: Optional[str] = None
```

#### ActionPlan增强
```python
class ActionPlan(BaseModel):
    type: Union[ActionType, str]
    description: str
    element_id: Optional[str] = None    # UI元素引用
    coordinates: Optional[List[Union[int, float]]] = None
    text: Optional[str] = None
    duration: Optional[float] = None
    # ... 其他操作相关字段
```

## 操作流程

### 1. 客户端发起请求
```python
request = {
    "type": "analyze_task",
    "task_id": task_id,
    "timestamp": time.time(),
    "data": {
        "text_command": "帮我打开计算器",
        "screenshot_base64": screenshot_data,
        "user_id": "default",
        "os_info": {
            "system": "Windows",
            "version": "10.0.19042",
            # ... 其他OS信息
        }
    }
}
```

### 2. 服务端分阶段处理
1. **OmniParser阶段**: 检测UI元素，发送`omniparser_result`
2. **Claude分析阶段**: AI智能分析，发送`claude_result`  
3. **最终结果**: 发送`analysis_result`完成任务

### 3. Claude智能分析
```python
# 构建包含操作系统信息的提示词
prompt = build_analysis_prompt(text_command, ui_elements, os_info)

# 执行Claude命令（带重试）
response = execute_claude_command_with_retry(prompt, image_path)

# 解析并验证响应
actions, reasoning, confidence = parse_claude_response(response)
```

### 4. 客户端结果显示
```
🎮 生成的操作计划 (2个步骤):
1. key: 使用Windows搜索快捷键打开搜索 [元素ID: search_key]
2. type: 输入计算器进行搜索 [文本: '计算器']
```

## 错误处理策略

### 1. 网络层错误
- **连接超时**: WebSocket自动重连，指数退避
- **响应超时**: 7分钟超时配置，适应Claude长时间处理

### 2. Claude响应错误
- **空响应**: 自动重试，最多3次
- **JSON格式错误**: 自动清理和修复
- **内容验证失败**: 降级到文本解析模式

### 3. 操作系统兼容性
- **未知系统**: 使用通用操作策略
- **权限问题**: 提供替代操作方案
- **API不可用**: 优雅降级到简单模式

## 性能优化

### 1. 响应时间优化
- **分阶段显示**: OmniParser结果立即显示，Claude结果异步更新
- **缓存机制**: 图像和分析结果缓存
- **并发处理**: 截图和分析并行执行

### 2. 资源管理
- **内存控制**: 及时释放图像资源
- **线程安全**: 使用适当的锁机制
- **超时控制**: 防止资源长期占用

### 3. 用户体验
- **实时反馈**: 显示处理进度和状态
- **错误提示**: 友好的错误信息和恢复建议
- **操作预览**: 显示将要执行的操作详情

## 配置选项

### Claude服务配置
```python
claude_config = {
    'max_retries': 3,           # 最大重试次数
    'retry_delay': 2.0,         # 重试延迟
    'timeout': 300,             # 命令超时
    'img_dir': '/path/to/img'   # 图像存储目录
}
```

### WebSocket配置
```python
websocket_config = {
    'ping_interval': 60,        # 心跳间隔
    'ping_timeout': 30,         # 心跳超时
    'receive_timeout': 420.0    # 接收超时（7分钟）
}
```

## 调试和监控

### 日志记录
```python
# Claude服务日志
logger.info(f"Claude分析开始: {text_command}")
logger.debug(f"OS信息: {os_info}")
logger.warning(f"重试第{attempt}次")
logger.error(f"解析失败: {error}")
```

### 性能指标
- **响应时间**: OmniParser + Claude总处理时间
- **成功率**: 操作计划生成成功率
- **重试率**: Claude调用重试频率
- **错误分类**: 不同类型错误的统计

## 未来扩展

### 1. 多模态输入
- **语音指令**: 集成语音识别
- **手势控制**: 视觉手势识别
- **上下文记忆**: 多轮对话支持

### 2. 执行引擎
- **pyautogui集成**: 自动执行生成的操作
- **安全控制**: 操作权限和安全检查
- **结果验证**: 执行结果的自动验证

### 3. 学习优化
- **操作历史**: 记录和分析用户操作模式
- **模型微调**: 基于使用反馈优化提示词
- **个性化**: 用户特定的操作偏好学习

## 版本历史

### v1.2.0 (当前版本)
- ✅ 添加操作系统信息支持
- ✅ 实现Claude调用重试机制
- ✅ 优化JSON响应解析
- ✅ 增强UI显示元素ID
- ✅ 跨平台快捷键支持

### v1.1.0
- ✅ Claude CLI基础集成
- ✅ 分阶段结果显示
- ✅ WebSocket通信优化

### v1.0.0
- ✅ 基础架构搭建
- ✅ OmniParser集成
- ✅ 客户端服务端通信