# -*- coding: utf-8 -*-
"""
拼音歌词字幕大师 - Chinese Song Video Subtitle & Pinyin Studio
Desktop Application built with CustomTkinter
"""
import os
import sys
import threading
import time
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Ensure backend package importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.ffmpeg_utils import get_video_info, burn_subtitles_to_video, FFMPEG_BIN
from backend.pinyin_engine import convert_to_pinyin, STYLE_CHOICES, CASE_CHOICES
from backend.whisper_engine import transcribe_song
from backend.ass_generator import generate_ass_file
from backend.lrc_parser import parse_lrc_file, parse_srt_file, export_to_srt

# Configure CustomTkinter Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class PinyinSubtitleApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🎵 拼音歌词字幕大师 - Chinese Song Subtitle & Pinyin Studio")
        self.geometry("1180x880")
        self.minsize(980, 720)

        # State Variables
        self.video_path = None
        self.video_info = None
        self.segments = []  # List of dicts: {'id': 1, 'start': 0.0, 'end': 3.5, 'text': '', 'pinyin': ''}
        self.cancel_event = threading.Event()
        self.is_processing = False
        self.last_exported_video = None

        # Build UI
        self._build_header()
        self._build_main_layout()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        header_frame = ctk.CTkFrame(self, height=65, corner_radius=0, fg_color="#1E1E2E")
        header_frame.pack(side="top", fill="x")

        title_label = ctk.CTkLabel(
            header_frame,
            text="🎵 拼音歌词字幕大师",
            font=ctk.CTkFont(family="Microsoft YaHei", size=22, weight="bold"),
            text_color="#F5F5F7"
        )
        title_label.pack(side="left", padx=20, pady=12)

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="一键导入中文歌视频 • AI智能识别 • 汉字拼音排版 • 高清无损压制导出",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            text_color="#A6ADC8"
        )
        subtitle_label.pack(side="left", padx=5, pady=12)

        theme_btn = ctk.CTkButton(
            header_frame,
            text="🌓 切换主题",
            width=90,
            height=30,
            command=self._toggle_theme,
            fg_color="#313244",
            hover_color="#45475A"
        )
        theme_btn.pack(side="right", padx=20, pady=15)

    def _toggle_theme(self):
        curr = ctk.get_appearance_mode()
        ctk.set_appearance_mode("Light" if curr == "Dark" else "Dark")

    def _build_main_layout(self):
        # Two-panel layout: Left = Video, Controls, Subtitle List | Right = Style & Preview
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=12)

        left_panel = ctk.CTkFrame(main_container, corner_radius=10)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_panel = ctk.CTkFrame(main_container, width=380, corner_radius=10)
        right_panel.pack(side="right", fill="y", padx=(0, 0))
        right_panel.pack_propagate(False)

        self._build_left_panel(left_panel)
        self._build_right_panel(right_panel)

    def _build_left_panel(self, parent):
        # 1. Video Selection Section
        vid_section = ctk.CTkFrame(parent, fg_color="#181825", corner_radius=8)
        vid_section.pack(fill="x", padx=12, pady=(12, 6))

        sec_title = ctk.CTkLabel(
            vid_section,
            text="第一步：选择中文歌视频",
            font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold"),
            text_color="#89B4FA"
        )
        sec_title.pack(anchor="w", padx=12, pady=(8, 4))

        vid_row = ctk.CTkFrame(vid_section, fg_color="transparent")
        vid_row.pack(fill="x", padx=12, pady=(0, 8))

        self.vid_path_entry = ctk.CTkEntry(
            vid_row,
            placeholder_text="点击右侧按钮选择视频文件 (MP4, MKV, MOV, FLV, AVI)...",
            font=ctk.CTkFont(size=12),
            height=34
        )
        self.vid_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(
            vid_row,
            text="📂 浏览视频",
            width=110,
            height=34,
            command=self._browse_video,
            fg_color="#89B4FA",
            text_color="#11111B",
            hover_color="#B4BEFE",
            font=ctk.CTkFont(weight="bold")
        )
        browse_btn.pack(side="right")

        self.vid_info_label = ctk.CTkLabel(
            vid_section,
            text="尚未载入视频",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            text_color="#6C7086"
        )
        self.vid_info_label.pack(anchor="w", padx=12, pady=(0, 8))

        # 2. Transcription / Generation Control Section
        gen_section = ctk.CTkFrame(parent, fg_color="#181825", corner_radius=8)
        gen_section.pack(fill="x", padx=12, pady=6)

        sec2_title = ctk.CTkLabel(
            gen_section,
            text="第二步：歌词与拼音生成",
            font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold"),
            text_color="#A6E3A1"
        )
        sec2_title.pack(anchor="w", padx=12, pady=(8, 4))

        btn_row = ctk.CTkFrame(gen_section, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 8))

        self.ai_btn = ctk.CTkButton(
            btn_row,
            text="🤖 AI 智能识别歌词与时间轴",
            height=36,
            command=self._start_ai_transcribe,
            fg_color="#A6E3A1",
            text_color="#11111B",
            hover_color="#94E2D5",
            font=ctk.CTkFont(weight="bold")
        )
        self.ai_btn.pack(side="left", padx=(0, 10))

        self.model_combo = ctk.CTkComboBox(
            btn_row,
            values=["base (推荐, 均衡快速)", "tiny (极速识别)", "small (高精确度)"],
            width=170,
            height=36
        )
        self.model_combo.set("base (推荐, 均衡快速)")
        self.model_combo.pack(side="left", padx=(0, 10))

        import_lrc_btn = ctk.CTkButton(
            btn_row,
            text="📄 导入歌词 (.lrc / .srt)",
            width=150,
            height=36,
            command=self._import_lrc,
            fg_color="#313244",
            hover_color="#45475A"
        )
        import_lrc_btn.pack(side="left", padx=(0, 10))

        paste_lrc_btn = ctk.CTkButton(
            btn_row,
            text="✍️ 粘贴纯歌词",
            width=110,
            height=36,
            command=self._open_paste_lyrics_dialog,
            fg_color="#313244",
            hover_color="#45475A"
        )
        paste_lrc_btn.pack(side="left")

        # Progress bar & status
        self.progress_frame = ctk.CTkFrame(gen_section, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=12, pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=12)
        self.progress_bar.pack(fill="x", pady=(2, 4))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            self.progress_frame,
            text="准备就绪",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            text_color="#CDD6F4"
        )
        self.status_label.pack(side="left")

        self.cancel_btn = ctk.CTkButton(
            self.progress_frame,
            text="取消操作",
            width=80,
            height=24,
            command=self._cancel_processing,
            fg_color="#F38BA8",
            text_color="#11111B",
            hover_color="#EBA0AC",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.cancel_btn.pack(side="right")
        self.cancel_btn.pack_forget()

        # 3. Subtitle Editor Table Section
        table_section = ctk.CTkFrame(parent, fg_color="#181825", corner_radius=8)
        table_section.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        table_header = ctk.CTkFrame(table_section, fg_color="transparent")
        table_header.pack(fill="x", padx=12, pady=(8, 4))

        sec3_title = ctk.CTkLabel(
            table_header,
            text="第三步：歌词与拼音在线校对表 (双击直接修改歌词或拼音)",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
            text_color="#F9E2AF"
        )
        sec3_title.pack(side="left")

        add_row_btn = ctk.CTkButton(
            table_header,
            text="➕ 加一行",
            width=75,
            height=26,
            command=self._add_empty_row,
            fg_color="#313244",
            hover_color="#45475A",
            font=ctk.CTkFont(size=11)
        )
        add_row_btn.pack(side="right", padx=(5, 0))

        regen_py_btn = ctk.CTkButton(
            table_header,
            text="🔄 重新生成拼音",
            width=115,
            height=26,
            command=self._regenerate_all_pinyin,
            fg_color="#313244",
            hover_color="#45475A",
            font=ctk.CTkFont(size=11)
        )
        regen_py_btn.pack(side="right", padx=(5, 0))

        clear_btn = ctk.CTkButton(
            table_header,
            text="🗑️ 清空",
            width=65,
            height=26,
            command=self._clear_subtitles,
            fg_color="#45475A",
            hover_color="#585B70",
            font=ctk.CTkFont(size=11)
        )
        clear_btn.pack(side="right")

        # Scrollable list for subtitle rows
        self.table_scroll = ctk.CTkScrollableFrame(table_section, fg_color="#11111B", corner_radius=6)
        self.table_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.row_widgets = []  # Will store list of widget dicts

        self._render_table()

    def _build_right_panel(self, parent):
        # Subtitle Styling & Export
        title = ctk.CTkLabel(
            parent,
            text="🎨 字幕样式与排版",
            font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),
            text_color="#CBA6F7"
        )
        title.pack(anchor="w", padx=15, pady=(15, 8))

        # Layout Mode
        ctk.CTkLabel(parent, text="排版风格:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=15, pady=(4, 2))
        self.layout_mode_combo = ctk.CTkComboBox(
            parent,
            values=[
                "双行式 (上方拼音 + 下方汉字)",
                "行内并列式 (汉字 [拼音])",
                "仅显示拼音",
                "仅显示汉字"
            ],
            command=lambda _: self._update_preview()
        )
        self.layout_mode_combo.set("双行式 (上方拼音 + 下方汉字)")
        self.layout_mode_combo.pack(fill="x", padx=15, pady=(0, 8))

        # Tone Style
        ctk.CTkLabel(parent, text="拼音声调格式:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=15, pady=(4, 2))
        self.tone_style_combo = ctk.CTkComboBox(
            parent,
            values=list(STYLE_CHOICES.keys()),
            command=lambda _: self._on_tone_style_changed()
        )
        self.tone_style_combo.set("带声调 (wǒ hé nǐ)")
        self.tone_style_combo.pack(fill="x", padx=15, pady=(0, 8))

        # Font family
        ctk.CTkLabel(parent, text="字幕字体:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=15, pady=(4, 2))
        self.font_combo = ctk.CTkComboBox(
            parent,
            values=["Microsoft YaHei", "SimHei", "KaiTi", "SimSun"],
            command=lambda _: self._update_preview()
        )
        self.font_combo.set("Microsoft YaHei")
        self.font_combo.pack(fill="x", padx=15, pady=(0, 8))

        # Colors & Sizes Frame
        grid_frame = ctk.CTkFrame(parent, fg_color="transparent")
        grid_frame.pack(fill="x", padx=15, pady=4)

        # Pinyin Font Size
        ctk.CTkLabel(grid_frame, text="拼音字号:", font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", pady=3)
        self.py_size_slider = ctk.CTkSlider(grid_frame, from_=18, to=56, number_of_steps=38, command=lambda _: self._update_preview())
        self.py_size_slider.set(32)
        self.py_size_slider.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)

        # Hanzi Font Size
        ctk.CTkLabel(grid_frame, text="汉字字号:", font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", pady=3)
        self.hz_size_slider = ctk.CTkSlider(grid_frame, from_=26, to=80, number_of_steps=54, command=lambda _: self._update_preview())
        self.hz_size_slider.set(52)
        self.hz_size_slider.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=3)

        # Pinyin Color
        ctk.CTkLabel(grid_frame, text="拼音颜色:", font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w", pady=3)
        self.py_color_combo = ctk.CTkComboBox(
            grid_frame,
            values=["明黄 (#FFD700)", "纯白 (#FFFFFF)", "浅青 (#00E5FF)", "荧光绿 (#76FF03)", "粉红 (#FF4081)"],
            command=lambda _: self._update_preview()
        )
        self.py_color_combo.set("明黄 (#FFD700)")
        self.py_color_combo.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=3)

        # Hanzi Color
        ctk.CTkLabel(grid_frame, text="汉字颜色:", font=ctk.CTkFont(size=11)).grid(row=3, column=0, sticky="w", pady=3)
        self.hz_color_combo = ctk.CTkComboBox(
            grid_frame,
            values=["纯白 (#FFFFFF)", "淡黄 (#FFF9C4)", "浅粉 (#F8BBD0)", "明黄 (#FFD700)"],
            command=lambda _: self._update_preview()
        )
        self.hz_color_combo.set("纯白 (#FFFFFF)")
        self.hz_color_combo.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=3)

        # Margin V
        ctk.CTkLabel(grid_frame, text="底部高度:", font=ctk.CTkFont(size=11)).grid(row=4, column=0, sticky="w", pady=3)
        self.margin_slider = ctk.CTkSlider(grid_frame, from_=20, to=150, number_of_steps=65, command=lambda _: self._update_preview())
        self.margin_slider.set(45)
        self.margin_slider.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=3)

        grid_frame.columnconfigure(1, weight=1)

        # Live Preview Canvas Box
        ctk.CTkLabel(parent, text="📺 效果实时预览:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=15, pady=(10, 4))
        self.preview_canvas = tk.Canvas(parent, height=130, bg="#11111B", highlightthickness=1, highlightbackground="#313244")
        self.preview_canvas.pack(fill="x", padx=15, pady=(0, 10))

        # Export Section
        export_box = ctk.CTkFrame(parent, fg_color="#181825", corner_radius=8)
        export_box.pack(fill="x", side="bottom", padx=15, pady=15)

        self.export_btn = ctk.CTkButton(
            export_box,
            text="🚀 一键导出高清视频 (压制拼音字幕)",
            height=46,
            command=self._start_export_video,
            fg_color="#FAB387",
            text_color="#11111B",
            hover_color="#F9E2AF",
            font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
        )
        self.export_btn.pack(fill="x", padx=12, pady=(12, 6))

        ext_btn_row = ctk.CTkFrame(export_box, fg_color="transparent")
        ext_btn_row.pack(fill="x", padx=12, pady=(0, 12))

        self.play_btn = ctk.CTkButton(
            ext_btn_row,
            text="▶️ 播放导出视频",
            height=30,
            command=self._play_exported_video,
            fg_color="#313244",
            hover_color="#45475A",
            font=ctk.CTkFont(size=11)
        )
        self.play_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.play_btn.configure(state="disabled")

        self.open_folder_btn = ctk.CTkButton(
            ext_btn_row,
            text="📂 打开文件位置",
            height=30,
            command=self._open_output_folder,
            fg_color="#313244",
            hover_color="#45475A",
            font=ctk.CTkFont(size=11)
        )
        self.open_folder_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.open_folder_btn.configure(state="disabled")

        self._update_preview()

    def _extract_color_hex(self, combo_value):
        if "(#" in combo_value:
            return combo_value.split("(#")[1].rstrip(")")
        return "#FFFFFF"

    def _update_preview(self):
        self.preview_canvas.delete("all")
        w = self.preview_canvas.winfo_width()
        if w < 100:
            w = 350
        h = 130
        cx = w / 2

        py_color = "#" + self._extract_color_hex(self.py_color_combo.get())
        hz_color = "#" + self._extract_color_hex(self.hz_color_combo.get())
        font_family = self.font_combo.get()
        mode = self.layout_mode_combo.get()

        py_size = int(self.py_size_slider.get() * 0.45)
        hz_size = int(self.hz_size_slider.get() * 0.45)

        # Background simulated video frame
        self.preview_canvas.create_rectangle(0, 0, w, h, fill="#181825", outline="")

        # Sample lyrics
        pinyin_sample = "wǒ hé wǒ de zǔ guó"
        hanzi_sample = "我和我的祖国"

        if mode == "双行式 (上方拼音 + 下方汉字)":
            # Pinyin on top
            self._draw_text_with_outline(
                cx, h - 68, pinyin_sample, font_family, py_size, py_color, "#000000"
            )
            # Hanzi on bottom
            self._draw_text_with_outline(
                cx, h - 34, hanzi_sample, font_family, hz_size, hz_color, "#000000", bold=True
            )
        elif mode == "行内并列式 (汉字 [拼音])":
            combined = f"{hanzi_sample} ({pinyin_sample})"
            self._draw_text_with_outline(
                cx, h - 45, combined, font_family, hz_size, hz_color, "#000000", bold=True
            )
        elif mode == "仅显示拼音":
            self._draw_text_with_outline(
                cx, h - 45, pinyin_sample, font_family, py_size + 4, py_color, "#000000"
            )
        else:
            self._draw_text_with_outline(
                cx, h - 45, hanzi_sample, font_family, hz_size, hz_color, "#000000", bold=True
            )

    def _draw_text_with_outline(self, x, y, text, font_family, size, text_color, outline_color, bold=False):
        weight = "bold" if bold else "normal"
        font = (font_family, size, weight)
        # Outline by drawing offset shadows
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    self.preview_canvas.create_text(x + dx, y + dy, text=text, font=font, fill=outline_color)
        # Main text
        self.preview_canvas.create_text(x, y, text=text, font=font, fill=text_color)

    def _on_tone_style_changed(self):
        self._regenerate_all_pinyin()
        self._update_preview()

    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="选择中文歌视频文件",
            filetypes=[("视频文件", "*.mp4 *.mkv *.mov *.flv *.avi *.webm *.ts"), ("所有文件", "*.*")]
        )
        if not path:
            return

        self.video_path = path
        self.vid_path_entry.delete(0, "end")
        self.vid_path_entry.insert(0, path)

        self.status_label.configure(text="正在分析视频信息...")
        threading.Thread(target=self._load_video_metadata, daemon=True).start()

    def _load_video_metadata(self):
        info = get_video_info(self.video_path)
        self.video_info = info

        dur = info.get("duration", 0)
        dur_str = f"{int(dur // 60):02d}:{int(dur % 60):02d}"
        res_str = f"{info.get('width', 0)}x{info.get('height', 0)}"
        audio_str = "包含音频" if info.get("has_audio") else "无音轨"

        text = f"时长: {dur_str} | 分辨率: {res_str} | 帧率: {info.get('fps', 30)}fps | {audio_str}"
        self.after(0, lambda: self.vid_info_label.configure(text=text, text_color="#A6ADC8"))
        self.after(0, lambda: self.status_label.configure(text="视频加载完成，可以开始识别或编辑字幕。"))

    # AI Transcription
    def _start_ai_transcribe(self):
        if not self.video_path or not os.path.isfile(self.video_path):
            messagebox.showwarning("提示", "请先选择一个有效的视频文件！")
            return

        if self.is_processing:
            return

        model_choice = self.model_combo.get().split(" ")[0].lower()
        tone_choice = self.tone_style_combo.get()

        self.is_processing = True
        self.cancel_event.clear()
        self.cancel_btn.pack(side="right")
        self.ai_btn.configure(state="disabled")
        self.export_btn.configure(state="disabled")

        def worker():
            try:
                def cb(msg, frac):
                    self.after(0, lambda: self.status_label.configure(text=msg))
                    self.after(0, lambda: self.progress_bar.set(frac))

                segs = transcribe_song(
                    self.video_path,
                    model_name=model_choice,
                    status_callback=cb,
                    cancel_event=self.cancel_event,
                    pinyin_tone_style=tone_choice
                )
                self.after(0, lambda: self._on_transcribe_done(segs))
            except InterruptedError:
                self.after(0, lambda: self.status_label.configure(text="识别已被用户取消。"))
                self.after(0, lambda: self.progress_bar.set(0))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("识别出错", f"AI 语音识别遇到错误:\n{str(e)}"))
                self.after(0, lambda: self.status_label.configure(text="识别失败"))
            finally:
                self.after(0, self._reset_processing_state)

        threading.Thread(target=worker, daemon=True).start()

    def _on_transcribe_done(self, segs):
        self.segments = segs
        self._render_table()
        messagebox.showinfo("完成", f"歌词与拼音识别完成！共提取 {len(segs)} 行歌词。\n您可以在列表中直接双击编辑微调。")

    def _cancel_processing(self):
        self.cancel_event.set()
        self.status_label.configure(text="正在中止操作...")

    def _reset_processing_state(self):
        self.is_processing = False
        self.cancel_btn.pack_forget()
        self.ai_btn.configure(state="normal")
        self.export_btn.configure(state="normal")

    # Table Rendering & Editing
    def _render_table(self):
        # Clear existing rows
        for child in self.table_scroll.winfo_children():
            child.destroy()
        self.row_widgets.clear()

        if not self.segments:
            empty_lbl = ctk.CTkLabel(
                self.table_scroll,
                text="当前暂无字幕数据\n点击上方【AI 智能识别】或【导入歌词】快速生成！",
                font=ctk.CTkFont(family="Microsoft YaHei", size=13),
                text_color="#6C7086"
            )
            empty_lbl.pack(pady=40)
            return

        # Header Row
        hdr = ctk.CTkFrame(self.table_scroll, fg_color="#1E1E2E", height=28)
        hdr.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(hdr, text="#", width=35, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        ctk.CTkLabel(hdr, text="开始(秒)", width=65, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
        ctk.CTkLabel(hdr, text="结束(秒)", width=65, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
        ctk.CTkLabel(hdr, text="中文歌词 (可编辑)", width=240, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(hdr, text="拼音注音 (可编辑)", width=240, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(hdr, text="操作", width=60, font=ctk.CTkFont(size=11, weight="bold")).pack(side="right", padx=5)

        for i, seg in enumerate(self.segments):
            row_frame = ctk.CTkFrame(self.table_scroll, fg_color="#181825", height=32)
            row_frame.pack(fill="x", pady=2)

            idx_lbl = ctk.CTkLabel(row_frame, text=str(i + 1), width=35, font=ctk.CTkFont(size=11))
            idx_lbl.pack(side="left")

            start_entry = ctk.CTkEntry(row_frame, width=65, height=26, font=ctk.CTkFont(size=11))
            start_entry.insert(0, f"{seg.get('start', 0.0):.2f}")
            start_entry.pack(side="left", padx=2)

            end_entry = ctk.CTkEntry(row_frame, width=65, height=26, font=ctk.CTkFont(size=11))
            end_entry.insert(0, f"{seg.get('end', 0.0):.2f}")
            end_entry.pack(side="left", padx=2)

            text_entry = ctk.CTkEntry(row_frame, width=240, height=26, font=ctk.CTkFont(family="Microsoft YaHei", size=11))
            text_entry.insert(0, seg.get("text", ""))
            text_entry.pack(side="left", padx=5)

            py_entry = ctk.CTkEntry(row_frame, width=240, height=26, font=ctk.CTkFont(family="Microsoft YaHei", size=11))
            py_entry.insert(0, seg.get("pinyin", ""))
            py_entry.pack(side="left", padx=5)

            # Auto-update pinyin when text changes
            def make_text_callback(t_ent, p_ent):
                def on_text_changed(event):
                    new_text = t_ent.get().strip()
                    tone_choice = self.tone_style_combo.get()
                    new_pinyin = convert_to_pinyin(new_text, tone_style=tone_choice)
                    p_ent.delete(0, "end")
                    p_ent.insert(0, new_pinyin)
                return on_text_changed

            text_entry.bind("<FocusOut>", make_text_callback(text_entry, py_entry))

            del_btn = ctk.CTkButton(
                row_frame,
                text="✕",
                width=30,
                height=24,
                fg_color="#45475A",
                hover_color="#F38BA8",
                command=lambda idx=i: self._delete_row(idx)
            )
            del_btn.pack(side="right", padx=5)

            self.row_widgets.append({
                "start": start_entry,
                "end": end_entry,
                "text": text_entry,
                "pinyin": py_entry
            })

    def _sync_segments_from_ui(self):
        """Read all entries from table into self.segments"""
        new_segs = []
        for i, widgets in enumerate(self.row_widgets):
            try:
                st = float(widgets["start"].get())
            except ValueError:
                st = 0.0
            try:
                et = float(widgets["end"].get())
            except ValueError:
                et = st + 2.0

            txt = widgets["text"].get().strip()
            py = widgets["pinyin"].get().strip()

            new_segs.append({
                "id": i + 1,
                "start": st,
                "end": et,
                "text": txt,
                "pinyin": py
            })
        self.segments = new_segs

    def _delete_row(self, index):
        self._sync_segments_from_ui()
        if 0 <= index < len(self.segments):
            self.segments.pop(index)
            self._render_table()

    def _add_empty_row(self):
        self._sync_segments_from_ui()
        last_end = self.segments[-1]["end"] if self.segments else 0.0
        self.segments.append({
            "id": len(self.segments) + 1,
            "start": round(last_end + 0.5, 2),
            "end": round(last_end + 3.5, 2),
            "text": "新歌词行",
            "pinyin": convert_to_pinyin("新歌词行", tone_style=self.tone_style_combo.get())
        })
        self._render_table()

    def _clear_subtitles(self):
        if self.segments and messagebox.askyesno("确认", "确定清空当前所有歌词字幕吗？"):
            self.segments = []
            self._render_table()

    def _regenerate_all_pinyin(self):
        self._sync_segments_from_ui()
        tone_choice = self.tone_style_combo.get()
        for seg in self.segments:
            seg["pinyin"] = convert_to_pinyin(seg.get("text", ""), tone_style=tone_choice)
        self._render_table()
        self.status_label.configure(text=f"已按【{tone_choice}】刷新全部拼音！")

    # Import LRC
    def _import_lrc(self):
        path = filedialog.askopenfilename(
            title="选择歌词或字幕文件",
            filetypes=[("歌词/字幕文件", "*.lrc *.srt"), ("LRC 文件", "*.lrc"), ("SRT 文件", "*.srt"), ("所有文件", "*.*")]
        )
        if not path:
            return

        tone_choice = self.tone_style_combo.get()
        try:
            if path.lower().endswith(".lrc"):
                segs = parse_lrc_file(path, tone_style=tone_choice)
            else:
                segs = parse_srt_file(path, tone_style=tone_choice)

            if not segs:
                messagebox.showwarning("提示", "未在该文件中读取到有效的时间轴与歌词。")
                return

            self.segments = segs
            self._render_table()
            messagebox.showinfo("导入成功", f"成功导入 {len(segs)} 行歌词并已自动生成拼音！")
        except Exception as e:
            messagebox.showerror("导入错误", f"解析歌词文件失败:\n{str(e)}")

    def _open_paste_lyrics_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("粘贴中文歌词")
        dialog.geometry("560x480")
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="请在下方粘贴歌词文本 (每行一句)：",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 5))

        txt_box = ctk.CTkTextbox(dialog, height=280)
        txt_box.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 15))

        def on_confirm():
            raw = txt_box.get("1.0", "end").strip()
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            if not lines:
                dialog.destroy()
                return

            tone_choice = self.tone_style_combo.get()
            self._sync_segments_from_ui()

            # Assign sequential timestamps
            curr_start = self.segments[-1]["end"] + 0.5 if self.segments else 0.0
            new_entries = []
            for line in lines:
                py = convert_to_pinyin(line, tone_style=tone_choice)
                end_t = round(curr_start + 3.0, 2)
                new_entries.append({
                    "id": len(self.segments) + len(new_entries) + 1,
                    "start": round(curr_start, 2),
                    "end": end_t,
                    "text": line,
                    "pinyin": py
                })
                curr_start = end_t + 0.5

            self.segments.extend(new_entries)
            self._render_table()
            dialog.destroy()
            messagebox.showinfo("完成", f"已导入 {len(lines)} 行歌词并注音！您可在列表中调整具体起止秒数。")

        ctk.CTkButton(btn_row, text="取消", fg_color="#45475A", command=dialog.destroy).pack(side="right", padx=(10, 0))
        ctk.CTkButton(btn_row, text="确认导入并注音", fg_color="#A6E3A1", text_color="#11111B", command=on_confirm).pack(side="right")

    # Export Video
    def _start_export_video(self):
        if not self.video_path or not os.path.isfile(self.video_path):
            messagebox.showwarning("提示", "请先选择需要压制字幕的中文歌视频！")
            return

        self._sync_segments_from_ui()
        if not self.segments:
            messagebox.showwarning("提示", "当前没有字幕内容，请先识别或添加歌词！")
            return

        # Default output path
        dir_name, base_name = os.path.split(self.video_path)
        name, ext = os.path.splitext(base_name)
        default_out = os.path.join(dir_name, f"{name}_拼音字幕.mp4")

        out_path = filedialog.asksaveasfilename(
            title="保存导出视频文件",
            initialdir=dir_name,
            initialfile=os.path.basename(default_out),
            defaultextension=".mp4",
            filetypes=[("MP4 视频文件", "*.mp4"), ("所有文件", "*.*")]
        )
        if not out_path:
            return

        if os.path.abspath(out_path) == os.path.abspath(self.video_path):
            messagebox.showerror("错误", "输出文件不能与原视频相同，请选择新的文件名！")
            return

        # Prepare ASS parameters
        font_family = self.font_combo.get()
        layout_mode = self.layout_mode_combo.get()
        pinyin_size = int(self.py_size_slider.get())
        hanzi_size = int(self.hz_size_slider.get())
        margin_v = int(self.margin_slider.get())
        py_color = "#" + self._extract_color_hex(self.py_color_combo.get())
        hz_color = "#" + self._extract_color_hex(self.hz_color_combo.get())

        res_x = self.video_info.get("width", 1920) if self.video_info else 1920
        res_y = self.video_info.get("height", 1080) if self.video_info else 1080
        total_dur = self.video_info.get("duration", 0) if self.video_info else 0

        self.is_processing = True
        self.cancel_event.clear()
        self.cancel_btn.pack(side="right")
        self.export_btn.configure(state="disabled")
        self.ai_btn.configure(state="disabled")

        def worker():
            ass_path = None
            try:
                # 1. Generate temp ASS file
                ass_path = os.path.splitext(out_path)[0] + "_temp.ass"
                generate_ass_file(
                    self.segments,
                    ass_path,
                    res_x=res_x,
                    res_y=res_y,
                    font_name=font_family,
                    pinyin_size=pinyin_size,
                    pinyin_color=py_color,
                    hanzi_size=hanzi_size,
                    hanzi_color=hz_color,
                    outline_width=2.5,
                    margin_v=margin_v,
                    layout_mode=layout_mode
                )

                # 2. Burn with FFmpeg
                def progress_cb(frac, curr_sec, tot_sec):
                    pct = int(frac * 100)
                    msg = f"正在压制视频: {pct}% ({int(curr_sec)}s / {int(tot_sec)}s)"
                    self.after(0, lambda: self.status_label.configure(text=msg))
                    self.after(0, lambda: self.progress_bar.set(frac))

                burn_subtitles_to_video(
                    self.video_path,
                    ass_path,
                    out_path,
                    total_duration=total_dur,
                    progress_callback=progress_cb,
                    cancel_event=self.cancel_event
                )

                self.last_exported_video = out_path
                self.after(0, lambda: self._on_export_success(out_path))

            except InterruptedError:
                self.after(0, lambda: self.status_label.configure(text="导出已被用户取消。"))
                self.after(0, lambda: self.progress_bar.set(0))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("导出失败", f"压制视频过程遇到错误:\n{str(e)}"))
                self.after(0, lambda: self.status_label.configure(text="导出失败"))
            finally:
                if ass_path and os.path.isfile(ass_path):
                    try:
                        os.remove(ass_path)
                    except Exception:
                        pass
                self.after(0, self._reset_processing_state)

        threading.Thread(target=worker, daemon=True).start()

    def _on_export_success(self, out_path):
        self.status_label.configure(text="🎉 视频导出成功！")
        self.progress_bar.set(1.0)
        self.play_btn.configure(state="normal")
        self.open_folder_btn.configure(state="normal")
        messagebox.showinfo("导出成功", f"🎉 拼音歌词视频已成功导出！\n\n保存路径:\n{out_path}")

    def _play_exported_video(self):
        if self.last_exported_video and os.path.isfile(self.last_exported_video):
            os.startfile(self.last_exported_video)

    def _open_output_folder(self):
        if self.last_exported_video and os.path.isfile(self.last_exported_video):
            subprocess.run(f'explorer /select,"{os.path.abspath(self.last_exported_video)}"', shell=True)

    def _on_close(self):
        if self.is_processing:
            if not messagebox.askyesno("退出提示", "后台正在处理中，确定要取消并退出吗？"):
                return
            self.cancel_event.set()
        self.destroy()


def main():
    app = PinyinSubtitleApp()
    app.mainloop()


if __name__ == "__main__":
    main()
