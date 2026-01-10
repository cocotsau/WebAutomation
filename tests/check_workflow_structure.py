import os
import sys
import json
import copy

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.workflow_manager import WorkflowManager, compute_logic_hierarchy, LOGIC_LOOP_TOOLS


def build_tree_view(steps):
    result = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        step = copy.deepcopy(s)
        step.pop("line", None)
        name = step.get("tool_name")
        params = step.get("params") or {}
        children_for_tree = []
        if_tools = {"If 条件", "Else If 条件", "Else 否则"}
        if name in LOGIC_LOOP_TOOLS and isinstance(params.get("children"), list):
            children_for_tree = params.get("children") or []
        elif name in if_tools and isinstance(params.get("children"), list):
            children_for_tree = params.get("children") or []
        elif isinstance(step.get("children"), list):
            children_for_tree = step.get("children") or []
        step["children"] = build_tree_view(children_for_tree)
        result.append(step)
    return result


def strip_runtime_fields(steps):
    for s in steps:
        if not isinstance(s, dict):
            continue
        s.pop("line", None)
        s.pop("expanded", None)
        params = s.get("params")
        if isinstance(params, dict) and isinstance(params.get("children"), list):
            strip_runtime_fields(params["children"])
        if isinstance(s.get("children"), list):
            strip_runtime_fields(s["children"])


def canonical_copy(steps):
    clone = copy.deepcopy(steps)
    strip_runtime_fields(clone)
    return clone


def iter_workflows(base_dir):
    for group in os.listdir(base_dir):
        group_path = os.path.join(base_dir, group)
        if not os.path.isdir(group_path):
            continue
        for fname in os.listdir(group_path):
            if not fname.endswith(".json"):
                continue
            if fname.endswith(".elements.json"):
                continue
            yield group, fname[:-5]


def debug_tree(prefix, group, name, steps):
    def walk(step_list, depth=0):
        indent = "  " * depth
        for s in step_list:
            if not isinstance(s, dict):
                continue
            tool = s.get("tool_name")
            params = s.get("params") or {}
            scope = None
            if isinstance(params, dict):
                scope = params.get("scope")
            children = s.get("children") or []
            print(f"{prefix} {group}/{name} {indent}- name={tool}, scope={scope}, children={len(children)}")
            if children:
                walk(children, depth + 1)
    print(f"{prefix} {group}/{name} begin")
    walk(steps, 0)
    print(f"{prefix} {group}/{name} end")


def check_workflow(manager, group, name):
    try:
        raw = manager.load_for_editor(name, group)
    except Exception as e:
        print(f"FAIL {group}/{name}: 加载流程失败: {e}")
        return False
    if not isinstance(raw, dict):
        print(f"SKIP {group}/{name}: invalid payload")
        return True
    steps_editor = raw.get("steps") or []
    if not isinstance(steps_editor, list):
        steps_editor = []
    baseline = steps_editor
    tree_view = build_tree_view(baseline)
    debug_tree("[GUIView]", group, name, tree_view)
    try:
        normalized_from_gui = compute_logic_hierarchy(tree_view, strict=True)
    except Exception as e:
        print(f"FAIL {group}/{name}: GUI 结构规范化失败: {e}")
        return False
    a = canonical_copy(baseline)
    b = canonical_copy(normalized_from_gui)
    if a == b:
        print(f"OK {group}/{name}")
        return True
    print(f"FAIL {group}/{name}")
    print("from_file:")
    print(json.dumps(a, ensure_ascii=False, indent=2))
    print("from_gui:")
    print(json.dumps(b, ensure_ascii=False, indent=2))
    return False


def run_gui_to_json_check(manager: WorkflowManager):
    base_dir = getattr(manager, "base_dir", os.path.join("workflows"))
    if not os.path.exists(base_dir):
        return True, []
    all_ok = True
    failed = []
    for group, name in iter_workflows(base_dir):
        ok = check_workflow(manager, group, name)
        if not ok:
            all_ok = False
            failed.append(f"{group}/{name}")
    return all_ok, failed


def reconstruct_gui_view_from_json(manager: WorkflowManager, group: str, name: str):
    """
    反向检查：仅根据磁盘上的 JSON 还原出“GUI 应该显示的树形结构”并打印。
    用途：
      - 当你在 GUI 中看到的 Steps 与磁盘 JSON 不一致时，
        可以运行本函数，看看纯粹根据 JSON 推导出的 GUI 结构长什么样，
        再和 GUI 里的 [Steps] / [GUI-Tree] 日志对比。
    """
    raw = manager.load_workflow(name, group)
    if not isinstance(raw, dict):
        print(f"[ReverseGUI] {group}/{name}: invalid payload")
        return
    steps_file = raw.get("steps") or []
    if not isinstance(steps_file, list):
        steps_file = []
    try:
        normalized = compute_logic_hierarchy(steps_file, strict=True)
    except Exception as e:
        print(f"[ReverseGUI] {group}/{name}: compute_logic_hierarchy on file failed: {e}")
        return

    tree_view = build_tree_view(normalized)

    def debug_steps(step_list, depth=0):
        indent = "  " * depth
        for s in step_list:
            if not isinstance(s, dict):
                continue
            name = s.get("tool_name")
            params = s.get("params") or {}
            scope = params.get("scope")
            children = s.get("children") or []
            print(f"[ReverseGUI] {indent}- name={name}, scope={scope}, children={len(children)}")
            if children:
                debug_steps(children, depth + 1)

    print(f"[ReverseGUI] {group}/{name} begin")
    debug_steps(tree_view, 0)
    print(f"[ReverseGUI] {group}/{name} end")


def compare_file_vs_gui(manager: WorkflowManager, group: str, name: str, gui_steps):
    if not isinstance(gui_steps, list):
        gui_steps = []
    try:
        raw = manager.load_workflow(name, group)
    except Exception as e:
        print(f"[ReverseCompare] {group}/{name}: load_workflow failed: {e}")
        return False
    if not isinstance(raw, dict):
        print(f"[ReverseCompare] {group}/{name}: invalid payload")
        return False
    steps_file = raw.get("steps") or []
    if not isinstance(steps_file, list):
        steps_file = []
    try:
        normalized_file = compute_logic_hierarchy(steps_file, strict=True)
    except Exception as e:
        print(f"[ReverseCompare] {group}/{name}: compute_logic_hierarchy on file failed: {e}")
        return False
    try:
        normalized_gui = compute_logic_hierarchy(gui_steps, strict=True)
    except Exception as e:
        print(f"[ReverseCompare] {group}/{name}: compute_logic_hierarchy on gui failed: {e}")
        return False
    a = canonical_copy(normalized_file)
    b = canonical_copy(normalized_gui)
    if a == b:
        print(f"OK {group}/{name}")
        return True
    print(f"FAIL {group}/{name}")
    print("from_file:")
    print(json.dumps(a, ensure_ascii=False, indent=2))
    print("from_gui:")
    print(json.dumps(b, ensure_ascii=False, indent=2))
    return False


def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    workflows_dir = os.path.join(project_root, "workflows")
    manager = WorkflowManager(base_dir=workflows_dir)
    # 如果带两个参数执行：python check_workflow_structure.py <Group> <Name>
    # 则只对单个流程做反向 GUI 结构打印，方便调试。
    if len(sys.argv) == 3:
        group = sys.argv[1]
        name = sys.argv[2]
        reconstruct_gui_view_from_json(manager, group, name)
        return

    all_ok = True
    for group, name in iter_workflows(manager.base_dir):
        ok = check_workflow(manager, group, name)
        if not ok:
            all_ok = False
    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
