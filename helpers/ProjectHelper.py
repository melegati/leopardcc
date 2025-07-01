import json
import re
import os
import shutil
import subprocess
from pathlib import Path
from interfaces.LintError import LintError
from interfaces.TestError import TestError
from tap import parser #type: ignore


def install_npm_packages(project_copy_path: str, package_manager_command: str='npm'):
    node_modules_dir = '/node_modules'
    project_path = Path(project_copy_path) 
    dirpath = project_path / node_modules_dir
    if dirpath.exists() and dirpath.is_dir():
        shutil.rmtree(dirpath)
    package_lock_file = project_path / '/package-lock.json'
    install_command = 'ci' if package_lock_file.exists() else 'install'
    subprocess.run(['cd ' + project_copy_path +
                    ' && ' + package_manager_command + ' ' + install_command],
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
    erroneous_code = content[target_line - 1] if target_line - 1 < len(content) else ''

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
    
    if not stdout.startswith('{'):
        stdout = stdout[stdout.find('{'):]

    test_info = json.loads(stdout)
    failures = test_info['failures']

    errors: list[TestError] = []
    for failure in failures:
        error: TestError = {'expectation': failure['fullTitle'],
                            'message_stack': failure['err']['stack'],
                            'test_file': failure['file'] if 'file' in failure else None,
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
                        shell=True, capture_output=True, text=True, check=True, timeout=120)
        
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
    
def get_mocha_errors_from_stdout(dirty_path: str, test_command: str, line_pattern: str) -> list[TestError]:
    try:
        mocha_json_name = 'mocha-output.json'
        output_options = ' --reporter json > ' + mocha_json_name
        test_command += output_options
        
        mocha_json_output_path = dirty_path + '/' + mocha_json_name
        
        subprocess.run(['cd ' + dirty_path + ' && ' + test_command],
                        shell=True, capture_output=True, text=True, check=True, timeout=120)
        
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
                        shell=True, capture_output=True, text=True, check=True, timeout=120)
        
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
    
# function needed because of a bug in the output of tap that breaks the YAML parsing    
def read_fixed_tap_file(test_output):
    inside_yaml = False
    inside_braces = False
    output_lines = []

    for line in test_output.splitlines():
        stripped_line = line.strip()

        if stripped_line == "---":
            inside_yaml = True
            output_lines.append(line)
            continue
        elif stripped_line == "..." and inside_yaml:
            inside_yaml = False
            output_lines.append(line)
            continue

        if inside_yaml:
            if "{" in line:
                inside_braces = True
            if "}" in line:
                inside_braces = False
                line = '   ' + line

            if inside_braces and not stripped_line.endswith("{"):
                output_lines.append('  ' + line)
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)

    return '\n'.join(output_lines)

def __parse_tap_output(test_output: str, file_line_pattern)-> list[TestError]:
    tap_parser = parser.Parser()
    tap_file = tap_parser.parse_text(read_fixed_tap_file(test_output))
    
    errors: list[TestError] = []
    for line in tap_file:
        if line.category == 'test' and not line.ok:
            stack = line.yaml_block['stack'] if hasattr(line.yaml_block, '__getitem__') and 'stack' in line.yaml_block else None
            
            test_file = None
            test_line = None
            if stack:
                regex_match = re.search(file_line_pattern, line.yaml_block['stack'])
                if regex_match is not None:
                    test_file = regex_match.group(1)
                    test_line = regex_match.group(2)
                    if test_file.startswith('file://'):
                        test_file = test_file[7:]
                else:
                    print('failed to read test_file')
                    print(stack)
                

            error: TestError = {
                'expectation': line.description,
                'message_stack': stack,
                'test_file': test_file,
                'target_line': int(test_line) if test_line is not None else 0
            }
            errors.append(error)

    return errors

def get_tap_errors(dirty_path: str, test_command: str, line_pattern: str) -> list[TestError]:
    try:
        output_file_name = 'output.tap'
        test_command = test_command + ' > ' + output_file_name
        
        output_path = dirty_path + '/' + output_file_name
        
        result = subprocess.run(test_command, cwd=dirty_path, shell=True, check=True, timeout=120, stderr=subprocess.PIPE)
        if result.returncode != 0:
            pass
            # raise subprocess.CalledProcessError(result.returncode, test_command)
        
        if os.path.exists(output_path):
            os.remove(output_path) 
        return []

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        with open(output_path, 'r') as output_file:
            test_output = output_file.read()

        errors = __parse_tap_output(test_output, line_pattern)

        if len(errors) == 0 and e.stderr is not None:
            lines = e.stderr.splitlines()
            first_line = lines[0].decode().rsplit(':', 1)
            test_file = first_line[0]
            if test_file.startswith('file://'):
                test_file = test_file[7:]
            test_line = first_line[1]
            error: TestError = {
                'expectation': None,
                'message_stack': b'\n'.join(lines[1:]),
                'test_file': test_file,
                'target_line': int(test_line) if test_line is not None else 0
            }
            errors.append(error)

        if os.path.exists(output_path):
            os.remove(output_path) 
        return errors