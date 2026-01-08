from typing import Dict, Any, List
from core.action_base import ActionBase
from core.flow_control import BreakLoopException, ContinueLoopException
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
            context['loop_index'] = i
            try:
                if not runner(children, context):
                    return False
            except BreakLoopException:
                print(f"[Loop] Break triggered at iteration {i+1}")
                break
            except ContinueLoopException:
                print(f"[Loop] Continue triggered at iteration {i+1}")
                continue
        
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
            
        data_list = context.get(var_name, [])
        if not isinstance(data_list, list):
            print(f"[ForEach] Error: Variable '{var_name}' is not a list or not found.")
            return False

        print(f"[ForEach] Iterating over {var_name} ({len(data_list)} items).")
        for i, item in enumerate(data_list):
            print(f"[ForEach] Item {i+1}: {item}")
            context[item_name] = item
            context['loop_index'] = i
            try:
                if not runner(children, context):
                    return False
            except BreakLoopException:
                print(f"[ForEach] Break triggered at index {i}")
                break
            except ContinueLoopException:
                print(f"[ForEach] Continue triggered at index {i}")
                continue
                
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
        max_loops = int(self.params.get("max_loops", 1000))

        if not runner:
            return False

        print(f"[While] Starting loop with condition: {condition_expr}")
        loops = 0
        while True:
            if loops >= max_loops:
                print("[While] Max loops reached, breaking.")
                break
                
            try:
                result = eval(condition_expr, {}, context)
            except Exception as e:
                print(f"[While] Condition error: {e}")
                return False
                
            if not result:
                break
                
            loops += 1
            context['loop_index'] = loops - 1
            
            try:
                if not runner(children, context):
                    return False
            except BreakLoopException:
                print("[While] Break triggered")
                break
            except ContinueLoopException:
                print("[While] Continue triggered")
                continue
                
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "condition", "type": "str", "label": "Condition (Python Expr)", "default": "True"},
            {"name": "max_loops", "type": "int", "label": "Max Loops (Safety)", "default": 1000}
        ]

class BreakAction(ActionBase):
    @property
    def name(self) -> str: return "Break"
    @property
    def description(self) -> str: return "Breaks out of the current loop."
    def execute(self, context: Dict[str, Any]) -> bool:
        raise BreakLoopException()

class ContinueAction(ActionBase):
    @property
    def name(self) -> str: return "Continue"
    @property
    def description(self) -> str: return "Skips to the next iteration of the current loop."
    def execute(self, context: Dict[str, Any]) -> bool:
        raise ContinueLoopException()

class IfAction(ActionBase):
    @property
    def name(self) -> str: return "If"
    @property
    def description(self) -> str: return "Executes children if condition is true."
    def execute(self, context: Dict[str, Any]) -> bool:
        condition = self.params.get("condition", "False")
        children = self.params.get("children", [])
        runner = context.get("__runner__")
        
        try:
            result = eval(condition, {}, context)
        except Exception as e:
            print(f"[If] Condition error: {e}")
            result = False
            
        print(f"[If] Condition '{condition}' evaluated to {result}")
        
        if result and runner:
            if not runner(children, context):
                # We do not return False here if children fail? 
                # If children fail, runner returns False. 
                # Engine usually stops on failure.
                # So we should return False too.
                context['_last_if_result'] = bool(result)
                return False
                
        context['_last_if_result'] = bool(result)
        return True
        
    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [{"name": "condition", "type": "str", "label": "Condition (Python Expr)", "default": "True"}]

class ElseIfAction(ActionBase):
    @property
    def name(self) -> str: return "ElseIf"
    @property
    def description(self) -> str: return "Executes children if previous conditions were false and this condition is true."
    def execute(self, context: Dict[str, Any]) -> bool:
        last_result = context.get('_last_if_result')
        
        if last_result:
            print("[ElseIf] Skipped because previous block was True")
            context['_last_if_result'] = True
            return True
            
        condition = self.params.get("condition", "False")
        children = self.params.get("children", [])
        runner = context.get("__runner__")
        
        try:
            result = eval(condition, {}, context)
        except Exception as e:
            print(f"[ElseIf] Condition error: {e}")
            result = False
            
        print(f"[ElseIf] Condition '{condition}' evaluated to {result}")
        
        if result and runner:
            if not runner(children, context):
                context['_last_if_result'] = bool(result)
                return False
            
        context['_last_if_result'] = bool(result)
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [{"name": "condition", "type": "str", "label": "Condition (Python Expr)", "default": "True"}]

class ElseAction(ActionBase):
    @property
    def name(self) -> str: return "Else"
    @property
    def description(self) -> str: return "Executes children if previous conditions were false."
    def execute(self, context: Dict[str, Any]) -> bool:
        last_result = context.get('_last_if_result')
        
        if last_result:
            print("[Else] Skipped because previous block was True")
            context['_last_if_result'] = True
            return True
            
        print("[Else] Executing else block")
        children = self.params.get("children", [])
        runner = context.get("__runner__")
        
        if runner:
            if not runner(children, context):
                context['_last_if_result'] = True
                return False
            
        context['_last_if_result'] = True
        return True
