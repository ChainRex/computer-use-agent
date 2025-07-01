from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import time
import uvicorn
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.schemas.data_models import (
    TaskAnalysisRequest, TaskAnalysisResponse, ActionPlan, UIElement,
    OmniParserResult, ClaudeAnalysisResult, MessageType,
    CompletionVerificationRequest, CompletionVerificationResponse
)

app = FastAPI(title="Computer Use Agent Server", version="1.0.0")

# 全局服务实例
omniparser_service = None
claude_service = None

def initialize_services():
    """初始化所有服务"""
    global omniparser_service, claude_service
    
    # 初始化OmniParser服务
    try:
        from server.omniparser import OmniParserService
        omniparser_service = OmniParserService()
        print("✅ OmniParser服务初始化成功")
    except Exception as e:
        print(f"❌ OmniParser服务初始化失败: {e}")
        print("📝 将使用模拟模式")
    
    # 初始化Claude服务
    try:
        from server.claude import ClaudeService
        claude_service = ClaudeService()
        print("✅ Claude服务初始化成功")
    except Exception as e:
        print(f"❌ Claude服务初始化失败: {e}")
        print("📝 将使用模拟分析模式")

# 启动时初始化所有服务
initialize_services()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"新客户端连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"客户端断开连接，当前连接数: {len(self.active_connections)}")

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"message": "Computer Use Agent Server is running"}

@app.get("/health")
async def health_check():
    omniparser_status = omniparser_service.get_status() if omniparser_service else {"available": False}
    claude_status = {"available": claude_service is not None} if claude_service else {"available": False}
    return {
        "status": "healthy", 
        "timestamp": time.time(),
        "omniparser": omniparser_status,
        "claude": claude_status
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)
            
            print(f"收到消息类型: {message.get('type')}")
            
            if message.get("type") == "analyze_task":
                # 处理任务分析请求（支持分阶段响应）
                response = await handle_task_analysis(message, websocket)
                await websocket.send_text(json.dumps(response))
            elif message.get("type") == "verify_task_completion":
                # 处理任务完成度验证请求（旧版本兼容）
                response = await handle_task_completion_verification(message, websocket)
                await websocket.send_text(json.dumps(response))
            elif message.get("type") == MessageType.VERIFY_COMPLETION:
                # 处理简化的任务完成验证请求
                response = await handle_simple_completion_verification(message, websocket)
                await websocket.send_text(json.dumps(response))
            else:
                # 未知消息类型
                error_response = {
                    "type": "error",
                    "message": f"未知消息类型: {message.get('type')}"
                }
                await websocket.send_text(json.dumps(error_response))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket错误: {e}")
        manager.disconnect(websocket)

async def handle_task_analysis(message: dict, websocket: WebSocket) -> dict:
    """处理任务分析请求（支持分阶段响应）"""
    try:
        # 解析请求数据
        task_data = message["data"]
        request = TaskAnalysisRequest(**task_data)
        task_id = message["task_id"]
        
        print(f"处理任务: {task_id}")
        print(f"指令: {request.text_command}")
        print(f"截图数据长度: {len(request.screenshot_base64)}")
        
        # 第一阶段：使用OmniParser分析屏幕元素
        ui_elements = []
        annotated_screenshot = None
        omni_start_time = time.time()
        
        if omniparser_service and omniparser_service.is_available():
            try:
                print("🔍 使用OmniParser分析屏幕元素...")
                annotated_img_base64, parsed_elements = omniparser_service.parse_screen(request.screenshot_base64)
                
                # 转换为标准格式
                ui_elements = [
                    UIElement(
                        id=elem.get('id', i),
                        type=elem.get('type', 'unknown'),
                        description=elem.get('description', ''),
                        coordinates=elem.get('coordinates', []),
                        text=elem.get('text', ''),
                        confidence=elem.get('confidence', 0.0)
                    ) for i, elem in enumerate(parsed_elements)
                ]
                
                annotated_screenshot = annotated_img_base64
                omni_processing_time = time.time() - omni_start_time
                
                print(f"✅ 检测到 {len(ui_elements)} 个UI元素")
                
                # 立即发送OmniParser结果
                omni_result = OmniParserResult(
                    task_id=task_id,
                    success=True,
                    ui_elements=ui_elements,
                    annotated_screenshot_base64=annotated_screenshot,
                    processing_time=omni_processing_time,
                    element_count=len(ui_elements)
                )
                
                omni_message = {
                    "type": "omniparser_result",
                    "task_id": task_id,
                    "timestamp": time.time(),
                    "data": omni_result.model_dump()
                }
                
                await websocket.send_text(json.dumps(omni_message))
                print("📤 OmniParser结果已发送给客户端")
                
            except Exception as e:
                print(f"⚠️ OmniParser分析失败，使用模拟模式: {e}")
        
        # 第二阶段：使用Claude进行AI分析
        claude_start_time = time.time()
        
        if claude_service:
            try:
                print("🧠 使用Claude进行智能任务分析...")
                actions, reasoning, confidence = claude_service.analyze_task_with_claude(
                    request.text_command,
                    request.screenshot_base64,
                    ui_elements,
                    annotated_screenshot,
                    request.os_info,
                    task_id  # 传递task_id给记忆模块
                )
                
                claude_processing_time = time.time() - claude_start_time
                
                # 发送Claude分析结果
                claude_result = ClaudeAnalysisResult(
                    task_id=task_id,
                    success=True,
                    reasoning=reasoning,
                    actions=actions,
                    expected_outcome="根据Claude分析生成的操作计划",
                    confidence=confidence,
                    processing_time=claude_processing_time
                )
                
                claude_message = {
                    "type": "claude_result",
                    "task_id": task_id,
                    "timestamp": time.time(),
                    "data": claude_result.model_dump()
                }
                
                await websocket.send_text(json.dumps(claude_message))
                print(f"✅ Claude分析完成，生成 {len(actions)} 个操作步骤")
                
                # 创建最终响应（兼容性）
                response = TaskAnalysisResponse(
                    task_id=task_id,
                    success=True,
                    reasoning=reasoning,
                    actions=actions,
                    expected_outcome="根据Claude分析生成的操作计划",
                    confidence=confidence,
                    ui_elements=ui_elements,
                    annotated_screenshot_base64=annotated_screenshot
                )
                
            except Exception as e:
                print(f"⚠️ Claude分析失败，使用模拟分析: {e}")
                response = simulate_ai_analysis(task_id, request, ui_elements)
                response.ui_elements = ui_elements
                response.annotated_screenshot_base64 = annotated_screenshot
        else:
            print("📝 使用模拟AI分析...")
            response = simulate_ai_analysis(task_id, request, ui_elements)
            response.ui_elements = ui_elements
            response.annotated_screenshot_base64 = annotated_screenshot
        
        # 返回最终结果
        return {
            "type": "analysis_result",
            "task_id": task_id,
            "timestamp": time.time(),
            "data": response.model_dump()
        }
        
    except Exception as e:
        print(f"任务分析失败: {e}")
        return {
            "type": "error",
            "task_id": message.get("task_id", "unknown"),
            "timestamp": time.time(),
            "message": f"任务分析失败: {str(e)}"
        }

async def handle_task_completion_verification(message: dict, websocket: WebSocket) -> dict:
    """处理任务完成度验证请求"""
    try:
        # 解析请求数据
        verification_data = message["data"]
        task_id = message["task_id"]
        original_command = verification_data["original_command"]
        previous_claude_output = verification_data["previous_claude_output"]
        screenshot_base64 = verification_data.get("screenshot_base64")
        verification_prompt = verification_data.get("verification_prompt")
        
        print(f"处理任务完成度验证: {task_id}")
        print(f"原始指令: {original_command}")
        print(f"使用内存截图数据进行验证")
        
        # 使用Claude进行任务完成度验证
        if claude_service:
            try:
                print("🔍 使用Claude验证任务完成度...")
                status, reasoning, confidence = claude_service.verify_task_completion_with_base64(
                    original_command,
                    previous_claude_output,
                    screenshot_base64,
                    verification_prompt
                )
                
                print(f"✅ 任务完成度验证结果: {status} (置信度: {confidence:.2f})")
                
                # 构建响应数据
                verification_result = {
                    "task_id": task_id,
                    "status": status,
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "verification_time": time.time()
                }
                
                return {
                    "type": "task_completion_result",
                    "task_id": task_id,
                    "timestamp": time.time(),
                    "data": verification_result
                }
                
            except Exception as e:
                print(f"⚠️ Claude任务完成度验证失败: {e}")
                return {
                    "type": "task_completion_result",
                    "task_id": task_id,
                    "timestamp": time.time(),
                    "data": {
                        "task_id": task_id,
                        "status": "unclear",
                        "reasoning": f"验证过程发生异常: {str(e)}",
                        "confidence": 0.0,
                        "verification_time": time.time()
                    }
                }
        else:
            print("📝 Claude服务不可用，使用模拟验证...")
            return {
                "type": "task_completion_result",
                "task_id": task_id,
                "timestamp": time.time(),
                "data": {
                    "task_id": task_id,
                    "status": "unclear",
                    "reasoning": "Claude服务不可用，无法进行智能验证",
                    "confidence": 0.0,
                    "verification_time": time.time()
                }
            }
        
    except Exception as e:
        print(f"任务完成度验证失败: {e}")
        return {
            "type": "error",
            "task_id": message.get("task_id", "unknown"),
            "timestamp": time.time(),
            "message": f"任务完成度验证失败: {str(e)}"
        }

async def handle_simple_completion_verification(message: dict, websocket: WebSocket) -> dict:
    """处理简化的任务完成验证请求"""
    try:
        # 解析请求数据
        verification_data = message["data"]
        request = CompletionVerificationRequest(**verification_data)
        task_id = message["task_id"]
        
        print(f"处理简化任务完成度验证: {task_id}")
        
        # 使用Claude服务的简化验证接口
        if claude_service:
            try:
                print("🔍 使用简化接口验证任务完成度...")
                verification_result = claude_service.verify_completion_simple(
                    task_id, 
                    request.screenshot_base64
                )
                
                print(f"✅ 简化验证结果: {verification_result.status} (置信度: {verification_result.confidence:.2f})")
                
                return {
                    "type": MessageType.COMPLETION_RESULT,
                    "task_id": task_id,
                    "timestamp": time.time(),
                    "data": verification_result.model_dump()
                }
                
            except Exception as e:
                print(f"⚠️ 简化验证失败: {e}")
                error_result = CompletionVerificationResponse(
                    task_id=task_id,
                    status="unclear",
                    reasoning=f"验证过程发生异常: {str(e)}",
                    confidence=0.0,
                    next_steps="请检查系统状态后重试",
                    next_actions=None,
                    verification_time=0.0
                )
                
                return {
                    "type": MessageType.COMPLETION_RESULT,
                    "task_id": task_id,
                    "timestamp": time.time(),
                    "data": error_result.model_dump()
                }
        else:
            print("📝 Claude服务不可用，使用模拟验证...")
            mock_result = CompletionVerificationResponse(
                task_id=task_id,
                status="unclear",
                reasoning="Claude服务不可用，无法进行智能验证",
                confidence=0.0,
                next_steps="请确保Claude服务正常运行",
                next_actions=None,
                verification_time=0.0
            )
            
            return {
                "type": MessageType.COMPLETION_RESULT,
                "task_id": task_id,
                "timestamp": time.time(),
                "data": mock_result.model_dump()
            }
        
    except Exception as e:
        print(f"简化任务完成度验证失败: {e}")
        return {
            "type": "error",
            "task_id": message.get("task_id", "unknown"),
            "timestamp": time.time(),
            "message": f"简化任务完成度验证失败: {str(e)}"
        }

def simulate_ai_analysis(task_id: str, request: TaskAnalysisRequest, ui_elements: list = None) -> TaskAnalysisResponse:
    """模拟AI分析过程（临时实现）"""
    
    command = request.text_command.lower()
    
    # 简单的关键词匹配逻辑
    if "计算器" in command or "calculator" in command or "计算" in command:
        actions = [
            ActionPlan(
                type="click",
                description="点击计算器图标",
                element_id="calculator_icon"
            ),
            ActionPlan(
                type="wait",
                description="等待计算器启动",
                duration=2.0
            )
        ]
        
        if "1+2" in command or "1加2" in command or "计算1+2" in command:
            actions.extend([
                ActionPlan(type="click", description="点击数字1", element_id="calc_1"),
                ActionPlan(type="click", description="点击加号", element_id="calc_plus"),
                ActionPlan(type="click", description="点击数字2", element_id="calc_2"),
                ActionPlan(type="click", description="点击等号", element_id="calc_equals")
            ])
            expected_outcome = "计算器显示结果: 3"
        else:
            expected_outcome = "计算器已打开"
        
        return TaskAnalysisResponse(
            task_id=task_id,
            success=True,
            reasoning=f"用户想要使用计算器功能，指令: '{request.text_command}'",
            actions=actions,
            expected_outcome=expected_outcome,
            confidence=0.8
        )
    
    elif "记事本" in command or "notepad" in command:
        return TaskAnalysisResponse(
            task_id=task_id,
            success=True,
            reasoning="用户想要打开记事本",
            actions=[
                ActionPlan(
                    type="key",
                    description="按下Win+R打开运行对话框",
                    text="win+r"
                ),
                ActionPlan(
                    type="type",
                    description="输入notepad",
                    text="notepad"
                ),
                ActionPlan(
                    type="key",
                    description="按下回车",
                    text="enter"
                )
            ],
            expected_outcome="记事本应用已打开",
            confidence=0.9
        )
    
    else:
        return TaskAnalysisResponse(
            task_id=task_id,
            success=False,
            reasoning="暂时无法理解此指令",
            error_message=f"未识别的指令: '{request.text_command}'"
        )

if __name__ == "__main__":
    print("启动Computer Use Agent服务端...")
    print("WebSocket地址: ws://localhost:8000/ws")
    print("API文档: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )