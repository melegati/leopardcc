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
        pass

    @abstractmethod
    def get_test_errors(self, project_path: str) -> list[TestError]:
        pass

    @abstractmethod
    def get_test_case(self, error: TestError) -> None | str:
        pass
