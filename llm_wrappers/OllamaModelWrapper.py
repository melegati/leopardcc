from llm_wrappers.OpenAIAPIWrapper import OpenAIAPIWrapper
from llm_wrappers.TransformersTokenCounter import TransformersTokenCounter


class OllamaModelWrapper(OpenAIAPIWrapper):

    configured_models = { 'deepseek-r1:1.5b': { 
                                'max_context': 128000, 
                                'hf_tokenizer': "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"  },
                          'gpt-oss:120b': {
                                'max_context': 128000, 
                                'hf_tokenizer': "openai/gpt-oss-120b"  },
                          'qwen3.6:35b': {
                                'max_context': 256000, 
                                'hf_tokenizer': "Qwen/Qwen3.6-35B-A3B"  },      
                        }
    
    @staticmethod
    def get_configured_models():
        return list(OllamaModelWrapper.configured_models.keys())

    def __init__(self,
                 model: str,
                log_path: str):

        super().__init__(
            api_key = "ollama", #ignored
            log_path = log_path,
            token_counter=TransformersTokenCounter(self.configured_models[model]['hf_tokenizer']),
            model = model,
            max_context_length=self.configured_models[model]['max_context'],
            base_url="http://localhost:11434/v1/"
        )