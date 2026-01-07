import os
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
            {"name": "key", "label": "Robot Key", "type": "string"},
            {"name": "content", "label": "Message Content", "type": "string"},
            {"name": "is_markdown", "label": "Use Markdown", "type": "bool"}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        key = self.params.get("key")
        content = self.params.get("content")
        is_md = self.params.get("is_markdown", False)
        
        # Support variable substitution in content
        # Simple substitution for now?
        # Actually, the user might want to use {var} syntax.
        # Let's try to format it using context.
        try:
            content = content.format(**context)
        except:
            pass # If format fails, use as is (e.g. key errors)
            
        if not key or not content:
            return False
            
        notifier = WeChatNotification(wechat_keys=key)
        if is_md:
            return notifier.send_markdown(content)
        else:
            return notifier.send_text(content)
