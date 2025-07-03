from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import (
    install_npm_packages, fix_eslint_issues,
    get_eslint_errors, get_mocha_errors_from_stdout,
)


class Supertest(ProjectInterface):
    @property
    def path(self):
        return 'repos/supertest'

    @property
    def code_dir(self):
        return '/'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        install_npm_packages(project_copy_path)

    def run_lint_fix(self, code):
        fixed_code = fix_eslint_issues(code, self.dirty_path)

        return fixed_code

    def get_lint_errors(self):
        lint_command = 'npx eslint lib/**/*.js test/**/*.js index.js'
        errors = get_eslint_errors(self.dirty_path, lint_command)

        return errors

    def get_test_errors(self):
        test_command = 'npx mocha --require should --exit'
        line_pattern = r' *at Context.<anonymous> \(\D+:(\d+):\d+\)'

        errors = get_mocha_errors_from_stdout(self.dirty_path, test_command, line_pattern)
        return errors
