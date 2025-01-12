from lizard import FunctionInfo  # type: ignore
from OpenAIWrapper import OpenAIWrapper
from Interfaces import PromptStrategyInterface, ProjectInterface
from Logger import get_logger
from ProjectHelper import compute_cyclomatic_complexity, extract_function_code, patch_code, get_test_cases_from_errors, is_new_function_improved
from PromptHelper import refactor_function, refactor_with_lint_errors, refactor_with_test_errors, refactor_for_better_improvement


# TODO (LS-2025-01-11) Break me down, refactor me
def improve_function(function: FunctionInfo, wrapper: OpenAIWrapper, project: ProjectInterface, strategy: PromptStrategyInterface):
    get_logger().info("Refactoring function " + function.name +
                      " from file " + function.filename +
                      " with CC: " + str(function.cyclomatic_complexity))

    code = extract_function_code(function)
    function_history: list[str] = [code]

    refactored_code = refactor_function(code, wrapper, strategy)

    target_file = function.filename.replace(
        project.project_path, project.dirty_path)
    patch_code(file_path=target_file,
               old_code=code,
               new_code=refactored_code)
    function_history.append(refactored_code)

    is_project_improved = False
    improvement_iteration = 0

    while not is_project_improved:
        get_logger().info("Improvement iteration: " + str(improvement_iteration))
        if improvement_iteration >= 5:
            raise BaseException("Improvement iterations exceeded")
        improvement_iteration += 1

        does_linting_pass = False
        linting_iteration = 0
        while not does_linting_pass:
            get_logger().info("Linting iteration: " + str(linting_iteration))
            if linting_iteration >= 2:
                raise BaseException("Lint iterations exceeded")

            lint_errors = project.get_lint_errors(project.dirty_path)
            does_linting_pass = len(lint_errors) == 0
            if not does_linting_pass:
                linting_iteration += 1
                get_logger().info(str(len(lint_errors)) + " linting errors")
                get_logger().debug(lint_errors)

                top_lint_errors = lint_errors[:10]
                refactored_code = refactor_with_lint_errors(
                    top_lint_errors, wrapper, strategy)
                patch_code(file_path=target_file,
                           old_code=function_history[-1],
                           new_code=refactored_code)
                function_history.append(refactored_code)

        do_tests_pass = False
        test_iteration = 0
        while not do_tests_pass:
            get_logger().info("Test iteration: " + str(test_iteration))
            if test_iteration >= 5:
                raise BaseException("Test iterations exceeded")

            test_errors = project.get_test_errors(project.dirty_path)
            do_tests_pass = test_errors == None
            if not do_tests_pass:
                test_iteration += 1
                get_logger().info(str(len(test_errors)) + " test errors")
                get_logger().debug(test_errors)

                top_test_errors = test_errors[:10]
                test_cases = get_test_cases_from_errors(
                    top_test_errors, project)

                refactored_code = refactor_with_test_errors(
                    top_test_errors, test_cases, wrapper, strategy)
                patch_code(file_path=target_file,
                           old_code=function_history[-1],
                           new_code=refactored_code)
                function_history.append(refactored_code)

        # check improvement
        target_file_functions = compute_cyclomatic_complexity(target_file)
        improved_function = [
            fun for fun in target_file_functions if fun.name == function.name][0]

        is_project_improved = is_new_function_improved(
            function, improved_function)
        get_logger().info("Improved function has CC: " +
                          str(improved_function.cyclomatic_complexity))
        if not is_project_improved:
            refactored_code = refactor_for_better_improvement(
                wrapper, strategy)
            patch_code(file_path=target_file,
                       old_code=function_history[-1],
                       new_code=refactored_code)
            function_history.append(refactored_code)
