# -*- coding: utf-8 -*-

import os
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By


import json
import requests
from pathlib import Path

class Web:


    @staticmethod
    def wait_page_loaded(driver, locator: tuple = (By.TAG_NAME, "body"), timeout: int = 20):
        print(f"等待页面加载完成, 超时: {timeout}秒")
        try:
            WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
            WebDriverWait(driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")
            print("页面加载完成")
            return True
        except Exception as e:
            print(f"页面加载超时: 错误: {e}")
            return False

    @staticmethod
    def wait_element_located(driver, locator: tuple, timeout: int = 20):
        print(f"等待元素定位: {locator[0]}='{locator[1]}', 超时: {timeout}秒")
        try:
            element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
            print(f"元素定位成功: {locator[0]}='{locator[1]}'")
            return element
        except Exception as e:
            print(f"元素定位失败: {locator[0]}='{locator[1]}', 错误: {e}")
            raise
    
    @staticmethod
    def wait_all_elements_located(driver, locator: tuple, timeout: int = 20):
        print(f"等待所有元素定位: {locator[0]}='{locator[1]}', 超时: {timeout}秒")
        try:
            elements = WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located(locator))
            print(f"所有元素定位成功: 找到{len(elements)}个元素")
            return elements
        except Exception as e:
            print(f"所有元素定位失败: {locator[0]}='{locator[1]}', 错误: {e}")
            raise
    
    @staticmethod
    def wait_element_visible(driver, locator: tuple, timeout: int = 20):
        print(f"等待元素可见: {locator[0]}='{locator[1]}', 超时: {timeout}秒")
        try:
            element = WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))
            print(f"元素可见成功: {locator[0]}='{locator[1]}'")
            return element
        except Exception as e:
            print(f"元素可见失败: {locator[0]}='{locator[1]}', 错误: {e}")
            raise
    
    @staticmethod
    def wait_all_elements_visible(driver, locator: tuple, timeout: int = 20):
        print(f"等待所有元素可见: {locator[0]}='{locator[1]}', 超时: {timeout}秒")
        try:
            elements = WebDriverWait(driver, timeout).until(EC.visibility_of_all_elements_located(locator))
            print(f"所有元素可见成功: 找到{len(elements)}个可见元素")
            return elements
        except Exception as e:
            print(f"所有元素可见失败: {locator[0]}='{locator[1]}', 错误: {e}")
            raise
    
    @staticmethod
    def wait_element_hide(driver, locator: tuple, timeout: int = 20):
        print(f"等待元素隐藏: {locator[0]}='{locator[1]}', 超时: {timeout}秒")
        try:
            result = WebDriverWait(driver, timeout).until(EC.invisibility_of_element_located(locator))
            print(f"元素隐藏成功: {locator[0]}='{locator[1]}'")
            return result
        except Exception as e:
            print(f"元素隐藏失败: {locator[0]}='{locator[1]}', 错误: {e}")
            raise

    @staticmethod
    def wait_element_clickable(driver, locator: tuple, timeout: int = 20):
        print(f"等待元素可点击: {locator[0]}='{locator[1]}', 超时: {timeout}秒")
        try:
            element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
            print(f"元素可点击成功: {locator[0]}='{locator[1]}'")
            return element
        except Exception as e:
            print(f"元素可点击失败: {locator[0]}='{locator[1]}', 错误: {e}")
            raise

    @staticmethod
    def element_hover(driver, element):
        print("执行鼠标悬停操作")
        ActionChains(driver).move_to_element(element).perform()
        print("鼠标悬停完成")

    
    @staticmethod
    def element_hover_click(driver, element):
        print("执行鼠标悬停点击操作")
        ActionChains(driver).move_to_element(element).pause(0.5).click().perform()
        print("鼠标悬停点击完成")

    @staticmethod
    def element_hover_input_text(driver, element, text: str):
        print("执行鼠标悬停输入文本操作")
        ActionChains(driver).move_to_element(element).pause(0.5).perform()
        element.clear()
        element.send_keys(text)
        print("鼠标悬停输入文本完成")

    @staticmethod
    def switch_frame(driver, iframe_id: str | None = None, timeout: int = 20):
        print("切换到默认文档上下文以刷新frame列表")
        try:
            driver.switch_to.default_content()
        except Exception as e:
            print(f"切回默认文档失败: {e}")
        if iframe_id:
            print(f"按ID切换到 iframe: {iframe_id}")
            iframe_el = Web.wait_element_located(driver, (By.ID, iframe_id), timeout=timeout)
        else:
            print("检测到 iframe，尝试切换...")
            iframe_el = Web.wait_element_located(driver, (By.TAG_NAME, "iframe"), timeout=timeout)
        driver.switch_to.frame(iframe_el)
        print("已切换到 iframe")
        return True


    @staticmethod
    def scroll_into_view(driver, element):
        print("执行滚动到元素可见位置操作")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        print("滚动完成")


    @staticmethod
    def chrome_set_download_behavior(driver, behavior="allow", download_path=None):
        """
        设置Chrome下载行为
        :param driver: WebDriver实例
        :param behavior: 'allow', 'deny', 'default'
        :param download_path: 下载路径 (behavior='allow'时必须)
        """
        params = {"behavior": behavior}
        if download_path:
            params["downloadPath"] = download_path
            
        print(f"设置Chrome下载行为: {behavior}, 路径: {download_path}")
        driver.execute_cdp_cmd("Page.setDownloadBehavior", params)

    @staticmethod
    def draw_mouse_path(driver, points, color="#ff4d4f", width=2, duration_ms=3000):
        print("开始绘制鼠标轨迹")
        try:
            js = """
            (function(points,color,width,duration){
              var c = document.getElementById('__mouse_path_canvas__');
              var dpr = window.devicePixelRatio || 1;
              if(!c){
                c = document.createElement('canvas');
                c.id = '__mouse_path_canvas__';
                c.style.position = 'fixed';
                c.style.left = '0';
                c.style.top = '0';
                c.style.width = '100vw';
                c.style.height = '100vh';
                c.style.pointerEvents = 'none';
                c.style.zIndex = 2147483647;
                document.body.appendChild(c);
                c.width = Math.floor(window.innerWidth * dpr);
                c.height = Math.floor(window.innerHeight * dpr);
              }
              var ctx = c.getContext('2d');
              ctx.setTransform(dpr,0,0,dpr,0,0);
              ctx.clearRect(0,0,window.innerWidth,window.innerHeight);
              ctx.strokeStyle = color;
              ctx.lineWidth = width;
              ctx.lineJoin = 'round';
              ctx.lineCap = 'round';
              ctx.beginPath();
              for(var i=0;i<points.length;i++){
                var p = points[i];
                if(!p) continue;
                if(i===0){ ctx.moveTo(p[0], p[1]); } else { ctx.lineTo(p[0], p[1]); }
              }
              ctx.stroke();
              var start = points[0], end = points[points.length-1];
              if(start){ ctx.fillStyle = color; ctx.beginPath(); ctx.arc(start[0], start[1], width*2, 0, Math.PI*2); ctx.fill(); }
              if(end){ ctx.fillStyle = color; ctx.beginPath(); ctx.arc(end[0], end[1], width*2, 0, Math.PI*2); ctx.fill(); }
              setTimeout(function(){
                var el = document.getElementById('__mouse_path_canvas__');
                if(el && el.parentNode){ el.parentNode.removeChild(el); }
              }, duration);
            })(arguments[0], arguments[1], arguments[2], arguments[3]);
            """
            driver.execute_script(js, points, color, int(width), int(duration_ms))
            print("鼠标轨迹绘制完成")
            return True
        except Exception as e:
            print(f"鼠标轨迹绘制失败: {e}")
            return False

    @staticmethod
    def build_path_from_elements(driver, elements):
        try:
            points = driver.execute_script("""
              return Array.prototype.map.call(arguments[0], function(el){
                if(!el) return null;
                var r = el.getBoundingClientRect();
                return [Math.floor(r.left + r.width/2), Math.floor(r.top + r.height/2)];
              });
            """, elements)
            print(f"已生成坐标点: {points}")
            return points
        except Exception as e:
            print(f"生成坐标点失败: {e}")
            return []

    @staticmethod
    def wait_submenu_item_interactable(driver, parent_title_locator: tuple, item_li_locator: tuple, timeout: int = 10):
        print(f"等待子菜单项目可交互: {item_li_locator[0]}='{item_li_locator[1]}'")
        title_el = Web.wait_element_located(driver, parent_title_locator, timeout=timeout)
        ActionChains(driver).move_to_element(title_el).pause(0.5).perform()
        try:
            driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('mouseenter',{bubbles:true}));", title_el)
            driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));", title_el)
        except Exception as e:
            print(f"派发悬停事件失败: {e}")
        try:
            ActionChains(driver).move_to_element(title_el).pause(0.2).click().perform()
        except Exception as e:
            print(f"标题点击失败: {e}")
            try:
                driver.execute_script("arguments[0].click();", title_el)
            except Exception as e2:
                print(f"标题JS点击失败: {e2}")
        try:
            submenu_ul = title_el.find_element_by_xpath("../ul[contains(@class,'spmain-submenu-content')]")
        except Exception:
            submenu_ul = Web.wait_element_located(
                driver,
                (parent_title_locator[0], parent_title_locator[1].replace("//div[contains(@class,'spmain-submenu-title')]", "//ul[contains(@class,'spmain-submenu-content')]")),
                timeout=timeout
            )
        WebDriverWait(driver, timeout).until(lambda d: d.execute_script("return getComputedStyle(arguments[0]).display!=='none';", submenu_ul))
        item_el = Web.wait_element_located(driver, item_li_locator, timeout=timeout)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", item_el)
        def _ready(d):
            try:
                res = d.execute_script("""
                  var el=arguments[0], r=el.getBoundingClientRect();
                  if(r.width<=0 || r.height<=0) return false;
                  var x=Math.floor(r.left+r.width/2), y=Math.floor(r.top+r.height/2);
                  var topEl=document.elementFromPoint(x,y);
                  if(!topEl) return false;
                  var pe=getComputedStyle(topEl).pointerEvents;
                  return pe!=='none';
                """, item_el)
                return bool(res)
            except:
                return False
        WebDriverWait(driver, timeout).until(_ready)
        print("子菜单项目已可交互")
        return item_el

    @staticmethod
    def get_download_url_from_logs(driver, timeout=20):
        """从性能日志中捕获下载链接"""
        print("正在监听网络日志以捕获下载链接...")
        end_time = time.time() + timeout
        while time.time() < end_time:
            logs = driver.get_log('performance')
            for entry in logs:
                try:
                    message = json.loads(entry['message'])['message']
                    if message['method'] == 'Network.responseReceived':
                        params = message['params']
                        response = params['response']
                        headers = {k.lower(): v for k, v in response.get('headers', {}).items()}
                        
                        # 检查是否为附件下载
                        # 1. 检查 Content-Disposition
                        content_disposition = headers.get('content-disposition', '')
                        if 'attachment' in content_disposition or 'filename=' in content_disposition:
                            url = response['url']
                            print(f"捕获到下载链接(Content-Disposition): {url}")
                            return url
                        
                        # 2. 检查 Content-Type (常见的Excel/二进制流)
                        content_type = headers.get('content-type', '')
                        if 'application/vnd.ms-excel' in content_type or \
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in content_type or \
                        'application/octet-stream' in content_type:
                            # 进一步过滤掉非目标URL（例如 .js, .css, .png 等，虽然ContentType通常不对，但为了保险）
                            url = response['url']
                            if not url.endswith('.js') and not url.endswith('.css'):
                                print(f"捕获到下载链接(Content-Type): {url}")
                                return url
                                
                except Exception:
                    continue
            time.sleep(1)
        return None

    @staticmethod
    def http_download(url: str, save_path: str, driver=None, cookies=None, user_agent=None, timeout: int = 120):
        """HTTP下载文件，支持使用Selenium的Cookies"""
        try:
            # 确保保存目录存在
            save_dir = Path(save_path).parent
            save_dir.mkdir(parents=True, exist_ok=True)
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            req_cookies = {}
            
            # 优先使用传入的cookies和ua
            if user_agent:
                headers["User-Agent"] = user_agent
            if cookies:
                req_cookies = cookies
                
            # 如果提供了driver且没有提供cookies，则从driver获取
            if driver and not req_cookies:
                selenium_cookies = driver.get_cookies()
                for cookie in selenium_cookies:
                    req_cookies[cookie['name']] = cookie['value']
                
                # 尝试获取当前User-Agent
                if not user_agent:
                    try:
                        ua = driver.execute_script("return navigator.userAgent")
                        if ua:
                            headers["User-Agent"] = ua
                    except:
                        pass
            
            print(f"开始HTTP下载: {url}")
            print(f"保存路径: {save_path}")
            
            response = requests.get(url, headers=headers, cookies=req_cookies, timeout=timeout, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
            print(f"文件下载成功：{save_path}")
            return True
        except Exception as e:
            print(f"文件下载失败：{e}")
            return False

    @staticmethod
    def switch_to_window_by_url(driver, url_substring: str, max_attempts: int = 3, interval: int = 10, verify_locator: tuple | None = None, verify_timeout: int = 10):
        print(f"开始切换窗口: 目标URL包含 '{url_substring}', 最大重试: {max_attempts}, 间隔: {interval}秒")
        for attempt in range(1, max_attempts + 1):
            found = False
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                current_url = driver.current_url
                print(f"切换到窗口 {handle}, 当前URL: {current_url}")
                if url_substring in current_url:
                    found = True
                    print(f"成功切换到目标窗口 {handle}")
                    break
            if found:
                try:
                    Web.wait_page_loaded(driver, (By.TAG_NAME, "body"))
                    if verify_locator:
                        Web.wait_element_located(driver, verify_locator, timeout=verify_timeout)
                    print("目标窗口验证通过")
                    return True
                except Exception as e:
                    print(f"目标窗口验证失败: {e}")
                    if attempt < max_attempts:
                        time.sleep(interval)
                        continue
                    else:
                        raise Exception("切换至目标窗口后验证失败")
            else:
                if attempt < max_attempts:
                    print("未找到目标窗口，准备重试")
                    time.sleep(interval)
                    continue
                else:
                    raise Exception("未找到目标窗口句柄")
        return False
