import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple


class ElementManager:
    def __init__(self, file_path: Optional[str] = None):
        """
        Initialize ElementManager.
        :param file_path: Path to the elements JSON file. If None, it operates in memory only until saved.
        """
        self.file_path = file_path
        self._data_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._is_loaded = False
        self.workflow_id: Optional[str] = None
        self.workflow_name: Optional[str] = None
        
        if self.file_path:
            self.reload()

    def set_file_path(self, file_path: str, load_now: bool = True):
        """Switch to a different element file."""
        self.file_path = file_path
        if load_now:
            self.reload()
        else:
            self._data_cache = {}
            self._is_loaded = False

    def set_workflow_id(self, workflow_id: Optional[str]) -> None:
        if isinstance(workflow_id, str):
            workflow_id = workflow_id.strip() or None
        else:
            workflow_id = None
        self.workflow_id = workflow_id

    def set_workflow_name(self, workflow_name: Optional[str]) -> None:
        if isinstance(workflow_name, str):
            workflow_name = workflow_name.strip() or None
        else:
            workflow_name = None
        self.workflow_name = workflow_name

    def reload(self):
        """Reload data from file."""
        self._data_cache = {}
        if self.file_path and os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    raw_dict: Dict[str, Any] = data
                    elements = raw_dict.get("elements")
                    wf_id = raw_dict.get("workflow_id")
                    wf_name = raw_dict.get("workflow_name")
                    if isinstance(elements, dict):
                        self._data_cache = elements
                        if isinstance(wf_id, str) and wf_id.strip():
                            self.workflow_id = wf_id.strip()
                        else:
                            self.workflow_id = None
                        if isinstance(wf_name, str) and wf_name.strip():
                            self.workflow_name = wf_name.strip()
                        else:
                            self.workflow_name = None
                    else:
                        self._data_cache = raw_dict
                        self.workflow_id = None
                        self.workflow_name = None
            except Exception:
                self._data_cache = {}
                self.workflow_id = None
                self.workflow_name = None
        self._is_loaded = True

    def _read_all(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        if not self._is_loaded and self.file_path:
            self.reload()
        return self._data_cache

    def _write_all(self, data: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
        self._data_cache = data
        if self.file_path:
            parent = os.path.dirname(os.path.abspath(self.file_path))
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                payload: Any
                has_id = isinstance(self.workflow_id, str) and self.workflow_id.strip()
                has_name = isinstance(self.workflow_name, str) and self.workflow_name.strip()
                if has_id or has_name:
                    meta: Dict[str, Any] = {"elements": data}
                    if has_id:
                        meta["workflow_id"] = self.workflow_id.strip()  # type: ignore[union-attr]
                    if has_name:
                        meta["workflow_name"] = self.workflow_name.strip()  # type: ignore[union-attr]
                    payload = meta
                else:
                    payload = data
                json.dump(payload, f, indent=4, ensure_ascii=False)

    def list_elements(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        return self._read_all()

    def list_keys(self) -> List[str]:
        data = self._read_all()
        keys: List[str] = []
        for group, items in data.items():
            if not isinstance(items, dict):
                continue
            for name in items.keys():
                keys.append(f"{group}/{name}")
        return sorted(keys)

    def save_element(self, group: str, name: str, by: str, value: str, meta: Optional[Dict[str, Any]] = None) -> bool:
        group = (group or "Default").strip()
        name = (name or "").strip()
        by = (by or "").strip()
        value = (value or "").strip()
        if not name or not by or not value:
            return False

        data = self._read_all()
        if group not in data or not isinstance(data.get(group), dict):
            data[group] = {}

        existing = data.get(group, {}).get(name)
        element_id: Optional[str] = None
        if isinstance(existing, dict):
            eid = existing.get("id")
            if isinstance(eid, str) and eid.strip():
                element_id = eid.strip()
        if isinstance(meta, dict):
            mid = meta.get("id")
            if isinstance(mid, str) and mid.strip():
                element_id = mid.strip()
        if not element_id:
            element_id = str(uuid.uuid4())

        payload: Dict[str, Any] = {"by": by, "value": value, "id": element_id}
        if isinstance(meta, dict) and meta:
            payload.update({k: v for k, v in meta.items() if k != "id"})

        data[group][name] = payload
        self._write_all(data)
        return True

    def delete_element(self, key: str) -> bool:
        group, name = self._parse_key(key)
        if not group or not name:
            return False
        data = self._read_all()
        if group not in data or not isinstance(data.get(group), dict):
            return False
        if name not in data[group]:
            return False
        del data[group][name]
        if not data[group]:
            del data[group]
        self._write_all(data)
        return True

    def get_locator(self, key: str) -> Optional[Tuple[str, str]]:
        group, name = self._parse_key(key)
        data = self._read_all()
        item = None
        if group and name:
            item = (data.get(group) or {}).get(name) if isinstance(data.get(group), dict) else None
        else:
            target_id = key.strip() if isinstance(key, str) else ""
            if target_id:
                for g, items in data.items():
                    if not isinstance(items, dict):
                        continue
                    for n, meta in items.items():
                        if not isinstance(meta, dict):
                            continue
                        eid = meta.get("id")
                        if isinstance(eid, str) and eid.strip() == target_id:
                            item = meta
                            break
                    if item:
                        break
        if not isinstance(item, dict):
            return None
        by = item.get("by")
        value = item.get("value")
        if not isinstance(by, str) or not isinstance(value, str):
            return None
        return by, value

    def _parse_key(self, key: str) -> Tuple[str, str]:
        if not isinstance(key, str):
            return "", ""
        s = key.strip()
        if not s:
            return "", ""
        if "/" in s:
            parts = s.split("/", 1)
            return parts[0].strip(), parts[1].strip()
        return "Default", s

