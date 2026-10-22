# -*- coding: utf-8 -*-
"""
Desktop Shortcut Creator
"""
import os
import shutil

def create_desktop_shortcut():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    vbs_target = os.path.join(script_dir, "启动(静默无黑框).vbs")
    
    ps_file = os.path.join(script_dir, "_temp_shortcut.ps1")
    temp_lnk = os.path.join(desktop, "PinyinSubtitleApp.lnk")
    final_lnk = os.path.join(desktop, "拼音歌词字幕大师.lnk")
    
    ps_content = f'''
$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut('{temp_lnk}')
$sc.TargetPath = 'wscript.exe'
$sc.Arguments = '"{vbs_target}"'
$sc.WorkingDirectory = '{script_dir}'
$sc.Description = 'Chinese Song Subtitle & Pinyin Studio'
$sc.IconLocation = 'shell32.dll,116'
$sc.Save()
'''
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(ps_content)

    os.system(f'powershell -ExecutionPolicy Bypass -File "{ps_file}" >nul 2>nul')
    if os.path.exists(ps_file):
        try:
            os.remove(ps_file)
        except Exception:
            pass

    if os.path.exists(temp_lnk):
        try:
            shutil.copy2(temp_lnk, final_lnk)
            os.remove(temp_lnk)
        except Exception:
            pass

    return os.path.exists(final_lnk)

if __name__ == "__main__":
    ok = create_desktop_shortcut()
    print("Desktop shortcut status:", ok)
