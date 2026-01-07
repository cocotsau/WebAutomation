import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import Engine
from tools.basic_tools import PrintLogAction, DelayAction, SetVariableAction
from tools.logic_tools import LoopAction, ForEachAction, WhileAction

# Registry
REGISTRY = {
    "Print Log": PrintLogAction,
    "Delay": DelayAction,
    "Set Variable": SetVariableAction,
    "Loop": LoopAction,
    "For Each": ForEachAction,
    "While": WhileAction
}

def test_nested_loops():
    print("=== Testing Nested Loops ===")
    
    workflow = [
        {
            "tool_name": "Set Variable",
            "params": {
                "key": "fruits",
                "value": '["Apple", "Banana"]'
            }
        },
        {
            "tool_name": "For Each",
            "params": {
                "list_variable": "fruits",
                "item_variable": "fruit",
                "children": [
                    {
                        "tool_name": "Print Log",
                        "params": {"message": "Eating {fruit} (Index: {loop_index})"}
                    },
                    {
                        "tool_name": "Loop",
                        "params": {
                            "count": 2,
                            "children": [
                                {
                                    "tool_name": "Print Log",
                                    "params": {"message": "  Chewing {fruit}... (Chew Index: {loop_index})"}
                                }
                            ]
                        }
                    }
                ]
            }
        },
        {
            "tool_name": "Print Log",
            "params": {"message": "Done eating all fruits."}
        }
    ]
    
    engine = Engine()
    engine.load_workflow(workflow, REGISTRY)
    engine.run()

if __name__ == "__main__":
    test_nested_loops()
