from core.engine import Engine
from tools.basic_tools import PrintLogAction, DelayAction, SetVariableAction

# Registry of available tools
TOOL_REGISTRY = {
    "PrintLog": PrintLogAction,
    "Delay": DelayAction,
    "SetVariable": SetVariableAction
}

def main():
    # Example Workflow Data (usually loaded from a file or GUI)
    workflow_data = [
        {
            "tool_name": "PrintLog",
            "params": {"message": "Starting automation..."}
        },
        {
            "tool_name": "SetVariable",
            "params": {"key": "user", "value": "Trae"}
        },
        {
            "tool_name": "Delay",
            "params": {"seconds": 2}
        },
        {
            "tool_name": "PrintLog",
            "params": {"message": "Hello, {user}! Automation complete."}
        }
    ]

    engine = Engine()
    engine.load_workflow(workflow_data, TOOL_REGISTRY)
    engine.run()

if __name__ == "__main__":
    main()
