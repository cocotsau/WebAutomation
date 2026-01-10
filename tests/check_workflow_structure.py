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


def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    workflows_dir = os.path.join(project_root, "workflows")
    manager = WorkflowManager(base_dir=workflows_dir)
    all_ok = True
    for group, name in iter_workflows(manager.base_dir):
        ok = check_workflow(manager, group, name)
        if not ok:
            all_ok = False
    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
