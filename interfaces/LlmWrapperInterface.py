from abc import ABC, abstractmethod


class LLMWrapperInterface(ABC):
    @staticmethod
    @abstractmethod
    def name() -> str:
        """Provide a short, descriptive name, to differentiate this llm wrapper from others"""
        pass
    
    @property
    @abstractmethod
    def sent_tokens_count(self) -> int:
        pass

    @property
    @abstractmethod
    def received_tokens_count(self) -> int:
        pass

    @abstractmethod
    def send_message(self, prompt: str) -> str:
        pass