from abc import ABC, abstractmethod
import os
import shutil
from .LintError import LintError
from .TestError import TestError
import re
from pathlib import Path


class ProjectInterface(ABC):
    __dirty_path: str | None = None
    __target_path: str | None = None
    # __linter_config: str | None = None

    @property
    @abstractmethod
    def path(self) -> str:
        """The path to the root folder of the project"""
        pass

    @property
    def name(self) -> str:
        after_last_slash_pattern = r'([^\/]+)$'
        name_match = re.search(after_last_slash_pattern, self.path)
        if name_match is not None:
            return name_match.group(1)
        return self.path

    @property
    @abstractmethod
    def code_dir(self) -> str:
        """The directory inside the project which holds the source code (e. g. 'src', 'lib', ...)"""
        pass

    # @property
    # @abstractmethod
    # def linter_config_file(self) -> str:
    #     """The path inside the project to the linter config file."""
    #     pass

    def after_copy_hook(self, path_suffix: str) -> None:
        """Optional code to be executed to prepare running tests (e. g. installing 3rd party libraries)"""
        pass

    def __create_copy(self, path_suffix: str) -> str:
        destination_path = self.path + path_suffix

        if os.path.exists(destination_path):
            shutil.rmtree(destination_path)

        path_of_copy = shutil.copytree(
            self.path, destination_path, dirs_exist_ok=True, symlinks=True)

        self.after_copy_hook(path_suffix)

        return path_of_copy

    @property
    def dirty_path(self) -> str:
        """The path to the 'dirty' copy of the project. This is where code is being manipulated and tested."""
        if self.__dirty_path is None:
            self.__dirty_path = self.__create_copy('-dirty')

        return self.__dirty_path

    @property
    def target_path(self) -> str:
        """The path to the improved version of the project. This is where only verified changes are appplied."""
        if self.__target_path is None:
            self.__target_path = self.__create_copy('-target')

        return self.__target_path

    def run_lint_fix(self, code: str) -> str:
        """Optional: Resolve automatically fixable linting errors before applying code changes"""
        return code

    @abstractmethod
    def get_lint_errors(self) -> list[LintError]:
        """Checks source code for stylistic and programmatic errors and returns them.
        If no errors were found it returns an empty list."""
        pass

    @abstractmethod
    def get_test_errors(self) -> list[TestError]:
        """Runs tests and returns list of failing tests.
        If no test fails it returns an empty list."""
        pass

    def get_test_case(self, error: TestError) -> None | str:
        """Returns the test code for a given failing test case."""

        if error['target_line'] is None or error['test_file'] is None:
            return None

        with open(error['test_file'], 'r') as f:
            lines = f.readlines()

        # Find the start and end of the surrounding `it()` closure.
        start_line = error['target_line']

        # Traverse upwards to find the start of the `it()` closure.
        while start_line > 0 and not (lines[start_line].strip().startswith("it(")
                                      or lines[start_line].strip().startswith("test(")):
            start_line -= 1

        # Traverse downwards to find the end of the closure (assuming balanced braces).
        end_line = start_line
        open_braces = 0
        while end_line < len(lines):
            line = lines[end_line]
            open_braces += line.count('{')
            open_braces -= line.count('}')
            end_line += 1
            if open_braces == 0:
                break

        # Get the closure content
        test_case_lines = lines[start_line:end_line]

        white_spaces_count = len(test_case_lines[0]) - \
            len(test_case_lines[0].lstrip())
        test_case = ''
        for line in test_case_lines:
            test_case += line.removeprefix(white_spaces_count * ' ').rstrip()

        return test_case
    
    # @property
    # def linter_config(self) -> str:
    #     if self.__linter_config is None:
    #         if self.linter_config_file is None:
    #             self.__linter_config= None
    #         else: 
    #             with open(Path(self.path) / self.linter_config_file, 'r') as f:
    #                 self.__linter_config = f.read()

    #     return self.__linter_config
                
        