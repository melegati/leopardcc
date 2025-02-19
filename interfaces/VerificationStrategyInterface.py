from abc import ABC, abstractmethod
from interfaces.Function import Function


class VerificationStrategyInterface(ABC):
    """Provides methods to verify the correct behavior and the improvement of a software project"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provide a short, descriptive name, to differentiate this strategy from others"""
        pass
    
    @abstractmethod
    def verify_linting(self, function: Function):
        """Runs linting and attempts to fix potentially occuring errors"""
        pass

    @abstractmethod
    def verify_tests(self, function: Function):
        """Runs tests and attempts to fix potentially failing tests"""
        pass

    @abstractmethod
    def verify_improvement(self, function: Function):
        """Compares CC of refactored with original function and attempts to further improve refactoring if not satisfactory"""
        pass
