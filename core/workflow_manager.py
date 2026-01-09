import os
import json
import shutil
from typing import Dict, List, Any

class WorkflowManager:
    def __init__(self, base_dir="workflows"):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def save_workflow(self, name: str, group: str, data: List[Dict[str, Any]]) -> bool:
        """
        Save workflow data to a JSON file.
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

    def load_workflow(self, name: str, group: str) -> List[Dict[str, Any]]:
        """
        Load workflow data from a JSON file.
        """
        try:
            file_path = os.path.join(self.base_dir, group, f"{name}.json")
            if not os.path.exists(file_path):
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading workflow: {e}")
            return []

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
