# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Computer Use Agent is an AI-powered computer automation system that supports voice commands and screen operations. The system uses a client-server architecture where the client (PyQt6 GUI) runs on macOS/Windows and the server (FastAPI + AI models) runs on Linux.

## Development Commands

### Starting the Application
```bash
# Start server (Linux)
python start_server.py
# or directly:
python server/main.py

# Start client (Mac/Windows)  
python start_client.py
# or directly:
python client/main.py
```

### Dependencies Management
```bash
# Install all dependencies
pip install -r requirements.txt

# Key dependency groups:
# - Client: PyQt6, pillow, pyautogui, websockets
# - Server: fastapi, uvicorn, torch, transformers, omniparser models
# - Shared: pydantic, aiofiles, python-dotenv
```

### Server Endpoints
- WebSocket: `ws://server:8000/ws` (main communication)
- Health check: `http://server:8000/health`
- API docs: `http://server:8000/docs`

## Architecture Overview

### Client-Server Communication
- **Protocol**: WebSocket for real-time bidirectional communication
- **Data Models**: Defined in `shared/schemas/data_models.py` using Pydantic
- **Message Types**: `analyze_task`, `analysis_result`, `error`

### Key Components

#### Client Side (`client/`)
- **Main Window** (`ui/main_window.py`): PyQt6 GUI with task history, settings, and UI element display
  - Enhanced operation display with element IDs
  - Operating system detection and transmission
  - Real-time staged result display
- **Screenshot Manager** (`screenshot/screenshot_manager.py`): Handles screen capture with optimization and caching
- **Server Client** (`communication/server_client.py`): WebSocket client with shared event loop and connection management
- **Data Flow**: UI → Screenshot + OS Info → WebSocket → Server

#### Server Side (`server/`)
- **FastAPI Server** (`main.py`, `api/main.py`): WebSocket endpoints and REST API
  - Staged response system for real-time feedback
  - Enhanced error handling and timeout management
- **OmniParser Service** (`omniparser/omniparser_service.py`): Screen element detection using Florence-2 models
- **Claude Service** (`claude/claude_service.py`): AI-powered task analysis and operation generation
  - Robust retry mechanisms with exponential backoff
  - JSON response cleaning and validation
  - Operating system context integration
  - Element-based operation planning
- **Model Weights**: Located in `server/weights/` with Florence-2 models for UI element detection and captioning

### Data Models (`shared/schemas/data_models.py`)
- `TaskAnalysisRequest`: Client request with text command, screenshot, and OS info
- `TaskAnalysisResponse`: Server response with parsed UI elements and action plans
- `UIElement`: Represents detected screen elements with coordinates and metadata
- `ActionPlan`: Individual actions for task execution with element references
- `OSInfo`: Operating system information for context-aware analysis
- `OmniParserResult`: Intermediate results from UI element detection
- `ClaudeAnalysisResult`: AI-generated operation plans and reasoning

## Key Technical Details

### OmniParser Integration
- **Models Used**: Florence-2-base-ft for captioning, custom icon detection model
- **Config Paths**: Hardcoded to `/root/autodl-tmp/computer-use-agent/server/weights/`
- **Fallback**: `SimpleOmniParser` used when full models not available
- **Output**: Annotated screenshots + structured UI element data

### WebSocket Communication
- **Connection Management**: WebSocketManager with automatic retry and exponential backoff
- **Optimized Timeouts**: 60s ping interval, 30s ping timeout, 7-minute receive timeout for Claude
- **Long Operation Support**: Designed to handle Claude's extended processing times (up to 5+ minutes)
- **Error Handling**: Comprehensive timeout detection, connection retry, graceful disconnection
- **Performance**: Compression disabled to reduce CPU load during long operations

### Screenshot Management
- **Format**: PIL Images → base64 encoding for transmission
- **Optimization**: Compression and caching mechanisms
- **Threading**: Background capture with thread-safe operations

## Development Guidelines

### Code Change Management
**IMPORTANT**: Every time you modify code, you MUST commit changes to git and push to the repository:

```bash
# After making any code changes
git add .
git commit -m "Brief description of changes"
git push
```

This ensures all changes are tracked and the repository stays up to date.

### Working with Models
- Model weights are expected in `server/weights/` directory
- OmniParser requires both detection and captioning models
- Check `omniparser_service.py` for model loading logic
- Fallback mechanisms exist for missing models

### Client-Server Development
- Always use Pydantic models from `shared/schemas/data_models.py`
- WebSocket messages must include `type`, `task_id`, `timestamp`, `data` fields
- Test connections using health check endpoint before WebSocket operations

### Adding New Features
- Follow the existing client/server/shared directory structure
- Update data models in `shared/schemas/` for new message types
- Add error handling and timeout logic for network operations
- Use the existing screenshot and communication patterns

### Configuration
- Server configuration hardcoded in `omniparser_service.py`
- Client server URL configurable (default: `ws://localhost:8000/ws`)
- No external config files or environment variables currently used

## Current Implementation Status

### Completed (MVP Ready)
- ✅ Complete PyQt6 client interface
- ✅ FastAPI server with WebSocket support  
- ✅ OmniParser integration for UI element detection
- ✅ Real-time screenshot management
- ✅ Cross-platform deployment (Mac client + Linux server)
- ✅ Structured communication protocols

### Recently Completed
- ✅ Claude CLI integration for intelligent task analysis
- ✅ Staged display system (OmniParser → Claude results)
- ✅ Enhanced data models with pyautogui operation support
- ✅ Operating system detection and context-aware AI analysis
- ✅ Robust Claude response parsing with retry mechanisms
- ✅ Element ID display in operation plans

### Pending Implementation  
- [ ] pyautogui automation execution engine  
- [ ] Voice recording and TTS functionality
- [ ] Result verification system
- [ ] Security and permission controls

## Testing and Debugging

### Manual Testing
- Use `python start_server.py` and `python start_client.py`
- Check server health at `http://localhost:8000/health`
- Monitor WebSocket connections in client UI
- Test screenshot capture and UI element detection

### Claude Integration Testing
```bash
# Test Claude integration with existing image
python test_existing_image.py

# Test staged display functionality (OmniParser → Claude results)
python test_staged_display.py

# Test Claude service directly
python test_claude_integration.py

# Create small test images for development
python create_small_test_image.py
```

### Staged Display Architecture
The system now supports **real-time staged display**:

1. **Stage 1 - OmniParser Results**: Client immediately receives and displays UI element detection results and annotated screenshots
2. **Stage 2 - Claude Analysis**: Client receives and displays Claude's reasoning and generated pyautogui operation plans
3. **Stage 3 - Final Results**: Client receives final task completion confirmation

**Message Flow**:
- `omniparser_result` → Updates OmniParser display area with detected elements and annotated screenshots
- `claude_result` → Updates Claude display area with analysis reasoning and action plans  
- `analysis_result` → Final task completion status

**Client UI Layout**:
- **分析结果** tab with split view: OmniParser results (top) + Claude analysis (bottom)
- **UI元素详情** tab with detailed element table
- Real-time status updates during processing

### Claude CLI Integration
- **Command**: `claude -p "prompt_with_image_path"`
- **Timeout**: 5 minutes (300 seconds) with 3 retry attempts
- **Image Storage**: `/root/autodl-tmp/computer-use-agent/server/claude/img/`
- **Response Parsing**: Enhanced JSON parsing with automatic cleaning
- **Retry Mechanism**: Exponential backoff on failures
- **Fallback Mode**: Text-based parsing when JSON parsing fails

#### Claude Service Enhancements
- **Operating System Context**: Prompts include client OS information for platform-specific operations
- **Element-Based Operations**: Claude references UI element IDs instead of coordinates
- **Smart Prompt Engineering**: Prevents JSON formatting issues with quote escaping
- **Response Validation**: Multi-layer validation with automatic retry on invalid responses
- **Cross-Platform Shortcuts**: OS-specific keyboard shortcuts (Windows/macOS/Linux)

### Common Issues
- Model loading failures: Check paths in `server/weights/`
- WebSocket keepalive timeouts: System uses optimized 60s ping intervals for long Claude operations
- PyQt threading: Use proper Qt signal/slot mechanisms for UI updates
- Event loop conflicts: Client uses shared event loop pattern to avoid conflicts
- Large image WebSocket limits: Use smaller images for testing (see `create_small_test_image.py`)
- Claude CLI timeout: Claude operations can take 3-5 minutes, client configured for 7-minute timeout
- Connection failures: WebSocketManager includes automatic retry with exponential backoff

#### Claude Integration Issues
- **JSON Parsing Errors**: System automatically cleans responses and retries parsing
- **Empty Responses**: Retry mechanism with validation handles Claude timeouts
- **Quote Escaping**: Smart prompt engineering prevents JSON format corruption
- **OSInfo Access**: Proper Pydantic model handling for operating system data
- **Element ID Missing**: Enhanced UI display shows element IDs for all click operations

### WebSocket Configuration
```python
# Optimized settings in client/websocket_config.py
WEBSOCKET_CONFIG = {
    'ping_interval': 60,    # 60s ping interval
    'ping_timeout': 30,     # 30s ping timeout  
    'close_timeout': 30,    # 30s close timeout
    'compression': None     # Disabled for performance
}
RECEIVE_TIMEOUT = 420.0     # 7-minute receive timeout
```