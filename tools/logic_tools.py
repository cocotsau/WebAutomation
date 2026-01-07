from typing import Dict, Any, List
from core.action_base import ActionBase
import time

class LoopAction(ActionBase):
    @property
    def name(self) -> str:
        return "Loop"

    @property
    def description(self) -> str:
        return "Executes child steps a specific number of times."

    def execute(self, context: Dict[str, Any]) -> bool:
        count = int(self.params.get("count", 1))
        children = self.params.get("children", [])
        runner = context.get("__runner__")
        
        if not runner:
            print("[Loop] Error: No runner found in context.")
            return False

        print(f"[Loop] Starting loop {count} times.")
        for i in range(count):
            print(f"[Loop] Iteration {i+1}/{count}")
            # Inject loop index into context if needed, e.g., 'loop_index'
            context['loop_index'] = i
            if not runner(children, context):
                return False
        
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "count", "type": "int", "label": "Iterations", "default": 3}
        ]

class ForEachAction(ActionBase):
    @property
    def name(self) -> str:
        return "For Each"

    @property
    def description(self) -> str:
        return "Iterates over a list variable."

    def execute(self, context: Dict[str, Any]) -> bool:
        var_name = self.params.get("list_variable")
        item_name = self.params.get("item_variable", "item")
        children = self.params.get("children", [])
        runner = context.get("__runner__")

        if not runner:
            return False
            
        # Get list from context
        data_list = context.get(var_name, [])
        if not isinstance(data_list, list):
            print(f"[ForEach] Error: Variable '{var_name}' is not a list or not found.")
            return False

        print(f"[ForEach] Iterating over {var_name} ({len(data_list)} items).")
        for i, item in enumerate(data_list):
            print(f"[ForEach] Item {i+1}: {item}")
            context[item_name] = item
            context['loop_index'] = i
            if not runner(children, context):
                return False
                
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "list_variable", "type": "str", "label": "List Variable Name", "default": "my_list"},
            {"name": "item_variable", "type": "str", "label": "Item Variable Name", "default": "item"}
        ]

class WhileAction(ActionBase):
    @property
    def name(self) -> str:
        return "While"

    @property
    def description(self) -> str:
        return "Executes steps while a condition is true."

    def execute(self, context: Dict[str, Any]) -> bool:
        condition_expr = self.params.get("condition", "False")
        children = self.params.get("children", [])
        runner = context.get("__runner__")
        max_loops = int(self.params.get("max_loops", 1000)) # Safety break

        if not runner:
            return False

        print(f"[While] Starting loop with condition: {condition_expr}")
        loops = 0
        while True:
            if loops >= max_loops:
                print("[While] Max loops reached, breaking.")
                break
                
            # Evaluate condition
            # WARNING: eval is dangerous. In a real app, use a safe expression parser.
            # For this demo, we assume local trust.
            try:
                # Make context variables available to eval
                is_true = eval(condition_expr, {}, context)
            except Exception as e:
                print(f"[While] Condition error: {e}")
                return False
                
            if not is_true:
                print("[While] Condition false, ending loop.")
                break
                
            print(f"[While] Iteration {loops+1}")
            if not runner(children, context):
                return False
            
            loops += 1
            
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "condition", "type": "str", "label": "Condition (Python expr)", "default": "True"},
            {"name": "max_loops", "type": "int", "label": "Max Loops (Safety)", "default": 100}
        ]
