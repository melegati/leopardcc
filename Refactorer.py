from OpenAIWrapper import OpenAIWrapper
from interfaces.PromptStrategyInterface import PromptStrategyInterface
from interfaces.ProjectInterface import ProjectInterface
from interfaces.LizardResult import LizardResult
from interfaces.Function import Function
from Logger import get_logger
from ProjectHelper import compute_cyclomatic_complexity, is_new_function_improved, get_functions_sorted_by_complexity, get_most_complex_without_ignored
from interfaces.NotImprovableException import NotImprovableException


def __verify_linting__(function: Function):
    # TODO (LS-2025-01-16): Mv these three methods into another class that implements an interface - to allow using different methods, add loops etc
    lint_errors = function.project.get_lint_errors()
    does_linting_pass = len(lint_errors) == 0

    if not does_linting_pass:
        get_logger().info("Linting does not pass, attempting to fix")
        function.refactor_with_lint_errors(lint_errors)

        lint_errors = function.project.get_lint_errors()
        does_linting_pass = len(lint_errors) == 0
        if not does_linting_pass:
            raise NotImprovableException(function)


def __verify_unit_tests__(function: Function):
    test_errors = function.project.get_test_errors()
    do_tests_pass = len(test_errors) == 0

    if not do_tests_pass:
        get_logger().info("Unit tests do not pass, attempting to fix")
        function.refactor_with_test_errors(test_errors)
        __verify_linting__(function)

        test_errors = function.project.get_test_errors()
        do_tests_pass = len(test_errors) == 0
        if not do_tests_pass:
            raise NotImprovableException(function)


def __verify_improvement__(function: Function, functions_to_ignore: list[Function]):
    # TODO (LS-2025-01-16): How to deal with anonymous functions? Consider parameters as part of the name? Position? Length?
    refactored_function = get_most_complex_without_ignored(
        function, functions_to_ignore)

    is_improved = is_new_function_improved(
        old_function=function.lizard_result, new_function=refactored_function)

    if not is_improved:
        get_logger().info("Improvement is not satisfying, attempting to fix")
        function.refactor_for_better_improvement()
        __verify_linting__(function)
        __verify_unit_tests__(function)

        refactored_function = get_most_complex_without_ignored(
            function, functions_to_ignore)

        is_improved = is_new_function_improved(
            old_function=function.lizard_result, new_function=refactored_function)
        if not is_improved:
            raise NotImprovableException(function)

    get_logger().info("New CC: " + str(refactored_function.cyclomatic_complexity))


def improve_function(function: Function, processed_functions: list[Function], disregarded_functions: list[Function]):
    get_logger().info("Refactoring function " + function.lizard_result.name +
                      " from file " + function.lizard_result.filename +
                      " with CC: " + str(function.lizard_result.cyclomatic_complexity))

    function.initial_refactor()
    __verify_linting__(function)
    __verify_unit_tests__(function)
    __verify_improvement__(
        function, processed_functions + disregarded_functions)
