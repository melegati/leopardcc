import subprocess
import operator
import json
import shutil
import os
import functools
import datetime
import re
import lizard  # type: ignore
from lizard import FunctionInfo
from OpenAIWrapper import OpenAIWrapper


def create_copy_of_project(file_path: str, copy_suffix: str = '-copy') -> str:
    destination_path = file_path + copy_suffix

    if os.path.exists(destination_path):
        shutil.rmtree(destination_path)

    ignore_patterns = shutil.ignore_patterns('.git')
    return shutil.copytree(file_path, destination_path, dirs_exist_ok=True, ignore=ignore_patterns)


def measure_test_coverage(project_dir: str):
    try:
        subprocess.run(['cd ' + project_dir +
                        ' && npx nyc --exclude examples --exclude test --exclude benchmarks --reporter=json-summary npm test'],
                       shell=True, capture_output=True, text=True, check=True)
        with open(project_dir + '/coverage/coverage-summary.json', "r") as coverage_summary:
            coverage_info = json.load(coverage_summary)

        coverage_info_cleansed = dict()
        for module in coverage_info:
            coverage_info_cleansed[module.replace(project_dir, '')] = {
                'coverage': coverage_info[module]}

        return coverage_info_cleansed

    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        return None


def compute_cyclomatic_complexity(project_dir: str, code_dir: str) -> list[FunctionInfo]:
    extensions = lizard.get_extensions(extension_names=["io"])
    analysis = lizard.analyze(paths=[project_dir + code_dir], exts=extensions)

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


def get_test_stacktrace(project_dir: str) -> None | str:
    try:
        subprocess.run(['cd ' + project_dir + ' && npm test'],
                       shell=True, capture_output=True, text=True, check=True)
        return None

    except subprocess.CalledProcessError as e:
        stdout_cleaned = re.sub('\[[0-9;]+[a-zA-Z]', '', e.stdout)
        stdout_no_esc = re.sub('\u001b', '', stdout_cleaned)
        stdout_filtered = re.sub(
            '(.*\n)+.*' + str(e.returncode) + ' failing', '', stdout_no_esc)
        return stdout_filtered


def main() -> None:
    # Measure test coverage before changes
    # Measure complexity of code files
    # Have LLM refactor file
    # see if tests pass
    # Measure test coverage after changes
    # Measure complexity after changes
    # Provide summary of how values have changed

    project_dir = '/media/lebkuchen/storage-disk/Repos/express'
    code_dir = '/lib'

    key_file = open('openai-key.txt', "r", encoding="utf-8")
    api_key = key_file.read()
    wrapper = OpenAIWrapper(
        api_key=api_key, model="gpt-4o-mini", max_context_length=-1)

    # coverage_info = measure_test_coverage(project_dir)
    complexity_info = compute_cyclomatic_complexity(project_dir, code_dir)
    most_complex = find_most_complex_function(complexity_info)
    most_complex_code = extract_function_code(most_complex)

    refactored_code = refactor_function(most_complex_code, wrapper)

    copy_suffix = '-copy'
    project_copy_dir = create_copy_of_project(
        project_dir, copy_suffix=copy_suffix)

    patch_code(file_path=most_complex.filename.replace(
        project_dir, project_copy_dir), old_code=most_complex_code, new_code=refactored_code)

    filename = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S") + '.json'
    wrapper.save_history_to_json('conversation-logs/' + filename)


if __name__ == "__main__":
    main()
