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
from ProjectInterface import ProjectInterface, TestError


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
    file = open(function.filename)
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


def refactor_with_errors(errors: list[TestError], test_cases: list[str], wrapper: OpenAIWrapper) -> str:
    stacks = map(lambda error: error['expectation'] +
                 ": " + error['message_stack'], errors)
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
    project = D3Shape()

    project_path = project.project_path
    code_dir = project.code_dir

    key_file = open('openai-key.txt', "r", encoding="utf-8")
    api_key = key_file.read()
    wrapper = OpenAIWrapper(
        api_key=api_key, model="gpt-4o-mini", max_context_length=-1)

    # coverage_info = project.measure_test_coverage(project_path)
    complexity_info = compute_cyclomatic_complexity(project_path + code_dir)
    most_complex = get_most_complex_functions(complexity_info)[1]
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
    while not is_project_improved:
        print("Improvement iteration: " + str(improvement_iteration))
        if improvement_iteration >= 5:
            # TODO (LS-2024-12-03): raise BaseException("Improvement iterations exceeded")
            print("Improvement iterations exceeded")
            break
        improvement_iteration += 1

        is_project_plausible = False
        plausibility_iteration = 0
        failing_tests_history: list[list[TestError]] = []
        while not is_project_plausible:
            print("Plausibility iteration: " + str(plausibility_iteration))
            if plausibility_iteration >= 5:
                # TODO (LS-2024-11-28): raise BaseException("Plausibility iterations exceeded")
                print("Plausibility iterations exceeded")
                break
            plausibility_iteration += 1

            errors = project.get_test_errors(project_copy_path)
            is_project_plausible = errors == None
            if not is_project_plausible:
                failing_tests_history.append(errors)
                top_n_errors = errors[:10]
                test_cases = get_test_cases_from_errors(
                    top_n_errors, project, project_copy_path)

                refactored_code = refactor_with_errors(
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
        if not is_project_improved:
            refactored_code = refactor_for_better_improvement(wrapper)
            patch_code(file_path=target_file,
                       old_code=function_history[-1],
                       new_code=refactored_code)
            function_history.append(refactored_code)

    filename = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S") + '.json'
    wrapper.save_history_to_json('conversation-logs/' + filename)
    for i, test_run in enumerate(failing_tests_history):
        print("Test run " + str(i) + ": " +
              str(len(test_run)) + " failing tests")


if __name__ == "__main__":
    main()
