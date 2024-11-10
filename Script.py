import subprocess
import operator
import functools
import datetime
import re
import lizard  # type: ignore
from lizard import FunctionInfo
from OpenAIWrapper import OpenAIWrapper
from projects.Expressjs import Expressjs


def compute_cyclomatic_complexity(project_path: str, code_dir: str) -> list[FunctionInfo]:
    extensions = lizard.get_extensions(extension_names=["io"])
    analysis = lizard.analyze(paths=[project_path + code_dir], exts=extensions)

    functions = list()
    for file in list(analysis):
        for function in file.function_list:
            functions.append(function)

    return functions


def find_most_complex_function(functions: list[FunctionInfo]) -> FunctionInfo:
    result = sorted(
        functions, key=lambda fun: fun.cyclomatic_complexity, reverse=True)
    return result[0]


def extract_function_code(function: FunctionInfo) -> str:
    file = open(function.filename)
    code = file.readlines()
    function_lines = code[function.start_line - 1:function.end_line]
    function_code = functools.reduce(operator.add, function_lines)
    return function_code


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

    code_without_backticks = improved_code.replace(
        "```javascript\n", "").replace("\n```", "")
    return code_without_backticks


def patch_code(file_path: str, old_code: str, new_code: str) -> None:
    with open(file_path, 'r') as file:
        filedata = file.read()

    filedata = filedata.replace(old_code, new_code)

    with open(file_path, 'w') as file:
        file.write(filedata)


def main() -> None:
    project_path = Expressjs().project_path
    code_dir = Expressjs().code_dir

    key_file = open('openai-key.txt', "r", encoding="utf-8")
    api_key = key_file.read()
    wrapper = OpenAIWrapper(
        api_key=api_key, model="gpt-4o-mini", max_context_length=-1)

    # coverage_info = Expressjs().measure_test_coverage(project_path)
    complexity_info = compute_cyclomatic_complexity(project_path, code_dir)
    most_complex = find_most_complex_function(complexity_info)
    most_complex_code = extract_function_code(most_complex)

    refactored_code = refactor_function(most_complex_code, wrapper)

    project_copy_dir = Expressjs().create_copy()

    patch_code(file_path=most_complex.filename.replace(project_path, project_copy_dir),
               old_code=most_complex_code,
               new_code=refactored_code)

    filename = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S") + '.json'
    wrapper.save_history_to_json('conversation-logs/' + filename)


if __name__ == "__main__":
    main()
