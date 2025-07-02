"""
输入法检测模块 - 检测当前系统的输入法状态
"""

import platform
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class InputMethodInfo:
    """输入法信息"""
    current_im: str  # 当前输入法
    language: str    # 当前语言
    layout: str      # 键盘布局
    available_ims: list  # 可用输入法列表
    is_ime_active: bool  # 是否为IME输入法激活状态
    
class InputMethodDetector:
    """输入法检测器 - 跨平台检测当前输入法状态"""
    
    def __init__(self):
        self.os_name = platform.system()
        self._setup_os_specific()
        logger.info(f"InputMethodDetector initialized for {self.os_name}")
    
    def _setup_os_specific(self):
        """设置操作系统特定的检测方法"""
        if self.os_name == "Darwin":  # macOS
            self._setup_macos()
        elif self.os_name == "Windows":
            self._setup_windows()
        else:  # Linux
            self._setup_linux()
    
    def _setup_macos(self):
        """设置macOS输入法检测"""
        try:
            # 尝试导入macOS特定库
            import subprocess
            self.has_macos_support = True
        except Exception as e:
            logger.warning(f"macOS输入法检测初始化失败: {e}")
            self.has_macos_support = False
    
    def _setup_windows(self):
        """设置Windows输入法检测"""
        try:
            # 尝试导入Windows特定库
            import ctypes
            import ctypes.wintypes
            self.has_windows_support = True
            
            # Windows API常量
            self.HC_ACTION = 0
            self.WM_INPUTLANGCHANGE = 0x0051
            self.user32 = ctypes.windll.user32
            self.kernel32 = ctypes.windll.kernel32
        except Exception as e:
            logger.warning(f"Windows输入法检测初始化失败: {e}")
            self.has_windows_support = False
    
    def _setup_linux(self):
        """设置Linux输入法检测"""
        try:
            import subprocess
            self.has_linux_support = True
        except Exception as e:
            logger.warning(f"Linux输入法检测初始化失败: {e}")
            self.has_linux_support = False
    
    def get_current_input_method(self) -> InputMethodInfo:
        """
        获取当前输入法信息
        
        Returns:
            InputMethodInfo: 输入法信息
        """
        try:
            if self.os_name == "Darwin":
                return self._get_macos_input_method()
            elif self.os_name == "Windows":
                return self._get_windows_input_method()
            else:
                return self._get_linux_input_method()
        except Exception as e:
            logger.error(f"获取输入法信息失败: {e}")
            return self._get_fallback_input_method()
    
    def _get_macos_input_method(self) -> InputMethodInfo:
        """获取macOS输入法信息"""
        if not self.has_macos_support:
            return self._get_fallback_input_method()
        
        try:
            import subprocess
            
            # 获取当前输入法
            result = subprocess.run([
                'defaults', 'read', 'com.apple.HIToolbox', 'AppleSelectedInputSources'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # 解析输出以获取当前输入法
                if 'Chinese' in output or '中文' in output:
                    current_im = "Chinese"
                    is_ime_active = True
                elif 'ABC' in output or 'English' in output:
                    current_im = "English"
                    is_ime_active = False
                else:
                    current_im = "Unknown"
                    is_ime_active = False
                
                return InputMethodInfo(
                    current_im=current_im,
                    language=current_im,
                    layout="QWERTY",
                    available_ims=["English", "Chinese"],
                    is_ime_active=is_ime_active
                )
        except Exception as e:
            logger.warning(f"macOS输入法检测失败: {e}")
        
        return self._get_fallback_input_method()
    
    def _get_windows_input_method(self) -> InputMethodInfo:
        """获取Windows输入法信息"""
        if not self.has_windows_support:
            return self._get_fallback_input_method()
        
        try:
            import ctypes
            import ctypes.wintypes
            
            # 获取前台窗口
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return self._get_fallback_input_method()
            
            # 获取线程ID
            thread_id = self.user32.GetWindowThreadProcessId(hwnd, None)
            
            # 获取输入法布局
            hkl = self.user32.GetKeyboardLayout(thread_id)
            
            # 解析语言ID
            lang_id = hkl & 0xFFFF
            
            # 常见的语言ID映射
            language_map = {
                0x0409: "English (US)",
                0x0804: "Chinese (Simplified)",
                0x0404: "Chinese (Traditional)",
                0x0411: "Japanese",
                0x0412: "Korean"
            }
            
            current_lang = language_map.get(lang_id, f"Unknown ({hex(lang_id)})")
            is_ime_active = lang_id not in [0x0409]  # 非英语认为是IME激活
            
            return InputMethodInfo(
                current_im=current_lang,
                language=current_lang,
                layout="QWERTY",
                available_ims=list(language_map.values()),
                is_ime_active=is_ime_active
            )
            
        except Exception as e:
            logger.warning(f"Windows输入法检测失败: {e}")
        
        return self._get_fallback_input_method()
    
    def _get_linux_input_method(self) -> InputMethodInfo:
        """获取Linux输入法信息"""
        if not self.has_linux_support:
            return self._get_fallback_input_method()
        
        try:
            import subprocess
            
            # 尝试多种方法检测输入法
            methods = [
                # 检查IBus
                ['ibus', 'engine'],
                # 检查fcitx
                ['fcitx-remote', '-n'],
                # 检查环境变量
                'env_check'
            ]
            
            for method in methods:
                try:
                    if method == 'env_check':
                        # 检查环境变量
                        import os
                        im_module = os.environ.get('GTK_IM_MODULE', '')
                        qt_im_module = os.environ.get('QT_IM_MODULE', '')
                        xmodifiers = os.environ.get('XMODIFIERS', '')
                        
                        if 'ibus' in (im_module + qt_im_module + xmodifiers).lower():
                            current_im = "IBus"
                            is_ime_active = True
                        elif 'fcitx' in (im_module + qt_im_module + xmodifiers).lower():
                            current_im = "Fcitx"
                            is_ime_active = True
                        else:
                            current_im = "English"
                            is_ime_active = False
                        
                        return InputMethodInfo(
                            current_im=current_im,
                            language=current_im,
                            layout="QWERTY",
                            available_ims=["English", "IBus", "Fcitx"],
                            is_ime_active=is_ime_active
                        )
                    else:
                        result = subprocess.run(method, capture_output=True, text=True, timeout=3)
                        if result.returncode == 0:
                            output = result.stdout.strip()
                            if output:
                                is_ime_active = 'pinyin' in output.lower() or 'chinese' in output.lower()
                                return InputMethodInfo(
                                    current_im=output,
                                    language=output,
                                    layout="QWERTY",
                                    available_ims=["English", output],
                                    is_ime_active=is_ime_active
                                )
                except subprocess.TimeoutExpired:
                    continue
                except FileNotFoundError:
                    continue
                except Exception as e:
                    logger.debug(f"Linux输入法检测方法 {method} 失败: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Linux输入法检测失败: {e}")
        
        return self._get_fallback_input_method()
    
    def _get_fallback_input_method(self) -> InputMethodInfo:
        """获取默认输入法信息（当检测失败时使用）"""
        return InputMethodInfo(
            current_im="Unknown",
            language="English",
            layout="QWERTY", 
            available_ims=["English"],
            is_ime_active=False
        )
    
    def get_input_method_dict(self) -> Dict[str, Any]:
        """
        获取输入法信息的字典格式
        
        Returns:
            Dict[str, Any]: 输入法信息字典
        """
        info = self.get_current_input_method()
        return {
            "current_im": info.current_im,
            "language": info.language,
            "layout": info.layout,
            "available_ims": info.available_ims,
            "is_ime_active": info.is_ime_active,
            "os_name": self.os_name
        }

# 全局实例
input_method_detector = InputMethodDetector()

def get_current_input_method_info() -> Dict[str, Any]:
    """
    便捷函数：获取当前输入法信息
    
    Returns:
        Dict[str, Any]: 输入法信息字典
    """
    return input_method_detector.get_input_method_dict()