import os
import sys
import re
import time
import shutil
import subprocess
import tempfile
from pathlib import Path
from core.utils import ensure_ffmpeg, get_hardware_info

class KaraokeSeparator:
    def __init__(self, ffmpeg_path=None):
        self.ffmpeg_path = ffmpeg_path or ensure_ffmpeg()
        self.hardware_info = get_hardware_info()
        self._is_cancelled = False
        self._process = None

    def cancel(self):
        """取消当前分离任务"""
        self._is_cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def _has_video(self, file_path):
        """检测输入文件是否包含视频画面流"""
        try:
            cmd = [self.ffmpeg_path, "-i", str(file_path)]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = p.communicate()
            return "Video:" in stderr.decode('utf-8', errors='ignore')
        except Exception:
            return False

    def process_video(
        self,
        video_path: str,
        output_dir: str,
        export_video: bool = True,
        export_audio_mp3: bool = True,
        export_audio_wav: bool = False,
        export_vocals: bool = False,
        device_choice: str = "auto",  # 'auto', 'cuda', 'cpu'
        progress_callback=None
    ):
        """
        处理音视频：提取音频 -> AI人声与伴奏分离 -> 导出【左原装声音 + 右背景音乐】双声道音视频
        """
        self._is_cancelled = False
        video_p = Path(video_path).resolve()
        if not video_p.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        out_p = Path(output_dir).resolve()
        out_p.mkdir(parents=True, exist_ok=True)

        track_stem = video_p.stem
        # 检查是否包含视频画面
        has_video_track = self._has_video(video_p)
        if not has_video_track and not export_audio_mp3:
            export_audio_mp3 = True  # 纯音频输入时自动确保导出音频

        # 创建工作临时目录
        with tempfile.TemporaryDirectory(prefix="karaoke_sep_") as temp_dir:
            temp_path = Path(temp_dir)
            temp_wav = temp_path / f"{track_stem}_extracted.wav"

            # 1. 提取原音频（高品质原装声音）
            if progress_callback:
                progress_callback(0.05, "第 1/4 步: 正在从原文件中提取高品质原装音频...")

            self._run_cmd([
                self.ffmpeg_path, "-y",
                "-i", str(video_p),
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                str(temp_wav)
            ])

            if self._is_cancelled:
                raise InterruptedError("任务已被用户取消")

            # 2. 调用 AI Demucs 进行分离 (提取背景伴奏音乐)
            if progress_callback:
                progress_callback(0.15, "第 2/4 步: AI 人声分离引擎运行中 (正在提取纯背景伴奏音乐)...")

            # 决定使用设备
            if device_choice == "auto":
                device = "cuda" if self.hardware_info["has_gpu"] else "cpu"
            else:
                device = device_choice

            demucs_out_dir = temp_path / "demucs_out"
            demucs_out_dir.mkdir(exist_ok=True)

            # demucs 命令行
            cmd = [
                sys.executable, "-m", "demucs.separate",
                "-n", "htdemucs",
                "--two-stems=vocals",
                "-d", device,
                "-o", str(demucs_out_dir),
                str(temp_wav)
            ]

            # 监测 Demucs 运行输出与进度
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )

            # 持续读取进度
            percent_pattern = re.compile(r"(\d+)%\|")
            while True:
                if self._is_cancelled:
                    self._process.terminate()
                    raise InterruptedError("任务已被用户取消")
                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break
                if line:
                    match = percent_pattern.search(line)
                    if match and progress_callback:
                        pct = int(match.group(1))
                        mapped_pct = 0.15 + (pct / 100.0) * 0.60
                        progress_callback(mapped_pct, f"第 2/4 步: 背景伴奏音乐AI分离中 ({pct}%)...")

            returncode = self._process.wait()
            self._process = None

            if returncode != 0:
                raise RuntimeError("Demucs AI 背景音乐提取失败，请检查模型下载或硬件兼容性。")

            # 确认分离出的伴奏文件位置
            model_folder = demucs_out_dir / "htdemucs" / f"{track_stem}_extracted"
            no_vocals_wav = model_folder / "no_vocals.wav"

            if not no_vocals_wav.exists():
                raise FileNotFoundError("未能找到分离出的背景音乐文件！")

            created_files = []

            # 3. 导出音频 (KTV双声道 MP3: 左声道为原装声音, 右声道为纯背景音乐)
            if export_audio_mp3:
                if progress_callback:
                    progress_callback(0.80, "第 3/4 步: 正在合成双声道伴唱音频 (左原装声音 右背景音乐)...")
                out_mp3 = out_p / f"{track_stem}_KTV伴唱(左原声右伴奏).mp3"
                cmd_audio = [
                    self.ffmpeg_path, "-y",
                    "-i", str(temp_wav),
                    "-i", str(no_vocals_wav),
                    "-filter_complex",
                    "[0:a]pan=mono|c0=0.5*c0+0.5*c1[orig_mono];[1:a]pan=mono|c0=0.5*c0+0.5*c1[bg_mono];[orig_mono][bg_mono]join=inputs=2:channel_layout=stereo:map=0.0-FL|1.0-FR[aout]",
                    "-map", "[aout]",
                    "-codec:a", "libmp3lame",
                    "-b:a", "320k",
                    str(out_mp3)
                ]
                self._run_cmd(cmd_audio)
                created_files.append(out_mp3)

            # 4. 导出保留原视频画面的 KTV 双声道 MP4 视频 (左声道原装声音, 右声道背景伴奏)
            if export_video and has_video_track:
                if progress_callback:
                    progress_callback(0.90, "第 4/4 步: 正在合成 KTV 双声道 MP4 视频 (左原装声音 右背景音乐)...")

                out_video = out_p / f"{track_stem}_KTV双声道(左原声右伴奏).mp4"
                filter_str = "[1:a]pan=mono|c0=0.5*c0+0.5*c1[orig_mono];[2:a]pan=mono|c0=0.5*c0+0.5*c1[bg_mono];[orig_mono][bg_mono]join=inputs=2:channel_layout=stereo:map=0.0-FL|1.0-FR[aout]"

                # 优先采用 -c:v copy 进行无损秒级合成（原画质 100% 保留）
                cmd_copy = [
                    self.ffmpeg_path, "-y",
                    "-i", str(video_p),
                    "-i", str(temp_wav),
                    "-i", str(no_vocals_wav),
                    "-filter_complex", filter_str,
                    "-map", "0:v:0",
                    "-map", "[aout]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "320k",
                    "-shortest",
                    str(out_video)
                ]
                try:
                    self._run_cmd(cmd_copy)
                except Exception:
                    # 回退兼容模式：重新编码视频流为标准 H.264 MP4
                    cmd_reencode = [
                        self.ffmpeg_path, "-y",
                        "-i", str(video_p),
                        "-i", str(temp_wav),
                        "-i", str(no_vocals_wav),
                        "-filter_complex", filter_str,
                        "-map", "0:v:0",
                        "-map", "[aout]",
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-crf", "18",
                        "-c:a", "aac",
                        "-b:a", "320k",
                        "-shortest",
                        str(out_video)
                    ]
                    self._run_cmd(cmd_reencode)

                created_files.append(out_video)

            if progress_callback:
                progress_callback(1.0, "全部制作完成！")

            return created_files

    def _run_cmd(self, cmd_args):
        """执行后台命令并等待完成"""
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            err_msg = stderr.decode('utf-8', errors='replace')
            raise RuntimeError(f"命令执行失败: {err_msg}")
