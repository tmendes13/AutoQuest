"""Session 0 protocol: character creation deliberation before the campaign begins.

Flow:
    1. Narrator pitches the world (theme, tone, standard array instructions).
    2. Players deliberate on character creation (race, class, attributes,
       personality, backstory links) using a variant of party deliberation.
    3. A random spokesperson compiles all decisions into a unified output.
    4. Memory Keeper writes the compiled sheet (not validated).
    5. Arbiter validates: correct N, standard array, thematic consistency.
    6. If rejected, one more deliberation round. If accepted, game starts.
    7. Each player saves their character sheet to their private diary.
"""

import random
import json
import re
from dataclasses import dataclass, field

from config import send_chat_message
from agents.gm import memory_store
from agents.player import APPROVE, MODIFY


STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
ATTRIBUTE_NAMES = ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]
SESSION_ZERO_MAX_ROUNDS = 3
MAX_MODIFICATIONS = 3

PROTECTED_TAG_START = "[SYSTEM_PROTECTED_PLAYER_DATA]"
PROTECTED_TAG_END = "[/SYSTEM_PROTECTED_PLAYER_DATA]"


@dataclass
class SessionZeroLog:
    """Transient record of the Session 0 deliberation."""
    pitch: str = ""
    proposals: dict[str, str] = field(default_factory=dict)
    starter: str = ""
    history: list[str] = field(default_factory=list)
    final_sheet: str = ""
    spokesperson: str = ""
    arbiter_valid: bool = False
    arbiter_reason: str = ""


def _narrator_pitch(narrator_chat, num_players: int) -> str:
    """Ask the Narrator to present the world, theme, tone, and character creation rules."""
    prompt = (
        "You are starting a new D&D campaign. Before the adventure begins, "
        "present the world to the players. Describe the setting (Classic Medieval Fantasy), "
        "the tone (Epic Adventure), and the immediate premise or hook. "
        f"Then instruct the {num_players} players that they must each create ONE character by choosing a Race and a Class, "
        "distributing the Standard Array (15, 14, 13, 12, 10, 8) across Strength, Dexterity, Constitution, "
        "Intelligence, Wisdom, Charisma, defining a short Personality, and suggesting a backstory link "
        f"with the other {num_players - 1} party members. All characters start with 100 HP. "
        f"There will be exactly {num_players} characters in total — no more, no less. "
        "Be dramatic but concise (4 to 7 sentences). End by asking each player to introduce their character concept."
    )
    response = send_chat_message(narrator_chat, prompt, remember=False)
    return response.text.strip()


def _propose_character(player, pitch: str, validated_facts: str, num_players: int) -> str:
    """Ask a single player to propose their character concept."""
    context = (
        "The Narrator presents the world:\n"
        f"{pitch}\n\n"
        "Validated world facts:\n"
        f"{validated_facts}\n\n"
        f"You are ONE of exactly {num_players} players in this campaign. "
        "You are creating your character for this campaign. Propose your character's Name, Race, Class, "
        "distribution of the Standard Array (15, 14, 13, 12, 10, 8) across Strength, Dexterity, Constitution, "
        "Intelligence, Wisdom, Charisma, a short Personality (1 sentence), and a backstory link to the other "
        f"{num_players - 1} party members. Output in a clear structured format. Be creative but stay within classic medieval fantasy. "
        "Speak in first person as your character introducing yourself."
    )
    return send_chat_message(player.chat, context, remember=False).text.strip()


def _synthesize_characters(starter, pitch: str, proposals_block: str, validated_facts: str, num_players: int) -> str:
    """Starter combines all character proposals into a single starting group sheet."""
    context = (
        "The Narrator presents the world:\n"
        f"{pitch}\n\n"
        "Validated world facts:\n"
        f"{validated_facts}\n\n"
        "Your party members have proposed the following characters:\n"
        f"{proposals_block}\n\n"
        "You have been picked to OPEN the party discussion about character creation. "
        f"Combine everyone's ideas into a single unified party composition with EXACTLY {num_players} characters — "
        f"one per player, no more, no less. For each of the {num_players} characters, list "
        "Name, Race, Class, Attributes (the 6 values from the Standard Array), Personality, Backstory link, "
        "and HP: 100. Make sure every character uses ONLY the values from the Standard Array "
        "(15, 14, 13, 12, 10, 8) for their attributes. Output the full party sheet in a clear structured format."
    )
    return send_chat_message(starter.chat, context, remember=False).text.strip()


def _review_characters(player, pitch: str, current_sheet: str, validated_facts: str, num_players: int) -> tuple[str, str]:
    """Review the current party sheet: APPROVE or MODIFY."""
    context = (
        "The Narrator presents the world:\n"
        f"{pitch}\n\n"
        "Validated world facts:\n"
        f"{validated_facts}\n\n"
        "The current unified party character sheet is:\n"
        f"{current_sheet}\n\n"
        f"Review this party composition. There must be EXACTLY {num_players} characters — one per player. "
        "You may APPROVE it as-is, or MODIFY it if you see issues "
        "(e.g., wrong number of characters, a character doesn't use the Standard Array values, "
        "thematic inconsistency, or your own character is misrepresented). Stay collaborative.\n\n"
        "Reply STRICTLY in one of these two formats, nothing else:\n"
        "DECISION: APPROVE\n"
        "or\n"
        "DECISION: MODIFY\n"
        "NEW_PROPOSAL: <the full updated party sheet>"
    )
    raw = send_chat_message(player.chat, context, remember=False).text.strip()
    return _parse_review(raw)


def _parse_review(text: str) -> tuple[str, str]:
    """Extract the verdict + new proposal from the reviewer's reply."""
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
        decision = MODIFY if "MODIFY" in upper else APPROVE
    if decision == APPROVE:
        return APPROVE, ""
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


def _format_proposals(proposals: dict[str, str]) -> str:
    return "\n".join(f"[{name}]: {text}" for name, text in proposals.items())


def _build_queue(party, last_modifier_name: str, remaining: dict[str, int]):
    """Build the next circulation queue for Session 0 deliberation."""
    others = [p for p in party if p.name != last_modifier_name]
    random.shuffle(others)
    others.sort(key=lambda p: -remaining[p.name])
    return others


def _deliberate_characters(party, pitch: str, memory_path: str, log: SessionZeroLog, num_players: int) -> str:
    """Run the Session 0 character creation deliberation among players.

    Returns the final unified party sheet text.
    """
    validated_facts = memory_store.format_validated(memory_path)

    if not party:
        raise ValueError("Cannot deliberate with an empty party.")

    print("\n--- Session 0: character proposals ---")
    for player in party:
        text = _propose_character(player, pitch, validated_facts, num_players)
        log.proposals[player.name] = text
        print(f"  [{player.name}] proposes:\n{text}\n")

    if len(party) == 1:
        only = party[0]
        log.starter = only.name
        log.final_sheet = log.proposals[only.name]
        log.history.append(f"[solo by {only.name}] {log.final_sheet}")
        return log.final_sheet

    starter = random.choice(party)
    log.starter = starter.name
    print(f"\n--- Starter: {starter.name} ---")

    proposals_block = _format_proposals(log.proposals)
    current = _synthesize_characters(starter, pitch, proposals_block, validated_facts, num_players)
    log.history.append(f"[synthesis by {starter.name}] {current}")
    print(f"\n[{starter.name} synthesises]:\n{current}\n")

    remaining = {p.name: MAX_MODIFICATIONS for p in party}
    last_modifier_name = starter.name
    pass_index = 0

    while True:
        pass_index += 1
        queue = _build_queue(party, last_modifier_name, remaining)
        if not queue:
            break

        print(f"\n--- Circulation pass {pass_index} (queue: {[p.name for p in queue]}) ---")
        modified = False

        for reviewer in queue:
            if remaining[reviewer.name] <= 0:
                log.history.append(f"[implicit-approve by {reviewer.name}]")
                continue

            validated_facts = memory_store.format_validated(memory_path)
            verdict, new_proposal = _review_characters(reviewer, pitch, current, validated_facts, num_players)

            if verdict == APPROVE:
                print(f"  [{reviewer.name}] APPROVES")
                log.history.append(f"[approve by {reviewer.name}]")
                continue

            current = new_proposal
            remaining[reviewer.name] -= 1
            last_modifier_name = reviewer.name
            modified = True
            log.history.append(f"[modify by {reviewer.name}] {current}")
            print(f"  [{reviewer.name}] MODIFIES (remaining {remaining[reviewer.name]}/{MAX_MODIFICATIONS})")
            break

        if not modified:
            break

    log.final_sheet = current
    log.history.append(f"[final] {current}")
    print(f"\n--- Session 0 FINAL sheet ---\n{current}\n")
    return current


def _spokesperson_compile(party, pitch: str, final_sheet: str, validated_facts: str, num_players: int) -> tuple[str, str]:
    """Random spokesperson compiles the final unified output for the GM.

    Returns (spokesperson_name, compiled_output).
    """
    spokesperson = random.choice(party)
    context = (
        "The Narrator presents the world:\n"
        f"{pitch}\n\n"
        "Validated world facts:\n"
        f"{validated_facts}\n\n"
        "The party has agreed on the following character sheet:\n"
        f"{final_sheet}\n\n"
        "You are the SPOKESPERSON. Compile this into a final structured output for the Game Master. "
        f"Output EXACTLY {num_players} characters, labeled Player_1 through Player_{num_players}. "
        "For each character, output exactly:\n"
        "Player_N: {Name: ..., Race: ..., Class: ..., Attributes: [Str:X, Dex:X, Con:X, Int:X, Wis:X, Cha:X], "
        "HP: 100, Personality: ...}\n\n"
        f"Make sure the output contains EXACTLY {num_players} characters — no more, no less. "
        "Verify that every character uses ONLY the Standard Array values (15, 14, 13, 12, 10, 8). "
        "Output ONLY the compiled sheet, no extra commentary."
    )
    response = send_chat_message(spokesperson.chat, context, remember=False)
    return spokesperson.name, response.text.strip()


def _arbiter_validate_session_zero(arbiter_chat, memory_path: str, entry_id: str, num_players: int) -> tuple[bool, str]:
    """Arbiter validates the Session 0 character sheet.

    Checks:
    - Number of characters matches N
    - All use Standard Array values
    - Thematic consistency
    """
    candidate = memory_store.get_entry(memory_path, entry_id)
    if candidate is None:
        return False, "Entry not found in memory."

    validated_text = memory_store.format_validated(memory_path)
    prompt = (
        "VALIDATED FACTS ABOUT THE WORLD:\n"
        f"{validated_text}\n\n"
        "CANDIDATE SESSION 0 CHARACTER SHEET TO VALIDATE:\n"
        f"[{candidate['author']}] {candidate['content']}\n\n"
        f"Validate this Session 0 character creation output. There should be exactly {num_players} characters. "
        "Every character MUST use ONLY the values from the Standard Array (15, 14, 13, 12, 10, 8) "
        "for their six attributes (Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma). "
        "All characters must be thematically consistent with Classic Medieval Fantasy. "
        "All characters must have 100 HP.\n\n"
        "Reply STRICTLY in this format, on exactly two lines:\n"
        "DECISION: VALID\n"
        "REASON: <one short sentence>\n"
        "or\n"
        "DECISION: INVALID\n"
        "REASON: <one short sentence>"
    )
    response = send_chat_message(arbiter_chat, prompt, remember=False)
    is_valid = _parse_arbiter_decision(response.text)
    if is_valid:
        memory_store.mark_validated(memory_path, entry_id)
    else:
        memory_store.delete_entry(memory_path, entry_id)
    return is_valid, response.text


def _parse_arbiter_decision(text: str) -> bool:
    """Parse the arbiter's VALID/INVALID decision."""
    upper = text.upper()
    for line in upper.splitlines():
        line = line.strip()
        if line.startswith("DECISION:"):
            value = line.split(":", 1)[1].strip()
            if value.startswith("INVALID"):
                return False
            if value.startswith("VALID"):
                return True
    if "INVALID" in upper:
        return False
    return True


def _write_protected_player_data(memory_path: str, compiled_sheet: str) -> None:
    """Write the protected player data block at the top of the memory file."""
    data = memory_store._read(memory_path)
    data["protected_player_data"] = compiled_sheet
    memory_store._write(memory_path, data)
    print(f"[Memory] Protected player data written to {memory_path}")


def _parse_player_attributes_from_sheet(sheet: str, player_name: str) -> dict[str, int]:
    """Try to extract a specific player's attributes from the compiled sheet.

    Uses multiple regex patterns for robustness against different LLM formatting.
    """
    patterns = [
        rf'{re.escape(player_name)}.*?Attributes:\s*\[Str:(\d+),\s*Dex:(\d+),\s*Con:(\d+),\s*Int:(\d+),\s*Wis:(\d+),\s*Cha:(\d+)\]',
        rf'{re.escape(player_name)}.*?Attributes:\s*\[Strength:(\d+),\s*Dexterity:(\d+),\s*Constitution:(\d+),\s*Intelligence:(\d+),\s*Wisdom:(\d+),\s*Charisma:(\d+)\]',
        rf'{re.escape(player_name)}.*?Str[^:]*[:\s]*(\d+).*?Dex[^:]*[:\s]*(\d+).*?Con[^:]*[:\s]*(\d+).*?Int[^:]*[:\s]*(\d+).*?Wis[^:]*[:\s]*(\d+).*?Cha[^:]*[:\s]*(\d+)',
    ]
    for pat in patterns:
        match = re.search(pat, sheet, re.IGNORECASE | re.DOTALL)
        if match:
            return {
                "Strength": int(match.group(1)),
                "Dexterity": int(match.group(2)),
                "Constitution": int(match.group(3)),
                "Intelligence": int(match.group(4)),
                "Wisdom": int(match.group(5)),
                "Charisma": int(match.group(6)),
            }
    return {}


def _parse_player_info_from_sheet(sheet: str, player_name: str) -> dict:
    """Extract a player's race, class, personality from the compiled sheet."""
    info = {}
    patterns = {
        "race": rf'{re.escape(player_name)}.*?Race:\s*([^,\n}}]+)',
        "class": rf'{re.escape(player_name)}.*?Class:\s*([^,\n}}]+)',
        "personality": rf'{re.escape(player_name)}.*?Personality:\s*([^\n}}]+)',
    }
    for key, pat in patterns.items():
        match = re.search(pat, sheet, re.IGNORECASE | re.DOTALL)
        if match:
            info[key] = match.group(1).strip().rstrip('}')
    return info


def _count_players_in_sheet(sheet: str) -> int:
    """Count how many Player_N entries exist in the compiled sheet."""
    return len(re.findall(r'Player_\d+\s*:', sheet))


def _validate_sheet_programmatically(sheet: str, num_players: int) -> tuple[bool, str]:
    """Programmatic pre-validation before sending to the Arbiter.

    Returns (is_valid, reason).
    """
    count = _count_players_in_sheet(sheet)
    if count != num_players:
        return False, f"Sheet contains {count} characters but {num_players} were requested."

    all_values = re.findall(r'\b(15|14|13|12|10|8)\b', sheet)
    if len(all_values) < num_players * 6:
        return False, "Not all characters have 6 attributes from the Standard Array."

    hp_matches = re.findall(r'HP:\s*(\d+)', sheet, re.IGNORECASE)
    if len(hp_matches) < num_players:
        return False, "Not all characters have HP listed."
    for hp in hp_matches[:num_players]:
        if int(hp) != 100:
            return False, f"A character has {hp} HP instead of 100."

    return True, ""


def _update_player_from_sheet(player, compiled_sheet: str) -> None:
    """Update a player's attributes, race, class, personality from the compiled sheet."""
    info = _parse_player_info_from_sheet(compiled_sheet, player.name)
    attrs = _parse_player_attributes_from_sheet(compiled_sheet, player.name)

    if attrs:
        player.attributes = attrs
    if "race" in info:
        player.race = info["race"]
    if "class" in info:
        from models.dnd_class import Class
        player.dnd_class = Class(info["class"], 10)
    if "personality" in info:
        player.personality = info["personality"]
    player.max_hp = 100
    player.current_hp = 100


def run_session_zero(party, gm, num_players: int, on_event=None) -> SessionZeroLog:
    """Run the full Session 0 protocol.

    If on_event is provided, it is called as on_event(event_type, data)
    for UI integration (e.g. WebSocket emissions).

    Returns a SessionZeroLog with the results. After this returns successfully,
    the game can begin normally.
    """
    log = SessionZeroLog()

    print("\n========== SESSION 0: CHARACTER CREATION ==========")
    if on_event:
        on_event('system', {'message': 'Session 0: Character Creation starting...'})

    # Step 1: Narrator pitches the world
    print("\n[GM-Narrator] Pitching the world...")
    if on_event:
        on_event('phase', {'phase': 'session_zero', 'message': 'Narrator is pitching the world...'})
    pitch = _narrator_pitch(gm.narrator_chat, num_players)
    log.pitch = pitch
    print(f"\n[GM-Narrator Session 0 pitch]\n{pitch}\n")
    if on_event:
        on_event('gm_agent', {'agent': 'Session 0 Pitch', 'message': pitch})

    # Write pitch to memory as validated seed
    pitch_entry_id = memory_store.append_entry(
        gm.memory_path, author="narrator", content=pitch, validated=True
    )

    for attempt in range(1, SESSION_ZERO_MAX_ROUNDS + 1):
        print(f"\n>>> Session 0 deliberation (attempt {attempt}/{SESSION_ZERO_MAX_ROUNDS}) <<<")
        if on_event:
            on_event('system', {'message': f'Session 0 deliberation (attempt {attempt}/{SESSION_ZERO_MAX_ROUNDS})...'})

        # Step 2: Players deliberate on character creation
        final_sheet = _deliberate_characters(party, pitch, gm.memory_path, log, num_players)
        if on_event:
            on_event('gm_agent', {'agent': 'Session 0 Deliberation', 'message': final_sheet})

        # Step 3: Spokesperson compiles
        print("\n[Spokesperson] Compiling final output...")
        if on_event:
            on_event('phase', {'phase': 'session_zero', 'message': 'Spokesperson is compiling the final sheet...'})
        sp_name, compiled = _spokesperson_compile(party, pitch, final_sheet, memory_store.format_validated(gm.memory_path), num_players)
        log.spokesperson = sp_name
        log.final_sheet = compiled
        print(f"\n[Spokesperson {sp_name}]\n{compiled}\n")
        if on_event:
            on_event('gm_agent', {'agent': f'Spokesperson ({sp_name})', 'message': compiled})

        # Step 4: Programmatic pre-validation
        prog_valid, prog_reason = _validate_sheet_programmatically(compiled, num_players)
        if not prog_valid:
            print(f"[Pre-validation] FAILED: {prog_reason}")
            log.arbiter_valid = False
            log.arbiter_reason = f"PRE-VALIDATION: {prog_reason}"
            continue

        # Step 5: Write directly to memory (not validated) — do NOT use mem_keep()
        # because the Memory Keeper would summarise and lose critical attributes.
        entry_id = memory_store.append_entry(
            gm.memory_path, author="session_zero", content=compiled, validated=False
        )

        # Step 6: Arbiter validates
        print("\n[Arbiter] Validating Session 0 character sheet...")
        if on_event:
            on_event('phase', {'phase': 'session_zero', 'message': 'Arbiter is validating the character sheet...'})
        is_valid, arbiter_text = _arbiter_validate_session_zero(
            gm.arbiter_chat, gm.memory_path, entry_id, num_players
        )
        log.arbiter_valid = is_valid
        log.arbiter_reason = arbiter_text
        print(f"[Arbiter] {'VALID' if is_valid else 'INVALID'}: {arbiter_text.strip()}")
        if on_event:
            on_event('gm_agent', {'agent': 'Arbiter Decision', 'message': arbiter_text})

        if is_valid:
            # Step 6: Write protected player data block
            _write_protected_player_data(gm.memory_path, compiled)

            # Step 7: Update each player from the compiled sheet
            for player in party:
                _update_player_from_sheet(player, compiled)

            # Step 8: Save character sheet to each player's private diary
            from agents.player import save_character_sheet_to_diary
            for player in party:
                save_character_sheet_to_diary(gm.memory_path, player)

            if on_event:
                on_event('system', {'message': f'Session 0 complete. Arbiter: VALID'})
            print("\n========== SESSION 0 COMPLETE ==========")
            return log
        else:
            print(f"[Session 0] Character sheet rejected. Reason: {arbiter_text.strip()}")
            if on_event:
                on_event('system', {'message': f'Session 0 rejected by Arbiter: {arbiter_text.strip()}'})
            memory_store.delete_unvalidated(gm.memory_path)

    print("\n[Session 0] Max deliberation rounds reached. Aborting — could not produce a valid sheet.")
    raise RuntimeError(
        f"Session 0 failed after {SESSION_ZERO_MAX_ROUNDS} attempts. "
        f"Last reason: {log.arbiter_reason}"
    )
