#!/usr/bin/env python3
"""
测试分阶段显示功能
"""

import os
import sys
import time
import json
import base64
from PIL import Image
import io

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

def load_test_image() -> str:
    """加载测试图片"""
    # 使用小测试图片
    image_path = "/root/autodl-tmp/computer-use-agent/server/claude/img/small_test.png"
    
    if not os.path.exists(image_path):
        # 如果小图片不存在，创建一个
        print("📸 创建小测试图片...")
        exec(open("/root/autodl-tmp/computer-use-agent/create_small_test_image.py").read())
    
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    return base64.b64encode(image_data).decode('utf-8')

async def test_staged_websocket():
    """测试分阶段WebSocket通信"""
    import websockets
    import uuid
    
    try:
        # 加载测试图片
        image_base64 = load_test_image()
        print(f"✅ 测试图片加载成功，大小: {len(image_base64)} 字符")
        
        # 连接WebSocket
        uri = "ws://localhost:8000/ws"
        print(f"🔗 连接到: {uri}")
        
        async with websockets.connect(
            uri, 
            max_size=10*1024*1024,
            ping_interval=60,
            ping_timeout=30,
            close_timeout=30,
            compression=None
        ) as websocket:
            print("✅ WebSocket连接成功")
            
            # 构建测试请求
            task_id = str(uuid.uuid4())
            request = {
                "type": "analyze_task",
                "task_id": task_id,
                "timestamp": time.time(),
                "data": {
                    "text_command": "请分析这个VS Code界面，找到文件浏览器中的claude文件夹并点击",
                    "screenshot_base64": image_base64,
                    "user_id": "test_user"
                }
            }
            
            print(f"📤 发送任务请求: {request['data']['text_command']}")
            await websocket.send(json.dumps(request))
            
            # 接收分阶段响应
            response_count = 0
            while True:
                try:
                    print("⏳ 等待服务端响应...")
                    response_text = await websocket.recv()
                    response = json.loads(response_text)
                    response_count += 1
                    
                    message_type = response.get("type")
                    task_id_resp = response.get("task_id")
                    timestamp = response.get("timestamp")
                    
                    print(f"\n📨 收到响应 #{response_count}")
                    print(f"   类型: {message_type}")
                    print(f"   任务ID: {task_id_resp}")
                    print(f"   时间戳: {timestamp}")
                    
                    if message_type == "omniparser_result":
                        print("🔍 OmniParser 结果:")
                        data = response.get("data", {})
                        processing_time = data.get("processing_time", 0)
                        element_count = data.get("element_count", 0)
                        print(f"   处理时间: {processing_time:.2f}秒")
                        print(f"   检测元素: {element_count}个")
                        
                        ui_elements = data.get("ui_elements", [])
                        if ui_elements:
                            print("   UI元素示例:")
                            for i, elem in enumerate(ui_elements[:3]):
                                elem_type = elem.get('type', '未知')
                                description = elem.get('description', '无描述')[:40]
                                print(f"     {i+1}. {elem_type}: {description}")
                        
                        has_screenshot = bool(data.get("annotated_screenshot_base64"))
                        print(f"   标注截图: {'有' if has_screenshot else '无'}")
                        
                    elif message_type == "claude_result":
                        print("🧠 Claude 分析结果:")
                        data = response.get("data", {})
                        processing_time = data.get("processing_time", 0)
                        confidence = data.get("confidence", 0)
                        reasoning = data.get("reasoning", "")[:100]
                        actions = data.get("actions", [])
                        
                        print(f"   处理时间: {processing_time:.2f}秒")
                        print(f"   置信度: {confidence:.2%}")
                        print(f"   推理摘要: {reasoning}...")
                        print(f"   操作步骤: {len(actions)}个")
                        
                        if actions:
                            print("   操作示例:")
                            for i, action in enumerate(actions[:3]):
                                action_type = action.get('type', '未知')
                                description = action.get('description', '无描述')[:40]
                                print(f"     {i+1}. {action_type}: {description}")
                        
                    elif message_type == "analysis_result":
                        print("✅ 最终分析结果:")
                        data = response.get("data", {})
                        success = data.get("success", False)
                        print(f"   任务成功: {success}")
                        print("🏁 任务处理完成")
                        break
                        
                    elif message_type == "error":
                        print(f"❌ 错误响应: {response.get('message', '未知错误')}")
                        break
                        
                    else:
                        print(f"❓ 未知消息类型: {message_type}")
                        
                except Exception as e:
                    print(f"❌ 接收响应失败: {str(e)}")
                    break
            
            print(f"\n📊 总计收到 {response_count} 个响应")
            print("✅ 测试完成")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

def test_server_health():
    """测试服务器健康状态"""
    import requests
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print("🏥 服务器健康状态:")
            print(f"   状态: {health_data.get('status')}")
            
            omniparser = health_data.get('omniparser', {})
            print(f"   OmniParser: {'可用' if omniparser.get('available') else '不可用'}")
            
            claude = health_data.get('claude', {})
            print(f"   Claude: {'可用' if claude.get('available') else '不可用'}")
            
            return True
        else:
            print(f"❌ 服务器健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("分阶段显示功能测试")
    print("=" * 60)
    
    # 检查服务器状态
    if not test_server_health():
        print("\n💡 请先启动服务器: python start_server.py")
        sys.exit(1)
    
    # 测试分阶段WebSocket通信
    import asyncio
    asyncio.run(test_staged_websocket())
    
    print("\n=" * 60)
    print("测试完成")
    print("=" * 60)