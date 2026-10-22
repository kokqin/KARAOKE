# -*- coding: utf-8 -*-
import os
import sys
import shutil
import subprocess
import glob
import re
import json

def find_ffmpeg_executable():
    """
    Search for ffmpeg executable in:
    1. System PATH
    2. WinGet package directory
    3. Program Files or common tools directories
    """
    cmd = shutil.which("ffmpeg")
    if cmd:
        return cmd

    # Check WinGet Gyan.FFmpeg package
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pattern = os.path.join(
            local_app_data,
            "Microsoft", "WinGet", "Packages",
            "*FFmpeg*", "**", "ffmpeg.exe"
        )
        matches = glob.glob(winget_pattern, recursive=True)
        if matches:
            return matches[0]

    # Check standard locations
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\ffmpeg\bin\ffmpeg.exe")
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p

    return "ffmpeg"


def find_ffprobe_executable():
    cmd = shutil.which("ffprobe")
    if cmd:
        return cmd

    ffmpeg_path = find_ffmpeg_executable()
    if os.path.isabs(ffmpeg_path):
        ffprobe_cand = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe")
        if os.path.isfile(ffprobe_cand):
            return ffprobe_cand

    return "ffprobe"


FFMPEG_BIN = find_ffmpeg_executable()
FFPROBE_BIN = find_ffprobe_executable()


def get_video_info(video_path):
    """
    Retrieve video metadata: duration, width, height, fps, has_audio.
    """
    info = {
        "duration": 0.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "has_audio": True,
        "error": None
    }
    
    if not os.path.isfile(video_path):
        info["error"] = "视频文件不存在"
        return info

    ffprobe = find_ffprobe_executable()
    try:
        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_type",
            "-of", "json",
            video_path
        ]
        # Hide command window on Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo, encoding="utf-8", errors="ignore")
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            format_info = data.get("format", {})
            if "duration" in format_info:
                try:
                    info["duration"] = float(format_info["duration"])
                except ValueError:
                    pass

            has_audio = False
            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    info["width"] = s.get("width", info["width"])
                    info["height"] = s.get("height", info["height"])
                    fps_str = s.get("r_frame_rate", "30/1")
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        if float(den) > 0:
                            info["fps"] = round(float(num) / float(den), 2)
                elif s.get("codec_type") == "audio":
                    has_audio = True
            info["has_audio"] = has_audio
    except Exception as e:
        info["error"] = str(e)

    # Fallback to ffmpeg -i if ffprobe failed or returned 0 duration
    if info["duration"] <= 0:
        try:
            ffmpeg = find_ffmpeg_executable()
            cmd = [ffmpeg, "-i", video_path]
            proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, startupinfo=startupinfo, encoding="utf-8", errors="ignore")
            # Parse Duration: 00:03:15.54
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", proc.stderr)
            if match:
                hours = float(match.group(1))
                minutes = float(match.group(2))
                seconds = float(match.group(3))
                info["duration"] = hours * 3600 + minutes * 60 + seconds
        except Exception:
            pass

    return info


def extract_audio(video_path, output_wav_path, sample_rate=16000):
    """
    Extract 16kHz mono audio from video, optimized for Whisper ASR.
    """
    ffmpeg = find_ffmpeg_executable()
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        output_wav_path
    ]
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo, encoding="utf-8", errors="ignore")
    if proc.returncode != 0:
        raise RuntimeError(f"音频提取失败: {proc.stderr}")
    return output_wav_path


def format_ffmpeg_subtitles_filter(ass_path):
    r"""
    Prepare properly escaped subtitles filter path for ffmpeg on Windows.
    Colon ':' must be escaped as '\:', and backslashes converted to forward slashes.
    """
    abs_path = os.path.abspath(ass_path).replace("\\", "/")
    escaped_path = abs_path.replace(":", r"\:")
    return f"subtitles='{escaped_path}'"


def burn_subtitles_to_video(video_path, ass_path, output_video_path, total_duration=None, progress_callback=None, cancel_event=None):
    """
    Burn ASS subtitles into video using ffmpeg libass with progress reporting.
    """
    if total_duration is None or total_duration <= 0:
        info = get_video_info(video_path)
        total_duration = info["duration"] if info["duration"] > 0 else 60.0

    ffmpeg = find_ffmpeg_executable()
    vf_arg = format_ffmpeg_subtitles_filter(ass_path)

    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vf", vf_arg,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "19",
        "-c:a", "aac",
        "-b:a", "192k",
        "-progress", "pipe:1",
        "-nostats",
        output_video_path
    ]

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        startupinfo=startupinfo,
        encoding="utf-8",
        errors="ignore",
        bufsize=1
    )

    try:
        for line in process.stdout:
            if cancel_event and cancel_event.is_set():
                process.terminate()
                raise InterruptedError("导出已被用户取消")

            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    time_us = int(line.split("=")[1])
                    curr_sec = time_us / 1000000.0
                    if total_duration > 0:
                        progress = min(1.0, max(0.0, curr_sec / total_duration))
                        if progress_callback:
                            progress_callback(progress, curr_sec, total_duration)
                except ValueError:
                    pass
            elif line.startswith("progress=end"):
                if progress_callback:
                    progress_callback(1.0, total_duration, total_duration)

        process.wait()
        if process.returncode != 0:
            err_msg = process.stderr.read()
            raise RuntimeError(f"FFmpeg 压制视频失败 (code {process.returncode}): {err_msg}")

        return output_video_path

    except Exception:
        try:
            process.terminate()
        except Exception:
            pass
        raise
