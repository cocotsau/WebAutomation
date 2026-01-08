import logging
import time
from typing import List, Dict, Any
from core.action_base import ActionBase
from core.flow_control import BreakLoopException, ContinueLoopException

class Engine:
    """
    The engine that executes a sequence of actions.
    """
    def __init__(self):
        self.context = {}
        self.tool_registry = {}
        self.logger = logging.getLogger("ViewAuto.Engine")
        logging.basicConfig(level=logging.INFO)

    def load_workflow(self, workflow_data: List[Dict[str, Any]], tool_registry: Dict[str, Any]):
        """
        Load a workflow.
        
        Args:
            workflow_data: List of dicts, each containing 'tool_name' and 'params'.
            tool_registry: Dict mapping tool names to Action classes.
        """
        self.workflow_data = workflow_data
        self.tool_registry = tool_registry

    def execute_step_data(self, steps_data: List[Dict[str, Any]], context: Dict[str, Any]) -> bool:
        """
        Recursively execute a list of step data.
        This is injected into context as '__runner__'.
        """
        for i, step in enumerate(steps_data):
            # Skip disabled steps
            if step.get("disabled"):
                continue
            tool_name = step.get("tool_name")
            params = step.get("params", {})
            
            # For backward compatibility if 'tool_name' key is missing or different
            if not tool_name: 
                continue

            if tool_name in self.tool_registry:
                action_class = self.tool_registry[tool_name]
                try:
                    action_instance = action_class(params)
                    self.logger.info(f"Executing {action_instance.name}")
                    
                    success = action_instance.execute(context)
                    if not success:
                        self.logger.error(f"Step {tool_name} failed.")
                        return False
                except (BreakLoopException, ContinueLoopException):
                    raise
                except Exception as e:
                    self.logger.exception(f"Exception executing {tool_name}: {e}")
                    return False
            else:
                self.logger.error(f"Tool {tool_name} not found in registry.")
                return False
        return True

    def run(self):
        """
        Run the loaded workflow.
        """
        self.logger.info("Starting workflow execution...")
        self.context = {}  # Reset context
        
        # Inject the runner
        self.context["__runner__"] = self.execute_step_data
        
        if hasattr(self, 'workflow_data'):
            self.execute_step_data(self.workflow_data, self.context)
        
        self.logger.info("Workflow execution finished.")
