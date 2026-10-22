import os
import sys
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

from core.utils import BASE_DIR, get_hardware_info, ensure_ffmpeg, get_ffmpeg_path
from core.separator import KaraokeSeparator

class KaraokeApp:
    def __init__(self):
        self.output_dir = str(BASE_DIR / "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.selected_file = None
        self.separator = None
        self.is_processing = False
        self.hardware_info = get_hardware_info()

        if HAS_CTK:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
        else:
            self.root = tk.Tk()

        self.root.title("AI KTV 双声道伴唱分割器 (左原声 右伴奏)")
        self.root.geometry("780x680")
        self.root.minsize(700, 600)

        self._build_ui()

    def _build_ui(self):
        if HAS_CTK:
            self._build_ctk_ui()
        else:
            self._build_tk_ui()

    def _build_ctk_ui(self):
        # 顶部标题栏卡片
        top_frame = ctk.CTkFrame(self.root, corner_radius=12, fg_color="#1E1E24")
        top_frame.pack(fill="x", padx=20, pady=(20, 10))

        title_lbl = ctk.CTkLabel(
            top_frame, 
            text="🎤 AI 视频 KTV 双声道分割大师", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title_lbl.pack(pady=(12, 4))

        sub_lbl = ctk.CTkLabel(
            top_frame,
            text=f"自动分割音轨为【左声道: 原装声音 | 右声道: 背景音乐】• 完美适配 K歌伴唱与点歌机 | 算力: {self.hardware_info['device_name']}",
            font=ctk.CTkFont(size=12),
            text_color="#9E9E9E"
        )
        sub_lbl.pack(pady=(0, 12))

        # 文件选择卡片
        file_frame = ctk.CTkFrame(self.root, corner_radius=12)
        file_frame.pack(fill="x", padx=20, pady=10)

        file_title = ctk.CTkLabel(file_frame, text="📁 输入视频 / 音频文件", font=ctk.CTkFont(size=15, weight="bold"))
        file_title.pack(anchor="w", padx=15, pady=(12, 6))

        file_select_subframe = ctk.CTkFrame(file_frame, fg_color="transparent")
        file_select_subframe.pack(fill="x", padx=15, pady=(0, 10))

        self.file_entry = ctk.CTkEntry(
            file_select_subframe, 
            placeholder_text="点击右侧按钮选择，或直接粘贴视频/音频文件路径...",
            font=ctk.CTkFont(size=13)
        )
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(
            file_select_subframe,
            text="选择文件",
            width=100,
            command=self._choose_file
        )
        browse_btn.pack(side="right")

        self.file_info_lbl = ctk.CTkLabel(
            file_frame,
            text="支持格式: MP4, MKV, MOV, FLV, AVI, WEBM, MP3, WAV 等",
            font=ctk.CTkFont(size=12),
            text_color="#7A7A7A"
        )
        self.file_info_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        # 导出选项与设置卡片
        options_frame = ctk.CTkFrame(self.root, corner_radius=12)
        options_frame.pack(fill="x", padx=20, pady=10)

        options_title = ctk.CTkLabel(options_frame, text="⚙️ 声道分割与导出设置", font=ctk.CTkFont(size=15, weight="bold"))
        options_title.pack(anchor="w", padx=15, pady=(12, 6))

        # 核心模式指示：固定直接导出 KTV 左原声右伴奏 MP4
        mode_badge = ctk.CTkLabel(
            options_frame,
            text="🎯 导出格式: KTV 伴唱视频 (.mp4) ——【左声道: 原装声音 | 右声道: 背景音乐】",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#4CAF50"
        )
        mode_badge.pack(anchor="w", padx=15, pady=(0, 4))

        mode_desc = ctk.CTkLabel(
            options_frame,
            text="💡 提示: 左声道保留100%原装声音，右声道为纯背景音乐。播放时切到左声道听原唱，切到右声道变纯伴奏K歌。",
            font=ctk.CTkFont(size=12),
            text_color="#9E9E9E"
        )
        mode_desc.pack(anchor="w", padx=15, pady=(0, 8))

        checkboxes_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        checkboxes_frame.pack(fill="x", padx=15, pady=(0, 8))

        self.var_video = ctk.BooleanVar(value=True)
        self.var_mp3 = ctk.BooleanVar(value=False)

        cb_mp3 = ctk.CTkCheckBox(checkboxes_frame, text="额外保存一份【左原声右伴奏】的双声道音频 (.mp3)", variable=self.var_mp3)
        cb_mp3.grid(row=0, column=0, sticky="w", padx=(0, 20), pady=4)

        # 输出目录行
        out_subframe = ctk.CTkFrame(options_frame, fg_color="transparent")
        out_subframe.pack(fill="x", padx=15, pady=(8, 12))

        out_lbl = ctk.CTkLabel(out_subframe, text="保存至:", font=ctk.CTkFont(size=13))
        out_lbl.pack(side="left", padx=(0, 8))

        self.out_entry = ctk.CTkEntry(out_subframe, font=ctk.CTkFont(size=12))
        self.out_entry.insert(0, self.output_dir)
        self.out_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        out_browse_btn = ctk.CTkButton(out_subframe, text="更改目录", width=90, command=self._choose_output_dir)
        out_browse_btn.pack(side="right")

        # 底部状态及执行卡片
        action_frame = ctk.CTkFrame(self.root, corner_radius=12)
        action_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        self.status_lbl = ctk.CTkLabel(
            action_frame, 
            text="就绪: 请选择需要制作伴奏的视频或音频文件", 
            font=ctk.CTkFont(size=13)
        )
        self.status_lbl.pack(anchor="w", padx=20, pady=(15, 6))

        self.progress_bar = ctk.CTkProgressBar(action_frame, orientation="horizontal")
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 15))

        btn_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_container.pack(fill="x", padx=20, pady=(0, 15))

        self.start_btn = ctk.CTkButton(
            btn_container,
            text="🚀 一键分割导出 KTV 双声道 MP4 (左原声 右背景音乐)",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=45,
            command=self._start_process
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            btn_container,
            text="取消",
            height=45,
            width=80,
            fg_color="#D32F2F",
            hover_color="#B71C1C",
            state="disabled",
            command=self._cancel_process
        )
        self.cancel_btn.pack(side="left", padx=(0, 10))

        self.open_dir_btn = ctk.CTkButton(
            btn_container,
            text="📂 打开导出目录",
            height=45,
            width=130,
            fg_color="#37474F",
            hover_color="#263238",
            command=self._open_output_dir
        )
        self.open_dir_btn.pack(side="right")

    def _build_tk_ui(self):
        # 纯 Tkinter 降级模式UI
        self.root.configure(bg="#2E2E2E")
        lbl = tk.Label(self.root, text="AI K歌伴奏提取器 (左原声 右伴奏)", font=("Arial", 18, "bold"), fg="white", bg="#2E2E2E")
        lbl.pack(pady=10)

        frame = tk.Frame(self.root, bg="#3E3E3E", padx=10, pady=10)
        frame.pack(fill="x", padx=20, pady=10)

        self.file_entry = tk.Entry(frame, width=50)
        self.file_entry.pack(side="left", padx=5)
        browse_btn = tk.Button(frame, text="浏览...", command=self._choose_file)
        browse_btn.pack(side="left")

        self.var_video = tk.BooleanVar(value=True)
        self.var_mp3 = tk.BooleanVar(value=False)

        cb1 = tk.Checkbutton(self.root, text="KTV 双声道视频 (.mp4) [左原声 右背景音乐]", variable=self.var_video, bg="#2E2E2E", fg="white", selectcolor="#444", state="disabled")
        cb1.pack(anchor="w", padx=30)
        cb2 = tk.Checkbutton(self.root, text="额外保存一份双声道音频 (.mp3) [左原声 右背景音乐]", variable=self.var_mp3, bg="#2E2E2E", fg="white", selectcolor="#444")
        cb2.pack(anchor="w", padx=30)

        self.status_lbl = tk.Label(self.root, text="就绪", fg="white", bg="#2E2E2E")
        self.status_lbl.pack(pady=10)

        self.start_btn = tk.Button(self.root, text="🚀 一键导出 KTV 双声道 MP4 (左原声 右伴奏)", command=self._start_process, bg="#0078D7", fg="white", height=2)
        self.start_btn.pack(fill="x", padx=30, pady=10)

    def _choose_file(self):
        filetypes = [
            ("音视频文件", "*.mp4;*.mkv;*.mov;*.flv;*.avi;*.webm;*.mp3;*.wav;*.m4a;*.flac"),
            ("视频文件", "*.mp4;*.mkv;*.mov;*.flv;*.avi;*.webm"),
            ("音频文件", "*.mp3;*.wav;*.m4a;*.flac;*.aac"),
            ("所有文件", "*.*")
        ]
        file_path = filedialog.askopenfilename(title="选择需要分离伴奏的视频或音频", filetypes=filetypes)
        if file_path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, file_path)
            self._update_file_info(file_path)

    def _update_file_info(self, file_path):
        p = Path(file_path)
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            info = f"已选文件: {p.name} ({size_mb:.1f} MB)"
            if HAS_CTK:
                self.file_info_lbl.configure(text=info, text_color="#64B5F6")
            self.status_lbl.configure(text="文件已就绪，点击“开始提取伴奏”即可开始处理。")

    def _choose_output_dir(self):
        dir_path = filedialog.askdirectory(title="选择保存目录", initialdir=self.output_dir)
        if dir_path:
            self.output_dir = dir_path
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, dir_path)

    def _open_output_dir(self):
        current_dir = self.out_entry.get().strip() if HAS_CTK else self.output_dir
        if os.path.exists(current_dir):
            if sys.platform == 'win32':
                os.startfile(current_dir)
            else:
                subprocess.Popen(["xdg-open", current_dir])
        else:
            messagebox.showwarning("提示", "导出目录尚不存在。")

    def _update_progress(self, pct, msg):
        def _ui_update():
            if HAS_CTK:
                self.progress_bar.set(pct)
                self.status_lbl.configure(text=f"[{int(pct*100)}%] {msg}")
            else:
                self.status_lbl.configure(text=f"[{int(pct*100)}%] {msg}")
        self.root.after(0, _ui_update)

    def _start_process(self):
        file_path = self.file_entry.get().strip()
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("错误", "请先选择一个有效的视频或音频文件！")
            return

        export_video = self.var_video.get()
        export_mp3 = self.var_mp3.get()

        if not export_video and not export_mp3:
            messagebox.showwarning("提示", "请至少勾选一种导出格式！")
            return

        output_dir = self.out_entry.get().strip() if HAS_CTK else self.output_dir

        self.is_processing = True
        self.start_btn.configure(state="disabled")
        if HAS_CTK:
            self.cancel_btn.configure(state="normal")
            self.progress_bar.set(0.0)

        # 启动后台线程执行分离
        thread = threading.Thread(
            target=self._run_separation_thread,
            args=(file_path, output_dir, export_video, export_mp3),
            daemon=True
        )
        thread.start()

    def _cancel_process(self):
        if self.separator and self.is_processing:
            self.separator.cancel()
            self.status_lbl.configure(text="正在取消中...")

    def _run_separation_thread(self, file_path, output_dir, export_video, export_mp3):
        try:
            self._update_progress(0.02, "正在初始化环境与组件...")
            
            # 确保 FFmpeg 存在（若缺少会自动触发下载）
            ffmpeg_path = ensure_ffmpeg(progress_callback=self._update_progress)
            
            self.separator = KaraokeSeparator(ffmpeg_path=ffmpeg_path)
            
            created_files = self.separator.process_video(
                video_path=file_path,
                output_dir=output_dir,
                export_video=export_video,
                export_audio_mp3=export_mp3,
                device_choice="auto",
                progress_callback=self._update_progress
            )

            def _on_success():
                self.is_processing = False
                self.start_btn.configure(state="normal")
                if HAS_CTK:
                    self.cancel_btn.configure(state="disabled")
                    self.progress_bar.set(1.0)
                
                # 寻找导出的 MP4 文件
                mp4_files = [f for f in created_files if str(f).lower().endswith(".mp4")]
                target_file = mp4_files[0] if mp4_files else created_files[0]
                
                msg_text = (
                    "🎉 KTV 双声道伴唱制作成功！\n\n"
                    "已自动分割：\n"
                    "• 左声道 (L): 原装声音 (原唱完整声音)\n"
                    "• 右声道 (R): 背景音乐 (纯伴奏)\n\n"
                    f"文件保存在:\n{target_file}\n\n"
                    "是否立即打开导出文件夹？"
                )
                if messagebox.askyesno("制作完成", msg_text):
                    self._open_output_dir()

            self.root.after(0, _on_success)

        except InterruptedError:
            def _on_cancel():
                self.is_processing = False
                self.start_btn.configure(state="normal")
                if HAS_CTK:
                    self.cancel_btn.configure(state="disabled")
                    self.progress_bar.set(0.0)
                self.status_lbl.configure(text="任务已取消。")
            self.root.after(0, _on_cancel)

        except Exception as e:
            def _on_error(err=str(e)):
                self.is_processing = False
                self.start_btn.configure(state="normal")
                if HAS_CTK:
                    self.cancel_btn.configure(state="disabled")
                    self.progress_bar.set(0.0)
                self.status_lbl.configure(text=f"发生错误: {err}")
                messagebox.showerror("运行失败", f"处理过程中发生错误:\n{err}")
            self.root.after(0, _on_error)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = KaraokeApp()
    app.run()
