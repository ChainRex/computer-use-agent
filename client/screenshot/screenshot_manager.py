import base64
import io
import threading
import queue
import gc
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageGrab
from typing import Optional, Dict, Tuple
import time
import os
import weakref

class ScreenshotManager:
    def __init__(self):
        self.last_screenshot_time = 0
        self.screenshot_interval = 0.5  # 最小截图间隔0.5秒
        
        # 线程池用于异步截图操作
        self.thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="screenshot")
        
        # 缓存机制
        self._cache_lock = threading.Lock()
        self._image_cache: Dict[str, Tuple[Image.Image, float]] = {}  # key: (image, timestamp)
        self._base64_cache: Dict[str, Tuple[str, float]] = {}  # key: (base64_str, timestamp)
        self.cache_ttl = 2.0  # 缓存过期时间2秒
        self.max_cache_size = 5  # 最大缓存数量
        
        # 性能统计
        self.stats = {
            'total_screenshots': 0,
            'cache_hits': 0,
            'avg_capture_time': 0.0
        }
        
        # 启动缓存清理线程
        self._start_cache_cleaner()
        
    def _start_cache_cleaner(self):
        """启动缓存清理线程"""
        def cache_cleaner():
            while True:
                time.sleep(30)  # 每30秒清理一次过期缓存
                self._clean_expired_cache()
        
        cleaner_thread = threading.Thread(target=cache_cleaner, daemon=True, name="cache_cleaner")
        cleaner_thread.start()
    
    def _clean_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        with self._cache_lock:
            # 清理过期的图像缓存
            expired_keys = [k for k, (_, timestamp) in self._image_cache.items() 
                           if current_time - timestamp > self.cache_ttl]
            for key in expired_keys:
                image, _ = self._image_cache.pop(key)
                del image  # 显式释放图像对象
            
            # 清理过期的base64缓存
            expired_keys = [k for k, (_, timestamp) in self._base64_cache.items() 
                           if current_time - timestamp > self.cache_ttl]
            for key in expired_keys:
                self._base64_cache.pop(key)
            
            # 限制缓存大小
            if len(self._image_cache) > self.max_cache_size:
                oldest_keys = sorted(self._image_cache.keys(), 
                                   key=lambda k: self._image_cache[k][1])[:len(self._image_cache) - self.max_cache_size]
                for key in oldest_keys:
                    image, _ = self._image_cache.pop(key)
                    del image
            
            if len(self._base64_cache) > self.max_cache_size:
                oldest_keys = sorted(self._base64_cache.keys(), 
                                   key=lambda k: self._base64_cache[k][1])[:len(self._base64_cache) - self.max_cache_size]
                for key in oldest_keys:
                    self._base64_cache.pop(key)
        
        # 触发垃圾回收
        gc.collect()
    
    def _capture_screen_sync(self) -> Optional[Image.Image]:
        """同步捕获屏幕（内部方法）"""
        try:
            start_time = time.time()
            screenshot = ImageGrab.grab()
            capture_time = time.time() - start_time
            
            # 更新性能统计
            self.stats['total_screenshots'] += 1
            self.stats['avg_capture_time'] = (
                (self.stats['avg_capture_time'] * (self.stats['total_screenshots'] - 1) + capture_time) 
                / self.stats['total_screenshots']
            )
            
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
    
    def _generate_cache_key(self) -> str:
        """生成缓存键（基于时间戳和屏幕尺寸）"""
        screen_size = self.get_screen_size()
        # 使用秒级时间戳作为缓存键，同一秒内的截图可以复用
        timestamp_key = int(time.time())
        return f"{screen_size[0]}x{screen_size[1]}_{timestamp_key}"
    
    def capture_screen_to_base64(self) -> Optional[str]:
        """捕获屏幕并转换为base64字符串（带缓存）"""
        # 检查缓存
        cache_key = self._generate_cache_key()
        with self._cache_lock:
            if cache_key in self._base64_cache:
                base64_str, timestamp = self._base64_cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    self.stats['cache_hits'] += 1
                    return base64_str
        
        # 缓存未命中，重新截图
        screenshot = self._capture_screen_sync()
        if screenshot is None:
            return None
        
        try:
            # 异步处理图像压缩和编码
            base64_str = self._process_image_to_base64(screenshot)
            
            # 更新缓存
            with self._cache_lock:
                self._base64_cache[cache_key] = (base64_str, time.time())
            
            return base64_str
        except Exception as e:
            print(f"图片转换失败: {e}")
            return None
    
    def _process_image_to_base64(self, screenshot: Image.Image) -> str:
        """处理图像到base64（可在线程池中执行）"""
        # 压缩图片以减少传输大小
        compressed = screenshot.resize((1280, 720), Image.Resampling.LANCZOS)
        
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
    
    def get_performance_stats(self) -> Dict:
        """获取性能统计信息"""
        with self._cache_lock:
            cache_info = {
                'image_cache_size': len(self._image_cache),
                'base64_cache_size': len(self._base64_cache),
                'cache_hit_rate': (self.stats['cache_hits'] / max(1, self.stats['total_screenshots'])) * 100
            }
        
        return {**self.stats, **cache_info}
    
    def clear_cache(self):
        """手动清理所有缓存"""
        with self._cache_lock:
            # 释放图像对象
            for image, _ in self._image_cache.values():
                del image
            self._image_cache.clear()
            self._base64_cache.clear()
        gc.collect()
        print("缓存已清理")
    
    def shutdown(self):
        """关闭截图管理器，清理资源"""
        self.clear_cache()
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