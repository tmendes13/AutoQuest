"""Narrator sub-agent.

Reads the current memory file (the validated facts only) and produces the
next part of the story. The narrator never reads not-validated entries: only
already-arbitrated facts can influence the narrative.
"""

from config import client, types, MODEL, send_chat_message
from agents.gm import memory_store


SYSTEM_PROMPT = (
    "You are the Narrator of a DnD campaign. "
    "You will receive the validated facts about the world (the shared "
    "memory) and you must continue the story by narrating the result of the "
    "players' latest actions and describing the new situation. "
    "Be dramatic but concise (3 to 6 sentences). "
    "Stay strictly consistent with the validated facts: do NOT introduce "
    "items, characters, locations or events that contradict them. "
    "End by leaving the scene open for the players' next action.\n\n"
    "COMBAT: If enemies appear and combat starts, ADD this line AFTER your narration:\n"
    "[COMBAT] Monster_Name | HP_amount | weapon_damage\n\n"
    "Examples:\n"
    "[COMBAT] Goblin | 12 | 1d6\n"
    "[COMBAT] Orc Warrior | 28 | 1d8+2\n"
    "[COMBAT] Dragon | 80 | 3d8+1\n\n"
    "If multiple enemies: include one [COMBAT] line per enemy.\n"
    "Use realistic HP for creature type (Goblin 5-15, Orc 15-40, Dragon 50+).\n"
    "Use realistic weapon damage (d6 for small, d10 for medium, d12+ for large).\n\n"
    "EARLY COMBAT: In the FIRST few turns (turns 1-3), introduce combat encounters. "
    "Do NOT delay conflict - make it appear naturally but ENSURE combat happens early. "
    "Include [COMBAT] lines so the party actually fights and rolls dice."
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
        "Start the campaign. Describe the setting and introduce an IMMEDIATE "
        "combat threat or hostile encounter (bandits, monsters, enemies attacking). "
        "The party should face danger RIGHT NOW, not later. "
        "Include [COMBAT] lines with enemy stats. End by asking the players what they do."
    )
    return response.text.strip()


def narrate(narrator_chat, memory_path: str) -> str:
    """Continue the story based on the current validated memory."""
    validated = memory_store.format_validated(memory_path)
    response = send_chat_message(
        narrator_chat,
        "Here are the validated facts of the world (most recent at the bottom):\n"
        f"{validated}\n\n"
        "Narrate the result of the latest player action(s) and describe the "
        "new situation. Stay consistent with the validated facts.\n\n"
        "Remember: if a monster/enemy appears, include [COMBAT] lines with stats.",
        remember=False,
    )
    return response.text.strip()