from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import (
    install_npm_packages, fix_eslint_issues, 
    get_eslint_errors
)
import subprocess
import os
import re
import json


class Json5(ProjectInterface):
    @property
    def path(self):
        return 'repos/json5'

    @property
    def code_dir(self):
        return '/lib'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        install_npm_packages(project_copy_path)

    def run_lint_fix(self, code):
        fixed_code = fix_eslint_issues(code, self.dirty_path)

        return fixed_code

    def get_lint_errors(self):
        lint_command = 'npx eslint .'
        errors = get_eslint_errors(self.dirty_path, lint_command)

        return errors

    def __parse_tap_output(self, test_output: str, file_line_pattern)-> list[TestError]:
        test_info = json.loads(test_output)
        failures = test_info['failures']

        errors: list[TestError] = []
        for failure in failures:
            regex_match = re.search(file_line_pattern, failure['err']['stack'])
            if regex_match is not None:
                    test_file = regex_match.group(1)
                    test_line = regex_match.group(2)

            error: TestError = {'expectation': failure['fullTitle'],
                                'message_stack': failure['err']['stack'],
                               'test_file': self.path + '/' + test_file,
                                'target_line': int(test_line)}
            errors.append(error)

        return errors

    def get_test_errors(self):
        try:
            output_file_name = 'test-output.json'
            test_command = 'npx tap test -R json > ' + output_file_name
            
            output_path = self.dirty_path + '/' + output_file_name
            
            subprocess.run(test_command, cwd=self.dirty_path, shell=True, check=True, timeout=30)
            
            if os.path.exists(output_path):
                os.remove(output_path) 
            return []

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            with open(output_path, 'r') as output_file:
                test_output = output_file.read()

            file_line_pattern = r' *at Test.<anonymous> \((\D+):(\d+):\d+\)'
            errors = self.__parse_tap_output(test_output, file_line_pattern)

            if os.path.exists(output_path):
                os.remove(output_path) 
            return errors

    def get_test_case(self, error: TestError) -> None | str:
        if error['target_line'] is None:
            return None

        with open(error['test_file'], 'r') as f:
            lines = f.readlines()

        # Find the start and end of the surrounding test closure.
        start_line = error['target_line']

        # Traverse downwards to find the end of the closure (assuming balanced parentheses).
        end_line = start_line
        open_parentheses = 0
        while end_line < len(lines):
            line = lines[end_line]
            open_parentheses += line.count('(')
            open_parentheses -= line.count(')')
            end_line += 1
            if open_parentheses == 0:
                break

        # Get the closure content
        test_case_lines = lines[start_line:end_line]

        white_spaces_count = len(test_case_lines[0]) - \
            len(test_case_lines[0].lstrip())
        test_case = ''
        for line in test_case_lines:
            test_case += line.removeprefix(white_spaces_count * ' ').rstrip()

        return test_case