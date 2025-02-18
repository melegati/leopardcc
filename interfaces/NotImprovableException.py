from .Function import Function
from typing import Literal

Reason = Literal['failed linting', 'failed unit tests', 'unsatisfactory improvement']


class NotImprovableException(Exception):
    def __init__(self, function: Function, reason: Reason):
        self.function = function
        self.reason = reason
        self.message = "Function " + function.lizard_result.name + \
            " in file " + function.lizard_result.filename + " is not improvable due to " + reason
        super().__init__(self.message)
