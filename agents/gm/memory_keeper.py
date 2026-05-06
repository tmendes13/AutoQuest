from config import client, types, MODEL

def setup_mem_keeper():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are the memory keeper of the Game Master of a DnD campaign. "
                "Your role is to track all the events and keep them in memory"
            )
        )
    )

def mem_keep(gm_chat, player_actions: list[str]) -> str:
    actions = "\n".join(player_actions)
    response = gm_chat.send_message(
        f"The players acted:\n{actions}\n\nKeep the record of the events"
    )
    return response.text