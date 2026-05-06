import ollama
from dataclasses import dataclass

MODEL = "gpt-oss:20b-cloud"

# Wrapper para manter a mesma interface da API google.genai mas usar Ollama por baixo
@dataclass
class _Response:
    text: str

class _Chat:
    def __init__(self, model: str, system_instruction: str = ""):
        self.model = model
        self.messages = []
        if system_instruction:
            self.messages.append({"role": "system", "content": system_instruction})

    def send_message(self, message: str) -> _Response:
        self.messages.append({"role": "user", "content": message})
        response = ollama.chat(model=self.model, messages=self.messages)
        reply = response["message"]["content"]
        self.messages.append({"role": "assistant", "content": reply})
        return _Response(text=reply)

class _Chats:
    def create(self, model: str, config=None):
        sys_inst = config.system_instruction if config else ""
        return _Chat(model, sys_inst)

class _Client:
    chats = _Chats()

@dataclass
class _GenerateContentConfig:
    system_instruction: str = ""

class types:
    GenerateContentConfig = _GenerateContentConfig

client = _Client()