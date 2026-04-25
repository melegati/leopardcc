from llm_wrappers.OpenAIAPIWrapper import OpenAIAPIWrapper
from llm_wrappers.TiktokenTokenCounter import TiktokenTokenCounter


class OpenAIModelWrapper(OpenAIAPIWrapper):

    configured_models_max_context = {'gpt-4o-mini': 128000, 
                                     'gpt-4.1-mini':1047576, 
                                     'gpt-5-mini': 400000}
    
    @staticmethod
    def get_configured_models():
        return list(OpenAIModelWrapper.configured_models_max_context.keys())

    def __init__(self,
                 model: str,
                 log_path: str,
                 base_url: str = None):
        with open('openai-key.txt', "r", encoding="utf-8") as key_file:
            api_key = key_file.read()
        super().__init__(
            api_key=api_key,
            log_path=log_path,
            token_counter=TiktokenTokenCounter(model),
            model=model,
            max_context_length=self.configured_models_max_context[model],
            base_url=base_url)