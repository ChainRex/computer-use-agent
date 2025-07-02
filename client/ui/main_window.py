import sys
import asyncio
import os
import platform
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QTextEdit, QLabel, QLineEdit, 
                            QTextBrowser, QSplitter, QFrame, QTabWidget, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QScrollArea, QComboBox, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex
from PyQt6.QtGui import QFont, QPixmap

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from client.screenshot.screenshot_manager import ScreenshotManager
from client.communication.server_client import ServerClient
from client.automation import ExecutionManager, ExecutionConfig, ExecutionMode

class ScreenshotWorker(QThread):
    """专用截图工作线程"""
    screenshot_ready = pyqtSignal(object, str)  # PIL图像, base64数据
    screenshot_failed = pyqtSignal(str)  # 错误信息
    
    def __init__(self, screenshot_manager):
        super().__init__()
        self.screenshot_manager = screenshot_manager
        self.should_run = True
        self.mutex = QMutex()
        self.interval = 5.0  # 默认5秒间隔，减少频率
        
    def set_interval(self, seconds: float):
        """设置截图间隔"""
        self.mutex.lock()
        self.interval = max(1.0, seconds)  # 最小1秒间隔
        self.mutex.unlock()
    
    def stop(self):
        """停止截图线程"""
        self.should_run = False
        
    def run(self):
        """线程主循环"""
        while self.should_run:
            try:
                # 异步获取截图
                future = self.screenshot_manager.capture_screen_async()
                screenshot = future.result(timeout=5.0)  # 5秒超时
                
                if screenshot:
                    # 异步获取base64
                    base64_future = self.screenshot_manager.capture_screen_to_base64_async()
                    base64_data = base64_future.result(timeout=5.0)
                    
                    if base64_data:
                        self.screenshot_ready.emit(screenshot, base64_data)
                    else:
                        self.screenshot_failed.emit("Base64转换失败")
                else:
                    self.screenshot_failed.emit("截图失败")
                    
            except Exception as e:
                self.screenshot_failed.emit(f"截图线程错误: {str(e)}")
            
            # 等待下次截图
            self.msleep(int(self.interval * 1000))


class ConnectWorker(QThread):
    """处理连接的工作线程"""
    connection_result = pyqtSignal(bool, object)  # 连接结果信号(成功状态, ServerClient对象)
    
    def __init__(self, server_url):
        super().__init__()
        self.server_url = server_url
    
    def run(self):
        """在子线程中运行连接"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 在工作线程中创建ServerClient
            server_client = ServerClient(self.server_url)
            
            # 运行连接
            success = loop.run_until_complete(server_client.connect())
            
            if success:
                self.connection_result.emit(True, server_client)
            else:
                self.connection_result.emit(False, None)
                
        except Exception as e:
            print(f"连接错误: {e}")
            self.connection_result.emit(False, None)
        finally:
            loop.close()

class DisconnectWorker(QThread):
    """处理断开连接的工作线程"""
    disconnection_result = pyqtSignal(bool)  # 断开结果信号
    
    def __init__(self, server_client):
        super().__init__()
        self.server_client = server_client
    
    def run(self):
        """在子线程中运行断开连接"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行断开连接
            loop.run_until_complete(self.server_client.disconnect())
            self.disconnection_result.emit(True)
                
        except Exception as e:
            print(f"断开连接错误: {e}")
            self.disconnection_result.emit(False)
        finally:
            loop.close()

class TaskWorker(QThread):
    """处理异步任务的工作线程（支持分阶段响应）"""
    task_completed = pyqtSignal(object)  # 任务完成信号
    task_failed = pyqtSignal(str)        # 任务失败信号
    omniparser_result = pyqtSignal(object)  # OmniParser结果信号
    claude_result = pyqtSignal(object)      # Claude结果信号
    
    def __init__(self, server_url, text_command, screenshot_base64):
        super().__init__()
        self.server_url = server_url
        self.text_command = text_command
        self.screenshot_base64 = screenshot_base64
        self.os_info = self._get_os_info()
        self.input_method_info = self._get_input_method_info()
    
    def _get_os_info(self):
        """获取操作系统信息"""
        try:
            return {
                "system": platform.system(),
                "version": platform.version(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "platform": platform.platform()
            }
        except Exception as e:
            return {
                "system": "Unknown",
                "version": "Unknown",
                "release": "Unknown", 
                "machine": "Unknown",
                "processor": "Unknown",
                "platform": "Unknown",
                "error": str(e)
            }
    
    def _get_input_method_info(self):
        """获取输入法信息"""
        try:
            # 导入输入法检测模块
            import sys
            import os
            client_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if client_dir not in sys.path:
                sys.path.append(client_dir)
            
            from utils.input_method_detector import get_current_input_method_info
            return get_current_input_method_info()
        except Exception as e:
            print(f"获取输入法信息失败: {e}")
            return {
                "current_im": "Unknown",
                "language": "English",
                "layout": "QWERTY",
                "available_ims": ["English"],
                "is_ime_active": False,
                "os_name": platform.system()
            }
    
    def run(self):
        """在子线程中运行异步任务（支持分阶段响应）"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行异步任务
            loop.run_until_complete(self._run_async_task())
                
        except Exception as e:
            self.task_failed.emit(f"任务执行失败: {str(e)}")
        finally:
            loop.close()
    
    async def _run_async_task(self):
        """异步任务执行"""
        import sys
        import os
        import json
        import uuid
        import time
        
        # 添加客户端目录到路径以导入websocket_config
        client_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if client_dir not in sys.path:
            sys.path.append(client_dir)
        
        try:
            from websocket_config import WebSocketManager
            
            # 使用WebSocket管理器
            async with WebSocketManager(self.server_url) as ws_manager:
                # 构建任务请求
                task_id = str(uuid.uuid4())
                request = {
                    "type": "analyze_task",
                    "task_id": task_id,
                    "timestamp": time.time(),
                    "data": {
                        "text_command": self.text_command,
                        "screenshot_base64": self.screenshot_base64,
                        "user_id": "default",
                        "os_info": self.os_info,
                        "input_method_info": self.input_method_info
                    }
                }
                
                # 发送请求
                await ws_manager.send_message(request)
                
                # 接收分阶段响应
                while True:
                    try:
                        response = await ws_manager.receive_message()
                        message_type = response.get("type")
                        
                        if message_type == "omniparser_result":
                            # OmniParser结果
                            self.omniparser_result.emit(response)
                        elif message_type == "claude_result":
                            # Claude分析结果
                            self.claude_result.emit(response)
                        elif message_type == "analysis_result":
                            # 最终结果
                            self.task_completed.emit(response)
                            break
                        elif message_type == "error":
                            self.task_failed.emit(response.get("message", "服务端错误"))
                            break
                        else:
                            print(f"未知消息类型: {message_type}")
                            
                    except Exception as e:
                        if "超时" in str(e):
                            self.task_failed.emit(f"服务端响应超时: {str(e)}")
                        else:
                            self.task_failed.emit(f"接收响应失败: {str(e)}")
                        break
                        
        except Exception as e:
            self.task_failed.emit(f"连接失败: {str(e)}")

class TaskCompletionVerificationWorker(QThread):
    """任务完成度验证工作线程"""
    verification_completed = pyqtSignal(object)  # 验证完成信号
    verification_failed = pyqtSignal(str)        # 验证失败信号
    
    def __init__(self, server_url, task_id, original_command, previous_claude_output, screenshot_base64, verification_prompt):
        super().__init__()
        self.server_url = server_url
        self.task_id = task_id
        self.original_command = original_command
        self.previous_claude_output = previous_claude_output
        self.screenshot_base64 = screenshot_base64
        self.verification_prompt = verification_prompt
    
    def run(self):
        """在子线程中运行任务完成度验证"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行异步验证任务
            loop.run_until_complete(self._run_async_verification())
                
        except Exception as e:
            self.verification_failed.emit(f"验证执行失败: {str(e)}")
        finally:
            loop.close()
    
    async def _run_async_verification(self):
        """异步任务完成度验证"""
        import sys
        import os
        import json
        import time
        
        # 添加客户端目录到路径
        client_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if client_dir not in sys.path:
            sys.path.append(client_dir)
        
        try:
            from websocket_config import WebSocketManager
            
            # 使用WebSocket管理器
            async with WebSocketManager(self.server_url) as ws_manager:
                # 构建验证请求
                request = {
                    "type": "verify_task_completion",
                    "task_id": self.task_id,
                    "timestamp": time.time(),
                    "data": {
                        "original_command": self.original_command,
                        "previous_claude_output": self.previous_claude_output,
                        "screenshot_base64": self.screenshot_base64,
                        "verification_prompt": self.verification_prompt
                    }
                }
                
                # 发送请求
                await ws_manager.send_message(request)
                
                # 接收响应
                try:
                    response = await ws_manager.receive_message()
                    message_type = response.get("type")
                    
                    if message_type == "task_completion_result":
                        self.verification_completed.emit(response)
                    elif message_type == "error":
                        self.verification_failed.emit(response.get("message", "服务端验证错误"))
                    else:
                        self.verification_failed.emit(f"未知响应类型: {message_type}")
                        
                except Exception as e:
                    if "超时" in str(e):
                        self.verification_failed.emit(f"验证超时: {str(e)}")
                    else:
                        self.verification_failed.emit(f"接收验证响应失败: {str(e)}")
                        
        except Exception as e:
            self.verification_failed.emit(f"连接验证服务失败: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Computer Use Agent - 客户端 (优化版)")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化组件
        self.screenshot_manager = ScreenshotManager()
        self.server_client = None  # 在连接时创建
        self.current_screenshot_base64 = None
        self.current_screenshot_image = None
        
        # 初始化自动化执行管理器
        execution_config = ExecutionConfig(
            mode=ExecutionMode.SEMI_AUTO,
            confirm_dangerous_actions=True,
            screenshot_enabled=True,
            strict_mode=False,
            auto_retry=True
        )
        self.execution_manager = ExecutionManager(execution_config)
        
        # 执行相关数据
        self.current_action_plan = []
        self.current_ui_elements = []
        self.current_task_command = None  # 保存当前任务的原始指令
        self.current_claude_output = None  # 保存当前Claude输出
        
        # 设置UI
        self.setup_ui()
        
        # 连接执行管理器信号
        self._connect_execution_signals()
        
        # 启动截图工作线程
        self.screenshot_worker = ScreenshotWorker(self.screenshot_manager)
        self.screenshot_worker.screenshot_ready.connect(self.on_screenshot_ready)
        self.screenshot_worker.screenshot_failed.connect(self.on_screenshot_failed)
        self.screenshot_worker.start()
        
        
        # 用于缓存待更新的截图数据
        self.pending_screenshot_update = None
        
        # 初始截图（异步）
        self.manual_capture_screenshot()
    
    def setup_ui(self):
        """设置用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 标题
        title_label = QLabel("Computer Use Agent")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 分割器 - 左右布局
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧面板 - 控制区域
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧面板 - 截图预览
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割器比例
        splitter.setSizes([600, 600])
        
        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        status_widget = QWidget()
        status_widget.setLayout(status_layout)
        main_layout.addWidget(status_widget)
    
    def create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # 服务端连接区域
        connection_layout = QHBoxLayout()
        self.server_url_input = QLineEdit("ws://localhost:8000/ws")
        self.connect_btn = QPushButton("连接服务端")
        self.connect_btn.clicked.connect(self.toggle_connection)
        connection_layout.addWidget(QLabel("服务端地址:"))
        connection_layout.addWidget(self.server_url_input)
        connection_layout.addWidget(self.connect_btn)
        layout.addLayout(connection_layout)
        
        # 指令输入区域
        layout.addWidget(QLabel("输入指令:"))
        self.command_input = QTextEdit()
        self.command_input.setMaximumHeight(100)
        self.command_input.setPlaceholderText("请输入要执行的指令，例如：帮我打开计算器")
        layout.addWidget(self.command_input)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.screenshot_btn = QPushButton("手动截图")
        self.screenshot_btn.clicked.connect(self.manual_capture_screenshot)
        
        self.send_task_btn = QPushButton("发送任务")
        self.send_task_btn.clicked.connect(self.send_task)
        self.send_task_btn.setEnabled(True)  # 现在任务工作线程会自己连接
        
        
        button_layout.addWidget(self.screenshot_btn)
        button_layout.addWidget(self.send_task_btn)
        layout.addLayout(button_layout)
        
        # 执行状态显示（简化版）
        execution_frame = QFrame()
        execution_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        execution_layout = QVBoxLayout(execution_frame)
        execution_layout.addWidget(QLabel("🎮 自动化执行状态:"))
        
        self.execution_status = QLabel("执行状态: 就绪")
        execution_layout.addWidget(self.execution_status)
        
        layout.addWidget(execution_frame)
        
        # 创建标签页面板
        self.tab_widget = QTabWidget()
        
        # 第一个标签页：执行结果
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        
        # 分割器 - 上下布局，上半部分显示OmniParser结果，下半部分显示Claude结果
        result_splitter = QSplitter(Qt.Orientation.Vertical)
        result_layout.addWidget(result_splitter)
        
        # OmniParser结果区域
        omni_frame = QFrame()
        omni_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        omni_layout = QVBoxLayout(omni_frame)
        omni_layout.addWidget(QLabel("🔍 OmniParser 屏幕元素检测结果:"))
        self.omniparser_display = QTextBrowser()
        self.omniparser_display.setMaximumHeight(200)
        omni_layout.addWidget(self.omniparser_display)
        result_splitter.addWidget(omni_frame)
        
        # Claude分析结果区域
        claude_frame = QFrame()
        claude_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        claude_layout = QVBoxLayout(claude_frame)
        claude_layout.addWidget(QLabel("🧠 Claude 智能分析结果:"))
        self.claude_display = QTextBrowser()
        claude_layout.addWidget(self.claude_display)
        result_splitter.addWidget(claude_frame)
        
        # 设置分割器比例
        result_splitter.setSizes([150, 300])
        
        # 保持原有的统一结果显示（兼容性）
        result_layout.addWidget(QLabel("📋 任务执行结果:"))
        self.result_display = QTextBrowser()
        self.result_display.setMaximumHeight(150)
        result_layout.addWidget(self.result_display)
        
        self.tab_widget.addTab(result_tab, "分析结果")
        
        # 第二个标签页：UI元素详情
        elements_tab = QWidget()
        elements_layout = QVBoxLayout(elements_tab)
        elements_layout.addWidget(QLabel("检测到的UI元素:"))
        
        # UI元素表格
        self.elements_table = QTableWidget()
        self.elements_table.setColumnCount(5)
        self.elements_table.setHorizontalHeaderLabels(['ID', '类型', '描述', '坐标', '文本'])
        
        # 设置表格列宽
        header = self.elements_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID列
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 类型列
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)            # 描述列
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 坐标列
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 文本列
        
        elements_layout.addWidget(self.elements_table)
        
        # UI元素统计信息
        self.elements_stats = QLabel("UI元素统计: 暂无数据")
        elements_layout.addWidget(self.elements_stats)
        
        self.tab_widget.addTab(elements_tab, "UI元素详情")
        
        layout.addWidget(self.tab_widget)
        
        return panel
    
    def create_right_panel(self) -> QWidget:
        """创建右侧截图预览面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # 创建分割器来分上下两部分
        screenshot_splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(screenshot_splitter)
        
        # 上半部分：原始截图
        original_frame = QFrame()
        original_layout = QVBoxLayout(original_frame)
        original_layout.addWidget(QLabel("当前屏幕截图:"))
        
        self.screenshot_label = QLabel()
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_label.setStyleSheet("border: 1px solid gray;")
        self.screenshot_label.setText("暂无截图")
        self.screenshot_label.setMinimumHeight(200)
        original_layout.addWidget(self.screenshot_label)
        
        # 截图信息
        self.screenshot_info = QLabel("截图信息: 暂无")
        original_layout.addWidget(self.screenshot_info)
        
        screenshot_splitter.addWidget(original_frame)
        
        # 下半部分：OmniParser标注截图
        annotated_frame = QFrame()
        annotated_layout = QVBoxLayout(annotated_frame)
        annotated_layout.addWidget(QLabel("OmniParser标注截图:"))
        
        self.annotated_screenshot_label = QLabel()
        self.annotated_screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.annotated_screenshot_label.setStyleSheet("border: 1px solid blue;")
        self.annotated_screenshot_label.setText("等待分析结果...")
        self.annotated_screenshot_label.setMinimumHeight(200)
        annotated_layout.addWidget(self.annotated_screenshot_label)
        
        # 标注截图信息
        self.annotated_info = QLabel("OmniParser信息: 暂无")
        annotated_layout.addWidget(self.annotated_info)
        
        screenshot_splitter.addWidget(annotated_frame)
        
        # 设置分割器比例
        screenshot_splitter.setSizes([250, 250])
        
        return panel
    
    def toggle_connection(self):
        """切换服务端连接状态"""
        if self.server_client is None or not self.server_client.connected:
            # 尝试连接
            self.connect_to_server()
        else:
            # 断开连接
            self.disconnect_from_server()
    
    def connect_to_server(self):
        """连接到服务端"""
        self.connect_btn.setEnabled(False)
        self.status_label.setText("连接中...")
        
        # 创建连接工作线程
        self.connect_worker = ConnectWorker(self.server_url_input.text())
        self.connect_worker.connection_result.connect(self.on_connection_result)
        self.connect_worker.start()
    
    def on_connection_result(self, success, server_client):
        """连接结果回调"""
        if success:
            self.server_client = server_client
            self.connect_btn.setText("断开连接")
            self.status_label.setText("已连接到服务端")
            self.result_display.append("✅ 成功连接到服务端")
        else:
            self.status_label.setText("连接失败")
            self.result_display.append("❌ 连接服务端失败")
        
        self.connect_btn.setEnabled(True)
    
    def disconnect_from_server(self):
        """断开服务端连接"""
        self.connect_btn.setEnabled(False)
        self.status_label.setText("断开连接中...")
        
        # 创建断开连接工作线程
        self.disconnect_worker = DisconnectWorker(self.server_client)
        self.disconnect_worker.disconnection_result.connect(self.on_disconnection_result)
        self.disconnect_worker.start()
    
    def on_disconnection_result(self, success):
        """断开连接结果回调"""
        self.server_client = None
        self.connect_btn.setText("连接服务端")
        self.status_label.setText("已断开连接")
        self.result_display.append("🔌 已断开服务端连接")
        self.connect_btn.setEnabled(True)
    
    def on_screenshot_ready(self, screenshot_image, base64_data):
        """截图准备就绪的回调（在截图线程中调用）"""
        self.current_screenshot_base64 = base64_data
        self.current_screenshot_image = screenshot_image
        
        # 使用防抖机制更新UI
        self.pending_screenshot_update = (screenshot_image, base64_data)
        # 使用QTimer.singleShot在主线程中延迟执行UI更新
        QTimer.singleShot(100, self.update_screenshot_display)
    
    def on_screenshot_failed(self, error_msg):
        """截图失败的回调"""
        self.status_label.setText(f"截图失败: {error_msg}")
    
    
    def update_screenshot_display(self):
        """更新截图显示（防抖后执行）"""
        if not self.pending_screenshot_update:
            return
            
        screenshot_image, base64_data = self.pending_screenshot_update
        self.pending_screenshot_update = None
        
        try:
            # 缩放图像以适应显示
            from PIL import Image
            display_img = screenshot_image.resize((500, 300), Image.Resampling.LANCZOS)
            
            # 转换为QPixmap显示
            import io
            buffer = io.BytesIO()
            display_img.save(buffer, format='PNG')
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            
            self.screenshot_label.setPixmap(pixmap)
            self.screenshot_info.setText(f"截图尺寸: {screenshot_image.size}, Base64长度: {len(base64_data)}")
            
            # 清理临时对象
            del display_img
            buffer.close()
            
            self.status_label.setText("截图已更新")
            
        except Exception as e:
            self.screenshot_label.setText(f"显示截图失败: {str(e)}")
            self.status_label.setText("截图显示错误")
    
    def manual_capture_screenshot(self):
        """手动触发截图（立即执行）"""
        self.status_label.setText("正在截图...")
        
        # 在线程池中异步执行
        future = self.screenshot_manager.capture_screen_to_base64_async(
            callback=lambda result: self.on_manual_screenshot_ready(result)
        )
    
    def on_manual_screenshot_ready(self, base64_data):
        """手动截图完成回调"""
        if base64_data:
            self.current_screenshot_base64 = base64_data
            # 同时获取图像用于显示
            screenshot_img = self.screenshot_manager.capture_screen()
            if screenshot_img:
                self.current_screenshot_image = screenshot_img
                self.on_screenshot_ready(screenshot_img, base64_data)
    
    def send_task(self):
        """发送任务到服务端"""
        command = self.command_input.toPlainText().strip()
        
        if not command:
            self.result_display.append("❌ 请输入指令")
            return
        
        if not self.current_screenshot_base64:
            self.result_display.append("❌ 请先截图")
            return
        
        # 保存当前任务指令
        self.current_task_command = command
        
        # TaskWorker现在会自己建立连接，无需预先连接
        # 但我们仍然需要有效的服务端地址
        server_url = self.server_url_input.text().strip()
        if not server_url:
            self.result_display.append("❌ 请输入服务端地址")
            return
        
        # 显示发送状态
        self.result_display.append(f"📤 发送任务: {command}")
        self.status_label.setText("发送中...")
        self.send_task_btn.setEnabled(False)
        
        # 创建工作线程处理任务
        self.task_worker = TaskWorker(
            self.server_url_input.text(),
            command, 
            self.current_screenshot_base64
        )
        self.task_worker.task_completed.connect(self.on_task_completed)
        self.task_worker.task_failed.connect(self.on_task_failed)
        self.task_worker.omniparser_result.connect(self.on_omniparser_result)
        self.task_worker.claude_result.connect(self.on_claude_result)
        self.task_worker.start()
        
        # 清空之前的结果显示
        self.omniparser_display.clear()
        self.claude_display.clear()
    
    def on_task_completed(self, result):
        """任务完成回调"""
        try:
            self.result_display.append(f"✅ 最终任务完成:")
            
            # 处理字典格式和对象格式
            if isinstance(result, dict):
                task_id = result.get('task_id', '未知')
                data = result.get('data', {})
                success = data.get('success', False)
                reasoning = data.get('reasoning', '')
                annotated_screenshot = data.get('annotated_screenshot_base64')
                ui_elements = data.get('ui_elements', [])
                actions = data.get('actions', [])
                error_message = data.get('error_message')
            else:
                # 对象格式（保持兼容性）
                task_id = result.task_id
                success = result.success
                reasoning = result.reasoning
                annotated_screenshot = getattr(result, 'annotated_screenshot_base64', None)
                ui_elements = getattr(result, 'ui_elements', [])
                actions = getattr(result, 'actions', [])
                error_message = getattr(result, 'error_message', None)
            
            self.result_display.append(f"   任务ID: {task_id}")
            self.result_display.append(f"   成功状态: {success}")
            
            if reasoning:
                self.result_display.append(f"   推理总结: {reasoning[:100]}...")
            
            if actions:
                self.result_display.append(f"   操作计划: {len(actions)}个步骤")
            
            if error_message:
                self.result_display.append(f"   错误信息: {error_message}")
            
            # 显示标注截图（如果还没有显示的话）
            if annotated_screenshot:
                try:
                    self.display_annotated_screenshot(annotated_screenshot)
                    self.result_display.append(f"   📸 标注截图已更新")
                except Exception as e:
                    self.result_display.append(f"   📸 标注截图显示失败: {str(e)}")
            
            # 显示UI元素信息（如果还没有显示的话）
            if ui_elements:
                self.result_display.append(f"   🔍 UI元素总数: {len(ui_elements)}个")
                try:
                    self.update_elements_table(ui_elements)
                except Exception as e:
                    self.result_display.append(f"   ⚠️ UI元素表格更新失败: {str(e)}")
            
            self.result_display.append(f"🏁 任务处理流程完成")
            
        except Exception as e:
            self.result_display.append(f"❌ 处理最终结果时出错: {str(e)}")
            print(f"on_task_completed error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 无论成功还是失败，都要重置UI状态
            self.status_label.setText("任务完成")
            self.send_task_btn.setEnabled(True)
    
    def on_omniparser_result(self, response):
        """处理OmniParser结果"""
        try:
            data = response.get('data', {})
            task_id = response.get('task_id', '未知')
            processing_time = data.get('processing_time', 0)
            element_count = data.get('element_count', 0)
            
            # 更新OmniParser显示区域
            self.omniparser_display.append(f"🔍 <b>OmniParser 屏幕元素检测完成</b>")
            self.omniparser_display.append(f"📊 处理时间: {processing_time:.2f}秒")
            self.omniparser_display.append(f"🎯 检测到 {element_count} 个UI元素")
            
            # 显示检测到的UI元素概览
            ui_elements = data.get('ui_elements', [])
            if ui_elements:
                self.omniparser_display.append(f"\n📋 <b>检测到的UI元素:</b>")
                for i, elem in enumerate(ui_elements[:5]):  # 显示前5个
                    elem_type = elem.get('type', '未知')
                    description = elem.get('description', '无描述')[:30]
                    coordinates = elem.get('coordinates', [])
                    coord_str = f"({coordinates[0]:.0f},{coordinates[1]:.0f})" if len(coordinates) >= 2 else "未知位置"
                    self.omniparser_display.append(f"  {i+1}. {elem_type} {coord_str}: {description}")
                
                if len(ui_elements) > 5:
                    self.omniparser_display.append(f"  ... 还有 {len(ui_elements)-5} 个元素")
            
            # 更新UI元素表格
            if ui_elements:
                self.update_elements_table(ui_elements)
            
            # 显示标注截图
            annotated_screenshot = data.get('annotated_screenshot_base64')
            if annotated_screenshot:
                self.display_annotated_screenshot(annotated_screenshot)
                self.omniparser_display.append(f"\n📸 <b>标注截图已更新</b>")
                self.annotated_info.setText(f"OmniParser: 检测到{element_count}个元素，处理时间{processing_time:.2f}秒")
            
            # 保存UI元素供执行使用
            from shared.schemas.data_models import UIElement
            self.current_ui_elements = []
            for elem_data in ui_elements:
                ui_element = UIElement(
                    id=elem_data.get('id', 0),
                    type=elem_data.get('type', ''),
                    description=elem_data.get('description', ''),
                    coordinates=elem_data.get('coordinates', []),
                    text=elem_data.get('text', ''),
                    confidence=elem_data.get('confidence', 0.0)
                )
                self.current_ui_elements.append(ui_element)
            
            # 更新状态
            self.status_label.setText("OmniParser分析完成，等待Claude分析...")
            
        except Exception as e:
            self.omniparser_display.append(f"❌ 解析OmniParser结果失败: {str(e)}")
    
    def on_claude_result(self, response):
        """处理Claude分析结果"""
        try:
            data = response.get('data', {})
            task_id = response.get('task_id', '未知')
            processing_time = data.get('processing_time', 0)
            confidence = data.get('confidence', 0)
            reasoning = data.get('reasoning', '无推理信息')
            actions = data.get('actions', [])
            
            # 更新Claude显示区域
            self.claude_display.append(f"🧠 <b>Claude 智能分析完成</b>")
            self.claude_display.append(f"⏱️ 处理时间: {processing_time:.2f}秒")
            self.claude_display.append(f"🎯 置信度: {confidence:.2%}")
            
            # 显示推理过程
            self.claude_display.append(f"\n💭 <b>分析推理:</b>")
            # 将长文本分段显示
            reasoning_lines = reasoning.split('\n')
            for line in reasoning_lines:
                if line.strip():
                    # 每60字符换行
                    while len(line) > 60:
                        self.claude_display.append(f"  {line[:60]}")
                        line = line[60:]
                    if line.strip():
                        self.claude_display.append(f"  {line}")
            
            # 显示操作计划
            if actions:
                self.claude_display.append(f"\n🎮 <b>生成的操作计划 ({len(actions)}个步骤):</b>")
                for i, action in enumerate(actions, 1):
                    action_type = action.get('type', '未知')
                    description = action.get('description', '无描述')
                    element_id = action.get('element_id')
                    coordinates = action.get('coordinates')
                    text = action.get('text')
                    duration = action.get('duration')
                    
                    action_str = f"  {i}. <b>{action_type}</b>: {description}"
                    
                    if element_id:
                        action_str += f" [元素ID: {element_id}]"
                    if coordinates:
                        action_str += f" [坐标: {coordinates}]"
                    if text:
                        action_str += f" [文本: '{text}']"
                    if duration:
                        action_str += f" [时长: {duration}秒]"
                    
                    self.claude_display.append(action_str)
            else:
                self.claude_display.append(f"\n⚠️ 未生成操作计划")
            
            # 保存操作计划和UI元素供执行使用
            from shared.schemas.data_models import ActionPlan
            self.current_action_plan = []
            for action_data in actions:
                action = ActionPlan(
                    type=action_data.get('type', ''),
                    description=action_data.get('description', ''),
                    element_id=action_data.get('element_id'),
                    coordinates=action_data.get('coordinates'),
                    text=action_data.get('text'),
                    duration=action_data.get('duration')
                )
                self.current_action_plan.append(action)
            
            # 保存Claude输出用于后续任务完成度验证
            self.current_claude_output = f"推理过程: {reasoning}\n操作计划: {len(actions)}个步骤"
            
            # 自动执行操作计划
            if self.current_action_plan:
                self.claude_display.append(f"\n🚀 <b>操作计划已准备就绪，开始自动执行...</b>")
                self._auto_execute_action_plan()
            else:
                self.claude_display.append(f"\n⚠️ <b>未生成有效的操作计划</b>")
            
            # 更新状态
            self.status_label.setText("Claude分析完成")
            
        except Exception as e:
            self.claude_display.append(f"❌ 解析Claude结果失败: {str(e)}")
    
    def display_annotated_screenshot(self, annotated_base64):
        """显示标注后的截图"""
        try:
            import base64
            import io
            from PIL import Image
            
            # 解码base64图像
            image_data = base64.b64decode(annotated_base64)
            image = Image.open(io.BytesIO(image_data))
            
            # 缩放图像以适应显示区域
            display_img = image.resize((500, 300), Image.Resampling.LANCZOS)
            
            # 转换为QPixmap显示
            buffer = io.BytesIO()
            display_img.save(buffer, format='PNG')
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            
            self.annotated_screenshot_label.setPixmap(pixmap)
            
        except Exception as e:
            self.annotated_screenshot_label.setText(f"显示标注截图失败: {str(e)}")
            print(f"显示标注截图错误: {e}")
    
    def update_elements_table(self, ui_elements):
        """更新UI元素表格"""
        try:
            # 设置表格行数
            self.elements_table.setRowCount(len(ui_elements))
            
            # 统计不同类型的元素
            element_types = {}
            
            # 填充表格数据
            for row, elem in enumerate(ui_elements):
                # 处理字典格式和对象格式
                if isinstance(elem, dict):
                    elem_id = elem.get('id', row)
                    elem_type = elem.get('type', '未知')
                    elem_description = elem.get('description', '无描述')
                    elem_coordinates = elem.get('coordinates', [])
                    elem_text = elem.get('text', '')
                else:
                    # UIElement对象
                    elem_id = elem.id
                    elem_type = elem.type
                    elem_description = elem.description
                    elem_coordinates = elem.coordinates
                    elem_text = elem.text
                
                # ID
                self.elements_table.setItem(row, 0, QTableWidgetItem(str(elem_id)))
                
                # 类型
                self.elements_table.setItem(row, 1, QTableWidgetItem(elem_type))
                element_types[elem_type] = element_types.get(elem_type, 0) + 1
                
                # 描述
                description = elem_description[:100] + "..." if len(elem_description) > 100 else elem_description
                self.elements_table.setItem(row, 2, QTableWidgetItem(description))
                
                # 坐标
                if elem_coordinates and len(elem_coordinates) >= 2:
                    if len(elem_coordinates) == 4:
                        coords_str = f"({elem_coordinates[0]:.0f},{elem_coordinates[1]:.0f}) - ({elem_coordinates[2]:.0f},{elem_coordinates[3]:.0f})"
                    else:
                        coords_str = f"({elem_coordinates[0]:.0f},{elem_coordinates[1]:.0f})"
                else:
                    coords_str = "未知"
                self.elements_table.setItem(row, 3, QTableWidgetItem(coords_str))
                
                # 文本
                text = elem_text[:50] + "..." if len(elem_text) > 50 else elem_text
                self.elements_table.setItem(row, 4, QTableWidgetItem(text))
                
            
            # 更新统计信息
            stats_text = f"UI元素统计: 总计{len(ui_elements)}个元素"
            if element_types:
                type_summary = ", ".join([f"{t}({c}个)" for t, c in element_types.items()])
                stats_text += f" | 类型分布: {type_summary}"
            
            self.elements_stats.setText(stats_text)
            
        except Exception as e:
            self.elements_stats.setText(f"更新UI元素表格失败: {str(e)}")
            print(f"更新UI元素表格错误: {e}")
    
    def on_task_failed(self, error_msg):
        """任务失败回调"""
        self.result_display.append(f"❌ 任务失败: {error_msg}")
        self.status_label.setText("任务失败")
        self.send_task_btn.setEnabled(True)
    
    
    def _connect_execution_signals(self):
        """连接执行管理器信号"""
        self.execution_manager.execution_started.connect(self._on_execution_started)
        self.execution_manager.execution_completed.connect(self._on_execution_completed)
        self.execution_manager.execution_stopped.connect(self._on_execution_stopped)
        self.execution_manager.action_started.connect(self._on_action_started)
        self.execution_manager.action_completed.connect(self._on_action_completed)
        self.execution_manager.confirmation_requested.connect(self._on_confirmation_requested)
        self.execution_manager.error_occurred.connect(self._on_execution_error)
        self.execution_manager.status_changed.connect(self._on_execution_status_changed)
        self.execution_manager.task_completion_check_requested.connect(self._on_task_completion_check_requested)
    
    def _auto_execute_action_plan(self):
        """自动执行操作计划（无用户干预）"""
        if not self.current_action_plan:
            self.result_display.append("❌ 没有可执行的操作计划")
            return
        
        if self.execution_manager.is_executing():
            self.result_display.append("❌ 已有任务在执行中")
            return
        
        # 使用全自动模式，不需要用户确认
        config = ExecutionConfig(
            mode=ExecutionMode.FULL_AUTO,
            confirm_dangerous_actions=False,  # 关闭危险操作确认
            screenshot_enabled=False,         # 关闭截图功能
            strict_mode=False,
            auto_retry=True
        )
        self.execution_manager.update_config(config)
        
        # 开始执行
        success = self.execution_manager.execute_action_plan(
            self.current_action_plan,
            self.current_ui_elements,
            f"auto_task_{int(time.time())}",
            self.current_task_command,
            self.current_claude_output
        )
        
        if not success:
            self.result_display.append("❌ 自动执行启动失败")
    
    def _on_task_completion_check_requested(self, task_id, original_command, previous_claude_output):
        """任务完成度验证请求处理"""
        try:
            # 使用任务完成度检查器进行验证
            from client.automation.task_completion_checker import TaskCompletionChecker
            checker = TaskCompletionChecker()
            
            # 检查任务完成度
            check_result = checker.check_task_completion(
                task_id, 
                original_command, 
                previous_claude_output
            )
            
            if check_result.screenshot_base64 and check_result.verification_prompt:
                # 启动任务完成度验证工作线程
                self.verification_worker = TaskCompletionVerificationWorker(
                    self.server_url_input.text(),
                    task_id,
                    original_command,
                    previous_claude_output,
                    check_result.screenshot_base64,
                    check_result.verification_prompt
                )
                
                self.verification_worker.verification_completed.connect(self._on_verification_completed)
                self.verification_worker.verification_failed.connect(self._on_verification_failed)
                self.verification_worker.start()
                
                self.claude_display.append(f"\n🔍 <b>正在验证任务完成度...</b>")
                self.status_label.setText("验证任务完成度...")
            else:
                self.claude_display.append(f"\n❌ <b>任务完成度验证失败：无法获取截图数据</b>")
        
        except Exception as e:
            self.claude_display.append(f"\n❌ <b>启动任务完成度验证失败: {str(e)}</b>")
    
    def _on_verification_completed(self, response):
        """任务完成度验证完成处理"""
        try:
            data = response.get('data', {})
            status = data.get('status', 'unclear')
            reasoning = data.get('reasoning', '')
            confidence = data.get('confidence', 0.0)
            
            self.claude_display.append(f"\n✅ <b>任务完成度验证结果: {status}</b>")
            self.claude_display.append(f"🎯 置信度: {confidence:.2%}")
            self.claude_display.append(f"💭 判断理由: {reasoning}")
            
            if status == "completed":
                self.claude_display.append(f"\n🎉 <b>任务已完成！</b>")
                self.status_label.setText("任务完成")
            elif status == "incomplete":
                next_steps = data.get('next_steps')
                next_actions = data.get('next_actions')
                
                if next_steps:
                    self.claude_display.append(f"\n🔄 <b>任务未完成，建议下一步:</b> {next_steps}")
                
                if next_actions and len(next_actions) > 0:
                    self.claude_display.append(f"\n⚡ <b>下一步操作指令:</b>")
                    for i, action in enumerate(next_actions, 1):
                        action_type = action.get('type', 'unknown')
                        action_desc = action.get('description', '无描述')
                        element_id = action.get('element_id')
                        coordinates = action.get('coordinates')
                        action_text = action.get('text', '')
                        
                        action_line = f"  {i}. <b>{action_type.upper()}</b>: {action_desc}"
                        
                        # 添加元素ID和坐标显示
                        if element_id:
                            action_line += f" [元素ID: {element_id}]"
                        if coordinates:
                            action_line += f" [坐标: {coordinates}]"
                        if action_text:
                            action_line += f" ('{action_text}')"
                        
                        self.claude_display.append(action_line)
                    
                    # 继续执行新的操作指令
                    self._continue_task_execution_with_actions(next_actions)
                elif next_steps:
                    # 如果只有文字建议，使用旧的继续执行逻辑
                    self._continue_task_execution(next_steps)
                else:
                    self.claude_display.append(f"\n🔄 <b>任务未完成，但未提供下一步建议</b>")
                    self.status_label.setText("任务未完成")
            elif status == "failed":
                self.claude_display.append(f"\n❌ <b>任务执行失败</b>")
                self.status_label.setText("任务失败")
            else:
                self.claude_display.append(f"\n❓ <b>无法确定任务状态</b>")
                self.status_label.setText("状态不明")
        
        except Exception as e:
            self.claude_display.append(f"\n❌ <b>处理验证结果失败: {str(e)}</b>")
    
    def _on_verification_failed(self, error_msg):
        """任务完成度验证失败处理"""
        self.claude_display.append(f"\n❌ <b>任务完成度验证失败: {error_msg}</b>")
        self.status_label.setText("验证失败")
    
    def _continue_task_execution(self, next_steps_description):
        """继续执行任务"""
        try:
            # 将下一步建议作为新的任务指令
            self.command_input.setPlainText(next_steps_description)
            self.claude_display.append(f"\n🔄 <b>准备继续执行任务...</b>")
            
            # 等待2秒后自动重新开始分析
            QTimer.singleShot(2000, self.send_task)
            
        except Exception as e:
            self.claude_display.append(f"\n❌ <b>继续执行任务失败: {str(e)}</b>")
    
    def _continue_task_execution_with_actions(self, next_actions):
        """使用具体的操作指令继续执行任务"""
        try:
            from shared.schemas.data_models import ActionPlan
            
            # 转换字典格式的操作为ActionPlan对象
            action_plans = []
            for action_data in next_actions:
                action = ActionPlan(
                    type=action_data.get('type', ''),
                    description=action_data.get('description', ''),
                    element_id=action_data.get('element_id'),
                    coordinates=action_data.get('coordinates'),
                    text=action_data.get('text'),
                    duration=action_data.get('duration'),
                    keys=action_data.get('keys')
                )
                action_plans.append(action)
            
            self.claude_display.append(f"\n🔄 <b>开始执行{len(action_plans)}个后续操作...</b>")
            
            # 直接执行操作指令，不需要重新分析
            original_command = self.command_input.toPlainText()
            self.execution_manager.execute_action_plan(
                action_plans, 
                [], # UI元素列表（可以为空，因为操作指令已经包含必要信息）
                f"continuation_{int(time.time())}", 
                original_command,
                "继续执行验证后的操作指令"
            )
            
        except Exception as e:
            self.claude_display.append(f"\n❌ <b>继续执行操作指令失败: {str(e)}</b>")
            import traceback
            print(f"Error in _continue_task_execution_with_actions: {traceback.format_exc()}")
    
    
    def _on_execution_started(self, task_id):
        """执行开始处理"""
        self.execution_status.setText(f"执行状态: 正在执行 ({task_id})")
        self.result_display.append(f"🚀 开始自动执行任务: {task_id}")
    
    def _on_execution_completed(self, result):
        """执行完成处理"""
        self.execution_status.setText(f"执行状态: 完成")
        
        # 显示执行结果
        success_rate = result.success_rate * 100
        self.result_display.append(
            f"✅ 自动执行完成!\n"
            f"   成功率: {success_rate:.1f}% ({result.completed_actions}/{result.total_actions})\n"
            f"   执行时间: {result.total_execution_time:.2f}秒\n"
            f"   状态: {result.status.value}"
        )
        
        if result.final_error:
            self.result_display.append(f"❌ 错误: {result.final_error}")
    
    def _on_execution_stopped(self):
        """执行停止处理"""
        self.execution_status.setText("执行状态: 已停止")
        self.result_display.append("⏹️ 执行已停止")
    
    def _on_action_started(self, action_index, description):
        """操作开始处理"""
        self.result_display.append(f"🔄 步骤 {action_index + 1}: {description}")
    
    def _on_action_completed(self, action_index, result):
        """操作完成处理"""
        if result.status.value == "success":
            icon = "✅"
        else:
            icon = "❌"
        
        self.result_display.append(
            f"{icon} 步骤 {action_index + 1} 完成 - {result.description} "
            f"(耗时: {result.execution_time:.2f}s)"
        )
        
        if result.error_message:
            self.result_display.append(f"   错误: {result.error_message}")
    
    def _on_confirmation_requested(self, action_index, action_type, description, callback):
        """用户确认请求处理（自动模式下直接通过）"""
        # 在全自动模式下，直接确认所有操作
        callback(True)
        self.result_display.append(f"✅ 自动确认操作 {action_index + 1}: {description}")
    
    def _on_execution_error(self, error_message):
        """执行错误处理"""
        self.execution_status.setText("执行状态: 错误")
        self.result_display.append(f"❌ 执行错误: {error_message}")
    
    def _on_execution_status_changed(self, status):
        """执行状态变化处理"""
        # 可以在这里更新更详细的状态信息
        pass
    
    def closeEvent(self, event):
        """窗口关闭事件 - 清理资源"""
        try:
            # 停止工作线程
            if hasattr(self, 'screenshot_worker'):
                self.screenshot_worker.stop()
                self.screenshot_worker.wait(5000)  # 等待5秒
            
            
            # 关闭截图管理器
            if hasattr(self, 'screenshot_manager'):
                self.screenshot_manager.shutdown()
            
            # 断开服务端连接
            if self.server_client and self.server_client.connected:
                self.server_client.disconnect_sync()
            
            # 停止执行管理器
            if hasattr(self, 'execution_manager') and self.execution_manager.is_executing():
                self.execution_manager.stop_execution()
            
            # 关闭所有ServerClient连接
            ServerClient.shutdown_all()
                
        except Exception as e:
            print(f"清理资源时出错: {e}")
        
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    # 使用标准的Qt事件循环
    sys.exit(app.exec())

if __name__ == "__main__":
    main()