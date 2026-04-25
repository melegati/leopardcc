from transformers import AutoTokenizer

from llm_wrappers.TokenCounter import TokenCounter


class TransformersTokenCounter(TokenCounter):

    def __init__(self, hf_tokenizer):
        self.tokenizer = AutoTokenizer.from_pretrained(hf_tokenizer)

    def count_tokens(self, message):
        return len(self.tokenizer.encode(message, add_special_tokens=False))