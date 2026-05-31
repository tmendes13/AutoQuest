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


def propose(player: Player, gm_message: str, validated_facts: str) -> str:
    """Independent first draft from a single player.

    The player sees ONLY the GM message and the validated memory; they do
    not yet know what their party members will propose.
    """
    diary_str = f"Your private diary and secret thoughts:\n{player.diary}\n\n" if getattr(player, "diary", None) else ""
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (your shared memory, read-only):\n"
        f"{validated_facts}\n\n"
        f"{diary_str}"
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
    diary_str = f"Your private diary and secret thoughts:\n{player.diary}\n\n" if getattr(player, "diary", None) else ""
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (read-only):\n"
        f"{validated_facts}\n\n"
        "Your party's individual proposals:\n"
        f"{proposals_block}\n\n"
        f"{diary_str}"
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
    diary_str = f"Your private diary and secret thoughts:\n{player.diary}\n\n" if getattr(player, "diary", None) else ""
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (read-only):\n"
        f"{validated_facts}\n\n"
        f"{diary_str}"
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
    """Update the player's private thoughts based on the latest event.

    This keeps their personal diary constant in size by rewriting/consolidating it.
    The character sheet is preserved separately and never overwritten.
    """
    current_thoughts = player.diary if getattr(player, "diary", None) else "Nenhum pensamento anterior."
    sheet = getattr(player, "character_sheet", "") or ""
    sheet_block = f"Your character sheet:\n{sheet}\n\n" if sheet else ""
    context = (
        "You are playing as the character described in your system prompt. "
        "Update your private diary (personal thoughts) based on the latest event.\n\n"
        f"{sheet_block}"
        "Your previous thoughts:\n"
        f"{current_thoughts}\n\n"
        "Latest event in the world:\n"
        f"{latest_situation}\n\n"
        "Validated world facts:\n"
        f"{validated_facts}\n\n"
        "Rewrite your private thoughts. Consolidate them into exactly 1 to 3 very short, "
        "terse bullet points (in first person, keeping the same language as the context). "
        "Focus on your immediate worries, plans, or how you feel about your companion(s) "
        "according to your personality. "
        "Keep it extremely concise. Output bullet points only, no commentary, markdown or headers."
    )
    response = send_chat_message(player.chat, context, remember=False)
    player.diary = response.text.strip()
    print(f"  [{player.name}'s Secret Thoughts]:\n  {player.diary}")


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
    """Save the current private diaries of all party members to their individual disk files."""
    for p in party:
        diary_path = get_player_diary_path(memory_path, p.name)
        data = {"diary": p.diary, "character_sheet": p.character_sheet}
        with open(diary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_diaries(memory_path: str, party: list[Player]) -> None:
    """Load the private diaries of all party members from their individual disk files."""
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
    data = {"diary": player.diary, "character_sheet": sheet}
    with open(diary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
