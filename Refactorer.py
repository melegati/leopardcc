from interfaces.VerificationStrategyInterface import VerificationStrategyInterface
from interfaces.Function import Function


def improve_function(function: Function, verification_strategy: VerificationStrategyInterface):
    function.initial_refactor()
    verification_strategy.verify_linting(function)
    verification_strategy.verify_tests(function)
    verification_strategy.verify_improvement(function)
