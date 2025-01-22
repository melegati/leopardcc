from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import get_eslint_errors_from_json_stdout, get_mocha_errors_from_json_stdout
import shutil
import subprocess
import json
import os


class Expressjs(ProjectInterface):
    @property
    def path(self):
        return '/media/lebkuchen/storage-disk/Repos/express'

    @property
    def code_dir(self):
        return '/lib'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        node_modules_dir = '/node_modules'
        shutil.rmtree(project_copy_path + node_modules_dir)
        subprocess.run(['cd ' + project_copy_path +
                        ' && npm install'],
                       shell=True, capture_output=True, text=True, check=True)

    def run_lint_fix(self, code):
        patch_file_path = self.dirty_path + "/patch.js"
        with open(patch_file_path, 'w') as patch_file:
            patch_file.write(code)
        
        lint_fix_command = 'cat patch.js | npx eslint --stdin --format json --fix-dry-run'
        proc = subprocess.run(['cd ' + self.dirty_path + ' && ' + lint_fix_command],
                           shell=True, capture_output=True, text=True, check=False)

        os.remove(patch_file_path) 
        
        linter_output = json.loads(proc.stdout)
        if 'output' in linter_output[0]:
            improved_code = linter_output[0]['output']
            return improved_code
        
        return code

    def get_lint_errors(self):
        try:
            lint_command = 'npx eslint . --format json'
            subprocess.run(['cd ' + self.dirty_path + ' && ' + lint_command],
                           shell=True, capture_output=True, text=True, check=True, timeout=10)
            return []

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            if e.stdout is None:
                raise Exception(
                    "Linting result does not have stdout to read from")

            errors = get_eslint_errors_from_json_stdout(e.stdout)
            return errors

    def get_test_errors(self):
        try:
            mocha_json_name = 'mocha-output.json'
            test_command = 'npx mocha --require test/support/env --check-leaks test/ test/acceptance/ --reporter json --reporter-option output=' + mocha_json_name

            mocha_json_output_path = self.dirty_path + '/' + mocha_json_name
            
            subprocess.run(['cd ' + self.dirty_path + ' && ' + test_command],
                           shell=True, capture_output=True, text=True, check=True, timeout=10)
            
            if os.path.exists(mocha_json_output_path):
                os.remove(mocha_json_output_path) 
            return []

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            with open(mocha_json_output_path, 'r') as mocha_json_file:
                mocha_json_output = mocha_json_file.read()
            
            line_pattern = r' *at Context.<anonymous> \([^\d]+:(\d+):\d+\)'
            errors = get_mocha_errors_from_json_stdout(mocha_json_output, line_pattern)
            
            if os.path.exists(mocha_json_output_path):
                os.remove(mocha_json_output_path) 
            return errors
