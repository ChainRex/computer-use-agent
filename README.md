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

## 📋 项目任务清单 (TODO List)

### 📊 当前进度状态

```
总体进度: ██████████████░░░░░░ 70% 

模块进度:
├── OmniParser集成    ████████████████████ 100% ✅
├── 项目架构设计      ████████████████████ 100% ✅
├── 客户端开发        █████████████████░░░  85% ✅ (UI完成，缺少音频+自动化执行)
├── 服务端开发        ████████████████░░░░  80% ✅ (API完成，缺少Claude集成)
├── AI模型集成        ████████████░░░░░░░░  60% 🔄 (OmniParser完成，Claude待集成)
├── 通信协议          ████████████████████ 100% ✅
├── 安全机制          ░░░░░░░░░░░░░░░░░░░░   0%
└── 测试和部署        ████░░░░░░░░░░░░░░░░  20% (MVP测试完成)
```

### 🔴 高优先级任务 (必须完成)

#### 核心基础架构
- [x] **项目结构搭建** ✅
  - [x] 创建标准化的项目目录结构
  - [x] 配置基础的依赖管理文件 (requirements.txt)
  - [x] 建立共享协议和数据模型 (shared/schemas/data_models.py)
  - [ ] 完善共享工具和协议 (shared/protocols/, shared/utils/)

#### 客户端开发 (client/)
- [x] **PyQt主界面开发** ✅
  - [x] 实现MainWindow完整界面布局
  - [x] 添加实时状态显示组件 (录音中、处理中、执行中)
  - [x] 实现任务历史记录和结果显示
  - [x] 设计设置面板 (服务器地址配置)
  - [x] UI元素详情表格和标注截图显示
  - [ ] 创建语音录制按钮 (按住说话/点击切换)

- [ ] **音频处理模块**
  - [ ] 实现VoiceRecorder类 (pyaudio录音)
  - [ ] 添加VAD语音活动检测
  - [ ] 实现AudioPlayer类 (TTS播放)
  - [ ] 音频格式标准化 (16kHz, 16bit, mono WAV)

- [x] **屏幕截图管理器** ✅
  - [x] 实现ScreenshotManager类
  - [x] 支持连续截图和单次截图
  - [x] 图像压缩和base64编码
  - [x] 性能优化和缓存机制
  - [x] 多线程处理和防抖机制

- [ ] **自动化执行引擎**
  - [ ] 实现ClientActionExecutor核心类
  - [ ] 支持基础动作: click, type, key, drag, wait
  - [ ] 添加执行前后截图对比
  - [ ] 实现动作执行安全检查
  - [ ] 错误处理和执行回滚机制

- [x] **通信层开发** ✅
  - [x] 实现WebSocket客户端 (ServerClient)
  - [x] 定义任务分析请求/响应协议
  - [x] 连接重试和错误处理
  - [x] 同步和异步通信方法
  - [ ] 实现结果验证通信接口

#### 服务端开发 (server/)
- [x] **FastAPI基础服务** ✅
  - [x] 建立FastAPI应用结构
  - [x] 实现WebSocket路由和处理器
  - [x] 添加REST API接口 (/health)
  - [x] 连接管理和错误处理
  - [x] OmniParser服务集成

- [ ] **Claude API集成**
  - [ ] 实现ClaudeService类
  - [ ] 完善任务分析prompt工程
  - [ ] 实现执行计划生成逻辑
  - [ ] 添加结果验证AI分析

### 🟡 中优先级任务 (重要功能)

#### AI模型服务
- [ ] **语音识别服务**
  - [ ] 集成Whisper STT模型
  - [ ] 支持多种音频格式输入
  - [ ] 优化推理速度和准确率

- [ ] **TTS语音合成**
  - [ ] 集成pyttsx3或Azure Speech
  - [ ] 实现多语言语音输出
  - [ ] 音频质量优化

- [ ] **结果验证系统**
  - [ ] 实现LocalResultVerifier本地验证
  - [ ] 开发AIVerificationService AI验证
  - [ ] 屏幕变化对比算法
  - [ ] 验证结果评分机制

#### 安全和权限控制
- [ ] **安全管理器**
  - [ ] 实现SecurityManager类
  - [ ] 定义允许操作的应用程序白名单
  - [ ] 设置屏幕限制区域检查
  - [ ] 危险操作拦截机制

### 🟢 低优先级任务 (优化和扩展)

#### 测试和质量保证
- [ ] **测试框架建立**
  - [ ] 编写单元测试用例
  - [ ] 实现集成测试场景
  - [ ] 端到端测试自动化
  - [ ] 性能基准测试

#### 部署和运维
- [ ] **容器化部署**
  - [ ] 编写Dockerfile配置
  - [ ] 配置docker-compose.yml
  - [ ] 设置日志和监控

### 📋 项目里程碑

#### Milestone 1: 基础MVP (4-5周) ✅ **已完成**
**目标**: 实现计算器基础操作演示
- [x] OmniParser集成完成
- [x] 客户端基础界面完成 ✅
- [x] 服务端API基础功能完成 ✅
- [x] 端到端通信和UI解析演示成功 ✅
- [ ] 实际自动化操作执行 (待实现)

#### Milestone 2: 核心功能完善 (6-8周)
**目标**: 完整的任务执行和验证流程
- [ ] 完整的语音交互流程
- [ ] 可靠的执行结果验证
- [ ] 基础安全控制机制
- [ ] 支持3-5种常见应用操作

#### Milestone 3: 产品化优化 (8-10周)
**目标**: 可用性和稳定性提升
- [ ] 完善的错误处理机制
- [ ] 用户体验优化
- [ ] 性能调优完成
- [ ] 完整的测试覆盖

### 🎯 下一步行动建议

**🚀 MVP基础框架已完成！项目进度达到70%**

**立即优先任务**:
1. **集成Claude API** - 替换当前的模拟AI分析，实现真正智能的任务分析
2. **实现pyautogui自动化执行引擎** - 让客户端能够实际执行屏幕操作
3. **添加语音功能** - 集成Whisper和TTS，实现完整的语音交互

**已完成的重要功能**:
- ✅ 完整的PyQt6客户端界面（现代化UI、截图预览、任务历史）
- ✅ FastAPI服务端（WebSocket通信、任务分析API）
- ✅ OmniParser屏幕元素识别（检测UI元素、生成标注图像）
- ✅ 实时截图管理（性能优化、缓存机制）
- ✅ 跨平台部署（Mac客户端 + Linux服务端）

**本周目标**:
- 集成Claude API进行智能任务分析
- 实现客户端自动化操作执行
- 添加语音录制和播放功能

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