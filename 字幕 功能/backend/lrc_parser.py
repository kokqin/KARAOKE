# -*- coding: utf-8 -*-
"""
LRC & SRT Subtitle File Parser and Exporter
"""
import re
from .pinyin_engine import convert_to_pinyin, clean_song_text

def parse_lrc_file(file_path, tone_style="带声调 (wǒ hé nǐ)", case_style="全小写 (abc)"):
    """
    Parse a standard .lrc file into segment dictionaries with start, end, text, and pinyin.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    time_tag_pattern = re.compile(r"\[(\d{1,2}):(\d{1,2}(?:\.\d{1,3})?)\]")
    raw_entries = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        tags = time_tag_pattern.findall(line)
        if not tags:
            continue
            
        text = time_tag_pattern.sub("", line).strip()
        clean_text = clean_song_text(text, remove_punct=True)
        if not clean_text:
            continue

        for mm, ss in tags:
            seconds = int(mm) * 60 + float(ss)
            raw_entries.append((seconds, clean_text))

    raw_entries.sort(key=lambda x: x[0])

    segments = []
    for i, (start_sec, txt) in enumerate(raw_entries):
        if i < len(raw_entries) - 1:
            end_sec = round(raw_entries[i + 1][0], 2)
            if end_sec - start_sec > 8.0:
                end_sec = round(start_sec + 5.0, 2)
            elif end_sec <= start_sec:
                end_sec = round(start_sec + 2.0, 2)
        else:
            end_sec = round(start_sec + 4.0, 2)

        py = convert_to_pinyin(txt, tone_style=tone_style, case_style=case_style)
        segments.append({
            "id": i + 1,
            "start": round(start_sec, 2),
            "end": end_sec,
            "text": txt,
            "pinyin": py
        })

    return segments


def parse_srt_file(file_path, tone_style="带声调 (wǒ hé nǐ)", case_style="全小写 (abc)"):
    """
    Parse a standard .srt subtitle file into segment dictionaries.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip())
    segments = []

    time_pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")

    idx = 1
    for block in blocks:
        lines = [b.strip() for b in block.splitlines() if b.strip()]
        if len(lines) < 2:
            continue

        # Look for time line
        time_match = None
        text_lines = []
        for line in lines:
            m = time_pattern.search(line)
            if m:
                time_match = m
            elif time_match:
                text_lines.append(line)

        if not time_match or not text_lines:
            continue

        h1, m1, s1, ms1, h2, m2, s2, ms2 = [int(v) for v in time_match.groups()]
        start_sec = round(h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0, 2)
        end_sec = round(h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0, 2)

        text = " ".join(text_lines)
        clean_text = clean_song_text(text, remove_punct=False)
        py = convert_to_pinyin(clean_text, tone_style=tone_style, case_style=case_style)

        segments.append({
            "id": idx,
            "start": start_sec,
            "end": end_sec,
            "text": clean_text,
            "pinyin": py
        })
        idx += 1

    return segments


def export_to_srt(segments, file_path):
    """
    Export segments to .srt file with both Pinyin and Chinese characters.
    """
    def format_srt_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int(round((sec - int(sec)) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}")
        lines.append(seg.get("pinyin", ""))
        lines.append(seg.get("text", ""))
        lines.append("")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
