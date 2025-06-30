#!/usr/bin/env python3
"""
启动客户端的便捷脚本
"""

import subprocess
import sys
import os

def main():
    print("🚀 启动Computer Use Agent客户端...")
    
    # 切换到项目目录
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    try:
        # 启动客户端
        subprocess.run([
            sys.executable, "client/main.py"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 客户端已关闭")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()