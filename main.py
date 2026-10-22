import os
import sys

# 确保项目根目录在 sys.path 中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def check_and_install_dependencies():
    """检查必要的依赖包，如果缺少则尝试自动安装"""
    required_packages = ["torch", "demucs", "customtkinter"]
    missing_packages = []
    
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing_packages.append(pkg)
            
    if missing_packages:
        print(f"[*] 检测到缺少必要运行组件: {', '.join(missing_packages)}")
        print("[*] 正在为您自动下载并安装，请稍候（可能需要几分钟）...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])
            print("[+] 组件安装完成！")
        except Exception as e:
            print(f"[-] 自动安装组件失败: {e}")
            print("建议在命令行手动执行: pip install -r requirements.txt")

def main():
    check_and_install_dependencies()
    
    # 导入并启动桌面UI
    from gui.app import KaraokeApp
    app = KaraokeApp()
    app.run()

if __name__ == "__main__":
    main()
