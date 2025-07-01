from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import time
import uvicorn
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.schemas.data_models import TaskAnalysisRequest, TaskAnalysisResponse, ActionPlan, UIElement

app = FastAPI(title="Computer Use Agent Server", version="1.0.0")

# 全局OmniParser服务实例
omniparser_service = None

def initialize_omniparser():
    """初始化OmniParser服务"""
    global omniparser_service
    try:
        from server.omniparser import OmniParserService
        omniparser_service = OmniParserService()
        print("✅ OmniParser服务初始化成功")
    except Exception as e:
        print(f"❌ OmniParser服务初始化失败: {e}")
        print("📝 将使用模拟模式")

# 启动时初始化OmniParser
initialize_omniparser()

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
    return {
        "status": "healthy", 
        "timestamp": time.time(),
        "omniparser": omniparser_status
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
                # 处理任务分析请求
                response = await handle_task_analysis(message)
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

async def handle_task_analysis(message: dict) -> dict:
    """处理任务分析请求"""
    try:
        # 解析请求数据
        task_data = message["data"]
        request = TaskAnalysisRequest(**task_data)
        task_id = message["task_id"]
        
        print(f"处理任务: {task_id}")
        print(f"指令: {request.text_command}")
        print(f"截图数据长度: {len(request.screenshot_base64)}")
        
        # 使用OmniParser分析屏幕元素
        ui_elements = []
        annotated_screenshot = None
        
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
                print(f"✅ 检测到 {len(ui_elements)} 个UI元素")
                
            except Exception as e:
                print(f"⚠️ OmniParser分析失败，使用模拟模式: {e}")
        
        # AI分析过程（集成UI元素信息）
        response = simulate_ai_analysis(task_id, request, ui_elements)
        
        # 添加OmniParser结果
        response.ui_elements = ui_elements
        response.annotated_screenshot_base64 = annotated_screenshot
        
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