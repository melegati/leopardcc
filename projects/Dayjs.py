from interfaces.ProjectInterface import ProjectInterface
from interfaces.TestError import TestError
from interfaces.LintError import LintError
from helpers.ProjectHelper import get_eslint_errors, get_jest_errors, install_npm_packages


class Dayjs(ProjectInterface):
    @property
    def path(self):
        return '/media/lebkuchen/storage-disk/Repos/thesis-projects/dayjs'

    @property
    def code_dir(self):
        return '/src'

    def after_copy_hook(self, path_suffix) -> None:
        project_copy_path = self.path + path_suffix
        install_npm_packages(project_copy_path)

    def get_lint_errors(self):
        lint_command = 'npx eslint src/* test/* build/*'
        errors = get_eslint_errors(self.dirty_path, lint_command)

        return errors

    def get_test_errors(self):
        test_command = 'npx jest' 
        line_pattern = r' *at Object.<anonymous> \(\S+dayjs\D+:(\d+):\d+\)'

        errors = get_jest_errors(self.dirty_path, test_command, line_pattern)
        return errors
