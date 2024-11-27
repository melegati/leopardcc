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

    def __extract_errors_from_stacktrace(self, stacktrace: str) -> list[str]:
        stacktrace_newline = re.sub(r'\\n', r'\n', stacktrace)
        ansi_escape_pattern = re.compile(
            r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        stacktrace_no_ansi_esc = re.sub(
            ansi_escape_pattern, '', stacktrace_newline)
        split_pattern = r'passing \(\d+s\)\n *\d+ failing\n\n'
        stacktrace_summary = re.split(split_pattern, stacktrace_no_ansi_esc)[1]

        error_split_pattern = r'\)\n\n *\d+\)'
        stacktrace_summary = stacktrace_summary.strip()
        matches = re.split(error_split_pattern, stacktrace_summary)
        return matches

    def get_test_error_messages(self, project_path: str):
        try:
            subprocess.run(['cd ' + project_path + ' && npm test'],
                           shell=True, capture_output=True, text=True, check=True, timeout=7)
            return None

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            messages = self.__extract_errors_from_stacktrace(str(e.stdout))
            errors: list[TestError] = []
            for message in messages:
                error: TestError = {'message': message,
                                    'test_file': None, 'target_line': None}
                file_pattern = r' *at Context.<anonymous> \((.+):(\d+):'
                matches = re.findall(file_pattern, message)
                if len(matches) != 0:
                    (file, line) = matches[0]
                    error['test_file'] = file
                    error['target_line'] = int(line)
                errors.append(error)

            return errors
