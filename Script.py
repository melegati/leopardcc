import subprocess
import operator
import functools
import datetime
import re
import lizard  # type: ignore
from lizard import FunctionInfo
from OpenAIWrapper import OpenAIWrapper
from projects.Expressjs import Expressjs
from projects.D3Shape import D3Shape
from prompt_strategies.ChoiEtAl import ChoiEtAl
from Interfaces import PromptStrategyInterface, ProjectInterface, LintError, TestError
from Logger import get_logger, add_log_file_handler
import os


def prepare_log_dir() -> str:
    timestamp = filename = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S")
    log_dir = "logs/" + timestamp
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    return log_dir


def prepare_conversation_wrapper(log_dir: str) -> OpenAIWrapper:
    with open('openai-key.txt', "r", encoding="utf-8") as key_file:
        api_key = key_file.read()
    conversation_log_file_path = log_dir + "/conversation.json"
    wrapper = OpenAIWrapper(
        api_key=api_key,
        log_path=conversation_log_file_path,
        model="gpt-4o-mini",
        max_context_length=-1)

    return wrapper


def compute_cyclomatic_complexity(path: str) -> list[FunctionInfo]:
    extensions = lizard.get_extensions(extension_names=["io"])
    analysis = lizard.analyze(paths=[path], exts=extensions)

    functions = list()
    for file in list(analysis):
        for function in file.function_list:
            functions.append(function)

    return functions


def get_most_complex_functions(functions: list[FunctionInfo]) -> list[FunctionInfo]:
    result = sorted(
        functions, key=lambda fun: fun.cyclomatic_complexity, reverse=True)
    return result


def extract_function_code(function: FunctionInfo) -> str:
    with open(function.filename) as file:
        code = file.readlines()
    function_lines = code[function.start_line - 1:function.end_line]
    function_code = functools.reduce(operator.add, function_lines)
    return function_code


def get_test_cases_from_errors(errors: list[TestError], project: ProjectInterface) -> list[str]:
    test_cases: list[str] = []
    for error in errors:
        test_case = project.get_test_case(error)
        if test_case == None:
            continue
        test_cases.append(str(test_case))

    return test_cases


def is_new_function_improved(old_function: FunctionInfo, new_function: FunctionInfo) -> bool:
    old_cyclomatic = old_function.cyclomatic_complexity
    new_cyclomatic = new_function.cyclomatic_complexity
    return new_cyclomatic < old_cyclomatic


def __remove_code_block_backticks(code: str) -> str:
    no_backticks = code.replace("```javascript\n", "").replace("\n```", "")
    return no_backticks


def refactor_function(code: str, wrapper: OpenAIWrapper, strategy: PromptStrategyInterface) -> str:
    prompt = strategy.initial_prompt(code)

    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_with_lint_errors(errors: list[LintError], wrapper: OpenAIWrapper, strategy: PromptStrategyInterface) -> str:
    prompt = strategy.linting_explanation_prompt(errors)
    explanation = wrapper.send_message(prompt)

    prompt = strategy.linting_fix_prompt()
    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_with_test_errors(errors: list[TestError], test_cases: list[str], wrapper: OpenAIWrapper, strategy: PromptStrategyInterface) -> str:
    prompt = strategy.test_explanation_prompt(errors, test_cases)
    explanation = wrapper.send_message(prompt)

    prompt = strategy.test_fix_prompt()
    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_for_better_improvement(wrapper: OpenAIWrapper, strategy: PromptStrategyInterface) -> str:
    prompt = strategy.better_improvement_explanation_prompt()
    wrapper.send_message(prompt)

    prompt = strategy.better_improvement_fix_prompt()
    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def patch_code(file_path: str, old_code: str, new_code: str) -> None:
    with open(file_path, 'r') as file:
        filedata = file.read()

    filedata = filedata.replace(old_code, new_code)

    with open(file_path, 'w') as file:
        file.write(filedata)


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


def main() -> None:
    project = D3Shape()
    strategy = ChoiEtAl()

    original_path = project.project_path
    code_dir = project.code_dir

    log_dir = prepare_log_dir()
    add_log_file_handler(log_dir + "/log.txt")

    wrapper = prepare_conversation_wrapper(log_dir)

    complexity_info = compute_cyclomatic_complexity(original_path + code_dir)
    most_complex = get_most_complex_functions(complexity_info)[0]

    try:
        improve_function(most_complex, wrapper, project, strategy)

    except BaseException as e:
        get_logger().error(e)


if __name__ == "__main__":
    main()
