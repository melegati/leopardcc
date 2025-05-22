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
        number_linting_errors = len(lint_errors)

        if number_linting_errors > 0:
            get_logger().info("Linting does not pass, {} error(s), attempting to fix".format(number_linting_errors))
            function.refactor_with_lint_errors(lint_errors)

            lint_errors = function.project.get_lint_errors()
            number_linting_errors = len(lint_errors)
            if number_linting_errors > 0:
                raise NotImprovableException(function, "failed linting: {} error(s)".format(number_linting_errors))

    def verify_tests(self, function):
        test_errors = function.project.get_test_errors()
        number_test_errors = len(test_errors)

        if number_test_errors > 0:
            get_logger().info("Tests do not pass, {} error(s), attempting to fix".format(number_test_errors))
            function.refactor_with_test_errors(test_errors)
            self.verify_linting(function)

            test_errors = function.project.get_test_errors()
            number_test_errors = len(test_errors) 
            if number_test_errors > 0:
                raise NotImprovableException(function, "failed tests: {} error(s)".format(number_test_errors))

    def verify_improvement(self, function):
        is_improved = function.new_cc < function.old_cc

        if not is_improved:
            get_logger().info("Improvement is not satisfying, attempting to fix")
            function.refactor_for_better_improvement()
            self.verify_linting(function)
            self.verify_tests(function)

            is_improved = function.new_cc < function.old_cc
            if not is_improved:
                raise NotImprovableException(function, "unsatisfactory improvement")
