from .Function import Function
from typing import Literal

Reason = Literal['linting', 'unit tests', 'complexity reduction']


class NotImprovableException(Exception):
    def __init__(self, function: Function, reason: Reason):
        self.function = function
        self.reason = reason
        self.message = "Function " + function.lizard_result.name + \
            " in file " + function.lizard_result.filename + " is not improvable due to unsatisfactory " + reason
        super().__init__(self.message)
