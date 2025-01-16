from Function import Function


class NotImprovableException(Exception):
    def __init__(self, function: Function):
        self.message = "Function " + function.lizard_result.name + \
            " in file " + function.lizard_result.filename + " is not improvable."
        super().__init__(self.message)
