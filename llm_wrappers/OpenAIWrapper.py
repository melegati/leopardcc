from interfaces.LlmWrapperInterface import LLMWrapperInterface
import json
from pathlib import Path
from openai import OpenAI, RateLimitError
import tiktoken
from functools import reduce
import operator
import time
from util.Logger import get_logger
from random import randint


class OpenAIWrapper(LLMWrapperInterface):
    def __init__(self, api_key: str, log_path: str, model: str = "gpt-4o-mini", max_context_length: int = 128000):
        self.api_key = api_key
        self.model = model
        self.log_path = log_path
        self.max_context_length = max_context_length
        self.messages: list[dict[str, str]] = []
        self.client = OpenAI(api_key=self.api_key)
        self.tokenizer = tiktoken.encoding_for_model(model)
        self.__sent_tokens_count = 0
        self.__received_tokens_count = 0

    @property
    def name(self):
        return "OpenAI wrapper"
    
    @property
    def sent_tokens_count(self):
        return self.__sent_tokens_count

    @property
    def received_tokens_count(self):
        return self.__received_tokens_count

    def __add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def __get_context_length(self, context: list[dict[str, str]]) -> int:
        tokenized_messages = list(self.tokenizer.encode(msg["content"])
                                  for msg in context)
        tokens_per_message = list(len(tokens) for tokens in tokenized_messages)

        context_length = reduce(operator.add, tokens_per_message)
        return context_length

    def __get_context(self, prompt: str) -> list:
        context = self.messages + [{"role": "user", "content": prompt}]

        context_length = self.__get_context_length(context)
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
                    model=self.model,
                    messages=context
                )
                was_completion_successful = True
            
            except RateLimitError as e:
                delay = base_delay + randint(1, 5)
                get_logger().error("Rate limit error: " + e.message)
                get_logger().info("Waiting " + str(delay) + "s before next attempt")
                time.sleep(delay)
                base_delay +=5


        context_length = self.__get_context_length(context)
        self.__sent_tokens_count += context_length

        response_content = str(completion.choices[0].message.content)
        tokenized_response = self.tokenizer.encode(response_content)
        response_tokens_count = len(tokenized_response)
        self.__received_tokens_count += response_tokens_count

        self.__add_message("user", prompt)
        self.__add_message("assistant", response_content)
        self.__save_history_to_json()

        return response_content
