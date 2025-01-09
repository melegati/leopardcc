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
from ProjectInterface import ProjectInterface, LintError, TestError
from Logger import get_logger, add_log_file_handler
import os


def prepare_log_dir() -> str:
    timestamp = filename = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S")
    log_dir = "logs/" + timestamp
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    add_log_file_handler(log_dir + "/log.txt")

    return log_dir


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


def get_test_cases_from_errors(errors: list[TestError], project: ProjectInterface, project_path: str) -> list[str]:
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


def refactor_function(function_code: str, wrapper: OpenAIWrapper) -> str:
    prompt = """```javascript
    {code}
    ```
    Refactor the provided javascript method to enhance its readability and maintainability.
    You can assume that the given method is functionally correct. Ensure that you do not alter
    the external behavior of the method, maintaining both syntactic and semantic correctness.
    Provide the javascript method within a code block. Avoid using natural language explanations.
    """.format(code=function_code)

    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_with_lint_errors(errors: list[LintError], wrapper: OpenAIWrapper) -> str:
    messages = map(lambda error: "Error: {message} \nViolated rule: {rule}\nErroneous code: {code}".format(
        message=error['message'], rule=error['rule_id'], code=error['erroneous_code']), errors)
    message_stack = '\n\n'.join(messages)

    prompt = """The refactored JavaScript method you provided does not pass the linting check.
    The linting messages and the respective code look like:
    ```
    {message_stack}
    ```
    Explain why your code does not pass the linting check.
    """.format(message_stack=message_stack)

    explanation = wrapper.send_message(prompt)

    prompt = """Fix your method by utilizing the error message, the linting messages, the erroneous code,
    your explanation and the original method. Provide the javascript method within a code block.
    Do not explain anything in natural language."""

    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_with_test_errors(errors: list[TestError], test_cases: list[str], wrapper: OpenAIWrapper) -> str:
    stacks = map(lambda error: "{expectation}: {message_stack}".format(
        expectation=error['expectation'], message_stack=error['message_stack']), errors)
    stack_united = '\n\n'.join(list(stacks))
    test_cases_united = '\n\n'.join(test_cases)

    prompt = """The refactored JavaScript method you provided does not pass the unit test suite.
    The error messages and the call stack look like:
    ```
    {message_stack}
    ```
    Failing test(s) looks like:
    ```
    {tests}
    ```
    Explain why your code does not pass the unit tests.""".format(message_stack=stack_united, tests=test_cases_united)

    explanation = wrapper.send_message(prompt)

    prompt = """Fix your method by utilizing the error message, the call stack, the failing test,
    your explanation and the original method. Provide the javascript method within a code block.
    Do not explain anything in natural language."""

    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_for_better_improvement(wrapper: OpenAIWrapper) -> str:
    prompt = """The refactored Javascript method you provided lacks improvement in readability and maintainability. 
    Identify the section that can be modularized in the refactored method."""

    wrapper.send_message(prompt)

    prompt = """Please rectify the refactored Javascript method to enhance its readability and maintainability by
    utilizing information about the section that can be modularized. 
    The method you provide should be syntactically identical to the original method.
    Provide the full implementation of the improved Javascript method within a code block. 
    Avoid providing explanations in natural language."""

    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def patch_code(file_path: str, old_code: str, new_code: str) -> None:
    with open(file_path, 'r') as file:
        filedata = file.read()

    filedata = filedata.replace(old_code, new_code)

    with open(file_path, 'w') as file:
        file.write(filedata)


def main() -> None:
    log_dir = prepare_log_dir()
    project = D3Shape()

    project_path = project.project_path
    code_dir = project.code_dir

    with open('openai-key.txt', "r", encoding="utf-8") as key_file:
        api_key = key_file.read()
    conversation_log_file_path = log_dir + "/conversation.json"
    wrapper = OpenAIWrapper(
        api_key=api_key,
        log_path=conversation_log_file_path,
        model="gpt-4o-mini",
        max_context_length=-1)

    complexity_info = compute_cyclomatic_complexity(project_path + code_dir)
    most_complex = get_most_complex_functions(complexity_info)[1]
    get_logger().info("Refactoring function " + most_complex.name +
                      " from file " + most_complex.filename +
                      " with CC: " + str(most_complex.cyclomatic_complexity))

    most_complex_code = extract_function_code(most_complex)
    function_history: list[str] = [most_complex_code]

    refactored_code = refactor_function(most_complex_code, wrapper)

    project_copy_path = project.create_copy()

    target_file = most_complex.filename.replace(
        project_path, project_copy_path)
    patch_code(file_path=target_file,
               old_code=most_complex_code,
               new_code=refactored_code)
    function_history.append(refactored_code)

    is_project_improved = False
    improvement_iteration = 0
    failing_linting_history: list[list[LintError]] = []
    failing_tests_history: list[list[TestError]] = []
    try:
        while not is_project_improved:
            get_logger().info("Improvement iteration: " + str(improvement_iteration))
            if improvement_iteration >= 5:
                raise BaseException("Improvement iterations exceeded")
            improvement_iteration += 1

            does_linting_pass = False
            linting_iteration = 0
            while not does_linting_pass:
                get_logger().info("Linting iteration: " + str(linting_iteration))
                if linting_iteration >= 5:
                    raise BaseException("Lint iterations exceeded")

                lint_errors = project.get_lint_errors(project_copy_path)
                does_linting_pass = lint_errors == None
                if not does_linting_pass:
                    linting_iteration += 1
                    get_logger().info(str(len(lint_errors)) + " linter errors")
                    get_logger().debug(lint_errors)
                    failing_linting_history.append(lint_errors)

                    top_n_errors = lint_errors[:10]
                    refactored_code = refactor_with_lint_errors(
                        top_n_errors, wrapper)
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

                test_errors = project.get_test_errors(project_copy_path)
                do_tests_pass = test_errors == None
                if not do_tests_pass:
                    test_iteration += 1
                    get_logger().info(str(len(test_errors)) + " test errors")
                    get_logger().debug(test_errors)
                    failing_tests_history.append(test_errors)

                    top_n_errors = test_errors[:10]
                    test_cases = get_test_cases_from_errors(
                        top_n_errors, project, project_copy_path)

                    refactored_code = refactor_with_test_errors(
                        top_n_errors, test_cases, wrapper)
                    patch_code(file_path=target_file,
                               old_code=function_history[-1],
                               new_code=refactored_code)
                    function_history.append(refactored_code)

            # check improvement
            target_file_functions = compute_cyclomatic_complexity(target_file)
            improved_function = [fun for fun in target_file_functions if fun.name ==
                                 most_complex.name][0]

            is_project_improved = is_new_function_improved(
                most_complex, improved_function)
            get_logger().info("Improved function has CC: " +
                              str(improved_function.cyclomatic_complexity))
            if not is_project_improved:
                refactored_code = refactor_for_better_improvement(wrapper)
                patch_code(file_path=target_file,
                           old_code=function_history[-1],
                           new_code=refactored_code)
                function_history.append(refactored_code)

    except Exception as e:
        get_logger().error(e)


if __name__ == "__main__":
    main()
