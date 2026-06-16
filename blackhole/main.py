#!/usr/bin/env python3
"""Blackhole - AI 黑洞文件夹 启动入口"""
import sys
import os
import subprocess

# 确保项目根目录在 path 中
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def check_dependencies():
    """检查依赖是否安装"""
    try:
        import fastapi
        import uvicorn
        import httpx
        import watchdog
        return True
    except ImportError:
        return False


def install_dependencies():
    """自动安装依赖"""
    print("正在安装依赖...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "-r",
        os.path.join(ROOT, "requirements.txt"), "-q"
    ])


def main():
    if not check_dependencies():
        print("首次运行，正在安装依赖...")
        install_dependencies()

    from backend.app import start_app

    port = 8765
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"用法: python main.py [端口号]")
            sys.exit(1)

    print(f"""
╔══════════════════════════════════════════╗
║                                          ║
║   Blackhole - AI 黑洞文件夹              ║
║   http://localhost:{port}                  ║
║                                          ║
║   把文件扔进来，AI 帮你搞定剩下的        ║
║                                          ║
╚══════════════════════════════════════════╝
    """)
    start_app(open_browser=True, port=port)


if __name__ == "__main__":
    main()
