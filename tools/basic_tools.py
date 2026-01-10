import time
import json
import tkinter as tk
from tkinter import filedialog, simpledialog
from typing import Dict, Any, List
from core.action_base import ActionBase
import re
from core.exit_flow import ExitFlowException

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
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "file_path", "variable_type": "一般变量", "is_variable": True}
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
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "input_value", "variable_type": "一般变量", "is_variable": True}
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
            {"name": "output_variable", "label": "保存到变量", "type": "string", "default": "result", "variable_type": "一般变量", "is_variable": True}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        expression = self.params.get("expression", "")
        output_var = self.params.get("output_variable", "result")
        
        try:
            result = eval(expression, {}, context)
            context[output_var] = result
            print(f"[Calculate] {expression} = {result}")
            return True
        except Exception as e:
            print(f"[Calculate] Error: {e}")
            return False


class ExecutePythonCodeAction(ActionBase):
    @property
    def name(self) -> str:
        return "执行 Python 代码段"
    
    @property
    def description(self) -> str:
        return "执行 Python 代码段，可访问和修改流程变量。"
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "code", "label": "Python 代码段", "type": "text", "default": ""},
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        code = self.params.get("code", "")
        if not isinstance(code, str):
            code = str(code)
        try:
            pattern = re.compile(r"\{([\w]+)\}")
            processed = pattern.sub(lambda m: m.group(1), code)
        except Exception:
            processed = code
        try:
            exec(processed, {}, context)
            return True
        except Exception as e:
            print(f"[ExecutePythonCode] Error: {e}")
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


class CommentAction(ActionBase):
    @property
    def name(self) -> str:
        return "备注"
    
    @property
    def description(self) -> str:
        return "仅用于在流程中添加说明，不参与执行。"
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "text", "label": "备注内容", "type": "text", "default": ""},
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        return True

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


class ExitProgramAction(ActionBase):
    @property
    def name(self) -> str:
        return "退出程序"
    
    @property
    def description(self) -> str:
        return "立即结束整个流程，可设置退出码(0=正常,1=异常)。"
    
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "exit_code", "type": "int", "label": "退出码(0=正常,1=异常)", "default": 0}
        ]
    
    def execute(self, context: Dict[str, Any]) -> bool:
        code = self.params.get("exit_code", 0)
        try:
            code = int(code)
        except Exception:
            code = 0
        raise ExitFlowException(code)

class SetVariableAction(ActionBase):
    @property
    def name(self) -> str:
        return "设置变量"
        
    @property
    def description(self) -> str:
        return "设置上下文中的变量，支持多种数据类型。"
        
    def execute(self, context: Dict[str, Any]) -> bool:
        output_var = self.params.get("output_variable")
        value = self.params.get("value")
        value_type = self.params.get("value_type", "string")
        
        if not output_var:
            return False
        
        real_value = value
        if isinstance(value, str):
            text = value.strip()
            if value_type == "string":
                real_value = value
            elif value_type == "int":
                try:
                    real_value = int(text)
                except Exception:
                    real_value = 0
            elif value_type == "float":
                try:
                    real_value = float(text)
                except Exception:
                    real_value = 0.0
            elif value_type == "bool":
                lowered = text.lower()
                real_value = lowered in ("1", "true", "yes", "y", "on")
            elif value_type in ("list", "dict", "any"):
                try:
                    import ast
                    real_value = ast.literal_eval(text)
                except Exception:
                    real_value = value
        context[output_var] = real_value
        print(f"[VAR]: Set {output_var} = {real_value} (Type: {type(real_value).__name__})")
        return True
        
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "output_variable", "type": "str", "label": "变量名", "default": "my_var", "variable_type": "一般变量", "is_variable": True},
            {"name": "value_type", "type": "str", "label": "数据类型", "default": "string", "options": ["string", "int", "float", "bool", "list", "dict", "any"]},
            {"name": "value", "type": "str", "label": "变量值", "default": ""}
        ]
