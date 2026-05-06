from models.player import Player
from config import client, types, MODEL

def setup_agent(system_prompt: str):
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt
        )
    )

def act(player: Player, situation: str) -> str:
    context = f"Your status: {player.status()}\n\n Situation: {situation}\n\nWhat do you do?"
    response = player.chat.send_message(context)
    return response.text
