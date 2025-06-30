#!/usr/bin/env python3
"""
Computer Use Agent - 服务端入口
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from server.api.main import app
import uvicorn

if __name__ == "__main__":
    print("🚀 启动Computer Use Agent服务端...")
    print("📡 WebSocket地址: ws://localhost:8000/ws")
    print("📖 API文档: http://localhost:8000/docs")
    print("❤️  健康检查: http://localhost:8000/health")
    
    uvicorn.run(
        "server.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )