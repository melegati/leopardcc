from ProjectInterface import ProjectInterface, LintError, TestError
import shutil
import subprocess
import re
import json


class D3Shape(ProjectInterface):
    @property
    def project_path(self):
        return '/media/lebkuchen/storage-disk/Repos/d3-shape'

    @property
    def code_dir(self):
        return '/src'

    def after_copy_hook(self) -> None:
        project_copy_path = self.project_path + '-copy'
        node_modules_dir = '/node_modules'
        shutil.rmtree(project_copy_path + node_modules_dir)
        subprocess.run(['cd ' + project_copy_path +
                        ' && yarn install'],
                       shell=True, capture_output=True, text=True, check=True)

    def measure_test_coverage(self, project_path):
        pass

    def get_lint_errors(self, project_path):
        try:
            lint_command = 'npx eslint src test --fix --format json'
            subprocess.run(['cd ' + project_path + ' && ' + lint_command],
                           shell=True, capture_output=True, text=True, check=True, timeout=7)
            return None

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            if e.stdout is None:
                raise Exception(
                    "Linting result does not have stdout to read from")

            lint_info = json.loads(e.stdout)
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

            if len(errors) == 0:
                return None
            return errors

    def get_test_errors(self, project_path):
        try:
            test_command = 'npx mocha "test/**/*-test.js" --reporter json'
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
                                    'message_stack': failure['err']['stack'],
                                    'test_file': failure['file'],
                                    'target_line': None}
                line_pattern = r' *at Context.<anonymous> \S+d3-shape\D+:(\d+):\d+\)\n'
                line_match = re.search(line_pattern, failure['err']['stack'])
                if line_match is not None:
                    error['target_line'] = int(line_match.group(1))
                errors.append(error)

            return errors

    def get_test_case(self, error):
        if error['target_line'] is None:
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
            test_case += line.removeprefix(white_spaces_count * ' ').rstrip()

        return test_case
