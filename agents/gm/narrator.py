"""Narrator sub-agent.

Reads the current memory file (the validated facts only) and produces the
next part of the story. The narrator never reads not-validated entries: only
already-arbitrated facts can influence the narrative.
"""

from config import client, types, MODEL
from agents.gm import memory_store


SYSTEM_PROMPT = (
    "You are the Narrator of a DnD campaign. "
    "You will receive the validated facts about the world (the shared "
    "memory) and you must continue the story by narrating the result of the "
    "players' latest actions and describing the new situation. "
    "Be dramatic but concise (3 to 6 sentences). "
    "Stay strictly consistent with the validated facts: do NOT introduce "
    "items, characters, locations or events that contradict them. "
    "End by leaving the scene open for the players' next action."
)


def setup_narrator():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )


def start_campaign(narrator_chat) -> str:
    """Generate the very first situation of the campaign.

    There is no memory yet, so the narrator only has its system prompt to
    work from.
    """
    response = narrator_chat.send_message(
        "Start the campaign. Describe the setting, the immediate threat or "
        "mystery, and end by asking the players what they do."
    )
    return response.text.strip()


def narrate(narrator_chat, memory_path: str) -> str:
    """Continue the story based on the current validated memory."""
    validated = memory_store.format_validated(memory_path)
    response = narrator_chat.send_message(
        "Here are the validated facts of the world (most recent at the bottom):\n"
        f"{validated}\n\n"
        "Narrate the result of the latest player action(s) and describe the "
        "new situation. Stay consistent with the validated facts."
    )
    return response.text.strip()