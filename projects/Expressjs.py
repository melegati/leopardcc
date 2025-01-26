from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import fix_eslint_issues, get_eslint_errors, get_mocha_errors
import shutil
import subprocess


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
        fixed_code = fix_eslint_issues(code, self.dirty_path)

        return fixed_code

    def get_lint_errors(self):
        lint_command = 'npx eslint .'
        errors = get_eslint_errors(self.dirty_path, lint_command)

        return errors

    def get_test_errors(self):
        test_command = 'npx mocha --require test/support/env --check-leaks test/ test/acceptance/'
        line_pattern = r' *at Context.<anonymous> \([^\d]+:(\d+):\d+\)'
        
        errors = get_mocha_errors(self.dirty_path, test_command, line_pattern)
        return errors
