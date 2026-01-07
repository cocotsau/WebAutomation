import time
import json
from typing import Dict, Any, List
from core.action_base import ActionBase

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
