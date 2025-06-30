# Computer Use Agent

基于AI的计算机自动化操作系统，支持语音指令和屏幕操作。

## 项目结构

```
computer-use-agent/
├── client/                 # 客户端代码
│   ├── ui/                # PyQt界面
│   ├── screenshot/        # 屏幕截图
│   ├── communication/     # 服务端通信
│   └── main.py           # 客户端入口
├── server/                # 服务端代码
│   ├── api/              # FastAPI接口
│   └── main.py          # 服务端入口
├── shared/               # 共享代码
│   └── schemas/         # 数据模型
└── requirements.txt     # 依赖列表
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务端

```bash
python start_server.py
```

服务端将在 `http://localhost:8000` 启动

### 3. 启动客户端

```bash
python start_client.py
```

## 使用说明

1. 启动服务端和客户端
2. 在客户端界面点击"连接服务端"
3. 在指令输入框输入指令，例如：
   - "帮我打开计算器"
   - "计算1+2等于几"
   - "打开记事本"
4. 点击"发送任务"，查看AI分析结果

## 当前功能

✅ **已实现**：
- PyQt客户端界面
- 屏幕截图功能
- WebSocket通信
- 基础指令识别（计算器、记事本）
- 模拟AI任务分析

🚧 **开发中**：
- 语音识别和合成
- OmniParser屏幕元素识别
- Claude API集成
- 自动化执行引擎

## 测试指令

试试这些指令：
- "帮我打开计算器"
- "计算1+2等于几"
- "打开记事本"

## 开发说明

这是MVP版本，当前使用模拟的AI分析。后续将集成：
- OpenAI Whisper (语音识别)
- OmniParser (屏幕解析)
- Claude API (智能分析)
- PyAutoGUI (自动化执行)