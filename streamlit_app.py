import os
import sys
import tempfile
from pathlib import Path
import streamlit as st

# 确保项目根目录在 sys.path 中
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.utils import ensure_ffmpeg, get_hardware_info
from core.separator import KaraokeSeparator

# 页面基础配置
st.set_page_config(
    page_title="AI KTV 双声道伴唱分割器",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🔒 私人访问认证逻辑 (支持通过 st.secrets 或环境变量设置 APP_PASSWORD)
def check_password():
    """检查访问密码，若未配置密码则直接公开，若配置了密码则强制要求验证"""
    configured_password = None
    try:
        if "APP_PASSWORD" in st.secrets:
            configured_password = st.secrets["APP_PASSWORD"]
    except Exception:
        pass

    if not configured_password:
        configured_password = os.environ.get("APP_PASSWORD", "")

    # 如果未设置任何密码，则无需验证
    if not configured_password:
        return True

    def password_entered():
        if st.session_state.get("password_input") == configured_password:
            st.session_state["password_correct"] = True
            st.session_state.pop("password_input", None)
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct"):
        return True

    # 显示密码输入界面
    st.markdown("## 🔒 私人应用访问验证")
    st.info("此应用已开启私人访问保护，请输入访问密码以解锁使用：")
    st.text_input(
        "请输入访问密码", 
        type="password", 
        key="password_input", 
        on_change=password_entered,
        placeholder="输入密码后按回车..."
    )
    if st.session_state.get("password_correct") is False:
        st.error("❌ 密码错误，请重新输入！")
    return False

# 执行密码验证，未通过则停止渲染后续内容
if not check_password():
    st.stop()

# 侧边栏配置与状态说明
with st.sidebar:
    st.title("⚙️ 系统与设备")
    hw_info = get_hardware_info()
    st.info(f"**运行算力设备**: {hw_info['device_name']}")
    
    st.markdown("---")
    st.subheader("🎧 声道模式说明")
    st.markdown(
        """
        - 🔊 **左声道 (Left)**: **原装声音**  
          100% 原始完整音频（原唱与伴奏一应俱全，无任何 AI 削波与音质损失）。
        - 🎵 **右声道 (Right)**: **背景音乐**  
          Demucs AI 分离出的纯伴奏音乐（原声消音，适合拿麦克风欢唱）。
        
        > **使用技巧**: 在播放器（如 VLC、PotPlayer 或 KTV 播放系统）中选择左声道听原唱，切换到右声道即变纯伴奏！
        """
    )
    st.markdown("---")
    st.caption("AI 伴奏分离模型: Demucs (Hybrid Transformer)")

# 主界面标题
st.title("🎤 AI 视频/音频 KTV 双声道伴唱分割器")
st.markdown("上传任意视频或音乐文件，AI 自动分离并将音轨重构为标准的 **【左声道: 原装声音 | 右声道: 背景音乐】**！")

# 文件上传区
uploaded_file = st.file_uploader(
    "📁 选择或拖入视频/音频文件",
    type=["mp4", "mkv", "mov", "avi", "webm", "flv", "mp3", "wav", "m4a", "flac", "aac"],
    help="支持几乎所有主流音视频格式"
)

# 导出格式勾选
col1, col2 = st.columns(2)
with col1:
    export_video = st.checkbox("导出 KTV 双声道 MP4 视频 (保持原画质)", value=True)
with col2:
    export_mp3 = st.checkbox("额外导出 KTV 双声道 MP3 音频", value=False)

if uploaded_file is not None:
    file_details = {
        "文件名": uploaded_file.name,
        "文件大小": f"{uploaded_file.size / (1024 * 1024):.2f} MB",
        "格式": uploaded_file.type or Path(uploaded_file.name).suffix
    }
    st.write(f"📄 已选文件: **{file_details['文件名']}** ({file_details['文件大小']})")

    start_button = st.button("🚀 开始一键 AI 分离制作", type="primary", use_container_width=True)

    if start_button:
        if not export_video and not export_mp3:
            st.warning("⚠️ 请至少勾选一种导出格式（MP4 视频 或 MP3 音频）！")
        else:
            # 状态与进度条占位符
            status_box = st.status("正在初始化制作流程...", expanded=True)
            progress_bar = st.progress(0.0)

            def progress_callback(pct, msg):
                progress_bar.progress(min(max(float(pct), 0.0), 1.0))
                status_box.write(f"[{int(pct * 100)}%] {msg}")

            try:
                # 检查 FFmpeg 环境
                status_box.write("正在检查 FFmpeg 多媒体组件...")
                ffmpeg_path = ensure_ffmpeg(progress_callback=progress_callback)

                # 将上传文件写入临时文件
                input_suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=input_suffix) as tmp_in:
                    tmp_in.write(uploaded_file.getbuffer())
                    temp_input_path = tmp_in.name

                output_dir = BASE_DIR / "output"
                output_dir.mkdir(parents=True, exist_ok=True)

                separator = KaraokeSeparator(ffmpeg_path=ffmpeg_path)
                status_box.write("开始处理音轨并调用 Demucs AI 引擎...")

                created_files = separator.process_video(
                    video_path=temp_input_path,
                    output_dir=str(output_dir),
                    export_video=export_video,
                    export_audio_mp3=export_mp3,
                    device_choice="auto",
                    progress_callback=progress_callback
                )

                # 清理临时输入文件
                try:
                    os.unlink(temp_input_path)
                except Exception:
                    pass

                progress_bar.progress(1.0)
                status_box.update(label="🎉 制作完成！文件已生成完毕", state="complete", expanded=False)

                st.success("✅ KTV 双声道伴唱音视频制作成功！")

                # 展示导出文件并提供直接下载与在线预览
                for file_path in created_files:
                    fp = Path(file_path)
                    st.markdown(f"### 📦 成果文件: `{fp.name}`")
                    
                    with open(fp, "rb") as f:
                        file_bytes = f.read()

                    col_prev, col_dl = st.columns([2, 1])

                    # 预览与下载
                    if fp.suffix.lower() == ".mp4":
                        with col_prev:
                            st.video(file_bytes)
                        with col_dl:
                            st.download_button(
                                label=f"⬇️ 下载 MP4 视频 ({len(file_bytes) / (1024*1024):.1f} MB)",
                                data=file_bytes,
                                file_name=fp.name,
                                mime="video/mp4",
                                use_container_width=True
                            )
                    elif fp.suffix.lower() == ".mp3":
                        with col_prev:
                            st.audio(file_bytes, format="audio/mp3")
                        with col_dl:
                            st.download_button(
                                label=f"⬇️ 下载 MP3 音频 ({len(file_bytes) / (1024*1024):.1f} MB)",
                                data=file_bytes,
                                file_name=fp.name,
                                mime="audio/mp3",
                                use_container_width=True
                            )

            except Exception as e:
                status_box.update(label="❌ 处理失败", state="error", expanded=True)
                st.error(f"处理过程中出现错误: {e}")
