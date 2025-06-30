# Computer Use Agent

基于AI的计算机自动化操作系统，支持语音指令和屏幕操作。

> **🎉 MVP版本已完成！** 完整的客户端-服务端架构，支持跨平台部署。

## 🚀 快速开始

### 🖥️ 服务端部署（Linux）

```bash
# 克隆仓库
git clone git@github.com:ChainRex/computer-use-agent.git
cd computer-use-agent

# 安装依赖
pip install fastapi uvicorn websockets pydantic

# 启动服务端
python start_server.py
```

服务端地址: `ws://your-server-ip:8000/ws`

### 🍎 客户端部署（Mac）

```bash
# 克隆仓库
git clone git@github.com:ChainRex/computer-use-agent.git
cd computer-use-agent

# 安装依赖
pip install PyQt6 pillow pyautogui websockets qasync pydantic

# 启动客户端
python start_client.py
```

## 📱 使用说明

1. **启动服务端**（Linux云服务器）
2. **启动客户端**（Mac本地）
3. 在客户端中修改服务端地址为你的服务器IP
4. 点击"连接服务端"
5. 输入指令并发送任务

### 🎯 支持的指令

- `"帮我打开计算器"` → 生成打开计算器的操作步骤
- `"计算1+2等于几"` → 生成完整的计算序列
- `"打开记事本"` → 生成打开记事本的快捷键序列

## 🏗️ 项目架构

```
┌─────────────────────────────────┐    WebSocket    ┌─────────────────┐
│         Mac客户端               │ ←─────────────→ │   Linux服务端   │
│                                 │                  │                 │
│ • PyQt6界面                     │                  │ • FastAPI       │
│ • 屏幕截图                      │                  │ • 任务分析      │
│ • 指令输入                      │                  │ • 动作规划      │
│ • 执行引擎（待开发）            │                  │ • AI推理        │
└─────────────────────────────────┘                  └─────────────────┘
```

## 📋 开发状态

### ✅ 已完成
- [x] PyQt6客户端界面（文本输入、截图预览、状态显示）
- [x] FastAPI服务端（WebSocket API、任务分析）
- [x] 实时通信协议（标准化消息格式）
- [x] 基础指令识别（计算器、记事本、数学计算）
- [x] 跨平台部署（Mac客户端 + Linux服务端）

### 🚧 开发中
- [ ] **OmniParser集成** - 真实的屏幕元素识别
- [ ] **Claude API集成** - 智能任务分析
- [ ] **PyAutoGUI执行引擎** - 实际的屏幕操作
- [ ] **语音处理** - Whisper + TTS

### 📅 计划中
- [ ] 语音录制和播放
- [ ] 结果验证机制
- [ ] 更多应用支持（浏览器、文件管理器）
- [ ] 安全权限控制

## 🔧 开发环境

### 服务端要求
- Python 3.8+
- FastAPI, Uvicorn
- Linux系统（推荐Ubuntu）

### 客户端要求  
- Python 3.8+
- PyQt6, Pillow, PyAutoGUI
- macOS或Windows（图形界面）

## 📖 API文档

启动服务端后访问：
- **API文档**: `http://your-server:8000/docs`
- **健康检查**: `http://your-server:8000/health`
- **WebSocket**: `ws://your-server:8000/ws`

## 🤝 贡献

这是一个快速迭代的MVP项目，欢迎贡献：

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

## 📄 许可证

MIT License

---

**🌟 Star this repo if you find it useful!**