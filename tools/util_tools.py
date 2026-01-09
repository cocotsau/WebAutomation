import os
import re
from typing import Dict, Any, List
from PIL import Image

from core.action_base import ActionBase
from utils.file_tools import FileTools
from utils.img_ocr import ImgOcr
from utils.img_tools import ImgTools
from utils.notice import WeChatNotification

class WaitForFileAndCopyAction(ActionBase):
    @property
    def name(self) -> str:
        return "等待并复制文件"
    
    @property
    def description(self) -> str:
        return "Waits for a file in a directory and copies it."
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "source_dir", "label": "Source Directory (Watch)", "type": "string", "ui_options": {"browse_type": "directory"}},
            {"name": "dest_path", "label": "Destination File Path", "type": "string", "ui_options": {"browse_type": "file_save"}}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        src = self.params.get("source_dir")
        dst = self.params.get("dest_path")
        if not src or not dst:
            return False
        return FileTools.copy_file(src, dst)

class ClearDirectoryAction(ActionBase):
    @property
    def name(self) -> str:
        return "清空目录"
    
    @property
    def description(self) -> str:
        return "Deletes all files in a directory."
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "directory", "label": "Directory Path", "type": "string", "ui_options": {"browse_type": "directory"}}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        directory = self.params.get("directory")
        if not directory:
            return False
        FileTools.clear_directory(directory)
        return True

class OCRImageAction(ActionBase):
    @property
    def name(self) -> str:
        return "OCR 文字识别"
    
    @property
    def description(self) -> str:
        return "识别图片中的文字（支持本地路径或 Base64 字符串）。"
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "image_path", "label": "图片路径 (可选)", "type": "string", "default": "", "ui_options": {"browse_type": "file"}},
            {"name": "base64_str", "label": "Base64 字符串 (可选)", "type": "string", "default": ""},
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "ocr_text", "variable_type": "一般变量"}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        image_path = self.params.get("image_path", "")
        base64_str = self.params.get("base64_str", "")
        output_var = self.params.get("output_variable", "ocr_text")
        
        # 变量替换
        try:
            if image_path:
                image_path = image_path.format(**context)
            if base64_str:
                base64_str = base64_str.format(**context)
        except Exception:
            pass
            
        img = None
        try:
            # 智能识别输入源：优先处理显式 Base64，或者判断 image_path 是否包含 Base64 特征
            source = base64_str or image_path
            if not source:
                print("[OCR] 未提供图片路径或 Base64 字符串")
                return False

            # 判断是否为 Base64 (包含 data URI 前缀或长度较长且不包含路径分隔符)
            is_base64 = "base64," in source or (len(source) > 200 and not os.path.exists(source))
            
            if is_base64:
                img = ImgTools.base64_to_png(source)
                if not img:
                    msg = f"[OCR] Base64 转换图片失败: {source}"
                    if len(msg) > 100: msg = msg[:100] + "...(数据过长已截断)"
                    print(msg)
                    return False
            else:
                if not os.path.exists(source):
                    print(f"[OCR] 图片文件不存在: {source}")
                    return False
                img = Image.open(source)
                
            # 调用 img_ocr 中的 recognize
            ocr = ImgOcr()
            text = ocr.recognize(img)
            
            # 最终输出验证码字符串
            context[output_var] = text
            
            # 日志截断处理
            log_msg = f"[OCR] 识别结果: {text}"
            if len(log_msg) > 100:
                log_msg = log_msg[:100] + "\n...（日志信息过长，已截断）"
            print(log_msg)
            return True
            
        except Exception as e:
            error_msg = f"[OCR] 识别出错: {e}"
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "\n...（日志信息过长，已截断）"
            print(error_msg)
            return False

class WeChatNotifyAction(ActionBase):
    @property
    def name(self) -> str:
        return "微信通知"
    
    @property
    def description(self) -> str:
        return "Sends a message via WeChat Work Robot."
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "key", "label": "机器人 Key", "type": "string"},
            {"name": "content", "label": "消息内容", "type": "string"},
            {"name": "is_markdown", "label": "使用 Markdown", "type": "bool", "advanced": True}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        key = self.params.get("key")
        content = self.params.get("content")
        is_markdown = self.params.get("is_markdown", False)
        
        if not key or not content:
            return False
            
        notifier = WeChatNotification(key)
        if is_markdown:
            notifier.send_markdown(content)
        else:
            notifier.send_text(content)
        return True

class ExtractContentAction(ActionBase):
    @property
    def name(self) -> str:
        return "从文本中提取内容"
    
    @property
    def description(self) -> str:
        return "使用正则表达式提取内容"
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "text", "label": "目标文本", "type": "string"},
            {"name": "pattern", "label": "正则表达式", "type": "string"},
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "extracted_content", "variable_type": "一般变量"}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        text = self.params.get("text", "")
        pattern = self.params.get("pattern", "")
        output_var = self.params.get("output_variable", "extracted_content")
        
        # Support variable interpolation for text and pattern
        try:
            text = text.format(**context)
        except:
            pass
            
        try:
            match = re.search(pattern, text)
            if match:
                result = match.group(0) # Default to full match
                # If there are groups, use the first group
                if match.groups():
                    result = match.group(1)
                context[output_var] = result
                print(f"[ExtractContent] Found: {result}")
            else:
                context[output_var] = ""
                print(f"[ExtractContent] No match found for pattern '{pattern}' in '{text[:20]}...'")
            return True
        except Exception as e:
            print(f"[ExtractContent] Error: {e}")
            return False
