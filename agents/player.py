from google import genai
from models.player import Player
from google.genai import types
from config import client

def setup_agent(system_prompt: str):
    return client.chats.create(
        model="gemini-3-flash-preview",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt
        )
    )

def act(player: Player, situation: str) -> str:
    context = f"Your status: {player.status()}\n\n Situation: {situation}\n\nWhat do you do?"
    response = player.chat.send_message(context)
    return response.text
    
