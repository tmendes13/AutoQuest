from google import genai
import os
from dotenv import load_dotenv
from google.genai import types

load_dotenv()

gemini_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key = gemini_key)

def setup_gm():
    return client.chats.create(
        model="gemini-3-flash-preview",
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are the Game Master of a DnD campaign. "
                "Narrate the story dramatically, describe the environment, "
                "enemies and consequences of the players' actions. "
                "Keep responses concise and engaging."
            )
        )
    )

def narrate(gm_chat, player_actions: list[str]) -> str:
    actions = "\n".join(player_actions)
    response = gm_chat.send_message(
        f"The players acted:\n{actions}\n\nNarrate the result and describe the new situation."
    )
    return response.text