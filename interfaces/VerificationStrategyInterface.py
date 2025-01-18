from abc import ABC, abstractmethod
from interfaces.Function import Function


class VerificationStrategyInterface(ABC):
    """Provides methods to verify the correct behavior and the improvement of a software project"""

    @abstractmethod
    def verify_linting(self, function: Function):
        """Runs linting and attempts to fix potentially occuring errors"""
        pass

    @abstractmethod
    def verify_unit_tests(self, function: Function):
        """Runs unit tests and attempts to fix potentially failing tests"""
        pass

    @abstractmethod
    def verify_improvement(self, function: Function, functions_to_ignore: list[Function]):
        """Compares CC of refactored with original function and attempts to further improve refactoring if not satisfactory"""
        pass
