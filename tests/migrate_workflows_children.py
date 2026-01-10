import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.workflow_manager import WorkflowManager, compute_logic_hierarchy


def strip_runtime_fields(steps):
    for s in steps:
        if not isinstance(s, dict):
            continue
        s.pop("line", None)
        s.pop("expanded", None)
        params = s.get("params")
        if isinstance(params, dict) and isinstance(params.get("children"), list):
            strip_runtime_fields(params["children"])
            params.pop("children", None)
            s["params"] = params
        if isinstance(s.get("children"), list):
            strip_runtime_fields(s["children"])


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


def migrate_one(manager, group, name):
    raw = manager.load_workflow(name, group)
    if not isinstance(raw, dict):
        print(f"SKIP {group}/{name}: invalid payload")
        return False
    steps = raw.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    try:
        normalized = compute_logic_hierarchy(steps, strict=True)
    except Exception as e:
        print(f"FAIL {group}/{name}: compute_logic_hierarchy failed: {e}")
        return False
    strip_runtime_fields(normalized)
    payload = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "steps": normalized,
    }
    ok = manager.save_workflow(name, group, payload)
    if ok:
        print(f"OK {group}/{name}")
    else:
        print(f"FAIL {group}/{name}: save failed")
    return ok


def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    workflows_dir = os.path.join(project_root, "workflows")
    manager = WorkflowManager(base_dir=workflows_dir)
    all_ok = True
    for group, name in iter_workflows(manager.base_dir):
        ok = migrate_one(manager, group, name)
        if not ok:
            all_ok = False
    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

