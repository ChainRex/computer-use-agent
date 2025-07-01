#!/usr/bin/env python3
"""
创建一个小的测试图片
"""

import base64
import io
from PIL import Image, ImageDraw

def create_small_test_image():
    """创建一个小的测试图片"""
    # 创建较小的图片 (400x300)
    width, height = 400, 300
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # 绘制一些简单的UI元素
    # 标题栏
    draw.rectangle([0, 0, width, 30], fill='lightgray')
    draw.text((10, 8), "Test Application", fill='black')
    
    # 按钮1
    draw.rectangle([50, 60, 150, 90], fill='lightblue', outline='blue')
    draw.text((70, 70), "Button 1", fill='black')
    
    # 按钮2  
    draw.rectangle([200, 60, 300, 90], fill='lightgreen', outline='green')
    draw.text((220, 70), "Button 2", fill='black')
    
    # 文本框
    draw.rectangle([50, 120, 300, 150], fill='white', outline='gray')
    draw.text((60, 130), "Enter text here...", fill='gray')
    
    # 状态栏
    draw.rectangle([0, height-20, width, height], fill='lightgray')
    draw.text((10, height-15), "Ready", fill='black')
    
    # 转换为base64
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_data = buffer.getvalue()
    base64_str = base64.b64encode(image_data).decode('utf-8')
    
    # 保存到文件
    test_image_path = "/root/autodl-tmp/computer-use-agent/server/claude/img/small_test.png"
    with open(test_image_path, 'wb') as f:
        f.write(image_data)
    
    print(f"✅ 创建小测试图片: {test_image_path}")
    print(f"📏 图片尺寸: {width}x{height}")
    print(f"📊 Base64大小: {len(base64_str)} 字符")
    
    return base64_str

if __name__ == "__main__":
    create_small_test_image()