import time
import json
import tkinter as tk
from tkinter import filedialog, simpledialog
from typing import Dict, Any, List
from core.action_base import ActionBase

def get_tk_root():
    """Helper to get or create a hidden Tk root."""
    try:
        root = tk.Tk()
        root.withdraw() # Hide the main window
        root.attributes('-topmost', True) # Bring dialogs to front
        return root
    except Exception:
        return None

class FileDialogAction(ActionBase):
    @property
    def name(self) -> str:
        return "打开文件选择对话框"
    
    @property
    def description(self) -> str:
        return "弹出文件选择对话框，并将路径保存到变量。"
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "prompt", "label": "提示信息", "type": "string", "default": "请选择文件"},
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "file_path"}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        prompt = self.params.get("prompt", "请选择文件")
        output_var = self.params.get("output_variable", "file_path")
        
        print(f"[FileDialog] Prompt: {prompt}")
        
        root = get_tk_root()
        if root:
            file_path = filedialog.askopenfilename(title=prompt)
            root.destroy()
        else:
            # Fallback to console input
            print(f"!!! {prompt} !!!")
            file_path = input("请输入文件路径: ")
            
        if file_path:
            context[output_var] = file_path
            print(f"[FileDialog] Selected: {file_path}")
            return True
        else:
            print("[FileDialog] Cancelled or empty.")
            return False

class InputDialogAction(ActionBase):
    @property
    def name(self) -> str:
        return "打开输入对话框"
    
    @property
    def description(self) -> str:
        return "弹出输入对话框，并将结果保存到变量。"
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "prompt", "label": "标题/提示", "type": "string", "default": "请输入"},
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "input_value"}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        prompt = self.params.get("prompt", "请输入")
        output_var = self.params.get("output_variable", "input_value")
        
        print(f"[InputDialog] Prompt: {prompt}")
        
        root = get_tk_root()
        if root:
            value = simpledialog.askstring("输入", prompt)
            root.destroy()
        else:
            # Fallback to console input
            value = input(f"{prompt}: ")
            
        if value is not None:
            context[output_var] = value
            print(f"[InputDialog] Input: {value}")
            return True
        else:
            print("[InputDialog] Cancelled.")
            return False

class CalculateAction(ActionBase):
    @property
    def name(self) -> str:
        return "计算表达式"
    
    @property
    def description(self) -> str:
        return "执行 Python 表达式并将结果保存到变量。"
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "expression", "label": "表达式 (支持变量)", "type": "string"},
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "result"}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        expression = self.params.get("expression", "")
        output_var = self.params.get("output_variable", "result")
        
        try:
            # Safe-ish eval with context
            # We assume context values are safe or the user is trusted (local automation)
            result = eval(expression, {}, context)
            context[output_var] = result
            print(f"[Calculate] {expression} = {result}")
            return True
        except Exception as e:
            print(f"[Calculate] Error: {e}")
            return False

class PrintLogAction(ActionBase):
    @property
    def name(self) -> str:
        return "Print Log"

    @property
    def description(self) -> str:
        return "Prints a message to the console."

    def execute(self, context: Dict[str, Any]) -> bool:
        message = self.params.get("message", "")
        # Support variable interpolation from context
        try:
            # We use format, but handle potential key errors gracefully
            formatted_message = message.format(**context)
        except Exception:
            # If format fails (e.g. missing keys), print as is or partial
            # Simplest fallback:
            formatted_message = message
            
        print(f"[LOG]: {formatted_message}")
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "message", "type": "str", "label": "Message", "default": "Hello World"}
        ]

class DelayAction(ActionBase):
    @property
    def name(self) -> str:
        return "Delay"

    @property
    def description(self) -> str:
        return "Waits for a specified number of seconds."

    def execute(self, context: Dict[str, Any]) -> bool:
        seconds = self.params.get("seconds", 1)
        try:
            seconds = float(seconds)
        except ValueError:
            seconds = 1
            
        print(f"[DELAY]: Waiting for {seconds} seconds...")
        time.sleep(seconds)
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "seconds", "type": "float", "label": "Seconds to wait", "default": 1.0}
        ]

class SetVariableAction(ActionBase):
    @property
    def name(self) -> str:
        return "Set Variable"
        
    @property
    def description(self) -> str:
        return "Sets a variable in the context. Supports JSON for lists/dicts."
        
    def execute(self, context: Dict[str, Any]) -> bool:
        key = self.params.get("key")
        value = self.params.get("value")
        
        if not key:
            return False
            
        # Try to parse JSON if it looks like a structure
        real_value = value
        if isinstance(value, str):
            value_stripped = value.strip()
            if (value_stripped.startswith("[") and value_stripped.endswith("]")) or \
               (value_stripped.startswith("{") and value_stripped.endswith("}")):
                try:
                    real_value = json.loads(value)
                except json.JSONDecodeError:
                    pass # Keep as string
        
        context[key] = real_value
        print(f"[VAR]: Set {key} = {real_value} (Type: {type(real_value).__name__})")
        return True
        
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "key", "type": "str", "label": "Variable Name", "default": "my_var"},
            {"name": "value", "type": "str", "label": "Value (String or JSON)", "default": ""}
        ]
