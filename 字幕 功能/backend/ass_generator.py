# -*- coding: utf-8 -*-
"""
ASS Subtitle Generator
Generates high-definition Advanced SubStation Alpha subtitles with Pinyin and Chinese styling.
"""
import os

def hex_to_ass_color(hex_str: str) -> str:
    """
    Convert RGB hex string like '#FFFFFF' or '#FFD700' to ASS '&H00BBGGRR&' format.
    """
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join([c * 2 for c in hex_str])
    if len(hex_str) != 6:
        return "&H00FFFFFF&"
    r = hex_str[0:2]
    g = hex_str[2:4]
    b = hex_str[4:6]
    return f"&H00{b.upper()}{g.upper()}{r.upper()}&"


def format_ass_timestamp(seconds: float) -> str:
    """
    Convert seconds float (e.g. 75.34) to ASS timestamp format 'H:MM:SS.cc'
    """
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{h:d}:{m:02d}:{s:02d}.{centis:02d}"


def generate_ass_file(
    segments,
    output_ass_path,
    res_x=1920,
    res_y=1080,
    font_name="Microsoft YaHei",
    pinyin_size=32,
    pinyin_color="#FFD700",  # Gold / Yellow
    hanzi_size=52,
    hanzi_color="#FFFFFF",   # Crisp White
    outline_width=2.5,
    outline_color="#000000",
    shadow_depth=1.0,
    margin_v=45,
    layout_mode="双行式 (上方拼音 + 下方汉字)"
):
    """
    Generate an .ass subtitle file with high fidelity styling.
    """
    pinyin_ass_color = hex_to_ass_color(pinyin_color)
    hanzi_ass_color = hex_to_ass_color(hanzi_color)
    outline_ass_color = hex_to_ass_color(outline_color)

    # Base ASS Header
    ass_lines = [
        "[Script Info]",
        "Title: Chinese Song Subtitles with Pinyin",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.601",
        f"PlayResX: {res_x}",
        f"PlayResY: {res_y}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: SongDefault,{font_name},{hanzi_size},{hanzi_ass_color},&H000000FF,{outline_ass_color},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},{shadow_depth},2,20,20,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    for seg in segments:
        start_t = format_ass_timestamp(seg.get("start", 0.0))
        end_t = format_ass_timestamp(seg.get("end", 0.0))
        hanzi = seg.get("text", "").strip()
        pinyin_text = seg.get("pinyin", "").strip()

        if not hanzi and not pinyin_text:
            continue

        if layout_mode == "双行式 (上方拼音 + 下方汉字)":
            if pinyin_text and hanzi:
                text_content = f"{{\\fs{pinyin_size}\\c{pinyin_ass_color}}}{pinyin_text}\\N{{\\r\\fs{hanzi_size}\\c{hanzi_ass_color}}}{hanzi}"
            elif hanzi:
                text_content = f"{{\\fs{hanzi_size}\\c{hanzi_ass_color}}}{hanzi}"
            else:
                text_content = f"{{\\fs{pinyin_size}\\c{pinyin_ass_color}}}{pinyin_text}"
        elif layout_mode == "行内并列式 (汉字 [拼音])":
            if pinyin_text and hanzi:
                text_content = f"{{\\fs{hanzi_size}\\c{hanzi_ass_color}}}{hanzi} {{\\fs{pinyin_size}\\c{pinyin_ass_color}}}({pinyin_text})"
            else:
                text_content = hanzi or pinyin_text
        elif layout_mode == "仅显示拼音":
            text_content = f"{{\\fs{pinyin_size}\\c{pinyin_ass_color}}}{pinyin_text}"
        else:  # 仅显示汉字
            text_content = f"{{\\fs{hanzi_size}\\c{hanzi_ass_color}}}{hanzi}"

        dialogue_line = f"Dialogue: 0,{start_t},{end_t},SongDefault,,0,0,0,,{text_content}"
        ass_lines.append(dialogue_line)

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_lines))

    return output_ass_path
