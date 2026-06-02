"""Player agent primitives.

Each player owns an LLM chat (created via ``setup_agent``) and can be asked
to perform one of the four tasks below. Players READ the validated memory
that the Game Master maintains, but they never write to it; only the Memory
Keeper writes.

    - act:         legacy single-shot "what do you do?" call (kept for any
                   callers that don't run a deliberation; not used by the
                   default flow).
    - propose:     independent first draft of an action for the GM message.
    - synthesize:  the random starter combines everyone's proposals into a
                   single starting group proposal.
    - review:      circulation step. The reviewer either APPROVES the
                   current proposal or MODIFIES it (consuming one of their
                   modification slots in :mod:`agents.party`).
"""

import os
import json
from models.player import Player
from config import client, types, MODEL, send_chat_message


# Public verdict constants returned by :func:`review`.
APPROVE = "APPROVE"
MODIFY = "MODIFY"

# Global flag to disable diaries
USE_DIARIES = True

# Fixed trait keys — always present, values evolve. Constant size per player.
TRAIT_KEYS = [
    "mood",
    "trust_in_party",
    "primary_goal",
    "risk_tolerance",
    "recent_concern",
]

DEFAULT_TRAITS = {
    "mood": "neutral",
    "trust_in_party": "neutral",
    "primary_goal": "unknown",
    "risk_tolerance": "moderate",
    "recent_concern": "none",
}


def setup_agent(system_prompt: str):
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt
        )
    )


def act(player: Player, situation: str) -> str:
    """Legacy single-shot action. Kept for callers that don't deliberate."""
    context = f"Your status: {player.status()}\n\n Situation: {situation}\n\nWhat do you do?"
    response = send_chat_message(player.chat, context, remember=False)
    return response.text


def _format_diary_block(player: Player) -> str:
    """Build the private-diary + traits block injected into deliberation prompts."""
    parts = []
    if USE_DIARIES and getattr(player, "diary", None):
        parts.append(f"Your private thoughts:\n{player.diary}")
    traits = getattr(player, "traits", None)
    if traits:
        trait_lines = "\n".join(f"  - {k}: {v}" for k, v in traits.items())
        parts.append(f"Your character traits:\n{trait_lines}")
    return "\n\n".join(parts) + "\n\n" if parts else ""


def propose(player: Player, gm_message: str, validated_facts: str) -> str:
    """Independent first draft from a single player.

    The player sees ONLY the GM message and the validated memory; they do
    not yet know what their party members will propose.
    """
    diary_block = _format_diary_block(player)
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (your shared memory, read-only):\n"
        f"{validated_facts}\n\n"
        f"{diary_block}"
        f"Your status: {player.status()}\n\n"
        "Propose ONE concrete action you would take. "
        "Stay strictly consistent with the validated facts; only use items, "
        "weapons or abilities those facts say you have. "
        "Speak in the first person, 1 to 3 short sentences. "
        "Do not list multiple options."
    )
    return send_chat_message(player.chat, context, remember=False).text.strip()


def synthesize(
    player: Player,
    gm_message: str,
    proposals_block: str,
    validated_facts: str,
) -> str:
    """Starter combines all proposals into a single starting group proposal.

    Called once per deliberation round, on the player picked at random to
    open the discussion. The starter is allowed (and encouraged) to pick
    one player's idea, mix elements, or propose a small twist.
    """
    diary_block = _format_diary_block(player)
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (read-only):\n"
        f"{validated_facts}\n\n"
        "Your party's individual proposals:\n"
        f"{proposals_block}\n\n"
        f"{diary_block}"
        "You have been picked to OPEN the party discussion. "
        "Pick the best idea, combine elements, or propose a small twist "
        "that helps the group. Output ONE single proposal in the first "
        "person plural ('we ...') in 1 to 3 short sentences. "
        "Stay strictly consistent with the validated facts."
    )
    return send_chat_message(player.chat, context, remember=False).text.strip()


def review(
    player: Player,
    gm_message: str,
    current_proposal: str,
    validated_facts: str,
) -> tuple[str, str]:
    """Approve the current proposal or modify it.

    Returns ``(verdict, new_proposal)`` where ``verdict`` is either
    :data:`APPROVE` or :data:`MODIFY`. When the verdict is APPROVE, the
    second element is the empty string.
    """
    diary_block = _format_diary_block(player)
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (read-only):\n"
        f"{validated_facts}\n\n"
        f"{diary_block}"
        f"Your status: {player.status()}\n\n"
        "The current group proposal is:\n"
        f"{current_proposal}\n\n"
        "You may APPROVE the proposal as-is, or MODIFY it (a small "
        "adjustment, or a partial change of strategy if you clearly see a "
        "better collective action). Stay collaborative; do not create "
        "artificial conflict just to disagree.\n\n"
        "Reply STRICTLY in one of these two formats, nothing else:\n"
        "DECISION: APPROVE\n"
        "or\n"
        "DECISION: MODIFY\n"
        "NEW_PROPOSAL: <the full updated proposal, 1 to 3 short sentences, "
        "first person plural>"
    )
    raw = send_chat_message(player.chat, context, remember=False).text.strip()
    return _parse_review(raw)


def reflect(player: Player, latest_situation: str, validated_facts: str) -> None:
    """Update the player's private thoughts AND character traits.

    Thoughts are rewritten each round (constant size). Traits are a fixed
    set of keys whose values evolve — the dict never grows, guaranteeing
    O(1) token cost regardless of how many rounds have passed.
    The character sheet is preserved separately and never overwritten.
    """
    current_thoughts = player.diary if getattr(player, "diary", None) else "Nenhum pensamento anterior."
    current_traits = getattr(player, "traits", None) or DEFAULT_TRAITS.copy()
    traits_block = "\n".join(f"  {k}: {v}" for k, v in current_traits.items())
    sheet = getattr(player, "character_sheet", "") or ""
    sheet_block = f"Your character sheet:\n{sheet}\n\n" if sheet else ""

    context = (
        f"You are {player.name}, a {player.race} {player.dnd_class.name}. "
        f"Personality: {player.personality}.\n\n"
        f"{sheet_block}"
        "Your previous private thoughts:\n"
        f"{current_thoughts}\n\n"
        "Your current character traits:\n"
        f"{traits_block}\n\n"
        "Latest event in the world:\n"
        f"{latest_situation}\n\n"
        "Validated world facts:\n"
        f"{validated_facts}\n\n"
        "Update BOTH your private thoughts AND your character traits. "
        "Reply STRICTLY in this format:\n\n"
        "THOUGHTS:\n"
        "- <1 to 3 very short bullet points in first person, filtered through "
        "YOUR specific personality. If you are impulsive, show frustration or "
        "eagerness. If you are calculative, show analysis or caution.>\n\n"
        "TRAITS:\n"
        "mood: <your current emotional state — e.g. determined, frustrated, curious, anxious>\n"
        "trust_in_party: <high / growing / neutral / wavering / low>\n"
        "primary_goal: <what you personally want most right now>\n"
        "risk_tolerance: <high / moderate / low>\n"
        "recent_concern: <the one thing worrying you most right now>\n\n"
        "Make the thoughts and traits reflect YOUR personality. "
        "Two different characters with different personalities should produce "
        "different outputs for the same event."
    )
    response = send_chat_message(player.chat, context, remember=False)
    raw = response.text.strip()
    thoughts, traits = _parse_reflection(raw, player)
    player.diary = thoughts
    player.traits = traits
    print(f"  [{player.name}'s Secret Thoughts]:\n  {player.diary}")
    print(f"  [{player.name}'s Traits]: {player.traits}")


def _parse_reflection(raw: str, player: Player) -> tuple[str, dict]:
    """Parse the LLM reflection output into (thoughts, traits).

    Defensive: if parsing fails, keep previous values so nothing is lost.
    """
    thoughts = player.diary
    traits = getattr(player, "traits", None) or DEFAULT_TRAITS.copy()

    raw_upper = raw.upper()
    thoughts_start = raw_upper.find("THOUGHTS:")
    traits_start = raw_upper.find("TRAITS:")

    if thoughts_start != -1:
        end = traits_start if traits_start != -1 else len(raw)
        chunk = raw[thoughts_start + len("THOUGHTS:"):end].strip()
        if chunk:
            thoughts = chunk

    if traits_start != -1:
        chunk = raw[traits_start + len("TRAITS:"):].strip()
        new_traits = {}
        for line in chunk.splitlines():
            line = line.strip().lstrip("- ").strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key in TRAIT_KEYS and value:
                    new_traits[key] = value
        # Only overwrite keys that were successfully parsed
        for k, v in new_traits.items():
            traits[k] = v

    return thoughts, traits


def _parse_review(text: str) -> tuple[str, str]:
    """Extract the verdict + new proposal from the reviewer's reply.

    Defensive defaults:
        - Malformed reply with no clear DECISION line falls back to APPROVE
          (safer to keep the current proposal than to drop or invent one).
        - MODIFY without a usable NEW_PROPOSAL also falls back to APPROVE
          to avoid silently wiping the group's proposal.
    """
    upper = text.upper()
    decision = None
    for line in upper.splitlines():
        stripped = line.strip()
        if stripped.startswith("DECISION:"):
            value = stripped.split(":", 1)[1].strip()
            if value.startswith("APPROVE"):
                decision = APPROVE
            elif value.startswith("MODIFY"):
                decision = MODIFY
            break

    if decision is None:
        # No explicit DECISION line - last-ditch heuristic.
        decision = MODIFY if "MODIFY" in upper else APPROVE

    if decision == APPROVE:
        return APPROVE, ""

    # MODIFY: capture everything that comes after the NEW_PROPOSAL: marker,
    # preserving the original casing of the proposal text.
    captured: list[str] = []
    capturing = False
    for line in text.splitlines():
        if not capturing and line.strip().upper().startswith("NEW_PROPOSAL:"):
            after = line.split(":", 1)[1].strip() if ":" in line else ""
            if after:
                captured.append(after)
            capturing = True
            continue
        if capturing:
            captured.append(line)
    proposal = "\n".join(captured).strip()

    if not proposal:
        return APPROVE, ""
    return MODIFY, proposal


def get_player_diary_path(memory_path: str, player_name: str) -> str:
    """Derive a player's individual diary path from the campaign memory path and player's name."""
    base, ext = os.path.splitext(memory_path)
    # Sanitize the player name to avoid file system issues
    safe_name = "".join(c for c in player_name if c.isalnum() or c in ("-", "_"))
    return f"{base}_diary_{safe_name}.json"


def init_diaries(memory_path: str) -> None:
    """Reset the player diaries by deleting all individual diary files on disk."""
    import glob
    base, ext = os.path.splitext(memory_path)
    # Delete all individual diary files that match the pattern
    pattern = f"{base}_diary_*.json"
    for path in glob.glob(pattern):
        try:
            os.remove(path)
        except OSError:
            pass


def save_diaries(memory_path: str, party: list[Player]) -> None:
    """Save the current private diaries and traits of all party members to disk."""
    for p in party:
        diary_path = get_player_diary_path(memory_path, p.name)
        data = {"diary": p.diary, "character_sheet": getattr(p, "character_sheet", ""), "traits": getattr(p, "traits", None) or {}}
        with open(diary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_diaries(memory_path: str, party: list[Player]) -> None:
    """Load the private diaries and traits of all party members from disk."""
    for p in party:
        diary_path = get_player_diary_path(memory_path, p.name)
        if not os.path.exists(diary_path):
            continue
        try:
            with open(diary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "diary" in data:
                p.diary = data["diary"]
            if "character_sheet" in data:
                p.character_sheet = data["character_sheet"]
            if "traits" in data and data["traits"]:
                p.traits = data["traits"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass


def save_character_sheet_to_diary(memory_path: str, player: Player) -> None:
    """Save the player's character sheet as their permanent private diary entry.

    Called after Session 0 approval to persist race, class, attributes,
    personality, and HP as the character's immutable reference.
    """
    attrs_str = ", ".join(f"{k}:{v}" for k, v in player.attributes.items()) if player.attributes else "None"
    sheet = (
        f"CHARACTER SHEET\n"
        f"Name: {player.name}\n"
        f"Race: {player.race}\n"
        f"Class: {player.dnd_class.name}\n"
        f"Attributes: {attrs_str}\n"
        f"HP: {player.current_hp}/{player.max_hp}\n"
        f"Personality: {player.personality}\n"
    )
    player.character_sheet = sheet
    diary_path = get_player_diary_path(memory_path, player.name)
    data = {"diary": player.diary, "character_sheet": sheet, "traits": getattr(player, "traits", None) or {}}
    with open(diary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
