import base64
import io
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageGrab
from typing import Optional
import time
import os

class ScreenshotManager:
    def __init__(self):
        self.last_screenshot_time = 0
        self.screenshot_interval = 0.5  # 最小截图间隔0.5秒
        
        # 线程池用于异步截图操作
        self.thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="screenshot")
        
    
    def _capture_screen_sync(self) -> Optional[Image.Image]:
        """同步捕获屏幕（内部方法）"""
        try:
            screenshot = ImageGrab.grab()
            self.last_screenshot_time = time.time()
            return screenshot
        except Exception as e:
            print(f"截图失败: {e}")
            return None
    
    def capture_screen(self) -> Optional[Image.Image]:
        """捕获整个屏幕（同步方法，保持向后兼容）"""
        return self._capture_screen_sync()
    
    def capture_screen_async(self, callback=None):
        """异步捕获屏幕"""
        def capture_and_callback():
            screenshot = self._capture_screen_sync()
            if callback:
                callback(screenshot)
            return screenshot
        
        return self.thread_pool.submit(capture_and_callback)
    
    def capture_screen_to_base64(self) -> Optional[str]:
        """捕获屏幕并转换为base64字符串"""
        screenshot = self._capture_screen_sync()
        if screenshot is None:
            return None
        
        try:
            base64_str = self._process_image_to_base64(screenshot)
            return base64_str
        except Exception as e:
            print(f"图片转换失败: {e}")
            return None
    
    def _process_image_to_base64(self, screenshot: Image.Image) -> str:
        """处理图像到base64（可在线程池中执行）"""
        # 压缩图片以减少传输大小
        compressed = screenshot.resize((1280, 720), Image.Resampling.LANCZOS)
        
        # 如果图像有透明通道，转换为RGB模式
        if compressed.mode in ('RGBA', 'LA', 'P'):
            # 创建白色背景
            rgb_image = Image.new('RGB', compressed.size, (255, 255, 255))
            if compressed.mode == 'P':
                compressed = compressed.convert('RGBA')
            # 将原图像粘贴到白色背景上
            rgb_image.paste(compressed, mask=compressed.split()[-1] if compressed.mode == 'RGBA' else None)
            compressed = rgb_image
        
        # 转换为base64
        buffer = io.BytesIO()
        compressed.save(buffer, format='JPEG', quality=85, optimize=True)  # 使用JPEG减少大小
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        # 释放临时图像
        del compressed
        buffer.close()
        
        return img_str
    
    def capture_screen_to_base64_async(self, callback=None):
        """异步捕获屏幕并转换为base64"""
        def capture_and_convert():
            result = self.capture_screen_to_base64()
            if callback:
                callback(result)
            return result
        
        return self.thread_pool.submit(capture_and_convert)
    
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
            size = screenshot.size
            del screenshot  # 释放临时截图
            return size
        except:
            return (1920, 1080)  # 默认分辨率
    
    def shutdown(self):
        """关闭截图管理器，清理资源"""
        self.thread_pool.shutdown(wait=True)
        print("ScreenshotManager已关闭")

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