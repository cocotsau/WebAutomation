import json
from typing import Dict, Any, List
from core.action_base import ActionBase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
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

class OpenBrowserAction(ActionBase):
    @property
    def name(self) -> str:
        return "Open Browser"

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
        
        chrome_path = self.params.get("chrome_path", "")
        user_data_dir = self.params.get("user_data_dir", "")
        debug_port = int(self.params.get("debug_port", 9222))
        
        try:
            from utils.driver_helper import DriverHelper
        except ImportError:
            print("[WEB]: DriverHelper not found. Please ensure utils/driver_helper.py exists.")
            return False

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
                # Ensure path is not empty
                if not chrome_path and browser_config:
                     chrome_path = browser_config.exe_path.get(browser_type, "")
                
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
                # Standard Selenium Launch
                # Use DriverHelper to build options
                options = DriverHelper.build_selenium_chrome_options(
                    executable_path=chrome_path,
                    user_data_dir=user_data_dir,
                    headless=headless,
                    incognito=incognito,
                    window_size=window_size
                )
                
                options.add_experimental_option("detach", True)
                
                service = get_service()
                driver = webdriver.Chrome(service=service, options=options)
                
                if url:
                    driver.get(url)

            context["driver"] = driver
            print(f"[WEB]: Browser opened in {launch_mode} mode.")
            return True
            
        except Exception as e:
            print(f"[WEB]: Failed to open browser: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        default_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        default_data = os.path.join(os.getcwd(), "chrome_data")
        default_port = 9222
        
        if browser_config:
            default_exe = browser_config.exe_path.get("chrome", default_exe)
            default_data = browser_config.data_dir.get("chrome", default_data)
            default_port = browser_config.debug_port.get("chrome", default_port)

        return [
            {"name": "launch_mode", "type": "str", "label": "Launch Mode (selenium/subprocess)", "default": "selenium"},
            {"name": "browser_type", "type": "str", "label": "Browser Type (chrome/browser360)", "default": "chrome"},
            {"name": "url", "type": "str", "label": "Initial URL", "default": "https://www.google.com"},
            {"name": "headless", "type": "bool", "label": "Headless Mode", "default": False},
            {"name": "incognito", "type": "bool", "label": "Incognito Mode", "default": False},
            {"name": "kill_process", "type": "bool", "label": "Kill Existing Process", "default": False},
            {"name": "window_size", "type": "str", "label": "Window Size", "default": "1920,1080"},
            {"name": "chrome_path", "type": "str", "label": "Browser Path", "default": default_exe},
            {"name": "user_data_dir", "type": "str", "label": "User Data Dir", "default": default_data},
            {"name": "debug_port", "type": "int", "label": "Debug Port", "default": default_port}
        ]

class CloseBrowserAction(ActionBase):
    @property
    def name(self) -> str:
        return "Close Browser"

    @property
    def description(self) -> str:
        return "Closes the browser."

    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if driver:
            try:
                driver.quit()
                del context["driver"]
                print("[WEB]: Browser closed.")
            except Exception as e:
                print(f"[WEB]: Error closing browser: {e}")
        else:
            print("[WEB]: No browser found to close.")
        return True
        
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return []

class ClickElementAction(ActionBase):
    @property
    def name(self) -> str:
        return "Click Element"

    @property
    def description(self) -> str:
        return "Clicks an element identified by XPath or CSS Selector."

    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver:
            print("[WEB]: Driver not found in context.")
            return False
            
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        timeout = int(self.params.get("timeout", 20))
        
        locator_type = By.XPATH if by.lower() == "xpath" else By.CSS_SELECTOR
        
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
            {"name": "by", "type": "str", "label": "By (xpath/css)", "default": "xpath"},
            {"name": "value", "type": "str", "label": "Locator Value", "default": ""},
            {"name": "timeout", "type": "int", "label": "Timeout (s)", "default": 20}
        ]

class InputTextAction(ActionBase):
    @property
    def name(self) -> str:
        return "Input Text"

    @property
    def description(self) -> str:
        return "Inputs text into an element."

    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver:
            print("[WEB]: Driver not found.")
            return False
            
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        text = self.params.get("text", "")
        
        try:
            text = text.format(**context)
        except:
            pass
            
        locator_type = By.XPATH if by.lower() == "xpath" else By.CSS_SELECTOR
        
        try:
            if 'Web' in globals():
                element = Web.wait_element_visible(driver, (locator_type, value))
            else:
                element = WebDriverWait(driver, 20).until(EC.visibility_of_element_located((locator_type, value)))
            
            element.clear()
            element.send_keys(text)
            print(f"[WEB]: Input '{text}' to {by}={value}")
            return True
        except Exception as e:
            print(f"[WEB]: Failed to input text: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "by", "type": "str", "label": "By (xpath/css)", "default": "xpath"},
            {"name": "value", "type": "str", "label": "Locator Value", "default": ""},
            {"name": "text", "type": "str", "label": "Text", "default": ""}
        ]

class GoToUrlAction(ActionBase):
    @property
    def name(self) -> str:
        return "Go To URL"

    @property
    def description(self) -> str:
        return "Navigates the browser to a specific URL."

    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver:
            print("[WEB]: Driver not found.")
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
            {"name": "url", "type": "str", "label": "URL", "default": "https://"}
        ]

class HttpDownloadAction(ActionBase):
    @property
    def name(self) -> str:
        return "Http Download"

    @property
    def description(self) -> str:
        return "Downloads a file from a URL via HTTP."

    def execute(self, context: Dict[str, Any]) -> bool:
        url = self.params.get("url")
        save_path = self.params.get("save_path")
        timeout = int(self.params.get("timeout", 120))
        use_browser_cookies = self.params.get("use_browser_cookies", True)
        
        try:
            url = url.format(**context)
            save_path = save_path.format(**context)
        except:
            pass
            
        try:
            from utils.web import Web
            driver = context.get("driver") if use_browser_cookies else None
            return Web.http_download(url, save_path, driver=driver, timeout=timeout)
        except Exception as e:
            print(f"[WEB]: Download failed: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "url", "type": "str", "label": "Download URL", "default": ""},
            {"name": "save_path", "type": "str", "label": "Save Path", "default": "downloaded_file.ext"},
            {"name": "use_browser_cookies", "type": "bool", "label": "Use Browser Cookies", "default": True},
            {"name": "timeout", "type": "int", "label": "Timeout (s)", "default": 120}
        ]

class GetTextAction(ActionBase):
    @property
    def name(self) -> str:
        return "Get Text"

    @property
    def description(self) -> str:
        return "Gets the text of an element and saves it to a variable."

    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver:
            print("[WEB]: Driver not found.")
            return False
            
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        output_var = self.params.get("output_variable", "text_output")
        timeout = int(self.params.get("timeout", 20))
        
        locator_type = By.XPATH if by.lower() == "xpath" else By.CSS_SELECTOR
        
        try:
            if 'Web' in globals():
                element = Web.wait_element_visible(driver, (locator_type, value), timeout)
            else:
                element = WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((locator_type, value)))
            
            text = element.text
            context[output_var] = text
            print(f"[WEB]: Got text '{text}' from {value}, saved to {output_var}")
            return True
        except Exception as e:
            print(f"[WEB]: Failed to get text: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "by", "type": "str", "label": "By (xpath/css)", "default": "xpath"},
            {"name": "value", "type": "str", "label": "Locator Value", "default": ""},
            {"name": "output_variable", "type": "str", "label": "Output Variable", "default": "text_output"},
            {"name": "timeout", "type": "int", "label": "Timeout (s)", "default": 20}
        ]

class HoverElementAction(ActionBase):
    @property
    def name(self) -> str:
        return "Hover Element"
    
    @property
    def description(self) -> str:
        return "Moves mouse over an element."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver: return False
        
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        timeout = int(self.params.get("timeout", 20))
        
        locator_type = By.XPATH if by.lower() == "xpath" else By.CSS_SELECTOR
        
        try:
            if 'Web' in globals():
                element = Web.wait_element_visible(driver, (locator_type, value), timeout)
                Web.element_hover(driver, element)
            else:
                print("[WEB]: Web util not available")
                return False
            return True
        except Exception as e:
            print(f"[WEB]: Failed to hover: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "by", "type": "str", "label": "By (xpath/css)", "default": "xpath"},
            {"name": "value", "type": "str", "label": "Locator Value", "default": ""},
            {"name": "timeout", "type": "int", "label": "Timeout (s)", "default": 20}
        ]

class SwitchFrameAction(ActionBase):
    @property
    def name(self) -> str:
        return "Switch Frame"
        
    @property
    def description(self) -> str:
        return "Switch to an iframe by ID (or default content if empty)."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver: return False
        
        iframe_id = self.params.get("iframe_id", "")
        
        try:
            if 'Web' in globals():
                Web.switch_frame(driver, iframe_id if iframe_id else None)
            else:
                driver.switch_to.default_content()
                if iframe_id:
                    driver.switch_to.frame(iframe_id)
            return True
        except Exception as e:
            print(f"[WEB]: Failed to switch frame: {e}")
            return False

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "iframe_id", "type": "str", "label": "IFrame ID (Empty=Default)", "default": ""}
        ]

class ScrollToElementAction(ActionBase):
    @property
    def name(self) -> str:
        return "Scroll To Element"
        
    @property
    def description(self) -> str:
        return "Scrolls element into view."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver: return False
        
        by = self.params.get("by", "xpath")
        value = self.params.get("value")
        
        locator_type = By.XPATH if by.lower() == "xpath" else By.CSS_SELECTOR
        
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
            {"name": "by", "type": "str", "label": "By (xpath/css)", "default": "xpath"},
            {"name": "value", "type": "str", "label": "Locator Value", "default": ""}
        ]

class SwitchWindowAction(ActionBase):
    @property
    def name(self) -> str:
        return "Switch Window"
        
    @property
    def description(self) -> str:
        return "Switches to window containing URL substring."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver: return False
        
        url_substr = self.params.get("url_substring", "")
        
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
            {"name": "url_substring", "type": "str", "label": "URL Substring", "default": ""}
        ]

class DrawMousePathAction(ActionBase):
    @property
    def name(self) -> str:
        return "Draw Mouse Path"
    
    @property
    def description(self) -> str:
        return "Draws a mouse movement path on screen."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        driver = context.get("driver")
        if not driver: return False
        
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
            {"name": "points", "type": "str", "label": "Points (JSON or {var})", "default": "[[100,100],[200,200]]"},
            {"name": "color", "type": "str", "label": "Color (Hex)", "default": "#ff4d4f"},
            {"name": "width", "type": "int", "label": "Width (px)", "default": 2},
            {"name": "duration", "type": "int", "label": "Duration (ms)", "default": 3000}
        ]
