# Computer Use Agent 详细技术方案

## 项目概述

本项目旨在开发一个基于语音交互的计算机自动化操作系统，用户可以通过语音指令让AI助手完成屏幕操作任务（如打开计算器进行计算）。

## 总体架构

```
┌─────────────────────────────────┐    WebSocket/HTTP    ┌─────────────────┐
│         PyQt客户端              │ ←─────────────────→ │    服务端集群    │
│                                 │                      │                 │
│ • 语音输入/输出                  │                      │ • 语音识别      │
│ • 屏幕截图                      │                      │ • OmniParser    │
│ • 界面展示                      │                      │ • Claude推理    │
│ • 自动化执行引擎 (pyautogui)     │                      │ • 语音合成      │
│ • 结果验证                      │                      │ • 任务编排      │
└─────────────────────────────────┘                      └─────────────────┘
                                                                │
                                                         ┌─────────────┐
                                                         │  n8n编排    │
                                                         │  工作流     │
                                                         └─────────────┘
```

**架构修正说明**：
- **客户端**：负责界面交互、屏幕操作执行、结果验证
- **服务端**：负责AI模型推理（语音识别、图像解析、文本生成、语音合成）
- **数据流**：客户端采集数据 → 服务端AI处理 → 返回执行计划 → 客户端执行操作

## 模块详细设计

### 1. 项目结构设计

```
computer-use-agent/
├── client/                    # 客户端代码
│   ├── ui/                   # PyQt界面
│   ├── audio/                # 语音录制和播放
│   ├── screenshot/           # 屏幕截图
│   ├── automation/           # 自动化执行引擎 (pyautogui)
│   ├── verification/         # 执行结果验证
│   ├── communication/        # 客户端通信
│   └── main.py              # 客户端入口
├── server/                   # 服务端代码
│   ├── api/                 # FastAPI接口
│   ├── models/              # AI模型服务
│   │   ├── speech/          # 语音识别和合成
│   │   ├── vision/          # OmniParser集成
│   │   └── claude/          # Claude API集成
│   ├── workflows/           # n8n工作流
│   └── main.py             # 服务端入口
├── shared/                  # 共享代码
│   ├── protocols/           # 通信协议
│   ├── utils/              # 工具函数
│   └── schemas/            # 数据模型
├── docker/                 # 容器化配置
├── tests/                  # 测试代码
└── docs/                   # 文档
```

### 2. 客户端模块（PyQt）

#### 2.1 主界面设计（client/ui/main_window.py）

**技术选型**: PyQt6 + QML（可选，用于现代化UI）

**核心功能**:
- 语音录制按钮（按住说话/点击切换）
- 实时状态显示（录音中、处理中、执行中）
- 任务历史记录
- 设置面板（服务器地址、模型配置等）

**关键组件**:
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.voice_recorder = VoiceRecorder()
        self.screenshot_manager = ScreenshotManager() 
        self.server_client = ServerClient()
        self.setup_ui()
        
    def setup_ui(self):
        # 语音按钮
        self.voice_button = QPushButton("按住说话")
        # 状态显示
        self.status_label = QLabel("就绪")
        # 历史记录
        self.history_list = QListWidget()
```

#### 2.2 语音处理模块（client/audio/）

**音频录制（audio_recorder.py）**:
- 使用pyaudio进行实时音频采集
- 支持VAD（语音活动检测）自动开始/结束录制
- 音频格式：16kHz, 16bit, mono WAV

```python
class VoiceRecorder:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.chunk_size = 1024
        self.audio = pyaudio.PyAudio()
        
    def start_recording(self):
        # 开始录音逻辑
        pass
        
    def stop_recording(self) -> bytes:
        # 停止录音并返回音频数据
        pass
```

**音频播放（audio_player.py）**:
- 播放TTS生成的音频反馈
- 支持音频队列管理

#### 2.3 屏幕截图模块（client/screenshot/）

**截图管理器（screenshot_manager.py）**:
```python
class ScreenshotManager:
    def __init__(self):
        self.screenshot_interval = 1.0  # 1秒截图一次
        
    def capture_screen(self) -> PIL.Image:
        # 使用pillow或pyautogui截图
        return ImageGrab.grab()
        
    def start_continuous_capture(self):
        # 开启连续截图线程
        pass
        
    def get_latest_screenshot(self) -> bytes:
        # 返回最新截图的base64编码
        pass
```

#### 2.4 自动化执行模块（client/automation/）

**动作执行器（action_executor.py）**:
```python
class ClientActionExecutor:
    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5  # 每个动作间隔0.5秒
        
    async def execute_action_plan(self, actions: list, elements: dict) -> dict:
        """
        在客户端执行动作计划
        """
        results = []
        
        for action in actions:
            try:
                # 执行前截图
                before_screenshot = pyautogui.screenshot()
                
                result = await self._execute_single_action(action, elements)
                
                # 执行后截图
                after_screenshot = pyautogui.screenshot()
                result["before_screenshot"] = self._image_to_base64(before_screenshot)
                result["after_screenshot"] = self._image_to_base64(after_screenshot)
                
                results.append(result)
                
                # 短暂等待确保界面更新
                await asyncio.sleep(0.5)
                
            except Exception as e:
                results.append({
                    "action": action,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": time.time()
                })
                break  # 失败后停止执行
                
        return {
            "overall_status": "success" if all(r.get("status") == "success" for r in results) else "failed",
            "action_results": results,
            "execution_time": time.time()
        }
        
    async def _execute_single_action(self, action: dict, elements: dict) -> dict:
        action_type = action.get("type")
        
        if action_type == "click":
            return await self._click_element(action, elements)
        elif action_type == "type":
            return await self._type_text(action)
        elif action_type == "key":
            return await self._press_key(action)
        elif action_type == "drag":
            return await self._drag_element(action, elements)
        elif action_type == "wait":
            return await self._wait_action(action)
        else:
            raise ValueError(f"Unsupported action type: {action_type}")
            
    async def _click_element(self, action: dict, elements: dict) -> dict:
        element_id = action.get("element_id")
        element = self._find_element_by_id(elements, element_id)
        
        if not element:
            raise ValueError(f"Element with id {element_id} not found")
            
        # 计算点击坐标（边界框中心）
        bbox = element["bbox"]
        x = bbox[0] + bbox[2] // 2
        y = bbox[1] + bbox[3] // 2
        
        # 执行点击
        pyautogui.click(x, y)
        
        return {
            "action": action,
            "status": "success",
            "coordinates": [x, y],
            "element": element,
            "timestamp": time.time()
        }
```

#### 2.5 结果验证模块（client/verification/）

**本地验证器（local_verifier.py）**:
```python
class LocalResultVerifier:
    def __init__(self, server_client):
        self.server_client = server_client
        
    async def verify_execution_result(self, 
                                    expected_outcome: str,
                                    before_screenshot: bytes,
                                    after_screenshot: bytes) -> dict:
        """
        本地验证执行结果，必要时调用服务端AI分析
        """
        # 基础的像素级对比
        basic_diff = self._compare_screenshots(before_screenshot, after_screenshot)
        
        # 如果变化明显，调用服务端进行AI验证
        if basic_diff["change_percentage"] > 0.1:  # 变化超过10%
            ai_verification = await self.server_client.verify_result(
                expected_outcome=expected_outcome,
                before_image=before_screenshot,
                after_image=after_screenshot
            )
            return {
                "verification_type": "ai_assisted",
                "basic_diff": basic_diff,
                "ai_result": ai_verification,
                "success": ai_verification.get("success", False)
            }
        else:
            return {
                "verification_type": "basic",
                "basic_diff": basic_diff,
                "success": basic_diff["change_percentage"] > 0.01  # 至少有些变化
            }
```

#### 2.6 通信模块（client/communication/）

**WebSocket客户端（websocket_client.py）**:
```python
class ServerClient:
    def __init__(self, server_url="ws://localhost:8000/ws"):
        self.server_url = server_url
        self.websocket = None
        
    async def connect(self):
        self.websocket = await websockets.connect(self.server_url)
        
    async def send_task_for_analysis(self, audio_data: bytes, screenshot: bytes, text_command: str) -> dict:
        """
        发送任务到服务端进行AI分析，返回执行计划
        """
        task_data = {
            "type": "analyze_task",
            "audio": base64.b64encode(audio_data).decode() if audio_data else None,
            "screenshot": base64.b64encode(screenshot).decode(),
            "command": text_command,
            "timestamp": time.time()
        }
        
        await self.websocket.send(json.dumps(task_data))
        response = await self.websocket.receive()
        return json.loads(response)
        
    async def verify_result(self, expected_outcome: str, before_image: bytes, after_image: bytes) -> dict:
        """
        请求服务端验证执行结果
        """
        verify_data = {
            "type": "verify_result",
            "expected_outcome": expected_outcome,
            "before_image": base64.b64encode(before_image).decode(),
            "after_image": base64.b64encode(after_image).decode(),
            "timestamp": time.time()
        }
        
        await self.websocket.send(json.dumps(verify_data))
        response = await self.websocket.receive()
        return json.loads(response)
```

### 3. 服务端模块

#### 3.1 API服务（server/api/）

**FastAPI主服务（main.py）**:
```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Computer Use Agent API")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        task_data = json.loads(data)
        
        # 处理任务
        result = await process_task(task_data)
        await websocket.send_text(json.dumps(result))

@app.post("/api/tasks")
async def create_task(task: TaskSchema):
    # REST API任务提交接口
    pass
```

**任务路由（routes/tasks.py）**:
- `/api/tasks` - 创建新任务
- `/api/tasks/{task_id}` - 查询任务状态
- `/api/tasks/{task_id}/actions` - 获取执行计划
- `/api/health` - 健康检查

#### 3.2 模型服务集成（server/models/）

**Speech-to-Text服务（speech_service.py）**:
```python
class SpeechToTextService:
    def __init__(self):
        # 可选择：OpenAI Whisper, Azure Speech, Google Speech
        self.model_type = "whisper"
        
    async def transcribe(self, audio_data: bytes) -> str:
        if self.model_type == "whisper":
            return await self._whisper_transcribe(audio_data)
        elif self.model_type == "azure":
            return await self._azure_transcribe(audio_data)
            
    async def _whisper_transcribe(self, audio_data: bytes) -> str:
        # Whisper模型推理
        model = whisper.load_model("base")
        # 处理音频并返回文本
        pass
```

**Text-to-Speech服务（tts_service.py）**:
```python
class TextToSpeechService:
    def __init__(self):
        self.engine = pyttsx3.init()
        
    async def synthesize(self, text: str) -> bytes:
        # 生成语音并返回音频数据
        pass
```

**Claude API集成（claude_service.py）**:
```python
class ClaudeService:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        
    async def analyze_task(self, 
                          user_command: str, 
                          screenshot_path: str, 
                          omni_elements: dict) -> dict:
        
        prompt = f"""
        用户指令: {user_command}
        
        屏幕元素信息: {json.dumps(omni_elements, ensure_ascii=False)}
        
        请分析用户指令，制定执行计划。返回JSON格式的动作序列:
        {{
            "reasoning": "分析过程",
            "actions": [
                {{"type": "click", "element_id": 1, "description": "点击计算器图标"}},
                {{"type": "type", "text": "1+2=", "description": "输入计算表达式"}},
                {{"type": "click", "element_id": 5, "description": "点击等号"}},
                {{"type": "capture_result", "description": "获取计算结果"}}
            ],
            "expected_outcome": "期望的执行结果"
        }}
        """
        
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{
                "role": "user", 
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_path}}
                ]
            }]
        )
        
        return json.loads(message.content[0].text)
```

#### 3.3 视觉解析模块（server/vision/）

**OmniParser集成（omni_parser.py）**:
```python
class OmniParserService:
    def __init__(self):
        # 初始化OmniParser模型
        self.model = self._load_omniparser_model()
        
    def _load_omniparser_model(self):
        # 加载预训练的OmniParser模型
        # 具体实现依赖于OmniParser的API
        pass
        
    async def parse_screenshot(self, image_data: bytes) -> dict:
        """
        解析屏幕截图，返回元素信息
        
        Returns:
            {
                "elements": [
                    {
                        "id": 1,
                        "bbox": [x, y, width, height],
                        "text": "计算器",
                        "type": "icon",
                        "confidence": 0.95,
                        "clickable": true
                    }
                ],
                "resolution": [1920, 1080]
            }
        """
        # 将bytes转换为PIL Image
        image = Image.open(io.BytesIO(image_data))
        
        # 使用OmniParser解析
        results = self.model.parse(image)
        
        # 格式化输出
        formatted_results = {
            "elements": [],
            "resolution": [image.width, image.height]
        }
        
        for element in results:
            formatted_results["elements"].append({
                "id": element.get("id"),
                "bbox": element.get("bbox"),
                "text": element.get("text", ""),
                "type": element.get("type", "unknown"),
                "confidence": element.get("confidence", 0.0),
                "clickable": element.get("clickable", False)
            })
            
        return formatted_results
```

#### 3.4 结果验证服务（server/models/verification/）

**AI验证服务（ai_verifier.py）**:
```python
class AIVerificationService:
    def __init__(self, claude_service, omni_parser):
        self.claude_service = claude_service
        self.omni_parser = omni_parser
        
    async def verify_execution_result(self, 
                                    expected_outcome: str,
                                    before_screenshot: bytes,
                                    after_screenshot: bytes) -> dict:
        """
        使用AI验证执行结果
        """
        # 解析执行前后的屏幕元素
        before_elements = await self.omni_parser.parse_screenshot(before_screenshot)
        after_elements = await self.omni_parser.parse_screenshot(after_screenshot)
        
        # 分析变化
        changes = self._analyze_changes(before_elements, after_elements)
        
        # 使用Claude验证结果
        verification_prompt = f"""
        用户期望的结果: {expected_outcome}
        
        屏幕变化分析:
        - 新增元素: {changes.get('added_elements', [])}
        - 消失元素: {changes.get('removed_elements', [])}
        - 变化元素: {changes.get('modified_elements', [])}
        
        请判断执行结果是否符合用户期望，返回JSON格式:
        {{
            "success": true/false,
            "confidence": 0.0-1.0,
            "explanation": "详细说明",
            "suggestions": ["改进建议"]
        }}
        """
        
        claude_result = await self.claude_service.analyze_verification(
            prompt=verification_prompt,
            before_image=before_screenshot,
            after_image=after_screenshot
        )
        
        return {
            "verification_type": "ai_analysis",
            "changes": changes,
            "claude_result": claude_result,
            "timestamp": time.time()
        }
```

### 4. 数据协议设计（shared/protocols/）

#### 4.1 通信协议（communication_protocol.py）

```python
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class MessageType(str, Enum):
    ANALYZE_TASK = "analyze_task"          # 客户端 → 服务端：分析任务
    EXECUTION_PLAN = "execution_plan"      # 服务端 → 客户端：返回执行计划
    VERIFY_RESULT = "verify_result"        # 客户端 → 服务端：验证执行结果
    VERIFICATION_RESULT = "verification_result"  # 服务端 → 客户端：验证结果
    ERROR = "error"

class TaskMessage(BaseModel):
    type: MessageType
    task_id: str
    timestamp: float
    data: dict

class TaskAnalysisRequest(BaseModel):
    """客户端发送给服务端的任务分析请求"""
    audio_data: Optional[str] = None  # base64编码
    screenshot: str  # base64编码
    text_command: Optional[str] = None
    user_id: str = "default"

class ActionPlan(BaseModel):
    """服务端返回给客户端的执行计划"""
    reasoning: str
    actions: List[dict]
    expected_outcome: str
    confidence: float
    estimated_duration: Optional[int] = None  # 预估执行时间(秒)

class ExecutionResult(BaseModel):
    """客户端执行结果"""
    task_id: str
    overall_status: str  # success, failed, partial
    action_results: List[dict]
    execution_time: float
    error_message: Optional[str] = None

class VerificationRequest(BaseModel):
    """客户端发送的验证请求"""
    task_id: str
    expected_outcome: str
    before_screenshot: str  # base64编码
    after_screenshot: str   # base64编码
    execution_result: ExecutionResult

class VerificationResult(BaseModel):
    """服务端返回的验证结果"""
    task_id: str
    success: bool
    confidence: float
    explanation: str
    suggestions: List[str]
    audio_response: Optional[str] = None  # base64编码的语音反馈
```

#### 4.2 配置管理（config.py）

```python
from pydantic import BaseSettings

class ClientConfig(BaseSettings):
    server_url: str = "ws://localhost:8000"
    audio_sample_rate: int = 16000
    screenshot_interval: float = 1.0
    auto_retry_count: int = 3
    
    class Config:
        env_file = ".env"

class ServerConfig(BaseSettings):
    # API配置
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 模型配置
    claude_api_key: str
    whisper_model: str = "base"
    omni_parser_model_path: str = "./models/omniparser"
    
    # 服务配置
    redis_url: str = "redis://localhost:6379"
    task_timeout: int = 300  # 5分钟超时
    max_concurrent_tasks: int = 10
    
    class Config:
        env_file = ".env"
```

### 5. n8n工作流编排（server/workflows/）

#### 5.1 工作流设计

**主工作流（main_workflow.json）**:
```json
{
  "name": "Computer Use Agent Main Flow",
  "nodes": [
    {
      "id": "webhook-trigger",
      "type": "webhook",
      "name": "接收客户端任务",
      "webhook_path": "/webhook/analyze-task"
    },
    {
      "id": "speech-to-text",
      "type": "http-request",
      "name": "语音识别",
      "url": "http://localhost:8001/api/speech/transcribe",
      "method": "POST"
    },
    {
      "id": "omni-parser",
      "type": "http-request", 
      "name": "屏幕解析",
      "url": "http://localhost:8002/api/vision/parse",
      "method": "POST"
    },
    {
      "id": "claude-analysis",
      "type": "http-request",
      "name": "Claude任务分析",
      "url": "http://localhost:8003/api/claude/analyze",
      "method": "POST"
    },
    {
      "id": "return-plan",
      "type": "webhook-response",
      "name": "返回执行计划给客户端"
    },
    {
      "id": "verification-webhook",
      "type": "webhook",
      "name": "接收验证请求",
      "webhook_path": "/webhook/verify-result"
    },
    {
      "id": "ai-verification",
      "type": "http-request",
      "name": "AI结果验证",
      "url": "http://localhost:8003/api/claude/verify",
      "method": "POST"
    },
    {
      "id": "text-to-speech",
      "type": "http-request",
      "name": "语音合成",
      "url": "http://localhost:8005/api/tts/synthesize",
      "method": "POST"
    }
  ],
  "connections": [
    {
      "from": "webhook-trigger",
      "to": ["speech-to-text", "omni-parser"]
    },
    {
      "from": ["speech-to-text", "omni-parser"],
      "to": "claude-analysis"
    },
    {
      "from": "claude-analysis",
      "to": "return-plan"
    },
    {
      "from": "verification-webhook",
      "to": "ai-verification"
    },
    {
      "from": "ai-verification",
      "to": "text-to-speech"
    }
  ]
}
```

**工作流说明**：
1. 客户端发送任务分析请求（语音+截图）
2. 服务端并行处理语音识别和屏幕解析
3. Claude分析生成执行计划
4. 返回执行计划给客户端
5. 客户端执行操作后发送验证请求
6. 服务端AI验证结果并生成语音反馈

### 6. 部署和监控

#### 6.1 Docker容器化（docker/）

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  # Redis消息队列
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
      
  # 主API服务
  api-server:
    build: 
      context: .
      dockerfile: docker/Dockerfile.server
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
    depends_on:
      - redis
      
  # 语音服务
  speech-service:
    build:
      context: .
      dockerfile: docker/Dockerfile.speech
    ports:
      - "8001:8001"
      
  # 视觉解析服务
  vision-service:
    build:
      context: .
      dockerfile: docker/Dockerfile.vision  
    ports:
      - "8002:8002"
    volumes:
      - ./models:/app/models
      
  # n8n工作流
  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=password
    volumes:
      - n8n_data:/home/node/.n8n
      
volumes:
  n8n_data:
```

#### 6.2 监控和日志

**日志配置（logging_config.py）**:
```python
import logging
import sys
from loguru import logger

def setup_logging():
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # 添加文件输出
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )
```

### 7. 测试策略

#### 7.1 单元测试（tests/unit/）

```python
# tests/unit/test_speech_service.py
import pytest
from server.models.speech_service import SpeechToTextService

@pytest.mark.asyncio
async def test_speech_transcription():
    service = SpeechToTextService()
    
    # 加载测试音频文件
    with open("tests/fixtures/test_audio.wav", "rb") as f:
        audio_data = f.read()
    
    result = await service.transcribe(audio_data)
    assert isinstance(result, str)
    assert len(result) > 0
```

#### 7.2 集成测试（tests/integration/）

```python
# tests/integration/test_end_to_end.py
import pytest
from client.communication.websocket_client import ServerClient

@pytest.mark.asyncio
async def test_calculator_task():
    client = ServerClient("ws://localhost:8000/ws")
    await client.connect()
    
    # 模拟完整的计算器任务
    with open("tests/fixtures/calculator_command.wav", "rb") as audio_file:
        audio_data = audio_file.read()
        
    with open("tests/fixtures/desktop_screenshot.png", "rb") as screenshot_file:
        screenshot_data = screenshot_file.read()
    
    result = await client.send_task(
        audio_data=audio_data,
        screenshot=screenshot_data,
        text_command="帮我计算1+2等于几"
    )
    
    assert result["status"] == "success"
    assert "3" in result["final_summary"]
```

### 8. 性能优化策略

#### 8.1 客户端优化
- 音频流式传输，减少延迟
- 屏幕截图压缩，降低带宽占用
- 本地缓存常用UI元素识别结果

#### 8.2 服务端优化
- 模型推理并行化
- Redis缓存屏幕解析结果
- 连接池管理数据库连接
- 任务队列分级处理

### 9. 安全考虑

#### 9.1 权限控制
- 客户端操作权限限制（仅允许特定应用）
- API访问权限验证
- 敏感操作二次确认

#### 9.2 数据安全
- 音频数据本地处理，不上传到云端
- 屏幕截图脱敏处理
- API密钥安全存储

### 10. 扩展规划

#### 10.1 功能扩展
- 支持更多应用程序（浏览器、文本编辑器等）
- 多显示器支持
- 任务录制和回放功能

#### 10.2 技术演进
- 本地化大模型部署
- 更高精度的屏幕元素识别
- 自然语言理解优化

---

## 完整数据流程设计

### 典型任务执行流程

```
1. 用户语音输入: "帮我计算1+2等于几"
   ├─ 客户端录制音频
   ├─ 自动截取屏幕截图
   └─ 发送到服务端分析

2. 服务端AI分析阶段:
   ├─ Whisper: 语音转文字 → "帮我计算1+2等于几"
   ├─ OmniParser: 屏幕解析 → 识别桌面图标、应用等
   └─ Claude: 生成执行计划
       {
         "reasoning": "用户想要计算1+2，需要打开计算器应用",
         "actions": [
           {"type": "click", "element_id": 5, "description": "点击计算器图标"},
           {"type": "wait", "duration": 2, "description": "等待计算器启动"},
           {"type": "click", "element_id": "calc_1", "description": "点击数字1"},
           {"type": "click", "element_id": "calc_plus", "description": "点击加号"},
           {"type": "click", "element_id": "calc_2", "description": "点击数字2"},
           {"type": "click", "element_id": "calc_equals", "description": "点击等号"}
         ],
         "expected_outcome": "计算器显示结果3"
       }

3. 客户端执行阶段:
   ├─ 接收执行计划
   ├─ 逐步执行每个动作
   ├─ 每步后截图记录
   └─ 发送验证请求到服务端

4. 服务端验证阶段:
   ├─ 对比执行前后截图
   ├─ Claude分析是否达到预期结果
   └─ 生成总结和语音反馈: "计算完成，1+2等于3"

5. 客户端反馈阶段:
   ├─ 接收验证结果
   ├─ 播放语音反馈
   └─ 更新UI状态
```

### 安全和权限控制

#### 客户端安全措施
```python
class SecurityManager:
    def __init__(self):
        self.allowed_applications = [
            "Calculator", "Notepad", "Chrome", "Firefox"
        ]
        self.restricted_areas = [
            # 避免点击系统关键区域
            {"x1": 0, "y1": 0, "x2": 100, "y2": 50},  # 左上角系统菜单
        ]
    
    def validate_action(self, action: dict) -> bool:
        """验证动作是否安全"""
        if action["type"] == "click":
            return self._validate_click_safety(action)
        return True
        
    def _validate_click_safety(self, action: dict) -> bool:
        # 检查点击位置是否在限制区域内
        # 检查是否点击危险的系统按钮
        pass
```

## 开发时间估算

| 模块 | 预估时间 | 优先级 | 备注 |
|------|----------|--------|------|
| 基础架构搭建 | 3-5天 | 高 | 项目结构、通信协议 |
| 客户端UI开发 | 5-7天 | 高 | PyQt界面、音频录制 |
| 客户端自动化执行 | 4-6天 | 高 | pyautogui集成、安全控制 |
| 语音处理集成 | 3-4天 | 中 | Whisper、TTS集成 |
| OmniParser集成 | 4-6天 | 高 | 屏幕元素识别 |
| Claude API集成 | 2-3天 | 高 | 任务分析、结果验证 |
| 客户端结果验证 | 2-3天 | 中 | 本地验证逻辑 |
| n8n工作流配置 | 2-3天 | 中 | 服务端任务编排 |
| 测试和调优 | 5-7天 | 中 | 端到端测试 |

**总计**: 约5-7周的开发时间（考虑到架构调整）

## 技术风险和挑战

### 主要技术挑战

1. **跨平台兼容性**
   - Windows/Mac的屏幕截图API差异
   - 不同操作系统的自动化操作适配
   - 应用程序界面元素识别的准确性

2. **实时性能要求**
   - OmniParser模型推理延迟
   - 网络通信延迟对用户体验的影响
   - 大图片数据传输优化

3. **准确性保障**
   - 语音识别在嘈杂环境下的准确率
   - 屏幕元素识别的误识别问题
   - Claude指令理解的边界情况

### 解决方案

1. **兼容性解决**
   ```python
   # 跨平台适配层
   class PlatformAdapter:
       @staticmethod
       def get_adapter():
           if platform.system() == "Windows":
               return WindowsAdapter()
           elif platform.system() == "Darwin":
               return MacOSAdapter()
   ```

2. **性能优化**
   - 图像压缩和增量传输
   - 本地缓存常用界面元素
   - 异步处理和流式传输

3. **准确性提升**
   - 多模型集成验证
   - 用户确认机制
   - 操作回滚功能

## MVP开发计划

### 第一阶段：基础功能(2-3周)
- 客户端基本界面
- 屏幕截图和语音录制
- 服务端基础API
- Claude基本集成
- 简单的计算器操作

### 第二阶段：核心功能(3-4周) 
- OmniParser集成
- 完整的执行引擎
- 结果验证机制
- 错误处理和重试

### 第三阶段：优化完善(2-3周)
- 性能优化
- 安全机制
- 用户体验改进
- 测试和文档

## 项目任务清单 (TODO List)

### 🔴 高优先级任务 (必须完成)

#### 核心基础架构
- [x] **项目结构搭建** `[1-2天]` ✅
  - [x] 创建标准化的项目目录结构
  - [x] 配置基础的依赖管理文件 (requirements.txt)
  - [x] 建立共享协议和数据模型 (shared/schemas/data_models.py)
  - [ ] 完善共享工具和协议 (shared/protocols/, shared/utils/)

#### 客户端开发 (client/)
- [x] **PyQt主界面开发** `[3-4天]` ✅
  - [x] 实现MainWindow完整界面布局
  - [x] 添加实时状态显示组件 (录音中、处理中、执行中)
  - [x] 实现任务历史记录和结果显示
  - [x] 设计设置面板 (服务器地址配置)
  - [x] UI元素详情表格和标注截图显示
  - [ ] 创建语音录制按钮 (按住说话/点击切换)

- [ ] **音频处理模块** `[2-3天]`
  - [ ] 实现VoiceRecorder类 (pyaudio录音)
  - [ ] 添加VAD语音活动检测
  - [ ] 实现AudioPlayer类 (TTS播放)
  - [ ] 音频格式标准化 (16kHz, 16bit, mono WAV)

- [x] **屏幕截图管理器** `[2天]` ✅
  - [x] 实现ScreenshotManager类
  - [x] 支持连续截图和单次截图
  - [x] 图像压缩和base64编码
  - [x] 性能优化和缓存机制
  - [x] 多线程处理和防抖机制

- [ ] **自动化执行引擎** `[4-5天]`
  - [ ] 实现ClientActionExecutor核心类
  - [ ] 支持基础动作: click, type, key, drag, wait
  - [ ] 添加执行前后截图对比
  - [ ] 实现动作执行安全检查
  - [ ] 错误处理和执行回滚机制

- [x] **通信层开发** `[2-3天]` ✅
  - [x] 实现WebSocket客户端 (ServerClient)
  - [x] 定义任务分析请求/响应协议
  - [x] 连接重试和错误处理
  - [x] 同步和异步通信方法
  - [ ] 实现结果验证通信接口

#### 服务端开发 (server/)
- [x] **FastAPI基础服务** `[2-3天]` ✅
  - [x] 建立FastAPI应用结构
  - [x] 实现WebSocket路由和处理器
  - [x] 添加REST API接口 (/health)
  - [x] 连接管理和错误处理
  - [x] OmniParser服务集成

- [ ] **Claude API集成** `[2-3天]`
  - [ ] 实现ClaudeService类
  - [ ] 完善任务分析prompt工程
  - [ ] 实现执行计划生成逻辑
  - [ ] 添加结果验证AI分析

### 🟡 中优先级任务 (重要功能)

#### AI模型服务
- [ ] **语音识别服务** `[2-3天]`
  - [ ] 集成Whisper STT模型
  - [ ] 支持多种音频格式输入
  - [ ] 优化推理速度和准确率

- [ ] **TTS语音合成** `[1-2天]`
  - [ ] 集成pyttsx3或Azure Speech
  - [ ] 实现多语言语音输出
  - [ ] 音频质量优化

- [ ] **结果验证系统** `[3-4天]`
  - [ ] 实现LocalResultVerifier本地验证
  - [ ] 开发AIVerificationService AI验证
  - [ ] 屏幕变化对比算法
  - [ ] 验证结果评分机制

#### 安全和权限控制
- [ ] **安全管理器** `[2-3天]`
  - [ ] 实现SecurityManager类
  - [ ] 定义允许操作的应用程序白名单
  - [ ] 设置屏幕限制区域检查
  - [ ] 危险操作拦截机制

#### 工作流和部署
- [ ] **n8n工作流集成** `[2-3天]`
  - [ ] 设计主工作流JSON配置
  - [ ] 实现服务间HTTP调用
  - [ ] 配置并行处理节点

### 🟢 低优先级任务 (优化和扩展)

#### 测试和质量保证
- [ ] **测试框架建立** `[3-4天]`
  - [ ] 编写单元测试用例
  - [ ] 实现集成测试场景
  - [ ] 端到端测试自动化
  - [ ] 性能基准测试

#### 部署和运维
- [ ] **容器化部署** `[2-3天]`
  - [ ] 编写Dockerfile配置
  - [ ] 配置docker-compose.yml
  - [ ] 设置日志和监控

#### 性能优化
- [ ] **系统优化** `[按需进行]`
  - [ ] 图像传输压缩优化
  - [ ] 本地缓存机制
  - [ ] 异步处理优化
  - [ ] 内存使用优化

### 📋 项目里程碑

#### Milestone 1: 基础MVP (4-5周) ✅ **已完成**
**目标**: 实现计算器基础操作演示
- [x] OmniParser集成完成
- [x] 客户端基础界面完成 ✅
- [x] 服务端API基础功能完成 ✅
- [x] 端到端通信和UI解析演示成功 ✅
- [ ] 实际自动化操作执行 (待实现)

#### Milestone 2: 核心功能完善 (6-8周)
**目标**: 完整的任务执行和验证流程
- [ ] 完整的语音交互流程
- [ ] 可靠的执行结果验证
- [ ] 基础安全控制机制
- [ ] 支持3-5种常见应用操作

#### Milestone 3: 产品化优化 (8-10周)
**目标**: 可用性和稳定性提升
- [ ] 完善的错误处理机制
- [ ] 用户体验优化
- [ ] 性能调优完成
- [ ] 完整的测试覆盖

### 📊 当前进度状态

```
总体进度: ██████████████░░░░░░ 70% 

模块进度:
├── OmniParser集成    ████████████████████ 100% ✅
├── 项目架构设计      ████████████████████ 100% ✅
├── 客户端开发        █████████████████░░░  85% ✅ (UI完成，缺少音频+自动化执行)
├── 服务端开发        ████████████████░░░░  80% ✅ (API完成，缺少Claude集成)
├── AI模型集成        ████████████░░░░░░░░  60% 🔄 (OmniParser完成，Claude待集成)
├── 通信协议          ████████████████████ 100% ✅
├── 安全机制          ░░░░░░░░░░░░░░░░░░░░   0%
└── 测试和部署        ████░░░░░░░░░░░░░░░░  20% (MVP测试完成)
```

### 🎯 下一步行动建议

**🚀 MVP基础框架已完成！项目进度达到70%**

**立即优先任务**:
1. **集成Claude API** - 替换当前的模拟AI分析，实现真正智能的任务分析
2. **实现pyautogui自动化执行引擎** - 让客户端能够实际执行屏幕操作
3. **添加语音功能** - 集成Whisper和TTS，实现完整的语音交互

**已完成的重要功能**:
- ✅ 完整的PyQt6客户端界面（现代化UI、截图预览、任务历史）
- ✅ FastAPI服务端（WebSocket通信、任务分析API）
- ✅ OmniParser屏幕元素识别（检测UI元素、生成标注图像）
- ✅ 实时截图管理（性能优化、缓存机制）
- ✅ 跨平台部署（Mac客户端 + Linux服务端）

**本周目标**:
- 集成Claude API进行智能任务分析
- 实现客户端自动化操作执行
- 添加语音录制和播放功能

---

*本方案已根据"任务执行在客户端"的要求进行了架构调整，确保了安全性和实用性的平衡。*