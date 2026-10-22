# -*- coding: utf-8 -*-
"""
Whisper Speech-to-Text Transcription Engine
Extracts lyrics and timestamps from video/audio.
"""
import os
import tempfile
import whisper
from .ffmpeg_utils import extract_audio
from .pinyin_engine import convert_to_pinyin, clean_song_text

_LOADED_MODELS = {}

def get_whisper_model(model_name="base", device="cpu"):
    """
    Cache loaded models to avoid re-downloading/re-loading on subsequent runs.
    """
    key = f"{model_name}_{device}"
    if key not in _LOADED_MODELS:
        _LOADED_MODELS[key] = whisper.load_model(model_name, device=device)
    return _LOADED_MODELS[key]

def transcribe_song(
    video_path,
    model_name="base",
    status_callback=None,
    cancel_event=None,
    pinyin_tone_style="带声调 (wǒ hé nǐ)",
    pinyin_case_style="全小写 (abc)"
):
    """
    Transcribe song audio from video and generate subtitle segments with Pinyin.
    Returns list of dicts:
    [
        {
            "id": 1,
            "start": 1.25,
            "end": 4.50,
            "text": "我和我的祖国",
            "pinyin": "wǒ hé wǒ de zǔ guó"
        },
        ...
    ]
    """
    temp_wav = None
    try:
        if status_callback:
            status_callback("正在从视频中提取高保真音频...", 0.1)

        temp_dir = tempfile.gettempdir()
        temp_wav = os.path.join(temp_dir, f"song_audio_{os.getpid()}.wav")
        extract_audio(video_path, temp_wav)

        if cancel_event and cancel_event.is_set():
            raise InterruptedError("操作已被用户取消")

        if status_callback:
            status_callback(f"正在加载 Whisper AI 模型 [{model_name}]...", 0.3)

        model = get_whisper_model(model_name=model_name, device="cpu")

        if cancel_event and cancel_event.is_set():
            raise InterruptedError("操作已被用户取消")

        if status_callback:
            status_callback("正在智能识别歌词与时间轴 (AI 聆听中)...", 0.6)

        # Transcribe with Chinese language hint
        result = model.transcribe(
            temp_wav,
            language="zh",
            task="transcribe",
            temperature=0.0,
            beam_size=5,
            best_of=5,
            condition_on_previous_text=False,
            verbose=False
        )

        if cancel_event and cancel_event.is_set():
            raise InterruptedError("操作已被用户取消")

        if status_callback:
            status_callback("正在生成拼音与校验歌词结构...", 0.9)

        raw_segments = result.get("segments", [])
        formatted_segments = []

        seg_idx = 1
        for seg in raw_segments:
            text = seg.get("text", "").strip()
            # Clean Chinese text
            clean_text = clean_song_text(text, remove_punct=True)
            if not clean_text:
                continue

            start_t = round(float(seg.get("start", 0.0)), 2)
            end_t = round(float(seg.get("end", 0.0)), 2)
            if end_t <= start_t:
                end_t = round(start_t + 1.5, 2)

            py_str = convert_to_pinyin(
                clean_text,
                tone_style=pinyin_tone_style,
                case_style=pinyin_case_style
            )

            formatted_segments.append({
                "id": seg_idx,
                "start": start_t,
                "end": end_t,
                "text": clean_text,
                "pinyin": py_str
            })
            seg_idx += 1

        if status_callback:
            status_callback(f"识别完成！共生成 {len(formatted_segments)} 行拼音歌词", 1.0)

        return formatted_segments

    finally:
        if temp_wav and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass
