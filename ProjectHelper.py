import json
import re
from interfaces.LintError import LintError
from interfaces.TestError import TestError


def get_eslint_errors_from_json_stdout(stdout: bytes) -> list[LintError]:
    lint_info = json.loads(stdout)
    errors: list[LintError] = []
    for file_object in lint_info:
        for message in file_object['messages']:
            file_path = file_object['filePath']
            target_line = message['line']
            with open(file_path, 'r') as code_file:
                content = code_file.readlines()
            erroneous_code = content[target_line - 1]

            error: LintError = {
                'rule_id': message['ruleId'],
                'message': message['message'],
                'file': file_path,
                'target_line': target_line,
                'erroneous_code': erroneous_code
            }
            errors.append(error)

    return errors


def get_mocha_errors_from_json_stdout(stdout: bytes, line_pattern: str) -> list[TestError]:
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
