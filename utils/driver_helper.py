import sys
import subprocess
import os
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

class DriverHelper:

    @staticmethod
    def get_subprocess_chrome_args(
        port: int,
        user_data_dir: str,
        start_url: str,
        window_size: str = "1920,1080",
        headless: bool = False,
        private: bool = False) -> list:
        args = [
            f"--window-size={window_size}",
            "--window-position=0,0",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--disable-infobars",
            "--no-first-run",
            "--disable-dev-shm-usage",
            "--remote-allow-origins=*",
            "--disable-background-networking",
            "--disable-update-engine",
            "--disable-updater",
            "--log-level=3",
            "--disable-component-update",
        ]
        if headless:
            args.append("--headless")
        args.append(start_url)
        if private:
            args.append("--incognito")
        return args

    @staticmethod
    def patch_subprocess_popen():
        if sys.platform != 'win32':
            return
        if getattr(subprocess.Popen, '_is_patched_by_silent_driver', False):
            return
        _original_popen = subprocess.Popen
        class _HiddenPopen(_original_popen):
            _is_patched_by_silent_driver = True
            def __init__(self, *args, **kwargs):
                cmd_args = args[0] if args else kwargs.get('args')
                should_hide = False
                if kwargs.get('shell') is True:
                    should_hide = True
                cmd_str = str(cmd_args).lower()
                keywords = ['chromedriver', 'google-chrome', 'chrome', 'powershell', 'cmd.exe', 'reg.exe']
                if any(k in cmd_str for k in keywords):
                    should_hide = True
                if should_hide:
                    startupinfo = kwargs.get('startupinfo')
                    if not startupinfo:
                        startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    kwargs['startupinfo'] = startupinfo
                    creationflags = kwargs.get('creationflags', 0)
                    creationflags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                    kwargs['creationflags'] = creationflags
                    if 'stdin' not in kwargs:
                        kwargs['stdin'] = subprocess.DEVNULL
                    if 'stdout' not in kwargs:
                        kwargs['stdout'] = subprocess.DEVNULL
                    if 'stderr' not in kwargs:
                        kwargs['stderr'] = subprocess.DEVNULL
                super().__init__(*args, **kwargs)
        subprocess.Popen = _HiddenPopen

    @staticmethod
    def subprocess_launch_browser(executable_path: str, args: list, hide_console: bool = True):
        if hide_console:
            DriverHelper.patch_subprocess_popen()
            
        # 如果需要隐藏且是Windows，显式构造startupinfo以确保生效(即使patch未覆盖的情况)
        startupinfo = None
        creationflags = 0
        if hide_console and sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

        try:
            return subprocess.Popen(
                [executable_path, *args], 
                startupinfo=startupinfo, 
                creationflags=creationflags
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(f"启动失败，未找到可执行文件: {executable_path}") from e

    @staticmethod
    def get_chromedriver_service(local_driver_path: str, drivers_dir: str = "drivers", hide_console: bool = True) -> Service:
        """
        获取ChromeDriver Service
        :param local_driver_path: 本地驱动路径
        :param drivers_dir: 驱动下载目录
        :param hide_console: 是否隐藏控制台窗口(仅Windows生效)
        """
        def _get_service_class():
            return HiddenChromeService if (sys.platform == 'win32' and hide_console) else Service

        ServiceClass = _get_service_class()

        if os.path.exists(local_driver_path):
            try:
                return ServiceClass(executable_path=local_driver_path)
            except Exception:
                pass
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            downloaded_path = ChromeDriverManager().install()
            if not os.path.exists(drivers_dir):
                os.makedirs(drivers_dir)
            if os.path.abspath(downloaded_path) != os.path.abspath(local_driver_path):
                try:
                    shutil.copy2(downloaded_path, local_driver_path)
                except Exception:
                    pass
            return ServiceClass(executable_path=downloaded_path)
        except Exception:
            if os.path.exists(local_driver_path):
                return ServiceClass(executable_path=local_driver_path)
            raise

    @staticmethod
    def build_selenium_chrome_options(
        executable_path: str = None,
        user_data_dir: str = None,
        headless: bool = False,
        incognito: bool = False,
        window_size: str = "1920,1080",
        performance_logs: bool = False) -> webdriver.ChromeOptions:
        options = webdriver.ChromeOptions()
        if executable_path:
            options.binary_location = executable_path
        if user_data_dir:
            options.add_argument(f"--user-data-dir={user_data_dir}")
        if window_size:
            options.add_argument(f"--window-size={window_size}")
        options.add_argument("--window-position=0,0")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-allow-origins=*")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-update-engine")
        options.add_argument("--disable-updater")
        # ================恢复历史版本参数================
        # options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--disable-logging")
        options.add_argument("--silent")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        # ================恢复历史版本参数================
        options.add_argument("--log-level=3")
        options.add_argument("--disable-component-update")
        if headless:
            options.add_argument("--headless")
        if incognito:
            options.add_argument("--incognito")
        if performance_logs:
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        return options

    @staticmethod
    def selenium_launch_browser(
        local_driver_path: str,
        drivers_dir: str = "drivers",
        options: webdriver.ChromeOptions = None,
        hide_console: bool = True,) -> webdriver.Chrome:
        service = DriverHelper.get_chromedriver_service(local_driver_path, drivers_dir=drivers_dir, hide_console=hide_console)
        return webdriver.Chrome(service=service, options=options)
    
    @staticmethod
    def kill_processes(browser: str):
        is_windows = sys.platform == "win32"
        process_map = {
            "chrome": ("chrome.exe", "Google Chrome"),
            "edge": ("msedge.exe", "Microsoft Edge"),
            "firefox": ("firefox.exe", "firefox"),
            "browser360": ("360se.exe", "360浏览器"),
        }
        process_name = process_map.get(browser)
        if not process_name:
            return
        target_process = process_name[0] if is_windows else process_name[1]
        try:
            if is_windows:
                subprocess.run(['taskkill', '/F', '/IM', target_process, '/T'], timeout=10, check=True)
            else:
                subprocess.run(['pkill', '-9', '-f', target_process], timeout=10, check=True)
        except subprocess.CalledProcessError:
            pass
        except subprocess.TimeoutExpired:
            pass

class HiddenChromeService(Service):
    def __init__(self, executable_path: str, port: int = 0, service_args: list = None, log_path: str = None, env: dict = None):
        super().__init__(executable_path, port, service_args, log_path, env)
        # Explicitly set creation flags and log output for the service instance
        if sys.platform == 'win32':
            self.creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
        self.log_output = subprocess.DEVNULL