from interfaces.ProjectInterface import ProjectInterface
from interfaces.LintError import LintError
from interfaces.TestError import TestError
from helpers.ProjectHelper import get_eslint_errors_from_json_stdout, get_mocha_errors_from_json_stdout
import shutil
import subprocess
import re
import json


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

    def get_lint_errors(self):
        try:
            lint_command = 'npx eslint src test --fix --format json'
            subprocess.run(['cd ' + self.dirty_path + ' && ' + lint_command],
                           shell=True, capture_output=True, text=True, check=True, timeout=7)
            return []

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            if e.stdout is None:
                raise Exception(
                    "Linting result does not have stdout to read from")

            errors = get_eslint_errors_from_json_stdout(e.stdout)
            return errors

    def get_test_errors(self):
        try:
            test_command = 'npx mocha "test/**/*-test.js" --reporter json'
            subprocess.run(['cd ' + self.dirty_path + ' && ' + test_command],
                           shell=True, capture_output=True, text=True, check=True, timeout=7)
            return []

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            if e.stdout is None:
                raise Exception("Unit tests do not have stdout to read from")
            line_pattern = r' *at Context.<anonymous> \S+d3-shape\D+:(\d+):\d+\)\n'
            errors = get_mocha_errors_from_json_stdout(e.stdout, line_pattern)

            return errors
