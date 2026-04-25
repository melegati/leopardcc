from llm_wrappers.TokenCounter import TokenCounter


from google import genai


class GoogleTokenCounter(TokenCounter):

    def __init__(self, model, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def count_tokens(self, message: str) -> int:
        return self.client.models.count_tokens(model=self.model, contents=message)