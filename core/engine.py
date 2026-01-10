import logging
import time
from typing import List, Dict, Any
from core.action_base import ActionBase
from core.flow_control import BreakLoopException, ContinueLoopException
from core.exit_flow import ExitFlowException

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
            workflow_data: List of dicts, each containing 'id' (step/tool id) and 'params'.
            tool_registry: Dict mapping ids (and optionally names) to Action classes.
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
            tool_id = step.get("id") or step.get("tool_id")
            params = step.get("params", {})
            line = step.get("line")
            prefix = f"[步骤 {line}] " if line is not None else ""
            
            if not tool_id:
                self.logger.error(f"{prefix}Step is missing 'id' field, skipping.")
                continue

            if tool_id == "EndMarker":
                scope = params.get("scope")
                if scope == "if":
                    self.logger.info(f"{prefix}End IF")
                    self.context["_last_if_result"] = None
                else:
                    self.logger.info(f"{prefix}结束逻辑块")
                continue

            if tool_id in self.tool_registry:
                action_class = self.tool_registry[tool_id]
                try:
                    action_instance = action_class(params)
                    self.logger.info(f"{prefix}Executing {action_instance.name}")
                    
                    success = action_instance.execute(context)
                    if not success:
                        self.logger.error(f"{prefix}Step {tool_id} failed.")
                        return False
                except (BreakLoopException, ContinueLoopException):
                    raise
                except ExitFlowException as e:
                    self.logger.info(f"{prefix}ExitFlowException: {e}")
                    context["__exit_code__"] = getattr(e, "code", 0)
                    return False
                except Exception as e:
                    self.logger.exception(f"{prefix}Exception executing {tool_id}: {e}")
                    return False
            else:
                self.logger.error(f"{prefix}Tool {tool_id} not found in registry.")
                return False
        return True

    def run(self, initial_context: Dict[str, Any] = None):
        """
        Run the loaded workflow.
        """
        self.logger.info("Starting workflow execution...")
        
        # Initialize context with initial_context if provided, else empty
        if initial_context is not None:
            self.context = initial_context.copy()
        else:
            self.context = {}
        
        # Inject the runner
        self.context["__runner__"] = self.execute_step_data
        
        if hasattr(self, 'workflow_data'):
            self.execute_step_data(self.workflow_data, self.context)
        
        self.logger.info("Workflow execution finished.")
