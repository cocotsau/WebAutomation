import os
import json
from typing import Dict, List, Any


LOGIC_LOOP_TOOLS = {"For循环", "Foreach循环", "Foreach字典循环", "While循环"}


def compute_logic_hierarchy(steps, strict: bool = False):
    if not isinstance(steps, list):
        return []

    if_tools = ("If 条件", "Else If 条件", "Else 否则")

    def detect_legacy_flat(step_list):
        n = len(step_list)
        i = 0
        while i < n:
            step = step_list[i]
            if not isinstance(step, dict):
                i += 1
                continue
            name = step.get("tool_name")
            params = step.get("params") or {}
            if not isinstance(params, dict):
                params = {}

            if name in LOGIC_LOOP_TOOLS:
                depth = 1
                j = i + 1
                while j < n:
                    s2 = step_list[j]
                    if not isinstance(s2, dict):
                        j += 1
                        continue
                    n2 = s2.get("tool_name")
                    p2 = s2.get("params") or {}
                    if not isinstance(p2, dict):
                        p2 = {}
                    if n2 in LOGIC_LOOP_TOOLS:
                        depth += 1
                    elif n2 == "EndMarker":
                        scope2 = p2.get("scope")
                        if scope2 in (None, "loop"):
                            depth -= 1
                            if depth == 0:
                                break
                    j += 1
                if depth != 0:
                    raise ValueError("检测到旧版循环结构：缺少循环结束标记或结构不完整")
                if j > i + 1:
                    raise ValueError("检测到旧版循环结构（依赖 EndMarker 包含循环体），请使用新版编辑器重保存该流程")

            if name == "If 条件":
                depth_if = 1
                j = i + 1
                while j < n:
                    s2 = step_list[j]
                    if not isinstance(s2, dict):
                        j += 1
                        continue
                    n2 = s2.get("tool_name")
                    p2 = s2.get("params") or {}
                    if not isinstance(p2, dict):
                        p2 = {}
                    if n2 == "If 条件":
                        depth_if += 1
                    elif n2 == "EndMarker" and p2.get("scope") == "if":
                        if depth_if == 1:
                            break
                        depth_if -= 1
                    else:
                        if depth_if == 1 and n2 not in if_tools and not (n2 == "EndMarker" and p2.get("scope") == "if"):
                            raise ValueError("检测到旧版 If/Else 结构（依赖 EndMarker 包含分支体），请使用新版编辑器重保存该流程")
                    j += 1
                if depth_if != 1 and j >= n:
                    raise ValueError("检测到旧版 If 结构缺少 End IF 标记或结构不完整")

            children_lists = []
            if isinstance(params.get("children"), list):
                children_lists.append(params.get("children") or [])
            if isinstance(step.get("children"), list):
                children_lists.append(step.get("children") or [])
            for child_list in children_lists:
                if child_list:
                    detect_legacy_flat(child_list)

            i += 1

    if strict:
        detect_legacy_flat(steps)

    def normalize(step_list):
        result: List[Dict[str, Any]] = []
        for step in step_list:
            if not isinstance(step, dict):
                continue
            name = step.get("tool_name")
            params = step.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            step["params"] = params

            if name in LOGIC_LOOP_TOOLS or name in if_tools:
                children_source: List[Dict[str, Any]] = []
                if isinstance(params.get("children"), list):
                    children_source = params.get("children") or []
                elif isinstance(step.get("children"), list):
                    children_source = step.get("children") or []
                normalized_children = normalize(children_source) if children_source else []
                params["children"] = normalized_children
                step["params"] = params
                if isinstance(step.get("children"), list):
                    step["children"] = []
            else:
                if isinstance(params.get("children"), list):
                    params["children"] = normalize(params.get("children") or [])
                    step["params"] = params
                if isinstance(step.get("children"), list):
                    step["children"] = normalize(step.get("children") or [])
            result.append(step)
        return result

    normalized = normalize(steps)

    def annotate_endmarker_scope(step_list):
        logic_stack: List[str] = []

        def walk(lst):
            for step in lst:
                if not isinstance(step, dict):
                    continue
                name = step.get("tool_name")
                params = step.get("params") or {}
                if not isinstance(params, dict):
                    params = {}
                if name in LOGIC_LOOP_TOOLS or name == "If 条件":
                    logic_stack.append(name)
                elif name == "EndMarker":
                    if logic_stack:
                        top = logic_stack[-1]
                        scope = params.get("scope")
                        if not scope:
                            if top in LOGIC_LOOP_TOOLS:
                                params["scope"] = "loop"
                            elif top == "If 条件":
                                params["scope"] = "if"
                            step["params"] = params
                        logic_stack.pop()
                children: List[Dict[str, Any]] = []
                if name in LOGIC_LOOP_TOOLS and isinstance(params.get("children"), list):
                    children = params.get("children") or []
                elif isinstance(step.get("children"), list):
                    children = step.get("children") or []
                if children:
                    walk(children)

        walk(step_list)

    annotate_endmarker_scope(normalized)

    if strict:
        if_stack: List[Dict[str, Any]] = []

        def validate_if_blocks(step_list: List[Dict[str, Any]]):
            for step in step_list:
                if not isinstance(step, dict):
                    continue
                name = step.get("tool_name")
                params = step.get("params") or {}
                if not isinstance(params, dict):
                    params = {}
                if name == "If 条件":
                    if_stack.append(step)
                elif name == "EndMarker" and params.get("scope") == "if":
                    if not if_stack:
                        raise ValueError("End IF 缺少对应的 IF 条件")
                    if_stack.pop()
                children: List[Dict[str, Any]] = []
                if isinstance(step.get("children"), list):
                    children = step.get("children") or []
                if name in LOGIC_LOOP_TOOLS and isinstance(params.get("children"), list):
                    children = params.get("children") or children
                if name in if_tools and isinstance(params.get("children"), list):
                    extra_children = params.get("children") or []
                    if extra_children:
                        children = (children or []) + extra_children
                if children:
                    validate_if_blocks(children)

        validate_if_blocks(normalized)
        if if_stack:
            raise ValueError("存在 IF 条件 没有匹配的 End IF")

    counter = [1]

    def assign_lines(step_list):
        for step in step_list:
            if not isinstance(step, dict):
                continue
            step["line"] = counter[0]
            counter[0] += 1
            name = step.get("tool_name")
            params = step.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            children: List[Dict[str, Any]] = []
            if name in LOGIC_LOOP_TOOLS and isinstance(params.get("children"), list):
                children = params.get("children") or []
            elif name in if_tools and isinstance(params.get("children"), list):
                children = params.get("children") or []
            elif isinstance(step.get("children"), list):
                children = step.get("children") or []
            if children:
                assign_lines(children)

    assign_lines(normalized)
    return normalized


class WorkflowManager:
    def __init__(self, base_dir="workflows"):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def save_workflow(self, name: str, group: str, data: Any) -> bool:
        """
        Save workflow data (dict payload) to a JSON file.
        Path: workflows/<group>/<name>.json
        """
        try:
            group_dir = os.path.join(self.base_dir, group)
            if not os.path.exists(group_dir):
                os.makedirs(group_dir)
            
            file_path = os.path.join(group_dir, f"{name}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving workflow: {e}")
            return False
    
    def load_workflow(self, name: str, group: str) -> Any:
        """
        Load raw workflow payload from a JSON file.
        """
        try:
            file_path = os.path.join(self.base_dir, group, f"{name}.json")
            if not os.path.exists(file_path):
                return {}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading workflow: {e}")
            return {}

    def load_for_editor(self, name: str, group: str) -> Dict[str, Any]:
        """
        Load workflow and normalize steps hierarchy for GUI editor.
        """
        raw = self.load_workflow(name, group)
        if not isinstance(raw, dict):
            return {}
        steps = raw.get("steps") or []
        if not isinstance(steps, list):
            steps = []
        raw["steps"] = compute_logic_hierarchy(steps, strict=True)
        return raw

    def save_from_editor(self, file_key: str, group: str, workflow_id: str, display_name: str, steps: List[Dict[str, Any]]) -> bool:
        """
        Save editor steps after normalizing logic hierarchy.
        Line numbers are kept only in memory and stripped before persisting.
        """
        try:
            normalized_steps = compute_logic_hierarchy(steps, strict=True)
        except Exception as e:
            print("[SaveDebug] compute_logic_hierarchy failed:", e)

            def debug_steps(step_list: List[Dict[str, Any]], depth: int = 0) -> None:
                for step in step_list:
                    if not isinstance(step, dict):
                        continue
                    name = step.get("tool_name")
                    params = step.get("params") or {}
                    if not isinstance(params, dict):
                        params = {}
                    scope = params.get("scope")
                    children_field = step.get("children") or []
                    param_children = params.get("children") if isinstance(params.get("children"), list) else []
                    indent = "  " * depth
                    print(f"[SaveDebug] {indent}- name={name}, scope={scope}, children_field={len(children_field)}, param_children={len(param_children) if isinstance(param_children, list) else 0}")
                    if isinstance(children_field, list) and children_field:
                        debug_steps(children_field, depth + 1)
                    if isinstance(param_children, list) and param_children:
                        debug_steps(param_children, depth + 1)

            print("[SaveDebug] Steps snapshot before failure:")
            if isinstance(steps, list):
                debug_steps(steps, 0)
            raise

        def strip_lines(step_list: List[Dict[str, Any]]) -> None:
            for s in step_list:
                if "line" in s:
                    s.pop("line", None)
                params = s.get("params")
                if isinstance(params, dict) and isinstance(params.get("children"), list):
                    strip_lines(params["children"])
                if isinstance(s.get("children"), list):
                    strip_lines(s["children"])

        strip_lines(normalized_steps)

        payload: Dict[str, Any] = {
            "id": workflow_id,
            "name": display_name,
            "steps": normalized_steps
        }
        return self.save_workflow(file_key, group, payload)

    def list_workflows(self) -> Dict[str, List[str]]:
        """
        List all workflows grouped by folder.
        Returns: {"Group1": ["Workflow1", "Workflow2"], ...}
        """
        result = {}
        if not os.path.exists(self.base_dir):
            return result

        for group_name in os.listdir(self.base_dir):
            group_path = os.path.join(self.base_dir, group_name)
            if os.path.isdir(group_path):
                workflows = []
                for file_name in os.listdir(group_path):
                    if file_name.endswith(".json") and not file_name.endswith(".elements.json"):
                        workflows.append(file_name[:-5])  # Remove .json
                if workflows:
                    result[group_name] = workflows
        return result

    def delete_workflow(self, name: str, group: str) -> bool:
        """
        Delete a workflow file.
        """
        try:
            if not isinstance(name, str) or not isinstance(group, str):
                print("Error deleting workflow: name/group must be strings")
                return False
            file_path = os.path.join(self.base_dir, group, f"{name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                
                # Remove group dir if empty
                group_dir = os.path.join(self.base_dir, group)
                if not os.listdir(group_dir):
                    os.rmdir(group_dir)
                return True
            return False
        except Exception as e:
            print(f"Error deleting workflow: {e}")
            return False

    def get_all_groups(self) -> List[str]:
        """
        Get a list of all existing groups.
        """
        if not os.path.exists(self.base_dir):
            return []
        return [d for d in os.listdir(self.base_dir) if os.path.isdir(os.path.join(self.base_dir, d))]
