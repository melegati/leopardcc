from llm_wrappers.OpenAIAPIWrapper import OpenAIAPIWrapper
from llm_wrappers.TiktokenTokenCounter import TiktokenTokenCounter


class OpenAIModelWrapper(OpenAIAPIWrapper):

    def __init__(self,
                 model: str,
                 log_path: str,
                 max_context_length: int = 128000,
                 base_url: str = None):
        with open('openai-key.txt', "r", encoding="utf-8") as key_file:
            api_key = key_file.read()
        super().__init__(
            api_key=api_key,
            log_path=log_path,
            token_counter=TiktokenTokenCounter(model),
            model=model,
            max_context_length=max_context_length,
            base_url=base_url)