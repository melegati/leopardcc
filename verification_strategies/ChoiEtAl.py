from interfaces.VerificationStrategyInterface import VerificationStrategyInterface
from ProjectHelper import compute_cyclomatic_complexity, is_new_function_improved, get_functions_sorted_by_complexity, get_most_complex_without_ignored
from Logger import get_logger
from interfaces.NotImprovableException import NotImprovableException


class ChoiEtAl(VerificationStrategyInterface):
    """Verification methods adapted to JavaScript, taken from Choi, Jinsu et al. 2024: 'Iterative Refactoring of Real-World Open-Source Programs with Large Language Models'"""

    def verify_linting(self, function):
        lint_errors = function.project.get_lint_errors()
        does_linting_pass = len(lint_errors) == 0

        if not does_linting_pass:
            get_logger().info("Linting does not pass, attempting to fix")
            function.refactor_with_lint_errors(lint_errors)

            lint_errors = function.project.get_lint_errors()
            does_linting_pass = len(lint_errors) == 0
            if not does_linting_pass:
                raise NotImprovableException(function)

    def verify_unit_tests(self, function):
        test_errors = function.project.get_test_errors()
        do_tests_pass = len(test_errors) == 0

        if not do_tests_pass:
            get_logger().info("Unit tests do not pass, attempting to fix")
            function.refactor_with_test_errors(test_errors)
            self.verify_linting(function)

            test_errors = function.project.get_test_errors()
            do_tests_pass = len(test_errors) == 0
            if not do_tests_pass:
                raise NotImprovableException(function)

    def verify_improvement(self, function, functions_to_ignore):
        # TODO (LS-2025-01-16): How to deal with anonymous functions? Consider parameters as part of the name? Position? Length?
        refactored_function = get_most_complex_without_ignored(
            function, functions_to_ignore)

        is_improved = is_new_function_improved(
            old_function=function.lizard_result, new_function=refactored_function)

        if not is_improved:
            get_logger().info("Improvement is not satisfying, attempting to fix")
            function.refactor_for_better_improvement()
            self.verify_linting(function)
            self.verify_unit_tests(function)

            refactored_function = get_most_complex_without_ignored(
                function, functions_to_ignore)

            is_improved = is_new_function_improved(
                old_function=function.lizard_result, new_function=refactored_function)
            if not is_improved:
                raise NotImprovableException(function)

        get_logger().info("New CC: " + str(refactored_function.cyclomatic_complexity))
