from typing import Dict, Any, List
from core.action_base import ActionBase
from core.flow_control import BreakLoopException, ContinueLoopException
import time


def _resolve_operand(val: Any, context: Dict[str, Any]) -> Any:
    if isinstance(val, str):
        raw = val.strip()
        if raw.startswith("{") and raw.endswith("}"):
            name = raw[1:-1]
            return context.get(name)
        if raw in context:
            return context.get(raw)
        lower = raw.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        if lower in ("none", "null"):
            return None
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except Exception:
            pass
    return val


def _evaluate_relation(left: Any, op: str, right: Any, context: Dict[str, Any]) -> bool:
    lv = _resolve_operand(left, context)
    rv = _resolve_operand(right, context)
    try:
        if op == "等于":
            return lv == rv
        if op == "不等于":
            return lv != rv
        if op == "大于":
            return lv > rv
        if op == "大于等于":
            return lv >= rv
        if op == "小于":
            return lv < rv
        if op == "小于等于":
            return lv <= rv
        if op == "包含":
            try:
                return rv in lv
            except Exception:
                return str(rv) in str(lv)
        if op == "不包含":
            try:
                return rv not in lv
            except Exception:
                return str(rv) not in str(lv)
        if op == "等于True":
            return bool(lv) is True
        if op == "等于False":
            return bool(lv) is False
        if op == "是空值":
            return lv is None or lv == "" or lv == []
        if op == "不是空值":
            return not (lv is None or lv == "" or lv == [])
    except Exception as e:
        print(f"[Logic] Relation eval error ({op}): {e}")
        return False
    return False


class LoopAction(ActionBase):
    @property
    def name(self) -> str:
        return "Loop"

    @property
    def description(self) -> str:
        return "Executes child steps a specific number of times."

    def execute(self, context: Dict[str, Any]) -> bool:
        children = self.params.get("children", [])
        runner = context.get("__runner__")
        if not runner:
            print("[Loop] Error: No runner found in context.")
            return False
        index_name = self.params.get("index_variable", "loop_index")

        start_raw = self.params.get("start")
        end_raw = self.params.get("end")
        step_raw = self.params.get("step")

        use_range = any(str(self.params.get(k, "")).strip() for k in ("start", "end", "step"))
        if use_range:
            start = _resolve_operand(start_raw if start_raw is not None else 0, context)
            end = _resolve_operand(end_raw if end_raw is not None else 0, context)
            step = _resolve_operand(step_raw if step_raw is not None else 1, context)
            try:
                start = int(start)
                end = int(end)
                step = int(step)
            except Exception:
                print(f"[Loop] Invalid range values: start={start_raw}, end={end_raw}, step={step_raw}")
                return False
            if step == 0:
                print("[Loop] Step cannot be 0.")
                return False
            print(f"[Loop] Range loop from {start} to {end} step {step}.")
            current = start
            i = 0
            while (step > 0 and current <= end) or (step < 0 and current >= end):
                print(f"[Loop] Iteration {i+1}, value={current}")
                context[index_name] = current
                try:
                    if not runner(children, context):
                        return False
                except BreakLoopException:
                    print(f"[Loop] Break at value {current}")
                    break
                except ContinueLoopException:
                    print(f"[Loop] Continue at value {current}")
                current += step
                i += 1
        else:
            count = int(self.params.get("count", 1))
            print(f"[Loop] Starting loop {count} times.")
            for i in range(count):
                print(f"[Loop] Iteration {i+1}/{count}")
                context[index_name] = i
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
            {"name": "start", "type": "str", "label": "起始数", "default": "0", "variable_type": "一般变量", "is_variable": True},
            {"name": "end", "type": "str", "label": "结束数", "default": "10", "variable_type": "一般变量", "is_variable": True},
            {"name": "step", "type": "str", "label": "递增值", "default": "1", "variable_type": "一般变量", "is_variable": True},
            {"name": "index_variable", "type": "str", "label": "索引变量名", "default": "loop_index", "variable_type": "循环变量", "is_variable": True, "advanced": True},
            {"name": "count", "type": "int", "label": "循环次数(兼容旧版)", "default": 1, "advanced": True},
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
        item_name = self.params.get("item_variable", "loop_item")
        index_name = self.params.get("index_variable", "loop_index")
        expose_index = bool(self.params.get("expose_index", True))
        children = self.params.get("children", [])
        runner = context.get("__runner__")

        if not runner:
            return False
            
        list_var_name = var_name
        if isinstance(list_var_name, str) and list_var_name.startswith("{") and list_var_name.endswith("}"):
            list_var_name = list_var_name[1:-1]

        data_list = context.get(list_var_name, [])
        if not isinstance(data_list, list):
            print(f"[ForEach] Error: Variable '{var_name}' is not a list or not found.")
            return False

        print(f"[ForEach] Iterating over {var_name} ({len(data_list)} items).")
        for i, item in enumerate(data_list):
            print(f"[ForEach] Item {i+1}: {item}")
            context[item_name] = item
            if expose_index:
                context[index_name] = i
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
            {"name": "list_variable", "type": "str", "label": "循环列表", "default": "my_list", "variable_type": "一般变量", "is_variable": True},
            {"name": "expose_index", "type": "bool", "label": "输出循环项的位置", "default": True},
            {"name": "item_variable", "type": "str", "label": "循环项变量名", "default": "loop_item", "variable_type": "循环项", "is_variable": True, "advanced": True},
            {"name": "index_variable", "type": "str", "label": "索引变量名", "default": "loop_index", "variable_type": "循环变量", "is_variable": True, "advanced": True},
        ]


class ForEachDictAction(ActionBase):
    @property
    def name(self) -> str:
        return "For Each Dict"

    @property
    def description(self) -> str:
        return "Iterates over a dict variable."

    def execute(self, context: Dict[str, Any]) -> bool:
        var_name = self.params.get("dict_variable")
        key_name = self.params.get("key_variable", "loop_key")
        value_name = self.params.get("value_variable", "loop_value")
        children = self.params.get("children", [])
        runner = context.get("__runner__")

        if not runner:
            return False

        dict_var_name = var_name
        if isinstance(dict_var_name, str) and dict_var_name.startswith("{") and dict_var_name.endswith("}"):
            dict_var_name = dict_var_name[1:-1]

        data_dict = context.get(dict_var_name, {})
        if not isinstance(data_dict, dict):
            print(f"[ForEachDict] Error: Variable '{var_name}' is not a dict or not found.")
            return False

        print(f"[ForEachDict] Iterating over {var_name} ({len(data_dict)} items).")
        for k, v in data_dict.items():
            print(f"[ForEachDict] Item key={k}, value={v}")
            context[key_name] = k
            context[value_name] = v
            try:
                if not runner(children, context):
                    return False
            except BreakLoopException:
                print(f"[ForEachDict] Break triggered at key {k}")
                break
            except ContinueLoopException:
                print(f"[ForEachDict] Continue triggered at key {k}")
                continue

        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "dict_variable", "type": "str", "label": "循环字典", "default": "my_dict", "variable_type": "一般变量", "is_variable": True},
            {"name": "key_variable", "type": "str", "label": "键名变量", "default": "loop_key", "variable_type": "循环项", "is_variable": True, "advanced": True},
            {"name": "value_variable", "type": "str", "label": "键值变量", "default": "loop_value", "variable_type": "循环项", "is_variable": True, "advanced": True},
        ]

class WhileAction(ActionBase):
    @property
    def name(self) -> str:
        return "While"

    @property
    def description(self) -> str:
        return "Executes steps while a condition is true."

    def execute(self, context: Dict[str, Any]) -> bool:
        children = self.params.get("children", [])
        runner = context.get("__runner__")
        max_loops = int(self.params.get("max_loops", 1000))
        if not runner:
            return False

        left = self.params.get("left")
        relation = self.params.get("relation")
        right = self.params.get("right")
        condition_expr = self.params.get("condition")

        use_structured = bool(relation)
        loops = 0
        print("[While] Starting loop.")
        while True:
            if loops >= max_loops:
                print("[While] Max loops reached, breaking.")
                break

            if use_structured:
                result = _evaluate_relation(left, relation, right, context)
            elif condition_expr:
                try:
                    result = eval(condition_expr, {}, context)
                except Exception as e:
                    print(f"[While] Condition error: {e}")
                    return False
            else:
                result = False

            if not result:
                break

            context['loop_index'] = loops
            loops += 1

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
        relations = [
            "等于", "不等于",
            "大于", "大于等于",
            "小于", "小于等于",
            "包含", "不包含",
            "等于True", "等于False",
            "是空值", "不是空值",
        ]
        return [
            {"name": "left", "type": "str", "label": "对象1", "default": "", "variable_type": "一般变量", "is_variable": True},
            {"name": "relation", "type": "str", "label": "关系", "default": "等于", "options": relations},
            {
                "name": "right",
                "type": "str",
                "label": "对象2",
                "default": "",
                "variable_type": "一般变量",
                "is_variable": True,
                "enable_if": {
                    "relation": [
                        "等于", "不等于",
                        "大于", "大于等于",
                        "小于", "小于等于",
                        "包含", "不包含",
                    ]
                }
            },
            {"name": "max_loops", "type": "int", "label": "最大循环次数(安全)", "default": 1000, "advanced": True},
            {"name": "condition", "type": "str", "label": "兼容旧版条件表达式", "default": "True", "advanced": True},
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
        children = self.params.get("children", [])
        runner = context.get("__runner__")

        left = self.params.get("left")
        relation = self.params.get("relation")
        right = self.params.get("right")
        condition = self.params.get("condition")

        use_structured = bool(relation)
        if use_structured:
            result = _evaluate_relation(left, relation, right, context)
            print(f"[If] Relation '{left} {relation} {right}' evaluated to {result}")
        elif condition:
            try:
                result = eval(condition, {}, context)
            except Exception as e:
                print(f"[If] Condition error: {e}")
                result = False
            print(f"[If] Condition '{condition}' evaluated to {result}")
        else:
            result = False

        if result and runner:
            if not runner(children, context):
                context['_last_if_result'] = bool(result)
                return False

        context['_last_if_result'] = bool(result)
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        relations = [
            "等于", "不等于",
            "大于", "大于等于",
            "小于", "小于等于",
            "包含", "不包含",
            "等于True", "等于False",
            "是空值", "不是空值",
        ]
        return [
            {"name": "left", "type": "str", "label": "对象1", "default": "", "variable_type": "一般变量", "is_variable": True},
            {"name": "relation", "type": "str", "label": "关系", "default": "等于", "options": relations},
            {
                "name": "right",
                "type": "str",
                "label": "对象2",
                "default": "",
                "variable_type": "一般变量",
                "is_variable": True,
                "enable_if": {
                    "relation": [
                        "等于", "不等于",
                        "大于", "大于等于",
                        "小于", "小于等于",
                        "包含", "不包含",
                    ]
                }
            },
            {"name": "condition", "type": "str", "label": "兼容旧版条件表达式", "default": "True", "advanced": True},
        ]

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

        left = self.params.get("left")
        relation = self.params.get("relation")
        right = self.params.get("right")
        condition = self.params.get("condition")
        children = self.params.get("children", [])
        runner = context.get("__runner__")

        use_structured = bool(relation)
        if use_structured:
            result = _evaluate_relation(left, relation, right, context)
            print(f"[ElseIf] Relation '{left} {relation} {right}' evaluated to {result}")
        elif condition:
            try:
                result = eval(condition, {}, context)
            except Exception as e:
                print(f"[ElseIf] Condition error: {e}")
                result = False
            print(f"[ElseIf] Condition '{condition}' evaluated to {result}")
        else:
            result = False

        if result and runner:
            if not runner(children, context):
                context['_last_if_result'] = bool(result)
                return False

        context['_last_if_result'] = bool(result)
        return True

    def get_param_schema(self) -> List[Dict[str, Any]]:
        relations = [
            "等于", "不等于",
            "大于", "大于等于",
            "小于", "小于等于",
            "包含", "不包含",
            "等于True", "等于False",
            "是空值", "不是空值",
        ]
        return [
            {"name": "left", "type": "str", "label": "对象1", "default": "", "variable_type": "一般变量", "is_variable": True},
            {"name": "relation", "type": "str", "label": "关系", "default": "等于", "options": relations},
            {
                "name": "right",
                "type": "str",
                "label": "对象2",
                "default": "",
                "variable_type": "一般变量",
                "is_variable": True,
                "enable_if": {
                    "relation": [
                        "等于", "不等于",
                        "大于", "大于等于",
                        "小于", "小于等于",
                        "包含", "不包含",
                    ]
                }
            },
            {"name": "condition", "type": "str", "label": "兼容旧版条件表达式", "default": "True", "advanced": True},
        ]

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
