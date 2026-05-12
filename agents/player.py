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

from models.player import Player
from config import client, types, MODEL


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
    response = player.chat.send_message(context)
    return response.text


def propose(player: Player, gm_message: str, validated_facts: str) -> str:
    """Independent first draft from a single player.

    The player sees ONLY the GM message and the validated memory; they do
    not yet know what their party members will propose.
    """
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (your shared memory, read-only):\n"
        f"{validated_facts}\n\n"
        f"Your status: {player.status()}\n\n"
        "Propose ONE concrete action you would take. "
        "Stay strictly consistent with the validated facts; only use items, "
        "weapons or abilities those facts say you have. "
        "Speak in the first person, 1 to 3 short sentences. "
        "Do not list multiple options."
    )
    return player.chat.send_message(context).text.strip()


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
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (read-only):\n"
        f"{validated_facts}\n\n"
        "Your party's individual proposals:\n"
        f"{proposals_block}\n\n"
        "You have been picked to OPEN the party discussion. "
        "Pick the best idea, combine elements, or propose a small twist "
        "that helps the group. Output ONE single proposal in the first "
        "person plural ('we ...') in 1 to 3 short sentences. "
        "Stay strictly consistent with the validated facts."
    )
    return player.chat.send_message(context).text.strip()


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
    context = (
        "The Game Master says:\n"
        f"{gm_message}\n\n"
        "Validated facts about the world (read-only):\n"
        f"{validated_facts}\n\n"
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
    raw = player.chat.send_message(context).text.strip()
    return _parse_review(raw)


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
