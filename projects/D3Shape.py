from interfaces.ProjectInterface import ProjectInterface
from interfaces.LintError import LintError
from interfaces.TestError import TestError
from helpers.ProjectHelper import fix_eslint_issues, get_eslint_errors, get_mocha_errors
import shutil
import subprocess


class D3Shape(ProjectInterface):
    @property
    def path(self):
        return '/media/lebkuchen/storage-disk/Repos/d3-shape'

    @property
    def code_dir(self):
        return '/src'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        node_modules_dir = '/node_modules'
        shutil.rmtree(project_copy_path + node_modules_dir)
        subprocess.run(['cd ' + project_copy_path +
                        ' && yarn install'],
                       shell=True, capture_output=True, text=True, check=True)

    def run_lint_fix(self, code):
        fixed_code = fix_eslint_issues(code, self.dirty_path)

        return fixed_code
    
    def get_lint_errors(self):
        lint_command = 'npx eslint src'
        errors = get_eslint_errors(self.dirty_path, lint_command)

        return errors

    def get_test_errors(self):
        test_command = 'npx mocha "test/**/*-test.js"'
        line_pattern = r' *at Context.<anonymous> \S+d3-shape\D+:(\d+):\d+\)\n'
        errors = get_mocha_errors(self.dirty_path, test_command, line_pattern)

        return errors
