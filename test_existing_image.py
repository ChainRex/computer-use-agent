#!/usr/bin/env python3
"""
使用现有图片测试Claude集成
"""

import os
import sys
import base64
import json
from PIL import Image
import io

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from server.claude import ClaudeService
from shared.schemas.data_models import UIElement

def load_existing_image() -> str:
    """加载现有的测试图片"""
    image_path = "/root/autodl-tmp/computer-use-agent/server/claude/img/image.png"
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"测试图片不存在: {image_path}")
    
    # 读取图片并转换为base64
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    return base64.b64encode(image_data).decode('utf-8')

def test_with_existing_image():
    """使用现有图片测试Claude服务"""
    print("🧪 使用现有图片测试Claude服务...")
    
    try:
        # 加载现有图片
        print("📂 加载现有测试图片...")
        image_base64 = load_existing_image()
        print(f"✅ 图片加载成功，大小: {len(image_base64)} 字符")
        
        # 初始化Claude服务
        claude_service = ClaudeService()
        print("✅ Claude服务初始化成功")
        
        # 创建一些模拟的UI元素（实际应用中这些会由OmniParser检测）
        ui_elements = [
            UIElement(
                id=1,
                type="button",
                description="按钮",
                coordinates=[100, 100, 200, 140],
                text="Click Me",
                confidence=0.9
            ),
            UIElement(
                id=2,
                type="textbox",
                description="文本输入框",
                coordinates=[100, 200, 400, 240],
                text="",
                confidence=0.8
            )
        ]
        
        # 测试不同的指令
        test_commands = [
            "点击按钮",
            "在文本框中输入hello world",
            "截图并保存",
            "打开计算器应用"
        ]
        
        for i, command in enumerate(test_commands, 1):
            print(f"\n--- 测试 {i}: {command} ---")
            
            try:
                # 生成唯一的文件名
                filename = f"analysis_test_{i}.png"
                
                # 调用Claude分析
                actions, reasoning, confidence = claude_service.analyze_task_with_claude(
                    command,
                    image_base64,
                    ui_elements
                )
                
                print(f"✅ 分析完成")
                print(f"🎯 置信度: {confidence}")
                print(f"💭 推理: {reasoning[:200]}...")  # 只显示前200字符
                print(f"📋 操作数量: {len(actions)}")
                
                # 显示操作详情
                for j, action in enumerate(actions[:3], 1):  # 只显示前3个操作
                    print(f"  {j}. {action.type}: {action.description}")
                    if action.coordinates:
                        print(f"     坐标: {action.coordinates}")
                
                if len(actions) > 3:
                    print(f"  ... 还有 {len(actions) - 3} 个操作")
                    
            except Exception as e:
                print(f"❌ 测试失败: {str(e)}")
        
        # 清理
        claude_service.cleanup()
        print("\n✅ 所有测试完成!")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_claude_command():
    """直接测试Claude命令"""
    print("\n🧪 直接测试Claude命令...")
    
    image_path = "/root/autodl-tmp/computer-use-agent/server/claude/img/image.png"
    
    if not os.path.exists(image_path):
        print(f"❌ 图片不存在: {image_path}")
        return False
    
    try:
        import subprocess
        
        # 构建测试命令
        prompt = "请描述这张图片中的内容，特别是UI元素"
        cmd = ["claude", "-p", prompt, image_path]
        
        print(f"🔧 执行命令: {' '.join(cmd)}")
        
        # 执行命令（5分钟超时）
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode == 0:
            print("✅ Claude命令执行成功")
            print(f"📝 响应长度: {len(result.stdout)} 字符")
            print(f"📄 响应内容:\n{result.stdout[:500]}...")
            return True
        else:
            print(f"❌ Claude命令失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 直接测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("使用现有图片测试Claude集成")
    print("=" * 60)
    
    # 首先测试直接的Claude命令
    direct_success = test_direct_claude_command()
    
    if direct_success:
        # 如果直接命令成功，再测试服务集成
        service_success = test_with_existing_image()
        
        if service_success:
            print("\n🎉 所有测试通过!")
        else:
            print("\n💥 服务集成测试失败!")
    else:
        print("\n⚠️ 跳过服务测试，Claude命令不可用")
    
    print("\n=" * 60)
    print("测试完成")
    print("=" * 60)