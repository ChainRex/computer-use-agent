#!/usr/bin/env python3
"""
启动服务端的便捷脚本
"""

import subprocess
import sys
import os

def main():
    print("🚀 启动Computer Use Agent服务端...")
    
    # 切换到项目目录
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    try:
        # 启动服务端
        subprocess.run([
            sys.executable, "server/main.py"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 服务端已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()