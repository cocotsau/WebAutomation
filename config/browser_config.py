import sys
import os

debug_port = {
    "chrome": 9222,
    "browser360": 9223,
}
is_windows = sys.platform == "win32"
if is_windows:
    home_dir = os.path.expanduser("~")
    file_dir = os.path.join(home_dir, "Downloads")
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.join(home_dir, "AppData", "Local"))
    appdata = os.environ.get("APPDATA", os.path.join(home_dir, "AppData", "Roaming"))
    data_dir = {
        "chrome": os.path.join(local_appdata, "Google", "Chrome", "User Data"),
        "browser360": os.path.join(appdata, "360se6", "User Data") or os.path.join(appdata, "secoresdk", "360se6", "User Data"),
    }
    def _first_existing(paths):
        for p in paths:
            if os.path.exists(p):
                return p
        return None
    chrome_exe_candidates = [
        os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe"),
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    ]
    browser360_exe_candidates = [
        os.path.join(appdata, "360se6", "Application", "360se.exe"),
        os.path.join(appdata, "secoresdk", "360se6", "Application", "360se.exe"),
        "C:\\Program Files\\360\\360se6\\Application\\360se.exe",
        "C:\\Program Files (x86)\\360\\360se6\\Application\\360se.exe",
    ]
    exe_path = {
        "chrome": _first_existing(chrome_exe_candidates) or chrome_exe_candidates[0],
        "browser360": _first_existing(browser360_exe_candidates) or browser360_exe_candidates[0],
    }
else:
    file_dir = "/Users/allentsau/Downloads"
    data_dir = {
        "chrome": "/Users/allentsau/Library/Application Support/Google/Chrome",  # 用户数据目录（缓存/配置）
        "browser360": "/Users/allentsau/Library/Application Support/360Browser",  # 用户数据目录（缓存/配置）
    }
    exe_path = {
        "chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # 浏览器可执行文件
        "browser360": "/Applications/360Browser.app/Contents/MacOS/360Browser",  # 浏览器可执行文件
    }
