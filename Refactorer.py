from OpenAIWrapper import OpenAIWrapper
from interfaces.PromptStrategyInterface import PromptStrategyInterface
from interfaces.ProjectInterface import ProjectInterface
from interfaces.VerificationStrategyInterface import VerificationStrategyInterface
from interfaces.LizardResult import LizardResult
from interfaces.Function import Function
from Logger import get_logger


def improve_function(function: Function, processed_functions: list[Function], verification_strategy: VerificationStrategyInterface):
    get_logger().info("Refactoring function " + function.lizard_result.name +
                      " from file " + function.lizard_result.filename +
                      " with CC: " + str(function.lizard_result.cyclomatic_complexity))

    function.initial_refactor()
    verification_strategy.verify_linting(function)
    verification_strategy.verify_unit_tests(function)
    verification_strategy.verify_improvement(
        function, processed_functions)
