from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import (
    install_npm_packages, fix_eslint_issues, 
    get_eslint_errors, get_vitest_errors
)
import subprocess


class Svelte(ProjectInterface):
    @property
    def path(self):
        return 'repos/svelte'

    @property
    def code_dir(self):
        return '/packages'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        install_npm_packages(project_copy_path, package_manager_command='pnpm')
        subprocess.run(['cd ' + project_copy_path + ' && pnpm build'],
                    shell=True, capture_output=True, text=True, check=True)
        

    def run_lint_fix(self, code):
        fixed_code = fix_eslint_issues(code, self.dirty_path, package_manager_command='pnpm')

        return fixed_code

    def get_lint_errors(self):
        lint_command = 'pnpm eslint'
        errors = get_eslint_errors(self.dirty_path, lint_command)
        return errors

    def get_test_errors(self):
        test_command = 'pnpm vitest run'
        line_pattern = r' *at Context.<anonymous> \([^\d]+:(\d+):\d+\)'
        
        errors = get_vitest_errors(self.dirty_path, test_command, line_pattern)
        return errors