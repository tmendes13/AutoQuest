"""Game Master orchestrator.

Coordinates the three sub-agents (Narrator, Memory Keeper, Arbiter) over a
shared memory file. The whole flow is strictly synchronous: every step waits
for the previous one to finish, so there are no race conditions on the file.

Per-turn flow (after the campaign opening has already been emitted):

    1.  The party runs an internal deliberation (see :mod:`agents.party`)
        and produces ONE official response to the GM.
    2.  Memory Keeper summarises the party response and appends a
        NOT-validated entry tagged ``"party"``.
    3.  Arbiter validates that entry.
            VALID    -> label flipped to validated.
            INVALID  -> entry deleted; every remaining not-validated entry
                        is wiped and the party deliberates again
                        (up to ``MAX_RETRIES``).
    4.  Narrator reads the (now-updated) validated memory and produces the
        next part of the story.
    5.  Memory Keeper summarises the narrator's text and appends a
        NOT-validated entry tagged ``"narrator"``.
    6.  Arbiter validates that entry.
            VALID    -> label flipped to validated.
            INVALID  -> entry deleted; every remaining not-validated entry
                        is wiped and the narrator is asked again
                        (up to ``MAX_RETRIES``).
    7.  The narrator's text - now in the memory file as a validated entry -
        is returned and forwarded to the party as the next situation.
"""

from dataclasses import dataclass

from agents.gm import memory_store
from agents.gm.arbiter import setup_arbiter, arbitrate
from agents.gm.memory_keeper import setup_mem_keeper, mem_keep
from agents.gm.narrator import setup_narrator, start_campaign, narrate
from agents.party import deliberate
from models.player import Player


MAX_RETRIES = 3
DEFAULT_MEMORY_PATH = "memory.json"


class GMRetriesExhaustedError(RuntimeError):
    """Raised when an agent (player or narrator) has hallucinated more than
    ``MAX_RETRIES`` times in a row and the campaign cannot continue.

    Attributes
    ----------
    actor:        "player:<name>" or "narrator".
    last_text:    the last raw text produced by the agent before giving up.
    last_reason:  the arbiter's reason for the final rejection.
    """

    def __init__(self, actor: str, last_text: str, last_reason: str):
        super().__init__(
            f"{actor} exhausted {MAX_RETRIES} retries due to hallucinations."
        )
        self.actor = actor
        self.last_text = last_text
        self.last_reason = last_reason


# Label used in the memory file for entries that summarise the party's
# joint response (produced by :func:`agents.party.deliberate`).
PARTY_AUTHOR = "party"


@dataclass
class GameMaster:
    """Bundle of the three sub-agent chats plus the memory-file path."""

    narrator_chat: object
    mk_chat: object
    arbiter_chat: object
    memory_path: str


def setup_gm(memory_path: str = DEFAULT_MEMORY_PATH) -> GameMaster:
    """Create the three sub-agent chats and reset the shared memory file."""
    memory_store.init_memory(memory_path)
    return GameMaster(
        narrator_chat=setup_narrator(),
        mk_chat=setup_mem_keeper(),
        arbiter_chat=setup_arbiter(),
        memory_path=memory_path,
    )


def begin_campaign(gm: GameMaster) -> str:
    """Generate the opening narration and seed the memory file with it.

    The opening is taken as ground truth (validated) since there is nothing
    to compare it against. Future arbitration will compare new entries to
    these seed facts.
    """
    opening = start_campaign(gm.narrator_chat)
    entry_id = mem_keep(
        gm.mk_chat, gm.memory_path, author="narrator", raw_text=opening
    )
    memory_store.mark_validated(gm.memory_path, entry_id)
    return opening


def _ingest_with_arbitration(
    gm: GameMaster,
    author: str,
    raw_text: str,
) -> tuple[bool, str]:
    """Summarise + arbitrate one piece of text in a single synchronous step.

    Always returns ``(is_valid, raw_arbiter_text)``. If the arbiter rejects
    the entry, every remaining not-validated entry is also wiped to make
    sure no stale candidates leak into the next attempt.
    """
    entry_id = mem_keep(
        gm.mk_chat, gm.memory_path, author=author, raw_text=raw_text
    )
    is_valid, arbiter_text = arbitrate(
        gm.arbiter_chat, gm.memory_path, entry_id
    )
    if not is_valid:
        # Defensive: arbitrate already deleted the candidate, but make sure
        # no other not-validated entries are left lying around.
        memory_store.delete_unvalidated(gm.memory_path)
    return is_valid, arbiter_text


def run_turn(gm: GameMaster, party: list[Player], situation: str) -> str:
    """Run one full GM turn for a party of one or more players.

    The party runs an internal deliberation (see :mod:`agents.party`) and
    produces a single joint response, which is then submitted to the
    Memory Keeper + Arbiter pipeline as usual.

    Returns the narrator's new situation text - already in the memory file
    and validated - which the caller should pass back as the ``situation``
    argument of the next turn.
    """
    # ---- 1. Party deliberates (with retries on invalidation) ------------
    party_response = ""
    arbiter_text = ""
    for attempt in range(1, MAX_RETRIES + 1):
        print(
            f"\n>>> Party deliberation (attempt {attempt}/{MAX_RETRIES}) <<<"
        )
        party_response, _log = deliberate(party, situation, gm.memory_path)

        is_valid, arbiter_text = _ingest_with_arbitration(
            gm, author=PARTY_AUTHOR, raw_text=party_response
        )
        if is_valid:
            print(f"[Arbiter] Party action accepted. {arbiter_text.strip()}")
            break
        print(f"[Arbiter] Party action REJECTED. {arbiter_text.strip()}")
    else:
        # Retries exhausted: stop the game, the party keeps hallucinating.
        raise GMRetriesExhaustedError(
            actor=PARTY_AUTHOR,
            last_text=party_response,
            last_reason=arbiter_text.strip(),
        )

    # ---- 2. Narrator narrates (with retries on invalidation) ------------
    narration = ""
    arbiter_text = ""
    for attempt in range(1, MAX_RETRIES + 1):
        narration = narrate(gm.narrator_chat, gm.memory_path)
        print(f"\nNarrator (attempt {attempt}): {narration}\n")

        is_valid, arbiter_text = _ingest_with_arbitration(
            gm, author="narrator", raw_text=narration
        )
        if is_valid:
            print(f"[Arbiter] Narration accepted. {arbiter_text.strip()}")
            return narration
        print(f"[Arbiter] Narration REJECTED. {arbiter_text.strip()}")

    # Retries exhausted: stop the game, the narrator keeps hallucinating.
    raise GMRetriesExhaustedError(
        actor="narrator",
        last_text=narration,
        last_reason=arbiter_text.strip(),
    )
