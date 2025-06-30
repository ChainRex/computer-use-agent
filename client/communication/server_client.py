import asyncio
import websockets
import json
import time
from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.schemas.data_models import TaskAnalysisRequest, TaskAnalysisResponse

class ServerClient:
    def __init__(self, server_url: str = "ws://localhost:8000/ws"):
        self.server_url = server_url
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connected = False
    
    async def connect(self) -> bool:
        """连接到服务端"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.connected = True
            print(f"已连接到服务端: {self.server_url}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            print("已断开连接")
    
    async def send_task_for_analysis(self, text_command: str, screenshot_base64: str) -> Optional[TaskAnalysisResponse]:
        """发送任务给服务端分析"""
        if not self.connected:
            print("未连接到服务端")
            return None
        
        try:
            # 创建任务请求
            task_request = TaskAnalysisRequest(
                text_command=text_command,
                screenshot_base64=screenshot_base64
            )
            
            # 创建消息
            message = {
                "type": "analyze_task",
                "task_id": f"task_{int(time.time() * 1000)}",
                "timestamp": time.time(),
                "data": task_request.model_dump()
            }
            
            # 发送消息
            await self.websocket.send(json.dumps(message))
            print("任务已发送，等待服务端响应...")
            
            # 等待响应
            response_str = await self.websocket.recv()
            response_data = json.loads(response_str)
            
            # 解析响应
            if response_data.get("type") == "analysis_result":
                return TaskAnalysisResponse(**response_data["data"])
            else:
                print(f"收到未知响应类型: {response_data.get('type')}")
                return None
                
        except Exception as e:
            print(f"发送任务失败: {e}")
            return None
    
    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            await self.websocket.ping()
            return True
        except:
            return False

# 测试函数
async def test_client():
    client = ServerClient()
    
    if await client.connect():
        # 测试发送消息
        response = await client.send_task_for_analysis(
            text_command="测试指令",
            screenshot_base64="test_base64_data"
        )
        
        if response:
            print(f"收到响应: {response}")
        
        await client.disconnect()
    else:
        print("连接失败")

if __name__ == "__main__":
    asyncio.run(test_client())