from abc import ABC, abstractmethod


class LLMWrapperInterface(ABC):
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