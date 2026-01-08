import os
import re
from typing import Dict, Any, List
from PIL import Image

from core.action_base import ActionBase
from utils.file_tools import FileTools
from utils.img_ocr import ImgOcr
from utils.notice import WeChatNotification

class WaitForFileAndCopyAction(ActionBase):
    @property
    def name(self) -> str:
        return "Wait & Copy File"
    
    @property
    def description(self) -> str:
        return "Waits for a file in a directory and copies it."
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "source_dir", "label": "Source Directory (Watch)", "type": "string"},
            {"name": "dest_path", "label": "Destination File Path", "type": "string"}
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
        return "Clear Directory"
    
    @property
    def description(self) -> str:
        return "Deletes all files in a directory."
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "directory", "label": "Directory Path", "type": "string"}
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
        return "OCR Image"
    
    @property
    def description(self) -> str:
        return "Recognizes text in an image."
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "image_path", "label": "Image Path", "type": "string"},
            {"name": "output_variable", "label": "Output Variable Name", "type": "string", "default": "ocr_text"}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        path = self.params.get("image_path")
        output_var = self.params.get("output_variable", "ocr_text")
        
        if not path or not os.path.exists(path):
            print(f"[OCR] Image not found: {path}")
            return False
            
        try:
            with Image.open(path) as img:
                ocr = ImgOcr()
                text = ocr.recognize(img)
                context[output_var] = text
                print(f"[OCR] Result: {text}")
                return True
        except Exception as e:
            print(f"[OCR] Error: {e}")
            return False

class WeChatNotifyAction(ActionBase):
    @property
    def name(self) -> str:
        return "WeChat Notify"
    
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
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "extracted_content"}
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
