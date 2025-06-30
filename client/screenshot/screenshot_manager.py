import base64
import io
from PIL import Image, ImageGrab
from typing import Optional
import time
import os

class ScreenshotManager:
    def __init__(self):
        self.last_screenshot_time = 0
        self.screenshot_interval = 0.5  # 最小截图间隔0.5秒
        
    def capture_screen(self) -> Optional[Image.Image]:
        """捕获整个屏幕"""
        try:
            screenshot = ImageGrab.grab()
            self.last_screenshot_time = time.time()
            return screenshot
        except Exception as e:
            print(f"截图失败: {e}")
            return None
    
    def capture_screen_to_base64(self) -> Optional[str]:
        """捕获屏幕并转换为base64字符串"""
        screenshot = self.capture_screen()
        if screenshot is None:
            return None
        
        try:
            # 压缩图片以减少传输大小
            screenshot = screenshot.resize((1280, 720), Image.Resampling.LANCZOS)
            
            # 转换为base64
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG', optimize=True)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return img_str
        except Exception as e:
            print(f"图片转换失败: {e}")
            return None
    
    def save_screenshot(self, filename: Optional[str] = None) -> Optional[str]:
        """保存截图到文件"""
        screenshot = self.capture_screen()
        if screenshot is None:
            return None
        
        try:
            if filename is None:
                timestamp = int(time.time())
                filename = f"screenshot_{timestamp}.png"
            
            # 确保目录存在
            os.makedirs("screenshots", exist_ok=True)
            filepath = os.path.join("screenshots", filename)
            
            screenshot.save(filepath)
            print(f"截图已保存: {filepath}")
            return filepath
        except Exception as e:
            print(f"保存截图失败: {e}")
            return None
    
    def get_screen_size(self) -> tuple:
        """获取屏幕分辨率"""
        try:
            screenshot = ImageGrab.grab()
            return screenshot.size
        except:
            return (1920, 1080)  # 默认分辨率

# 测试函数
def test_screenshot():
    manager = ScreenshotManager()
    
    print("测试截图功能...")
    
    # 测试基础截图
    screenshot = manager.capture_screen()
    if screenshot:
        print(f"截图成功，尺寸: {screenshot.size}")
    
    # 测试base64转换
    base64_str = manager.capture_screen_to_base64()
    if base64_str:
        print(f"Base64转换成功，长度: {len(base64_str)}")
    
    # 测试保存截图
    filepath = manager.save_screenshot()
    if filepath:
        print(f"截图保存成功: {filepath}")
    
    # 测试屏幕尺寸
    size = manager.get_screen_size()
    print(f"屏幕尺寸: {size}")

if __name__ == "__main__":
    test_screenshot()