from llm_wrappers.TokenCounter import TokenCounter


import tiktoken


class TiktokenTokenCounter(TokenCounter):

    def __init__(self, model):
        self.tokenizer = tiktoken.encoding_for_model(model)

    def count_tokens(self, message: str) -> int:
        return len(self.tokenizer.encode(message))