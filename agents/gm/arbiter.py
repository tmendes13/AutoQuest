"""Rule Arbiter sub-agent.

Reads the shared memory file and validates a single not-validated entry
against the already-validated facts. The check focuses on hallucinations
only, not on whether the action is balanced or interesting:

    - Does the actor possess any item / weapon they claim to use?
    - Are they in the same environment that has already been established?
    - Is the enemy they target actually present in the current scene?
    - Do they reference characters, places or objects that exist?

If the entry passes, its label is flipped to validated.
If it fails, the entry is removed from the memory file.
"""

from config import client, types, MODEL
from agents.gm import memory_store


SYSTEM_PROMPT = (
    "You are the Arbiter of a DnD Game Master. Your only job is to detect "
    "hallucinations between a candidate memory entry and the already-"
    "validated facts about the world. You DO NOT judge whether an action is "
    "smart, fair, balanced or dramatic. You ONLY verify factual consistency:\n"
    "  - Does the actor actually possess the items or weapons they claim to use?\n"
    "  - Are they in the same environment that has been established?\n"
    "  - Is the enemy they target actually present in the current scene?\n"
    "  - Do they reference characters, places or objects that exist?\n"
    "If the candidate introduces a NEW fact that does NOT contradict the "
    "validated facts (for example: walking into a new room, drawing a weapon "
    "they already own, describing previously-unmentioned scenery), treat it "
    "as VALID; the world is allowed to grow. Only flag INVALID when there is "
    "a direct contradiction with the validated facts or the actor relies on "
    "something that does not exist according to those facts.\n"
    "\n"
    "Reply STRICTLY in this format, on exactly two lines:\n"
    "DECISION: VALID\n"
    "REASON: <one short sentence>\n"
    "or\n"
    "DECISION: INVALID\n"
    "REASON: <one short sentence>"
)


def setup_arbiter():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )


def _parse_decision(text: str) -> bool:
    """Parse the arbiter's reply.

    Returns True for VALID, False for INVALID. If the reply is malformed we
    default to VALID so that a single bad LLM response does not block the
    game; the worst case is a borderline entry being kept.
    """
    upper = text.upper()
    for line in upper.splitlines():
        line = line.strip()
        if line.startswith("DECISION:"):
            value = line.split(":", 1)[1].strip()
            if value.startswith("INVALID"):
                return False
            if value.startswith("VALID"):
                return True
    # Fallback heuristic when the model did not follow the format.
    if "INVALID" in upper:
        return False
    return True


def arbitrate(arbiter_chat, memory_path: str, entry_id: str) -> tuple[bool, str]:
    """Validate the entry with the given id against the validated entries.

    Side-effects on the memory file:
        VALID    -> the entry's label is flipped to validated.
        INVALID  -> the entry is removed from the file.

    Parameters
    ----------
    arbiter_chat:   The Arbiter LLM chat.
    memory_path:    Path to the shared memory JSON file.
    entry_id:       Id of the not-validated entry to check.

    Returns
    -------
    (is_valid, raw_arbiter_text) - the boolean decision plus the raw text
    returned by the LLM (useful for logging).
    """
    candidate = memory_store.get_entry(memory_path, entry_id)
    if candidate is None:
        return False, "Entry not found in memory."
    if candidate["validated"]:
        # Already validated by a previous pass - nothing to do.
        return True, "Entry already validated."

    validated_text = memory_store.format_validated(memory_path)
    prompt = (
        "VALIDATED FACTS ABOUT THE WORLD (most recent at the bottom):\n"
        f"{validated_text}\n\n"
        "CANDIDATE ENTRY TO CHECK:\n"
        f"[{candidate['author']}] {candidate['content']}\n\n"
        "Decide if the candidate is consistent with the validated facts."
    )
    response = arbiter_chat.send_message(prompt)
    is_valid = _parse_decision(response.text)
    if is_valid:
        memory_store.mark_validated(memory_path, entry_id)
    else:
        memory_store.delete_entry(memory_path, entry_id)
    return is_valid, response.text