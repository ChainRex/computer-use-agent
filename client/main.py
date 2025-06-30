#!/usr/bin/env python3
"""
Computer Use Agent - 客户端入口
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from client.ui.main_window import main

if __name__ == "__main__":
    main()