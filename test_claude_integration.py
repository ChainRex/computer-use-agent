#!/usr/bin/env python3
"""
Claude集成测试脚本
测试Claude服务的图像处理和指令生成功能
"""

import os
import sys
import base64
import json
from PIL import Image, ImageDraw
import io

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from server.claude import ClaudeService
from shared.schemas.data_models import UIElement

def create_test_image() -> str:
    """创建一个测试用的屏幕截图"""
    # 创建一个简单的测试图像
    width, height = 800, 600
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # 绘制一些UI元素
    # 按钮1
    draw.rectangle([100, 100, 200, 140], fill='lightblue', outline='blue')
    draw.text((120, 115), "Button 1", fill='black')
    
    # 按钮2
    draw.rectangle([250, 100, 350, 140], fill='lightgreen', outline='green')
    draw.text((270, 115), "Button 2", fill='black')
    
    # 文本框
    draw.rectangle([100, 200, 400, 240], fill='white', outline='gray')
    draw.text((110, 215), "Enter text here...", fill='gray')
    
    # 标题
    draw.text((100, 50), "Test Application", fill='black')
    
    # 转换为base64
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_data = buffer.getvalue()
    return base64.b64encode(image_data).decode('utf-8')

def create_test_ui_elements() -> list:
    """创建测试用的UI元素列表"""
    return [
        UIElement(
            id=1,
            type="button",
            description="Button 1",
            coordinates=[100, 100, 200, 140],
            text="Button 1",
            confidence=0.9
        ),
        UIElement(
            id=2,
            type="button", 
            description="Button 2",
            coordinates=[250, 100, 350, 140],
            text="Button 2",
            confidence=0.9
        ),
        UIElement(
            id=3,
            type="textbox",
            description="Text input field",
            coordinates=[100, 200, 400, 240],
            text="Enter text here...",
            confidence=0.8
        )
    ]

def test_claude_service():
    """测试Claude服务"""
    print("🧪 开始测试Claude服务...")
    
    try:
        # 初始化Claude服务
        claude_service = ClaudeService()
        print("✅ Claude服务初始化成功")
        
        # 创建测试数据
        test_image_base64 = create_test_image()
        test_ui_elements = create_test_ui_elements()
        test_command = "点击第一个按钮"
        
        print(f"📝 测试指令: {test_command}")
        print(f"🖼️ 测试图像大小: {len(test_image_base64)} 字符")
        print(f"🎯 UI元素数量: {len(test_ui_elements)}")
        
        # 测试Claude分析
        print("\n🧠 调用Claude分析...")
        actions, reasoning, confidence = claude_service.analyze_task_with_claude(
            test_command,
            test_image_base64,
            test_ui_elements
        )
        
        # 输出结果
        print(f"\n✅ Claude分析完成!")
        print(f"🎯 置信度: {confidence}")
        print(f"💭 推理过程: {reasoning}")
        print(f"📋 生成操作步骤数量: {len(actions)}")
        
        print("\n📋 详细操作步骤:")
        for i, action in enumerate(actions, 1):
            print(f"  {i}. {action.type}: {action.description}")
            if action.coordinates:
                print(f"     坐标: {action.coordinates}")
            if action.text:
                print(f"     文本: '{action.text}'")
            if action.duration:
                print(f"     持续时间: {action.duration}秒")
        
        # 清理
        claude_service.cleanup()
        print("\n✅ 测试完成!")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_fallback_mode():
    """测试降级模式（Claude不可用时）"""
    print("\n🧪 测试降级模式...")
    
    # 模拟Claude不可用的情况
    # 这里可以通过修改环境或配置来测试
    print("📝 降级模式测试需要手动配置")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Claude集成测试")
    print("=" * 60)
    
    # 检查Claude CLI是否可用
    try:
        import subprocess
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Claude CLI 已安装")
            claude_available = True
        else:
            print("⚠️ Claude CLI 未正确安装或配置")
            claude_available = False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Claude CLI 未找到")
        claude_available = False
    
    if claude_available:
        success = test_claude_service()
        if success:
            print("\n🎉 所有测试通过!")
        else:
            print("\n💥 测试失败!")
            sys.exit(1)
    else:
        print("\n⚠️ 跳过Claude测试，CLI不可用")
        print("💡 请安装Claude CLI并配置认证")
        print("💡 参考: https://docs.anthropic.com/claude/docs/cli")
    
    # 测试降级模式
    test_fallback_mode()
    
    print("\n=" * 60)
    print("测试完成")
    print("=" * 60)