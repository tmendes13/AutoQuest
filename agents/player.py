from google import genai
import os
from dotenv import load_dotenv
from models.player import Player
from google.genai import types

load_dotenv()

gemini_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key = gemini_key)

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
    
