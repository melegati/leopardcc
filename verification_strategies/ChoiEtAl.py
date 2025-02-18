from interfaces.VerificationStrategyInterface import VerificationStrategyInterface
from util.Logger import get_logger
from interfaces.NotImprovableException import NotImprovableException


class ChoiEtAl(VerificationStrategyInterface):
    """Verification methods adapted to JavaScript, taken from Choi, Jinsu et al. 2024: 'Iterative Refactoring of Real-World Open-Source Programs with Large Language Models'"""

    @property
    def name(self):
        return "Choi et al."

    def verify_linting(self, function):
        lint_errors = function.project.get_lint_errors()
        does_linting_pass = len(lint_errors) == 0

        if not does_linting_pass:
            get_logger().info("Linting does not pass, attempting to fix")
            function.refactor_with_lint_errors(lint_errors)

            lint_errors = function.project.get_lint_errors()
            does_linting_pass = len(lint_errors) == 0
            if not does_linting_pass:
                raise NotImprovableException(function, "failed linting")

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
                raise NotImprovableException(function, "failed unit tests")

    def verify_improvement(self, function):
        is_improved = function.new_cc < function.old_cc

        if not is_improved:
            get_logger().info("Improvement is not satisfying, attempting to fix")
            function.refactor_for_better_improvement()
            self.verify_linting(function)
            self.verify_unit_tests(function)

            is_improved = function.new_cc < function.old_cc
            if not is_improved:
                raise NotImprovableException(function, "unsatisfactory improvement")
