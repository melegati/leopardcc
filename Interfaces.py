from abc import ABC, abstractmethod
from typing import TypedDict
import os
import shutil
import subprocess


class LintError(TypedDict):
    rule_id: str
    message: str
    file: str
    target_line: int
    erroneous_code: str


class TestError(TypedDict):
    expectation: str
    message_stack: str
    test_file: str
    target_line: int | None


class ProjectInterface(ABC):
    __dirty_path: str | None = None
    __target_path: str | None = None

    @property
    @abstractmethod
    def project_path(self) -> str:
        """The path to the root folder of the project"""
        pass

    @property
    @abstractmethod
    def code_dir(self) -> str:
        """The directory inside the project which holds the source code (e. g. 'src', 'lib', ...)"""
        pass

    def after_copy_hook(self, path_suffix: str) -> None:
        """Optional code to be executed to prepare running tests (e. g. installing 3rd party libraries)"""
        pass

    def __create_copy(self, path_suffix: str) -> str:
        destination_path = self.project_path + path_suffix

        if os.path.exists(destination_path):
            shutil.rmtree(destination_path)

        ignore_patterns = shutil.ignore_patterns('.git')
        path_of_copy = shutil.copytree(
            self.project_path, destination_path, dirs_exist_ok=True, ignore=ignore_patterns)

        self.after_copy_hook(path_suffix)

        return path_of_copy

    @property
    def dirty_path(self) -> str:
        if self.__dirty_path is None:
            self.__dirty_path = self.__create_copy('-dirty')

        return self.__dirty_path

    @property
    def target_path(self) -> str:
        if self.__target_path is None:
            self.__target_path = self.__create_copy('-target')

        return self.__target_path

    @abstractmethod
    def get_lint_errors(self, project_path: str) -> list[LintError]:
        """Checks source code for stylistic and programmatic errors and returns them.
        If no errors were found it returns an empty list."""
        pass

    @abstractmethod
    def get_test_errors(self, project_path: str) -> list[TestError]:
        """Runs projects unit tests and returns list of failing tests.
        If no test fails it returns an empty list."""
        pass

    @abstractmethod
    def get_test_case(self, error: TestError) -> None | str:
        """Returns the test code for a given failing test case."""
        pass


class PromptStrategyInterface(ABC):
    @abstractmethod
    def initial_prompt(self, code: str) -> str:
        """Ask for refactoring a function to achieve a better maintainability and readability."""
        pass

    @abstractmethod
    def linting_explanation_prompt(self, errors: list[LintError]) -> str:
        """Ask for an explanation why given linting errors were thrown."""
        pass

    @abstractmethod
    def linting_fix_prompt(self) -> str:
        """Ask for code that fixes linting errors."""
        pass

    @abstractmethod
    def test_explanation_prompt(self, errors: list[TestError], test_cases: list[str]) -> str:
        """Ask for an explanation why given tests with their test cases fail."""
        pass

    @abstractmethod
    def test_fix_prompt(self) -> str:
        """Ask for code that fixes tests."""
        pass

    @abstractmethod
    def better_improvement_explanation_prompt(self) -> str:
        """Ask for an explanation of how the code can be improved further."""
        pass

    @abstractmethod
    def better_improvement_fix_prompt(self) -> str:
        """Ask for code that further improves the maintainability and readability."""
        pass
