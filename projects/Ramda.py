from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import (
    install_npm_packages, fix_eslint_issues,
    get_eslint_errors, get_mocha_errors, 
)


class Ramda(ProjectInterface):
    @property
    def path(self):
        return 'repos/ramda'

    @property
    def code_dir(self):
        return '/source'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        install_npm_packages(project_copy_path)

    def run_lint_fix(self, code):
        fixed_code = fix_eslint_issues(code, self.dirty_path)

        return fixed_code

    def get_lint_errors(self):
        lint_command = 'npx eslint scripts/bookmarklet scripts/*.js source/*.js source/internal/*.js test/*.js test/**/*.js lib/sauce/*.js lib/bench/*.js'
        errors = get_eslint_errors(self.dirty_path, lint_command)

        return errors

    def get_test_errors(self):
        test_command = 'npx cross-env BABEL_ENV=cjs mocha --require @babel/register' 
        line_pattern = r' *at Context.<anonymous> \(\D+:(\d+):\d+\)'

        errors = get_mocha_errors(self.dirty_path, test_command, line_pattern)
        return errors
