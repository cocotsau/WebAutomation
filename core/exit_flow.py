from core.flow_control import BreakLoopException


class ExitFlowException(BreakLoopException):
    """Exception raised to exit the whole workflow with a given code."""

    def __init__(self, code: int = 0):
        super().__init__(f"Exit workflow with code {code}")
        self.code = int(code)

