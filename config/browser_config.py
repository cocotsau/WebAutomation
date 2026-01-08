import sys
import os

is_windows = sys.platform == "win32"
if is_windows:
    home_dir = os.path.expanduser("~")
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.join(home_dir, "AppData", "Local"))
    appdata = os.environ.get("APPDATA", os.path.join(home_dir, "AppData", "Roaming"))
    data_dir = {
        "chrome": os.path.join(local_appdata, "Google", "Chrome", "User Data"),
        "browser360": os.path.join(appdata, "360se6", "User Data") or os.path.join(appdata, "secoresdk", "360se6", "User Data"),
        "edge": os.path.join(local_appdata, "Microsoft", "Edge", "User Data"),
        "firefox": os.path.join(appdata, "Mozilla", "Firefox", "Profiles"),
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
    edge_exe_candidates = [
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        os.path.join(local_appdata, "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    firefox_exe_candidates = [
        "C:\\Program Files\\Mozilla Firefox\\firefox.exe",
        "C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe",
        os.path.join(local_appdata, "Mozilla Firefox", "firefox.exe"),
    ]

    exe_path = {
        "chrome": _first_existing(chrome_exe_candidates) or chrome_exe_candidates[0],
        "browser360": _first_existing(browser360_exe_candidates) or browser360_exe_candidates[0],
        "edge": _first_existing(edge_exe_candidates) or edge_exe_candidates[0],
        "firefox": _first_existing(firefox_exe_candidates) or firefox_exe_candidates[0],
    }
else:
    home_dir = os.path.expanduser("~")
    data_dir = {
        "chrome": os.path.join(home_dir, "Library/Application Support/Google/Chrome"),
        "browser360": os.path.join(home_dir, "Library/Application Support/360Browser"),
        "edge": os.path.join(home_dir, "Library/Application Support/Microsoft Edge"),
        "firefox": os.path.join(home_dir, "Library/Application Support/Firefox/Profiles"),
    }
    exe_path = {
        "chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # 浏览器可执行文件
        "browser360": "/Applications/360Browser.app/Contents/MacOS/360Browser",  # 浏览器可执行文件
        "edge": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "firefox": "/Applications/Firefox.app/Contents/MacOS/firefox",
    }
