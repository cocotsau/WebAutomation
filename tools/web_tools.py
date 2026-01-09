import json
from typing import Dict, Any, List
from core.action_base import ActionBase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import os
import shutil

# Add project root to path to import web.py
sys.path.append(os.getcwd())

try:
    from config import browser_config
except ImportError:
    browser_config = None

try:
    from utils.web import Web
except ImportError:
    try:
        from web import Web
    except ImportError:
        pass


def _map_by(by: str):
    s = (by or "").strip().lower()
    mapping = {
        "xpath": By.XPATH,
        "css": By.CSS_SELECTOR,
        "css_selector": By.CSS_SELECTOR,
        "id": By.ID,
        "name": By.NAME,
        "class": By.CLASS_NAME,
        "class_name": By.CLASS_NAME,
        "tag": By.TAG_NAME,
        "tag_name": By.TAG_NAME,
        "link_text": By.LINK_TEXT,
        "partial_link_text": By.PARTIAL_LINK_TEXT,
    }
    return mapping.get(s, By.XPATH)


def _resolve_locator_from_element_library(context: Dict[str, Any], element_key: str):
    try:
        if isinstance(element_key, str):
            element_key = element_key.format(**context)
    except Exception:
        pass

    # 1. Try private manager from context
    private_mgr = context.get("element_manager_private")
    if private_mgr:
        locator = private_mgr.get_locator(element_key)
        if locator:
            return locator

    # 2. Try global manager from context
    global_mgr = context.get("element_manager_global")
    if global_mgr:
        locator = global_mgr.get_locator(element_key)
        if locator:
            return locator

    # 3. Fallback to default ElementManager (legacy)
    try:
        from core.element_manager import ElementManager
        mgr = ElementManager()
        locator = mgr.get_locator(element_key)
        if locator:
            return locator
    except Exception:
        pass

    return None

class OpenBrowserAction(ActionBase):
    @property
    def name(self) -> str:
        return "打开浏览器"

    @property
    def description(self) -> str:
        return "Open a browser (Chrome/360) and load a URL"

    def execute(self, context: Dict[str, Any]) -> bool:
        launch_mode = self.params.get("launch_mode", "selenium")
        browser_type = self.params.get("browser_type", "chrome")
        url = self.params.get("url")
        headless = self.params.get("headless", False)
        incognito = self.params.get("incognito", False)
        kill_process = self.params.get("kill_process", False)
        window_size = self.params.get("window_size", "1920,1080")
        output_var = self.params.get("output_variable", "driver")
        
        chrome_path = self.params.get("chrome_path", "")
        user_data_dir = self.params.get("user_data_dir", "")
        use_local_profile = self.params.get("use_local_profile", False)
        debug_port = int(self.params.get("debug_port", 0))
        
        try:
            from utils.driver_helper import DriverHelper
        except ImportError:
            print("[WEB]: DriverHelper not found. Please ensure utils/driver_helper.py exists.")
            return False

        # Use browser_config to resolve paths if not provided
        if browser_config:
            if not chrome_path:
                chrome_path = browser_config.exe_path.get(browser_type, "")
            if not user_data_dir and use_local_profile:
                user_data_dir = browser_config.data_dir.get(browser_type, "")

        # Kill existing process if requested
        if kill_process:
            print(f"[WEB]: Killing existing {browser_type} processes...")
            DriverHelper.kill_processes(browser_type)

        drivers_dir = os.path.join(os.getcwd(), "drivers")
        chromedriver_name = "chromedriver.exe" if sys.platform == "win32" else "chromedriver"
        local_driver_path = os.path.join(drivers_dir, chromedriver_name)

        def get_service():
            try:
                return DriverHelper.get_chromedriver_service(local_driver_path, drivers_dir)
            except Exception as e:
                print(f"[WEB]: Failed to get chromedriver service: {e}")
                return Service()

        try:
            if launch_mode == "subprocess":
                # Find free port if not specified
                if debug_port == 0:
                    import socket
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('', 0))
                        debug_port = s.getsockname()[1]

                # Launch via subprocess
                args = DriverHelper.get_subprocess_chrome_args(
                    port=debug_port,
                    user_data_dir=user_data_dir,
                    start_url=url if url else "about:blank",
                    headless=headless,
                    window_size=window_size,
                    private=incognito
                )
                
                print(f"[WEB]: Launching subprocess: {chrome_path}")
                DriverHelper.subprocess_launch_browser(chrome_path, args)
                
                # Connect via Selenium
                options = webdriver.ChromeOptions()
                options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
                
                service = get_service()
                driver = webdriver.Chrome(service=service, options=options)
                
            else:
                if browser_type.lower() in ["chrome", "browser360"]:
                    options = DriverHelper.build_selenium_chrome_options(
                        executable_path=chrome_path,
                        user_data_dir=user_data_dir,
                        headless=headless,
                        incognito=incognito,
                        window_size=window_size
                    )
                    options.add_experimental_option("detach", True)
                    
                    driver = DriverHelper.selenium_launch_browser(
                        local_driver_path=local_driver_path,
                        drivers_dir=drivers_dir,
                        options=options
                    )
                    
                    if url:
                        driver.get(url)
                elif browser_type.lower() == "edge":
                    opts = EdgeOptions()
                    if headless:
                        opts.add_argument("--headless=new")
                    if incognito:
                        opts.add_argument("--inprivate")
                    if user_data_dir:
                        opts.add_argument(f"--user-data-dir={user_data_dir}")
                    service = EdgeService(EdgeChromiumDriverManager().install())
                    driver = webdriver.Edge(service=service, options=opts)
                    if window_size:
                        try:
                            w, h = window_size.split(",")
                            driver.set_window_size(int(w), int(h))
                        except:
                            pass
                    if url:
                        driver.get(url)
                elif browser_type.lower() == "firefox":
                    opts = FirefoxOptions()
                    if headless:
                        opts.add_argument("-headless")
                    if incognito:
                        opts.add_argument("-private")
                    if user_data_dir:
                        opts.add_argument(f"-profile")
                        opts.add_argument(user_data_dir)
                    service = FirefoxService(GeckoDriverManager().install())
                    driver = webdriver.Firefox(service=service, options=opts)
                    if window_size:
                        try:
                            w, h = window_size.split(",")
                            driver.set_window_size(int(w), int(h))
                        except:
                            pass
                    if url:
                        driver.get(url)
                else:
                    print(f"[WEB]: Unsupported browser_type for selenium: {browser_type}")
                    return False

            context["driver"] = driver
            context[output_var] = driver
            print(f"[WEB]: Browser opened in {launch_mode} mode.")
            return True
            
        except Exception as e:
            print(f"[WEB]: Failed to open browser: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        default_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        default_data = ""
        default_port = 0
        if browser_config:
            default_exe = browser_config.exe_path.get("chrome", default_exe)
            # default_data = browser_config.data_dir.get("chrome", default_data)
            # default_port = browser_config.debug_port.get("chrome", default_port)
        return [
            {"name": "launch_mode", "type": "str", "label": "启动模式", "default": "selenium", "options": ["selenium", "subprocess"]},
            {"name": "browser_type", "type": "str", "label": "浏览器类型", "default": "chrome", "options": ["chrome", "browser360", "edge", "firefox"]},
            {"name": "output_variable", "type": "str", "label": "输出变量名", "default": "", "variable_type": "网页对象", "is_variable": True},
            {"name": "url", "type": "str", "label": "初始URL", "default": "https://"},
            {"name": "kill_process", "type": "bool", "label": "结束同类进程", "default": False},
            {"name": "debug_port", "type": "int", "label": "调试端口", "default": default_port, "advanced": True, "enable_if": {"kill_process": True}},
            {"name": "incognito", "type": "bool", "label": "隐私模式", "default": False, "advanced": True},
            {"name": "headless", "type": "bool", "label": "无头模式", "default": False, "advanced": True},
            {"name": "window_size", "type": "str", "label": "窗口大小", "default": "1920,1080", "advanced": True},
            {"name": "chrome_path", "type": "str", "label": "浏览器路径", "default": default_exe, "advanced": True, "ui_options": {"browse_type": "file", "file_filter": "Executables (*.exe)"}},
            {"name": "use_local_profile", "type": "bool", "label": "默认用户数据", "default": False, "advanced": True, "description": "勾选后将尝试使用本机安装的浏览器配置文件（需先关闭浏览器）"},
            {"name": "user_data_dir", "type": "str", "label": "用户数据目录", "default": default_data, "advanced": True, "placeholder": "留空则使用临时目录", "ui_options": {"browse_type": "directory"}},
        ]

class CloseBrowserAction(ActionBase):
    @property
    def name(self) -> str:
        return "关闭浏览器"

    @property
    def description(self) -> str:
        return "Closes the browser."

    def execute(self, context: Dict[str, Any]) -> bool:
        driver_var = self.params.get("driver_variable", "")
        browser_type = self.params.get("browser_type", "")
        kill_process = self.params.get("kill_process", False)
        
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
            
        driver = context.get(d_var_name) or context.get("driver")
        if driver:
            try:
                driver.quit()
                if d_var_name in context:
                    del context[d_var_name]
                if "driver" in context and context["driver"] is driver:
                    del context["driver"]
                print(f"[WEB]: Browser closed (variable: {d_var_name}).")
            except Exception as e:
                print(f"[WEB]: Error closing browser: {e}")
        else:
            print(f"[WEB]: No browser found to close (variable: {d_var_name}).")
        if kill_process and browser_type:
            try:
                from utils.driver_helper import DriverHelper
                DriverHelper.kill_processes(browser_type)
                print(f"[WEB]: Killed existing {browser_type} processes.")
            except Exception as e:
                print(f"[WEB]: Error killing processes: {e}")
        return True
        
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "browser_type", "type": "str", "label": "浏览器类型", "default": "chrome", "options": ["chrome", "browser360", "edge", "firefox"]},
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True},
            {"name": "kill_process", "type": "bool", "label": "终止浏览器进程", "default": False, "advanced": True}
        ]

class ClickElementAction(ActionBase):
    @property
    def name(self) -> str:
        return "点击元素"

    @property
    def description(self) -> str:
        return "Clicks an element identified by XPath or CSS Selector."

    def execute(self, context: Dict[str, Any]) -> bool:
        locator_source = self.params.get("locator_source", "手动")
        
        # 1. 直接处理网页元素变量
        if locator_source == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            element = context.get(var_name)
            if not element:
                print(f"[WEB]: Web element variable '{element_var}' (resolved as '{var_name}') not found.")
                return False
            try:
                try:
                    element.click()
                except Exception as click_err:
                    # Fallback to JS click if possible
                    driver_var = self.params.get("driver_variable", "")
                    # 处理驱动变量名
                    d_var_name = driver_var
                    if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
                        d_var_name = d_var_name[1:-1]
                    
                    driver = context.get(d_var_name) or context.get("driver")
                    if driver:
                        print(f"[WEB]: Standard click failed for dynamic element, trying JS click: {click_err}")
                        driver.execute_script("arguments[0].click();", element)
                    else:
                        raise click_err
                
                print(f"[WEB]: Clicked dynamic element from variable '{element_var}'")
                return True
            except Exception as e:
                print(f"[WEB]: Failed to click dynamic element: {e}")
                return False

        # 2. 原有的定位逻辑
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
        
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
            
        element_key = self.params.get("element_key", "")
        by = self.params.get("by", "xpath")
        value = self.params.get("value")

        if locator_source == "元素库" and element_key:
            resolved = _resolve_locator_from_element_library(context, element_key)
            if not resolved:
                print(f"[WEB]: Element not found in library: {element_key}")
                return False
            by, value = resolved
        else:
            try:
                if isinstance(value, str):
                    value = value.format(**context)
            except:
                pass

        timeout = int(self.params.get("timeout", 20))
        locator_type = _map_by(by)
        
        try:
            if 'Web' in globals():
                Web.wait_element_clickable(driver, (locator_type, value), timeout).click()
            else:
                WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((locator_type, value))).click()
                
            print(f"[WEB]: Clicked element {by}={value}")
            return True
        except Exception as e:
            print(f"[WEB]: Failed to click element: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True, "enable_if": {"locator_source": ["手动", "元素库", "网页元素"]}},
            {"name": "locator_source", "type": "str", "label": "定位来源", "default": "手动", "options": ["手动", "元素库", "网页元素"]},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"locator_source": "网页元素"}},
            {"name": "element_key", "type": "str", "label": "元素库 Key", "default": "", "enable_if": {"locator_source": "元素库"}, "ui_options": {"element_picker": True}},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"], "enable_if": {"locator_source": "手动"}},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "enable_if": {"locator_source": "手动"}},
            {"name": "timeout", "type": "int", "label": "超时时间(秒)", "default": 20, "advanced": True, "enable_if": {"locator_source": ["手动", "元素库"]}}
        ]

class InputTextAction(ActionBase):
    @property
    def name(self) -> str:
        return "输入文本"

    @property
    def description(self) -> str:
        return "Inputs text into an element."

    def execute(self, context: Dict[str, Any]) -> bool:
        locator_source = self.params.get("locator_source", "手动")
        text = self.params.get("text", "")
        clear_first = self.params.get("clear_first", True)
        
        try:
            text = text.format(**context)
        except:
            pass

        element = None
        
        # 1. 直接处理网页元素变量
        if locator_source == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            element = context.get(var_name)
            if not element:
                print(f"[WEB]: Web element variable '{element_var}' (resolved as '{var_name}') not found.")
                return False
        else:
            # 2. 原有的定位逻辑
            driver_var = self.params.get("driver_variable", "")
            # 处理驱动变量名
            d_var_name = driver_var
            if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
                d_var_name = d_var_name[1:-1]
            
            driver = context.get(d_var_name) or context.get("driver")
            if not driver:
                print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
                return False
                
            element_key = self.params.get("element_key", "")
            by = self.params.get("by", "xpath")
            value = self.params.get("value")

            if locator_source == "元素库" and element_key:
                resolved = _resolve_locator_from_element_library(context, element_key)
                if not resolved:
                    print(f"[WEB]: Element not found in library: {element_key}")
                    return False
                by, value = resolved
            else:
                try:
                    if isinstance(value, str):
                        value = value.format(**context)
                except:
                    pass
                
            timeout = int(self.params.get("timeout", 20))
            locator_type = _map_by(by)
            
            try:
                if 'Web' in globals():
                    element = Web.wait_element_visible(driver, (locator_type, value), timeout)
                else:
                    element = WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((locator_type, value)))
            except Exception as e:
                print(f"[WEB]: Failed to find element: {e}")
                return False

        # 3. 执行输入操作
        try:
            if clear_first:
                element.clear()
            element.send_keys(text)
            print(f"[WEB]: Inputted text into element")
            return True
        except Exception as e:
            print(f"[WEB]: Failed to input text: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True, "enable_if": {"locator_source": ["手动", "元素库", "网页元素"]}},
            {"name": "locator_source", "type": "str", "label": "定位来源", "default": "手动", "options": ["手动", "元素库", "网页元素"]},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"locator_source": "网页元素"}},
            {"name": "element_key", "type": "str", "label": "元素库 Key", "default": "", "enable_if": {"locator_source": "元素库"}, "ui_options": {"element_picker": True}},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"], "enable_if": {"locator_source": "手动"}},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "enable_if": {"locator_source": "手动"}},
            {"name": "text", "type": "str", "label": "输入文本", "default": ""},
            {"name": "clear_first", "type": "bool", "label": "输入前清空", "default": True, "advanced": True},
            {"name": "timeout", "type": "int", "label": "超时时间(秒)", "default": 20, "advanced": True, "enable_if": {"locator_source": ["手动", "元素库"]}}
        ]

class GoToUrlAction(ActionBase):
    @property
    def name(self) -> str:
        return "访问网页"

    @property
    def description(self) -> str:
        return "Navigates the browser to a specific URL."

    def execute(self, context: Dict[str, Any]) -> bool:
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
            
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
            
        url = self.params.get("url", "")
        try:
            url = url.format(**context)
        except:
            pass
            
        if not url:
            return False
            
        try:
            driver.get(url)
            print(f"[WEB]: Navigated to {url}")
            return True
        except Exception as e:
            print(f"[WEB]: Navigation failed: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True},
            {"name": "url", "type": "str", "label": "链接地址", "default": "https://"}
        ]

class HttpDownloadAction(ActionBase):
    @property
    def name(self) -> str:
        return "HTTP 下载"

    @property
    def description(self) -> str:
        return "Downloads a file from a URL via HTTP."

    def execute(self, context: Dict[str, Any]) -> bool:
        url = self.params.get("url")
        save_path = self.params.get("save_path")
        timeout = int(self.params.get("timeout", 120))
        use_browser_cookies = self.params.get("use_browser_cookies", True)
        driver_var = self.params.get("driver_variable", "")
        
        try:
            url = url.format(**context)
            save_path = save_path.format(**context)
        except:
            pass
            
        try:
            from utils.web import Web
            # 处理驱动变量名
            d_var_name = driver_var
            if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
                d_var_name = d_var_name[1:-1]
                
            driver = (context.get(d_var_name) or context.get("driver")) if use_browser_cookies else None
            return Web.http_download(url, save_path, driver=driver, timeout=timeout)
        except Exception as e:
            print(f"[WEB]: Download failed: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "url", "type": "str", "label": "下载链接", "default": ""},
            {"name": "save_path", "type": "str", "label": "保存路径", "default": "downloaded_file.ext"},
            {"name": "use_browser_cookies", "type": "bool", "label": "使用浏览器 Cookies", "default": True, "advanced": True},
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True, "advanced": True, "enable_if": {"use_browser_cookies": True}},
            {"name": "timeout", "type": "int", "label": "超时时间(秒)", "default": 120, "advanced": True}
        ]

class GetElementInfoAction(ActionBase):
    @property
    def name(self) -> str:
        return "获取元素信息"

    @property
    def description(self) -> str:
        return "Gets the text or attribute of an element and saves it to a variable."

    def execute(self, context: Dict[str, Any]) -> bool:
        locator_source = self.params.get("locator_source", "手动")
        attr_name = self.params.get("attribute_name", "text")
        output_var = self.params.get("output_variable", "text_output")
        
        element = None
        
        # 1. 直接处理网页元素变量
        if locator_source == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            element = context.get(var_name)
            if not element:
                print(f"[WEB]: Web element variable '{element_var}' (resolved as '{var_name}') not found.")
                return False
        else:
            # 2. 原有的定位逻辑
            driver_var = self.params.get("driver_variable", "")
            # 处理驱动变量名
            d_var_name = driver_var
            if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
                d_var_name = d_var_name[1:-1]
            
            driver = context.get(d_var_name) or context.get("driver")
            if not driver:
                print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
                return False
                
            element_key = self.params.get("element_key", "")
            by = self.params.get("by", "xpath")
            value = self.params.get("value")

            if locator_source == "元素库" and element_key:
                resolved = _resolve_locator_from_element_library(context, element_key)
                if not resolved:
                    print(f"[WEB]: Element not found in library: {element_key}")
                    return False
                by, value = resolved
            else:
                try:
                    if isinstance(value, str):
                        value = value.format(**context)
                except:
                    pass
                
            timeout = int(self.params.get("timeout", 20))
            locator_type = _map_by(by)
            
            try:
                if 'Web' in globals():
                    element = Web.wait_element_visible(driver, (locator_type, value), timeout)
                else:
                    element = WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((locator_type, value)))
            except Exception as e:
                print(f"[WEB]: Failed to find element: {e}")
                return False

        # 3. 执行获取信息操作
        try:
            if attr_name == "text":
                result = element.text
            else:
                result = element.get_attribute(attr_name)

            context[output_var] = result
            logging_info = f"[WEB]: Got {attr_name} '{result}', saved to {output_var}"
            if logging_info and len(logging_info) > 100:
                logging_info = logging_info[:100] + "\n...（日志信息过长，已截断）"
            print(logging_info)
            return True
        except Exception as e:
            print(f"[WEB]: Failed to get {attr_name}: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True, "enable_if": {"locator_source": ["手动", "元素库", "网页元素"]}},
            {"name": "locator_source", "type": "str", "label": "定位来源", "default": "手动", "options": ["手动", "元素库", "网页元素"]},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"locator_source": "网页元素"}},
            {"name": "element_key", "type": "str", "label": "元素库 Key", "default": "", "enable_if": {"locator_source": "元素库"}, "ui_options": {"element_picker": True}},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"], "enable_if": {"locator_source": "手动"}},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "enable_if": {"locator_source": "手动"}},
            {"name": "attribute_name", "type": "str", "label": "属性名称", "default": "text", "options": ["text", "textContent", "innerHTML", "outerHTML", "value", "src", "href", "className", "id", "name"]},
            {"name": "output_variable", "type": "str", "label": "输出变量名", "default": "text_output", "variable_type": "一般变量", "is_variable": True},
            {"name": "timeout", "type": "int", "label": "超时时间(秒)", "default": 20, "advanced": True, "enable_if": {"locator_source": ["手动", "元素库"]}}
        ]

class SetCheckboxAction(ActionBase):
    @property
    def name(self) -> str:
        return "设置复选框"

    @property
    def description(self) -> str:
        return "设置复选框或单选框的状态（勾选、取消勾选或反选）。"

    def execute(self, context: Dict[str, Any]) -> bool:
        locator_source = self.params.get("locator_source", "手动")
        action_type = self.params.get("action_type", "勾选")
        timeout = int(self.params.get("timeout", 20))

        # 1. 直接处理网页元素变量
        if locator_source == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            element = context.get(var_name)
            if not element:
                print(f"[WEB]: Web element variable '{element_var}' (resolved as '{var_name}') not found.")
                return False
            
            driver_var = self.params.get("driver_variable", "")
            # 处理驱动变量名
            d_var_name = driver_var
            if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
                d_var_name = d_var_name[1:-1]
            
            driver = context.get(d_var_name) or context.get("driver")
            if not driver:
                print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found in context (needed for JS click fallback).")
                return False
                
            try:
                is_selected = element.is_selected()
                target_state = is_selected
                
                if action_type == "勾选":
                    target_state = True
                elif action_type == "取消勾选":
                    target_state = False
                elif action_type == "反选":
                    target_state = not is_selected
                
                if is_selected != target_state:
                    try:
                        element.click()
                    except Exception as click_err:
                        print(f"[WEB]: Standard click failed for dynamic element, trying JS click: {click_err}")
                        driver.execute_script("arguments[0].click();", element)
                    
                    print(f"[WEB]: Dynamic element checkbox state changed from {is_selected} to {target_state}")
                else:
                    print(f"[WEB]: Dynamic element checkbox already in state {target_state}")
                return True
            except Exception as e:
                print(f"[WEB]: Failed to set dynamic element checkbox: {e}")
                return False

        # 2. 原有的定位逻辑
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
        
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False

        element_key = self.params.get("element_key", "")
        by = self.params.get("by", "xpath")
        value = self.params.get("value")

        if locator_source == "元素库" and element_key:
            resolved = _resolve_locator_from_element_library(context, element_key)
            if not resolved:
                print(f"[WEB]: Element not found in library: {element_key}")
                return False
            by, value = resolved
        
        try:
            if isinstance(value, str):
                value = value.format(**context)
        except:
            pass

        locator_type = _map_by(by)
        
        try:
            if 'Web' in globals():
                # 使用 wait_element_located 而不是 wait_element_visible
                # 因为 Ant Design 等框架的 checkbox input 往往是隐藏 (opacity: 0)
                element = Web.wait_element_located(driver, (locator_type, value), timeout)
            else:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((locator_type, value)))
            
            is_selected = element.is_selected()
            target_state = is_selected
            
            if action_type == "勾选":
                target_state = True
            elif action_type == "取消勾选":
                target_state = False
            elif action_type == "反选":
                target_state = not is_selected
            
            if is_selected != target_state:
                try:
                    element.click()
                except Exception as click_err:
                    # 如果常规点击失败（通常因为元素被遮挡或不可见），尝试使用 JS 点击
                    print(f"[WEB]: Standard click failed, trying JS click: {click_err}")
                    driver.execute_script("arguments[0].click();", element)
                
                print(f"[WEB]: Checkbox state changed from {is_selected} to {target_state} for {value}")
            else:
                print(f"[WEB]: Checkbox already in state {target_state} for {value}")
            
            return True
        except Exception as e:
            print(f"[WEB]: Failed to set checkbox: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True, "enable_if": {"locator_source": ["手动", "元素库", "网页元素"]}},
            {"name": "locator_source", "type": "str", "label": "定位来源", "default": "手动", "options": ["手动", "元素库", "网页元素"]},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"locator_source": "网页元素"}},
            {"name": "element_key", "type": "str", "label": "元素库 Key", "default": "", "enable_if": {"locator_source": "元素库"}, "ui_options": {"element_picker": True}},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"], "enable_if": {"locator_source": "手动"}},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "enable_if": {"locator_source": "手动"}},
            {"name": "action_type", "type": "str", "label": "动作类型", "default": "勾选", "options": ["勾选", "取消勾选", "反选"]},
            {"name": "timeout", "type": "int", "label": "超时时间(秒)", "default": 20, "advanced": True, "enable_if": {"locator_source": ["手动", "元素库"]}}
        ]


class SaveElementAction(ActionBase):
    @property
    def name(self) -> str:
        return "Save Element"

    @property
    def description(self) -> str:
        return "Saves an element locator into element library."

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "group", "type": "str", "label": "分组", "default": "Default", "ui_options": {"element_group_picker": True}},
            {"name": "name", "type": "str", "label": "元素名称", "default": ""},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"]},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "ui_options": {"element_picker": True}},
            {"name": "description", "type": "str", "label": "备注", "default": "", "advanced": True},
            {"name": "overwrite", "type": "bool", "label": "允许覆盖同名元素", "default": True, "advanced": True},
        ]

    def execute(self, context: Dict[str, Any]) -> bool:
        group = self.params.get("group", "Default")
        name = self.params.get("name", "")
        by = self.params.get("by", "xpath")
        value = self.params.get("value", "")
        description = self.params.get("description", "")
        overwrite = bool(self.params.get("overwrite", True))

        try:
            if isinstance(group, str):
                group = group.format(**context)
            if isinstance(name, str):
                name = name.format(**context)
            if isinstance(by, str):
                by = by.format(**context)
            if isinstance(value, str):
                value = value.format(**context)
            if isinstance(description, str):
                description = description.format(**context)
        except Exception:
            pass

        group = (group or "Default").strip()
        name = (name or "").strip()
        by = (by or "").strip()
        value = (value or "").strip()

        if not name or not by or not value:
            print("[WEB]: Save element failed: group/name/by/value required.")
            return False

        try:
            # 1. Try private manager from context (Preferred)
            mgr = context.get("element_manager_private")
            
            # 2. Try global manager if private not available
            if not mgr:
                mgr = context.get("element_manager_global")
            
            # 3. Fallback to default (legacy/standalone mode)
            if not mgr:
                from core.element_manager import ElementManager
                mgr = ElementManager("elements.json") # Default global file
                print("[WEB]: Warning: Using default global elements.json (Context managers not found)")

            existing = mgr.list_elements()
            if not overwrite:
                if isinstance(existing, dict) and isinstance(existing.get(group), dict) and name in existing[group]:
                    print(f"[WEB]: Element already exists: {group}/{name}")
                    return False

            meta = {"description": description} if description else None
            ok = mgr.save_element(group=group, name=name, by=by, value=value, meta=meta)
            if ok:
                print(f"[WEB]: Element saved: {group}/{name}")
                return True
            print("[WEB]: Save element failed.")
            return False
        except Exception as e:
            print(f"[WEB]: Save element failed: {e}")
            return False

class HoverElementAction(ActionBase):
    @property
    def name(self) -> str:
        return "悬停元素"
    
    @property
    def description(self) -> str:
        return "Moves mouse over an element."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        locator_source = self.params.get("locator_source", "手动")
        offset_x = int(self.params.get("offset_x", 0))
        offset_y = int(self.params.get("offset_y", 0))
        
        # 1. 直接处理网页元素变量
        if locator_source == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            element = context.get(var_name)
            if not element:
                print(f"[WEB]: Web element variable '{element_var}' (resolved as '{var_name}') not found.")
                return False
            
            driver_var = self.params.get("driver_variable", "")
            # 处理驱动变量名
            d_var_name = driver_var
            if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
                d_var_name = d_var_name[1:-1]
            
            driver = context.get(d_var_name) or context.get("driver")
            if not driver:
                print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found in context (needed for hover).")
                return False
                
            try:
                if 'Web' in globals():
                    Web.element_hover(driver, element, offset_x=offset_x, offset_y=offset_y)
                    print(f"[WEB]: Hovered on dynamic element from variable '{element_var}'")
                    return True
                else:
                    print("[WEB]: Web util not available for dynamic element hover")
                    return False
            except Exception as e:
                print(f"[WEB]: Failed to hover dynamic element: {e}")
                return False

        # 2. 原有的定位逻辑
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
        
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
        
        element_key = self.params.get("element_key", "")
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        
        if locator_source == "元素库" and element_key:
            resolved = _resolve_locator_from_element_library(context, element_key)
            if not resolved:
                print(f"[WEB]: Element not found in library: {element_key}")
                return False
            by, value = resolved
        
        try:
            if isinstance(value, str):
                value = value.format(**context)
        except:
            pass
        timeout = int(self.params.get("timeout", 20))
        
        locator_type = _map_by(by)
        
        try:
            if 'Web' in globals():
                element = Web.wait_element_visible(driver, (locator_type, value), timeout)
                Web.element_hover(driver, element, offset_x=offset_x, offset_y=offset_y)
            else:
                print("[WEB]: Web util not available")
                return False
            return True
        except Exception as e:
            print(f"[WEB]: Failed to hover: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True, "enable_if": {"locator_source": ["手动", "元素库", "网页元素"]}},
            {"name": "locator_source", "type": "str", "label": "定位来源", "default": "手动", "options": ["手动", "元素库", "网页元素"]},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"locator_source": "网页元素"}},
            {"name": "element_key", "type": "str", "label": "元素库 Key", "default": "", "enable_if": {"locator_source": "元素库"}, "ui_options": {"element_picker": True}},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"], "enable_if": {"locator_source": "手动"}},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "enable_if": {"locator_source": "手动"}},
            {"name": "offset_x", "type": "int", "label": "水平偏移(px)", "default": 0, "advanced": True, "description": "相对于元素中心点的水平偏移量"},
            {"name": "offset_y", "type": "int", "label": "垂直偏移(px)", "default": 0, "advanced": True, "description": "相对于元素中心点的垂直偏移量"},
            {"name": "timeout", "type": "int", "label": "超时时间(秒)", "default": 20, "advanced": True, "enable_if": {"locator_source": ["手动", "元素库"]}}
        ]

class SwitchFrameAction(ActionBase):
    @property
    def name(self) -> str:
        return "切换 IFrame"
        
    @property
    def description(self) -> str:
        return "Switch to an iframe by ID (or default content if empty)."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
        
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
        
        switch_type = self.params.get("switch_type", "ID/Name")
        
        target = None
        if switch_type == "ID/Name":
            target = self.params.get("iframe_id", "")
            try:
                if isinstance(target, str):
                    target = target.format(**context)
            except:
                pass
        elif switch_type == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            target = context.get(var_name)
            if not target:
                print(f"[WEB]: Web element variable '{element_var}' (resolved as '{var_name}') not found.")
                return False

        try:
            if 'Web' in globals():
                # Web.switch_frame should handle both str (ID/Name) and WebElement
                Web.switch_frame(driver, target if target else None)
            else:
                if not target:
                    driver.switch_to.default_content()
                else:
                    driver.switch_to.frame(target)
            return True
        except Exception as e:
            print(f"[WEB]: Failed to switch frame: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True},
            {"name": "switch_type", "type": "str", "label": "切换方式", "default": "ID/Name", "options": ["ID/Name", "网页元素"]},
            {"name": "iframe_id", "type": "str", "label": "IFrame ID/Name(空则默认)", "default": "", "enable_if": {"switch_type": "ID/Name"}},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"switch_type": "网页元素"}}
        ]

class ScrollToElementAction(ActionBase):
    @property
    def name(self) -> str:
        return "滚动到元素"
        
    @property
    def description(self) -> str:
        return "Scrolls element into view."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        locator_source = self.params.get("locator_source", "手动")
        
        # 1. 直接处理网页元素变量
        if locator_source == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            element = context.get(var_name)
            if not element:
                print(f"[WEB]: Web element variable '{element_var}' (resolved as '{var_name}') not found.")
                return False
            
            driver_var = self.params.get("driver_variable", "")
            # 处理驱动变量名
            d_var_name = driver_var
            if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
                d_var_name = d_var_name[1:-1]
            
            driver = context.get(d_var_name) or context.get("driver")
            if not driver:
                print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found in context (needed for scroll).")
                return False
                
            try:
                if 'Web' in globals():
                    Web.scroll_into_view(driver, element)
                    print(f"[WEB]: Scrolled to dynamic element from variable '{element_var}'")
                    return True
                else:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    return True
            except Exception as e:
                print(f"[WEB]: Failed to scroll to dynamic element: {e}")
                return False

        # 2. 原有的定位逻辑
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
        
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
        
        element_key = self.params.get("element_key", "")
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        
        if locator_source == "元素库" and element_key:
            resolved = _resolve_locator_from_element_library(context, element_key)
            if not resolved:
                print(f"[WEB]: Element not found in library: {element_key}")
                return False
            by, value = resolved
        
        try:
            if isinstance(value, str):
                value = value.format(**context)
        except:
            pass
        
        locator_type = _map_by(by)
        
        try:
            if 'Web' in globals():
                element = Web.wait_element_located(driver, (locator_type, value))
                Web.scroll_into_view(driver, element)
            else:
                element = driver.find_element(locator_type, value)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            return True
        except Exception as e:
            print(f"[WEB]: Failed to scroll: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True, "enable_if": {"locator_source": ["手动", "元素库", "网页元素"]}},
            {"name": "locator_source", "type": "str", "label": "定位来源", "default": "手动", "options": ["手动", "元素库", "网页元素"]},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"locator_source": "网页元素"}},
            {"name": "element_key", "type": "str", "label": "元素库 Key", "default": "", "enable_if": {"locator_source": "元素库"}, "ui_options": {"element_picker": True}},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"], "enable_if": {"locator_source": "手动"}},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "enable_if": {"locator_source": "手动"}}
        ]

class SwitchWindowAction(ActionBase):
    @property
    def name(self) -> str:
        return "切换窗口"
        
    @property
    def description(self) -> str:
        return "Switches to window containing URL substring."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
            
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
        
        url_substr = self.params.get("url_substring", "")
        try:
            if isinstance(url_substr, str):
                url_substr = url_substr.format(**context)
        except:
            pass
        
        try:
            if 'Web' in globals():
                return Web.switch_to_window_by_url(driver, url_substr)
            else:
                # Basic implementation fallback
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    if url_substr in driver.current_url:
                        return True
                return False
        except Exception as e:
            print(f"[WEB]: Failed to switch window: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True},
            {"name": "url_substring", "type": "str", "label": "URL 子串匹配", "default": ""}
        ]

class DrawMousePathAction(ActionBase):
    @property
    def name(self) -> str:
        return "绘制鼠标轨迹"
    
    @property
    def description(self) -> str:
        return "Draws a mouse movement path on screen."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
            
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
        
        points_str = self.params.get("points", "[]")
        color = self.params.get("color", "#ff4d4f")
        width = int(self.params.get("width", 2))
        duration = int(self.params.get("duration", 3000))
        
        try:
            # Support context variable for points if it looks like {var}
            if isinstance(points_str, str) and points_str.startswith("{") and points_str.endswith("}"):
                 # simple check, but user might pass complex format string. 
                 # Let's try standard format first
                 formatted = points_str.format(**context)
                 # If it resolved to a string that is JSON
                 try:
                     points = json.loads(formatted)
                 except:
                     # Maybe the variable itself is a list object in context?
                     # format() converts to string.
                     # If points_str is exactly "{var}", we can get object directly.
                     var_name = points_str[1:-1]
                     points = context.get(var_name, [])
            else:
                 points = json.loads(points_str)
            
            if 'Web' in globals():
                return Web.draw_mouse_path(driver, points, color, width, duration)
            else:
                print("[WEB]: Web util not available")
                return False
        except Exception as e:
            print(f"[WEB]: Failed to draw path: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True},
            {"name": "points", "type": "str", "label": "点位(JSON 或 {变量})", "default": "[[100,100],[200,200]]"},
            {"name": "color", "type": "str", "label": "颜色(十六进制)", "default": "#ff4d4f"},
            {"name": "width", "type": "int", "label": "线宽(px)", "default": 2},
            {"name": "duration", "type": "int", "label": "持续时间(ms)", "default": 3000, "advanced": True}
        ]

class WaitElementAction(ActionBase):
    @property
    def name(self) -> str:
        return "等待元素"
    @property
    def description(self) -> str:
        return "等待网页上的元素满足指定条件（如可见、存在等）。"
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True},
            {"name": "locator_source", "type": "str", "label": "定位来源", "default": "手动", "options": ["手动", "元素库", "网页元素"]},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"locator_source": "网页元素"}},
            {"name": "element_key", "type": "str", "label": "元素库 Key", "default": "", "enable_if": {"locator_source": "元素库"}, "ui_options": {"element_picker": True}},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"], "enable_if": {"locator_source": "手动"}},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "enable_if": {"locator_source": "手动"}},
            {"name": "timeout", "type": "int", "label": "超时时间(秒)", "default": 20},
            {"name": "wait_type", "type": "str", "label": "等待方式", "default": "visible", "options": ["visible", "present", "hidden"]},
            {"name": "output_variable", "type": "str", "label": "输出变量名", "default": "element", "variable_type": "网页元素", "is_variable": True, "enable_if": {"wait_type": ["visible", "present"]}}
        ]
    def execute(self, context: Dict[str, Any]) -> bool:
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
        
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
            
        locator_source = self.params.get("locator_source", "手动")
        timeout = int(self.params.get("timeout", 20))
        wait_type = self.params.get("wait_type", "visible")
        output_var = self.params.get("output_variable", "element")

        # 1. 直接处理网页元素变量
        if locator_source == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            element = context.get(var_name)
            if not element:
                print(f"[WEB]: Web element variable '{element_var}' (resolved as '{var_name}') not found.")
                return False
            
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                if wait_type == "visible":
                    element = WebDriverWait(driver, timeout).until(EC.visibility_of(element))
                    context[output_var] = element
                elif wait_type == "present":
                    try:
                        element.is_enabled()
                    except:
                        print(f"[WEB]: Element {element_var} is stale or not present.")
                        return False
                    context[output_var] = element
                elif wait_type == "hidden":
                    if 'Web' in globals():
                        Web.wait_element_hide(driver, element=element, timeout=timeout)
                    else:
                        WebDriverWait(driver, timeout).until(lambda d: not element.is_displayed())
                
                print(f"[WEB]: Waited for dynamic element '{element_var}' to be {wait_type}")
                return True
            except Exception as e:
                print(f"[WEB]: Wait for dynamic element ({wait_type}) failed: {e}")
                return False

        # 2. 原有的定位逻辑
        element_key = self.params.get("element_key", "")
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        
        if locator_source == "元素库" and element_key:
            resolved = _resolve_locator_from_element_library(context, element_key)
            if not resolved:
                print(f"[WEB]: Element not found in library: {element_key}")
                return False
            by, value = resolved
        else:
            try:
                if isinstance(value, str):
                    value = value.format(**context)
            except Exception:
                pass
        locator_type = _map_by(by)
        
        try:
            if 'Web' in globals():
                if wait_type == "visible":
                    element = Web.wait_element_visible(driver, (locator_type, value), timeout)
                    context[output_var] = element
                elif wait_type == "present":
                    element = Web.wait_element_located(driver, (locator_type, value), timeout)
                    context[output_var] = element
                elif wait_type == "hidden":
                    Web.wait_element_hide(driver, (locator_type, value), timeout)
                return True
            else:
                return False
        except Exception as e:
            print(f"[WEB]: Wait element ({wait_type}) failed: {e}")
            return False

class WaitAllElementsAction(ActionBase):
    @property
    def name(self) -> str:
        return "等待全部元素"
    @property
    def description(self) -> str:
        return "等待所有符合条件的元素出现。"
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "driver_variable", "type": "str", "label": "网页对象变量名", "default": "", "variable_type": "网页对象", "is_variable": True},
            {"name": "locator_source", "type": "str", "label": "定位来源", "default": "手动", "options": ["手动", "元素库", "网页元素"]},
            {"name": "target_element_variable", "type": "str", "label": "网页元素变量名", "default": "", "variable_type": "网页元素", "is_variable": True, "enable_if": {"locator_source": "网页元素"}},
            {"name": "element_key", "type": "str", "label": "元素库 Key", "default": "", "enable_if": {"locator_source": "元素库"}, "ui_options": {"element_picker": True}},
            {"name": "by", "type": "str", "label": "定位方式", "default": "xpath", "options": ["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"], "enable_if": {"locator_source": "手动"}},
            {"name": "value", "type": "str", "label": "定位值", "default": "", "enable_if": {"locator_source": "手动"}},
            {"name": "timeout", "type": "int", "label": "超时时间(秒)", "default": 20},
            {"name": "wait_type", "type": "str", "label": "等待方式", "default": "visible", "options": ["visible", "present", "hidden"]},
            {"name": "output_variable", "type": "str", "label": "输出变量名", "default": "elements", "variable_type": "一般变量", "is_variable": True, "enable_if": {"wait_type": ["visible", "present"]}}
        ]
    def execute(self, context: Dict[str, Any]) -> bool:
        driver_var = self.params.get("driver_variable", "")
        # 处理驱动变量名
        d_var_name = driver_var
        if isinstance(d_var_name, str) and d_var_name.startswith("{") and d_var_name.endswith("}"):
            d_var_name = d_var_name[1:-1]
        
        driver = context.get(d_var_name) or context.get("driver")
        if not driver:
            print(f"[WEB]: Driver '{driver_var}' (resolved as '{d_var_name}') not found.")
            return False
            
        locator_source = self.params.get("locator_source", "手动")
        timeout = int(self.params.get("timeout", 20))
        wait_type = self.params.get("wait_type", "visible")
        output_var = self.params.get("output_variable", "elements")

        # 1. 直接处理网页元素变量
        if locator_source == "网页元素":
            element_var = self.params.get("target_element_variable", "")
            # 处理可能带大括号的变量名
            var_name = element_var
            if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            
            target = context.get(var_name)
            if not target:
                print(f"[WEB]: Web element(s) variable '{element_var}' (resolved as '{var_name}') not found.")
                return False
            
            # 如果是单元素，包装成列表；如果是列表，直接使用
            elements = target if isinstance(target, list) else [target]
            
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                valid_elements = []
                for el in elements:
                    try:
                        if wait_type == "visible":
                            if el.is_displayed():
                                valid_elements.append(el)
                        elif wait_type == "present":
                            el.is_enabled() # check if stale
                            valid_elements.append(el)
                        elif wait_type == "hidden":
                            if not el.is_displayed():
                                valid_elements.append(el)
                    except:
                        pass
                
                if wait_type != "hidden":
                    context[output_var] = valid_elements
                
                print(f"[WEB]: Checked dynamic elements from '{element_var}', {len(valid_elements)} match {wait_type}")
                return True
            except Exception as e:
                print(f"[WEB]: Wait for dynamic elements ({wait_type}) failed: {e}")
                return False

        # 2. 原有的定位逻辑
        element_key = self.params.get("element_key", "")
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        
        if locator_source == "元素库" and element_key:
            resolved = _resolve_locator_from_element_library(context, element_key)
            if not resolved:
                print(f"[WEB]: Element not found in library: {element_key}")
                return False
            by, value = resolved
        else:
            try:
                if isinstance(value, str):
                    value = value.format(**context)
            except Exception:
                pass
        locator_type = _map_by(by)
        
        try:
            if 'Web' in globals():
                if wait_type == "visible":
                    elements = Web.wait_all_elements_visible(driver, (locator_type, value), timeout)
                    context[output_var] = elements
                elif wait_type == "present":
                    elements = Web.wait_all_elements_located(driver, (locator_type, value), timeout)
                    context[output_var] = elements
                elif wait_type == "hidden":
                    Web.wait_all_elements_hide(driver, (locator_type, value), timeout)
                return True
            else:
                return False
        except Exception as e:
            print(f"[WEB]: Wait all elements ({wait_type}) failed: {e}")
            return False

class GetFirstVisibleAction(ActionBase):
    @property
    def name(self) -> str:
        return "获取第一个可见元素"

    @property
    def description(self) -> str:
        return "从元素列表中查找并返回第一个在页面上可见的元素。"

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "elements_variable", "type": "str", "label": "元素列表变量", "default": "", "variable_type": "一般变量", "is_variable": True},
            {"name": "output_variable", "type": "str", "label": "输出变量名", "default": "visible_element", "variable_type": "网页元素", "is_variable": True}
        ]

    def execute(self, context: Dict[str, Any]) -> bool:
        elements_var = self.params.get("elements_variable", "")
        # 处理可能带大括号的变量名
        var_name = elements_var
        if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
            var_name = var_name[1:-1]
            
        elements = context.get(var_name)
        output_var = self.params.get("output_variable", "visible_element")
        
        if not isinstance(elements, list):
            print(f"[WEB]: {elements_var} (resolved as '{var_name}') is not a list or not found.")
            return False
            
        try:
            if 'Web' in globals():
                element = Web.get_first_visible(elements)
                context[output_var] = element
                return True
            return False
        except Exception as e:
            print(f"[WEB]: Get first visible failed: {e}")
            return False

class FindChildAction(ActionBase):
    @property
    def name(self) -> str:
        return "查找子元素"

    @property
    def description(self) -> str:
        return "在指定的父元素下查找第一个符合 XPATH 的子元素。"

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "parent_element", "type": "str", "label": "父元素变量", "default": "", "variable_type": "网页元素", "is_variable": True},
            {"name": "xpath", "type": "str", "label": "子元素 XPATH", "default": ""},
            {"name": "output_variable", "type": "str", "label": "输出变量名", "default": "child_element", "variable_type": "网页元素", "is_variable": True}
        ]

    def execute(self, context: Dict[str, Any]) -> bool:
        parent_var = self.params.get("parent_element", "")
        # 处理可能带大括号的变量名
        var_name = parent_var
        if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
            var_name = var_name[1:-1]
            
        parent = context.get(var_name)
        xpath = self.params.get("xpath", "")
        output_var = self.params.get("output_variable", "child_element")
        
        if not parent:
            print(f"[WEB]: Parent element {parent_var} (resolved as '{var_name}') not found.")
            return False
            
        try:
            xpath = xpath.format(**context)
        except:
            pass
            
        try:
            if 'Web' in globals():
                element = Web.find_child(parent, xpath)
                context[output_var] = element
                return True
            return False
        except Exception as e:
            print(f"[WEB]: Find child failed: {e}")
            return False

class FindChildrenAction(ActionBase):
    @property
    def name(self) -> str:
        return "查找所有子元素"

    @property
    def description(self) -> str:
        return "在指定的父元素下查找所有符合 XPATH 的子元素。"

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "parent_element", "type": "str", "label": "父元素变量", "default": "", "variable_type": "网页元素", "is_variable": True},
            {"name": "xpath", "type": "str", "label": "子元素 XPATH", "default": ""},
            {"name": "output_variable", "type": "str", "label": "输出变量名", "default": "child_elements", "variable_type": "一般变量", "is_variable": True}
        ]

    def execute(self, context: Dict[str, Any]) -> bool:
        parent_var = self.params.get("parent_element", "")
        # 处理可能带大括号的变量名
        var_name = parent_var
        if isinstance(var_name, str) and var_name.startswith("{") and var_name.endswith("}"):
            var_name = var_name[1:-1]
            
        parent = context.get(var_name)
        xpath = self.params.get("xpath", "")
        output_var = self.params.get("output_variable", "child_elements")
        
        if not parent:
            print(f"[WEB]: Parent element {parent_var} (resolved as '{var_name}') not found.")
            return False
            
        try:
            xpath = xpath.format(**context)
        except:
            pass
            
        try:
            if 'Web' in globals():
                elements = Web.find_children(parent, xpath)
                context[output_var] = elements
                return True
            return False
        except Exception as e:
            print(f"[WEB]: Find children failed: {e}")
            return False
