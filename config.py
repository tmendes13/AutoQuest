import os
import json
import ollama
import sys
from dataclasses import dataclass

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_LOGS_DIR = os.path.join(_PROJECT_ROOT, "logs")

class ConsoleJsonLogger:
    def __init__(self, original_stdout, log_path=None):
        if log_path is None:
            log_path = os.path.join(_LOGS_DIR, "log.json")
        self.original_stdout = original_stdout
        self.log_path = log_path
        self.buffer = []
        try:
            parent = os.path.dirname(self.log_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def write(self, text):
        self.original_stdout.write(text)
        if text:
            self.buffer.append(text)
            full_text = "".join(self.buffer)
            lines = full_text.splitlines()
            try:
                with open(self.log_path, "w", encoding="utf-8") as f:
                    json.dump(lines, f, ensure_ascii=False, indent=2)
            except OSError:
                pass

    def flush(self):
        self.original_stdout.flush()

    def __getattr__(self, name):
        return getattr(self.original_stdout, name)

# Redirect stdout automatically upon import
if not isinstance(sys.stdout, ConsoleJsonLogger):
    sys.stdout = ConsoleJsonLogger(sys.stdout)

MODEL = "gpt-oss:20b-cloud"

TOKEN_PATH = None

def get_token_path(memory_path: str) -> str:
    """Derive the tokens path in the logs/ directory from the campaign memory path."""
    return os.path.join(_LOGS_DIR, "tokens.json")


def init_tokens(memory_path: str) -> None:
    """Reset the tokens tracking JSON file."""
    global TOKEN_PATH
    TOKEN_PATH = get_token_path(memory_path)
    parent = os.path.dirname(TOKEN_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if os.path.exists(TOKEN_PATH):
        try:
            os.remove(TOKEN_PATH)
        except OSError:
            pass
    # Initialize with an empty dictionary
    try:
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def track_tokens(agent_name: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Incrementally track the tokens consumed by the specified agent and keep a general total at the end."""
    global TOKEN_PATH
    if not TOKEN_PATH:
        return
    
    # Read existing
    try:
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
    except (json.JSONDecodeError, OSError):
        data = {}
        
    # Remove total_general if it exists to re-calculate it freshly
    data.pop("total_general", None)
    
    # Get agent's stats
    agent_data = data.setdefault(agent_name, {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "calls": 0
    })
    
    # Update stats
    agent_data["prompt_tokens"] += prompt_tokens
    agent_data["completion_tokens"] += completion_tokens
    agent_data["total_tokens"] += (prompt_tokens + completion_tokens)
    agent_data["calls"] += 1
    
    # Calculate fresh total_general across all agents
    total_prompt = sum(stats.get("prompt_tokens", 0) for stats in data.values())
    total_completion = sum(stats.get("completion_tokens", 0) for stats in data.values())
    total_calls = sum(stats.get("calls", 0) for stats in data.values())
    total_tokens = total_prompt + total_completion
    
    data["total_general"] = {
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "calls": total_calls
    }
    
    # Save back to file
    try:
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# Wrapper para manter a mesma interface da API google.genai mas usar Ollama por baixo
@dataclass
class _Response:
    text: str


class _Chat:
    def __init__(self, model: str, system_instruction: str = ""):
        self.model = model
        self.system_instruction = system_instruction
        self.messages = []
        self.agent_name = "unknown"  # Dynamically set after setup
        if system_instruction:
            self.messages.append({"role": "system", "content": system_instruction})

    def send_message(self, message: str, remember: bool = True) -> _Response:
        agent_name = getattr(self, "agent_name", "unknown")
        
        if not remember:
            messages = []
            if self.system_instruction:
                messages.append({"role": "system", "content": self.system_instruction})
            messages.append({"role": "user", "content": message})
            response = ollama.chat(model=self.model, messages=messages)
            
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)
            track_tokens(agent_name, prompt_tokens, completion_tokens)
            
            return _Response(text=response["message"]["content"])
            
        self.messages.append({"role": "user", "content": message})
        response = ollama.chat(model=self.model, messages=self.messages)
        reply = response["message"]["content"]
        self.messages.append({"role": "assistant", "content": reply})
        
        prompt_tokens = response.get("prompt_eval_count", 0)
        completion_tokens = response.get("eval_count", 0)
        track_tokens(agent_name, prompt_tokens, completion_tokens)
        
        return _Response(text=reply)


def send_chat_message(chat, message: str, remember: bool = True) -> _Response:
    try:
        return chat.send_message(message, remember=remember)
    except TypeError:
        return chat.send_message(message)


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