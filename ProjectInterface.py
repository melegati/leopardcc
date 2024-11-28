from abc import ABC, abstractmethod
from typing import TypedDict
import os
import shutil
import subprocess


class TestError(TypedDict):
    expectation: str
    message_stack: str
    test_file: str | None
    target_line: int | None


class ProjectInterface(ABC):
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

    def after_copy_hook(self) -> None:
        """Optional code to be executed to prepare running tests (e. g. installing 3rd party libraries)"""
        pass

    def create_copy(self) -> str:
        copy_suffix = '-copy'
        destination_path = self.project_path + copy_suffix

        if os.path.exists(destination_path):
            shutil.rmtree(destination_path)

        ignore_patterns = shutil.ignore_patterns('.git')
        path_of_copy = shutil.copytree(
            self.project_path, destination_path, dirs_exist_ok=True, ignore=ignore_patterns)

        self.after_copy_hook()

        return path_of_copy

    @abstractmethod
    def measure_test_coverage(self, project_path: str) -> None | str:
        pass

    @abstractmethod
    def get_test_errors(self, project_path: str) -> None | list[TestError]:
        pass

    @abstractmethod
    def get_test_case(self, error: TestError) -> str | None:
        pass
