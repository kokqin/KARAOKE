# -*- coding: utf-8 -*-
"""
Pinyin Engine for Chinese Song Subtitles
Converts Chinese text to Pinyin with various styles and alignments.
"""
import re
import pypinyin
from pypinyin import pinyin, Style

CHINESE_PUNCTUATION = "，。！？、；：“”‘’（）《》〈〉【】…—～·"
ENGLISH_PUNCTUATION = ",.!?;:'\"()[]<>-~"
ALL_PUNCTUATION = set(CHINESE_PUNCTUATION + ENGLISH_PUNCTUATION)

STYLE_CHOICES = {
    "带声调 (wǒ hé nǐ)": Style.TONE,
    "数字声调 (wo3 he2 ni3)": Style.TONE2,
    "无声调 (wo he ni)": Style.NORMAL,
}

CASE_CHOICES = ["全小写 (abc)", "首字母大写 (Abc)", "全大写 (ABC)"]

def clean_song_text(text: str, remove_punct: bool = True) -> str:
    """
    Clean lyrics text for singing display: remove extra whitespace and optionally punctuation.
    """
    text = text.strip()
    if remove_punct:
        chars = [c for c in text if c not in ALL_PUNCTUATION]
        text = "".join(chars)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text

def convert_to_pinyin(
    text: str,
    tone_style: str = "带声调 (wǒ hé nǐ)",
    case_style: str = "全小写 (abc)",
    remove_punct: bool = True,
    heteronym: bool = False
) -> str:
    """
    Convert a line of Chinese text to formatted Pinyin string.
    """
    if not text or not text.strip():
        return ""

    style = STYLE_CHOICES.get(tone_style, Style.TONE)
    
    # Process Chinese text into pinyin items
    pinyin_list = pinyin(text, style=style, heteronym=heteronym, errors="default")
    
    formatted_words = []
    for item in pinyin_list:
        raw_word = item[0] if item else ""
        if not raw_word:
            continue
            
        # Skip punctuation if requested
        if remove_punct and raw_word in ALL_PUNCTUATION:
            continue
            
        w = raw_word.strip()
        if not w:
            continue

        # Case formatting
        if case_style == "首字母大写 (Abc)":
            w = w.capitalize()
        elif case_style == "全大写 (ABC)":
            w = w.upper()
        else:
            w = w.lower()

        formatted_words.append(w)

    return " ".join(formatted_words)

def generate_aligned_ruby_pairs(text: str, tone_style: str = "带声调 (wǒ hé nǐ)"):
    """
    Generate list of (char, pinyin) pairs for word-aligned or ruby rendering.
    """
    style = STYLE_CHOICES.get(tone_style, Style.TONE)
    pinyin_list = pinyin(text, style=style, heteronym=False, errors="default")
    
    pairs = []
    for char, py_item in zip(text, pinyin_list):
        py = py_item[0] if py_item else ""
        if char in ALL_PUNCTUATION:
            pairs.append((char, ""))
        else:
            pairs.append((char, py))
    return pairs
