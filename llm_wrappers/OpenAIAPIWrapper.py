from interfaces.LlmWrapperInterface import LLMWrapperInterface
import json
from pathlib import Path
from openai import OpenAI, RateLimitError
import time
from llm_wrappers.TokenCounter import TokenCounter
from util.Logger import get_logger
from random import randint


class OpenAIAPIWrapper(LLMWrapperInterface):
    @staticmethod
    def name():
        return "OpenAI API wrapper"
    
    def __init__(self, 
                 api_key: str, 
                 log_path: str, 
                 token_counter: TokenCounter, 
                 model: str, 
                 max_context_length: int = 128000, 
                 base_url: str = None):
        self.api_key = api_key
        self.__model = model
        self.log_path = log_path
        self.max_context_length = max_context_length
        self.messages: list[dict[str, str]] = []
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.token_counter = token_counter
        self.__sent_tokens_count = 0
        self.__received_tokens_count = 0
    
    @property
    def model(self):
        return self.__model

    @property
    def sent_tokens_count(self):
        return self.__sent_tokens_count

    @property
    def received_tokens_count(self):
        return self.__received_tokens_count

    def __add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def __get_context(self, prompt: str) -> list:
        context = self.messages + [{"role": "user", "content": prompt}]

        context_length = self.token_counter.get_context_length(context)
        if self.max_context_length > 0:
            while context_length > self.max_context_length and len(context) > 1:
                # Remove oldest message until within length limit
                context.pop(0)
                context_length = self.__get_context_length(context)

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

        was_completion_successful = False
        base_delay = 5
        while not was_completion_successful:
            try:
                completion = self.client.chat.completions.create(
                    model=self.__model,
                    messages=context
                )
                was_completion_successful = True
            
            except RateLimitError as e:
                delay = base_delay + randint(1, 5)
                get_logger().error("Rate limit error: " + e.message)
                get_logger().error("Context length: " + self.__get_context_length(context))
                if base_delay > 60:
                    get_logger().fatal("Failed to get answer from OpenAI.")
                    raise Exception("Failed to get answer from OpenAI.")
                get_logger().info("Waiting " + str(delay) + "s before next attempt")
                time.sleep(delay)
                base_delay +=5

        self.__sent_tokens_count += completion.usage.prompt_tokens

        response_content = str(completion.choices[0].message.content)
        self.__received_tokens_count += completion.usage.completion_tokens

        self.__add_message("user", prompt)
        self.__add_message("assistant", response_content)
        self.__save_history_to_json()

        return response_content


