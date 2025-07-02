from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import (
    install_npm_packages, fix_eslint_issues,
    get_eslint_errors, get_jest_errors, 
)


class GithubReadmeStats(ProjectInterface):
    @property
    def path(self):
        return 'repos/github-readme-stats'

    @property
    def code_dir(self):
        return '/src'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        install_npm_packages(project_copy_path)

    def run_lint_fix(self, code):
        fixed_code = fix_eslint_issues(code, self.dirty_path)

        return fixed_code

    def get_lint_errors(self):
        lint_command = 'npx eslint --max-warnings 0 "./src/**/*.js" "./scripts/**/*.js" "./tests/**/*.js" "./api/**/*.js" "./themes/**/*.js"'
        errors = get_eslint_errors(self.dirty_path, lint_command)

        return errors

    def get_test_errors(self):
        test_command = 'node --experimental-vm-modules node_modules/jest/bin/jest.js'
        line_pattern = r' *at Object.<anonymous> \(\S+github\-readme\D+:(\d+):\d+\)'

        errors = get_jest_errors(self.dirty_path, test_command, line_pattern)
        return errors
