from ProjectInterface import ProjectInterface, TestError
import shutil
import subprocess
import re
import json


class Expressjs(ProjectInterface):
    @property
    def project_path(self):
        return '/media/lebkuchen/storage-disk/Repos/express'

    @property
    def code_dir(self):
        return '/lib'

    def after_copy_hook(self) -> None:
        project_copy_path = self.project_path + '-copy'
        node_modules_dir = '/node_modules'
        shutil.rmtree(project_copy_path + node_modules_dir)
        subprocess.run(['cd ' + project_copy_path +
                        ' && npm install'],
                       shell=True, capture_output=True, text=True, check=True)

    def measure_test_coverage(self, project_path: str):
        try:
            subprocess.run(['cd ' + project_path +
                            ' && npx nyc --exclude examples --exclude test --exclude benchmarks --reporter=json-summary npm test'],
                           shell=True, capture_output=True, text=True, check=True)
            with open(project_path + '/coverage/coverage-summary.json', "r") as coverage_summary:
                coverage_info = json.load(coverage_summary)

            coverage_info_cleansed = dict()
            for module in coverage_info:
                coverage_info_cleansed[module.replace(project_path, '')] = {
                    'coverage': coverage_info[module]}

            return coverage_info_cleansed

        except subprocess.CalledProcessError as e:
            print(f"An error occurred: {e}")
            return None

    def get_test_errors(self, project_path: str):
        try:
            test_command = 'npx mocha --require test/support/env --reporter json --check-leaks test/ test/acceptance/'
            subprocess.run(['cd ' + project_path + ' && ' + test_command],
                           shell=True, capture_output=True, text=True, check=True, timeout=7)
            return None

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            if e.stdout is None:
                raise Exception("Unit tests do not have stdout to read from")
            test_info = json.loads(e.stdout)
            failures = test_info['failures']

            errors: list[TestError] = []
            for failure in failures:
                error: TestError = {'expectation': failure['fullTitle'],
                                    'error': failure['err']['message'],
                                    'test_file': failure['file'],
                                    'target_line': None}
                line_pattern = r' *at Context.<anonymous> \([^\d]+:(\d+):\d+\)'
                line_match = re.search(line_pattern, failure['err']['stack'])
                if line_match is not None:
                    error['target_line'] = int(line_match.group(1))
                errors.append(error)

            return errors

    def get_test_case(self, error: TestError) -> str | None:
        if error['test_file'] is None or error['target_line'] is None:
            return None

        with open(error['test_file'], 'r') as f:
            lines = f.readlines()

        # Find the start and end of the surrounding `it()` closure.
        start_line = error['target_line']

        # Traverse upwards to find the start of the `it()` closure.
        while start_line > 0 and not (lines[start_line].strip().startswith("it(")
                                      or lines[start_line].strip().startswith("test(")):
            start_line -= 1

        # Traverse downwards to find the end of the closure (assuming balanced braces).
        end_line = start_line
        open_braces = 0
        while end_line < len(lines):
            line = lines[end_line]
            open_braces += line.count('{')
            open_braces -= line.count('}')
            end_line += 1
            if open_braces == 0:
                break

        # Get the closure content
        test_case_lines = lines[start_line:end_line]

        white_spaces_count = len(test_case_lines[0]) - \
            len(test_case_lines[0].lstrip())
        test_case = ''
        for line in test_case_lines:
            test_case += line.removeprefix(white_spaces_count * ' ')

        return test_case
