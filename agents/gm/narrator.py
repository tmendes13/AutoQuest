from config import client, types, MODEL

def setup_narrator():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are the narrator of a Game Master of a DnD campaign. "
                "Narrate the story dramatically, describe the environment, "
                "enemies and consequences of the players' actions. "
                "Keep responses concise and engaging."
                "You'll receive the player's action from the memory keeper of the Game Master"
            )
        )
    )

def start_campaign(gm_chat) -> str:
    prompt = (
        "Start the campaign. Describe the setting, the current threat or mystery, "
        "and end by asking the players what they do."
    )

    response = gm_chat.send_message(prompt)
    return response.text

def narrate(gm_chat, mem_keeper_prompt) -> str:
    response = gm_chat.send_message(
        f"The players acted:\n{mem_keeper_prompt}\n\nNarrate the result and describe the new situation."
    )
    return response.text