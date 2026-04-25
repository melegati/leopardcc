from llm_wrappers.GoogleTokenCounter import GoogleTokenCounter
from llm_wrappers.OpenAIAPIWrapper import OpenAIAPIWrapper


class GoogleModelWrapper(OpenAIAPIWrapper):

    def __init__(self,
                 model: str,
                log_path: str,
                max_context_length: int = 128000,
                base_url: str = None):
        with open('google-key.txt', 'r', encoding='utf-8') as key_file:
            api_key = key_file.read()

        super().__init__(
            api_key = api_key,
            log_path = log_path,
            token_counter=GoogleTokenCounter(model, api_key),
            model = model,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )