import json
from pathlib import Path
from openai import OpenAI


class OpenAIWrapper:
    def __init__(self, api_key: str, log_path: str, model: str = "gpt-4o-mini", max_context_length: int = 128000):
        self.api_key = api_key
        self.model = model
        self.log_path = log_path
        self.max_context_length = max_context_length
        self.messages: list[dict[str, str]] = []
        self.client = OpenAI(api_key=self.api_key)

    def __add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def __get_context(self, prompt: str) -> list:
        context = self.messages + [{"role": "user", "content": prompt}]

        total_tokens = sum(len(msg["content"].split()) for msg in context)
        if self.max_context_length != -1:
            while total_tokens > self.max_context_length and len(context) > 1:
                # Remove oldest message until within length limit
                context.pop(0)
                total_tokens = sum(len(msg["content"].split())
                                   for msg in context)

        return context

    def __save_history_to_json(self):
        try:
            file = Path(self.log_path)
            file.parent.mkdir(exist_ok=True, parents=True)

            with open(self.log_path, 'w') as json_file:
                json.dump(self.messages, json_file, indent=4)
        except IOError as e:
            print(
                f"Failed to save message history to {self.log_path}: {e}")

    def send_message(self, prompt: str):
        context = self.__get_context(prompt)

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=context
        )
        response_content = str(completion.choices[0].message.content)

        self.__add_message("user", prompt)
        self.__add_message("assistant", response_content)
        self.__save_history_to_json()

        return response_content
