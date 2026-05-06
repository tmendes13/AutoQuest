from config import client, types, MODEL

def setup_arbiter():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are the arbiter instance of a DnD Game Master, "
                "Analyse the events that the memory_keeper sent to you and"
                " say if they make sense or not, "
            )
        )
    )

def decide(gm_chat, mem_keeper_prompt) -> str:
    response = gm_chat.send_message(
        f"{mem_keeper_prompt}"
    )
    return response.text