import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

# 获取应用根目录
BASE_DIR = Path(__file__).resolve().parent.parent
BIN_DIR = BASE_DIR / "bin"
BIN_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG_URL = "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"

def get_ffmpeg_path():
    """获取 FFmpeg 可执行文件路径，优先本地 bin 目录，次之系统环境变量"""
    local_ffmpeg = BIN_DIR / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
        
    return None

def get_ffprobe_path():
    """获取 FFprobe 可执行文件路径"""
    local_ffprobe = BIN_DIR / "ffprobe.exe"
    if local_ffprobe.exists():
        return str(local_ffprobe)
    
    sys_ffprobe = shutil.which("ffprobe")
    if sys_ffprobe:
        return sys_ffprobe
        
    return None

def download_ffmpeg(progress_callback=None):
    """
    自动下载并解压免安装版 FFmpeg 到 bin 目录
    """
    zip_path = BIN_DIR / "ffmpeg_temp.zip"
    try:
        if progress_callback:
            progress_callback(0.1, "正在下载必要多媒体组件 FFmpeg...")

        def _reporthook(block_num, block_size, total_size):
            if total_size > 0 and progress_callback:
                percent = min(0.1 + (block_num * block_size / total_size) * 0.7, 0.8)
                progress_callback(percent, f"正在下载 FFmpeg: {int((block_num * block_size) / (1024*1024))}MB / {int(total_size / (1024*1024))}MB")

        # 使用 urllib 下载
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(FFMPEG_URL, headers=headers)
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)

        if progress_callback:
            progress_callback(0.85, "正在解压并安装 FFmpeg 组件...")

        # 解压获取 bin/ffmpeg.exe 和 bin/ffprobe.exe
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                filename = os.path.basename(member)
                if filename in ("ffmpeg.exe", "ffprobe.exe"):
                    source = zip_ref.open(member)
                    target = open(BIN_DIR / filename, "wb")
                    with source, target:
                        shutil.copyfileobj(source, target)

        if zip_path.exists():
            zip_path.unlink()

        if progress_callback:
            progress_callback(1.0, "FFmpeg 组件就绪！")
        return True
    except Exception as e:
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass
        raise RuntimeError(f"自动下载 FFmpeg 失败: {e}\n建议手动将 ffmpeg.exe 复制到 bin 文件夹中。")

def ensure_ffmpeg(progress_callback=None):
    """确保 FFmpeg 存在，若不存在则在 Windows 下触发自动下载，在 Linux 下检查系统依赖"""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        return ffmpeg_path
    
    if os.name == 'nt':
        download_ffmpeg(progress_callback)
        ffmpeg_path = get_ffmpeg_path()
    else:
        raise FileNotFoundError("未在系统中检测到 FFmpeg！在 Linux/Streamlit 环境下请先执行: sudo apt-get update && sudo apt-get install -y ffmpeg")

    if not ffmpeg_path:
        raise FileNotFoundError("未能找到或安装 FFmpeg，请检查网络或手动配置。")
    return ffmpeg_path

def get_hardware_info():
    """获取硬件信息及 GPU 加速支持情况"""
    info = {
        "has_gpu": False,
        "device_name": "CPU (中央处理器)",
        "device_type": "cpu"
    }
    try:
        import torch
        if torch.cuda.is_available():
            info["has_gpu"] = True
            info["device_name"] = f"NVIDIA GPU ({torch.cuda.get_device_name(0)})"
            info["device_type"] = "cuda"
    except Exception:
        pass
    return info
