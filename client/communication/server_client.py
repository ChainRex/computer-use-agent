import asyncio
import websockets
import json
import time
import threading
import weakref
from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.schemas.data_models import (
    TaskAnalysisRequest, TaskAnalysisResponse, 
    OmniParserResult, ClaudeAnalysisResult
)

class ServerClient:
    _shared_loop = None  # 共享事件循环
    _loop_thread = None  # 事件循环线程
    _clients = []  # 活跃客户端列表
    
    def __init__(self, server_url: str = "ws://localhost:8000/ws"):
        self.server_url = server_url
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connected = False
        self._connection_lock = threading.Lock()
        
        # 注册到共享客户端列表
        ServerClient._clients.append(weakref.ref(self))
        
        # 确保共享事件循环存在
        self._ensure_shared_loop()
    
    @classmethod
    def _ensure_shared_loop(cls):
        """确保共享事件循环存在"""
        if cls._shared_loop is None or cls._shared_loop.is_closed():
            cls._shared_loop = asyncio.new_event_loop()
            
            # 启动事件循环线程
            if cls._loop_thread is None or not cls._loop_thread.is_alive():
                cls._loop_thread = threading.Thread(
                    target=cls._run_shared_loop,
                    daemon=True,
                    name="ServerClient-EventLoop"
                )
                cls._loop_thread.start()
    
    @classmethod
    def _run_shared_loop(cls):
        """运行共享事件循环"""
        asyncio.set_event_loop(cls._shared_loop)
        try:
            cls._shared_loop.run_forever()
        except Exception as e:
            print(f"共享事件循环错误: {e}")
        finally:
            cls._shared_loop.close()
    
    def _run_in_loop(self, coro):
        """在共享事件循环中运行协程"""
        if self._shared_loop and not self._shared_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(coro, self._shared_loop)
            return future.result(timeout=30)  # 30秒超时
        else:
            raise RuntimeError("共享事件循环不可用")
    
    async def connect(self) -> bool:
        """连接到服务端"""
        with self._connection_lock:
            if self.connected:
                return True
            
            try:
                # 添加连接超时和重试机制
                self.websocket = await asyncio.wait_for(
                    websockets.connect(
                        self.server_url,
                        ping_interval=20,  # 20秒心跳
                        ping_timeout=10,   # 10秒心跳超时
                        close_timeout=10   # 10秒关闭超时
                    ),
                    timeout=10.0  # 10秒连接超时
                )
                self.connected = True
                print(f"已连接到服务端: {self.server_url}")
                return True
            except asyncio.TimeoutError:
                print(f"连接超时: {self.server_url}")
                self.connected = False
                return False
            except Exception as e:
                print(f"连接失败: {e}")
                self.connected = False
                return False
    
    def connect_sync(self) -> bool:
        """同步连接方法"""
        try:
            return self._run_in_loop(self.connect())
        except Exception as e:
            print(f"同步连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        with self._connection_lock:
            if self.websocket:
                try:
                    await asyncio.wait_for(self.websocket.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    print("断开连接超时")
                except Exception as e:
                    print(f"断开连接错误: {e}")
                finally:
                    self.websocket = None
                    self.connected = False
                    print("已断开连接")
    
    def disconnect_sync(self):
        """同步断开连接方法"""
        try:
            self._run_in_loop(self.disconnect())
        except Exception as e:
            print(f"同步断开连接失败: {e}")
    
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
            
            # 发送消息（添加超时）
            await asyncio.wait_for(
                self.websocket.send(json.dumps(message)),
                timeout=10.0
            )
            print("任务已发送，等待服务端响应...")
            
            # 等待响应（添加超时）
            response_str = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=60.0  # 60秒超时等待分析结果
            )
            response_data = json.loads(response_str)
            
            # 解析响应
            if response_data.get("type") == "analysis_result":
                return TaskAnalysisResponse(**response_data["data"])
            else:
                print(f"收到未知响应类型: {response_data.get('type')}")
                return None
                
        except asyncio.TimeoutError:
            print("任务发送或接收响应超时")
            return None
        except websockets.exceptions.ConnectionClosed:
            print("连接已断开")
            self.connected = False
            return None
        except Exception as e:
            print(f"发送任务失败: {e}")
            return None
    
    def send_task_sync(self, text_command: str, screenshot_base64: str) -> Optional[TaskAnalysisResponse]:
        """同步发送任务方法"""
        try:
            return self._run_in_loop(self.send_task_for_analysis(text_command, screenshot_base64))
        except Exception as e:
            print(f"同步发送任务失败: {e}")
            return None
    
    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            if self.websocket and self.connected:
                await asyncio.wait_for(self.websocket.ping(), timeout=5.0)
                return True
            else:
                return False
        except Exception:
            self.connected = False
            return False
    
    @classmethod
    def shutdown_all(cls):
        """关闭所有客户端和共享事件循环"""
        try:
            # 清理所有活跃客户端
            for client_ref in cls._clients[:]:
                client = client_ref()
                if client:
                    try:
                        client.disconnect_sync()
                    except:
                        pass
            
            cls._clients.clear()
            
            # 停止共享事件循环
            if cls._shared_loop and not cls._shared_loop.is_closed():
                cls._shared_loop.call_soon_threadsafe(cls._shared_loop.stop)
                
                # 等待线程结束
                if cls._loop_thread and cls._loop_thread.is_alive():
                    cls._loop_thread.join(timeout=5.0)
            
            cls._shared_loop = None
            cls._loop_thread = None
            print("ServerClient已全部关闭")
            
        except Exception as e:
            print(f"关闭ServerClient时出错: {e}")
    
    def __del__(self):
        """析构函数 - 清理资源"""
        try:
            if self.connected:
                self.disconnect_sync()
        except:
            pass

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