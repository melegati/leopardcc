from abc import ABC, abstractmethod
from .LintError import LintError
from .TestError import TestError


class PromptStrategyInterface(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provide a short, descriptive name, to differentiate this strategy from others"""
        pass
    
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
