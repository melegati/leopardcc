import json
import re
import os
import shutil
import subprocess
from pathlib import Path
from interfaces.LintError import LintError
from interfaces.TestError import TestError


def install_npm_packages(project_copy_path: str, package_manager_command: str='npm'):
    node_modules_dir = '/node_modules'
    dirpath = Path(project_copy_path) / node_modules_dir
    if dirpath.exists() and dirpath.is_dir():
        shutil.rmtree(dirpath)
    subprocess.run(['cd ' + project_copy_path +
                    ' && ' + package_manager_command + ' install'],
                    shell=True, capture_output=True, text=True, check=True)


def fix_eslint_issues(code: str, dirty_path: str, package_manager_command: str='npx') -> str:
    patch_file_path = dirty_path + "/patch.js"
    with open(patch_file_path, 'w') as patch_file:
        patch_file.write(code)
    
    lint_fix_command = 'cat patch.js | ' + package_manager_command + ' eslint --stdin --format json --fix-dry-run'
    proc = subprocess.run(['cd ' + dirty_path + ' && ' + lint_fix_command],
                        shell=True, capture_output=True, text=True, check=False)

    os.remove(patch_file_path) 
    
    linter_output = json.loads(proc.stdout)
    if 'output' in linter_output[0]:
        improved_code = linter_output[0]['output']
        return improved_code
    
    print("lint fix did not work")
    return code


def __extract_eslint_error(message: dict[str, str], file_path: str) -> LintError:
    target_line = int(message['line'])
    with open(file_path, 'r') as code_file:
        content = code_file.readlines()
    erroneous_code = content[target_line - 1]

    error: LintError = {
        'rule_id': message['ruleId'],
        'message': message['message'],
        'file': file_path,
        'target_line': target_line,
        'erroneous_code': erroneous_code,
        'severity': int(message['severity'])
    }
    return error


def __get_eslint_errors_from_json_output(output: bytes | str) -> list[LintError]:
    lint_info = json.loads(output)
    errors: list[LintError] = []
    for file_object in lint_info:
        for message in file_object['messages']:
            file_path = file_object['filePath']
            error = __extract_eslint_error(message, file_path)
            errors.append(error)

    return errors


def get_eslint_errors(dirty_path: str, lint_command: str) -> list[LintError]:
    try: 
        eslint_json_name = 'eslint-output.json'
        output_options = ' --format json -o ' + eslint_json_name
        lint_command += output_options
        
        eslint_json_output_path = dirty_path + '/' + eslint_json_name

        subprocess.run(['cd ' + dirty_path + ' && ' + lint_command],
                        shell=True, capture_output=True, text=True, check=True, timeout=120)
        
        if os.path.exists(eslint_json_output_path):
            os.remove(eslint_json_output_path) 
        return []


    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        with open(eslint_json_output_path, 'r') as eslint_json_file:
            eslint_json_output = eslint_json_file.read()

        errors = __get_eslint_errors_from_json_output(eslint_json_output)

        if os.path.exists(eslint_json_output_path):
            os.remove(eslint_json_output_path) 
        return errors


def __get_mocha_errors_from_json_output(stdout: bytes | str, line_pattern: str) -> list[TestError]:
    test_info = json.loads(stdout)
    failures = test_info['failures']

    errors: list[TestError] = []
    for failure in failures:
        error: TestError = {'expectation': failure['fullTitle'],
                            'message_stack': failure['err']['stack'],
                            'test_file': failure['file'],
                            'target_line': None}
        line_match = re.search(line_pattern, failure['err']['stack'])
        if line_match is not None:
            error['target_line'] = int(line_match.group(1))
        errors.append(error)

    return errors


def get_mocha_errors(dirty_path: str, test_command: str, line_pattern: str) -> list[TestError]:
    try:
        mocha_json_name = 'mocha-output.json'
        output_options = ' --reporter json --reporter-option output=' + mocha_json_name
        test_command += output_options
        
        mocha_json_output_path = dirty_path + '/' + mocha_json_name
        
        subprocess.run(['cd ' + dirty_path + ' && ' + test_command],
                        shell=True, capture_output=True, text=True, check=True, timeout=30)
        
        if os.path.exists(mocha_json_output_path):
            os.remove(mocha_json_output_path) 
        return []

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        with open(mocha_json_output_path, 'r') as mocha_json_file:
            mocha_json_output = mocha_json_file.read()

        errors = __get_mocha_errors_from_json_output(mocha_json_output, line_pattern)

        if os.path.exists(mocha_json_output_path):
            os.remove(mocha_json_output_path) 
        return errors


def __get_jest_errors_from_json_output(jest_json_output: str, line_pattern: str) -> list[TestError]:
    test_info = json.loads(jest_json_output)
    test_results = test_info['testResults']

    errors: list[TestError] = []
    for test in test_results:
        if test['status'] == "failed":
            for assertion in test['assertionResults']:
                if assertion['status'] == "failed":
                    ansi_code_escape_pattern = r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])'
                    cleaned_messages = re.sub(ansi_code_escape_pattern, "", "".join(assertion['failureMessages']))
                    
                    error: TestError = {
                        'expectation': assertion['fullName'],
                        'message_stack': cleaned_messages,
                        'test_file': test['name'],
                        'target_line': None
                    }
                    line_match = re.search(line_pattern, error['message_stack'])
                    if line_match is not None:
                        error['target_line'] = int(line_match.group(1))

                    errors.append(error)

    return errors


def get_jest_errors(dirty_path: str, test_command: str, line_pattern: str) -> list[TestError]:
    try:
        jest_json_name = 'jest-output.json'
        output_options = ' --json --outputFile=' + jest_json_name
        test_command +=  output_options

        jest_json_output_path = dirty_path + '/' + jest_json_name

        subprocess.run(['cd ' + dirty_path + ' && ' + test_command],
                        shell=True, capture_output=True, text=True, check=True, timeout=30)
        
        if os.path.exists(jest_json_output_path):
            os.remove(jest_json_output_path) 
        
        return []

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        with open(jest_json_output_path) as jest_json_file:
            jest_json_output = jest_json_file.read()

        errors = __get_jest_errors_from_json_output(jest_json_output, line_pattern)

        if os.path.exists(jest_json_output_path):
            os.remove(jest_json_output_path) 
        return errors
    
def __get_vitest_errors_from_json_output(jest_json_output: str, line_pattern: str) -> list[TestError]:
    test_info = json.loads(jest_json_output)
    test_results = test_info['testResults']

    errors: list[TestError] = []
    for test in test_results:
        if test['status'] == "failed":
            for assertion in test['assertionResults']:
                if assertion['status'] == "failed":
                    ansi_code_escape_pattern = r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])'
                    cleaned_messages = re.sub(ansi_code_escape_pattern, "", "".join(assertion['failureMessages']))
                    
                    error: TestError = {
                        'expectation': assertion['fullName'],
                        'message_stack': cleaned_messages,
                        'test_file': test['name'],
                        'target_line': None
                    }
                    line_match = re.search(line_pattern, error['message_stack'])
                    if line_match is not None:
                        error['target_line'] = int(line_match.group(1))

                    errors.append(error)

    return errors

def get_vitest_errors(dirty_path: str, test_command: str, line_pattern: str) -> list[TestError]:
    try:
        vitest_json_name = 'vitest-output.json'
        output_options = '  --reporter=json --outputFile=' + vitest_json_name
        test_command +=  output_options

        vitest_json_output_path = dirty_path + '/' + vitest_json_name

        subprocess.run(['cd ' + dirty_path + ' && ' + test_command],
                        shell=True, capture_output=True, text=True, check=True, timeout=120)
        
        if os.path.exists(vitest_json_output_path):
            os.remove(vitest_json_output_path) 
        
        return []

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        with open(vitest_json_output_path) as jest_json_file:
            jest_json_output = jest_json_file.read()

        errors = __get_vitest_errors_from_json_output(jest_json_output, line_pattern)

        if os.path.exists(vitest_json_output_path):
            os.remove(vitest_json_output_path) 
        return errors   