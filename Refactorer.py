from OpenAIWrapper import OpenAIWrapper
from interfaces.PromptStrategyInterface import PromptStrategyInterface
from interfaces.ProjectInterface import ProjectInterface
from interfaces.VerificationStrategyInterface import VerificationStrategyInterface
from interfaces.LizardResult import LizardResult
from interfaces.Function import Function


def improve_function(function: Function, processed_functions: list[Function], verification_strategy: VerificationStrategyInterface):
    function.initial_refactor()
    verification_strategy.verify_linting(function)
    verification_strategy.verify_unit_tests(function)
    verification_strategy.verify_improvement(
        function, processed_functions)
