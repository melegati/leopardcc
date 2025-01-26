from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import fix_eslint_issues, get_eslint_errors, get_mocha_errors
import shutil
import subprocess
import os
import re
from tap import parser #type: ignore


class Underscore(ProjectInterface):
    @property
    def path(self):
        return '/media/lebkuchen/storage-disk/Repos/thesis-projects/underscore'

    @property
    def code_dir(self):
        return '/modules'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        node_modules_dir = '/node_modules'
        shutil.rmtree(project_copy_path + node_modules_dir)
        subprocess.run(['cd ' + project_copy_path +
                        ' && npm install'],
                       shell=True, capture_output=True, text=True, check=True)

    def run_lint_fix(self, code):
        fixed_code = fix_eslint_issues(code, self.dirty_path)

        return fixed_code

    def get_lint_errors(self):
        lint_command = 'npx eslint modules/*.js'
        errors = get_eslint_errors(self.dirty_path, lint_command)

        return errors

    def __parse_tap_output(self, test_output: str, file_line_pattern)-> list[TestError]:
        tap_parser = parser.Parser()
        tap_file = tap_parser.parse_text(test_output)
        
        errors: list[TestError] = []
        for line in tap_file:
            if line.category == 'test' and not line.ok:
                regex_match = re.search(file_line_pattern, line.yaml_block['stack'])
                if regex_match is not None:
                    test_file = regex_match.group(1)
                    test_line = regex_match.group(2)

                error: TestError = {
                    'expectation': line.description,
                    'message_stack': line.yaml_block['message'],
                    'test_file': test_file,
                    'target_line': int(test_line)
                }
                errors.append(error)

        return errors

    def get_test_errors(self):
        try:
            output_file_name = 'qunit-output.tap'
            test_command = 'npx qunit test/ > ' + output_file_name
            
            output_path = self.dirty_path + '/' + output_file_name
            
            result = subprocess.run(test_command, cwd=self.dirty_path, shell=True, check=True, timeout=30)
            if result.returncode != 0:
                pass
                # raise subprocess.CalledProcessError(result.returncode, test_command)
            
            if os.path.exists(output_path):
                os.remove(output_path) 
            return []

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            with open(output_path, 'r') as output_file:
                test_output = output_file.read()

            file_line_pattern = r' *at Object.<anonymous> \((\S+underscore\D+):(\d+):\d+\)'
            errors = self.__parse_tap_output(test_output, file_line_pattern)

            if os.path.exists(output_path):
                os.remove(output_path) 
            return errors
