import sys
import asyncio
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QTextEdit, QLabel, QLineEdit, 
                            QTextBrowser, QSplitter, QFrame, QTabWidget, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from client.screenshot.screenshot_manager import ScreenshotManager
from client.communication.server_client import ServerClient

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
    """处理异步任务的工作线程"""
    task_completed = pyqtSignal(object)  # 任务完成信号
    task_failed = pyqtSignal(str)        # 任务失败信号
    
    def __init__(self, server_url, text_command, screenshot_base64):
        super().__init__()
        self.server_url = server_url
        self.text_command = text_command
        self.screenshot_base64 = screenshot_base64
    
    def run(self):
        """在子线程中运行异步任务"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 在工作线程中创建新的ServerClient
            server_client = ServerClient(self.server_url)
            
            # 连接并发送任务
            connected = loop.run_until_complete(server_client.connect())
            if not connected:
                self.task_failed.emit("无法连接到服务端")
                return
            
            # 运行异步任务
            result = loop.run_until_complete(
                server_client.send_task_for_analysis(
                    self.text_command, 
                    self.screenshot_base64
                )
            )
            
            # 断开连接
            loop.run_until_complete(server_client.disconnect())
            
            if result:
                self.task_completed.emit(result)
            else:
                self.task_failed.emit("服务端返回空结果")
                
        except Exception as e:
            self.task_failed.emit(f"任务执行失败: {str(e)}")
        finally:
            loop.close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Computer Use Agent - 客户端")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化组件
        self.screenshot_manager = ScreenshotManager()
        self.server_client = None  # 在连接时创建
        self.current_screenshot_base64 = None
        
        # 设置UI
        self.setup_ui()
        
        # 自动截图定时器
        self.screenshot_timer = QTimer()
        self.screenshot_timer.timeout.connect(self.auto_capture_screenshot)
        self.screenshot_timer.start(2000)  # 每2秒自动截图
        
        # 初始截图
        self.capture_screenshot()
    
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
        self.status_label = QLabel("就绪")
        main_layout.addWidget(self.status_label)
    
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
        self.screenshot_btn.clicked.connect(self.capture_screenshot)
        
        self.send_task_btn = QPushButton("发送任务")
        self.send_task_btn.clicked.connect(self.send_task)
        self.send_task_btn.setEnabled(True)  # 现在任务工作线程会自己连接
        
        button_layout.addWidget(self.screenshot_btn)
        button_layout.addWidget(self.send_task_btn)
        layout.addLayout(button_layout)
        
        # 创建标签页面板
        self.tab_widget = QTabWidget()
        
        # 第一个标签页：执行结果
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        result_layout.addWidget(QLabel("执行结果:"))
        self.result_display = QTextBrowser()
        result_layout.addWidget(self.result_display)
        self.tab_widget.addTab(result_tab, "执行结果")
        
        # 第二个标签页：UI元素详情
        elements_tab = QWidget()
        elements_layout = QVBoxLayout(elements_tab)
        elements_layout.addWidget(QLabel("检测到的UI元素:"))
        
        # UI元素表格
        self.elements_table = QTableWidget()
        self.elements_table.setColumnCount(6)
        self.elements_table.setHorizontalHeaderLabels(['ID', '类型', '描述', '坐标', '文本', '置信度'])
        
        # 设置表格列宽
        header = self.elements_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID列
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 类型列
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)            # 描述列
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 坐标列
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 文本列
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # 置信度列
        
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
    
    def capture_screenshot(self):
        """捕获屏幕截图"""
        try:
            # 获取base64截图
            self.current_screenshot_base64 = self.screenshot_manager.capture_screen_to_base64()
            
            if self.current_screenshot_base64:
                # 同时获取PIL图像用于显示
                screenshot_img = self.screenshot_manager.capture_screen()
                if screenshot_img:
                    # 缩放图像以适应显示
                    from PIL import Image
                    display_img = screenshot_img.resize((500, 300), Image.Resampling.LANCZOS)
                    
                    # 转换为QPixmap显示
                    import io
                    
                    buffer = io.BytesIO()
                    display_img.save(buffer, format='PNG')
                    pixmap = QPixmap()
                    pixmap.loadFromData(buffer.getvalue())
                    
                    self.screenshot_label.setPixmap(pixmap)
                    self.screenshot_info.setText(f"截图尺寸: {screenshot_img.size}, Base64长度: {len(self.current_screenshot_base64)}")
                    
                self.status_label.setText("截图已更新")
            else:
                self.screenshot_label.setText("截图失败")
                self.status_label.setText("截图失败")
                
        except Exception as e:
            self.result_display.append(f"❌ 截图错误: {str(e)}")
            self.status_label.setText("截图错误")
    
    def auto_capture_screenshot(self):
        """自动截图（静默）"""
        try:
            self.current_screenshot_base64 = self.screenshot_manager.capture_screen_to_base64()
        except:
            pass  # 静默处理错误
    
    def send_task(self):
        """发送任务到服务端"""
        command = self.command_input.toPlainText().strip()
        
        if not command:
            self.result_display.append("❌ 请输入指令")
            return
        
        if not self.current_screenshot_base64:
            self.result_display.append("❌ 请先截图")
            return
        
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
        self.task_worker.start()
    
    def on_task_completed(self, result):
        """任务完成回调"""
        self.result_display.append(f"✅ 服务端响应:")
        self.result_display.append(f"   任务ID: {result.task_id}")
        self.result_display.append(f"   成功: {result.success}")
        
        if result.reasoning:
            self.result_display.append(f"   分析: {result.reasoning}")
        
        # 显示标注截图
        if hasattr(result, 'annotated_screenshot_base64') and result.annotated_screenshot_base64:
            self.display_annotated_screenshot(result.annotated_screenshot_base64)
            self.result_display.append(f"   📸 已更新OmniParser标注截图")
        
        # 显示UI元素信息
        if hasattr(result, 'ui_elements') and result.ui_elements:
            self.result_display.append(f"   🔍 检测到UI元素: {len(result.ui_elements)}个")
            for elem in result.ui_elements[:5]:  # 只显示前5个元素
                coords = f"({elem.coordinates[0]:.0f},{elem.coordinates[1]:.0f})" if elem.coordinates and len(elem.coordinates) >= 2 else "未知位置"
                self.result_display.append(f"     - {elem.type} {coords}: {elem.description[:40]}...")
            if len(result.ui_elements) > 5:
                self.result_display.append(f"     ... 还有{len(result.ui_elements)-5}个元素，查看'UI元素详情'标签页获取完整列表")
            
            # 更新UI元素表格
            self.update_elements_table(result.ui_elements)
            
            # 更新标注信息
            self.annotated_info.setText(f"OmniParser信息: 检测到{len(result.ui_elements)}个UI元素")
            
            # 自动切换到UI元素详情标签页
            self.tab_widget.setCurrentIndex(1)
        
        if result.actions:
            self.result_display.append(f"   计划动作数: {len(result.actions)}")
            for i, action in enumerate(result.actions):
                self.result_display.append(f"     {i+1}. {action.type}: {action.description}")
        
        if result.expected_outcome:
            self.result_display.append(f"   预期结果: {result.expected_outcome}")
        
        if result.error_message:
            self.result_display.append(f"   错误: {result.error_message}")
        
        self.status_label.setText("任务完成")
        self.send_task_btn.setEnabled(True)
    
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
                # ID
                self.elements_table.setItem(row, 0, QTableWidgetItem(str(elem.id)))
                
                # 类型
                elem_type = elem.type
                self.elements_table.setItem(row, 1, QTableWidgetItem(elem_type))
                element_types[elem_type] = element_types.get(elem_type, 0) + 1
                
                # 描述
                description = elem.description[:100] + "..." if len(elem.description) > 100 else elem.description
                self.elements_table.setItem(row, 2, QTableWidgetItem(description))
                
                # 坐标
                if elem.coordinates and len(elem.coordinates) >= 2:
                    if len(elem.coordinates) == 4:
                        coords_str = f"({elem.coordinates[0]:.0f},{elem.coordinates[1]:.0f}) - ({elem.coordinates[2]:.0f},{elem.coordinates[3]:.0f})"
                    else:
                        coords_str = f"({elem.coordinates[0]:.0f},{elem.coordinates[1]:.0f})"
                else:
                    coords_str = "未知"
                self.elements_table.setItem(row, 3, QTableWidgetItem(coords_str))
                
                # 文本
                text = elem.text[:50] + "..." if len(elem.text) > 50 else elem.text
                self.elements_table.setItem(row, 4, QTableWidgetItem(text))
                
                # 置信度
                confidence_str = f"{elem.confidence:.2f}" if elem.confidence is not None and elem.confidence >= 0 else "N/A"
                self.elements_table.setItem(row, 5, QTableWidgetItem(confidence_str))
            
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

def main():
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    # 使用标准的Qt事件循环
    sys.exit(app.exec())

if __name__ == "__main__":
    main()