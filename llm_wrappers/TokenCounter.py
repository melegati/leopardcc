import operator
from abc import ABC, abstractmethod
from functools import reduce


class TokenCounter(ABC):

    @abstractmethod
    def count_tokens(self, message: str) -> int:
        pass

    def get_context_length(self, context: list[dict[str, str]]) -> int:
        tokenized_messages = list([self.count_tokens(msg["content"])] for msg in context)
        tokens_per_message = list(len(tokens) for tokens in tokenized_messages)

        context_length = reduce(operator.add, tokens_per_message)
        return context_length