from llm_wrappers.GoogleTokenCounter import GoogleTokenCounter
from llm_wrappers.OpenAIAPIWrapper import OpenAIAPIWrapper


class GoogleModelWrapper(OpenAIAPIWrapper):

    configured_models_max_context = { 'gemini-2.5-flash': 1048576 }
    
    @staticmethod
    def get_configured_models():
        return list(GoogleModelWrapper.configured_models_max_context.keys())

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
            max_context_length=self.configured_models_max_context[model],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )