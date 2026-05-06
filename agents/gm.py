from config import client, types, MODEL

def setup_gm():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are the Game Master of a DnD campaign. "
                "Narrate the story dramatically, describe the environment, "
                "enemies and consequences of the players' actions. "
                "Keep responses concise and engaging."
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

def narrate(gm_chat, player_actions: list[str]) -> str:
    actions = "\n".join(player_actions)
    response = gm_chat.send_message(
        f"The players acted:\n{actions}\n\nNarrate the result and describe the new situation."
    )
    return response.text