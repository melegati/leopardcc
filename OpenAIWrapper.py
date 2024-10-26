from openai import OpenAI
import json

class OpenAIWrapper:
  def __init__(self, api_key: str, model: str = "gpt-4o-mini", max_context_length: int = 4096):
    self.api_key = api_key
    self.model = model
    self.max_context_length = max_context_length
    self.messages: list[dict[str, str]] = []
    self.client = OpenAI(api_key=self.api_key)

  def add_message(self, role: str, content: str):
    self.messages.append({"role": role, "content": content})

  def get_context(self, prompt: str) -> list:
    context = self.messages + [{"role": "user", "content": prompt}]
    
    total_tokens = sum(len(msg["content"].split()) for msg in context)
    while total_tokens > self.max_context_length and len(context) > 1:
        context.pop(0)  # Remove oldest message until within length limit
        total_tokens = sum(len(msg["content"].split()) for msg in context)

    return context

  def save_history_to_json(self, file_path: str):
    try:
        with open(file_path, 'w') as json_file:
            json.dump(self.messages, json_file, indent=4)
        print(f"Conversation history saved to {file_path}")
    except IOError as e:
        print(f"Failed to save history to {file_path}: {e}")

  def send_message(self, prompt: str):
    context = self.get_context(prompt)
    
    completion = self.client.chat.completions.create(
      model=self.model,
      messages=context
    )
    response_content = str(completion.choices[0].message.content)
    
    self.add_message("user", prompt)
    self.add_message("assistant", response_content)

    return response_content

  
  def clear_history(self):
    self.messages = []
