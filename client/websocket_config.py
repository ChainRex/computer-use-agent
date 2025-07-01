"""
WebSocket连接配置和工具函数
"""

import asyncio
import websockets
import json
import logging

logger = logging.getLogger(__name__)

# WebSocket连接的标准配置
WEBSOCKET_CONFIG = {
    'max_size': 10 * 1024 * 1024,  # 10MB
    'ping_interval': 60,            # 60秒ping间隔
    'ping_timeout': 30,             # 30秒ping超时
    'close_timeout': 30,            # 30秒关闭超时
    'compression': None             # 禁用压缩
}

# 接收超时配置
RECEIVE_TIMEOUT = 420.0  # 7分钟超时，适应Claude处理时间

async def create_websocket_connection(uri: str, max_retries: int = 3):
    """
    创建WebSocket连接，带重试机制
    
    Args:
        uri: WebSocket URI
        max_retries: 最大重试次数
    
    Returns:
        websocket连接对象
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.info(f"WebSocket连接重试 {attempt}/{max_retries}")
                await asyncio.sleep(min(2 ** attempt, 10))  # 指数退避，最多10秒
            
            websocket = await websockets.connect(uri, **WEBSOCKET_CONFIG)
            logger.info(f"WebSocket连接成功 (尝试 {attempt + 1})")
            return websocket
            
        except Exception as e:
            last_error = e
            logger.warning(f"WebSocket连接失败 (尝试 {attempt + 1}): {str(e)}")
            
            if attempt == max_retries:
                break
    
    raise last_error or Exception("WebSocket连接失败")

async def send_websocket_message(websocket, message: dict, timeout: float = 10.0):
    """
    发送WebSocket消息，带超时控制
    
    Args:
        websocket: WebSocket连接
        message: 要发送的消息字典
        timeout: 发送超时时间
    """
    try:
        message_json = json.dumps(message)
        await asyncio.wait_for(websocket.send(message_json), timeout=timeout)
        logger.debug(f"发送消息: {message.get('type', 'unknown')}")
    except asyncio.TimeoutError:
        raise Exception(f"发送消息超时 ({timeout}秒)")
    except Exception as e:
        raise Exception(f"发送消息失败: {str(e)}")

async def receive_websocket_message(websocket, timeout: float = None):
    """
    接收WebSocket消息，带超时控制
    
    Args:
        websocket: WebSocket连接
        timeout: 接收超时时间，None使用默认值
    
    Returns:
        解析后的消息字典
    """
    if timeout is None:
        timeout = RECEIVE_TIMEOUT
    
    try:
        response_text = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        response = json.loads(response_text)
        logger.debug(f"接收消息: {response.get('type', 'unknown')}")
        return response
    except asyncio.TimeoutError:
        raise Exception(f"接收消息超时 ({timeout}秒)")
    except json.JSONDecodeError as e:
        raise Exception(f"消息格式错误: {str(e)}")
    except Exception as e:
        raise Exception(f"接收消息失败: {str(e)}")

class WebSocketManager:
    """WebSocket连接管理器，提供更高级的连接管理功能"""
    
    def __init__(self, uri: str):
        self.uri = uri
        self.websocket = None
        self.connected = False
    
    async def connect(self, max_retries: int = 3):
        """连接WebSocket"""
        try:
            self.websocket = await create_websocket_connection(self.uri, max_retries)
            self.connected = True
            logger.info("WebSocket管理器连接成功")
        except Exception as e:
            self.connected = False
            logger.error(f"WebSocket管理器连接失败: {str(e)}")
            raise
    
    async def disconnect(self):
        """断开WebSocket连接"""
        if self.websocket and self.connected:
            try:
                await self.websocket.close()
                logger.info("WebSocket管理器断开连接")
            except Exception as e:
                logger.warning(f"WebSocket断开连接时出错: {str(e)}")
            finally:
                self.websocket = None
                self.connected = False
    
    async def send_message(self, message: dict, timeout: float = 10.0):
        """发送消息"""
        if not self.connected or not self.websocket:
            raise Exception("WebSocket未连接")
        
        await send_websocket_message(self.websocket, message, timeout)
    
    async def receive_message(self, timeout: float = None):
        """接收消息"""
        if not self.connected or not self.websocket:
            raise Exception("WebSocket未连接")
        
        return await receive_websocket_message(self.websocket, timeout)
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()